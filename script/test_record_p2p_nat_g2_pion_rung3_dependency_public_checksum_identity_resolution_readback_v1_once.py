#!/usr/bin/env python3
"""Tests for the one-use offline SumDB identity readback recorder."""

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

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import unittest
from unittest import mock

PATH = Path(__file__).with_name(
    "record_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_readback_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location(
    "sumdb_identity_readback_recorder_v1_tests",
    PATH,
)
assert SPEC and SPEC.loader
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class OfflineReadbackRecorderV1Tests(unittest.TestCase):
    def actual_snapshot(self):
        snapshot = R.FrozenSnapshot()
        self.addCleanup(snapshot.close)
        return snapshot

    def test_01_actual_lookup_signed_note_and_record_are_strict(self):
        snapshot = self.actual_snapshot()
        raw = snapshot.raw(
            f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/lookup.response"
        )
        parsed = R.parse_lookup_record(raw)
        self.assertEqual(parsed["recordNumber"], 468)
        self.assertEqual(parsed["treeSize"], 57_977_200)
        self.assertEqual(parsed["moduleZipH1"], R.PERMIT.TARGET_ZIP_H1)
        self.assertEqual(parsed["goModH1"], R.PERMIT.TARGET_MOD_H1)

    def test_02_actual_snapshot_independent_readback_passes(self):
        snapshot = self.actual_snapshot()
        verified = R.verify_snapshot(snapshot)
        self.assertEqual(
            verified["executionAttemptId"],
            R.PERMIT.ATTEMPT_ID,
        )
        self.assertEqual(verified["evidenceFileCount"], 11)
        self.assertEqual(verified["tileFileCount"], 9)
        self.assertEqual(verified["aggregateResponseBodyBytes"], 54_106)
        self.assertEqual(verified["inclusionProofHashCount"], 26)
        self.assertEqual(verified["consistencyProofHashCount"], 25)
        self.assertEqual(
            verified["resolvedModuleZipH1"],
            R.PERMIT.TARGET_ZIP_H1,
        )

    def test_03_independent_plan_matches_exact_nine_paths(self):
        plan = R.derive_independent_plan(468, 57_977_200)
        self.assertEqual(
            [row["path"] for row in plan["tiles"]],
            [
                "/tile/8/0/001",
                "/tile/8/0/x226/060",
                "/tile/8/0/x226/473.p/112",
                "/tile/8/1/000",
                "/tile/8/1/883",
                "/tile/8/1/884.p/169",
                "/tile/8/2/000",
                "/tile/8/2/003.p/116",
                "/tile/8/3/000.p/3",
            ],
        )

    def test_04_lookup_mutations_fail_signature_or_record(self):
        snapshot = self.actual_snapshot()
        raw = snapshot.raw(
            f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/lookup.response"
        )
        cases = (
            raw.replace(R.PERMIT.TARGET_ZIP_H1.encode(), b"h1:" + b"A" * 44, 1),
            raw.replace(R.PERMIT.TARGET_MOD_H1.encode(), b"h1:" + b"B" * 44, 1),
            raw[:-2] + bytes([raw[-2] ^ 1]) + raw[-1:],
            raw.replace(b"\n\n", b"\nextra\n\n", 1),
        )
        for changed in cases:
            with self.subTest():
                with self.assertRaises(R.ReadbackError):
                    R.parse_lookup_record(changed)

    def test_05_ed25519_signature_mutation_fails(self):
        snapshot = self.actual_snapshot()
        raw = snapshot.raw(
            f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/lookup.response"
        )
        note = raw[raw.find(b"\n\n") + 2 :]
        R.verify_signed_tree_note(note)
        changed = bytearray(note)
        changed[-3] = ord("A") if changed[-3] != ord("A") else ord("B")
        with self.assertRaises(R.ReadbackError):
            R.verify_signed_tree_note(bytes(changed))

    def test_06_tile_body_mutation_breaks_recomputed_proof(self):
        snapshot = self.actual_snapshot()
        lookup = R.parse_lookup_record(
            snapshot.raw(
                f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/lookup.response"
            )
        )
        plan = R.derive_independent_plan(
            lookup["recordNumber"],
            lookup["treeSize"],
        )
        evidence = json.loads(
            snapshot.raw(
                f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/evidence.json"
            )
        )
        bodies = {
            row["path"]: snapshot.raw(
                f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/{row['file']['name']}"
            )
            for row in evidence["tiles"]
        }
        first = plan["tiles"][0]["path"]
        changed = bytearray(bodies[first])
        changed[0] ^= 1
        bodies[first] = bytes(changed)
        inclusion = [
            R.span_hash(span, plan["nodeSpecs"], bodies)
            for span in plan["inclusionSpans"]
        ]
        with self.assertRaises(R.ReadbackError):
            R.verify_inclusion_path(
                lookup["recordLeafHash"],
                lookup["recordNumber"],
                lookup["treeSize"],
                inclusion,
                lookup["root"],
            )

    def test_07_content_binding_rejects_mutation(self):
        snapshot = self.actual_snapshot()
        raw = snapshot.raw(
            f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/evidence.json"
        )
        value = R.strict_json(raw, "test")
        R.verify_content_binding(value, "test")
        value["status"] = "mutated"
        with self.assertRaises(R.ReadbackError):
            R.verify_content_binding(value, "test")

    def test_08_actual_preflight_is_no_write_offline_and_auth_free(self):
        before = {
            path: (R.ROOT / path).exists()
            for path in (
                R.PERMIT.READBACK_CLAIM_PATH,
                R.PERMIT.READBACK_RECEIPT_PATH,
                R.PERMIT.READBACK_MANIFEST_PATH,
            )
        }
        protected = {
            str(R.ROOT / row["path"])
            for row in R.PERMIT.ALL_FROZEN_FILES
        }
        protected.add(str(R.ROOT / R.PERMIT.EVIDENCE_DIRECTORY_PATH))
        real_open = os.open

        def guarded_open(path, *args, **kwargs):
            if str(path) in protected:
                raise AssertionError(
                    f"pre-claim frozen execution input open: {path}"
                )
            return real_open(path, *args, **kwargs)

        with mock.patch.object(
            R.PERMIT.HeldFile,
            "__init__",
            side_effect=AssertionError(
                "recorder preflight opened a frozen execution input"
            ),
        ), mock.patch.object(R.os, "open", side_effect=guarded_open):
            result = R.preflight()
        after = {
            path: (R.ROOT / path).exists()
            for path in before
        }
        self.assertEqual(before, after)
        self.assertEqual(result["status"], "preflight_passed_no_network_no_writes")
        self.assertEqual(result["networkRequestAttemptCount"], 0)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertEqual(result["sourceAcquisitionCount"], 0)
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])

    def test_09_cli_preflight_and_default_failure_are_canonical(self):
        command = ["python3", "-I", "-B", "-S", R.PERMIT.RECORDER_PATH]
        preflight = subprocess.run(
            [*command, "--preflight"],
            cwd=R.ROOT,
            check=True,
            capture_output=True,
        )
        self.assertEqual(
            preflight.stdout,
            R.canonical_bytes(json.loads(preflight.stdout)),
        )
        default = subprocess.run(
            command,
            cwd=R.ROOT,
            check=False,
            capture_output=True,
        )
        self.assertEqual(default.returncode, 1)
        self.assertEqual(json.loads(default.stdout)["failureCode"], "E_ARGUMENT")

    def make_temp_root(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / R.PERMIT.DEPENDENCY_ROOT).mkdir(parents=True)
        os.chmod(root / R.PERMIT.DEPENDENCY_ROOT, 0o700)
        (root / R.PERMIT.READBACK_RECEIPT_PATH).parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        return temporary, root

    def test_10_claim_is_exclusive_mode_0600_and_durable_shape(self):
        temporary, root = self.make_temp_root()
        self.addCleanup(temporary.cleanup)
        binding = {"permit": {}, "checker": {}, "recorder": {}}
        result = R.create_readback_claim(root, "a" * 32, binding)
        path = root / R.PERMIT.READBACK_CLAIM_PATH
        info = path.stat()
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
        self.assertEqual(info.st_nlink, 1)
        self.assertEqual(result["rawSha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        value = json.loads(path.read_bytes())
        self.assertEqual(value["readbackAttemptId"], "a" * 32)
        self.assertEqual(value["authorityBinding"], binding)
        with self.assertRaises(R.ReadbackError) as rejected:
            R.create_readback_claim(root, "b" * 32, binding)
        self.assertEqual(rejected.exception.code, "E_CONSUMED")

    def test_11_atomic_publication_is_no_replace_and_mode_0600(self):
        temporary, root = self.make_temp_root()
        self.addCleanup(temporary.cleanup)

        def rename(src_fd, src, dst_fd, dst):
            try:
                os.stat(dst, dir_fd=dst_fd)
            except FileNotFoundError:
                pass
            else:
                raise R.ReadbackError("E_RENAME", "publication")
            os.rename(src, dst, src_dir_fd=src_fd, dst_dir_fd=dst_fd)

        payload = R.content_bound({"status": "synthetic"})
        result = R.atomic_publish(
            root,
            R.PERMIT.READBACK_RECEIPT_PATH,
            payload,
            rename_fn=rename,
        )
        target = root / R.PERMIT.READBACK_RECEIPT_PATH
        self.assertEqual(target.read_bytes(), R.canonical_bytes(payload))
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(result["rawSha256"], R.sha256(target.read_bytes()))
        with self.assertRaises(R.ReadbackError):
            R.atomic_publish(
                root,
                R.PERMIT.READBACK_RECEIPT_PATH,
                payload,
                rename_fn=rename,
            )

    def test_12_atomic_failure_cleans_temporary_and_writes_no_output(self):
        temporary, root = self.make_temp_root()
        self.addCleanup(temporary.cleanup)

        def reject(*args):
            raise R.ReadbackError("E_RENAME", "publication")

        with self.assertRaises(R.ReadbackError):
            R.atomic_publish(
                root,
                R.PERMIT.READBACK_RECEIPT_PATH,
                {"status": "synthetic"},
                rename_fn=reject,
            )
        parent = (root / R.PERMIT.READBACK_RECEIPT_PATH).parent
        self.assertFalse((root / R.PERMIT.READBACK_RECEIPT_PATH).exists())
        self.assertFalse(any(".tmp-" in item.name for item in parent.iterdir()))

    def test_13_execution_authority_binding_is_exact(self):
        binding = R.execution_authority_binding()
        self.assertEqual(
            binding["permit"]["rawSha256"],
            R.PERMIT.EXECUTION_AUTHORITY[0]["rawSha256"],
        )
        self.assertEqual(
            binding["checker"]["rawSha256"],
            R.PERMIT.EXECUTION_AUTHORITY[1]["rawSha256"],
        )
        self.assertEqual(
            binding["runner"]["rawSha256"],
            R.PERMIT.EXECUTION_AUTHORITY[2]["rawSha256"],
        )

    def test_14_recorder_reverse_pin_and_normalized_hash_are_exact(self):
        checker = R.READBACK_CHECKER_PATH.read_bytes()
        recorder = Path(R.__file__).read_bytes()
        self.assertEqual(
            R.EXPECTED_READBACK_CHECKER_RAW,
            hashlib.sha256(checker).hexdigest(),
        )
        self.assertEqual(
            hashlib.sha256(
                R.PERMIT.normalized_recorder_bytes(recorder)
            ).hexdigest(),
            R.PERMIT.EXPECTED_RECORDER_NORMALIZED_SHA256,
        )

    def test_15_span_plan_small_tree_is_deterministic(self):
        self.assertEqual(R.inclusion_spans(4, 0, 5), [(0, 4)])
        self.assertEqual(
            R.consistency_spans(3, 5),
            [(2, 1), (3, 1), (0, 2), (4, 1)],
        )
        for start, count in (
            (0, 1),
            (0, 3),
            (3, 5),
            (256, 257),
        ):
            nodes = R.perfect_nodes(start, count)
            covered = sum(1 << level for level, _ in nodes)
            self.assertEqual(covered, count)

    def test_16_proof_hash_bundle_matches_frozen_evidence(self):
        snapshot = self.actual_snapshot()
        verified = R.verify_snapshot(snapshot)
        evidence = json.loads(
            snapshot.raw(
                f"{R.PERMIT.EVIDENCE_DIRECTORY_PATH}/evidence.json"
            )
        )
        self.assertEqual(
            verified["canonicalProofBundleSha256"],
            evidence["proof"]["canonicalProofBundleSha256"],
        )

    def test_17_execute_sets_and_restores_umask_without_real_output(self):
        def observed_umask():
            value = os.umask(0)
            os.umask(value)
            return value

        before = observed_umask()
        during = []

        def failed_preflight():
            during.append(observed_umask())
            raise R.ReadbackError("E_SYNTHETIC", "preflight")

        with mock.patch.object(R, "preflight", side_effect=failed_preflight):
            with self.assertRaises(R.ReadbackError):
                R.execute()
        self.assertEqual(during, [0o077])
        self.assertEqual(observed_umask(), before)
        for path in (
            R.PERMIT.READBACK_CLAIM_PATH,
            R.PERMIT.READBACK_RECEIPT_PATH,
            R.PERMIT.READBACK_MANIFEST_PATH,
        ):
            self.assertFalse((R.ROOT / path).exists())

    def test_18_no_execution_runner_import_or_invocation(self):
        source = Path(R.__file__).read_text()
        self.assertNotIn("resolve_p2p", source)
        self.assertNotIn("identity_v1_once", source)
        self.assertNotIn("PERMIT.evaluate(", source)
        self.assertIn("PERMIT.expected_payload_from_package", source)

    def test_19_terminal_exclusivity_and_readback_namespace(self):
        execution_failure = (
            R.ROOT
            / R.PERMIT.BASE
            / "bounded-dependency-public-checksum-identity-resolution-failure-v1.json"
        )
        self.assertFalse(execution_failure.exists())
        self.assertTrue((R.ROOT / R.PERMIT.EXECUTION_RECEIPT["path"]).exists())
        self.assertTrue((R.ROOT / R.PERMIT.EXECUTION_MANIFEST["path"]).exists())
        self.assertFalse((R.ROOT / R.PERMIT.READBACK_CLAIM_PATH).exists())
        self.assertFalse((R.ROOT / R.PERMIT.READBACK_RECEIPT_PATH).exists())
        self.assertFalse((R.ROOT / R.PERMIT.READBACK_MANIFEST_PATH).exists())

    def test_20_synthetic_success_publishes_receipt_then_manifest_last(self):
        binding = {
            "permit": {"rawSha256": "a" * 64},
            "checker": {"rawSha256": "b" * 64},
            "recorder": {"rawSha256": "c" * 64},
        }
        preflight = {
            "authorityBinding": binding,
        }
        claim = {
            "path": R.PERMIT.READBACK_CLAIM_PATH,
            "bytes": 1,
            "rawSha256": "d" * 64,
            "mode": "0600",
        }
        verified = {
            "executionAttemptId": R.PERMIT.ATTEMPT_ID,
            "resolvedModuleZipH1": R.PERMIT.TARGET_ZIP_H1,
        }

        class Snapshot:
            def final_barrier(self):
                pass

            def close(self):
                pass

        published = []
        events = []

        def publish(root, path, payload):
            events.append(f"publish:{path}")
            published.append((path, payload))
            return {
                "path": path,
                "bytes": len(R.canonical_bytes(payload)),
                "rawSha256": R.sha256(R.canonical_bytes(payload)),
                "mode": "0600",
            }

        def create_claim(*args):
            events.append("claim_fsynced")
            return claim

        def open_snapshot():
            self.assertEqual(events, ["claim_fsynced"])
            events.append("frozen_snapshot_opened")
            return Snapshot()

        with mock.patch.object(R, "preflight", return_value=preflight), \
            mock.patch.object(
                R,
                "create_readback_claim",
                side_effect=create_claim,
            ), \
            mock.patch.object(R, "FrozenSnapshot", side_effect=open_snapshot), \
            mock.patch.object(R, "verify_snapshot", return_value=verified), \
            mock.patch.object(R, "atomic_publish", side_effect=publish), \
            mock.patch.object(R.secrets, "token_hex", return_value="e" * 32):
            result = R.execute()
        self.assertEqual(
            [path for path, _ in published],
            [
                R.PERMIT.READBACK_RECEIPT_PATH,
                R.PERMIT.READBACK_MANIFEST_PATH,
            ],
        )
        self.assertEqual(
            events[:2],
            ["claim_fsynced", "frozen_snapshot_opened"],
        )
        receipt = published[0][1]
        manifest = published[1][1]
        self.assertEqual(receipt["authorityBinding"], binding)
        self.assertEqual(manifest["authorityBinding"], binding)
        self.assertEqual(receipt["readbackClaim"], claim)
        self.assertEqual(receipt["verified"], verified)
        self.assertTrue(manifest["manifestWrittenLast"])
        self.assertEqual(
            result["status"],
            "identity_resolution_readback_publication_complete",
        )

    def test_21_synthetic_verification_failure_publishes_nothing(self):
        class Snapshot:
            def final_barrier(self):
                pass

            def close(self):
                pass

        publish = mock.Mock()
        with mock.patch.object(
            R,
            "preflight",
            return_value={"authorityBinding": {}},
        ), mock.patch.object(
            R,
            "create_readback_claim",
            return_value={"path": R.PERMIT.READBACK_CLAIM_PATH},
        ), mock.patch.object(
            R,
            "FrozenSnapshot",
            return_value=Snapshot(),
        ), mock.patch.object(
            R,
            "verify_snapshot",
            side_effect=R.ReadbackError("E_SYNTHETIC", "snapshot"),
        ), mock.patch.object(
            R,
            "atomic_publish",
            publish,
        ):
            with self.assertRaises(R.ReadbackError):
                R.execute()
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
