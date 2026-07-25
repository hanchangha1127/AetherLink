#!/usr/bin/env python3
"""Adversarial offline tests for the one-use Wave6 acquisition runner."""

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
    raise RuntimeError("Wave6 runner tests require `python3 -I -B -S`")

from contextlib import nullcontext
import copy
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import signal
import stat
import tempfile
import threading
import time
import unittest
from unittest import mock
import zipfile


RUNNER_PATH = Path(__file__).with_name(
    "acquire_p2p_nat_g2_pion_rung3_dependency_wave6_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave6_source_acquirer_v1",
    RUNNER_PATH,
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def make_zip(
    module: str,
    version: str,
    files: dict[str, bytes],
) -> bytes:
    output = io.BytesIO()
    prefix = f"{module}@{version}/"
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, raw in files.items():
            info = zipfile.ZipInfo(prefix + name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return output.getvalue()


def fixture() -> tuple[list[dict[str, object]], dict[int, bytes]]:
    rows: list[dict[str, object]] = []
    bodies: dict[int, bytes] = {}
    ordinal = 0
    for tuple_order in range(1, 19):
        module = f"example.test/dependency{tuple_order}"
        version = f"v1.0.{tuple_order}"
        digest = runner.sha256(f"{module}\n{version}\n".encode())
        tuple_id = f"wave6-{tuple_order:03d}-{digest[:12]}"
        selected = False
        mod = f"module {module}\n\ngo 1.22\n".encode()
        archive = make_zip(
            module,
            version,
            {
                "go.mod": mod,
                "source.go": (
                    f"package dependency{tuple_order}\n".encode()
                ),
            },
        )
        for kind, body, expected_h1, maximum in (
            (
                "mod",
                mod,
                runner.VALIDATION.go_mod_h1(mod),
                runner.CHECK.MAX_MOD_BYTES,
            ),
            (
                "zip",
                archive,
                runner.VALIDATION.module_zip_h1(
                    archive,
                    module,
                    version,
                ),
                runner.CHECK.MAX_ZIP_BYTES,
            ),
        ):
            ordinal += 1
            path = f"/{module}/@v/{version}.{kind}"
            rows.append(
                {
                    "requestOrdinal": ordinal,
                    "tupleOrder": tuple_order,
                    "tupleId": tuple_id,
                    "tupleDigestSha256": digest,
                    "selectedByGraphAlgorithm": selected,
                    "module": module,
                    "version": version,
                    "kind": kind,
                    "method": "GET",
                    "host": runner.CHECK.PROXY_HOST,
                    "port": 443,
                    "path": path,
                    "url": f"https://{runner.CHECK.PROXY_HOST}{path}",
                    "expectedH1": expected_h1,
                    "maximumResponseBodyBytes": maximum,
                    "acceptedFileName": (
                        f"{tuple_order:03d}-{digest[:20]}.{kind}"
                    ),
                }
            )
            bodies[ordinal] = body
    return rows, bodies


def values(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "decision": {
            "contentBinding": {"sha256": "d" * 64},
        },
        "permit": {
            "contentBinding": {"sha256": "p" * 64},
            "requestContract": {
                "requestCount": 36,
                "resources": rows,
                "resourcesCanonicalSha256": runner.sha256(
                    runner.canonical_bytes(rows)
                ),
            },
            "authority": {
                "externalAuthenticationRequired": False,
                "repositoryOwnerIdentityProofRequired": False,
                "accountRequired": False,
                "ownerRequired": False,
                "sshRequired": False,
                "gpgRequired": False,
                "authenticationRequired": False,
                "passwordRequired": False,
                "privateKeyRequired": False,
                "signatureRequired": False,
                "tokenRequired": False,
                "cookieRequired": False,
                "clientCertificateRequired": False,
                "userActionRequired": False,
            },
            "toolBindings": [
                {
                    "path": runner.CHECK.RUNNER_PATH,
                    "rawSha256": "r" * 64,
                }
            ],
        },
    }


def prepare_root(root: Path) -> None:
    (root / runner.CHECK.DEPENDENCY_ROOT).mkdir(
        parents=True,
        mode=0o700,
    )
    (root / runner.CHECK.BASE).mkdir(
        parents=True,
        mode=0o700,
    )


def terminal(root: Path, path: str) -> Path:
    return root / path


class FakeProcessState:
    def __init__(
        self,
        *,
        fail_step: str | None = None,
        fail_steps: set[str] | None = None,
        pending_on_cancel: bool = False,
    ) -> None:
        self.fail_steps = set(fail_steps or ())
        if fail_step is not None:
            self.fail_steps.add(fail_step)
        self.pending_on_cancel = pending_on_cancel
        self.calls: list[str] = []
        self.mask: set[signal.Signals] = set()
        self.handler: object = object()
        self.pending: set[signal.Signals] = set()
        self.timer = (5.0, 0.25)
        self.umask_value = 0o022
        self.signal_calls = 0
        self.timer_calls = 0
        self.cancel_calls = 0
        self.umask_calls = 0
        self.block_calls = 0
        self.setmask_calls = 0
        self.clock = 100.0

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if name in self.fail_steps:
            raise OSError(f"synthetic {name} failure")

    def pthread_sigmask(self, how, values):
        previous = set(self.mask)
        values = set(values)
        if how == signal.SIG_BLOCK:
            if values:
                if values == {signal.SIGALRM}:
                    label = "contain_signal_mask"
                else:
                    self.block_calls += 1
                    label = {
                        1: "setup_mask",
                        2: "mask_for_restore",
                    }.get(
                        self.block_calls,
                        "mask_for_restore_retry",
                    )
                self._record(label)
                self.mask.update(values)
            else:
                self.calls.append("query_mask")
        elif how == signal.SIG_SETMASK:
            self.setmask_calls += 1
            label = (
                "restore_signal_mask"
                if self.block_calls >= 2
                else "setup_unmask"
            )
            self._record(label)
            self.mask = values
        else:
            raise AssertionError(how)
        return previous

    def getsignal(self, _signum):
        self.calls.append("get_handler")
        return self.handler

    def getitimer(self, _which):
        self.calls.append("get_timer")
        return self.timer

    def signal(self, _signum, handler):
        self.signal_calls += 1
        label = (
            "install_handler"
            if self.signal_calls == 1
            else "restore_handler"
        )
        self._record(label)
        previous = self.handler
        self.handler = handler
        return previous

    def setitimer(self, _which, delay, interval=0):
        self.timer_calls += 1
        if self.timer_calls == 1:
            label = "install_timer"
        elif float(delay) == 0:
            self.cancel_calls += 1
            label = (
                "cancel_installed_timer"
                if self.cancel_calls == 1
                else "cancel_installed_timer_retry"
            )
        else:
            label = "restore_previous_timer"
        self._record(label)
        previous = self.timer
        self.timer = (float(delay), float(interval))
        if self.pending_on_cancel and label.startswith(
            "cancel_installed_timer"
        ):
            self.pending.add(signal.SIGALRM)
        return previous

    def sigpending(self):
        self._record("inspect_pending_alarm")
        return set(self.pending)

    def sigwait(self, values):
        self._record("drain_pending_alarm")
        values = set(values)
        if signal.SIGALRM not in values or signal.SIGALRM not in self.pending:
            raise AssertionError("no matching pending alarm")
        self.pending.remove(signal.SIGALRM)
        return signal.SIGALRM

    def umask(self, value):
        self.umask_calls += 1
        label = (
            "install_umask"
            if self.umask_calls == 1
            else "restore_umask"
        )
        self._record(label)
        previous = self.umask_value
        self.umask_value = value
        return previous

    def monotonic(self):
        self.clock += 0.01
        return self.clock

    def operations(self) -> runner.ProcessOps:
        return runner.ProcessOps(
            getsignal=self.getsignal,
            getitimer=self.getitimer,
            set_signal=self.signal,
            setitimer=self.setitimer,
            sigpending=self.sigpending,
            sigwait=self.sigwait,
            pthread_sigmask=self.pthread_sigmask,
            umask=self.umask,
            monotonic=self.monotonic,
        )


class Wave6RunnerTests(unittest.TestCase):
    def run_attempt(
        self,
        root: Path,
        fetch,
        rows: list[dict[str, object]],
        *,
        hook=None,
        ops=None,
        whole_timeout: float = 10,
        checkpoint=None,
    ):
        prepare_root(root)
        arguments = {"hook": hook}
        if ops is not None:
            arguments["ops"] = ops
        with runner.ExecutionNamespace(root, **arguments) as namespace:
            return runner._attempt(
                fetch,
                values(rows),
                namespace,
                whole_timeout=whole_timeout,
                checkpoint=checkpoint,
            )

    def test_success_claims_before_36_fetches_and_manifest_is_last(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls: list[int] = []
            events: list[str] = []

            def hook(event: str, _namespace) -> None:
                events.append(event)

            def fetch(resource, _deadline):
                self.assertTrue(
                    terminal(root, runner.CHECK.CLAIM_PATH).exists()
                )
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            receipt = self.run_attempt(
                root,
                fetch,
                rows,
                hook=hook,
            )
            self.assertEqual(calls, list(range(1, 37)))
            self.assertEqual(
                receipt["status"],
                "consumed_success_pending_independent_readback",
            )
            self.assertEqual(
                (
                    receipt["dispatchBoundaryCount"],
                    receipt["responseCommittedCount"],
                    receipt["validationCommittedCount"],
                    receipt["persistenceCommittedCount"],
                ),
                (36, 36, 36, 36),
            )
            self.assertEqual(
                receipt["responseCommittedBytes"],
                sum(len(raw) for raw in bodies.values()),
            )
            self.assertEqual(
                receipt["operationCountSemantics"],
                "exact_terminal_success",
            )
            self.assertIsNone(receipt["currentResourceOrdinal"])
            self.assertIsNone(receipt["currentOperationPhase"])
            self.assertIs(
                receipt["additionalCompletionUncertain"],
                False,
            )
            self.assertEqual(events[-3:], [
                "after_publish",
                "after_receipt_persisted",
                "after_manifest_persisted",
            ])
            accepted = terminal(root, runner.CHECK.FINAL_ACCEPTED)
            self.assertEqual(len(list(accepted.iterdir())), 36)
            self.assertTrue(
                terminal(root, runner.CHECK.CLAIM_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.RECEIPT_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.MANIFEST_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )
            self.assertTrue(
                all(
                    stat.S_IMODE(path.stat().st_mode) == 0o600
                    for path in accepted.iterdir()
                )
            )

    def test_h1_mismatch_consumes_once_and_retains_staging(self) -> None:
        rows, bodies = fixture()
        rows = copy.deepcopy(rows)
        rows[3]["expectedH1"] = "h1:" + "A" * 43 + "="
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls: list[int] = []

            def fetch(resource, _deadline):
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(root, fetch, rows)
            self.assertEqual(caught.exception.code, "E_H1_MISMATCH")
            self.assertEqual(
                runner.error_document(caught.exception)["status"],
                "consumed_failure_no_retry",
            )
            self.assertEqual(calls, [1, 2, 3, 4])
            self.assertTrue(
                terminal(root, runner.CHECK.CLAIM_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )
            dependency = terminal(root, runner.CHECK.DEPENDENCY_ROOT)
            self.assertEqual(
                len(
                    [
                        path
                        for path in dependency.iterdir()
                        if path.name.startswith(runner.CHECK.STAGING_PREFIX)
                    ]
                ),
                1,
            )
            failure = json.loads(
                terminal(root, runner.CHECK.FAILURE_PATH).read_text()
            )
            self.assertFalse(
                failure["externalAuthenticationRequired"]
            )
            self.assertFalse(failure["userActionRequired"])
            self.assertFalse(failure["retryResumeOrBackfillAllowed"])
            self.assertEqual(
                (
                    failure["dispatchBoundaryCount"],
                    failure["responseCommittedCount"],
                    failure["validationCommittedCount"],
                    failure["persistenceCommittedCount"],
                ),
                (4, 4, 3, 3),
            )
            self.assertEqual(
                failure["responseCommittedBytes"],
                sum(len(bodies[index]) for index in range(1, 5)),
            )
            self.assertEqual(failure["currentResourceOrdinal"], 4)
            self.assertEqual(
                failure["currentOperationPhase"],
                "validation_may_have_completed",
            )
            self.assertIs(
                failure["additionalCompletionUncertain"],
                True,
            )

    def test_pending_alarm_records_lower_bounds_and_in_flight_phase(
        self,
    ) -> None:
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        unblocked_mask = set(previous_mask)
        unblocked_mask.discard(signal.SIGALRM)
        signal.pthread_sigmask(signal.SIG_SETMASK, unblocked_mask)

        def alarm_handler(_signum, _frame):
            raise runner.AcquisitionError(
                "E_DEADLINE",
                "synthetic_alarm",
            )

        def assert_failure(
            root: Path,
            expected_counts: tuple[int, int, int, int],
            expected_phase: str,
            expected_state: str,
            expected_bytes: int,
        ) -> None:
            failure = json.loads(
                terminal(root, runner.CHECK.FAILURE_PATH).read_text()
            )
            self.assertEqual(
                (
                    failure["dispatchBoundaryCount"],
                    failure["responseCommittedCount"],
                    failure["validationCommittedCount"],
                    failure["persistenceCommittedCount"],
                ),
                expected_counts,
            )
            self.assertEqual(
                failure["responseCommittedBytes"],
                expected_bytes,
            )
            self.assertEqual(failure["currentResourceOrdinal"], 1)
            self.assertEqual(
                failure["currentOperationPhase"],
                expected_phase,
            )
            self.assertIs(
                failure["additionalCompletionUncertain"],
                True,
            )
            self.assertEqual(
                failure["operationCountSemantics"],
                "committed_lower_bounds",
            )
            self.assertEqual(
                failure["sourceAcquisitionState"],
                expected_state,
            )
            self.assertNotIn("sourceAcquired", failure)

        signal.signal(signal.SIGALRM, alarm_handler)
        try:
            rows, bodies = fixture()
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def fetch(resource, _deadline):
                    os.kill(os.getpid(), signal.SIGALRM)
                    return bodies[resource["requestOrdinal"]]

                with self.assertRaises(runner.AcquisitionError) as caught:
                    self.run_attempt(root, fetch, rows)
                self.assertEqual(caught.exception.code, "E_DEADLINE")
                assert_failure(
                    root,
                    (1, 0, 0, 0),
                    "fetch_may_have_completed",
                    "unknown_after_dispatch",
                    0,
                )

            rows, bodies = fixture()
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def validate_mod(_raw, _module):
                    os.kill(os.getpid(), signal.SIGALRM)
                    return {"goModH1": rows[0]["expectedH1"]}

                with mock.patch.object(
                    runner.VALIDATION,
                    "validate_mod",
                    side_effect=validate_mod,
                ):
                    with self.assertRaises(
                        runner.AcquisitionError
                    ) as caught:
                        self.run_attempt(
                            root,
                            lambda resource, _deadline: bodies[
                                resource["requestOrdinal"]
                            ],
                            rows,
                        )
                self.assertEqual(caught.exception.code, "E_DEADLINE")
                assert_failure(
                    root,
                    (1, 1, 0, 0),
                    "validation_may_have_completed",
                    "partial_committed_with_additional_completion_uncertain",
                    len(bodies[1]),
                )

            rows, bodies = fixture()
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fired = False

                def hook(event, _namespace):
                    nonlocal fired
                    if event == "after_resource_persisted" and not fired:
                        fired = True
                        os.kill(os.getpid(), signal.SIGALRM)

                with self.assertRaises(runner.AcquisitionError) as caught:
                    self.run_attempt(
                        root,
                        lambda resource, _deadline: bodies[
                            resource["requestOrdinal"]
                        ],
                        rows,
                        hook=hook,
                    )
                self.assertEqual(caught.exception.code, "E_DEADLINE")
                assert_failure(
                    root,
                    (1, 1, 1, 0),
                    "persist_may_have_completed",
                    "partial_committed_with_additional_completion_uncertain",
                    len(bodies[1]),
                )
            self.assertEqual(
                signal.pthread_sigmask(signal.SIG_BLOCK, set()),
                unblocked_mask,
            )
        finally:
            signal.signal(signal.SIGALRM, previous_handler)
            signal.pthread_sigmask(
                signal.SIG_SETMASK,
                previous_mask,
            )

    def test_sigalrm_is_deliverable_during_fetch_validation_and_fsync(
        self,
    ) -> None:
        rows, bodies = fixture()
        original_mod = runner.VALIDATION.validate_mod
        original_zip = runner.VALIDATION.validate_zip
        observations: list[str] = []

        def assert_unblocked(label: str) -> None:
            current = signal.pthread_sigmask(signal.SIG_BLOCK, set())
            self.assertNotIn(signal.SIGALRM, current)
            observations.append(label)

        def fetch(resource, _deadline):
            assert_unblocked("fetch")
            if resource["requestOrdinal"] == 3:
                raise runner.AcquisitionError("E_TEST_STOP", "request_03")
            return bodies[resource["requestOrdinal"]]

        def validate_mod(*arguments):
            assert_unblocked("validate_mod")
            return original_mod(*arguments)

        def validate_zip(*arguments):
            assert_unblocked("validate_zip")
            return original_zip(*arguments)

        def checked_fsync(fd: int) -> None:
            assert_unblocked("fsync")
            os.fsync(fd)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(
                runner.VALIDATION,
                "validate_mod",
                side_effect=validate_mod,
            ), mock.patch.object(
                runner.VALIDATION,
                "validate_zip",
                side_effect=validate_zip,
            ):
                with self.assertRaises(
                    runner.AcquisitionError
                ) as caught:
                    self.run_attempt(
                        root,
                        fetch,
                        rows,
                        ops=runner.FileOps(fsync=checked_fsync),
                    )
            self.assertEqual(caught.exception.code, "E_TEST_STOP")
            failure = json.loads(
                terminal(root, runner.CHECK.FAILURE_PATH).read_text()
            )
            self.assertEqual(
                (
                    failure["dispatchBoundaryCount"],
                    failure["responseCommittedCount"],
                    failure["validationCommittedCount"],
                    failure["persistenceCommittedCount"],
                ),
                (3, 2, 2, 2),
            )
            self.assertEqual(failure["currentResourceOrdinal"], 3)
            self.assertEqual(
                failure["currentOperationPhase"],
                "fetch_may_have_completed",
            )
        self.assertIn("fetch", observations)
        self.assertIn("validate_mod", observations)
        self.assertIn("validate_zip", observations)
        self.assertIn("fsync", observations)

    def test_canonical_preflight_context_composes_without_writes(self) -> None:
        self.assertFalse(
            terminal(runner.ROOT, runner.CHECK.CLAIM_PATH).exists()
        )
        package, _ = runner.CHECK.evaluate(True)
        permit = package["permit"]
        self.assertEqual(
            permit["oneUseContract"]["existingClaimState"],
            "already_consumed",
        )
        self.assertIs(
            permit["oneUseContract"]["claimAbsentAtPermitPublication"],
            True,
        )
        x_sys = [
            row for row in permit["requestContract"]["resources"]
            if row["module"] == "golang.org/x/sys"
            and row["version"] in {"v0.12.0", "v0.5.0"}
        ]
        self.assertEqual(
            {
                row["expectedH1"]
                for row in x_sys
                if row["kind"] == "mod"
            },
            {"h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg="},
        )
        self.assertEqual(
            len({row["acceptedFileName"] for row in x_sys}),
            4,
        )
        result = runner.validate_execution_context()
        self.assertTrue(result["validationPassed"])
        self.assertEqual(result["requestCount"], 36)
        self.assertFalse(result["networkUsed"])
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        self.assertFalse(
            terminal(runner.ROOT, runner.CHECK.CLAIM_PATH).exists()
        )

    def test_semantic_or_cardinality_mutation_fails_before_claim(self) -> None:
        original, _ = fixture()
        mutations = (
            lambda rows: rows.__setitem__(35, dict(rows[34])),
            lambda rows: rows[35].__setitem__(
                "requestOrdinal",
                37,
            ),
            lambda rows: rows[1].__setitem__(
                "tupleId",
                rows[3]["tupleId"],
            ),
            lambda rows: rows[0].__setitem__(
                "selectedByGraphAlgorithm",
                "false",
            ),
            lambda rows: rows[0].__setitem__(
                "requestOrdinal",
                True,
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                rows = copy.deepcopy(original)
                mutation(rows)
                permit = values(rows)["permit"]
                with self.assertRaises(runner.AcquisitionError):
                    runner._validate_resource_contract(rows, permit)

    def test_expired_deadline_fetches_zero_after_durable_claim(self) -> None:
        rows, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls: list[int] = []
            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: calls.append(
                        resource["requestOrdinal"]
                    ),
                    rows,
                    whole_timeout=-1,
                )
            self.assertEqual(caught.exception.code, "E_DEADLINE")
            self.assertEqual(calls, [])
            self.assertTrue(
                terminal(root, runner.CHECK.CLAIM_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )

    def test_claim_fsync_uncertainty_never_fetches(self) -> None:
        rows, _ = fixture()
        for failing_call in (1, 2):
            with self.subTest(failing_call=failing_call):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    calls = 0
                    fsync_calls = 0

                    def controlled_fsync(fd: int) -> None:
                        nonlocal fsync_calls
                        fsync_calls += 1
                        if fsync_calls == failing_call:
                            raise OSError("synthetic fsync failure")
                        os.fsync(fd)

                    def fetch(_resource, _deadline):
                        nonlocal calls
                        calls += 1
                        return b"x"

                    with self.assertRaises(
                        runner.AcquisitionError
                    ) as caught:
                        self.run_attempt(
                            root,
                            fetch,
                            rows,
                            ops=runner.FileOps(
                                fsync=controlled_fsync
                            ),
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "E_CLAIM_STATE_UNCERTAIN",
                    )
                    self.assertEqual(calls, 0)
                    self.assertTrue(
                        terminal(root, runner.CHECK.CLAIM_PATH).exists()
                    )

    def test_claim_replacement_is_detected_before_network(self) -> None:
        rows, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fetches = 0

            def hook(event: str, namespace) -> None:
                if event != "after_claim_durable":
                    return
                name = Path(runner.CHECK.CLAIM_PATH).name
                os.unlink(name, dir_fd=namespace.dependency_fd)
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=namespace.dependency_fd,
                )
                os.write(fd, b"replacement")
                os.close(fd)

            def fetch(_resource, _deadline):
                nonlocal fetches
                fetches += 1
                return b"x"

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(root, fetch, rows, hook=hook)
            self.assertEqual(
                caught.exception.code,
                "E_FAILURE_PUBLICATION_UNCERTAIN",
            )
            self.assertEqual(fetches, 0)

    def test_intermediate_symlink_and_post_claim_rebind_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            (root / "build").mkdir()
            os.symlink(outside, root / "build" / "offline-source")
            (root / runner.CHECK.BASE).mkdir(parents=True)
            with self.assertRaises(runner.AcquisitionError) as caught:
                with runner.ExecutionNamespace(root):
                    self.fail("intermediate symlink was accepted")
            self.assertEqual(caught.exception.code, "E_NAMESPACE")
            self.assertEqual(list(outside.iterdir()), [])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            outside = root / "outside"
            outside.mkdir()
            source = root / "build" / "offline-source"
            displaced = source.with_name("offline-source-held")
            with runner.ExecutionNamespace(root) as namespace:
                namespace.create_claim(
                    {
                        "documentType": "test-claim",
                        "schemaVersion": "1.0",
                    }
                )
                source.rename(displaced)
                os.symlink(outside, source)
                with self.assertRaises(runner.AcquisitionError) as caught:
                    namespace.barrier(runner.ExecutionState.CLAIMED)
                self.assertEqual(caught.exception.code, "E_NAMESPACE")
                self.assertEqual(namespace.resources, {})
                self.assertIsNone(namespace.staging)
            self.assertEqual(list(outside.iterdir()), [])

    def test_partial_directory_open_failure_closes_every_owned_fd(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            real_open = os.open
            real_close = os.close
            real_fstat = os.fstat
            opened: list[int] = []
            closed: list[int] = []
            fstat_calls = 0

            def tracked_open(*arguments, **keywords):
                fd = real_open(*arguments, **keywords)
                opened.append(fd)
                return fd

            def tracked_close(fd: int) -> None:
                closed.append(fd)
                real_close(fd)

            def failing_fstat(fd: int):
                nonlocal fstat_calls
                fstat_calls += 1
                if fstat_calls == 2:
                    raise OSError("synthetic component fstat failure")
                return real_fstat(fd)

            with mock.patch.object(
                runner.os,
                "open",
                side_effect=tracked_open,
            ), mock.patch.object(
                runner.os,
                "close",
                side_effect=tracked_close,
            ), mock.patch.object(
                runner.os,
                "fstat",
                side_effect=failing_fstat,
            ):
                with self.assertRaises(runner.AcquisitionError) as caught:
                    with runner.ExecutionNamespace(root):
                        self.fail("partial directory open was accepted")
            self.assertEqual(caught.exception.code, "E_NAMESPACE")
            self.assertGreaterEqual(len(opened), 2)
            self.assertTrue(set(opened).issubset(set(closed)))
            for fd in opened:
                with self.assertRaises(OSError):
                    real_fstat(fd)

    def test_preflight_classifies_exact_existing_claim_as_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            terminal(root, runner.CHECK.CLAIM_PATH).write_text(
                "existing",
            )
            with self.assertRaises(runner.AcquisitionError) as caught:
                runner._reject_consumed_claim(root)
            self.assertEqual(caught.exception.code, "E_CONSUMED")
            self.assertEqual(caught.exception.phase, "claim")
            self.assertEqual(
                runner.error_document(caught.exception)["status"],
                "already_consumed",
            )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            terminal(root, runner.CHECK.CLAIM_PATH).with_name(
                Path(runner.CHECK.CLAIM_PATH).name.upper()
            ).write_text("casefold collision")
            with self.assertRaises(runner.AcquisitionError) as caught:
                runner._reject_consumed_claim(root)
            self.assertEqual(caught.exception.code, "E_NAMESPACE")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            with mock.patch.object(
                runner.os,
                "listdir",
                return_value=["\u00e9", "e\u0301"],
            ):
                with self.assertRaises(runner.AcquisitionError) as caught:
                    runner._reject_consumed_claim(root)
            self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_accepted_directory_rebind_blocks_next_write(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir(mode=0o700)
            calls: list[int] = []

            def hook(event: str, namespace) -> None:
                if event != "after_resource_persisted":
                    return
                if len(namespace.resources) != 1:
                    return
                os.rename(
                    "accepted",
                    "accepted-held",
                    src_dir_fd=namespace.staging.fd,
                    dst_dir_fd=namespace.staging.fd,
                )
                os.symlink(
                    outside,
                    "accepted",
                    dir_fd=namespace.staging.fd,
                )

            def fetch(resource, _deadline):
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(root, fetch, rows, hook=hook)
            self.assertEqual(
                caught.exception.code,
                "E_FAILURE_PUBLICATION_UNCERTAIN",
            )
            self.assertEqual(calls, [1])
            self.assertEqual(list(outside.iterdir()), [])

    def test_final_rebind_after_publish_suppresses_receipt(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def hook(event: str, namespace) -> None:
                if event != "after_publish":
                    return
                final = Path(runner.CHECK.FINAL_ROOT).name
                os.rename(
                    final,
                    "moved-final",
                    src_dir_fd=namespace.dependency_fd,
                    dst_dir_fd=namespace.dependency_fd,
                )
                os.mkdir(
                    final,
                    0o700,
                    dir_fd=namespace.dependency_fd,
                )

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    rows,
                    hook=hook,
                )
            self.assertEqual(
                caught.exception.code,
                "E_POST_PUBLISH_UNCERTAIN",
            )
            self.assertFalse(
                terminal(root, runner.CHECK.RECEIPT_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.MANIFEST_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )

    def test_receipt_replacement_prevents_manifest(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def hook(event: str, namespace) -> None:
                if event != "after_receipt_persisted":
                    return
                name = Path(runner.CHECK.RECEIPT_PATH).name
                os.unlink(name, dir_fd=namespace.docs_fd)
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=namespace.docs_fd,
                )
                os.write(fd, b"replacement")
                os.close(fd)

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    rows,
                    hook=hook,
                )
            self.assertEqual(
                caught.exception.code,
                "E_POST_PUBLISH_UNCERTAIN",
            )
            self.assertFalse(
                terminal(root, runner.CHECK.MANIFEST_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )

    def test_atomic_no_replace_preserves_preexisting_final(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def hook(event: str, namespace) -> None:
                if event == "before_publish":
                    os.mkdir(
                        Path(runner.CHECK.FINAL_ROOT).name,
                        0o700,
                        dir_fd=namespace.dependency_fd,
                    )

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    rows,
                    hook=hook,
                )
            self.assertEqual(
                caught.exception.code,
                "E_POST_PUBLISH_UNCERTAIN",
            )
            final = terminal(root, runner.CHECK.FINAL_ROOT)
            self.assertTrue(final.is_dir())
            self.assertEqual(list(final.iterdir()), [])
            self.assertFalse(
                terminal(root, runner.CHECK.RECEIPT_PATH).exists()
            )

    def test_execute_restores_preexisting_real_timer(self) -> None:
        original_handler = signal.getsignal(signal.SIGALRM)
        original_timer = signal.getitimer(signal.ITIMER_REAL)

        def prior_handler(_signum, _frame):
            pass

        signal.signal(signal.SIGALRM, prior_handler)
        signal.setitimer(signal.ITIMER_REAL, 5.0, 0.25)
        started = time.monotonic()
        try:
            authority = mock.Mock()
            authority.__enter__ = mock.Mock(return_value=authority)
            authority.__exit__ = mock.Mock(return_value=None)
            namespace = mock.Mock()
            namespace.__enter__ = mock.Mock(return_value=namespace)
            namespace.__exit__ = mock.Mock(return_value=None)
            with mock.patch.object(
                runner,
                "preflight",
                return_value=({"permit": {}}, {}),
            ), mock.patch.object(
                runner.CHECK,
                "AuthorityFiles",
                return_value=authority,
            ), mock.patch.object(
                runner,
                "ExecutionNamespace",
                return_value=namespace,
            ), mock.patch.object(
                runner,
                "_attempt",
                return_value={"synthetic": True},
            ):
                self.assertEqual(
                    runner.execute(lambda _resource, _deadline: b""),
                    {"synthetic": True},
                )
            delay, interval = signal.getitimer(signal.ITIMER_REAL)
            elapsed = time.monotonic() - started
            self.assertGreater(
                delay,
                max(0.1, 5.0 - elapsed - 0.2),
            )
            self.assertLessEqual(delay, 5.0)
            self.assertAlmostEqual(interval, 0.25, places=2)
            self.assertIs(signal.getsignal(signal.SIGALRM), prior_handler)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, original_handler)
            if original_timer[0] > 0:
                signal.setitimer(
                    signal.ITIMER_REAL,
                    max(
                        0.000001,
                        original_timer[0]
                        - (time.monotonic() - started),
                    ),
                    original_timer[1],
                )

    def test_worker_thread_execute_fails_before_process_state_change(
        self,
    ) -> None:
        before_handler = signal.getsignal(signal.SIGALRM)
        before_timer = signal.getitimer(signal.ITIMER_REAL)
        before_umask = os.umask(0)
        os.umask(before_umask)
        errors: list[BaseException] = []

        def invoke() -> None:
            try:
                runner.execute()
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=invoke)
        worker.start()
        worker.join()
        after_umask = os.umask(0)
        os.umask(after_umask)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], runner.AcquisitionError)
        self.assertEqual(errors[0].code, "E_SIGNAL_THREAD")
        self.assertEqual(signal.getsignal(signal.SIGALRM), before_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), before_timer)
        self.assertEqual(after_umask, before_umask)

    def test_execute_setup_failure_restores_mask_handler_timer_and_umask(
        self,
    ) -> None:
        process = FakeProcessState(fail_step="install_timer")
        with mock.patch.object(
            runner,
            "preflight",
            return_value=({"permit": {}}, {}),
        ):
            with self.assertRaises(OSError):
                runner.execute(
                    lambda _resource, _deadline: b"",
                    process_ops=process.operations(),
                )
        self.assertEqual(
            [
                name for name in process.calls
                if name in {
                    "mask_for_restore",
                    "cancel_installed_timer",
                    "restore_handler",
                    "restore_previous_timer",
                    "restore_signal_mask",
                }
            ],
            [
                "mask_for_restore",
                "cancel_installed_timer",
                "restore_handler",
                "restore_previous_timer",
                "restore_signal_mask",
            ],
        )
        self.assertEqual(process.mask, set())
        self.assertEqual(process.umask_value, 0o022)

    def test_execute_rejects_prior_masked_sigalrm_before_preflight(
        self,
    ) -> None:
        before_handler = signal.getsignal(signal.SIGALRM)
        before_timer = signal.getitimer(signal.ITIMER_REAL)
        before_umask = os.umask(0)
        os.umask(before_umask)
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM},
        )
        try:
            with mock.patch.object(runner, "preflight") as preflight:
                with self.assertRaises(
                    runner.AcquisitionError
                ) as caught:
                    runner.execute()
            self.assertEqual(caught.exception.code, "E_SIGNAL_MASK")
            self.assertEqual(caught.exception.phase, "caller_mask")
            preflight.assert_not_called()
            self.assertEqual(
                signal.getsignal(signal.SIGALRM),
                before_handler,
            )
            self.assertEqual(
                signal.getitimer(signal.ITIMER_REAL),
                before_timer,
            )
            current_umask = os.umask(0)
            os.umask(current_umask)
            self.assertEqual(current_umask, before_umask)
        finally:
            signal.pthread_sigmask(
                signal.SIG_SETMASK,
                previous_mask,
            )

    def test_cleanup_failures_attempt_all_later_restorations_and_are_uncertain(
        self,
    ) -> None:
        cleanup_steps = [
            "mask_for_restore",
            "cancel_installed_timer",
            "restore_handler",
            "restore_previous_timer",
            "restore_umask",
            "restore_signal_mask",
        ]
        for failing_step in cleanup_steps:
            with self.subTest(failing_step=failing_step):
                process = FakeProcessState(fail_step=failing_step)
                authority = mock.Mock()
                authority.__enter__ = mock.Mock(return_value=authority)
                authority.__exit__ = mock.Mock(return_value=None)
                namespace = mock.Mock()
                namespace.__enter__ = mock.Mock(return_value=namespace)
                namespace.__exit__ = mock.Mock(return_value=None)
                with mock.patch.object(
                    runner,
                    "preflight",
                    return_value=({"permit": {}}, {}),
                ), mock.patch.object(
                    runner.CHECK,
                    "AuthorityFiles",
                    return_value=authority,
                ), mock.patch.object(
                    runner,
                    "ExecutionNamespace",
                    return_value=namespace,
                ), mock.patch.object(
                    runner,
                    "_attempt",
                    return_value={"synthetic": True},
                ):
                    with self.assertRaises(
                        runner.AcquisitionError
                    ) as caught:
                        runner.execute(
                            lambda _resource, _deadline: b"",
                            process_ops=process.operations(),
                        )
                self.assertEqual(
                    caught.exception.code,
                    "E_PROCESS_STATE_RESTORE_UNCERTAIN",
                )
                self.assertIs(caught.exception.consumed, True)
                self.assertEqual(
                    runner.error_document(caught.exception)["status"],
                    "consumed_terminal_state_uncertain",
                )
                observed_cleanup = [
                    name for name in process.calls
                    if name in cleanup_steps
                ]
                expected_cleanup = list(cleanup_steps)
                if failing_step == "restore_handler":
                    expected_cleanup.remove("restore_previous_timer")
                    expected_cleanup.remove("restore_signal_mask")
                    self.assertIn(
                        signal.SIGALRM,
                        process.mask,
                    )
                    self.assertIn(
                        "contain_signal_mask",
                        process.calls,
                    )
                    self.assertEqual(process.timer, (0.0, 0.0))
                self.assertEqual(observed_cleanup, expected_cleanup)

    def test_pending_restore_alarm_is_consumed_before_prior_handler(
        self,
    ) -> None:
        def run_case(process: FakeProcessState) -> runner.AcquisitionError:
            authority = mock.Mock()
            authority.__enter__ = mock.Mock(return_value=authority)
            authority.__exit__ = mock.Mock(return_value=None)
            namespace = mock.Mock()
            namespace.__enter__ = mock.Mock(return_value=namespace)
            namespace.__exit__ = mock.Mock(return_value=None)
            with mock.patch.object(
                runner,
                "preflight",
                return_value=({"permit": {}}, {}),
            ), mock.patch.object(
                runner.CHECK,
                "AuthorityFiles",
                return_value=authority,
            ), mock.patch.object(
                runner,
                "ExecutionNamespace",
                return_value=namespace,
            ), mock.patch.object(
                runner,
                "_attempt",
                return_value={"synthetic": True},
            ):
                with self.assertRaises(
                    runner.AcquisitionError
                ) as caught:
                    runner.execute(
                        lambda _resource, _deadline: b"",
                        process_ops=process.operations(),
                    )
            return caught.exception

        for fail_steps, expected_containment in (
            (set(), False),
            ({"inspect_pending_alarm"}, True),
            ({"drain_pending_alarm"}, True),
        ):
            with self.subTest(fail_steps=sorted(fail_steps)):
                prior_calls: list[int] = []

                def prior_handler(signum, _frame):
                    prior_calls.append(signum)

                process = FakeProcessState(
                    fail_steps=fail_steps,
                    pending_on_cancel=True,
                )
                process.handler = prior_handler
                error = run_case(process)
                self.assertEqual(
                    error.code,
                    "E_PROCESS_STATE_RESTORE_UNCERTAIN",
                )
                self.assertIs(error.consumed, True)
                self.assertEqual(
                    runner.error_document(error)["status"],
                    "consumed_terminal_state_uncertain",
                )
                self.assertEqual(prior_calls, [])
                self.assertEqual(
                    "contain_signal_mask" in process.calls,
                    expected_containment,
                )
                if expected_containment:
                    self.assertIn(signal.SIGALRM, process.mask)
                    self.assertEqual(process.timer, (0.0, 0.0))
                    self.assertNotIn(
                        "restore_handler",
                        process.calls,
                    )
                    self.assertNotIn(
                        "restore_signal_mask",
                        process.calls,
                    )
                else:
                    self.assertEqual(process.pending, set())
                    self.assertIs(process.handler, prior_handler)
                    self.assertEqual(process.mask, set())

    def test_terminal_teardown_alarm_closes_all_fds_and_is_uncertain(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            authority = mock.Mock()
            authority.__enter__ = mock.Mock(return_value=authority)
            authority.__exit__ = mock.Mock(return_value=None)
            owned_fds: list[int] = []

            def synthetic_attempt(
                _fetch,
                _values,
                namespace,
                *,
                checkpoint,
            ):
                self.assertIsNotNone(checkpoint)
                namespace.create_claim(
                    {
                        "documentType": "test-claim",
                        "schemaVersion": "1.0",
                    }
                )
                namespace.published = True
                owned_fds.extend(
                    [
                        namespace.claim.fd,
                        *namespace.owned_directory_fds,
                    ]
                )
                return {"synthetic": True}

            real_close = os.close
            real_fstat = os.fstat
            first_close = True

            def interrupted_first_close(fd: int) -> None:
                nonlocal first_close
                if first_close:
                    first_close = False
                    raise runner.AcquisitionError(
                        "E_DEADLINE",
                        "synthetic_terminal_close",
                    )
                real_close(fd)

            process = FakeProcessState()
            with mock.patch.object(
                runner,
                "ROOT",
                root,
            ), mock.patch.object(
                runner,
                "preflight",
                return_value=({"permit": {}}, {}),
            ), mock.patch.object(
                runner.CHECK,
                "AuthorityFiles",
                return_value=authority,
            ), mock.patch.object(
                runner,
                "_attempt",
                side_effect=synthetic_attempt,
            ), mock.patch.object(
                runner.os,
                "close",
                side_effect=interrupted_first_close,
            ):
                with self.assertRaises(
                    runner.AcquisitionError
                ) as caught:
                    runner.execute(
                        lambda _resource, _deadline: b"",
                        process_ops=process.operations(),
                    )
            self.assertEqual(
                caught.exception.code,
                "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
            )
            self.assertIs(caught.exception.consumed, True)
            self.assertEqual(
                runner.error_document(caught.exception)["status"],
                "consumed_terminal_state_uncertain",
            )
            self.assertTrue(owned_fds)
            for fd in owned_fds:
                with self.assertRaises(OSError):
                    real_fstat(fd)

    def test_success_result_store_alone_marks_teardown_as_consumed(
        self,
    ) -> None:
        authority = mock.Mock()
        authority.__enter__ = mock.Mock(return_value=authority)
        authority.__exit__ = mock.Mock(return_value=None)
        namespace = mock.Mock()
        namespace.claim = None
        namespace.published = False
        namespace.receipt = None
        namespace.manifest = None
        namespace.failure = None
        namespace.__enter__ = mock.Mock(return_value=namespace)
        namespace.__exit__ = mock.Mock(
            side_effect=runner.AcquisitionError(
                "E_DEADLINE",
                "synthetic_result_store_boundary",
            )
        )
        with mock.patch.object(
            runner,
            "preflight",
            return_value=({"permit": {}}, {}),
        ), mock.patch.object(
            runner.CHECK,
            "AuthorityFiles",
            return_value=authority,
        ), mock.patch.object(
            runner,
            "ExecutionNamespace",
            return_value=namespace,
        ), mock.patch.object(
            runner,
            "_attempt",
            return_value={"synthetic": True},
        ):
            with self.assertRaises(
                runner.AcquisitionError
            ) as caught:
                runner.execute(
                    lambda _resource, _deadline: b"",
                    process_ops=FakeProcessState().operations(),
                )
        self.assertEqual(
            caught.exception.code,
            "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
        )
        self.assertIs(caught.exception.consumed, True)
        self.assertEqual(
            runner.error_document(caught.exception)["status"],
            "consumed_terminal_state_uncertain",
        )

    def test_namespace_close_defers_alarm_until_every_fd_is_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            namespace = runner.ExecutionNamespace(root).__enter__()
            namespace.create_claim(
                {
                    "documentType": "test-claim",
                    "schemaVersion": "1.0",
                }
            )
            owned_fds = [
                namespace.claim.fd,
                *namespace.owned_directory_fds,
            ]
            real_sigmask = signal.pthread_sigmask
            real_close = os.close
            real_fstat = os.fstat
            events: list[str] = []

            def alarm_after_mask_restore(how, values):
                events.append(
                    "mask_block"
                    if how == signal.SIG_BLOCK
                    else "mask_restore"
                )
                previous = real_sigmask(how, values)
                if how == signal.SIG_SETMASK:
                    raise runner.AcquisitionError(
                        "E_DEADLINE",
                        "synthetic_close_boundary",
                    )
                return previous

            def tracked_close(fd: int) -> None:
                events.append(f"close:{fd}")
                real_close(fd)

            with mock.patch.object(
                runner.signal,
                "pthread_sigmask",
                side_effect=alarm_after_mask_restore,
            ), mock.patch.object(
                runner.os,
                "close",
                side_effect=tracked_close,
            ):
                with self.assertRaises(
                    runner.AcquisitionError
                ) as caught:
                    namespace.close()
            self.assertEqual(caught.exception.code, "E_DEADLINE")
            self.assertTrue(owned_fds)
            self.assertEqual(events[0], "mask_block")
            self.assertEqual(events[-1], "mask_restore")
            self.assertEqual(
                len(
                    [
                        event
                        for event in events[1:-1]
                        if event.startswith("close:")
                    ]
                ),
                len(owned_fds),
            )
            for fd in owned_fds:
                with self.assertRaises(OSError):
                    real_fstat(fd)

    def test_error_document_never_requests_authentication_or_retry(self) -> None:
        value = runner.error_document(
            runner.AcquisitionError("E_NETWORK", "request_01")
        )
        self.assertFalse(value["retryAllowed"])
        self.assertFalse(value["externalAuthenticationRequired"])
        self.assertFalse(value["userActionRequired"])

        resource = fixture()[0][0]
        connection_calls: list[tuple[str, int]] = []
        request_calls: list[tuple[tuple, dict]] = []

        class RejectedResponse:
            status = 500

            @staticmethod
            def getheaders():
                return [("Location", "https://hostile.invalid/")]

            @staticmethod
            def getheader(_name):
                return None

        class DirectConnection:
            def __init__(self, host, port, **_kwargs):
                connection_calls.append((host, port))

            @staticmethod
            def request(*_args, **_kwargs):
                request_calls.append((_args, _kwargs))

            @staticmethod
            def getresponse():
                return RejectedResponse()

            @staticmethod
            def close():
                return None

        hostile_environment = {
            "HTTP_PROXY": "http://hostile.invalid:8080",
            "HTTPS_PROXY": "http://hostile.invalid:8443",
            "ALL_PROXY": "socks5://hostile.invalid:1080",
            "NO_PROXY": "",
        }
        for status in (302, 401, 407):
            RejectedResponse.status = status
            with self.subTest(status=status):
                with mock.patch.dict(
                    os.environ,
                    hostile_environment,
                    clear=False,
                ):
                    with self.assertRaises(
                        runner.VALIDATION.AcquisitionError
                    ) as caught:
                        runner.VALIDATION.direct_fetch(
                            resource,
                            time.monotonic() + 5,
                            connection_factory=DirectConnection,
                        )
                self.assertEqual(caught.exception.code, "E_RESPONSE")
        self.assertEqual(
            connection_calls,
            [(runner.CHECK.PROXY_HOST, 443)] * 3,
        )
        self.assertEqual(len(request_calls), 3)
        for args, kwargs in request_calls:
            serialized = repr((args, kwargs))
            self.assertNotIn("Authorization", serialized)
            self.assertNotIn("Cookie", serialized)

    def test_wave6_direct_fetch_reaches_wave4_and_translates_errors(
        self,
    ) -> None:
        resource = fixture()[0][0]
        deadline = time.monotonic() + 5
        with mock.patch.object(
            runner.WAVE4,
            "direct_fetch",
            return_value=b"response",
        ) as primitive:
            self.assertEqual(
                runner.direct_fetch(resource, deadline),
                b"response",
            )
            primitive.assert_called_once_with(resource, deadline)
        primitive_error = runner.WAVE4.AcquisitionError(
            "E_RESPONSE",
            "request_01",
        )
        with mock.patch.object(
            runner.WAVE4,
            "direct_fetch",
            side_effect=primitive_error,
        ):
            with self.assertRaises(runner.AcquisitionError) as caught:
                runner.direct_fetch(resource, deadline)
        self.assertEqual(caught.exception.code, "E_RESPONSE")
        self.assertEqual(caught.exception.phase, "request_01")
        self.assertIs(
            inspect.signature(runner.execute).parameters[
                "fetch"
            ].default,
            runner.direct_fetch,
        )

    def test_response_and_zip_aggregate_branches_report_counters(
        self,
    ) -> None:
        def failure_for(
            rows,
            bodies,
            patches,
        ):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with patches:
                    with self.assertRaises(
                        runner.AcquisitionError
                    ) as caught:
                        self.run_attempt(
                            root,
                            lambda resource, _deadline: bodies[
                                resource["requestOrdinal"]
                            ],
                            rows,
                        )
                failure = json.loads(
                    terminal(root, runner.CHECK.FAILURE_PATH).read_text()
                )
                return caught.exception, failure

        rows, _ = fixture()
        individual_rows = copy.deepcopy(rows)
        for row in individual_rows:
            if row["kind"] == "mod":
                row["maximumResponseBodyBytes"] = 1
        error, failure = failure_for(
            individual_rows,
            {1: b"xx"},
            mock.patch.object(runner.CHECK, "MAX_MOD_BYTES", 1),
        )
        self.assertEqual((error.code, error.phase), (
            "E_RESPONSE_SIZE",
            "request_01",
        ))
        self.assertEqual(
            (
                failure["dispatchBoundaryCount"],
                failure["responseCommittedCount"],
                failure["validationCommittedCount"],
                failure["persistenceCommittedCount"],
            ),
            (1, 1, 0, 0),
        )

        rows, _ = fixture()
        error, failure = failure_for(
            rows,
            {1: b"xx"},
            mock.patch.object(
                runner.CHECK,
                "MAX_AGGREGATE_MOD_BYTES",
                1,
            ),
        )
        self.assertEqual((error.code, error.phase), (
            "E_RESPONSE_SIZE",
            "aggregate_mod",
        ))
        self.assertEqual(
            (
                failure["dispatchBoundaryCount"],
                failure["responseCommittedCount"],
                failure["validationCommittedCount"],
                failure["persistenceCommittedCount"],
            ),
            (1, 1, 0, 0),
        )

        rows, _ = fixture()
        synthetic_mod = mock.patch.object(
            runner.VALIDATION,
            "validate_mod",
            return_value={"goModH1": rows[0]["expectedH1"]},
        )
        with synthetic_mod:
            error, failure = failure_for(
                rows,
                {1: b"m", 2: b"zz"},
                mock.patch.object(
                    runner.CHECK,
                    "MAX_AGGREGATE_ZIP_BYTES",
                    1,
                ),
            )
        self.assertEqual((error.code, error.phase), (
            "E_RESPONSE_SIZE",
            "aggregate_zip",
        ))
        self.assertEqual(
            (
                failure["dispatchBoundaryCount"],
                failure["responseCommittedCount"],
                failure["validationCommittedCount"],
                failure["persistenceCommittedCount"],
            ),
            (2, 2, 1, 1),
        )
        self.assertIsNone(failure["currentResourceOrdinal"])
        self.assertIsNone(failure["currentOperationPhase"])
        self.assertIs(
            failure["additionalCompletionUncertain"],
            False,
        )

        rows, _ = fixture()
        aggregate_zip_limit = 150
        individually_valid_uncompressed = 100
        self.assertLessEqual(
            individually_valid_uncompressed,
            runner.CHECK.MAX_ZIP_UNCOMPRESSED_BYTES,
        )
        self.assertLessEqual(
            individually_valid_uncompressed,
            aggregate_zip_limit,
        )
        expected_mod_h1 = {
            row["module"]: row["expectedH1"]
            for row in rows
            if row["kind"] == "mod"
        }
        expected_zip_h1 = {
            row["module"]: row["expectedH1"]
            for row in rows
            if row["kind"] == "zip"
        }

        def cumulative_mod(_raw, module):
            return {"goModH1": expected_mod_h1[module]}

        def cumulative_zip(_raw, module, _version, _mod):
            return {
                "moduleZipH1": expected_zip_h1[module],
                "entryCount": 1,
                "uncompressedBytes": individually_valid_uncompressed,
            }

        with mock.patch.object(
            runner.VALIDATION,
            "validate_mod",
            side_effect=cumulative_mod,
        ), mock.patch.object(
            runner.VALIDATION,
            "validate_zip",
            side_effect=cumulative_zip,
        ), mock.patch.object(
            runner.CHECK,
            "MAX_ALL_ZIP_UNCOMPRESSED_BYTES",
            aggregate_zip_limit,
        ):
            error, failure = failure_for(
                rows,
                {
                    1: b"m1",
                    2: b"z1",
                    3: b"m2",
                    4: b"z2",
                },
                nullcontext(),
            )
        self.assertEqual((error.code, error.phase), (
            "E_ZIP_AGGREGATE",
            "zip",
        ))
        self.assertEqual(
            (
                failure["dispatchBoundaryCount"],
                failure["responseCommittedCount"],
                failure["validationCommittedCount"],
                failure["persistenceCommittedCount"],
            ),
            (4, 4, 3, 3),
        )
        self.assertEqual(failure["currentResourceOrdinal"], 4)
        self.assertEqual(
            failure["currentOperationPhase"],
            "validation_may_have_completed",
        )
        self.assertIs(
            failure["additionalCompletionUncertain"],
            True,
        )
        rows, _ = fixture()
        with mock.patch.object(
            runner.VALIDATION,
            "validate_mod",
            return_value={"goModH1": rows[0]["expectedH1"]},
        ):
            error, failure = failure_for(
                rows,
                {1: b"mm", 2: b"zz"},
                mock.patch.object(
                    runner.CHECK,
                    "MAX_AGGREGATE_BYTES",
                    3,
                ),
            )
        self.assertEqual((error.code, error.phase), (
            "E_RESPONSE_SIZE",
            "aggregate_total",
        ))
        self.assertEqual(
            (
                failure["dispatchBoundaryCount"],
                failure["responseCommittedCount"],
                failure["validationCommittedCount"],
                failure["persistenceCommittedCount"],
            ),
            (2, 2, 1, 1),
        )
        self.assertIsNone(failure["currentResourceOrdinal"])
        self.assertIsNone(failure["currentOperationPhase"])
        self.assertIs(
            failure["additionalCompletionUncertain"],
            False,
        )

        rows, _ = fixture()
        with mock.patch.object(
            runner.VALIDATION,
            "validate_mod",
            return_value={"goModH1": rows[0]["expectedH1"]},
        ), mock.patch.object(
            runner.VALIDATION,
            "validate_zip",
            return_value={
                "moduleZipH1": rows[1]["expectedH1"],
                "entryCount": runner.CHECK.MAX_ALL_ZIP_FILES + 1,
                "uncompressedBytes": 0,
            },
        ):
            error, failure = failure_for(
                rows,
                {1: b"m", 2: b"z"},
                nullcontext(),
            )
        self.assertEqual((error.code, error.phase), (
            "E_ZIP_AGGREGATE",
            "zip",
        ))
        self.assertEqual(
            (
                failure["dispatchBoundaryCount"],
                failure["responseCommittedCount"],
                failure["validationCommittedCount"],
                failure["persistenceCommittedCount"],
            ),
            (2, 2, 1, 1),
        )
        self.assertEqual(failure["currentResourceOrdinal"], 2)
        self.assertEqual(
            failure["currentOperationPhase"],
            "validation_may_have_completed",
        )
        self.assertIs(
            failure["additionalCompletionUncertain"],
            True,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
