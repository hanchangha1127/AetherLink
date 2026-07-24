#!/usr/bin/env python3
"""Tests for the one-use offline Wave3 acquisition readback recorder."""

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

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest import mock
import warnings
import zipfile


PATH = Path(__file__).with_name(
    "record_p2p_nat_g2_pion_rung3_dependency_wave3_readback_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location("wave3_readback_recorder_tests", PATH)
R = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(R)


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
    "complete_snapshot_claim_and_receipt_immediately_before_manifest",
]


def fake_preflight(authority=None):
    return {
        "authorityBinding": {} if authority is None else authority,
        "permit": {
            "verificationContract": {
                "retainedFdPublicationBarriers": list(BARRIER_NAMES),
            }
        },
    }


class FakeNamespace:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.root_fd = -1
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


class Wave3ReadbackRecorderTests(unittest.TestCase):
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

    def test_03_zip_structure_path_mode_and_header_mutations_fail(self):
        module, version = "example.test/a", "v1.0.0"
        for files in (
            {"../evil": b"x"},
            {"a\\b": b"x"},
            {"a:b": b"x"},
            {"a": b"x", "a/b": b"y"},
            {"Case": b"x", "case": b"y"},
        ):
            with self.subTest(files=files), self.assertRaises(R.ReadbackError):
                R.validate_zip(make_zip(module, version, files), module, version, None)
        symlink = io.BytesIO()
        with zipfile.ZipFile(symlink, "w") as archive:
            info = zipfile.ZipInfo(f"{module}@{version}/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")
        with self.assertRaises(R.ReadbackError):
            R.validate_zip(symlink.getvalue(), module, version, None)
        raw = bytearray(make_zip(module, version, {"a.txt": b"alpha"}))
        raw[10:12] = (int.from_bytes(raw[10:12], "little") ^ 1).to_bytes(
            2, "little"
        )
        with self.assertRaises(R.ReadbackError):
            R.validate_zip(bytes(raw), module, version, None)

    def test_04_zip64_marker_inside_payload_is_not_false_positive(self):
        module, version = "example.test/a", "v1.0.0"
        payload = b"PK\x06\x06" + b"PK\x06\x07"
        raw = make_zip(
            module,
            version,
            {"signature.bin": payload},
            compression=zipfile.ZIP_STORED,
        )
        self.assertEqual(
            R.validate_zip(raw, module, version, None)["entryCount"],
            1,
        )

    def test_05_live_retained_snapshot_verifies_twice_read_only(self):
        claim = R.ROOT / R.PERMIT.READBACK_CLAIM_PATH
        receipt = R.ROOT / R.PERMIT.READBACK_RECEIPT_PATH
        manifest = R.ROOT / R.PERMIT.READBACK_MANIFEST_PATH
        self.assertFalse(os.path.lexists(claim))
        snapshot = R.FrozenSnapshot()
        try:
            first = R.verify_snapshot(snapshot)
            snapshot.refresh()
            second = R.verify_snapshot(snapshot)
            self.assertEqual(first, second)
            self.assertEqual(first["acceptedResourceCount"], 32)
            self.assertEqual(first["aggregateAcceptedBytes"], 32_425_130)
            self.assertEqual(len(first["resources"]), 32)
        finally:
            snapshot.close()
        self.assertFalse(os.path.lexists(claim))
        self.assertFalse(os.path.lexists(receipt))
        self.assertFalse(os.path.lexists(manifest))

    def test_06_preflight_opens_no_frozen_acquisition_input(self):
        result = R.preflight()
        self.assertFalse(result["frozenAcquisitionInputOpened"])
        self.assertEqual(result["networkRequestAttemptCount"], 0)

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
                    "E_CURRENT_PATH_IDENTITY",
                )
            finally:
                if claim_fd >= 0:
                    os.close(claim_fd)
                namespace.close()

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

    def test_09_current_path_and_project_root_swaps_fail_barriers(self):
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
            root_fd, _ = R._open_root(root.absolute(), "test")
            held = R.HeldFile(root_fd, expected)
            try:
                (root / "a").rename(root / "old-a")
                replacement = root / "a" / "b"
                replacement.mkdir(parents=True, mode=0o700)
                replacement_target = replacement / "value"
                replacement_target.write_bytes(b"same")
                replacement_target.chmod(0o600)
                with self.assertRaises(R.ReadbackError) as caught:
                    held.barrier()
                self.assertEqual(
                    caught.exception.code,
                    "E_CURRENT_PATH_IDENTITY",
                )
            finally:
                held.close()
                os.close(root_fd)

            directory_info = (root / "a" / "b").stat()
            directory_expected = {
                "path": "a/b",
                "mode": "0700",
                "ownerUid": directory_info.st_uid,
                "linkCount": directory_info.st_nlink,
            }
            root_fd, _ = R._open_root(root.absolute(), "test")
            held_directory = R.HeldDirectory(
                root_fd,
                directory_expected,
                {"value"},
            )
            try:
                (root / "a").rename(root / "old-a-2")
                replacement = root / "a" / "b"
                replacement.mkdir(parents=True, mode=0o700)
                replacement_target = replacement / "value"
                replacement_target.write_bytes(b"same")
                replacement_target.chmod(0o600)
                with self.assertRaises(R.ReadbackError):
                    held_directory.barrier()
            finally:
                held_directory.close()
                os.close(root_fd)

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

        def claim(_root, _attempt, _authority, _root_fd):
            events.append("claim")
            return {"path": "claim", "rawSha256": "b" * 64}, -1

        def verify(snapshot):
            snapshot.events.append("verify")
            return {"acceptedResourceCount": 32}

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
        receipt_payload = published_payloads[R.PERMIT.READBACK_RECEIPT_PATH]
        manifest_payload = published_payloads[R.PERMIT.READBACK_MANIFEST_PATH]
        self.assertEqual(
            receipt_payload[
                "completedRetainedFdPublicationBarrierCountAtReceipt"
            ],
            1,
        )
        self.assertEqual(
            receipt_payload[
                "remainingRetainedFdPublicationBarrierCountBeforeManifest"
            ],
            2,
        )
        self.assertTrue(
            receipt_payload[
                "allRequiredPublicationBarriersRequiredBeforeManifest"
            ]
        )
        self.assertFalse(
            receipt_payload[
                "allRequiredPublicationBarriersCompleteAtReceipt"
            ]
        )
        self.assertEqual(
            manifest_payload[
                "completedRetainedFdPublicationBarrierCountBeforeManifest"
            ],
            3,
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
            return_value={"acceptedResourceCount": 32},
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
            return_value={"acceptedResourceCount": 32},
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
                return_value={"acceptedResourceCount": 32},
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
                        creation_fd = os.open(
                            target,
                            os.O_RDWR | os.O_CLOEXEC | R.O_NOFOLLOW,
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
                stale = output_parent / (
                    R.PERMIT.READBACK_TEMP_PREFIXES[0] + "stale"
                )
                stale.symlink_to(root / "missing")
                with self.assertRaises(R.ReadbackError) as caught:
                    namespace.preclaim_barrier()
                self.assertEqual(
                    caught.exception.code,
                    "E_STALE_TEMP_NAMESPACE",
                )
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
