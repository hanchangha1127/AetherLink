#!/usr/bin/env python3
"""Mutation tests for non-authorizing G0 repository/remote source observations."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import pickle
from pathlib import Path
import socket
import unittest
from unittest import mock

from script import check_v1_g0_independent_validation_context as independent
from script import check_v1_g0_decision as decision
from script import check_v1_g0_receipt_bundle as receipt
from script import check_v1_g0_repository_remote_sources as sources


ROOT = Path(__file__).resolve().parents[1]
FIXED_REPOSITORY_TIME = "2026-07-21T02:00:00Z"


class V1G0RepositoryRemoteSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with mock.patch.object(sources, "_utc_now", return_value=FIXED_REPOSITORY_TIME):
            cls.repository = sources._verify_local_repository_source(ROOT)
        payload = sources._repository_payload(cls.repository)
        assert isinstance(payload, tuple) and len(payload) == 6
        cls.repository_payload = payload
        cls.checkpoint = payload[4][-1]

    @staticmethod
    def parse(raw: bytes) -> dict[str, object]:
        value = json.loads(raw.decode("utf-8"))
        assert isinstance(value, dict)
        return value

    @staticmethod
    def later_times(start: str, seconds: int = 1) -> tuple[str, str]:
        parsed = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        first = parsed + timedelta(seconds=seconds)
        second = first + timedelta(seconds=seconds)
        return (
            first.strftime("%Y-%m-%dT%H:%M:%SZ"),
            second.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def verify_remote(
        self,
        response: tuple[int, tuple[tuple[str, str], ...], object] | None = None,
        *,
        times: tuple[str, str] | None = None,
        duration_millis: object = 1_000,
    ) -> sources._RemoteCheckpointSourceObservation:
        if response is None:
            response = (
                200,
                (
                    ("content-length", str(len(self.checkpoint))),
                    ("content-encoding", "identity"),
                ),
                self.checkpoint,
            )
        if times is None:
            times = self.later_times(FIXED_REPOSITORY_TIME)
        return sources._verify_supplied_remote_checkpoint_source(
            self.repository,
            status=response[0],
            headers=response[1],
            body=response[2],
            started_at=times[0],
            completed_at=times[1],
            duration_millis=duration_millis,
        )

    def test_exact_local_source_is_opaque_and_mechanical_only(self) -> None:
        self.assertTrue(sources._factory_owned_repository_source(self.repository))
        binding, observed_at, observation_ref, raw, lineage, checkpoint_blob = (
            self.repository_payload
        )
        document = self.parse(raw)
        self.assertEqual(binding, sources._target_binding())
        self.assertEqual(observed_at, FIXED_REPOSITORY_TIME)
        self.assertEqual(document["observationRef"], observation_ref)
        self.assertEqual(
            document["status"],
            "mechanically_verified_candidate_non_authorizing",
        )
        self.assertEqual(document["scopeProfileBinding"]["entryCount"], 18)
        self.assertEqual(len(document["lineageEntries"]), 6)
        self.assertEqual(
            tuple(hashlib.sha256(raw).hexdigest() for raw in lineage),
            receipt.LINEAGE_RAW_SHA256,
        )
        self.assertEqual(
            sources._git_object_id("blob", lineage[-1]),
            checkpoint_blob,
        )
        self.assertNotIn("accepted", document)
        self.assertNotIn("verified", document)
        self.assertNotIn("authority", document)

    def test_source_identities_cannot_be_constructed_copied_or_serialized(self) -> None:
        with self.assertRaises(TypeError):
            sources._RepositorySourceObservation()
        with self.assertRaises(TypeError):
            sources._RemoteCheckpointSourceObservation()
        with self.assertRaises(TypeError):
            copy.copy(self.repository)
        with self.assertRaises(TypeError):
            copy.deepcopy(self.repository)
        with self.assertRaises(TypeError):
            pickle.dumps(self.repository)
        forged = object.__new__(sources._RepositorySourceObservation)
        self.assertFalse(sources._factory_owned_repository_source(forged))
        generic = object.__new__(independent._IndependentAdapterResult)
        self.assertFalse(sources._factory_owned_repository_source(generic))

    def test_module_exposes_no_context_or_authority_consumer_and_partial_inputs_fail(self) -> None:
        self.assertEqual(sources.__all__, ())
        for name in (
            "accept",
            "activate",
            "authorize",
            "build_context",
            "close_g0",
            "derive_g1a",
            "compile_repository_remote_candidate_results",
        ):
            self.assertFalse(hasattr(sources, name), name)
        remote = self.verify_remote()
        self.assertTrue(sources._factory_owned_remote_source(remote))
        with self.assertRaises(independent._IndependentValidationContextError):
            independent._build_candidate_independent_validation_context(
                lineage_blobs=self.repository_payload[4],
                adapter_results=(self.repository, remote),
            )

    def test_exact_git_parsers_reject_status_mode_path_and_object_drift(self) -> None:
        raw_diff = sources._run_git(
            ROOT,
            (
                "diff-tree",
                "--no-commit-id",
                "--raw",
                "-r",
                "--abbrev=40",
                "--no-renames",
                "-z",
                "929fda5f2c01cd7d53325a036071b6a684ecaa1f",
                receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
            ),
        )
        self.assertEqual(len(sources._parse_diff_entries(raw_diff)), 18)
        with self.assertRaises(sources._SourceObservationError):
            sources._parse_diff_entries(raw_diff.replace(b" M\0", b" R\0", 1))

        path = receipt.V3_CHECKPOINT_PATH
        tree_raw = sources._run_git(
            ROOT,
            (
                "ls-tree",
                "--full-tree",
                "--full-name",
                "-z",
                receipt.EXPECTED_RECORDED_COMMIT_OBJECT_ID,
                "--",
                path,
            ),
        )
        self.assertEqual(
            sources._parse_tree_entry(tree_raw, path),
            ("100644", "blob", self.repository_payload[5]),
        )
        with self.assertRaises(sources._SourceObservationError):
            sources._parse_tree_entry(tree_raw.replace(b"100644", b"100755", 1), path)
        with self.assertRaises(sources._SourceObservationError):
            sources._parse_tree_entry(tree_raw, "docs/v1/g0/other.json")
        self.assertEqual(
            sources._git_object_id("blob", self.checkpoint),
            self.repository_payload[5],
        )
        self.assertNotIn("HOME", sources._git_environment())
        self.assertNotIn("HTTPS_PROXY", sources._git_environment())
        self.assertEqual(sources._git_environment()["GIT_NO_LAZY_FETCH"], "1")
        with self.assertRaises(sources._SourceObservationError):
            sources._run_git(
                ROOT,
                ("rev-parse", "--show-object-format"),
                maximum_stdout_bytes=1,
            )

    def test_local_verifier_rejects_blob_mode_replace_and_promisor_drift(self) -> None:
        real_run_git = sources._run_git
        checkpoint_blob = self.repository_payload[5]

        def corrupt_blob(root: Path, arguments: tuple[str, ...], **kwargs: object) -> bytes:
            raw = real_run_git(root, arguments, **kwargs)
            if arguments == ("cat-file", "blob", checkpoint_blob):
                return bytes((raw[0] ^ 1,)) + raw[1:]
            return raw

        def change_mode(root: Path, arguments: tuple[str, ...], **kwargs: object) -> bytes:
            raw = real_run_git(root, arguments, **kwargs)
            if arguments[:1] == ("ls-tree",) and receipt.V3_CHECKPOINT_PATH in arguments:
                return raw.replace(b"100644", b"100755", 1)
            return raw

        def add_replace(root: Path, arguments: tuple[str, ...], **kwargs: object) -> bytes:
            if arguments[:1] == ("for-each-ref",):
                return b"refs/replace/0000000000000000000000000000000000000000\n"
            return real_run_git(root, arguments, **kwargs)

        def add_promisor(root: Path, arguments: tuple[str, ...], **kwargs: object) -> bytes:
            if arguments[:1] == ("config",):
                return b"remote.origin.promisor true\n"
            return real_run_git(root, arguments, **kwargs)

        late_replace_calls = 0

        def add_late_replace(root: Path, arguments: tuple[str, ...], **kwargs: object) -> bytes:
            nonlocal late_replace_calls
            if arguments[:1] == ("for-each-ref",):
                late_replace_calls += 1
                if late_replace_calls == 2:
                    return b"refs/replace/0000000000000000000000000000000000000000\n"
            return real_run_git(root, arguments, **kwargs)

        for label, side_effect in (
            ("blob", corrupt_blob),
            ("mode", change_mode),
            ("replace", add_replace),
            ("promisor", add_promisor),
            ("late-replace", add_late_replace),
        ):
            with self.subTest(label=label):
                with (
                    mock.patch.object(sources, "_run_git", side_effect=side_effect),
                    mock.patch.object(sources, "_utc_now", return_value=FIXED_REPOSITORY_TIME),
                    self.assertRaises(sources._SourceObservationError),
                ):
                    sources._verify_local_repository_source(ROOT)

        safe_policy = sources._repository_policy_state(ROOT, ROOT / ".git", ROOT / ".git" / "objects")
        late_policy_states = (
            (("Git object alternates",), (), b"", b""),
            ((), ("pack-late.promisor",), b"", b""),
            ((), (), b"", b"remote.origin.promisor true\n"),
        )
        for index, late_policy in enumerate(late_policy_states):
            with self.subTest(late_policy=index):
                with (
                    mock.patch.object(
                        sources,
                        "_repository_policy_state",
                        side_effect=(safe_policy, late_policy),
                    ),
                    mock.patch.object(sources, "_utc_now", return_value=FIXED_REPOSITORY_TIME),
                    self.assertRaises(sources._SourceObservationError),
                ):
                    sources._verify_local_repository_source(ROOT)
        with (
            mock.patch.object(sources, "EXPECTED_REVIEWED_SCOPE_ENTRIES_SHA256", "0" * 64),
            mock.patch.object(sources, "_utc_now", return_value=FIXED_REPOSITORY_TIME),
            self.assertRaises(sources._SourceObservationError),
        ):
            sources._verify_local_repository_source(ROOT)

    def test_exact_remote_source_is_bound_but_still_non_authorizing(self) -> None:
        remote = self.verify_remote()
        self.assertTrue(sources._factory_owned_remote_source(remote))
        payload = sources._remote_payload(remote)
        assert isinstance(payload, tuple) and len(payload) == 8
        document = self.parse(payload[6])
        self.assertIs(payload[0], self.repository)
        self.assertEqual(payload[1], sources._target_binding())
        self.assertEqual(payload[7], self.checkpoint)
        self.assertEqual(
            document["status"],
            "supplied_bytes_matched_candidate_non_authorizing",
        )
        self.assertFalse(document["provenanceBoundary"]["networkPerformedByThisModule"])
        self.assertFalse(document["provenanceBoundary"]["collectorAuthenticated"])
        self.assertFalse(document["provenanceBoundary"]["remoteRefReachabilityVerified"])
        self.assertEqual(document["expectedRequest"]["url"], sources.REMOTE_URL)
        self.assertEqual(document["suppliedResponse"]["bodyByteLength"], len(self.checkpoint))
        with self.assertRaises(TypeError):
            copy.copy(remote)
        with self.assertRaises(TypeError):
            pickle.dumps(remote)

    def test_remote_source_rejects_transport_body_and_clock_drift(self) -> None:
        class TupleSubclass(tuple):
            pass

        class StringSubclass(str):
            pass

        valid_headers = (("content-length", str(len(self.checkpoint))),)
        cases: tuple[
            tuple[str, tuple[int, tuple[tuple[str, str], ...], object], object],
            ...,
        ] = (
            ("redirect", (302, (), b""), 1),
            ("encoding", (200, (("content-encoding", "gzip"),), self.checkpoint), 1),
            ("length", (200, (("content-length", "1"),), self.checkpoint), 1),
            (
                "duplicate-length",
                (
                    200,
                    (("content-length", str(len(self.checkpoint))), ("content-length", str(len(self.checkpoint)))),
                    self.checkpoint,
                ),
                1,
            ),
            ("header-case", (200, (("Content-Length", str(len(self.checkpoint))),), self.checkpoint), 1),
            ("header-unknown", (200, (("set-cookie", "secret"),), self.checkpoint), 1),
            ("header-crlf", (200, (("content-encoding", "identity\r\nforged"),), self.checkpoint), 1),
            ("header-surrogate", (200, (("content-encoding", "identity\ud800"),), self.checkpoint), 1),
            ("tuple-subclass", (200, TupleSubclass(valid_headers), self.checkpoint), 1),
            (
                "entry-subclass",
                (200, (TupleSubclass(("content-length", str(len(self.checkpoint)))),), self.checkpoint),
                1,
            ),
            (
                "string-subclass",
                (200, ((StringSubclass("content-length"), str(len(self.checkpoint))),), self.checkpoint),
                1,
            ),
            ("length-digits", (200, (("content-length", "9" * 11),), self.checkpoint), 1),
            ("body", (200, valid_headers, self.checkpoint[:-1] + b" "), 1),
            (
                "oversized",
                (200, (), b"x" * (receipt.MAX_V3_CHECKPOINT_BYTES + 1)),
                1,
            ),
            ("duration", (200, valid_headers, self.checkpoint), -1),
        )
        for label, response, duration in cases:
            with self.subTest(label=label):
                with self.assertRaises(sources._SourceObservationError):
                    self.verify_remote(response, duration_millis=duration)

        start, end = self.later_times(FIXED_REPOSITORY_TIME)
        with self.assertRaises(sources._SourceObservationError):
            self.verify_remote(times=(end, start))
        forged = object.__new__(sources._RepositorySourceObservation)
        with self.assertRaises(sources._SourceObservationError):
            sources._verify_supplied_remote_checkpoint_source(
                forged,
                status=200,
                headers=valid_headers,
                body=self.checkpoint,
                started_at=start,
                completed_at=end,
                duration_millis=1,
            )

    def test_default_checker_performs_no_network_and_preserves_dormant_boundary(self) -> None:
        real_run_git = sources._run_git
        allowed_commands = {
            "rev-parse",
            "for-each-ref",
            "config",
            "cat-file",
            "diff-tree",
            "ls-tree",
        }

        def read_only_git(root: Path, arguments: tuple[str, ...], **kwargs: object) -> bytes:
            self.assertIn(arguments[0], allowed_commands)
            return real_run_git(root, arguments, **kwargs)

        with (
            mock.patch.object(socket, "socket", side_effect=AssertionError("unexpected socket")),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("unexpected socket")),
            mock.patch.object(sources, "_run_git", side_effect=read_only_git),
            mock.patch.object(sources, "_utc_now", return_value=FIXED_REPOSITORY_TIME),
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected worktree read")),
            mock.patch.object(
                decision,
                "read_g0_content_addressed_snapshot",
                side_effect=AssertionError("unexpected worktree document snapshot"),
            ),
        ):
            self.assertEqual(sources._collect_worktree_contract_failures(ROOT), ())
        self.assertIn("mechanical_candidate_only", sources.SOURCE_OBSERVATION_DORMANT_MESSAGE)
        self.assertIn("cannot activate receipts", sources.SOURCE_OBSERVATION_DORMANT_MESSAGE)


if __name__ == "__main__":
    unittest.main()
