#!/usr/bin/env python3
"""Tests for the one-use offline Wave18 acquisition readback recorder."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("tests require `python3 -I -B -S`")

import ast
import hashlib
import http.client
import importlib.util
import io
import json
import copy
import errno
import os
from pathlib import Path
import re
import runpy
import socket
import stat
import tempfile
import threading
import unittest
from unittest import mock
import unicodedata
import warnings
import zipfile


NETWORK_ATTEMPTS: list[str] = []


def _deny_test_network(*_args, **_kwargs):
    NETWORK_ATTEMPTS.append("network")
    raise AssertionError(
        "offline Wave18 readback tests must never create network connections"
    )


http.client.HTTPSConnection = _deny_test_network
socket.create_connection = _deny_test_network


PATH = Path(__file__).with_name(
    "record_p2p_nat_g2_pion_rung3_dependency_wave18_readback_v1_once.py"
)
PRELOAD_ROOT = Path(__file__).resolve().parents[1]
PRELOAD_PERMIT_PATH = (
    PRELOAD_ROOT
    / "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave18-"
    "readback-execution-permit-v1.json"
)
PRELOAD_TOOL_PATHS = [
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave18_"
        "readback_execution_permit_v1.py"
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave18_"
        "readback_execution_permit_v1.py"
    ),
    (
        "script/record_p2p_nat_g2_pion_rung3_dependency_wave18_"
        "readback_v1_once.py"
    ),
    (
        "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave18_"
        "readback_v1_once.py"
    ),
]


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def _strict_canonical_permit(raw: bytes) -> dict[str, object]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AssertionError("duplicate permit JSON key")
            result[key] = value
        return result

    def reject_non_integer(_):
        raise AssertionError("non-integer permit JSON number")

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=reject_non_integer,
            parse_constant=reject_non_integer,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AssertionError("invalid permit JSON") from error
    if type(value) is not dict or raw != _canonical_json_bytes(value):
        raise AssertionError("permit JSON is not strict canonical JSON")
    binding = value.get("contentBinding")
    unbound = dict(value)
    unbound.pop("contentBinding", None)
    expected_binding = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": hashlib.sha256(
            _canonical_json_bytes(unbound)
        ).hexdigest(),
    }
    if (
        type(binding) is not dict
        or set(binding) != {"algorithm", "sha256"}
        or binding != expected_binding
    ):
        raise AssertionError("permit content binding mismatch")
    tools = value.get("toolBindings")
    if (
        type(tools) is not list
        or len(tools) != len(PRELOAD_TOOL_PATHS)
        or any(
            type(row) is not dict
            or set(row) != {"path", "rawSha256"}
            or type(row["path"]) is not str
            or type(row["rawSha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", row["rawSha256"]) is None
            for row in tools
        )
        or [row["path"] for row in tools] != PRELOAD_TOOL_PATHS
        or len({row["path"] for row in tools}) != len(PRELOAD_TOOL_PATHS)
    ):
        raise AssertionError("permit tool bindings are not exact")
    return value


def _require_subject_raw_and_normalized_seal(
    permit: dict[str, object],
    subject_path: str,
    subject_raw: bytes,
    subject_normalized: bytes,
) -> None:
    tools = permit["toolBindings"]
    matches = [row for row in tools if row["path"] == subject_path]
    if (
        len(matches) != 1
        or matches[0]["rawSha256"]
        != hashlib.sha256(subject_raw).hexdigest()
        or type(permit.get("recorderNormalizedSha256")) is not str
        or permit["recorderNormalizedSha256"]
        != hashlib.sha256(subject_normalized).hexdigest()
    ):
        raise AssertionError("recorder preload raw/normalized seal mismatch")


def _dotted_call_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _canonical_call_surface(raw: bytes) -> tuple[dict[str, int], str]:
    tree = ast.parse(raw.decode("utf-8", errors="strict"))
    calls: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted_call_name(node.func)
            if name is not None:
                calls[name] = calls.get(name, 0) + 1
    digest = hashlib.sha256(
        (
            json.dumps(
                calls,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
    ).hexdigest()
    return calls, digest


RECORDER_CALL_SURFACE_SHA256 = (
    "a758f79bea56fab79178ff611d80575fe31a97f0ac9848d42ea78c52541b0fa7"
)


def _require_call_surface(raw: bytes, expected_digest: str) -> dict[str, int]:
    calls, digest = _canonical_call_surface(raw)
    if digest != expected_digest:
        raise AssertionError("canonical AST call-surface digest mismatch")
    return calls


def _recorder_ast_gate(raw: bytes) -> bytes:
    tree = ast.parse(raw.decode("utf-8", errors="strict"))
    calls = _require_call_surface(raw, RECORDER_CALL_SURFACE_SHA256)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    expected_imports = {
        "__future__",
        "sys",
        "argparse",
        "base64",
        "binascii",
        "ctypes",
        "errno",
        "hashlib",
        "io",
        "json",
        "os",
        "pathlib",
        "re",
        "secrets",
        "signal",
        "stat",
        "struct",
        "types",
        "typing",
        "unicodedata",
        "zipfile",
        "zlib",
    }
    if len(imports) != len(expected_imports) or set(imports) != expected_imports:
        raise AssertionError("recorder preload import gate failed")
    exact_calls = {
        "compile": 1,
        "exec": 1,
        "load_readback_checker": 1,
        "PERMIT.package_preflight_for_recorder": 1,
        "create_readback_claim": 1,
        "verify_snapshot": 2,
        "validate_mod": 1,
        "validate_zip": 1,
        "atomic_publish": 2,
        "preflight": 2,
        "execute": 1,
        "validate_argument_vector": 1,
    }
    if any(calls.get(name, 0) != count for name, count in exact_calls.items()):
        raise AssertionError("recorder preload exact call gate failed")
    forbidden_fragments = (
        "input",
        "getpass",
        "socket",
        "subprocess",
        "urlopen",
        "HTTPConnection",
        "HTTPSConnection",
        "create_connection",
        "check_p2p_nat_g2_pion_rung3_dependency_wave18_acquisition",
        "acquire_p2p_nat_g2_pion_rung3_dependency_wave18",
    )
    if any(
        any(fragment in name for fragment in forbidden_fragments)
        for name in calls
    ):
        raise AssertionError("recorder preload forbidden call gate failed")
    normalized, substitutions = re.subn(
        rb'EXPECTED_READBACK_CHECKER_RAW = "[0-9a-f]{64}"',
        (
            b'EXPECTED_READBACK_CHECKER_RAW = "'
            + (b"0" * 64)
            + b'"'
        ),
        raw,
        count=1,
    )
    if substitutions != 1:
        raise AssertionError("recorder preload normalization gate failed")
    return normalized


def _preload_recorder_gate(
    path: Path,
) -> tuple[bytes, bytes, dict[str, object]]:
    raw = path.read_bytes()
    normalized = _recorder_ast_gate(raw)
    permit = _strict_canonical_permit(PRELOAD_PERMIT_PATH.read_bytes())
    _require_subject_raw_and_normalized_seal(
        permit,
        PRELOAD_TOOL_PATHS[2],
        raw,
        normalized,
    )
    return raw, normalized, permit


(
    RECORDER_PRELOAD_RAW,
    RECORDER_PRELOAD_NORMALIZED,
    RECORDER_PRELOAD_PERMIT,
) = _preload_recorder_gate(PATH)
# The recorder deliberately retains an all-zero reverse pin until the separate
# Wave18 readback checker/permit bytes are frozen. This suite remains sealed
# until that pin is replaced with the finalized checker raw SHA-256.
SPEC = importlib.util.spec_from_file_location("wave18_readback_recorder_tests", PATH)
R = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(R)
if PATH.read_bytes() != RECORDER_PRELOAD_RAW:
    raise AssertionError("recorder changed between preload gate and exec")


def make_zip(
    module: str,
    version: str,
    files: dict[str, bytes],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for relative, body in files.items():
            info = zipfile.ZipInfo(f"{module}@{version}/{relative}")
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = compression
            archive.writestr(info, body)
    return output.getvalue()


class FakeSnapshot:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        events.append("snapshot")

    def refresh(self) -> None:
        self.events.append("refresh")

    def final_barrier(self) -> None:
        self.events.append("barrier")

    def close(self) -> None:
        self.events.append("close")


BARRIER_NAMES = [
    "complete_snapshot_and_claim_immediately_before_receipt",
    "complete_snapshot_claim_and_receipt_after_receipt",
    (
        "complete_snapshot_claim_and_receipt_"
        "immediately_before_manifest_publication"
    ),
]


def fake_preflight(authority=None):
    return {
        "authorityBinding": {} if authority is None else authority,
        "permit": {
            "verificationContract": {
                "retainedFdPreManifestBarriers": list(BARRIER_NAMES),
            }
        },
    }


class FakeNamespace:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.root_fd = -1
        self.owned_fds = []
        events.append("namespace")

    def preclaim_barrier(self) -> None:
        self.events.append("preclaim")

    def hold_claim(self, _claim, _creation_fd) -> None:
        self.events.append("hold_claim")

    def publication_barrier(self, *, receipt_required: bool) -> None:
        self.events.append(
            "namespace_barrier_receipt"
            if receipt_required
            else "namespace_barrier_pre_receipt"
        )

    def close(self) -> None:
        self.events.append("namespace_close")


class Wave18ReadbackRecorderTests(unittest.TestCase):
    def tearDown(self) -> None:
        self.assertEqual(NETWORK_ATTEMPTS, [])

    def test_01_mod_h1_and_quoted_directive_are_independent(self):
        for raw in (
            b"module example.test/a\n",
            b'module "example.test/a"\n',
            b'module "example.test/a" // retained form\n',
        ):
            result = R.validate_mod(raw, "example.test/a")
            expected = R.dirhash_h1(
                [("go.mod", hashlib.sha256(raw).hexdigest())]
            )
            self.assertEqual(result["goModH1"], expected)
        with self.assertRaises(R.ReadbackError):
            R.validate_mod(b"module example.test/b\n", "example.test/a")

    def test_02_zip_h1_prefix_crc_and_mod_parity(self):
        module, version = "example.test/a", "v1.2.3"
        mod = b"module example.test/a\n"
        raw = make_zip(
            module,
            version,
            {"go.mod": mod, "a.txt": b"alpha", "dir/b.txt": b"beta"},
        )
        result = R.validate_zip(raw, module, version, mod)
        rows = [
            (
                f"{module}@{version}/{name}",
                hashlib.sha256(body).hexdigest(),
            )
            for name, body in {
                "go.mod": mod,
                "a.txt": b"alpha",
                "dir/b.txt": b"beta",
            }.items()
        ]
        self.assertEqual(result["moduleZipH1"], R.dirhash_h1(rows))
        self.assertTrue(result["rootGoModPresent"])
        with self.assertRaises(R.ReadbackError):
            R.validate_zip(raw, module, version, mod + b"x")

    def test_02_root_go_mod_is_required_and_exact_true(self):
        snapshot = R.FrozenSnapshot()
        actual_raw = snapshot.raw
        real_validate_zip = R.validate_zip
        try:
            permit_path = (
                R.PERMIT.BASE
                + "/bounded-dependency-source-acquisition-wave18-"
                "execution-permit-v1.json"
            )
            permit = R.strict_json(
                actual_raw(permit_path),
                "permit_fixture",
            )
            resources = permit["requestContract"]["resources"]
            accepted = {
                Path(row["path"]).name: row
                for row in R.PERMIT.ACCEPTED_FILES
            }
            zip_resources = [
                row for row in resources if row["kind"] == "zip"
            ]
            self.assertEqual(
                [row["requestOrdinal"] for row in zip_resources],
                [2, 4, 6],
            )
            for resource in zip_resources:
                mod_resource = next(
                    row
                    for row in resources
                    if row["kind"] == "mod"
                    and row["tupleId"] == resource["tupleId"]
                )
                mod_raw = actual_raw(
                    accepted[mod_resource["acceptedFileName"]]["path"]
                )
                zip_raw = actual_raw(
                    accepted[resource["acceptedFileName"]]["path"]
                )
                prefix = (
                    f"{resource['module']}@{resource['version']}/"
                )
                with zipfile.ZipFile(io.BytesIO(zip_raw), "r") as archive:
                    files = {
                        info.filename[len(prefix) :]: archive.read(info)
                        for info in archive.infolist()
                    }
                self.assertIn("go.mod", files)
                files.pop("go.mod")
                without_root = make_zip(
                    resource["module"],
                    resource["version"],
                    files,
                )
                with self.subTest(
                    ordinal=resource["requestOrdinal"],
                    rootGoModPresent="archive-missing",
                ), self.assertRaises(R.ReadbackError) as caught:
                    R.validate_zip(
                        without_root,
                        resource["module"],
                        resource["version"],
                        mod_raw,
                    )
                self.assertEqual(caught.exception.code, "E_MOD_PARITY")

                for replacement in ("missing", False, 0, None):

                    def altered_root_result(
                        raw,
                        candidate_module,
                        candidate_version,
                        candidate_mod_raw,
                        *,
                        replacement=replacement,
                        target_module=resource["module"],
                    ):
                        result = real_validate_zip(
                            raw,
                            candidate_module,
                            candidate_version,
                            candidate_mod_raw,
                        )
                        if candidate_module == target_module:
                            result = dict(result)
                            if replacement == "missing":
                                result.pop("rootGoModPresent")
                            else:
                                result["rootGoModPresent"] = replacement
                        return result

                    with self.subTest(
                        ordinal=resource["requestOrdinal"],
                        rootGoModPresent=replacement,
                    ), mock.patch.object(
                        R,
                        "validate_zip",
                        side_effect=altered_root_result,
                    ), self.assertRaises(R.ReadbackError) as caught:
                        R.verify_snapshot(snapshot)
                    self.assertEqual(
                        caught.exception.code,
                        "E_MOD_PARITY",
                    )
        finally:
            snapshot.close()

    def test_03_zip_structure_path_mode_and_header_mutations_fail(self):
        module, version = "example.test/a", "v1.0.0"
        mod = b"module example.test/a\n"
        for files in (
            {"go.mod": mod, "../evil": b"x"},
            {"go.mod": mod, "a\\b": b"x"},
            {"go.mod": mod, "a:b": b"x"},
            {"go.mod": mod, "a": b"x", "a/b": b"y"},
            {"go.mod": mod, "Case": b"x", "case": b"y"},
        ):
            with self.subTest(files=files), self.assertRaises(R.ReadbackError):
                R.validate_zip(make_zip(module, version, files), module, version, mod)
        symlink = io.BytesIO()
        with zipfile.ZipFile(symlink, "w") as archive:
            info = zipfile.ZipInfo(f"{module}@{version}/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")
        with self.assertRaises(R.ReadbackError):
            R.validate_zip(symlink.getvalue(), module, version, None)
        raw = bytearray(
            make_zip(module, version, {"go.mod": mod, "a.txt": b"alpha"})
        )
        raw[10:12] = (int.from_bytes(raw[10:12], "little") ^ 1).to_bytes(
            2, "little"
        )
        with self.assertRaises(R.ReadbackError):
            R.validate_zip(bytes(raw), module, version, mod)

    def test_04_zip64_marker_inside_payload_is_not_false_positive(self):
        module, version = "example.test/a", "v1.0.0"
        payload = b"PK\x06\x06" + b"PK\x06\x07"
        raw = make_zip(
            module,
            version,
            {
                "go.mod": b"module example.test/a\n",
                "signature.bin": payload,
            },
            compression=zipfile.ZIP_STORED,
        )
        self.assertEqual(
            R.validate_zip(
                raw,
                module,
                version,
                b"module example.test/a\n",
            )["entryCount"],
            2,
        )

    def test_05_live_retained_snapshot_verifies_twice_read_only(self):
        claim = R.ROOT / R.PERMIT.READBACK_CLAIM_PATH
        receipt = R.ROOT / R.PERMIT.READBACK_RECEIPT_PATH
        manifest = R.ROOT / R.PERMIT.READBACK_MANIFEST_PATH
        self.assertFalse(os.path.lexists(claim))
        snapshot = R.FrozenSnapshot()
        try:
            self.assertTrue(
                all(item.retained_components for item in snapshot.files.values())
            )
            self.assertTrue(
                all(
                    item.retained_components
                    for item in snapshot.directories
                )
            )
            first = R.verify_snapshot(snapshot)
            snapshot.refresh()
            second = R.verify_snapshot(snapshot)
            self.assertEqual(first, second)
            self.assertEqual(
                first["acquisitionAttemptId"],
                "4380f5bbcd3366154b05111381ccab18",
            )
            self.assertEqual(first["acceptedResourceCount"], 6)
            self.assertEqual(first["authorityFileCount"], 15)
            self.assertEqual(first["selectedTupleCount"], 0)
            self.assertEqual(first["selectedRequestOrdinals"], [])
            self.assertEqual(first["aggregateModBytes"], 279)
            self.assertEqual(first["aggregateZipBytes"], 2_108_821)
            self.assertEqual(first["aggregateAcceptedBytes"], 2_109_100)
            self.assertEqual(first["aggregateZipEntryCount"], 971)
            self.assertEqual(
                first["aggregateZipUncompressedBytes"],
                7_225_800,
            )
            self.assertFalse(first["externalAuthenticationRequired"])
            self.assertFalse(first["userActionRequired"])
            self.assertEqual(len(first["resources"]), 6)
            self.assertEqual(
                [row["acceptedFileName"] for row in first["resources"]],
                [
                    "001-bb2025870bcef7a0c287.mod",
                    "001-bb2025870bcef7a0c287.zip",
                    "002-3c84a9eecca520aed886.mod",
                    "002-3c84a9eecca520aed886.zip",
                    "003-4615480e24f0c4184e4c.mod",
                    "003-4615480e24f0c4184e4c.zip",
                ],
            )
            self.assertEqual(
                first["acquisitionClaimRawSha256"],
                "08f5134ce03805e512c2dec0dee13251ce682d793d2b87f7f8e29f6d3426d362",
            )
            self.assertEqual(
                first["evidenceRawSha256"],
                "954d26f4d95a500b1c993b6e4727f787416db866246a009754c8baa1cb7febed",
            )
            self.assertEqual(
                first["acceptedResourceHashSetCanonicalSha256"],
                "757651958dc0538863d7654d59df95a4171cf44fccfa726da87fb0fdf5babc0f",
            )
            self.assertEqual(
                first["acquisitionReceiptRawSha256"],
                "30c703bde55144665117bffcafa0f7fcd1b54c9885acd8fb028adda9339643ca",
            )
            self.assertEqual(
                first["acquisitionManifestRawSha256"],
                "28230bf973cc4346772430080e87c1ac06d0482b9188e072cc75b72020332b7a",
            )
        finally:
            snapshot.close()
        self.assertFalse(os.path.lexists(claim))
        self.assertFalse(os.path.lexists(receipt))
        self.assertFalse(os.path.lexists(manifest))

    def test_05_selector_counts_and_v16_binding_fail_closed(self):
        snapshot = R.FrozenSnapshot()
        permit_path = (
            R.PERMIT.BASE
            + "/bounded-dependency-source-acquisition-wave18-"
            "execution-permit-v1.json"
        )
        actual_raw = snapshot.raw
        original = R.strict_json(actual_raw(permit_path), "permit_fixture")

        def rebound(changed):
            unbound = dict(changed)
            unbound.pop("contentBinding")
            changed["contentBinding"]["sha256"] = R.sha256(
                R.canonical_bytes(unbound)
            )
            return R.canonical_bytes(changed)

        baseline = original["requestContract"]["resources"]
        self.assertEqual(
            R.validate_resource_selection(baseline, "test"),
            ([], set()),
        )

        def assert_resources_rejected(
            resources,
            *,
            row_index,
            mutation,
        ):
            changed = copy.deepcopy(original)
            changed["requestContract"]["resources"] = resources
            changed_raw = rebound(changed)
            changed_content = changed["contentBinding"]["sha256"]
            changed_claim = R.strict_json(
                actual_raw(R.PERMIT.ACQUISITION_CLAIM_PATH),
                "claim_fixture",
            )
            changed_claim["permitContentSha256"] = changed_content
            changed_claim_raw = R.canonical_bytes(changed_claim)

            def raw_contract(path):
                if path == permit_path:
                    return changed_raw
                if path == R.PERMIT.ACQUISITION_CLAIM_PATH:
                    return changed_claim_raw
                return actual_raw(path)

            with self.subTest(
                row_index=row_index,
                mutation=mutation,
            ), mock.patch.object(
                snapshot,
                "raw",
                side_effect=raw_contract,
            ), mock.patch.object(
                R.PERMIT,
                "EXPECTED_ACQUISITION_PERMIT_CONTENT",
                changed_content,
            ), self.assertRaises(R.ReadbackError) as caught:
                R.verify_snapshot(snapshot)
            self.assertEqual(caught.exception.code, "E_RESOURCES")

        def assert_rebound_ordinal_rejected(resources, row_index):
            changed = copy.deepcopy(original)
            resource_digest = R.sha256(R.canonical_bytes(resources))
            changed["requestContract"]["resources"] = resources
            changed["requestContract"][
                "resourcesCanonicalSha256"
            ] = resource_digest
            changed_raw = rebound(changed)
            changed_content = changed["contentBinding"]["sha256"]
            changed_claim = R.strict_json(
                actual_raw(R.PERMIT.ACQUISITION_CLAIM_PATH),
                "claim_fixture",
            )
            changed_claim["permitContentSha256"] = changed_content
            changed_claim_raw = R.canonical_bytes(changed_claim)
            self.assertEqual(
                R.sha256(
                    R.canonical_bytes(
                        changed["requestContract"]["resources"]
                    )
                ),
                changed["requestContract"][
                    "resourcesCanonicalSha256"
                ],
            )

            def raw_contract(path):
                if path == permit_path:
                    return changed_raw
                if path == R.PERMIT.ACQUISITION_CLAIM_PATH:
                    return changed_claim_raw
                return actual_raw(path)

            with self.subTest(
                row_index=row_index,
                mutation="ordinal-rebound",
            ), mock.patch.object(
                snapshot,
                "raw",
                side_effect=raw_contract,
            ), mock.patch.object(
                R.PERMIT,
                "EXPECTED_ACQUISITION_PERMIT_CONTENT",
                changed_content,
            ), mock.patch.object(
                R.PERMIT,
                "EXPECTED_RESOURCES_CANONICAL",
                resource_digest,
            ), self.assertRaises(R.ReadbackError) as caught:
                R.verify_snapshot(snapshot)
            self.assertEqual(caught.exception.code, "E_ORDER")

        try:
            for index in range(6):
                for value in (True, 0, "false", None):
                    resources = copy.deepcopy(baseline)
                    resources[index]["selectedByGraphAlgorithm"] = value
                    with self.subTest(
                        index=index,
                        value=value,
                    ), self.assertRaises(R.ReadbackError) as caught:
                        R.validate_resource_selection(resources, "test")
                    self.assertEqual(caught.exception.code, "E_RESOURCES")
                resources = copy.deepcopy(baseline)
                del resources[index]["selectedByGraphAlgorithm"]
                with self.subTest(
                    index=index,
                    value="missing",
                ), self.assertRaises(R.ReadbackError) as caught:
                    R.validate_resource_selection(resources, "test")
                self.assertEqual(caught.exception.code, "E_RESOURCES")

            for index in range(6):
                resources = copy.deepcopy(baseline)
                resources[index]["requestOrdinal"] = index + 7
                assert_rebound_ordinal_rejected(resources, index)

            resource_fields = tuple(baseline[0])
            self.assertTrue(
                all(tuple(resource) == resource_fields for resource in baseline)
            )
            for index in range(6):
                for field in resource_fields:
                    if field == "selectedByGraphAlgorithm":
                        continue
                    resources = copy.deepcopy(baseline)
                    resources[index][field] = None
                    assert_resources_rejected(
                        resources,
                        row_index=index,
                        mutation=f"{field}=null",
                    )

                    resources = copy.deepcopy(baseline)
                    del resources[index][field]
                    assert_resources_rejected(
                        resources,
                        row_index=index,
                        mutation=f"{field}=missing",
                    )

                resources = copy.deepcopy(baseline)
                resources[index]["unexpectedResourceField"] = False
                assert_resources_rejected(
                    resources,
                    row_index=index,
                    mutation="extra-key",
                )
                for field in (
                    "maximumResponseBodyBytes",
                    "port",
                    "requestOrdinal",
                    "tupleOrder",
                ):
                    for alias in (False, True):
                        resources = copy.deepcopy(baseline)
                        resources[index][field] = alias
                        assert_resources_rejected(
                            resources,
                            row_index=index,
                            mutation=f"{field}=bool:{alias}",
                        )
            for stale_module in (
                "golang.org/x/crypto",
                "golang.org/x/term",
                "golang.org/x/text",
            ):
                resources = copy.deepcopy(baseline)
                resources[0]["module"] = stale_module
                assert_resources_rejected(
                    resources,
                    row_index=0,
                    mutation=f"stale-module:{stale_module}",
                )

            authority_mutations = [
                (
                    "stale-wave17-request-count",
                    lambda value: value["requestContract"].__setitem__(
                        "requestCount",
                        2,
                    ),
                    "E_AUTHORITY",
                ),
                (
                    "request-count-bool",
                    lambda value: value["requestContract"].__setitem__(
                        "requestCount",
                        True,
                    ),
                    "E_AUTHORITY",
                ),
                (
                    "stale-wave17-tuple-count",
                    lambda value: value["requestContract"].__setitem__(
                        "tupleCount",
                        1,
                    ),
                    "E_AUTHORITY",
                ),
                (
                    "unknown-request-field",
                    lambda value: value["requestContract"].__setitem__(
                        "unknown",
                        False,
                    ),
                    "E_RECEIPT",
                ),
                (
                    "stale-v15-predecessor",
                    lambda value: value.__setitem__(
                        "predecessorBindings",
                        {
                            "combinedFixedPointV" + "15": value[
                                "predecessorBindings"
                            ]["combinedFixedPointV16"]
                        },
                    ),
                    "E_AUTHORITY",
                ),
                (
                    "wave17-anchor-rebound",
                    lambda value: value["predecessorBindings"][
                        "combinedFixedPointV16"
                    ].__setitem__(
                        "wave17NamespaceAnchor",
                        value["decisionBinding"]["files"][0],
                    ),
                    "E_AUTHORITY",
                ),
            ]
            for key in (
                "authenticationAllowed",
                "authorizationHeaderAllowed",
                "proxyAuthorizationHeaderAllowed",
                "cookieAllowed",
                "clientCertificateAllowed",
            ):
                authority_mutations.extend(
                    (
                        (
                            f"{key}=true",
                            lambda value, key=key: value[
                                "requestContract"
                            ].__setitem__(key, True),
                            "E_AUTHORITY",
                        ),
                        (
                            f"{key}=int-zero",
                            lambda value, key=key: value[
                                "requestContract"
                            ].__setitem__(key, 0),
                            "E_AUTHORITY",
                        ),
                    )
                )
            for value in (True, 0):
                authority_mutations.append(
                    (
                        f"ownerProofRequired={value!r}",
                        lambda document, value=value: document[
                            "authority"
                        ].__setitem__("ownerProofRequired", value),
                        "E_AUTHORITY",
                    )
                )
            for mutation, mutate, expected_code in authority_mutations:
                changed = copy.deepcopy(original)
                mutate(changed)
                changed_raw = rebound(changed)
                changed_content = changed["contentBinding"]["sha256"]
                changed_claim = R.strict_json(
                    actual_raw(R.PERMIT.ACQUISITION_CLAIM_PATH),
                    "claim_fixture",
                )
                changed_claim["permitContentSha256"] = changed_content
                changed_claim_raw = R.canonical_bytes(changed_claim)

                def raw_contract(
                    path,
                    *,
                    changed=changed_raw,
                    claim=changed_claim_raw,
                ):
                    if path == permit_path:
                        return changed
                    if path == R.PERMIT.ACQUISITION_CLAIM_PATH:
                        return claim
                    return actual_raw(path)

                with self.subTest(mutation=mutation), mock.patch.object(
                    snapshot,
                    "raw",
                    side_effect=raw_contract,
                ), mock.patch.object(
                    R.PERMIT,
                    "EXPECTED_ACQUISITION_PERMIT_CONTENT",
                    changed_content,
                ), self.assertRaises(R.ReadbackError) as caught:
                    R.verify_snapshot(snapshot)
                self.assertEqual(caught.exception.code, expected_code)

            authority_14 = [
                row
                for row in R.PERMIT.ACQUISITION_AUTHORITY
                if not row["path"].endswith("/.wave-17-v1.claim")
            ]
            self.assertEqual(len(authority_14), 14)
            with mock.patch.object(
                R.PERMIT,
                "ACQUISITION_AUTHORITY",
                authority_14,
            ), self.assertRaises(R.ReadbackError) as caught:
                R.verify_snapshot(snapshot)
            self.assertEqual(caught.exception.code, "E_AUTHORITY")
        finally:
            snapshot.close()

    def test_05_verify_snapshot_fixed_record_and_validator_mutations_fail(self):
        snapshot = R.FrozenSnapshot()
        actual_raw = snapshot.raw
        permit_path = (
            R.PERMIT.BASE
            + "/bounded-dependency-source-acquisition-wave18-"
            "execution-permit-v1.json"
        )
        acquisition_permit = R.strict_json(
            actual_raw(permit_path),
            "permit_fixture",
        )
        resources = acquisition_permit["requestContract"]["resources"]
        try:
            for path, field, replacement, expected_code in (
                (
                    R.PERMIT.ACQUISITION_CLAIM_PATH,
                    "attemptId",
                    "fff8d6073748eab6fd1a05c79c57a84f",
                    "E_CLAIM",
                ),
                (
                    R.PERMIT.ACQUISITION_CLAIM_PATH,
                    "externalAuthenticationRequired",
                    0,
                    "E_CLAIM",
                ),
                (
                    R.PERMIT.EVIDENCE_PATH,
                    "aggregateZipEntryCount",
                    972,
                    "E_EVIDENCE",
                ),
                (
                    R.PERMIT.ACQUISITION_RECEIPT_PATH,
                    "aggregateResponseBytes",
                    2_109_101,
                    "E_RECEIPT",
                ),
                (
                    R.PERMIT.ACQUISITION_RECEIPT_PATH,
                    "acceptedResourceHashSetCanonicalSha256",
                    "0" * 64,
                    "E_RECEIPT",
                ),
                (
                    R.PERMIT.ACQUISITION_RECEIPT_PATH,
                    "additionalCompletionUncertain",
                    0,
                    "E_RECEIPT",
                ),
                (
                    R.PERMIT.ACQUISITION_MANIFEST_PATH,
                    "manifestWrittenLast",
                    1,
                    "E_MANIFEST",
                ),
            ):
                with self.subTest(path=path, field=field):
                    changed = R.strict_json(actual_raw(path), "fixture")
                    changed[field] = replacement
                    changed_raw = R.canonical_bytes(changed)

                    def mutated_raw(
                        candidate,
                        *,
                        target=path,
                        replacement_raw=changed_raw,
                    ):
                        return (
                            replacement_raw
                            if candidate == target
                            else actual_raw(candidate)
                        )

                    with mock.patch.object(
                        snapshot,
                        "raw",
                        side_effect=mutated_raw,
                    ), self.assertRaises(R.ReadbackError) as caught:
                        R.verify_snapshot(snapshot)
                    self.assertEqual(
                        caught.exception.code,
                        expected_code,
                    )

            for path, expected_code in (
                (R.PERMIT.ACQUISITION_CLAIM_PATH, "E_CLAIM"),
                (R.PERMIT.EVIDENCE_PATH, "E_EVIDENCE"),
                (R.PERMIT.ACQUISITION_RECEIPT_PATH, "E_RECEIPT"),
                (R.PERMIT.ACQUISITION_MANIFEST_PATH, "E_MANIFEST"),
            ):
                original_record = R.strict_json(
                    actual_raw(path),
                    "schema_fixture",
                )
                for mutation in ("missing", "extra"):
                    changed = copy.deepcopy(original_record)
                    if mutation == "missing":
                        changed.pop("documentType")
                    else:
                        changed["unexpectedSchemaField"] = False
                    changed_raw = R.canonical_bytes(changed)

                    def schema_mutated_raw(
                        candidate,
                        *,
                        target=path,
                        replacement_raw=changed_raw,
                    ):
                        return (
                            replacement_raw
                            if candidate == target
                            else actual_raw(candidate)
                        )

                    with self.subTest(
                        path=path,
                        schema_mutation=mutation,
                    ), mock.patch.object(
                        snapshot,
                        "raw",
                        side_effect=schema_mutated_raw,
                    ), self.assertRaises(R.ReadbackError) as caught:
                        R.verify_snapshot(snapshot)
                    self.assertEqual(caught.exception.code, expected_code)

            evidence_alias = R.strict_json(
                actual_raw(R.PERMIT.EVIDENCE_PATH),
                "evidence_fixture",
            )
            zip_row = next(
                row
                for row in evidence_alias["resources"]
                if row["kind"] == "zip"
            )
            zip_row["rootGoModPresent"] = 1
            evidence_alias_bytes = R.canonical_bytes(evidence_alias)

            def evidence_alias_source(candidate):
                return (
                    evidence_alias_bytes
                    if candidate == R.PERMIT.EVIDENCE_PATH
                    else actual_raw(candidate)
                )

            with mock.patch.object(
                snapshot,
                "raw",
                side_effect=evidence_alias_source,
            ), self.assertRaises(R.ReadbackError) as caught:
                R.verify_snapshot(snapshot)
            self.assertEqual(caught.exception.code, "E_EVIDENCE")

            real_validate_mod = R.validate_mod
            injected = False
            wrong_h1 = (
                "h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
            )
            R.decode_h1(wrong_h1, "test")

            def valid_but_wrong_h1(raw, module):
                nonlocal injected
                result = real_validate_mod(raw, module)
                if not injected:
                    injected = True
                    result = dict(result)
                    result["goModH1"] = wrong_h1
                return result

            with mock.patch.object(
                R,
                "validate_mod",
                side_effect=valid_but_wrong_h1,
            ), self.assertRaises(R.ReadbackError) as caught:
                R.verify_snapshot(snapshot)
            self.assertEqual(caught.exception.code, "E_H1")

            for field in ("entryCount", "uncompressedBytes"):
                for target_zip_index in range(3):
                    with self.subTest(
                        aggregate_field=field,
                        zip_index=target_zip_index,
                    ):
                        real_validate_zip = R.validate_zip
                        zip_index = 0

                        def drifted_zip_result(
                            raw,
                            module,
                            version,
                            mod_raw,
                            *,
                            target_field=field,
                            target_index=target_zip_index,
                        ):
                            nonlocal zip_index
                            result = real_validate_zip(
                                raw,
                                module,
                                version,
                                mod_raw,
                            )
                            if zip_index == target_index:
                                result = dict(result)
                                result[target_field] += 1
                            zip_index += 1
                            return result

                        with mock.patch.object(
                            R,
                            "validate_zip",
                            side_effect=drifted_zip_result,
                        ), self.assertRaises(R.ReadbackError) as caught:
                            R.verify_snapshot(snapshot)
                        self.assertEqual(
                            caught.exception.code,
                            "E_AGGREGATE",
                        )

            for accepted in R.PERMIT.ACCEPTED_FILES:
                target_path = accepted["path"]
                changed_raw = bytearray(actual_raw(target_path))
                changed_raw[-1] ^= 1
                changed_raw = bytes(changed_raw)

                def mutated_accepted_raw(
                    candidate,
                    *,
                    target=target_path,
                    replacement_raw=changed_raw,
                ):
                    return (
                        replacement_raw
                        if candidate == target
                        else actual_raw(candidate)
                    )

                with self.subTest(
                    accepted_path=target_path,
                    mutation="last-byte-bit-flip",
                ), mock.patch.object(
                    snapshot,
                    "raw",
                    side_effect=mutated_accepted_raw,
                ), self.assertRaises(R.ReadbackError) as caught:
                    R.verify_snapshot(snapshot)
                self.assertEqual(caught.exception.code, "E_ACCEPTED")

            for index, accepted in enumerate(R.PERMIT.ACCEPTED_FILES):
                target_path = accepted["path"]
                original_raw = actual_raw(target_path)
                for mutation, changed_raw in (
                    ("size-plus-one", original_raw + b"\0"),
                    ("size-minus-one", original_raw[:-1]),
                ):

                    def mutated_size_raw(
                        candidate,
                        *,
                        target=target_path,
                        replacement_raw=changed_raw,
                    ):
                        return (
                            replacement_raw
                            if candidate == target
                            else actual_raw(candidate)
                        )

                    with self.subTest(
                        ordinal=index + 1,
                        mutation=mutation,
                    ), mock.patch.object(
                        snapshot,
                        "raw",
                        side_effect=mutated_size_raw,
                    ), self.assertRaises(R.ReadbackError) as caught:
                        R.verify_snapshot(snapshot)
                    self.assertEqual(caught.exception.code, "E_ACCEPTED")

                changed_specs = copy.deepcopy(R.PERMIT.ACCEPTED_FILES)
                changed_specs[index]["rawSha256"] = "0" * 64
                with self.subTest(
                    ordinal=index + 1,
                    mutation="bound-raw-hash",
                ), mock.patch.object(
                    R.PERMIT,
                    "ACCEPTED_FILES",
                    changed_specs,
                ), self.assertRaises(R.ReadbackError) as caught:
                    R.verify_snapshot(snapshot)
                self.assertEqual(caught.exception.code, "E_ACCEPTED")

                resource = resources[index]
                if resource["kind"] == "mod":
                    real_validator = R.validate_mod

                    def wrong_resource_h1(
                        raw,
                        module,
                        *,
                        target_module=resource["module"],
                    ):
                        result = real_validator(raw, module)
                        if module == target_module:
                            result = dict(result)
                            result["goModH1"] = wrong_h1
                        return result

                    patcher = mock.patch.object(
                        R,
                        "validate_mod",
                        side_effect=wrong_resource_h1,
                    )
                else:
                    real_validator = R.validate_zip

                    def wrong_resource_h1(
                        raw,
                        module,
                        version,
                        mod_raw,
                        *,
                        target_module=resource["module"],
                    ):
                        result = real_validator(
                            raw,
                            module,
                            version,
                            mod_raw,
                        )
                        if module == target_module:
                            result = dict(result)
                            result["moduleZipH1"] = wrong_h1
                        return result

                    patcher = mock.patch.object(
                        R,
                        "validate_zip",
                        side_effect=wrong_resource_h1,
                    )
                with self.subTest(
                    ordinal=index + 1,
                    mutation="verified-h1",
                ), patcher, self.assertRaises(R.ReadbackError) as caught:
                    R.verify_snapshot(snapshot)
                self.assertEqual(caught.exception.code, "E_H1")

                evidence = R.strict_json(
                    actual_raw(R.PERMIT.EVIDENCE_PATH),
                    "evidence_fixture",
                )
                evidence["resources"][index]["rawSha256"] = "0" * 64
                changed_evidence_raw = R.canonical_bytes(evidence)

                def mutated_evidence_raw(
                    candidate,
                    *,
                    replacement_raw=changed_evidence_raw,
                ):
                    return (
                        replacement_raw
                        if candidate == R.PERMIT.EVIDENCE_PATH
                        else actual_raw(candidate)
                    )

                with self.subTest(
                    ordinal=index + 1,
                    mutation="evidence-row",
                ), mock.patch.object(
                    snapshot,
                    "raw",
                    side_effect=mutated_evidence_raw,
                ), self.assertRaises(R.ReadbackError) as caught:
                    R.verify_snapshot(snapshot)
                self.assertEqual(caught.exception.code, "E_EVIDENCE")
        finally:
            snapshot.close()

    def test_05_verify_snapshot_accepted_zip_structural_mutations_fail(self):
        snapshot = R.FrozenSnapshot()
        actual_raw = snapshot.raw
        permit_path = (
            R.PERMIT.BASE
            + "/bounded-dependency-source-acquisition-wave18-"
            "execution-permit-v1.json"
        )
        try:
            permit = R.strict_json(actual_raw(permit_path), "permit_fixture")
            resources = permit["requestContract"]["resources"]
            accepted = {
                Path(row["path"]).name: row
                for row in R.PERMIT.ACCEPTED_FILES
            }
            zip_resources = [
                row for row in resources if row["kind"] == "zip"
            ]
            self.assertEqual(
                [row["requestOrdinal"] for row in zip_resources],
                [2, 4, 6],
            )
            for resource in zip_resources:
                mod_resource = next(
                    row
                    for row in resources
                    if row["kind"] == "mod"
                    and row["tupleId"] == resource["tupleId"]
                )
                mod_raw = actual_raw(
                    accepted[mod_resource["acceptedFileName"]]["path"]
                )
                original_zip = actual_raw(
                    accepted[resource["acceptedFileName"]]["path"]
                )
                R.validate_zip(
                    original_zip,
                    resource["module"],
                    resource["version"],
                    mod_raw,
                )
                _, central_offset, _ = R._zip_layout(original_zip)
                central = R.ZIP_CENTRAL_HEADER.unpack_from(
                    original_zip,
                    central_offset,
                )
                local_offset = central[-1]

                local_mismatch = bytearray(original_zip)
                local_mismatch[local_offset + 8] ^= 1

                central_mismatch = bytearray(original_zip)
                central_mismatch[central_offset + 10] ^= 1

                crc_mismatch = bytearray(original_zip)
                wrong_crc = (central[7] ^ 1).to_bytes(4, "little")
                crc_mismatch[
                    central_offset + 16 : central_offset + 20
                ] = wrong_crc
                local = R.ZIP_LOCAL_HEADER.unpack_from(
                    original_zip,
                    local_offset,
                )
                if local[2] & 0x0008:
                    data_end = (
                        local_offset
                        + R.ZIP_LOCAL_HEADER.size
                        + local[9]
                        + local[10]
                        + central[8]
                    )
                    descriptor_crc = (
                        data_end + 4
                        if int.from_bytes(
                            original_zip[data_end : data_end + 4],
                            "little",
                        )
                        == R.ZIP_DATA_DESCRIPTOR_SIGNATURE
                        else data_end
                    )
                    crc_mismatch[
                        descriptor_crc : descriptor_crc + 4
                    ] = wrong_crc
                else:
                    crc_mismatch[
                        local_offset + 14 : local_offset + 18
                    ] = wrong_crc

                prefix = (
                    f"{resource['module']}@{resource['version']}/"
                )
                with zipfile.ZipFile(
                    io.BytesIO(original_zip),
                    "r",
                ) as archive:
                    files = {
                        info.filename[len(prefix) :]: archive.read(info)
                        for info in archive.infolist()
                    }
                self.assertIn("go.mod", files)
                files["go.mod"] += b"\n// parity mutation\n"
                parity_mismatch = make_zip(
                    resource["module"],
                    resource["version"],
                    files,
                )

                for name, changed_zip, expected_code in (
                    (
                        "local_header",
                        bytes(local_mismatch),
                        "E_ZIP_STRUCTURE",
                    ),
                    (
                        "central_header",
                        bytes(central_mismatch),
                        "E_ZIP_STRUCTURE",
                    ),
                    (
                        "crc",
                        bytes(crc_mismatch),
                        "E_ZIP_CRC",
                    ),
                    (
                        "go_mod_parity",
                        parity_mismatch,
                        "E_MOD_PARITY",
                    ),
                ):
                    with self.subTest(
                        ordinal=resource["requestOrdinal"],
                        mutation=name,
                    ), self.assertRaises(R.ReadbackError) as caught:
                        R.validate_zip(
                            changed_zip,
                            resource["module"],
                            resource["version"],
                            mod_raw,
                        )
                    self.assertEqual(
                        caught.exception.code,
                        expected_code,
                    )
        finally:
            snapshot.close()

    def test_06_preflight_opens_no_frozen_acquisition_input(self):
        result = R.preflight()
        self.assertFalse(result["frozenAcquisitionInputOpened"])
        self.assertEqual(result["networkRequestAttemptCount"], 0)
        no_auth_keys = (
            "networkAuthorized",
            "dnsAuthorized",
            "socketAuthorized",
            "proxyAuthorized",
            "authenticationRequired",
            "credentialRequired",
            "externalAuthenticationRequired",
            "repositoryOwnerIdentityProofRequired",
            "ownerProofRequired",
            "accountRequired",
            "ownerRequired",
            "sshRequired",
            "gpgRequired",
            "passwordRequired",
            "privateKeyRequired",
            "signatureRequired",
            "tokenRequired",
            "cookieRequired",
            "clientCertificateRequired",
            "sourceAcquisitionAuthorized",
            "sourceExtractionAuthorized",
            "sourceLoadOrExecutionAuthorized",
            "compileAuthorized",
            "packageManagerAuthorized",
            "subprocessAuthorized",
            "gitOperationAuthorized",
            "deviceAuthorized",
            "deploymentAuthorized",
            "userActionRequired",
        )
        baseline = R.PERMIT.package_preflight_for_recorder()
        for key in no_auth_keys:
            for unauthorized in (True, 0):
                with self.subTest(key=key, unauthorized=unauthorized):
                    changed = copy.deepcopy(baseline)
                    changed["permit"]["authority"][key] = unauthorized
                    with mock.patch.object(
                        R.PERMIT,
                        "package_preflight_for_recorder",
                        return_value=changed,
                    ), self.assertRaises(R.ReadbackError) as caught:
                        R.preflight()
                    self.assertEqual(caught.exception.code, "E_PREFLIGHT")
                    self.assertFalse(
                        os.path.lexists(
                            R.ROOT / R.PERMIT.READBACK_CLAIM_PATH
                        )
                    )
            changed = copy.deepcopy(baseline)
            del changed["permit"]["authority"][key]
            with self.subTest(
                key=key,
                unauthorized="missing",
            ), mock.patch.object(
                R.PERMIT,
                "package_preflight_for_recorder",
                return_value=changed,
            ), self.assertRaises(R.ReadbackError) as caught:
                R.preflight()
            self.assertEqual(caught.exception.code, "E_PREFLIGHT")
            self.assertFalse(
                os.path.lexists(R.ROOT / R.PERMIT.READBACK_CLAIM_PATH)
            )

        changed = copy.deepcopy(baseline)
        changed["permit"]["authority"]["unexpectedAuthenticationField"] = False
        with self.subTest(
            unauthorized="extra-key",
        ), mock.patch.object(
            R.PERMIT,
            "package_preflight_for_recorder",
            return_value=changed,
        ), self.assertRaises(R.ReadbackError) as caught:
            R.preflight()
        self.assertEqual(caught.exception.code, "E_PREFLIGHT")
        self.assertFalse(
            os.path.lexists(R.ROOT / R.PERMIT.READBACK_CLAIM_PATH)
        )

    def test_07_claim_is_exclusive_0600_canonical_and_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            claim, claim_fd = R.create_readback_claim(
                root,
                "1" * 32,
                {"permit": {"rawSha256": "2" * 64}},
            )
            try:
                self.assertEqual(claim["mode"], "0600")
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertEqual(
                    (os.fstat(claim_fd).st_dev, os.fstat(claim_fd).st_ino),
                    (target.stat().st_dev, target.stat().st_ino),
                )
                value = json.loads(target.read_text())
                self.assertEqual(value["readbackAttemptId"], "1" * 32)
                self.assertEqual(target.read_bytes(), R.canonical_bytes(value))
                with self.assertRaises(R.ReadbackError) as caught:
                    R.create_readback_claim(
                        root,
                        "3" * 32,
                        {"permit": {"rawSha256": "4" * 64}},
                    )
                self.assertEqual(caught.exception.code, "E_CONSUMED")
            finally:
                os.close(claim_fd)

    def test_08_claim_fsync_ambiguity_is_consumed_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            with mock.patch.object(R.os, "fsync", side_effect=OSError("synthetic")):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.create_readback_claim(root, "1" * 32, {"x": 1})
            self.assertTrue(caught.exception.consumed)
            self.assertTrue(caught.exception.uncertain)
            self.assertTrue(os.path.lexists(target))

    def test_08_claim_creation_inode_is_continuously_held(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            (root / R.PERMIT.READBACK_RECEIPT_PATH).parent.mkdir(
                parents=True,
                mode=0o700,
            )
            namespace = R.ReadbackNamespace(root)
            claim_fd = -1
            try:
                namespace.preclaim_barrier()
                claim, claim_fd = R.create_readback_claim(
                    root,
                    "1" * 32,
                    {"x": 1},
                    namespace.root_fd,
                    namespace.owned_fds,
                )
                raw = target.read_bytes()
                target.rename(target.with_name(target.name + ".old"))
                target.write_bytes(raw)
                target.chmod(0o600)
                with self.assertRaises(R.ReadbackError) as caught:
                    namespace.hold_claim(claim, claim_fd)
                claim_fd = -1
                self.assertEqual(
                    caught.exception.code,
                    "E_CLAIM_STATE_UNCERTAIN",
                )
                self.assertTrue(caught.exception.consumed)
                self.assertTrue(caught.exception.uncertain)
                self.assertEqual(
                    caught.exception.phase,
                    "claim_identity",
                )
            finally:
                if claim_fd >= 0:
                    if claim_fd in namespace.owned_fds:
                        R._close_owned_fd(namespace.owned_fds, claim_fd)
                    else:
                        os.close(claim_fd)
                namespace.close()

    def test_08_execute_claim_path_loss_is_terminal_uncertainty(self):
        for mutation in ("unlink", "replace"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / R.PERMIT.READBACK_CLAIM_PATH
                target.parent.mkdir(parents=True, mode=0o700)
                (root / R.PERMIT.BASE).mkdir(parents=True, mode=0o700)
                original_create = R.create_readback_claim

                def create_then_mutate(
                    claim_root,
                    attempt,
                    authority,
                    retained_root_fd,
                    fd_owner,
                ):
                    claim, claim_fd = original_create(
                        claim_root,
                        attempt,
                        authority,
                        retained_root_fd,
                        fd_owner,
                    )
                    raw = target.read_bytes()
                    if mutation == "replace":
                        target.rename(target.with_name(target.name + ".old"))
                        target.write_bytes(raw)
                        target.chmod(0o600)
                    else:
                        target.unlink()
                    return claim, claim_fd

                with mock.patch.object(
                    R,
                    "preflight",
                    return_value=fake_preflight(),
                ), mock.patch.object(
                    R,
                    "create_readback_claim",
                    side_effect=create_then_mutate,
                ):
                    with self.assertRaises(R.ReadbackError) as caught:
                        R.execute(root)
                self.assertEqual(
                    caught.exception.code,
                    "E_CONSUMED_STATE_UNCERTAIN",
                )
                self.assertEqual(
                    caught.exception.phase,
                    "claim_identity",
                )
                self.assertTrue(caught.exception.consumed)
                self.assertTrue(caught.exception.uncertain)
                self.assertFalse(
                    os.path.lexists(root / R.PERMIT.READBACK_RECEIPT_PATH)
                )
                self.assertFalse(
                    os.path.lexists(root / R.PERMIT.READBACK_MANIFEST_PATH)
                )

    def test_08_actual_claim_fsync_and_hold_precede_snapshot_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            (root / R.PERMIT.BASE).mkdir(parents=True, mode=0o700)
            events: list[str] = []
            actual_fsync = R.os.fsync

            def traced_fsync(fd):
                info = os.fstat(fd)
                events.append(
                    "fsync_file"
                    if stat.S_ISREG(info.st_mode)
                    else "fsync_directory"
                )
                return actual_fsync(fd)

            class TracedNamespace(R.ReadbackNamespace):
                def hold_claim(self, claim, claim_fd):
                    super().hold_claim(claim, claim_fd)
                    events.append("hold_claim")

            def stop_snapshot(_root):
                events.append("snapshot")
                raise R.ReadbackError("E_STOP", "snapshot")

            with mock.patch.object(
                R,
                "preflight",
                return_value=fake_preflight(),
            ), mock.patch.object(R.os, "fsync", side_effect=traced_fsync):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.execute(
                        root,
                        snapshot_factory=stop_snapshot,
                        namespace_factory=TracedNamespace,
                    )
            hold_index = events.index("hold_claim")
            snapshot_index = events.index("snapshot")
            file_fsync_index = events.index("fsync_file")
            directory_fsync_index = events.index("fsync_directory")
            self.assertLess(file_fsync_index, directory_fsync_index)
            self.assertLess(directory_fsync_index, hold_index)
            self.assertLess(hold_index, snapshot_index)
            self.assertTrue(os.path.lexists(target))
            self.assertTrue(caught.exception.consumed)
            self.assertFalse(caught.exception.uncertain)

    def test_09_atomic_publication_is_0600_and_no_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_RECEIPT_PATH
            target.parent.mkdir(parents=True, mode=0o700)

            def rename(source_fd, source, target_fd, target_name):
                os.rename(
                    source,
                    target_name,
                    src_dir_fd=source_fd,
                    dst_dir_fd=target_fd,
                )

            payload = R.content_bound({"value": 1})
            result = R.atomic_publish(
                root,
                R.PERMIT.READBACK_RECEIPT_PATH,
                payload,
                rename,
            )
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(result["rawSha256"], hashlib.sha256(target.read_bytes()).hexdigest())
            with self.assertRaises(R.ReadbackError):
                R.atomic_publish(
                    root,
                    R.PERMIT.READBACK_RECEIPT_PATH,
                    payload,
                    rename,
                )

    def test_09_final_name_verification_occurs_after_parent_fsync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_RECEIPT_PATH
            target.parent.mkdir(parents=True, mode=0o700)

            def rename(source_fd, source, target_fd, target_name):
                os.rename(
                    source,
                    target_name,
                    src_dir_fd=source_fd,
                    dst_dir_fd=target_fd,
                )

            real_fsync = os.fsync
            calls = 0

            def fsync_then_swap(fd):
                nonlocal calls
                calls += 1
                real_fsync(fd)
                if calls == 2:
                    raw = target.read_bytes()
                    target.rename(target.with_name(target.name + ".old"))
                    target.write_bytes(raw)
                    target.chmod(0o600)

            with mock.patch.object(R.os, "fsync", side_effect=fsync_then_swap):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.atomic_publish(
                        root,
                        R.PERMIT.READBACK_RECEIPT_PATH,
                        R.content_bound({"value": 1}),
                        rename,
                    )
            self.assertEqual(
                caught.exception.code,
                "E_PUBLICATION_DURABILITY_UNCERTAIN",
            )

    @unittest.skipUnless(
        sys.platform == "darwin",
        "renameatx_np(RENAME_EXCL) is Darwin-specific",
    )
    def test_09_actual_darwin_rename_excl_race_has_one_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            parent_fd = os.open(
                parent,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
            )
            try:
                bodies = {"left.tmp": b"left", "right.tmp": b"right"}
                for name, body in bodies.items():
                    fd = os.open(
                        name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    try:
                        os.write(fd, body)
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                os.fsync(parent_fd)
                gate = threading.Barrier(3)
                outcomes = []
                lock = threading.Lock()

                def contender(name):
                    gate.wait()
                    try:
                        R.rename_no_replace(
                            parent_fd,
                            name,
                            parent_fd,
                            "winner",
                        )
                        outcome = (name, "success")
                    except R.ReadbackError as error:
                        outcome = (name, error.code)
                    with lock:
                        outcomes.append(outcome)

                threads = [
                    threading.Thread(target=contender, args=(name,))
                    for name in bodies
                ]
                for thread in threads:
                    thread.start()
                gate.wait()
                for thread in threads:
                    thread.join()
                self.assertEqual(
                    sorted(result for _, result in outcomes),
                    ["E_OUTPUT_EXISTS", "success"],
                )
                winner = next(name for name, result in outcomes if result == "success")
                loser = next(
                    name for name, result in outcomes if result == "E_OUTPUT_EXISTS"
                )
                self.assertEqual((parent / "winner").read_bytes(), bodies[winner])
                self.assertFalse((parent / winner).exists())
                self.assertEqual((parent / loser).read_bytes(), bodies[loser])
            finally:
                os.close(parent_fd)

    def test_09_component_chain_and_project_root_swaps_fail_barriers(self):
        with tempfile.TemporaryDirectory() as directory:
            container = Path(directory)
            root = container / "project"
            nested = root / "a" / "b"
            nested.mkdir(parents=True, mode=0o700)
            target = nested / "value"
            target.write_bytes(b"same")
            target.chmod(0o600)
            info = target.stat()
            expected = {
                "path": "a/b/value",
                "rawSha256": hashlib.sha256(b"same").hexdigest(),
                "bytes": 4,
                "mode": "0600",
                "ownerUid": info.st_uid,
                "linkCount": info.st_nlink,
            }
            owned: list[int] = []
            root_fd, _ = R._open_root(root.absolute(), "test", owned)
            held = R.HeldFile(root_fd, expected, owned)
            try:
                (root / "a").rename(root / "old-a")
                (root / "a").mkdir(mode=0o700)
                (root / "old-a" / "b").rename(root / "a" / "b")
                self.assertEqual(
                    (root / "a" / "b" / "value").stat().st_ino,
                    info.st_ino,
                )
                with self.assertRaises(R.ReadbackError) as caught:
                    held.barrier()
                self.assertEqual(
                    caught.exception.code,
                    "E_COMPONENT_IDENTITY",
                )
            finally:
                held.close()
                R._close_owned_fds(owned)

            directory_info = (root / "a" / "b").stat()
            directory_expected = {
                "path": "a/b",
                "mode": "0700",
                "ownerUid": directory_info.st_uid,
                "linkCount": directory_info.st_nlink,
            }
            owned = []
            root_fd, _ = R._open_root(root.absolute(), "test", owned)
            held_directory = R.HeldDirectory(
                root_fd,
                directory_expected,
                {"value"},
                owned,
            )
            try:
                (root / "a").rename(root / "old-a-2")
                (root / "a").mkdir(mode=0o700)
                (root / "old-a-2" / "b").rename(root / "a" / "b")
                self.assertEqual(
                    (root / "a" / "b").stat().st_ino,
                    directory_info.st_ino,
                )
                with self.assertRaises(R.ReadbackError) as caught:
                    held_directory.barrier()
                self.assertEqual(
                    caught.exception.code,
                    "E_COMPONENT_IDENTITY",
                )
            finally:
                held_directory.close()
                R._close_owned_fds(owned)

            retained = R.ReadbackNamespace(root)
            try:
                root.rename(container / "old-project")
                root.mkdir(mode=0o700)
                with self.assertRaises(R.ReadbackError) as caught:
                    retained._root_barrier()
                self.assertEqual(caught.exception.code, "E_ROOT_IDENTITY")
            finally:
                retained.close()

    def test_10_synthetic_execute_orders_claim_two_passes_receipt_manifest(self):
        events: list[str] = []
        authority = {"permit": {"rawSha256": "a" * 64}}

        def claim(_root, _attempt, _authority, _root_fd, _fd_owner):
            events.append("claim")
            return {"path": "claim", "rawSha256": "b" * 64}, -1

        def verify(snapshot):
            snapshot.events.append("verify")
            return {"acceptedResourceCount": 6}

        published_payloads = {}

        def publish(_root, path, payload, **_kwargs):
            events.append("receipt" if path.endswith("readback-v1.json") else "manifest")
            published_payloads[path] = payload
            return {
                "path": path,
                "rawSha256": hashlib.sha256(R.canonical_bytes(payload)).hexdigest(),
                "bytes": len(R.canonical_bytes(payload)),
                "mode": "0600",
                "contentSha256": payload["contentBinding"]["sha256"],
            }

        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(authority),
        ), mock.patch.object(R, "create_readback_claim", side_effect=claim), mock.patch.object(
            R, "verify_snapshot", side_effect=verify
        ), mock.patch.object(R, "atomic_publish", side_effect=publish):
            result = R.execute(
                Path("/unused"),
                snapshot_factory=lambda _root: FakeSnapshot(events),
                namespace_factory=lambda _root: FakeNamespace(events),
            )
        self.assertEqual(
            [event for event in events if event in {"claim", "snapshot", "verify", "receipt", "manifest"}],
            ["claim", "snapshot", "verify", "verify", "receipt", "manifest"],
        )
        self.assertEqual(events.count("barrier"), 3)
        self.assertLess(
            max(index for index, event in enumerate(events) if event == "barrier"),
            events.index("manifest"),
        )
        manifest_index = events.index("manifest")
        self.assertEqual(
            events[manifest_index - 2 : manifest_index + 1],
            ["barrier", "namespace_barrier_receipt", "manifest"],
        )
        receipt_payload = published_payloads[R.PERMIT.READBACK_RECEIPT_PATH]
        manifest_payload = published_payloads[R.PERMIT.READBACK_MANIFEST_PATH]
        self.assertEqual(
            receipt_payload[
                "completedRetainedFdPreManifestBarrierCountAtReceipt"
            ],
            1,
        )
        self.assertEqual(
            receipt_payload[
                "remainingRetainedFdPreManifestBarrierCount"
            ],
            2,
        )
        self.assertTrue(
            receipt_payload[
                "allRequiredPreManifestBarriersRequired"
            ]
        )
        self.assertFalse(
            receipt_payload[
                "allRequiredPreManifestBarriersCompleteAtReceipt"
            ]
        )
        self.assertEqual(
            manifest_payload[
                "completedPreManifestCurrentPathIdentityBarrierCount"
            ],
            3,
        )
        for payload in (receipt_payload, manifest_payload, result):
            self.assertTrue(payload["completionAppliesToRetainedSnapshot"])
            self.assertFalse(
                payload[
                    "currentPathIdentityGuaranteedThroughManifestPublication"
                ]
            )
            self.assertFalse(
                payload[
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
                ]
            )
        self.assertEqual(
            receipt_payload["status"],
            (
                "wave18_acquisition_retained_snapshot_"
                "independently_read_back"
            ),
        )
        self.assertEqual(
            manifest_payload["status"],
            (
                "wave18_acquisition_retained_snapshot_"
                "readback_publication_complete"
            ),
        )
        self.assertEqual(
            result["lastCurrentPathIdentityBarrierTiming"],
            "immediately_before_manifest_publication",
        )
        self.assertEqual(
            [
                event
                for event in events[events.index("manifest") + 1 :]
                if "barrier" in event
            ],
            [],
        )
        self.assertEqual(result["networkRequestAttemptCount"], 0)

    def test_11_failure_after_claim_publishes_no_success(self):
        events: list[str] = []
        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ), mock.patch.object(
            R,
            "create_readback_claim",
            return_value=({"path": "claim"}, -1),
        ), mock.patch.object(
            R,
            "verify_snapshot",
            side_effect=R.ReadbackError("E_SYNTHETIC", "verification"),
        ), mock.patch.object(R, "atomic_publish") as publish:
            with self.assertRaises(R.ReadbackError) as caught:
                R.execute(
                    Path("/unused"),
                    snapshot_factory=lambda _root: FakeSnapshot(events),
                    namespace_factory=lambda _root: FakeNamespace(events),
                )
        self.assertTrue(caught.exception.consumed)
        self.assertFalse(caught.exception.uncertain)
        publish.assert_not_called()

    def test_12_receipt_only_gap_is_terminal_uncertainty(self):
        events: list[str] = []
        calls = 0

        def publish(_root, path, payload, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise R.ReadbackError("E_SYNTHETIC", "publication")
            return {
                "path": path,
                "rawSha256": "a" * 64,
                "bytes": 1,
                "mode": "0600",
                "contentSha256": payload["contentBinding"]["sha256"],
            }

        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ), mock.patch.object(
            R,
            "create_readback_claim",
            return_value=({"path": "claim"}, -1),
        ), mock.patch.object(
            R,
            "verify_snapshot",
            return_value={"acceptedResourceCount": 6},
        ), mock.patch.object(R, "atomic_publish", side_effect=publish):
            with self.assertRaises(R.ReadbackError) as caught:
                R.execute(
                    Path("/unused"),
                    snapshot_factory=lambda _root: FakeSnapshot(events),
                    namespace_factory=lambda _root: FakeNamespace(events),
                )
        self.assertTrue(caught.exception.consumed)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(
            caught.exception.code,
            "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
        )

    def test_13_unknown_claim_call_gap_is_consumed_uncertainty(self):
        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ), mock.patch.object(
            R,
            "create_readback_claim",
            side_effect=RuntimeError("synthetic post-create return gap"),
        ):
            with self.assertRaises(R.ReadbackError) as caught:
                R.execute(
                    Path("/unused"),
                    namespace_factory=lambda _root: FakeNamespace([]),
                )
        self.assertTrue(caught.exception.consumed)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(caught.exception.code, "E_CLAIM_STATE_UNCERTAIN")

    def test_14_publication_call_gap_is_terminal_uncertainty(self):
        events: list[str] = []
        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ), mock.patch.object(
            R,
            "create_readback_claim",
            return_value=({"path": "claim"}, -1),
        ), mock.patch.object(
            R,
            "verify_snapshot",
            return_value={"acceptedResourceCount": 6},
        ), mock.patch.object(
            R,
            "atomic_publish",
            side_effect=RuntimeError("synthetic publication call gap"),
        ):
            with self.assertRaises(R.ReadbackError) as caught:
                R.execute(
                    Path("/unused"),
                    snapshot_factory=lambda _root: FakeSnapshot(events),
                    namespace_factory=lambda _root: FakeNamespace(events),
                )
        self.assertTrue(caught.exception.consumed)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(
            caught.exception.code,
            "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
        )

    def test_15_claim_durability_uncertainty_is_not_receipt_uncertainty(self):
        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ), mock.patch.object(
            R,
            "create_readback_claim",
            side_effect=R.ReadbackError(
                "E_CLAIM_STATE_UNCERTAIN",
                "claim",
                consumed=True,
                uncertain=True,
            ),
        ):
            with self.assertRaises(R.ReadbackError) as caught:
                R.execute(
                    Path("/unused"),
                    namespace_factory=lambda _root: FakeNamespace([]),
                )
        self.assertTrue(caught.exception.consumed)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(caught.exception.code, "E_CLAIM_STATE_UNCERTAIN")

    def test_16_each_explicit_publication_barrier_fails_closed(self):
        class FaultSnapshot(FakeSnapshot):
            def __init__(self, events, fail_at):
                super().__init__(events)
                self.fail_at = fail_at
                self.barriers = 0

            def final_barrier(self):
                self.barriers += 1
                self.events.append("barrier")
                if self.barriers == self.fail_at:
                    raise R.ReadbackError("E_SYNTHETIC", "barrier")

        for fail_at in (1, 2, 3):
            events: list[str] = []

            def publish(_root, path, payload, **_kwargs):
                events.append(
                    "receipt" if path.endswith("readback-v1.json") else "manifest"
                )
                return {
                    "path": path,
                    "rawSha256": "a" * 64,
                    "bytes": 1,
                    "mode": "0600",
                    "contentSha256": payload["contentBinding"]["sha256"],
                }

            with self.subTest(fail_at=fail_at), mock.patch.object(
                R,
                "preflight",
                return_value=fake_preflight(),
            ), mock.patch.object(
                R,
                "create_readback_claim",
                return_value=({"path": "claim"}, -1),
            ), mock.patch.object(
                R,
                "verify_snapshot",
                return_value={"acceptedResourceCount": 6},
            ), mock.patch.object(R, "atomic_publish", side_effect=publish):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.execute(
                        Path("/unused"),
                        snapshot_factory=lambda _root: FaultSnapshot(
                            events,
                            fail_at,
                        ),
                        namespace_factory=lambda _root: FakeNamespace(events),
                    )
            self.assertTrue(caught.exception.consumed)
            self.assertEqual(caught.exception.uncertain, fail_at > 1)
            self.assertNotIn("manifest", events)
            self.assertEqual(events.count("barrier"), fail_at)
            self.assertEqual(events.count("receipt"), 0 if fail_at == 1 else 1)

    def test_16_each_actual_barrier_component_replacement_is_uncertain(self):
        for fail_at in (1, 2, 3):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                claim_path = root / R.PERMIT.READBACK_CLAIM_PATH
                claim_path.parent.mkdir(parents=True, mode=0o700)
                (root / R.PERMIT.BASE).mkdir(parents=True, mode=0o700)
                events: list[str] = []
                test_case = self

                class ReplacingNamespace(R.ReadbackNamespace):
                    def __init__(self, namespace_root):
                        super().__init__(namespace_root)
                        self.barrier_count = 0

                    def publication_barrier(self, *, receipt_required):
                        self.barrier_count += 1
                        if self.barrier_count == fail_at:
                            claim_inode = claim_path.stat().st_ino
                            dependency_inode = (
                                claim_path.parent.stat().st_ino
                            )
                            original_ancestor = (
                                root / "build" / "offline-source"
                            )
                            moved_ancestor = (
                                root / "build" / "old-offline-source"
                            )
                            original_ancestor.rename(moved_ancestor)
                            claim_path.parent.parent.mkdir(
                                parents=True,
                                mode=0o700,
                            )
                            moved_dependencies = (
                                moved_ancestor
                                / Path(
                                    *Path(
                                        R.PERMIT.READBACK_CLAIM_PATH
                                    ).parent.parts[2:]
                                )
                            )
                            moved_dependencies.rename(
                                claim_path.parent
                            )
                            test_case.assertEqual(
                                claim_path.stat().st_ino,
                                claim_inode,
                            )
                            test_case.assertEqual(
                                claim_path.parent.stat().st_ino,
                                dependency_inode,
                            )
                        return super().publication_barrier(
                            receipt_required=receipt_required
                        )

                with mock.patch.object(
                    R,
                    "preflight",
                    return_value=fake_preflight(),
                ), mock.patch.object(
                    R,
                    "verify_snapshot",
                    return_value={"acceptedResourceCount": 6},
                ):
                    with self.assertRaises(R.ReadbackError) as caught:
                        R.execute(
                            root,
                            snapshot_factory=lambda _root: FakeSnapshot(
                                events
                            ),
                            namespace_factory=ReplacingNamespace,
                        )
                self.assertTrue(caught.exception.consumed)
                self.assertTrue(caught.exception.uncertain)
                self.assertEqual(
                    caught.exception.code,
                    (
                        "E_CONSUMED_STATE_UNCERTAIN"
                        if fail_at == 1
                        else "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN"
                    ),
                )
                cause_codes = []
                cause = caught.exception
                while cause is not None:
                    cause_codes.append(getattr(cause, "code", None))
                    cause = cause.__cause__
                self.assertIn(
                    "E_CLAIM_STATE_UNCERTAIN",
                    cause_codes,
                )
                self.assertIn(
                    "E_COMPONENT_IDENTITY",
                    cause_codes,
                )
                self.assertFalse(
                    os.path.lexists(root / R.PERMIT.READBACK_MANIFEST_PATH)
                )
                self.assertEqual(
                    os.path.lexists(root / R.PERMIT.READBACK_RECEIPT_PATH),
                    fail_at > 1,
                )

    def test_17_permit_consumed_states_translate_without_e_internal(self):
        cases = {
            "claim_only": ("E_CONSUMED", False, "claim_only"),
            "complete": ("E_CONSUMED", False, "complete"),
            "receipt_only": (
                "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
                True,
                "receipt_only",
            ),
            "stale_temporary_namespace": (
                "E_STALE_TEMP_NAMESPACE",
                True,
                "stale_temporary_namespace",
            ),
            "inconsistent": (
                "E_NAMESPACE_STATE_UNCERTAIN",
                True,
                "inconsistent",
            ),
        }
        for state, (code, uncertain, phase) in cases.items():
            with self.subTest(state=state), mock.patch.object(
                R.PERMIT,
                "package_preflight_for_recorder",
                side_effect=R.PERMIT.PermitError("E_CONSUMED", state),
            ):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.preflight()
            self.assertEqual(caught.exception.code, code)
            self.assertNotEqual(caught.exception.code, "E_INTERNAL")
            self.assertTrue(caught.exception.consumed)
            self.assertEqual(caught.exception.uncertain, uncertain)
            self.assertEqual(caught.exception.phase, phase)

    def test_18_claim_receipt_manifest_current_name_replacements_fail(self):
        for slot, relative in (
            ("claim", R.PERMIT.READBACK_CLAIM_PATH),
            ("receipt", R.PERMIT.READBACK_RECEIPT_PATH),
            ("manifest", R.PERMIT.READBACK_MANIFEST_PATH),
        ):
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                claim_path = root / R.PERMIT.READBACK_CLAIM_PATH
                receipt_parent = (root / R.PERMIT.READBACK_RECEIPT_PATH).parent
                claim_path.parent.mkdir(parents=True, mode=0o700)
                receipt_parent.mkdir(parents=True, mode=0o700)
                namespace = R.ReadbackNamespace(root)
                try:
                    target = root / relative
                    target.write_bytes((slot + "-bytes").encode())
                    target.chmod(0o600)
                    info = target.stat()
                    raw = target.read_bytes()
                    expected = {
                        "path": relative,
                        "rawSha256": hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw),
                        "mode": "0600",
                        "ownerUid": info.st_uid,
                        "linkCount": info.st_nlink,
                    }
                    if slot == "claim":
                        creation_fd = R._open_to_owner(
                            namespace.owned_fds,
                            lambda: os.open(
                                target,
                                os.O_RDWR
                                | os.O_CLOEXEC
                                | R.O_NOFOLLOW,
                            ),
                        )
                        namespace.hold_claim(expected, creation_fd)
                        held = namespace.claim
                    else:
                        namespace.install_published(
                            slot,
                            expected,
                            (info.st_dev, info.st_ino),
                        )
                        held = getattr(namespace, slot)
                    self.assertIsNotNone(held)
                    self.assertTrue(held.retained_components)
                    held.barrier()
                    target.rename(target.with_name(target.name + ".old"))
                    target.write_bytes(raw)
                    target.chmod(0o600)
                    with self.assertRaises(R.ReadbackError) as caught:
                        held.barrier()
                    self.assertEqual(
                        caught.exception.code,
                        "E_CURRENT_PATH_IDENTITY",
                    )
                finally:
                    namespace.close()

    def test_18_held_claim_hardlink_fails_identity_barrier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            (root / R.PERMIT.BASE).mkdir(parents=True, mode=0o700)
            target.write_bytes(b"held-claim")
            target.chmod(0o600)
            info = target.stat()
            expected = {
                "path": R.PERMIT.READBACK_CLAIM_PATH,
                "rawSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "bytes": info.st_size,
                "mode": "0600",
                "ownerUid": info.st_uid,
                "linkCount": 1,
            }
            namespace = R.ReadbackNamespace(root)
            try:
                claim_fd = R._open_to_owner(
                    namespace.owned_fds,
                    lambda: os.open(
                        target,
                        os.O_RDWR | os.O_CLOEXEC | R.O_NOFOLLOW,
                    ),
                )
                namespace.hold_claim(expected, claim_fd)
                os.link(target, target.with_name(target.name + ".hardlink"))
                with self.assertRaises(R.ReadbackError) as caught:
                    namespace.claim.barrier()
                self.assertEqual(caught.exception.code, "E_FROZEN")
            finally:
                namespace.close()

    def test_19_readback_namespace_rejects_stale_temp_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / R.PERMIT.READBACK_CLAIM_PATH).parent.mkdir(
                parents=True,
                mode=0o700,
            )
            output_parent = (root / R.PERMIT.READBACK_RECEIPT_PATH).parent
            output_parent.mkdir(parents=True, mode=0o700)
            namespace = R.ReadbackNamespace(root)
            try:
                namespace.preclaim_barrier()
                for prefix in R.PERMIT.READBACK_TEMP_PREFIXES:
                    nfd = (
                        prefix.upper()
                        + unicodedata.normalize("NFD", "é")
                    )
                    nfc = (
                        prefix.upper()
                        + unicodedata.normalize("NFC", "é")
                    )
                    self.assertEqual(
                        R.portable_name(nfd),
                        R.portable_name(nfc),
                    )
                    self.assertTrue(
                        R.has_portable_prefix(
                            [
                                R.PERMIT.STAGING_PREFIX.upper()
                                + nfd[-2:]
                            ],
                            [R.PERMIT.STAGING_PREFIX],
                        )
                    )
                    for variant in (
                        prefix + "stale",
                        nfd,
                        nfc,
                    ):
                        stale = output_parent / variant
                        stale.symlink_to(root / "missing")
                        with self.assertRaises(
                            R.ReadbackError
                        ) as caught:
                            namespace.preclaim_barrier()
                        self.assertEqual(
                            caught.exception.code,
                            "E_STALE_TEMP_NAMESPACE",
                        )
                        stale.unlink()
            finally:
                namespace.close()

    def test_19_retained_preclaim_distinguishes_terminal_states(self):
        cases = {
            "claim_only": (
                ("claim",),
                "E_CONSUMED",
                False,
            ),
            "receipt_only": (
                ("claim", "receipt"),
                "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
                True,
            ),
            "complete": (
                ("claim", "receipt", "manifest"),
                "E_CONSUMED",
                False,
            ),
            "inconsistent": (
                ("receipt",),
                "E_NAMESPACE_STATE_UNCERTAIN",
                True,
            ),
        }
        for state, (occupied, code, uncertain) in cases.items():
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = {
                    "claim": root / R.PERMIT.READBACK_CLAIM_PATH,
                    "receipt": root / R.PERMIT.READBACK_RECEIPT_PATH,
                    "manifest": root / R.PERMIT.READBACK_MANIFEST_PATH,
                }
                paths["claim"].parent.mkdir(parents=True, mode=0o700)
                paths["receipt"].parent.mkdir(parents=True, mode=0o700)
                namespace = R.ReadbackNamespace(root)
                try:
                    for name in occupied:
                        paths[name].write_bytes(b"x")
                    self.assertEqual(namespace.namespace_state(), state)
                    with self.assertRaises(R.ReadbackError) as caught:
                        namespace.preclaim_barrier()
                    self.assertEqual(caught.exception.code, code)
                    self.assertEqual(caught.exception.phase, state)
                    self.assertEqual(caught.exception.uncertain, uncertain)
                finally:
                    namespace.close()

    def test_20_no_network_process_or_acquisition_import_surface(self):
        source = PATH.read_text()
        for token in (
            "import socket",
            "import ssl",
            "import http",
            "import urllib",
            "import subprocess",
            "importlib",
            "runpy",
        ):
            self.assertNotIn(token, source)
        self.assertNotIn("sourceExtraction", source.split("def validate_zip", 1)[0])

    def test_20_full_ast_call_surface_rejects_same_count_bypasses(self):
        preload_mutations = (
            (
                "constant",
                b"MAX_MOD_BYTES = 1 * 1024 * 1024",
                b"MAX_MOD_BYTES = 2 * 1024 * 1024",
            ),
            (
                "branch",
                b"        if args.preflight:\n",
                b"        if not args.preflight:\n",
            ),
            (
                "argument",
                (
                    b'        group.add_argument("--preflight", '
                    b'action="store_true")'
                ),
                (
                    b'        group.add_argument("--preflight-drift", '
                    b'action="store_true")'
                ),
            ),
        )
        for label, old, new in preload_mutations:
            changed = RECORDER_PRELOAD_RAW.replace(old, new, 1)
            with self.subTest(preload_raw_mutation=label):
                self.assertNotEqual(changed, RECORDER_PRELOAD_RAW)
                normalized = _recorder_ast_gate(changed)
                with self.assertRaises(AssertionError):
                    _require_subject_raw_and_normalized_seal(
                        RECORDER_PRELOAD_PERMIT,
                        PRELOAD_TOOL_PATHS[2],
                        changed,
                        normalized,
                    )

        original_calls, original_digest = _canonical_call_surface(
            RECORDER_PRELOAD_RAW
        )
        self.assertEqual(original_digest, RECORDER_CALL_SURFACE_SHA256)
        for changed in (
            RECORDER_PRELOAD_RAW.replace(
                b"bool(chunk)",
                b"input()",
                1,
            ),
            RECORDER_PRELOAD_RAW.replace(
                b"bool(chunk)",
                (
                    b"acquire_p2p_nat_g2_pion_rung3_dependency_"
                    b"wave18_v1_once()"
                ),
                1,
            ),
            RECORDER_PRELOAD_RAW.replace(
                b"bool(chunk)",
                (
                    b"check_p2p_nat_g2_pion_rung3_dependency_"
                    b"wave18_acquisition_v1()"
                ),
                1,
            ),
            RECORDER_PRELOAD_RAW.replace(
                b"first = verify_snapshot(snapshot)",
                b"first = validate_zip(snapshot)",
                1,
            ),
        ):
            with self.subTest(mutation=changed[:80]):
                self.assertNotEqual(changed, RECORDER_PRELOAD_RAW)
                changed_calls, changed_digest = _canonical_call_surface(changed)
                self.assertEqual(
                    sum(original_calls.values()),
                    sum(changed_calls.values()),
                )
                self.assertNotEqual(changed_digest, original_digest)
                with self.assertRaises(AssertionError):
                    _require_call_surface(
                        changed,
                        RECORDER_CALL_SURFACE_SHA256,
                    )

    def test_21_wave18_uncompressed_limits_are_per_zip_and_across_all(self):
        self.assertEqual(
            R.MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP,
            128 * 1024 * 1024,
        )
        self.assertEqual(
            R.MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL,
            384 * 1024 * 1024,
        )
        self.assertLess(
            7_225_800,
            R.MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL,
        )
        source = (R.ROOT / R.__file__).read_text()
        self.assertIn(
            "total <= MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP",
            source,
        )
        self.assertIn(
            "<= MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL",
            source,
        )
        self.assertEqual(R.MAX_AGGREGATE_MOD_BYTES, 3 * 1024 * 1024)
        self.assertEqual(R.MAX_AGGREGATE_ZIP_BYTES, 48 * 1024 * 1024)
        self.assertEqual(R.MAX_AGGREGATE_BYTES, 51 * 1024 * 1024)
        self.assertEqual(R.MAX_ZIP_FILES_ACROSS_ALL, 60_000)
        readback_permit = R.strict_json(
            (R.ROOT / R.PERMIT.PERMIT_PATH).read_bytes(),
            "permit_fixture",
        )
        self.assertEqual(
            readback_permit["resourceLimits"],
            {
                "maximumPackageFileBytes": (
                    R.PERMIT.MAXIMUM_PACKAGE_FILE_BYTES
                ),
                "maximumAcceptedResourceCount": 6,
                "maximumModBytes": R.MAX_MOD_BYTES,
                "maximumZipBytes": R.MAX_ZIP_BYTES,
                "maximumAggregateModBytes": R.MAX_AGGREGATE_MOD_BYTES,
                "maximumAggregateZipBytes": R.MAX_AGGREGATE_ZIP_BYTES,
                "maximumAggregateAcceptedBytes": R.MAX_AGGREGATE_BYTES,
                "maximumZipEntriesPerZip": R.MAX_ZIP_FILES,
                "maximumZipEntriesAcrossAll": R.MAX_ZIP_FILES_ACROSS_ALL,
                "maximumZipEntryNameBytes": R.MAX_ZIP_NAME_BYTES,
                "maximumZipEntryBytes": R.MAX_ZIP_FILE_BYTES,
                "maximumZipUncompressedBytesPerZip": (
                    R.MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP
                ),
                "maximumZipUncompressedBytesAcrossAll": (
                    R.MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL
                ),
            },
        )

    def test_22_partial_component_open_is_registered_and_cleanup_closes_all(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").mkdir(mode=0o700)
            (root / "a" / "not-a-directory").write_bytes(b"x")
            before = len(os.listdir("/dev/fd"))
            root_owner: list[int] = []
            ephemeral: list[int] = []
            root_fd, _ = R._open_root(root.absolute(), "test", root_owner)
            try:
                with self.assertRaises(OSError):
                    R._open_directory_beneath(
                        root_fd,
                        "a/not-a-directory",
                        "test",
                        ephemeral,
                    )
                self.assertTrue(ephemeral)
            finally:
                R._close_owned_fds(ephemeral)
                R._close_owned_fds(root_owner)
            self.assertEqual(len(os.listdir("/dev/fd")), before)

    def test_23_close_all_finishes_before_signal_mask_restore_error(self):
        read_fd, write_fd = os.pipe()
        owner = [read_fd, write_fd]
        real_mask = R.signal.pthread_sigmask

        def restore_then_raise(how, mask):
            result = real_mask(how, mask)
            if how == R.signal.SIG_SETMASK:
                raise RuntimeError("synthetic restore error")
            return result

        with mock.patch.object(
            R.signal,
            "pthread_sigmask",
            side_effect=restore_then_raise,
        ):
            with self.assertRaises(RuntimeError):
                R._close_owned_fds(owner)
        self.assertEqual(owner, [])
        for fd in (read_fd, write_fd):
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_24_execute_cleanup_is_independent_and_not_overclassified(self):
        events: list[str] = []

        class BadSnapshot(FakeSnapshot):
            def close(self):
                self.events.append("snapshot_close_attempted")
                raise RuntimeError("synthetic snapshot close")

        class BadNamespace(FakeNamespace):
            def close(self):
                self.events.append("namespace_close_attempted")
                raise RuntimeError("synthetic namespace close")

        before_umask = os.umask(0o077)
        os.umask(before_umask)
        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ), mock.patch.object(
            R,
            "create_readback_claim",
            return_value=({"path": "claim"}, -1),
        ), mock.patch.object(
            R,
            "verify_snapshot",
            side_effect=R.ReadbackError("E_SYNTHETIC", "verification"),
        ):
            with self.assertRaises(R.ReadbackError) as caught:
                R.execute(
                    Path("/unused"),
                    snapshot_factory=lambda _root: BadSnapshot(events),
                    namespace_factory=lambda _root: BadNamespace(events),
                )
        self.assertEqual(caught.exception.code, "E_CLEANUP_STATE_UNCERTAIN")
        self.assertTrue(caught.exception.consumed)
        self.assertFalse(caught.exception.uncertain)
        self.assertIn("snapshot_close_attempted", events)
        self.assertIn("namespace_close_attempted", events)
        observed_umask = os.umask(before_umask)
        os.umask(observed_umask)
        self.assertEqual(observed_umask, before_umask)

    def test_25_checker_bootstrap_restore_failure_closes_opened_fd(self):
        before = len(os.listdir("/dev/fd"))
        real_mask = R.signal.pthread_sigmask
        restore_calls = 0

        def fail_first_restore(how, mask):
            nonlocal restore_calls
            result = real_mask(how, mask)
            if how == R.signal.SIG_SETMASK:
                restore_calls += 1
                if restore_calls == 1:
                    raise RuntimeError("synthetic bootstrap restore")
            return result

        with mock.patch.object(
            R.signal,
            "pthread_sigmask",
            side_effect=fail_first_restore,
        ):
            with self.assertRaises(RuntimeError):
                R.load_readback_checker()
        self.assertEqual(len(os.listdir("/dev/fd")), before)

    def test_26_claim_open_restore_failure_is_consumed_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            (root / R.PERMIT.BASE).mkdir(parents=True, mode=0o700)
            namespace = R.ReadbackNamespace(root)
            baseline_owned = tuple(namespace.owned_fds)
            real_mask = R.signal.pthread_sigmask
            restore_calls = 0

            def fail_claim_restore(how, mask):
                nonlocal restore_calls
                result = real_mask(how, mask)
                if how == R.signal.SIG_SETMASK:
                    restore_calls += 1
                    if restore_calls == 5:
                        raise RuntimeError("synthetic claim restore")
                return result

            try:
                with mock.patch.object(
                    R.signal,
                    "pthread_sigmask",
                    side_effect=fail_claim_restore,
                ):
                    with self.assertRaises(R.ReadbackError) as caught:
                        R.create_readback_claim(
                            root,
                            "1" * 32,
                            {"x": 1},
                            namespace.root_fd,
                            namespace.owned_fds,
                        )
                self.assertEqual(
                    caught.exception.code,
                    "E_CLAIM_STATE_UNCERTAIN",
                )
                self.assertTrue(caught.exception.consumed)
                self.assertTrue(caught.exception.uncertain)
                self.assertTrue(os.path.lexists(target))
                self.assertEqual(
                    tuple(namespace.owned_fds),
                    baseline_owned,
                )
            finally:
                namespace.close()

    def test_27_atomic_temp_restore_failure_cleans_reserved_name_and_fds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_parent = root / "out"
            output_parent.mkdir(mode=0o700)
            before = len(os.listdir("/dev/fd"))
            real_mask = R.signal.pthread_sigmask
            restore_calls = 0

            def fail_temp_restore(how, mask):
                nonlocal restore_calls
                result = real_mask(how, mask)
                if how == R.signal.SIG_SETMASK:
                    restore_calls += 1
                    if restore_calls == 4:
                        raise RuntimeError("synthetic temp restore")
                return result

            with mock.patch.object(
                R.signal,
                "pthread_sigmask",
                side_effect=fail_temp_restore,
            ):
                with self.assertRaises(RuntimeError):
                    R.atomic_publish(
                        root,
                        "out/result.json",
                        R.content_bound({"value": 1}),
                    )
            self.assertFalse((output_parent / "result.json").exists())
            self.assertEqual(list(output_parent.iterdir()), [])
            self.assertEqual(len(os.listdir("/dev/fd")), before)

    def test_28_claim_owner_append_failure_is_consumed_uncertainty(self):
        class FailingAppendOwner(list):
            def append(self, _fd):
                raise MemoryError("synthetic owner append")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            owner = FailingAppendOwner()
            before = len(os.listdir("/dev/fd"))
            with self.assertRaises(R.ReadbackError) as caught:
                R.create_readback_claim(
                    root,
                    "1" * 32,
                    {"x": 1},
                    fd_owner=owner,
                )
            self.assertEqual(
                caught.exception.code,
                "E_CLAIM_STATE_UNCERTAIN",
            )
            self.assertTrue(caught.exception.consumed)
            self.assertTrue(caught.exception.uncertain)
            self.assertTrue(os.path.lexists(target))
            self.assertEqual(owner, [])
            self.assertEqual(len(os.listdir("/dev/fd")), before)

    def test_29_atomic_temp_owner_append_failure_cleans_name_and_fds(self):
        class FailingAppendOwner(list):
            def append(self, _fd):
                raise MemoryError("synthetic owner append")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_parent = root / "out"
            output_parent.mkdir(mode=0o700)
            before = len(os.listdir("/dev/fd"))
            real_open_to_owner = R._open_to_owner
            real_close_owned_fds = R._close_owned_fds
            open_calls = 0
            close_calls = 0

            def fail_temporary_transfer(owner, opener, on_opened=None):
                nonlocal open_calls
                open_calls += 1
                if open_calls == 4:
                    return real_open_to_owner(
                        FailingAppendOwner(),
                        opener,
                        on_opened,
                    )
                return real_open_to_owner(owner, opener, on_opened)

            def fail_orphan_cleanup(owner):
                nonlocal close_calls
                close_calls += 1
                real_close_owned_fds(owner)
                if close_calls == 2:
                    raise RuntimeError("synthetic orphan cleanup")

            with mock.patch.object(
                R,
                "_open_to_owner",
                side_effect=fail_temporary_transfer,
            ), mock.patch.object(
                R,
                "_close_owned_fds",
                side_effect=fail_orphan_cleanup,
            ):
                with self.assertRaises(RuntimeError):
                    R.atomic_publish(
                        root,
                        "out/result.json",
                        R.content_bound({"value": 1}),
                    )
            self.assertEqual(open_calls, 4)
            self.assertEqual(close_calls, 3)
            self.assertFalse((output_parent / "result.json").exists())
            self.assertEqual(list(output_parent.iterdir()), [])
            self.assertEqual(len(os.listdir("/dev/fd")), before)

    def test_30_existing_claim_cleanup_failure_stays_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            target.write_bytes(b"existing")
            real_close_owned_fds = R._close_owned_fds
            close_calls = 0

            def close_then_fail(owner):
                nonlocal close_calls
                close_calls += 1
                real_close_owned_fds(owner)
                if close_calls == 1:
                    raise RuntimeError("synthetic traversal cleanup")

            with mock.patch.object(
                R,
                "_close_owned_fds",
                side_effect=close_then_fail,
            ):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.create_readback_claim(root, "1" * 32, {"x": 1})
            self.assertEqual(caught.exception.code, "E_CONSUMED")
            self.assertEqual(caught.exception.phase, "claim_cleanup")
            self.assertTrue(caught.exception.consumed)
            self.assertFalse(caught.exception.uncertain)

    def test_31_bulk_close_retries_and_object_close_remains_retryable(self):
        read_fd, write_fd = os.pipe()
        snapshot = object.__new__(R.FrozenSnapshot)
        snapshot.closed = False
        snapshot.owned_fds = [read_fd, write_fd]
        snapshot.root_fd = read_fd
        real_close = R.os.close
        transient_attempts = 0

        def fail_read_once(fd):
            nonlocal transient_attempts
            if fd == read_fd and transient_attempts == 0:
                transient_attempts += 1
                raise OSError(errno.EIO, "synthetic transient close")
            return real_close(fd)

        with mock.patch.object(R.os, "close", side_effect=fail_read_once):
            snapshot.close()
        self.assertTrue(snapshot.closed)
        self.assertEqual(snapshot.owned_fds, [])
        self.assertEqual(transient_attempts, 1)
        for fd in (read_fd, write_fd):
            with self.assertRaises(OSError):
                os.fstat(fd)

        read_fd, write_fd = os.pipe()
        snapshot = object.__new__(R.FrozenSnapshot)
        snapshot.closed = False
        snapshot.owned_fds = [read_fd, write_fd]
        snapshot.root_fd = read_fd

        def refuse_read_close(fd):
            if fd == read_fd:
                raise OSError(errno.EIO, "synthetic persistent close")
            return real_close(fd)

        with mock.patch.object(R.os, "close", side_effect=refuse_read_close):
            with self.assertRaises(OSError):
                snapshot.close()
        self.assertFalse(snapshot.closed)
        self.assertEqual(snapshot.owned_fds, [read_fd])
        os.fstat(read_fd)
        with self.assertRaises(OSError):
            os.fstat(write_fd)

        snapshot.close()
        self.assertTrue(snapshot.closed)
        self.assertEqual(snapshot.owned_fds, [])
        with self.assertRaises(OSError):
            os.fstat(read_fd)

    def test_32_umask_activation_restore_error_restores_original_umask(self):
        before_umask = os.umask(0o077)
        os.umask(before_umask)
        real_mask = R.signal.pthread_sigmask
        restore_calls = 0

        def fail_first_restore(how, mask):
            nonlocal restore_calls
            result = real_mask(how, mask)
            if how == R.signal.SIG_SETMASK:
                restore_calls += 1
                if restore_calls == 1:
                    raise RuntimeError("synthetic activation restore")
            return result

        with mock.patch.object(
            R.signal,
            "pthread_sigmask",
            side_effect=fail_first_restore,
        ):
            with self.assertRaises(RuntimeError):
                R.execute(Path("/unused"))
        observed_umask = os.umask(0o077)
        os.umask(observed_umask)
        self.assertEqual(observed_umask, before_umask)

    def test_33_existing_consumed_survives_outer_umask_retry_failure(self):
        events: list[str] = []

        class ExistingNamespace(FakeNamespace):
            def preclaim_barrier(self):
                raise R.ReadbackError(
                    "E_CONSUMED",
                    "claim_only",
                    consumed=True,
                    uncertain=False,
                )

        real_restore = R._RestrictedUmask.restore
        restore_calls = 0

        def restore_then_raise(guard):
            nonlocal restore_calls
            restore_calls += 1
            if restore_calls == 1:
                raise RuntimeError("synthetic umask cleanup")
            real_restore(guard)
            raise RuntimeError("synthetic outer umask retry")

        with mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ), mock.patch.object(
            R._RestrictedUmask,
            "restore",
            side_effect=restore_then_raise,
            autospec=True,
        ):
            with self.assertRaises(R.ReadbackError) as caught:
                R.execute(
                    Path("/unused"),
                    namespace_factory=lambda _root: ExistingNamespace(events),
                )
        self.assertEqual(
            caught.exception.code,
            "E_CLEANUP_STATE_UNCERTAIN",
        )
        self.assertTrue(caught.exception.consumed)
        self.assertFalse(caught.exception.uncertain)

    def test_34_existing_claim_restore_error_stays_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / R.PERMIT.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True, mode=0o700)
            target.write_bytes(b"existing")
            real_mask = R.signal.pthread_sigmask
            restore_calls = 0
            claim_restore_call = (
                len(R.PERMIT.READBACK_CLAIM_PATH.split("/")) + 1
            )

            def fail_claim_restore(how, mask):
                nonlocal restore_calls
                result = real_mask(how, mask)
                if how == R.signal.SIG_SETMASK:
                    restore_calls += 1
                    if restore_calls == claim_restore_call:
                        raise RuntimeError("synthetic claim restore")
                return result

            with mock.patch.object(
                R.signal,
                "pthread_sigmask",
                side_effect=fail_claim_restore,
            ):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.create_readback_claim(root, "1" * 32, {"x": 1})
            self.assertEqual(caught.exception.code, "E_CONSUMED")
            self.assertTrue(caught.exception.consumed)
            self.assertFalse(caught.exception.uncertain)

    def test_35_first_publication_barrier_output_or_temp_is_uncertain(self):
        cases = ("receipt", "manifest", "temporary")
        for occupied in cases:
            with self.subTest(occupied=occupied), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                claim_path = root / R.PERMIT.READBACK_CLAIM_PATH
                claim_path.parent.mkdir(parents=True, mode=0o700)
                output_parent = root / R.PERMIT.BASE
                output_parent.mkdir(parents=True, mode=0o700)
                namespace = R.ReadbackNamespace(root)
                claim_fd = -1
                try:
                    claim, claim_fd = R.create_readback_claim(
                        root,
                        "1" * 32,
                        {"x": 1},
                        namespace.root_fd,
                        namespace.owned_fds,
                    )
                    namespace.hold_claim(claim, claim_fd)
                    claim_fd = -1
                    if occupied == "receipt":
                        (
                            root / R.PERMIT.READBACK_RECEIPT_PATH
                        ).write_bytes(b"unexpected")
                    elif occupied == "manifest":
                        (
                            root / R.PERMIT.READBACK_MANIFEST_PATH
                        ).write_bytes(b"unexpected")
                    else:
                        (
                            output_parent
                            / (
                                R.PERMIT.READBACK_TEMP_PREFIXES[0]
                                + "unexpected"
                            )
                        ).write_bytes(b"unexpected")
                    with self.assertRaises(R.ReadbackError) as caught:
                        namespace.publication_barrier(
                            receipt_required=False,
                        )
                    self.assertTrue(caught.exception.consumed)
                    self.assertTrue(caught.exception.uncertain)
                finally:
                    if claim_fd >= 0:
                        if claim_fd in namespace.owned_fds:
                            R._close_owned_fd(
                                namespace.owned_fds,
                                claim_fd,
                            )
                        else:
                            os.close(claim_fd)
                    namespace.close()

    def test_36_observed_output_survives_ephemeral_cleanup_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claim_path = root / R.PERMIT.READBACK_CLAIM_PATH
            claim_path.parent.mkdir(parents=True, mode=0o700)
            (root / R.PERMIT.BASE).mkdir(parents=True, mode=0o700)
            namespace = R.ReadbackNamespace(root)
            claim_fd = -1
            try:
                claim, claim_fd = R.create_readback_claim(
                    root,
                    "1" * 32,
                    {"x": 1},
                    namespace.root_fd,
                    namespace.owned_fds,
                )
                namespace.hold_claim(claim, claim_fd)
                claim_fd = -1
                (
                    root / R.PERMIT.READBACK_RECEIPT_PATH
                ).write_bytes(b"unexpected")
                real_close_owned_fds = R._close_owned_fds
                close_calls = 0
                observation_cleanup_failures = 0
                observation_owner_count = 2 * len(
                    R._safe_relative(R.PERMIT.BASE, "test")
                )

                def fail_observation_cleanup(owner):
                    nonlocal close_calls, observation_cleanup_failures
                    close_calls += 1
                    owned_count = len(owner)
                    real_close_owned_fds(owner)
                    if (
                        owned_count == observation_owner_count
                        and observation_cleanup_failures == 0
                    ):
                        observation_cleanup_failures += 1
                        raise RuntimeError("synthetic observation cleanup")

                with mock.patch.object(
                    R,
                    "_close_owned_fds",
                    side_effect=fail_observation_cleanup,
                ):
                    with self.assertRaises(R.ReadbackError) as caught:
                        namespace.publication_barrier(
                            receipt_required=False,
                        )
                self.assertEqual(caught.exception.code, "E_OUTPUT_STATE")
                self.assertTrue(caught.exception.consumed)
                self.assertTrue(caught.exception.uncertain)
                self.assertGreater(close_calls, 3)
                self.assertEqual(observation_cleanup_failures, 1)
            finally:
                if claim_fd >= 0:
                    if claim_fd in namespace.owned_fds:
                        R._close_owned_fd(
                            namespace.owned_fds,
                            claim_fd,
                        )
                    else:
                        os.close(claim_fd)
                namespace.close()

    def test_37_preclaim_state_survives_ephemeral_cleanup_failure(self):
        cases = {
            "claim": ("E_CONSUMED", False),
            "receipt": (
                "E_RECEIPT_ONLY_OR_TERMINAL_UNCERTAIN",
                True,
            ),
            "stale": ("E_STALE_TEMP_NAMESPACE", True),
        }
        for occupied, (code, uncertain) in cases.items():
            with self.subTest(occupied=occupied), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                claim = root / R.PERMIT.READBACK_CLAIM_PATH
                receipt = root / R.PERMIT.READBACK_RECEIPT_PATH
                claim.parent.mkdir(parents=True, mode=0o700)
                receipt.parent.mkdir(parents=True, mode=0o700)
                namespace = R.ReadbackNamespace(root)
                try:
                    if occupied == "claim":
                        claim.write_bytes(b"observed")
                    elif occupied == "receipt":
                        claim.write_bytes(b"observed")
                        receipt.write_bytes(b"observed")
                    else:
                        (
                            receipt.parent
                            / (
                                R.PERMIT.READBACK_TEMP_PREFIXES[0]
                                + "observed"
                            )
                        ).write_bytes(b"observed")
                    real_close_owned_fds = R._close_owned_fds

                    def close_then_fail(owner):
                        real_close_owned_fds(owner)
                        raise RuntimeError("synthetic ephemeral cleanup")

                    with mock.patch.object(
                        R,
                        "_close_owned_fds",
                        side_effect=close_then_fail,
                    ):
                        with self.assertRaises(R.ReadbackError) as caught:
                            namespace.namespace_state()
                    self.assertEqual(caught.exception.code, code)
                    self.assertTrue(caught.exception.consumed)
                    self.assertEqual(
                        caught.exception.uncertain,
                        uncertain,
                    )
                finally:
                    namespace.close()

    def test_38_output_fault_state_matrix_is_exact_and_typed(self):
        cases = (
            (
                R.ReadbackError("E_SYNTHETIC", "verification"),
                "failed_closed_not_consumed",
            ),
            (
                R.ReadbackError(
                    "E_SYNTHETIC",
                    "verification",
                    consumed=True,
                ),
                "consumed_failure_no_retry",
            ),
            (
                R.ReadbackError(
                    "E_SYNTHETIC",
                    "publication",
                    consumed=True,
                    uncertain=True,
                ),
                "consumed_terminal_state_uncertain",
            ),
            (
                R.ReadbackError(
                    "E_CONSUMED",
                    "claim_only",
                    consumed=True,
                ),
                "already_consumed",
            ),
            (
                RuntimeError("synthetic internal fault"),
                "failed_closed_not_consumed",
            ),
        )
        expected_keys = {
            "documentType",
            "schemaVersion",
            "status",
            "failureCode",
            "failurePhase",
            "retryAllowed",
            "networkAuthorized",
            "externalAuthenticationRequired",
            "userActionRequired",
        }
        for error, expected_status in cases:
            sink = type("Sink", (), {"buffer": io.BytesIO()})()
            with self.subTest(
                error=type(error).__name__,
                status=expected_status,
            ), mock.patch.object(
                sys,
                "stdout",
                sink,
            ), mock.patch.object(
                R,
                "execute",
                side_effect=error,
            ):
                self.assertEqual(R.main(["--execute"]), 1)
            report = json.loads(sink.buffer.getvalue())
            self.assertEqual(set(report), expected_keys)
            self.assertEqual(report["status"], expected_status)
            for key in (
                "retryAllowed",
                "networkAuthorized",
                "externalAuthenticationRequired",
                "userActionRequired",
            ):
                self.assertIs(type(report[key]), bool)
                self.assertIs(report[key], False)

    def test_38_post_success_reporting_failure_is_consumed(self):
        reported = R._post_success_reporting_failure()
        self.assertEqual(
            reported["status"],
            "consumed_success_reporting_failed",
        )
        self.assertEqual(
            reported["failureCode"],
            "E_POST_SUCCESS_REPORTING",
        )
        self.assertEqual(reported["failurePhase"], "reporting")
        self.assertIs(reported["retryAllowed"], False)
        self.assertIs(reported["readbackPublicationComplete"], True)
        self.assertIs(
            reported["completionAppliesToRetainedSnapshot"],
            True,
        )
        self.assertIs(reported["externalAuthenticationRequired"], False)
        self.assertIs(reported["userActionRequired"], False)

    def test_39_runpy_invalid_argument_cannot_write_or_use_network(self):
        real_os_open = os.open
        write_open_attempts: list[tuple[object, int]] = []
        write_flags = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | os.O_TRUNC
            | os.O_APPEND
        )

        def read_only_os_open(path, flags, *args, **kwargs):
            if flags & write_flags:
                write_open_attempts.append((path, flags))
                raise AssertionError(
                    "runpy readback test attempted a filesystem write"
                )
            return real_os_open(path, flags, *args, **kwargs)

        invalid_vectors = (
            ["--exe"],
            ["--execute", "--execute"],
            ["--execute", "additional"],
            ["--preflight", "--preflight"],
            ["--preflight", "additional"],
            ["--invalid"],
        )
        for arguments in invalid_vectors:
            with self.subTest(arguments=arguments):
                sink = type("Sink", (), {"buffer": io.BytesIO()})()
                with mock.patch.object(
                    sys,
                    "argv",
                    [str(PATH), *arguments],
                ), mock.patch.object(
                    sys,
                    "stdout",
                    sink,
                ), mock.patch.object(
                    os,
                    "open",
                    side_effect=read_only_os_open,
                ):
                    with self.assertRaises(SystemExit) as caught:
                        runpy.run_path(str(PATH), run_name="__main__")
                self.assertEqual(caught.exception.code, 1)
                report = json.loads(sink.buffer.getvalue())
                self.assertEqual(report["failureCode"], "E_ARGUMENT")
                self.assertEqual(
                    report["status"],
                    "failed_closed_not_consumed",
                )
        self.assertEqual(write_open_attempts, [])
        self.assertEqual(NETWORK_ATTEMPTS, [])
        for relative in (
            R.PERMIT.READBACK_CLAIM_PATH,
            R.PERMIT.READBACK_RECEIPT_PATH,
            R.PERMIT.READBACK_MANIFEST_PATH,
        ):
            self.assertFalse(os.path.lexists(R.ROOT / relative))

    def test_40_imported_main_enforces_exact_argument_vectors(self):
        R.validate_argument_vector(["--preflight"])
        R.validate_argument_vector(["--execute"])
        invalid_vectors = (
            [],
            ["--exe"],
            ["--execute", "--execute"],
            ["--execute", "additional"],
            ["--preflight", "--preflight"],
            ["--preflight", "additional"],
            ["--execute", "--preflight"],
        )
        for arguments in invalid_vectors:
            with self.subTest(arguments=arguments):
                with self.assertRaises(R.ReadbackError) as caught:
                    R.validate_argument_vector(arguments)
                self.assertEqual(caught.exception.code, "E_ARGUMENT")

        preflight_sink = type("Sink", (), {"buffer": io.BytesIO()})()
        with mock.patch.object(
            sys,
            "stdout",
            preflight_sink,
        ), mock.patch.object(
            R,
            "preflight",
            return_value=fake_preflight(),
        ) as preflight_call, mock.patch.object(
            R,
            "execute",
            side_effect=AssertionError("preflight invoked execute"),
        ):
            self.assertEqual(R.main(["--preflight"]), 0)
        preflight_call.assert_called_once_with()
        preflight_report = json.loads(preflight_sink.buffer.getvalue())
        self.assertEqual(
            preflight_report["status"],
            "authorized_not_consumed",
        )
        self.assertIs(
            preflight_report["frozenAcquisitionInputOpened"],
            False,
        )

        execute_sink = type("Sink", (), {"buffer": io.BytesIO()})()
        synthetic_result = {
            "documentType": "synthetic-wave18-readback-result",
            "status": "complete",
        }
        with mock.patch.object(
            sys,
            "stdout",
            execute_sink,
        ), mock.patch.object(
            R,
            "execute",
            return_value=synthetic_result,
        ) as execute_call, mock.patch.object(
            R,
            "preflight",
            side_effect=AssertionError("execute invoked preflight directly"),
        ):
            self.assertEqual(R.main(["--execute"]), 0)
        execute_call.assert_called_once_with()
        self.assertEqual(
            json.loads(execute_sink.buffer.getvalue()),
            synthetic_result,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
