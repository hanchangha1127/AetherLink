#!/usr/bin/env python3
"""Offline contract tests for the Wave3 acquisition decision and permit."""

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
import copy
import hashlib
import json
from pathlib import Path
import unittest


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition_v1.py"
)
SOURCE = PATH.read_bytes()
NAMESPACE = {"__file__": str(PATH), "__name__": "wave3_acquisition_checker_test"}
exec(compile(SOURCE, str(PATH), "exec"), NAMESPACE)
C = type("Checker", (), NAMESPACE)


class Wave3AcquisitionContractTests(unittest.TestCase):
    def test_01_exact_package_validates_offline(self):
        values, summary = C.evaluate(True)
        self.assertTrue(summary["validationPassed"])
        self.assertEqual(summary["requestCount"], 32)
        self.assertFalse(summary["networkUsed"])
        self.assertFalse(summary["sourceAcquired"])
        self.assertEqual(values["decision"]["status"], "exact_32_resource_contract_prepared_acquisition_not_authorized")
        self.assertEqual(values["permit"]["status"], "authorized_not_consumed")

    def test_02_v2_binding_and_resource_derivation_are_exact(self):
        v2 = C.v2_expected()
        rows = C.resources_from_v2(v2)
        self.assertEqual(len(rows), 32)
        self.assertEqual([row["tupleOrder"] for row in rows], [value for value in range(1, 17) for _ in range(2)])
        self.assertEqual([row["kind"] for row in rows], ["mod", "zip"] * 16)
        self.assertEqual(rows[0]["url"], "https://proxy.golang.org/github.com/kr/pty/@v/v1.1.1.mod")
        self.assertEqual(rows[-1]["url"], "https://proxy.golang.org/golang.org/x/tools/@v/v0.41.0.zip")
        self.assertTrue(all(row["expectedH1"].startswith("h1:") for row in rows))

    def test_03_decision_has_no_execution_authority(self):
        values, _ = C.evaluate(True)
        authority = values["decision"]["authority"]
        self.assertTrue(authority["decisionRecorded"])
        self.assertTrue(all(value is False for key, value in authority.items() if key != "decisionRecorded"))
        self.assertFalse(values["decision"]["reservedNamespace"]["reservationIsWriteAuthority"])

    def test_04_permit_is_exact_one_use_authentication_free_scope(self):
        permit = C.evaluate(True)[0]["permit"]
        request = permit["requestContract"]
        self.assertEqual(request["requestCount"], 32)
        self.assertTrue(request["directHttpsOnly"])
        for key in (
            "redirectAllowed", "ambientProxyAllowed", "alternateHostAllowed",
            "authenticationAllowed", "authorizationHeaderAllowed",
            "proxyAuthorizationHeaderAllowed", "cookieAllowed",
            "clientCertificateAllowed", "rangeHeaderAllowed",
            "queryOrFragmentAllowed", "retryResumeOrBackfillAllowed",
        ):
            self.assertFalse(request[key])
        self.assertTrue(permit["oneUseContract"]["claimCreatedOExcl0600AndFsyncedBeforeDnsOrNetwork"])
        self.assertFalse(permit["authority"]["externalAuthenticationRequired"])
        self.assertFalse(permit["authority"]["sourceExtractionAuthorized"])

    def test_05_caps_modes_and_terminal_order_are_pinned(self):
        permit = C.evaluate(True)[0]["permit"]
        limits = permit["absoluteResourceLimits"]
        self.assertEqual(limits["maximumModResponseBodyBytes"], 1 * 1024 * 1024)
        self.assertEqual(limits["maximumZipResponseBodyBytes"], 16 * 1024 * 1024)
        self.assertEqual(limits["maximumAggregateModResponseBodyBytes"], 8 * 1024 * 1024)
        self.assertEqual(limits["maximumAggregateZipResponseBodyBytes"], 128 * 1024 * 1024)
        self.assertEqual(limits["maximumAggregateResponseBodyBytes"], 128 * 1024 * 1024)
        self.assertEqual(limits["perRequestDeadlineMilliseconds"], 30_000)
        self.assertEqual(limits["wholeAttemptDeadlineMilliseconds"], 600_000)
        self.assertEqual(permit["filesystemAuthority"]["newFileMode"], "0600")
        self.assertEqual(permit["filesystemAuthority"]["newDirectoryMode"], "0700")
        self.assertTrue(permit["terminalContract"]["manifestWrittenLast"])
        self.assertTrue(permit["terminalContract"]["failurePublishesFailureOnly"])

    def test_06_runner_normalization_and_reverse_pin_are_exact(self):
        runner = C.stable_read(C.RUNNER_PATH)
        checker = C.stable_read(C.THIS_CHECKER_PATH)
        C.validate_runner(runner, checker)
        self.assertEqual(hashlib.sha256(C.normalized_runner(runner)).hexdigest(), C.EXPECTED_RUNNER_NORMALIZED_SHA256)

    def test_07_resource_order_authority_and_cap_mutations_differ(self):
        values, _ = C.evaluate(True)
        decision = values["decision"]
        permit = values["permit"]
        mutations = []
        changed = copy.deepcopy(decision)
        changed["requestSet"]["resources"][0], changed["requestSet"]["resources"][1] = changed["requestSet"]["resources"][1], changed["requestSet"]["resources"][0]
        mutations.append((decision, changed))
        changed = copy.deepcopy(permit)
        changed["requestContract"]["redirectAllowed"] = True
        mutations.append((permit, changed))
        changed = copy.deepcopy(permit)
        changed["absoluteResourceLimits"]["maximumZipResponseBodyBytes"] += 1
        mutations.append((permit, changed))
        for original, changed in mutations:
            self.assertNotEqual(C.canonical_bytes(original), C.canonical_bytes(changed))
            self.assertNotEqual(
                hashlib.sha256(C.canonical_bytes(original)).hexdigest(),
                hashlib.sha256(C.canonical_bytes(changed)).hexdigest(),
            )

    def test_08_json_is_canonical_and_strict(self):
        values, _ = C.evaluate(True)
        for name in ("decision", "permit"):
            raw = C.canonical_bytes(values[name])
            self.assertEqual(C.strict_json(raw), values[name])
            self.assertTrue(raw.endswith(b"\n"))
        with self.assertRaises(C.CheckError):
            C.strict_json(b'{"a":1,"a":2}\n')
        self.assertNotEqual(type(True), type(1))

    def test_09_checker_has_no_network_or_process_surface(self):
        tree = ast.parse(SOURCE)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        self.assertFalse({"http.client", "socket", "ssl", "requests"} & imports)


if __name__ == "__main__":
    unittest.main(verbosity=2)
