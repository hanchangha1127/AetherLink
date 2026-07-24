#!/usr/bin/env python3
"""Synthetic tests for the one-use SumDB identity resolver."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (sys.flags.isolated and sys.flags.dont_write_bytecode and sys.flags.no_site):
    raise RuntimeError("tests require `python3 -I -B -S`")

import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock


PATH = Path(__file__).with_name(
    "resolve_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location("sumdb_identity_runner_v1", PATH)
assert SPEC and SPEC.loader
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


def leaf_hash(payload: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + payload).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def tree_hash(hashes: list[bytes], start: int, count: int) -> bytes:
    if count == 1:
        return hashes[start]
    split = 1 << ((count - 1).bit_length() - 1)
    return node_hash(
        tree_hash(hashes, start, split),
        tree_hash(hashes, start + split, count - split),
    )


def direct_expr(expr, hashes):
    if expr[0] == "node":
        level, index = expr[1], expr[2]
        count = 1 << level
        return tree_hash(hashes, index * count, count)
    return node_hash(
        direct_expr(expr[1], hashes),
        direct_expr(expr[2], hashes),
    )


def custom_plan(old_size: int, new_size: int, record_number: int):
    inclusion = R.inclusion_exprs(record_number, new_size)
    consistency = R.consistency_exprs(old_size, new_size)
    nodes = set()
    for expr in (*inclusion, *consistency):
        nodes |= R.expr_nodes(expr)
    specs = {
        node: R.tile_spec_for_node(*node, new_size)
        for node in nodes
    }
    tiles = {}
    for spec in specs.values():
        tiles[spec["path"]] = {
            key: spec[key]
            for key in (
                "path",
                "tileLevel",
                "tileIndex",
                "width",
                "expectedBytes",
            )
        }
    return {
        "inclusionExpressions": inclusion,
        "consistencyExpressions": consistency,
        "nodeSpecs": specs,
        "tiles": sorted(
            tiles.values(),
            key=lambda row: (
                row["tileLevel"],
                row["tileIndex"],
                row["width"],
            ),
        ),
    }


def synthetic_tile_bodies(plan, hashes, new_size):
    result = {}
    for tile in plan["tiles"]:
        base_level = tile["tileLevel"] * R.TILE_HEIGHT
        subtree_size = 1 << base_level
        start_node = tile["tileIndex"] * R.FULL_TILE_WIDTH
        body = []
        for node in range(start_node, start_node + tile["width"]):
            body.append(
                tree_hash(
                    hashes,
                    node * subtree_size,
                    subtree_size,
                )
            )
        result[tile["path"]] = b"".join(body)
    return result


def synthetic_signed_tree_note(
    tree_size: int,
    root: bytes,
    seed: bytes = b"AetherLink synthetic SumDB seed!",
):
    self_check = R.PERMIT.DECISION.RUNG2
    expanded = hashlib.sha512(seed).digest()
    scalar_bytes = bytearray(expanded[:32])
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 63
    scalar_bytes[31] |= 64
    scalar = int.from_bytes(scalar_bytes, "little")
    public = self_check.ed25519_encode_point(
        self_check.ed25519_scalar_multiply(
            scalar,
            self_check.ED25519_BASE,
        )
    )
    key_payload = b"\x01" + public
    key_hash = hashlib.sha256(
        b"sum.golang.org\n" + key_payload
    ).digest()[:4]
    signed_text = (
        b"go.sum database tree\n"
        + str(tree_size).encode()
        + b"\n"
        + base64.b64encode(root)
        + b"\n"
    )
    nonce = int.from_bytes(
        hashlib.sha512(expanded[32:] + signed_text).digest(),
        "little",
    ) % self_check.ED25519_L
    encoded_nonce = self_check.ed25519_encode_point(
        self_check.ed25519_scalar_multiply(
            nonce,
            self_check.ED25519_BASE,
        )
    )
    challenge = int.from_bytes(
        hashlib.sha512(encoded_nonce + public + signed_text).digest(),
        "little",
    ) % self_check.ED25519_L
    signature = encoded_nonce + (
        (nonce + challenge * scalar) % self_check.ED25519_L
    ).to_bytes(32, "little")
    verifier_key = (
        "sum.golang.org+"
        + key_hash.hex()
        + "+"
        + base64.b64encode(key_payload).decode()
    )
    note = (
        signed_text
        + b"\n\xe2\x80\x94 sum.golang.org "
        + base64.b64encode(key_hash + signature)
        + b"\n"
    )
    return verifier_key, note


class SumDbIdentityResolverV1Tests(unittest.TestCase):
    def test_01_pinned_old_signed_note_verifies(self) -> None:
        signed_text = (
            "go.sum database tree\n"
            f"{R.OLD_TREE_SIZE}\n"
            f"{R.PERMIT.DECISION.OLD_ROOT_HASH_BASE64}\n"
        ).encode()
        note = (
            signed_text
            + b"\n\xe2\x80\x94 sum.golang.org "
            + R.PERMIT.DECISION.OLD_SIGNATURE_BASE64.encode()
            + b"\n"
        )
        parsed = R.verify_signed_note(note)
        self.assertEqual(parsed["treeSize"], R.OLD_TREE_SIZE)
        self.assertEqual(parsed["root"], R.OLD_ROOT)

    def synthetic_lookup(self) -> bytes:
        zip_h1 = "h1:" + base64.b64encode(bytes(range(32))).decode()
        signed_text = (
            "go.sum database tree\n"
            f"{R.OLD_TREE_SIZE}\n"
            f"{R.PERMIT.DECISION.OLD_ROOT_HASH_BASE64}\n"
        ).encode()
        note = (
            signed_text
            + b"\n\xe2\x80\x94 sum.golang.org "
            + R.PERMIT.DECISION.OLD_SIGNATURE_BASE64.encode()
            + b"\n"
        )
        record = (
            f"0\n{R.TARGET_MODULE} {R.TARGET_VERSION} {zip_h1}\n"
            f"{R.TARGET_MODULE} {R.TARGET_VERSION}/go.mod "
            f"{R.TARGET_MOD_H1}\n\n"
        ).encode()
        return record + note

    def test_02_strict_lookup_parses_exact_two_line_record(self) -> None:
        parsed = R.parse_lookup_response(self.synthetic_lookup())
        self.assertEqual(parsed["recordNumber"], 0)
        self.assertEqual(parsed["treeSize"], R.OLD_TREE_SIZE)
        self.assertEqual(parsed["goModH1"], R.TARGET_MOD_H1)
        self.assertEqual(len(R.decode_h1(parsed["moduleZipH1"], "test")), 32)

    def test_03_lookup_rejects_extra_empty_wrong_and_cr_records(self) -> None:
        raw = self.synthetic_lookup()
        separator = raw.index(b"\n\n")
        record = raw[:separator]
        note = raw[separator + 2 :]
        mutations = (
            record + b"\nunrelated.example/x v1.0.0 h1:bad\n\n" + note,
            b"\n\n" + note,
            record.replace(R.TARGET_MOD_H1.encode(), b"h1:bad") + b"\n\n" + note,
            raw.replace(b"\n", b"\r\n", 1),
            raw + b"x",
        )
        for changed in mutations:
            with self.assertRaises(R.ResolverError):
                R.parse_lookup_response(changed)

    def test_04a_signed_note_and_record_number_mutations_fail(self) -> None:
        raw = self.synthetic_lookup()
        separator = raw.index(b"\n\n")
        record = raw[:separator]
        note = raw[separator + 2 :]
        signature_prefix = b"\xe2\x80\x94 sum.golang.org "
        signature_start = note.index(signature_prefix) + len(signature_prefix)
        signature_end = note.index(b"\n", signature_start)
        signature = base64.b64decode(
            note[signature_start:signature_end],
            validate=True,
        )
        mutated_signature = (
            signature[:-1] + bytes([signature[-1] ^ 1])
        )
        bad_signature_note = (
            note[:signature_start]
            + base64.b64encode(mutated_signature)
            + note[signature_end:]
        )
        mutations = (
            record + b"\n\n" + bad_signature_note,
            raw.replace(
                R.PERMIT.DECISION.OLD_ROOT_HASH_BASE64.encode(),
                base64.b64encode(b"\x00" * 32),
                1,
            ),
            raw.replace(
                str(R.OLD_TREE_SIZE).encode(),
                str(R.OLD_TREE_SIZE + 1).encode(),
                1,
            ),
            raw.replace(b"0\n", f"{R.OLD_TREE_SIZE}\n".encode(), 1),
        )
        for changed in mutations:
            with self.assertRaises(R.ResolverError):
                R.parse_lookup_response(changed)

    def test_04_tree_size_is_bounded_before_proof_planning(self) -> None:
        raw = self.synthetic_lookup()
        changed = raw.replace(
            str(R.OLD_TREE_SIZE).encode(),
            str(2**62 + 1).encode(),
            1,
        )
        with self.assertRaises(R.ResolverError):
            R.parse_lookup_response(changed)

    def test_05_stored_hash_index_split_round_trips(self) -> None:
        expected = (
            (0, 0),
            (0, 1),
            (1, 0),
            (0, 2),
            (0, 3),
            (1, 1),
            (2, 0),
        )
        self.assertEqual(
            tuple(R.split_stored_hash_index(index) for index in range(7)),
            expected,
        )
        for index in range(10_000):
            level, node = R.split_stored_hash_index(index)
            self.assertEqual(R.stored_hash_index(level, node), index)

    def test_06_tile_paths_are_canonical_and_round_trip(self) -> None:
        cases = (
            (0, 0, 256, "/tile/8/0/000"),
            (0, 1, 1, "/tile/8/0/001.p/1"),
            (1, 1234, 255, "/tile/8/1/x001/234.p/255"),
            (
                2,
                1_002_003,
                17,
                "/tile/8/2/x001/x002/003.p/17",
            ),
        )
        for level, index, width, path in cases:
            self.assertEqual(R.encode_tile_path(level, index, width), path)
            self.assertEqual(
                R.parse_tile_path(path),
                (level, index, width),
            )
        for invalid in (
            "/tile/8/00/000",
            "/tile/8/0/00",
            "/tile/8/0/x000/001",
            "/tile/8/0/000.p/0",
            "/tile/8/0/000.p/256",
            "/tile/8/0/000?x=1",
        ):
            with self.assertRaises(R.ResolverError):
                R.parse_tile_path(invalid)

    def test_07_tile_mapping_matches_synthetic_full_tree(self) -> None:
        for size, record, old in (
            (3, 1, 1),
            (255, 200, 128),
            (256, 17, 255),
            (257, 256, 256),
            (513, 300, 257),
        ):
            payloads = [f"leaf-{index}\n".encode() for index in range(size)]
            hashes = [leaf_hash(payload) for payload in payloads]
            plan = custom_plan(old, size, record)
            tiles = synthetic_tile_bodies(plan, hashes, size)
            inclusion = [
                R.evaluate_expr(expr, plan["nodeSpecs"], tiles)
                for expr in plan["inclusionExpressions"]
            ]
            consistency = [
                R.evaluate_expr(expr, plan["nodeSpecs"], tiles)
                for expr in plan["consistencyExpressions"]
            ]
            root = tree_hash(hashes, 0, size)
            old_root = tree_hash(hashes, 0, old)
            R.verify_inclusion(payloads[record], record, size, inclusion, root)
            R.verify_consistency(old, size, old_root, root, consistency)

    def test_08_consistency_is_exhaustive_for_small_trees(self) -> None:
        payloads = [f"entry-{index}\n".encode() for index in range(64)]
        hashes = [leaf_hash(payload) for payload in payloads]
        for new_size in range(1, 65):
            new_root = tree_hash(hashes, 0, new_size)
            for old_size in range(1, new_size + 1):
                old_root = tree_hash(hashes, 0, old_size)
                proof = [
                    direct_expr(expr, hashes)
                    for expr in R.consistency_exprs(old_size, new_size)
                ]
                R.verify_consistency(
                    old_size,
                    new_size,
                    old_root,
                    new_root,
                    proof,
                )

    def test_09_consistency_rejects_mutated_short_and_extra(self) -> None:
        payloads = [f"entry-{index}\n".encode() for index in range(37)]
        hashes = [leaf_hash(payload) for payload in payloads]
        proof = [
            direct_expr(expr, hashes)
            for expr in R.consistency_exprs(13, 37)
        ]
        old_root = tree_hash(hashes, 0, 13)
        new_root = tree_hash(hashes, 0, 37)
        mutations = [
            proof[:-1],
            proof + [b"\x00" * 32],
            [b"\x00" * 32, *proof[1:]],
        ]
        for changed in mutations:
            with self.assertRaises(R.ResolverError):
                R.verify_consistency(
                    13,
                    37,
                    old_root,
                    new_root,
                    changed,
                )

    def test_10_equal_tree_requires_root_and_empty_delta(self) -> None:
        root = hashlib.sha256(b"root").digest()
        R.verify_consistency(10, 10, root, root, [])
        for other, proof in (
            (hashlib.sha256(b"other").digest(), []),
            (root, [b"\x00" * 32]),
        ):
            with self.assertRaises(R.ResolverError):
                R.verify_consistency(10, 10, root, other, proof)

    def test_11_url_validation_allows_only_lookup_and_hash_tiles(self) -> None:
        for url in (
            R.LOOKUP_URL,
            "https://sum.golang.org/tile/8/0/000",
            "https://sum.golang.org/tile/8/1/x001/234.p/17",
        ):
            R.validate_request_url(url)
        for url in (
            "http://sum.golang.org/tile/8/0/000",
            "https://sum.golang.org/latest",
            "https://sum.golang.org/tile/8/data/000",
            "https://sum.golang.org/tile/8/0/000?x=1",
            "https://proxy.golang.org/github.com/kr/pty/@v/v1.1.1.zip",
        ):
            with self.assertRaises(R.ResolverError):
                R.validate_request_url(url)

    def test_12_runner_reverse_pins_checker_and_normalized_hash(self) -> None:
        runner_raw = PATH.read_bytes()
        checker_raw = R.PERMIT_CHECKER_PATH.read_bytes()
        self.assertEqual(
            R.EXPECTED_PERMIT_CHECKER_RAW,
            hashlib.sha256(checker_raw).hexdigest(),
        )
        self.assertEqual(
            hashlib.sha256(
                R.PERMIT.normalized_runner_bytes(runner_raw)
            ).hexdigest(),
            R.PERMIT.EXPECTED_RUNNER_NORMALIZED_SHA256,
        )
        R.PERMIT.validate_runner_semantics(runner_raw, checker_raw)

    def test_13_direct_transport_and_durable_claim_surface(self) -> None:
        source = PATH.read_text()
        for required in (
            "http.client.HTTPSConnection",
            "ssl.create_default_context",
            "body=None",
            "encode_chunked=False",
            "os.O_EXCL",
            'getattr(os, "O_NOFOLLOW", 0)',
            "os.fsync",
            "renameatx_np",
            "signal.setitimer",
            "os.umask(0o077)",
        ):
            self.assertIn(required, source)
        for forbidden in (
            "ProxyHandler",
            "urlopen",
            "subprocess",
            "shutil.rmtree",
            "proxy.golang.org",
            'ResolverError(f"E_RENAME_',
        ):
            self.assertNotIn(forbidden, source)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-S", str(PATH), *args],
            cwd=R.ROOT,
            capture_output=True,
            check=False,
        )

    def test_14_cli_preflight_and_invalid_are_canonical(self) -> None:
        preflight = self.run_cli("--preflight")
        self.assertEqual(preflight.returncode, 0)
        value = json.loads(preflight.stdout)
        self.assertEqual(
            value["status"],
            "preflight_passed_no_network_no_writes",
        )
        self.assertEqual(value["networkRequestAttemptCount"], 0)
        invalid = self.run_cli("--secret")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stderr, b"")
        self.assertNotIn(b"secret", invalid.stdout)

    def test_15_proof_bundle_rejects_missing_tile(self) -> None:
        size, old, record = 300, 257, 123
        payloads = [f"leaf-{index}\n".encode() for index in range(size)]
        hashes = [leaf_hash(payload) for payload in payloads]
        plan = custom_plan(old, size, record)
        tiles = synthetic_tile_bodies(plan, hashes, size)
        tiles.pop(next(iter(tiles)))
        expr = next(iter(plan["inclusionExpressions"]))
        with self.assertRaises(R.ResolverError):
            R.evaluate_expr(expr, plan["nodeSpecs"], tiles)

    class FakeResponse:
        def __init__(
            self,
            body=b"abc",
            status=200,
            headers=None,
        ):
            self.body = body
            self.offset = 0
            self.status = status
            self.headers = (
                [("Content-Length", str(len(body)))]
                if headers is None
                else headers
            )

        def getheaders(self):
            return list(self.headers)

        def getheader(self, name):
            values = [
                value
                for key, value in self.headers
                if key.lower() == name.lower()
            ]
            return values[0] if values else None

        def read(self, size):
            chunk = self.body[self.offset : self.offset + size]
            self.offset += len(chunk)
            return chunk

        def close(self):
            pass

    class FakeConnection:
        instances = []
        response_factory = None

        def __init__(self, host, port, timeout, context):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.context = context
            self.requests = []
            type(self).instances.append(self)

        def request(self, method, path, body, headers, encode_chunked):
            self.requests.append(
                {
                    "method": method,
                    "path": path,
                    "body": body,
                    "headers": dict(headers),
                    "encode_chunked": encode_chunked,
                }
            )

        def getresponse(self):
            return type(self).response_factory()

        def close(self):
            pass

    def fake_direct_fetch(self, response_factory, maximum=64):
        self.FakeConnection.instances = []
        self.FakeConnection.response_factory = response_factory
        with mock.patch.object(
            R.http.client,
            "HTTPSConnection",
            self.FakeConnection,
        ), mock.patch.object(
            R.ssl,
            "create_default_context",
            return_value=object(),
        ):
            return R.direct_fetch(
                R.LOOKUP_URL,
                maximum,
                time.monotonic() + 100,
            )

    def test_16_direct_https_request_is_exact_and_attempted_once(self) -> None:
        self.assertEqual(
            self.fake_direct_fetch(lambda: self.FakeResponse()),
            b"abc",
        )
        self.assertEqual(len(self.FakeConnection.instances), 1)
        connection = self.FakeConnection.instances[0]
        self.assertEqual(connection.host, "sum.golang.org")
        self.assertEqual(connection.port, 443)
        self.assertLessEqual(connection.timeout, 15)
        self.assertEqual(len(connection.requests), 1)
        request = connection.requests[0]
        self.assertEqual(request["method"], "GET")
        self.assertEqual(
            request["path"],
            "/lookup/github.com/kr/pty@v1.1.1",
        )
        self.assertIsNone(request["body"])
        self.assertFalse(request["encode_chunked"])
        self.assertFalse(
            {"authorization", "proxy-authorization", "cookie", "range"}
            & {key.lower() for key in request["headers"]}
        )

    def test_17_direct_https_rejects_response_policy_drift_no_retry(self) -> None:
        cases = (
            lambda: self.FakeResponse(status=302),
            lambda: self.FakeResponse(headers=[("WWW-Authenticate", "x")]),
            lambda: self.FakeResponse(headers=[("Set-Cookie", "x")]),
            lambda: self.FakeResponse(headers=[("Content-Encoding", "gzip")]),
            lambda: self.FakeResponse(
                headers=[("X-Large", "x" * (R.MAXIMUM_HEADER_BYTES + 1))]
            ),
            lambda: self.FakeResponse(
                body=b"abc",
                headers=[("Content-Length", "2")],
            ),
            lambda: self.FakeResponse(body=b"abcde"),
        )
        for factory in cases:
            with self.subTest(factory=factory):
                with self.assertRaises(R.ResolverError):
                    self.fake_direct_fetch(factory, maximum=4)
                self.assertEqual(len(self.FakeConnection.instances), 1)
                self.assertEqual(
                    len(self.FakeConnection.instances[0].requests),
                    1,
                )

    def test_17a_slow_drip_is_stopped_by_absolute_request_timer(self) -> None:
        class SlowResponse(self.FakeResponse):
            def read(self, size):
                time.sleep(0.2)
                return super().read(size)

        started = time.monotonic()
        with mock.patch.object(
            R,
            "PER_REQUEST_TIMEOUT_SECONDS",
            0.05,
        ):
            with self.assertRaises(R.ResolverError) as rejected:
                self.fake_direct_fetch(
                    lambda: SlowResponse(body=b"abc"),
                    maximum=4,
                )
        self.assertEqual(rejected.exception.code, "E_DEADLINE")
        self.assertEqual(rejected.exception.phase, "network")
        self.assertLess(time.monotonic() - started, 0.15)

    def make_temp_runtime(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        dependency = root / R.PERMIT.DEPENDENCY_ROOT
        dependency.mkdir(parents=True)
        os.chmod(dependency, 0o700)
        (root / R.PERMIT.RECEIPT_PATH).parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        binding = {
            "permit": {
                "path": R.PERMIT.PERMIT_PATH,
                "rawSha256": "a" * 64,
                "contentSha256": "b" * 64,
            },
            "checker": {
                "path": R.PERMIT.THIS_CHECKER_PATH,
                "rawSha256": "c" * 64,
            },
            "runner": {
                "path": R.PERMIT.RUNNER_PATH,
                "rawSha256": "d" * 64,
            },
        }
        preflight = lambda: {
            "status": "preflight_passed_no_network_no_writes",
            "permitContentSha256": "b" * 64,
            "authorityBinding": binding,
            "networkRequestAttemptCount": 0,
            "fileWriteCount": 0,
            "sourceAcquisitionCount": 0,
        }
        return temporary, root, preflight

    def test_18_synthetic_success_fsm_claims_before_lookup_and_publishes(self) -> None:
        temporary, root, preflight = self.make_temp_runtime()
        self.addCleanup(temporary.cleanup)
        calls = []
        tile_path = "/tile/8/0/000.p/1"

        def fetch(url, maximum, deadline):
            self.assertTrue((root / R.PERMIT.CLAIM_PATH).exists())
            calls.append(url)
            return b"lookup" if len(calls) == 1 else b"x" * 32

        synthetic_h1 = "h1:" + base64.b64encode(b"z" * 32).decode()
        lookup = {
            "recordNumber": 0,
            "recordPayload": b"record\n",
            "recordLeafHash": b"l" * 32,
            "moduleZipH1": synthetic_h1,
            "goModH1": R.TARGET_MOD_H1,
            "treeSize": 2,
            "root": b"r" * 32,
            "rootHashBase64": base64.b64encode(b"r" * 32).decode(),
            "signatureBase64": base64.b64encode(b"s" * 68).decode(),
            "signedTreeTextSha256": "e" * 64,
        }
        plan = {
            "inclusionExpressions": [],
            "consistencyExpressions": [],
            "nodeSpecs": {},
            "tiles": [
                {
                    "path": tile_path,
                    "tileLevel": 0,
                    "tileIndex": 0,
                    "width": 1,
                    "expectedBytes": 32,
                }
            ],
        }
        terminal_order = []

        def terminal_writer(path, payload):
            terminal_order.append(path)
            return R.write_terminal_at(root, path, payload)

        def rename_fn(src_fd, src, dst_fd, dst):
            os.rename(src, dst, src_dir_fd=src_fd, dst_dir_fd=dst_fd)

        result = R._execute_attempt(
            fetch,
            time.monotonic() + 30,
            root=root,
            preflight_fn=preflight,
            rename_fn=rename_fn,
            terminal_writer=terminal_writer,
            parse_lookup_fn=lambda raw: lookup,
            derive_plan_fn=lambda record, size: plan,
            verify_bundle_fn=lambda lookup, plan, tiles: {
                "inclusionProofHashCount": 1,
                "consistencyProofHashCount": 1,
                "inclusionProofHashesBase64": [
                    base64.b64encode(b"i" * 32).decode()
                ],
                "consistencyProofHashesBase64": [
                    base64.b64encode(b"c" * 32).decode()
                ],
                "canonicalProofBundleSha256": "f" * 64,
                "recordInclusionVerified": True,
                "oldToNewConsistencyVerified": True,
            },
            old_tree_size=1,
            old_root=b"o" * 32,
        )
        self.assertTrue(result["moduleZipH1Resolved"])
        self.assertEqual(calls, [R.LOOKUP_URL, f"https://{R.LOOKUP_HOST}{tile_path}"])
        self.assertTrue((root / R.PERMIT.CLAIM_PATH).exists())
        evidence = root / R.PERMIT.FINAL_EVIDENCE_PATH
        self.assertEqual(
            sorted(path.name for path in evidence.iterdir()),
            [
                "evidence.json",
                "lookup.response",
                next(
                    path.name
                    for path in evidence.iterdir()
                    if path.name.startswith("tile-")
                ),
            ],
        )
        self.assertEqual(
            terminal_order,
            [R.PERMIT.RECEIPT_PATH, R.PERMIT.MANIFEST_PATH],
        )
        self.assertFalse((root / R.PERMIT.FAILURE_PATH).exists())
        previous_calls = len(calls)
        with self.assertRaises(R.ResolverError):
            R._execute_attempt(
                fetch,
                time.monotonic() + 30,
                root=root,
                preflight_fn=preflight,
                rename_fn=rename_fn,
                terminal_writer=terminal_writer,
            )
        self.assertEqual(len(calls), previous_calls)

    def test_18a_signed_small_tree_end_to_end_publication(self) -> None:
        temporary, root, preflight = self.make_temp_runtime()
        self.addCleanup(temporary.cleanup)
        old_size = 3
        new_size = 5
        record_number = 4
        zip_h1 = "h1:" + base64.b64encode(b"z" * 32).decode()
        record_payload = (
            f"{R.TARGET_MODULE} {R.TARGET_VERSION} {zip_h1}\n"
            f"{R.TARGET_MODULE} {R.TARGET_VERSION}/go.mod "
            f"{R.TARGET_MOD_H1}\n"
        ).encode()
        records = [b"a\n", b"b\n", b"c\n", b"d\n", record_payload]
        hashes = [leaf_hash(record) for record in records]
        old_root = tree_hash(hashes, 0, old_size)
        new_root = tree_hash(hashes, 0, new_size)
        verifier_key, note = synthetic_signed_tree_note(new_size, new_root)
        lookup_raw = str(record_number).encode() + b"\n" + record_payload + b"\n" + note
        calls = []

        with mock.patch.object(
            R.PERMIT.DECISION,
            "SUMDB_VERIFIER_KEY",
            verifier_key,
        ), mock.patch.object(
            R,
            "OLD_TREE_SIZE",
            old_size,
        ), mock.patch.object(
            R,
            "OLD_ROOT",
            old_root,
        ):
            plan = R.derive_tile_plan(record_number, new_size)
            tile_bodies = synthetic_tile_bodies(plan, hashes, new_size)

            def fetch(url, maximum, deadline):
                self.assertTrue((root / R.PERMIT.CLAIM_PATH).exists())
                calls.append(url)
                if url == R.LOOKUP_URL:
                    return lookup_raw
                path = url.removeprefix(f"https://{R.LOOKUP_HOST}")
                return tile_bodies[path]

            result = R._execute_attempt(
                fetch,
                time.monotonic() + 30,
                root=root,
                preflight_fn=preflight,
                rename_fn=lambda src_fd, src, dst_fd, dst: os.rename(
                    src,
                    dst,
                    src_dir_fd=src_fd,
                    dst_dir_fd=dst_fd,
                ),
                terminal_writer=lambda path, payload: R.write_terminal_at(
                    root,
                    path,
                    payload,
                ),
                old_tree_size=old_size,
                old_root=old_root,
            )
        self.assertTrue(result["moduleZipH1Resolved"])
        self.assertEqual(len(calls), 1 + len(plan["tiles"]))
        evidence = json.loads(
            (
                root
                / R.PERMIT.FINAL_EVIDENCE_PATH
                / "evidence.json"
            ).read_bytes()
        )
        self.assertTrue(evidence["proof"]["recordInclusionVerified"])
        self.assertTrue(evidence["proof"]["oldToNewConsistencyVerified"])
        self.assertEqual(evidence["target"]["moduleZipH1"], zip_h1)

    def test_19_post_claim_failure_consumes_and_retains_staging(self) -> None:
        temporary, root, preflight = self.make_temp_runtime()
        self.addCleanup(temporary.cleanup)
        calls = 0

        def fetch(url, maximum, deadline):
            nonlocal calls
            calls += 1
            self.assertTrue((root / R.PERMIT.CLAIM_PATH).exists())
            raise R.ResolverError("E_SYNTHETIC", "lookup")

        with self.assertRaises(R.ResolverError):
            R._execute_attempt(
                fetch,
                time.monotonic() + 30,
                root=root,
                preflight_fn=preflight,
                rename_fn=lambda *args: None,
                terminal_writer=lambda path, payload: R.write_terminal_at(
                    root,
                    path,
                    payload,
                ),
            )
        self.assertEqual(calls, 1)
        self.assertTrue((root / R.PERMIT.CLAIM_PATH).exists())
        self.assertTrue((root / R.PERMIT.FAILURE_PATH).exists())
        self.assertFalse((root / R.PERMIT.RECEIPT_PATH).exists())
        self.assertFalse((root / R.PERMIT.MANIFEST_PATH).exists())
        staging = [
            path
            for path in (root / R.PERMIT.DEPENDENCY_ROOT).iterdir()
            if path.name.startswith(R.PERMIT.STAGING_PREFIX)
        ]
        self.assertEqual(len(staging), 1)
        with self.assertRaises(R.ResolverError):
            R._execute_attempt(
                fetch,
                time.monotonic() + 30,
                root=root,
                preflight_fn=preflight,
                rename_fn=lambda *args: None,
                terminal_writer=lambda path, payload: R.write_terminal_at(
                    root,
                    path,
                    payload,
                ),
            )
        self.assertEqual(calls, 1)

    def test_20_expired_deadline_fails_before_claim_or_fetch(self) -> None:
        temporary, root, preflight = self.make_temp_runtime()
        self.addCleanup(temporary.cleanup)
        calls = 0

        def fetch(url, maximum, deadline):
            nonlocal calls
            calls += 1
            return b""

        with self.assertRaises(R.ResolverError) as rejected:
            R._execute_attempt(
                fetch,
                time.monotonic() - 1,
                root=root,
                preflight_fn=preflight,
            )
        self.assertEqual(rejected.exception.code, "E_DEADLINE")
        self.assertEqual(calls, 0)
        self.assertFalse((root / R.PERMIT.CLAIM_PATH).exists())

    def test_21_execute_sets_and_restores_umask_077(self) -> None:
        def observed_umask():
            current = os.umask(0)
            os.umask(current)
            return current

        before = observed_umask()
        during = []

        def attempt(fetch, deadline):
            during.append(observed_umask())
            return {"status": "synthetic"}

        with mock.patch.object(R, "_execute_attempt", side_effect=attempt):
            self.assertEqual(R.execute(), {"status": "synthetic"})
        self.assertEqual(during, [0o077])
        self.assertEqual(observed_umask(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
