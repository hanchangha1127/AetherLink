#!/usr/bin/env python3
"""Tests for the one-use offline Wave9 acquisition readback recorder."""

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
import errno
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest import mock
import unicodedata
import warnings
import zipfile


PATH = Path(__file__).with_name(
    "record_p2p_nat_g2_pion_rung3_dependency_wave9_readback_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location("wave9_readback_recorder_tests", PATH)
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


class Wave9ReadbackRecorderTests(unittest.TestCase):
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
            self.assertEqual(first["acceptedResourceCount"], 20)
            self.assertEqual(first["authorityFileCount"], 14)
            self.assertEqual(first["selectedTupleCount"], 0)
            self.assertEqual(first["aggregateAcceptedBytes"], 16_285_940)
            self.assertEqual(first["aggregateZipEntryCount"], 5_349)
            self.assertEqual(
                first["aggregateZipUncompressedBytes"],
                54_936_288,
            )
            self.assertFalse(first["externalAuthenticationRequired"])
            self.assertFalse(first["userActionRequired"])
            self.assertEqual(len(first["resources"]), 20)
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
            owned: list[int] = []
            root_fd, _ = R._open_root(root.absolute(), "test", owned)
            held = R.HeldFile(root_fd, expected, owned)
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
                replacement = root / "a" / "b"
                replacement.mkdir(parents=True, mode=0o700)
                replacement_target = replacement / "value"
                replacement_target.write_bytes(b"same")
                replacement_target.chmod(0o600)
                with self.assertRaises(R.ReadbackError):
                    held_directory.barrier()
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
            return {"acceptedResourceCount": 20}

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
                "wave9_acquisition_retained_snapshot_"
                "independently_read_back"
            ),
        )
        self.assertEqual(
            manifest_payload["status"],
            (
                "wave9_acquisition_retained_snapshot_"
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
            return_value={"acceptedResourceCount": 20},
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
            return_value={"acceptedResourceCount": 20},
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
                return_value={"acceptedResourceCount": 20},
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

    def test_16_each_actual_barrier_claim_replacement_is_uncertain(self):
        for fail_at in (1, 2, 3):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                claim_path = root / R.PERMIT.READBACK_CLAIM_PATH
                claim_path.parent.mkdir(parents=True, mode=0o700)
                (root / R.PERMIT.BASE).mkdir(parents=True, mode=0o700)
                events: list[str] = []

                class ReplacingNamespace(R.ReadbackNamespace):
                    def __init__(self, namespace_root):
                        super().__init__(namespace_root)
                        self.barrier_count = 0

                    def publication_barrier(self, *, receipt_required):
                        self.barrier_count += 1
                        if self.barrier_count == fail_at:
                            raw = claim_path.read_bytes()
                            claim_path.rename(
                                claim_path.with_name(
                                    claim_path.name + ".replaced"
                                )
                            )
                            claim_path.write_bytes(raw)
                            claim_path.chmod(0o600)
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
                    return_value={"acceptedResourceCount": 20},
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
                nfd = (
                    R.PERMIT.READBACK_TEMP_PREFIXES[0].upper()
                    + unicodedata.normalize("NFD", "é")
                )
                nfc = (
                    R.PERMIT.READBACK_TEMP_PREFIXES[0].upper()
                    + unicodedata.normalize("NFC", "é")
                )
                self.assertEqual(R.portable_name(nfd), R.portable_name(nfc))
                self.assertTrue(
                    R.has_portable_prefix(
                        [R.PERMIT.STAGING_PREFIX.upper() + nfd[-2:]],
                        [R.PERMIT.STAGING_PREFIX],
                    )
                )
                for variant in (
                    R.PERMIT.READBACK_TEMP_PREFIXES[0] + "stale",
                    nfd,
                    nfc,
                ):
                    stale = output_parent / variant
                    stale.symlink_to(root / "missing")
                    with self.assertRaises(R.ReadbackError) as caught:
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

    def test_21_wave9_uncompressed_limits_are_per_zip_and_across_all(self):
        self.assertEqual(
            R.MAX_ZIP_UNCOMPRESSED_BYTES_PER_ZIP,
            128 * 1024 * 1024,
        )
        self.assertEqual(
            R.MAX_ZIP_UNCOMPRESSED_BYTES_ACROSS_ALL,
            1024 * 1024 * 1024,
        )
        self.assertLess(
            54_936_288,
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
        self.assertEqual(R.MAX_AGGREGATE_MOD_BYTES, 8 * 1024 * 1024)
        self.assertEqual(R.MAX_AGGREGATE_ZIP_BYTES, 128 * 1024 * 1024)
        self.assertEqual(R.MAX_ZIP_FILES_ACROSS_ALL, 300_000)

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

                def fail_observation_cleanup(owner):
                    nonlocal close_calls
                    close_calls += 1
                    real_close_owned_fds(owner)
                    if close_calls == 3:
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
                self.assertEqual(close_calls, 3)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
