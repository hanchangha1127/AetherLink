#!/usr/bin/env python3
"""Tests for the Wave6 acquisition permit checker."""

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
    raise RuntimeError("Wave6 acquisition tests require `python3 -I -B -S`")

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave6_acquisition_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave6_acquisition_permit_v1",
    CHECKER_PATH,
)
assert SPEC and SPEC.loader
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


class Wave6AcquisitionPermitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package, cls.summary = check.evaluate(True)
        cls.decision = cls.package["decision"]
        cls.permit = cls.package["permit"]
        cls.rows = check.normalized_resources(cls.decision)

    def test_materialized_package_is_exact_and_content_bound(self) -> None:
        raw = (check.ROOT / check.PERMIT_PATH).read_bytes()
        self.assertEqual(raw, check.canonical_bytes(self.permit))
        self.assertEqual(check.strict_json(raw), self.permit)
        without = dict(self.permit)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            check.sha256(check.canonical_bytes(without)),
        )
        actual = {
            path: check.sha256((check.ROOT / path).read_bytes())
            for path in (
                check.THIS_CHECKER_PATH,
                check.THIS_TESTS_PATH,
                check.RUNNER_PATH,
                check.RUNNER_TESTS_PATH,
            )
        }
        self.assertEqual(
            {
                row["path"]: row["rawSha256"]
                for row in self.permit["toolBindings"]
            },
            actual,
        )

    def test_exact_request_contract_and_no_authentication(self) -> None:
        self.assertEqual(len(self.rows), 36)
        self.assertEqual(
            [row["requestOrdinal"] for row in self.rows],
            list(range(1, 37)),
        )
        self.assertEqual(
            [row["kind"] for row in self.rows],
            ["mod", "zip"] * 18,
        )
        self.assertEqual(
            sum(row["selectedByGraphAlgorithm"] for row in self.rows[::2]),
            0,
        )
        self.assertEqual(
            self.permit["requestContract"][
                "sourceRequestSetCanonicalSha256"
            ],
            "d1ea9ec1fab702b1bf405f13e1d7aaeb9a5354ff7f98a0d916870def124372a1",
        )
        source_requests = self.decision[
            "sourceAcquisitionPreparation"
        ]["requestSet"]
        self.assertEqual(
            check.sha256(check.digest_bytes(source_requests)),
            "d1ea9ec1fab702b1bf405f13e1d7aaeb9a5354ff7f98a0d916870def124372a1",
        )
        self.assertNotEqual(
            check.sha256(check.canonical_bytes(source_requests)),
            "d1ea9ec1fab702b1bf405f13e1d7aaeb9a5354ff7f98a0d916870def124372a1",
        )
        self.assertEqual(
            self.permit["requestContract"]["resourcesCanonicalSha256"],
            "9fe734b3800d051abe4c4df0cbf7e5545594da90588c625b253a2535f1310cb0",
        )
        self.assertEqual(
            self.permit["oneUseContract"]["existingClaimState"],
            "already_consumed",
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "claimAbsentAtPermitPublication"
            ],
            True,
        )
        self.assertEqual(
            self.permit["authority"],
            {
                "wave6PublicProxy36GetAcquisitionAuthorizedOnce": True,
                "dnsTcpTlsHttpsToExactProxyAuthorized": True,
                "sourceExtractionAuthorized": False,
                "sourceLoadOrExecutionAuthorized": False,
                "compileAuthorized": False,
                "packageManagerAuthorized": False,
                "subprocessAuthorized": False,
                "gitOperationAuthorized": False,
                "deviceAuthorized": False,
                "deploymentAuthorized": False,
                "productRuntimeNetworkAuthorized": False,
                "repositoryOwnerIdentityProofRequired": False,
                "accountRequired": False,
                "ownerRequired": False,
                "sshRequired": False,
                "gpgRequired": False,
                "externalAuthenticationRequired": False,
                "authenticationRequired": False,
                "passwordRequired": False,
                "privateKeyRequired": False,
                "signatureRequired": False,
                "tokenRequired": False,
                "cookieRequired": False,
                "clientCertificateRequired": False,
                "userActionRequired": False,
            },
        )
        true_authority = {
            "wave6PublicProxy36GetAcquisitionAuthorizedOnce",
            "dnsTcpTlsHttpsToExactProxyAuthorized",
        }
        for key, value in self.permit["authority"].items():
            self.assertIs(value, key in true_authority)
        self.assertFalse(
            self.permit["authority"]["externalAuthenticationRequired"]
        )
        self.assertFalse(
            self.permit["authority"]["repositoryOwnerIdentityProofRequired"]
        )
        self.assertFalse(self.permit["authority"]["passwordRequired"])
        self.assertFalse(self.permit["authority"]["privateKeyRequired"])
        self.assertFalse(self.permit["authority"]["signatureRequired"])
        self.assertFalse(self.permit["authority"]["tokenRequired"])
        self.assertFalse(self.permit["authority"]["userActionRequired"])
        self.assertFalse(
            self.permit["requestContract"]["authenticationAllowed"]
        )
        x_sys = [
            row for row in self.rows
            if row["module"] == "golang.org/x/sys"
            and row["version"] in {"v0.12.0", "v0.5.0"}
        ]
        self.assertEqual(len(x_sys), 4)
        self.assertEqual(len({row["tupleId"] for row in x_sys}), 2)
        self.assertEqual(len({row["url"] for row in x_sys}), 4)
        x_sys_mod = [row for row in x_sys if row["kind"] == "mod"]
        self.assertEqual(len(x_sys_mod), 2)
        self.assertEqual(
            {row["expectedH1"] for row in x_sys_mod},
            {"h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg="},
        )
        self.assertEqual(
            len({row["acceptedFileName"] for row in x_sys}),
            4,
        )
        identity_rows = self.decision["identityResolution"]["tuples"]
        self.assertEqual(
            [
                (
                    row["module"],
                    row["version"],
                    row["goModH1"],
                    row["moduleZipH1"],
                )
                for row in identity_rows
            ],
            check.DECISION.EXPECTED_IDENTITY_H1,
        )
        for tuple_order, identity in enumerate(identity_rows, 1):
            mod, archive = self.rows[(tuple_order - 1) * 2:tuple_order * 2]
            self.assertIs(identity["selectedByGraphAlgorithm"], False)
            self.assertIs(mod["selectedByGraphAlgorithm"], False)
            self.assertIs(archive["selectedByGraphAlgorithm"], False)
            self.assertEqual(mod["expectedH1"], identity["goModH1"])
            self.assertEqual(
                archive["expectedH1"],
                identity["moduleZipH1"],
            )

    def test_portfolio_caps_and_stale_wave_markers_are_pinned(self) -> None:
        limits = self.permit["absoluteResourceLimits"]
        self.assertEqual(limits["maximumRequestCount"], 36)
        self.assertEqual(
            limits["maximumAggregateModResponseBodyBytes"],
            8 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateZipResponseBodyBytes"],
            128 * 1024 * 1024,
        )
        self.assertEqual(
            limits["maximumAggregateResponseBodyBytes"],
            128 * 1024 * 1024,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "heldRootRelativeComponentTraversalRequired"
            ],
            True,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "intermediateDirectoryIdentityHeldThroughExecution"
            ],
            True,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "localFdOwnershipTransferAndCloseCleanupDefersOnlySigalrmAndSigint"
            ],
            True,
        )
        self.assertIs(
            self.permit["oneUseContract"][
                "closeCleanupCompletesBeforePriorSignalMaskRestoration"
            ],
            True,
        )
        self.assertIs(
            limits["callerBlockedSigalrmRejectedBeforePreflight"],
            True,
        )
        self.assertIs(
            limits["sigalrmUnblockedDuringFetchValidationWriteAndFsync"],
            True,
        )
        self.assertIs(
            limits[
                "originalSignalMaskRestoredExactlyOrUncertaintyReported"
            ],
            True,
        )
        self.assertIs(
            limits[
                "pendingInstalledSigalrmSynchronouslyConsumedBeforePriorHandlerRestoration"
            ],
            True,
        )
        self.assertIs(
            limits[
                "pendingSigalrmDrainFailureContainedWithoutPriorAlarmStateRestoration"
            ],
            True,
        )
        self.assertIs(
            limits["priorHandlerRestoredBeforePriorTimerArmed"],
            True,
        )
        self.assertIs(
            self.permit["terminalContract"][
                "failureOperationCountsAreCommittedLowerBounds"
            ],
            True,
        )
        self.assertEqual(
            self.permit["terminalContract"][
                "zeroCommittedResponsesWithActiveFetchState"
            ],
            "unknown_after_dispatch",
        )
        self.assertEqual(
            self.permit["terminalContract"][
                "terminalTeardownUncertaintyFailureCode"
            ],
            "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
        )
        for path in (
            check.THIS_CHECKER_PATH,
            check.THIS_TESTS_PATH,
            check.RUNNER_PATH,
            check.RUNNER_TESTS_PATH,
            check.PERMIT_READER_PATH,
        ):
            source = (check.ROOT / path).read_text(encoding="utf-8")
            self.assertNotIn("wave" + "5", source.casefold())
            self.assertNotIn("wave-" + "5", source.casefold())
            self.assertNotIn("3" + "0-resource", source)
            self.assertNotIn("requestCount\"] == " + "30", source)
            self.assertNotIn('"requestCount": ' + "30", source)
            self.assertNotIn('"tupleCount": ' + "15", source)

    def test_resource_schema_mutations_fail_closed(self) -> None:
        for mutation in (
            lambda row: row.__setitem__("requestOrdinal", 2),
            lambda row: row.__setitem__("requestOrdinal", True),
            lambda row: row.__setitem__("resourceKind", "zip"),
            lambda row: row.__setitem__("authenticationRequired", True),
            lambda row: row.__setitem__("networkAuthorized", True),
            lambda row: row.__setitem__("maximumResponseBytes", 3),
            lambda row: row.__setitem__("maximumResponseBytes", True),
            lambda row: row.__setitem__("url", row["url"] + "?x=1"),
            lambda row: row.__setitem__("acceptedFileName", "wrong.mod"),
            lambda row: row.__setitem__(
                "selectedByGraphAlgorithm",
                "false",
            ),
            lambda row: row.__setitem__("selectedByGraphAlgorithm", 1),
            lambda row: row.__setitem__("module", "a//b"),
            lambda row: row.__setitem__("module", "a/../b"),
        ):
            source = copy.deepcopy(
                self.decision["sourceAcquisitionPreparation"]["requestSet"]
            )
            mutation(source[0])
            with self.assertRaises(check.CheckError):
                check._normalize_request_rows(source)
        changed = copy.deepcopy(self.decision)
        changed["sourceAcquisitionPreparation"]["requestCount"] = False
        with self.assertRaises(check.CheckError):
            check.normalized_resources(changed)

    def test_runner_reverse_pin_and_normalized_hash_fail_closed(self) -> None:
        runner_raw = (check.ROOT / check.RUNNER_PATH).read_bytes()
        checker_raw = (check.ROOT / check.THIS_CHECKER_PATH).read_bytes()
        check.validate_runner(runner_raw, checker_raw)
        reverse_mutation = runner_raw.replace(
            check.sha256(checker_raw).encode(),
            b"0" * 64,
            1,
        )
        with self.assertRaises(check.CheckError):
            check.validate_runner(reverse_mutation, checker_raw)
        body_mutation = runner_raw.replace(
            b"consumed_active",
            b"consumed_altered",
            1,
        )
        with self.assertRaises(check.CheckError):
            check.validate_runner(body_mutation, checker_raw)

    def test_strict_json_rejects_duplicates_and_noncanonical_is_separate(self) -> None:
        with self.assertRaises(check.CheckError):
            check.strict_json(b'{"a":1,"a":2}\n')
        value = {"b": 1, "a": 2}
        raw = check.canonical_bytes(value)
        self.assertEqual(check.strict_json(raw), value)
        self.assertNotEqual(raw, b'{"b":1,"a":2}\n')

    def test_runner_ast_has_no_ambient_network_or_subprocess_client(self) -> None:
        raw = (check.ROOT / check.RUNNER_PATH).read_bytes()
        source = raw.decode("utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        self.assertTrue(
            {"subprocess", "requests", "socket", "urllib.request"}
            .isdisjoint(imports)
        )
        self.assertNotIn("Authorization", source)
        self.assertNotIn("Proxy-Authorization", source)
        self.assertNotIn("Cookie", source)
        self.assertNotIn("def _stable(", source)
        self.assertIn("signal.pthread_sigmask", source)
        self.assertIn("directory_steps", source)
        self.assertIn("ImmutablePhaseLedger", source)
        self.assertIn("ProcessStateGuard", source)
        self.assertNotIn("ResourceOperationBoundary", source)

    def test_terminal_namespace_rejects_broken_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / check.BASE
            base.mkdir(parents=True)
            os.symlink(
                "missing",
                base / Path(check.RECEIPT_PATH).name,
            )
            with self.assertRaises(check.CheckError):
                check.HeldTerminalNamespace(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / check.BASE
            base.mkdir(parents=True)
            (base / Path(check.RECEIPT_PATH).name.upper()).write_text(
                "casefold collision",
            )
            with self.assertRaises(check.CheckError):
                check.HeldTerminalNamespace(root)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / check.BASE).mkdir(parents=True)
            with mock.patch.object(
                check.os,
                "listdir",
                return_value=["\u00e9", "e\u0301"],
            ):
                with self.assertRaises(check.CheckError):
                    check.HeldTerminalNamespace(root)

    def test_terminal_namespace_partial_open_closes_owned_fds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / check.BASE).mkdir(parents=True)
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
                    raise OSError("synthetic terminal component failure")
                return real_fstat(fd)

            with mock.patch.object(
                check.os,
                "open",
                side_effect=tracked_open,
            ), mock.patch.object(
                check.os,
                "close",
                side_effect=tracked_close,
            ), mock.patch.object(
                check.os,
                "fstat",
                side_effect=failing_fstat,
            ):
                with self.assertRaises(OSError):
                    check.HeldTerminalNamespace(root)
            self.assertGreaterEqual(len(opened), 2)
            self.assertTrue(set(opened).issubset(set(closed)))
            for fd in opened:
                with self.assertRaises(OSError):
                    real_fstat(fd)

    def test_pinned_hardlink_and_terminal_root_rebind_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = "held/input.bin"
            target = root / relative
            target.parent.mkdir()
            target.write_bytes(b"held")
            os.link(target, target.with_name("alias.bin"))
            with self.assertRaises(check.DECISION.DecisionFailure):
                check.DECISION.PinnedFile(
                    root,
                    relative,
                    expected_sha256=check.sha256(b"held"),
                    maximum_bytes=16,
                )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "root"
            (root / check.BASE).mkdir(parents=True)
            held = check.HeldTerminalNamespace(root)
            displaced = base / "displaced"
            root.rename(displaced)
            (root / check.BASE).mkdir(parents=True)
            try:
                with self.assertRaises(check.CheckError):
                    held.final_barrier()
            finally:
                held.close()

    def test_content_binding_is_reproducible(self) -> None:
        payload = check.content_bound({"z": 1, "a": [2]})
        without = dict(payload)
        binding = without.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            check.sha256(check.canonical_bytes(without)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
