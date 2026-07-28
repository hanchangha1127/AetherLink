#!/usr/bin/env python3
"""Tests for the Wave19 acquisition readback permit package."""

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
import errno
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import unittest
from unittest import mock
import unicodedata


NETWORK_ATTEMPTS: list[str] = []


def _deny_test_network(*_args, **_kwargs):
    NETWORK_ATTEMPTS.append("network")
    raise AssertionError(
        "offline Wave19 readback tests must never create network connections"
    )


http.client.HTTPSConnection = _deny_test_network
socket.create_connection = _deny_test_network


PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_wave19_"
    "readback_execution_permit_v1.py"
)
PRELOAD_ROOT = Path(__file__).resolve().parents[1]
PRELOAD_PERMIT_PATH = (
    PRELOAD_ROOT
    / "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave19-"
    "readback-execution-permit-v1.json"
)
PRELOAD_TOOL_PATHS = [
    (
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_"
        "readback_execution_permit_v1.py"
    ),
    (
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave19_"
        "readback_execution_permit_v1.py"
    ),
    (
        "script/record_p2p_nat_g2_pion_rung3_dependency_wave19_"
        "readback_v1_once.py"
    ),
    (
        "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave19_"
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


def _require_subject_raw_seal(
    permit: dict[str, object],
    subject_path: str,
    subject_raw: bytes,
) -> None:
    tools = permit["toolBindings"]
    matches = [row for row in tools if row["path"] == subject_path]
    if (
        len(matches) != 1
        or matches[0]["rawSha256"]
        != hashlib.sha256(subject_raw).hexdigest()
    ):
        raise AssertionError("checker preload raw seal mismatch")


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


CHECKER_CALL_SURFACE_SHA256 = (
    "c3c8dee10b79eb96bad28cf378f55ff14107db220e79a08dc6924ec0740c8ea1"
)


def _require_call_surface(raw: bytes, expected_digest: str) -> dict[str, int]:
    calls, digest = _canonical_call_surface(raw)
    if digest != expected_digest:
        raise AssertionError("canonical AST call-surface digest mismatch")
    return calls


def _checker_ast_gate(raw: bytes) -> bytes:
    tree = ast.parse(raw.decode("utf-8", errors="strict"))
    imports: list[str] = []
    calls = _require_call_surface(raw, CHECKER_CALL_SURFACE_SHA256)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    expected_imports = {
        "__future__",
        "sys",
        "argparse",
        "ast",
        "errno",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "re",
        "signal",
        "stat",
        "typing",
        "unicodedata",
    }
    if len(imports) != len(expected_imports) or set(imports) != expected_imports:
        raise AssertionError("checker preload import gate failed")
    exact_calls = {
        "validate_recorder": 1,
        "expected_payload_from_package": 1,
        "stable_read": 1,
        "verify_bound": 2,
        "audit_frozen_snapshot": 1,
        "readback_namespace_absent": 2,
        "package_preflight_for_recorder": 1,
    }
    if any(calls.get(name, 0) != count for name, count in exact_calls.items()):
        raise AssertionError("checker preload exact call gate failed")
    forbidden_fragments = (
        "input",
        "getpass",
        "socket",
        "subprocess",
        "urlopen",
        "HTTPConnection",
        "HTTPSConnection",
        "create_connection",
        "check_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition",
        "acquire_p2p_nat_g2_pion_rung3_dependency_wave19",
    )
    if any(
        any(fragment in name for fragment in forbidden_fragments)
        for name in calls
    ):
        raise AssertionError("checker preload forbidden call gate failed")
    normalized, substitutions = re.subn(
        (
            rb'EXPECTED_RECORDER_NORMALIZED_SHA256 = \(\n'
            rb'    "[0-9a-f]{64}"\n'
            rb'\)'
        ),
        (
            b'EXPECTED_RECORDER_NORMALIZED_SHA256 = (\n'
            + b'    "'
            + (b"0" * 64)
            + b'"\n)'
        ),
        raw,
        count=1,
    )
    if substitutions != 1:
        raise AssertionError("checker preload normalization gate failed")
    return normalized


def _preload_checker_gate(
    path: Path,
) -> tuple[bytes, bytes, dict[str, object]]:
    raw = path.read_bytes()
    normalized = _checker_ast_gate(raw)
    permit = _strict_canonical_permit(PRELOAD_PERMIT_PATH.read_bytes())
    _require_subject_raw_seal(permit, PRELOAD_TOOL_PATHS[0], raw)
    return raw, normalized, permit


(
    CHECKER_PRELOAD_RAW,
    CHECKER_PRELOAD_NORMALIZED,
    CHECKER_PRELOAD_PERMIT,
) = _preload_checker_gate(PATH)
SPEC = importlib.util.spec_from_file_location("wave19_readback_permit_tests", PATH)
C = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(C)
if PATH.read_bytes() != CHECKER_PRELOAD_RAW:
    raise AssertionError("checker changed between preload gate and exec")


def _synthetic_package_raw() -> tuple[dict[str, bytes], str, str]:
    checker_raw = (C.ROOT / C.THIS_CHECKER_PATH).read_bytes()
    reverse_pin = hashlib.sha256(checker_raw).hexdigest()
    recorder_raw = (C.ROOT / C.RECORDER_PATH).read_bytes()
    recorder_raw, substitutions = re.subn(
        (
            rb'EXPECTED_READBACK_CHECKER_RAW = "'
            rb'[0-9a-f]{64}"'
        ),
        (
            b'EXPECTED_READBACK_CHECKER_RAW = "'
            + reverse_pin.encode()
            + b'"'
        ),
        recorder_raw,
        count=1,
    )
    if substitutions != 1:
        raise AssertionError("recorder reverse-pin assignment must be unique")
    reader_raw = b"synthetic Wave19 readback reader\\n"
    raw = {
        C.READER_PATH: reader_raw,
        C.THIS_CHECKER_PATH: checker_raw,
        C.THIS_TESTS_PATH:
            (C.ROOT / C.THIS_TESTS_PATH).read_bytes(),
        C.RECORDER_PATH: recorder_raw,
        C.RECORDER_TESTS_PATH: b"synthetic recorder tests\\n",
    }
    return (
        raw,
        hashlib.sha256(reader_raw).hexdigest(),
        hashlib.sha256(C.normalized_recorder(recorder_raw)).hexdigest(),
    )


def _synthetic_permit() -> tuple[dict[str, object], dict[str, bytes]]:
    raw, reader_digest, recorder_digest = _synthetic_package_raw()
    with (
        mock.patch.object(C, "EXPECTED_READER_RAW", reader_digest),
        mock.patch.object(
            C,
            "EXPECTED_RECORDER_NORMALIZED_SHA256",
            recorder_digest,
        ),
    ):
        permit = C.content_bound(C.expected_payload_from_package(raw))
    return permit, raw


class Wave19ReadbackPermitTests(unittest.TestCase):
    def tearDown(self) -> None:
        self.assertEqual(NETWORK_ATTEMPTS, [])

    def test_01_frozen_snapshot_constants_are_exact(self):
        self.assertEqual(C.ATTEMPT_ID, "f10c20196d994afe3a8eba830eb42614")
        self.assertEqual(
            C.READBACK_CLAIM_PATH,
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-19-v1-readback.claim"
            ),
        )
        self.assertEqual(
            C.ACQUISITION_CLAIM_PATH,
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-19-v1.claim"
            ),
        )
        self.assertNotEqual(
            C.READBACK_CLAIM_PATH,
            C.ACQUISITION_CLAIM_PATH,
        )
        self.assertEqual(C.FINAL_DIRECTORY["linkCount"], 4)
        self.assertEqual(C.FINAL_DIRECTORY["exactEntries"], [
            "accepted",
            "evidence.json",
        ])
        self.assertEqual(C.ACCEPTED_DIRECTORY["linkCount"], 6)
        self.assertEqual(C.ACCEPTED_DIRECTORY["exactFileCount"], 4)
        self.assertEqual(len(C.ACQUISITION_AUTHORITY), 15)
        self.assertEqual(len(C.ACCEPTED_FILES), 4)
        self.assertEqual(
            sum(row["bytes"] for row in C.ACCEPTED_FILES),
            11_453_955,
        )
        self.assertEqual(
            sum(
                row["bytes"]
                for row in C.ACCEPTED_FILES
                if Path(row["path"]).suffix == ".mod"
            ),
            415,
        )
        self.assertEqual(
            sum(
                row["bytes"]
                for row in C.ACCEPTED_FILES
                if Path(row["path"]).suffix == ".zip"
            ),
            11_453_540,
        )
        self.assertEqual(
            [Path(row["path"]).suffix for row in C.ACCEPTED_FILES],
            [".mod", ".zip", ".mod", ".zip"],
        )
        self.assertEqual(
            [Path(row["path"]).name for row in C.ACCEPTED_FILES],
            [
                "001-a26a2513c9f4c49c479c.mod",
                "001-a26a2513c9f4c49c479c.zip",
                "002-c6022d5be99f60f2428e.mod",
                "002-c6022d5be99f60f2428e.zip",
            ],
        )
        acquisition_permit_path = (
            f"{C.BASE}/bounded-dependency-source-acquisition-wave19-"
            "execution-permit-v1.json"
        )
        acquisition_permit = C.strict_json(
            C.stable_read(acquisition_permit_path)
        )
        resources = acquisition_permit["requestContract"]["resources"]
        modules = [row["module"] for row in resources]
        expected_modules = [
            "golang.org/x/crypto",
            "golang.org/x/text",
        ]
        self.assertEqual(
            modules,
            [module for module in expected_modules for _ in range(2)],
        )
        self.assertEqual(
            {row["module"] for row in resources},
            set(expected_modules),
        )
        payload = C.frozen_snapshot_payload()
        self.assertEqual(payload["frozenFileCount"], 23)
        self.assertEqual(
            payload["frozenFilesCanonicalSha256"],
            "a95ea05b73ce1b4c8f4781eb313f2a58071f288c7872a203bfd58bacc3ed68b1",
        )
        self.assertEqual(payload["selectedTupleCount"], 0)
        self.assertEqual(payload["selectedRequestOrdinals"], [])
        self.assertEqual(payload["aggregateZipEntryCount"], 931)
        self.assertEqual(
            payload["aggregateZipUncompressedBytes"],
            46_404_827,
        )
        self.assertEqual(
            payload["acceptedResourceHashSetCanonicalSha256"],
            "a98db8197e88a28464082ef00a9700550652f46e3026993dd3adddcda50280d0",
        )
        authority_paths = {
            row["path"] for row in C.ACQUISITION_AUTHORITY
        }
        self.assertIn(
            "script/check_p2p_nat_g2_pion_combined_fixed_point_v17.py",
            authority_paths,
        )
        self.assertIn(
            "script/test_p2p_nat_g2_pion_combined_fixed_point_v17.py",
            authority_paths,
        )
        self.assertIn(
            (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-18-v1.claim"
            ),
            authority_paths,
        )
        v17 = acquisition_permit["predecessorBindings"][
            "combinedFixedPointV17"
        ]
        bound_authority_rows = [
            *acquisition_permit["decisionBinding"]["files"],
            {
                "path": v17["checkerPath"],
                "rawSha256": v17["checkerRawSha256"],
            },
            {
                "path": v17["testsPath"],
                "rawSha256": v17["testsRawSha256"],
            },
            v17["wave18NamespaceAnchor"],
            acquisition_permit["readerDocumentBinding"],
            *acquisition_permit["toolBindings"],
            *acquisition_permit["primitiveBindings"],
        ]
        self.assertEqual(len(bound_authority_rows), 14)
        self.assertEqual(
            {row["path"] for row in bound_authority_rows},
            authority_paths - {acquisition_permit_path},
        )
        self.assertFalse(
            any("_candidate_v1.py" in path for path in authority_paths)
        )
        self.assertEqual(
            payload["identityBindings"]["resourcesCanonicalSha256"],
            C.EXPECTED_RESOURCES_CANONICAL,
        )
        self.assertEqual(
            payload["predecessorBindings"]["combinedFixedPointV17"][
                "contentSha256"
            ],
            C.EXPECTED_V17_CONTENT,
        )
        self.assertFalse(
            any(
                "combined_fixed_point_v" + "10.py" in path
                for path in authority_paths
            )
        )

    def test_02_live_frozen_bytes_modes_and_inventory_validate(self):
        C.audit_frozen_snapshot()

    def test_03_materialized_package_is_sealed_and_exact(self):
        permit_path = C.ROOT / C.PERMIT_PATH
        if not C.is_sealed():
            self.assertEqual(
                C.EXPECTED_READER_RAW,
                C.sha256((C.ROOT / C.READER_PATH).read_bytes()),
            )
            self.assertEqual(
                C.EXPECTED_RECORDER_NORMALIZED_SHA256,
                C.PLACEHOLDER_SHA256,
            )
            self.assertFalse(permit_path.exists())
            return
        if not permit_path.exists():
            self.assertEqual(
                C.EXPECTED_READER_RAW,
                C.sha256((C.ROOT / C.READER_PATH).read_bytes()),
            )
            self.assertEqual(
                C.EXPECTED_RECORDER_NORMALIZED_SHA256,
                C.sha256(
                    C.normalized_recorder(
                        (C.ROOT / C.RECORDER_PATH).read_bytes()
                    )
                ),
            )
            return
        self.assertEqual(
            C.EXPECTED_READER_RAW,
            C.sha256((C.ROOT / C.READER_PATH).read_bytes()),
        )
        self.assertEqual(
            C.EXPECTED_RECORDER_NORMALIZED_SHA256,
            C.sha256(
                C.normalized_recorder(
                    (C.ROOT / C.RECORDER_PATH).read_bytes()
                )
            ),
        )
        permit, summary = C.evaluate(True)
        permit_raw = permit_path.read_bytes()
        self.assertEqual(permit_raw, C.canonical_bytes(permit))
        self.assertEqual(C.strict_json(permit_raw), permit)
        self.assertTrue(summary["validationPassed"])
        self.assertTrue(summary["frozenSnapshotVerified"])
        preflight = C.package_preflight_for_recorder()
        self.assertEqual(
            preflight["permitRawSha256"],
            C.sha256(permit_raw),
        )
        self.assertFalse(preflight["frozenAcquisitionInputOpened"])
        self.assertEqual(preflight["networkRequestAttemptCount"], 0)
        self.assertEqual(C.readback_namespace_state(), "absent")
        self.assertFalse(os.path.lexists(C.ROOT / C.READBACK_CLAIM_PATH))

    def test_04_synthetic_permit_is_strict_canonical_and_content_bound(self):
        permit, _ = _synthetic_permit()
        raw = C.canonical_bytes(permit)
        value = C.strict_json(raw)
        self.assertEqual(raw, C.canonical_bytes(value))
        C.verify_bound(raw, value)

    def test_05_authority_is_offline_and_authentication_free(self):
        permit, _ = _synthetic_permit()
        authority = permit["authority"]
        self.assertTrue(authority["offlineReadbackAuthorizedOnce"])
        package_paths = [
            permit["readerDocumentBinding"]["path"],
            *(row["path"] for row in permit["toolBindings"]),
        ]
        self.assertEqual(len(package_paths), 5)
        self.assertEqual(len(set(package_paths)), 5)
        self.assertEqual(
            set(package_paths),
            {
                C.READER_PATH,
                C.THIS_CHECKER_PATH,
                C.THIS_TESTS_PATH,
                C.RECORDER_PATH,
                C.RECORDER_TESTS_PATH,
            },
        )
        interpreter = permit["interpreterContract"]
        self.assertEqual(
            interpreter["command"],
            [
                "python3",
                "-I",
                "-B",
                "-S",
                C.RECORDER_PATH,
                "--execute",
            ],
        )
        self.assertEqual(
            interpreter["productionExactArgv"],
            ["--execute"],
        )
        self.assertEqual(
            interpreter["readOnlyPreflightExactArgv"],
            ["--preflight"],
        )
        for key in (
            "additionalArgumentsAllowed",
            "duplicateArgumentsAllowed",
            "abbreviatedArgumentsAllowed",
        ):
            self.assertIs(interpreter[key], False, key)
        verification = permit["verificationContract"]
        self.assertEqual(verification["completeVerificationPassCount"], 2)
        self.assertEqual(verification["retainedFdPreManifestBarrierCount"], 3)
        self.assertEqual(
            verification["retainedFdPreManifestBarriers"],
            [
                "complete_snapshot_and_claim_immediately_before_receipt",
                "complete_snapshot_claim_and_receipt_after_receipt",
                (
                    "complete_snapshot_claim_and_receipt_"
                    "immediately_before_manifest_publication"
                ),
            ],
        )
        self.assertTrue(
            verification[
                "allRequiredPreManifestBarriersCompleteImmediatelyBeforeManifestPublication"
            ]
        )
        self.assertFalse(
            verification["requiredFallibleBarrierAfterManifest"]
        )
        self.assertTrue(
            verification[
                "claimCreationFdHeldAtImmediatelyBeforeManifestBarrier"
            ]
        )
        self.assertTrue(verification["completionAppliesToRetainedSnapshot"])
        self.assertFalse(
            verification[
                "currentPathIdentityGuaranteedThroughManifestPublication"
            ]
        )
        self.assertFalse(
            verification[
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ]
        )
        self.assertTrue(
            verification[
                "executeSuccessRecordedBeforeStdoutReporting"
            ]
        )
        self.assertEqual(
            verification["postSuccessReportingFailure"],
            {
                "status": "consumed_success_reporting_failed",
                "failureCode": "E_POST_SUCCESS_REPORTING",
                "failurePhase": "reporting",
                "retryAllowed": False,
                "readbackPublicationComplete": True,
                "completionAppliesToRetainedSnapshot": True,
            },
        )
        for removed in (
            "readbackClaimHeldThroughManifestPublication",
            "claimCreationFdContinuouslyHeldThroughManifestPublication",
            "readbackReceiptHeldThroughManifestPublication",
        ):
            self.assertNotIn(removed, verification)
        output = permit["outputContract"]
        self.assertTrue(output["completionAppliesToRetainedSnapshot"])
        self.assertFalse(
            output["currentPathIdentityGuaranteedThroughManifestPublication"]
        )
        self.assertFalse(
            output[
                "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
            ]
        )
        self.assertTrue(
            output["executeSuccessRecordedBeforeStdoutReporting"]
        )
        self.assertEqual(
            output["postSuccessReportingFailureStatus"],
            "consumed_success_reporting_failed",
        )
        self.assertEqual(
            permit["outputContract"]["publicationOrder"],
            [
                "rename_no_replace",
                "parent_directory_fsync",
                "final_name_no_follow_reopen_and_source_inode_verification",
                "return",
            ],
        )
        for key in (
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
        ):
            self.assertFalse(authority[key], key)

    def test_06_recorder_cycle_and_independence_are_exact(self):
        raw, reader_digest, recorder_digest = _synthetic_package_raw()
        with (
            mock.patch.object(C, "EXPECTED_READER_RAW", reader_digest),
            mock.patch.object(
                C,
                "EXPECTED_RECORDER_NORMALIZED_SHA256",
                recorder_digest,
            ),
        ):
            C.validate_recorder(
                raw[C.RECORDER_PATH],
                raw[C.THIS_CHECKER_PATH],
            )
        source = raw[C.RECORDER_PATH].decode()
        self.assertNotIn("importlib", source)
        self.assertNotIn("subprocess", source)
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertFalse(
            imports.intersection({"http", "socket", "ssl", "urllib", "requests"})
        )

    def test_06_full_ast_call_surfaces_reject_same_count_bypasses(self):
        preload_mutations = (
            (
                "constant",
                b'ATTEMPT_ID = "f10c20196d994afe3a8eba830eb42614"',
                b'ATTEMPT_ID = "e10c20196d994afe3a8eba830eb42614"',
            ),
            (
                "branch",
                b"        if args.package_only:\n",
                b"        if not args.package_only:\n",
            ),
            (
                "argument",
                (
                    b'        group.add_argument("--package-only", '
                    b'action="store_true")'
                ),
                (
                    b'        group.add_argument("--package-only-drift", '
                    b'action="store_true")'
                ),
            ),
        )
        for label, old, new in preload_mutations:
            changed = CHECKER_PRELOAD_RAW.replace(old, new, 1)
            with self.subTest(preload_raw_mutation=label):
                self.assertNotEqual(changed, CHECKER_PRELOAD_RAW)
                _checker_ast_gate(changed)
                with self.assertRaises(AssertionError):
                    _require_subject_raw_seal(
                        CHECKER_PRELOAD_PERMIT,
                        PRELOAD_TOOL_PATHS[0],
                        changed,
                    )

        checker_raw = CHECKER_PRELOAD_RAW
        checker_mutated = checker_raw.replace(
            b"        audit_frozen_snapshot()\n",
            b"        input()\n",
            1,
        )
        self.assertNotEqual(checker_mutated, checker_raw)
        original_calls, original_digest = _canonical_call_surface(checker_raw)
        changed_calls, changed_digest = _canonical_call_surface(checker_mutated)
        self.assertEqual(sum(original_calls.values()), sum(changed_calls.values()))
        self.assertEqual(original_digest, CHECKER_CALL_SURFACE_SHA256)
        self.assertNotEqual(changed_digest, original_digest)
        with self.assertRaises(AssertionError):
            _require_call_surface(
                checker_mutated,
                CHECKER_CALL_SURFACE_SHA256,
            )

        raw, reader_digest, recorder_digest = _synthetic_package_raw()
        recorder_raw = raw[C.RECORDER_PATH]
        recorder_mutations = (
            recorder_raw.replace(b"bool(chunk)", b"input()", 1),
            recorder_raw.replace(
                b"bool(chunk)",
                (
                    b"acquire_p2p_nat_g2_pion_rung3_dependency_"
                    b"wave19_v1_once()"
                ),
                1,
            ),
            recorder_raw.replace(
                b"bool(chunk)",
                (
                    b"check_p2p_nat_g2_pion_rung3_dependency_"
                    b"wave19_acquisition_v1()"
                ),
                1,
            ),
            recorder_raw.replace(
                b"first = verify_snapshot(snapshot)",
                b"first = validate_zip(snapshot)",
                1,
            ),
        )
        original_calls, original_digest = _canonical_call_surface(recorder_raw)
        self.assertEqual(
            original_digest,
            C.EXPECTED_RECORDER_AST_CALL_SURFACE_SHA256,
        )
        for changed in recorder_mutations:
            with self.subTest(mutation=changed[:80]):
                self.assertNotEqual(changed, recorder_raw)
                changed_calls, changed_digest = _canonical_call_surface(changed)
                self.assertEqual(
                    sum(original_calls.values()),
                    sum(changed_calls.values()),
                )
                self.assertNotEqual(changed_digest, original_digest)
                with (
                    mock.patch.object(
                        C,
                        "EXPECTED_READER_RAW",
                        reader_digest,
                    ),
                    mock.patch.object(
                        C,
                        "EXPECTED_RECORDER_NORMALIZED_SHA256",
                        hashlib.sha256(
                            C.normalized_recorder(changed)
                        ).hexdigest(),
                    ),
                    self.assertRaises(C.PermitError) as caught,
                ):
                    C.validate_recorder(
                        changed,
                        raw[C.THIS_CHECKER_PATH],
                    )
                self.assertEqual(caught.exception.code, "E_RECORDER")

    def test_07_claim_precedes_snapshot_open_in_execute_source(self):
        recorder = C.ROOT / C.RECORDER_PATH
        if not recorder.exists():
            self.assertFalse(C.is_sealed())
            return
        source = recorder.read_text()
        claim = source.index(
            "claim, claim_creation_fd = create_readback_claim("
        )
        snapshot = source.index("snapshot = snapshot_factory(root)")
        self.assertLess(claim, snapshot)
        self.assertLess(
            source.index("namespace.hold_claim(claim, claim_creation_fd)"),
            snapshot,
        )
        self.assertIn("first = verify_snapshot(snapshot)", source)
        self.assertIn("second = verify_snapshot(snapshot)", source)

    def test_08_contract_mutations_are_rebound_and_rejected(self):
        original, _ = _synthetic_permit()
        for mutation in (
            "attempt",
            "aggregate",
            "authority",
            "claim",
            "permit_extra",
            "authority_extra",
            "authority_bool_int",
            "count_bool_int",
        ):
            changed = copy.deepcopy(original)
            if mutation == "attempt":
                changed["frozenAcquisitionSnapshot"]["attemptId"] = (
                    "fff8d6073748eab6fd1a05c79c57a84f"
                )
            elif mutation == "aggregate":
                changed["frozenAcquisitionSnapshot"]["aggregateAcceptedBytes"] += 1
            elif mutation == "authority":
                changed["authority"]["networkAuthorized"] = True
            elif mutation == "claim":
                changed["oneUseConsumption"]["claimPath"] += ".other"
            elif mutation == "permit_extra":
                changed["unknown"] = False
            elif mutation == "authority_extra":
                changed["authority"]["unknown"] = False
            elif mutation == "authority_bool_int":
                changed["authority"]["networkAuthorized"] = 0
            else:
                changed["frozenAcquisitionSnapshot"]["frozenFileCount"] = True
            changed.pop("contentBinding")
            rebound = C.content_bound(changed)
            with self.assertRaises(C.PermitError) as caught:
                C.verify_bound(C.canonical_bytes(rebound), original)
            self.assertEqual(caught.exception.code, "E_PERMIT")

    def test_08_wave19_cardinality_hash_aggregate_and_limit_drift_rejects(self):
        original, _ = _synthetic_permit()
        snapshot = original["frozenAcquisitionSnapshot"]

        def stale_wave18_frozen_25(value):
            value["frozenAcquisitionSnapshot"]["frozenFileCount"] = 25

        def authority_14(value):
            authority = value["frozenAcquisitionSnapshot"][
                "acquisitionAuthority"
            ]
            value["frozenAcquisitionSnapshot"]["acquisitionAuthority"] = [
                row
                for row in authority
                if not row["path"].endswith("/.wave-18-v1.claim")
            ]

        def bound_rows_14(value):
            predecessor = value["frozenAcquisitionSnapshot"][
                "predecessorBindings"
            ]["combinedFixedPointV17"]
            predecessor.pop("wave18NamespaceAnchor")

        def predecessor_v16(value):
            predecessors = value["frozenAcquisitionSnapshot"][
                "predecessorBindings"
            ]
            predecessors["combinedFixedPointV16"] = predecessors.pop(
                "combinedFixedPointV17"
            )

        def stale_wave18_aggregates(value):
            value["frozenAcquisitionSnapshot"].update(
                {
                    "aggregateModBytes": 279,
                    "aggregateZipBytes": 2_108_821,
                    "aggregateAcceptedBytes": 2_109_100,
                    "aggregateZipEntryCount": 971,
                    "aggregateZipUncompressedBytes": 7_225_800,
                }
            )

        def stale_wave18_hashes(value):
            value["frozenAcquisitionSnapshot"].update(
                {
                    "frozenFilesCanonicalSha256": (
                        "59595e842e331a333c74f688d57198546"
                        "ca8aad7347976a20906afc8df6161f4"
                    ),
                    "acceptedResourceHashSetCanonicalSha256": (
                        "757651958dc0538863d7654d59df95a4"
                        "171cf44fccfa726da87fb0fdf5babc0f"
                    ),
                }
            )

        def stale_wave18_limits(value):
            value["resourceLimits"].update(
                {
                    "maximumAcceptedResourceCount": 6,
                    "maximumAggregateModBytes": 3 * 1024 * 1024,
                    "maximumAggregateZipBytes": 48 * 1024 * 1024,
                    "maximumAggregateAcceptedBytes": 51 * 1024 * 1024,
                    "maximumZipEntriesAcrossAll": 60_000,
                    "maximumZipUncompressedBytesAcrossAll":
                        384 * 1024 * 1024,
                }
            )

        self.assertEqual(snapshot["frozenFileCount"], 23)
        self.assertEqual(len(snapshot["acquisitionAuthority"]), 15)
        for mutation in (
            stale_wave18_frozen_25,
            authority_14,
            bound_rows_14,
            predecessor_v16,
            stale_wave18_aggregates,
            stale_wave18_hashes,
            stale_wave18_limits,
        ):
            changed = copy.deepcopy(original)
            mutation(changed)
            changed.pop("contentBinding")
            rebound = C.content_bound(changed)
            with self.assertRaises(C.PermitError) as caught:
                C.verify_bound(C.canonical_bytes(rebound), original)
            self.assertEqual(caught.exception.code, "E_PERMIT")
        package_paths = (
            C.THIS_CHECKER_PATH,
            C.RECORDER_PATH,
            C.READER_PATH,
            C.PERMIT_PATH,
        )
        for package_path in package_paths:
            path = C.ROOT / package_path
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("golang.org/x/" + "mod", source)
            self.assertNotIn("golang.org/x/" + "net", source)
            self.assertNotIn("golang.org/x/" + "sync", source)
        for production_path in (
            C.THIS_CHECKER_PATH,
            C.RECORDER_PATH,
            C.READER_PATH,
            C.PERMIT_PATH,
        ):
            path = C.ROOT / production_path
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("combinedFixedPointV" + "16", source)

    def test_09_broken_symlink_occupies_readback_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / C.READBACK_CLAIM_PATH
            target.parent.mkdir(parents=True)
            (root / C.BASE).mkdir(parents=True)
            target.symlink_to(root / "missing")
            with self.assertRaises(C.PermitError) as caught:
                C.readback_namespace_absent(root)
            self.assertEqual(caught.exception.code, "E_CONSUMED")

    def test_10_frozen_file_aggregate_binding_is_reproducible(self):
        payload = C.frozen_snapshot_payload()
        frozen = [
            *C.ACQUISITION_AUTHORITY,
            C.ACQUISITION_CLAIM,
            C.EVIDENCE_FILE,
            *C.ACCEPTED_FILES,
            C.ACQUISITION_RECEIPT,
            C.ACQUISITION_MANIFEST,
        ]
        self.assertEqual(
            payload["frozenFilesCanonicalSha256"],
            hashlib.sha256(C.canonical_bytes(frozen)).hexdigest(),
        )

    def test_11_invalid_cli_fails_closed_without_write_authority(self):
        with self.assertRaises(C.PermitError):
            C.Parser(add_help=False).parse_args(["--unknown"])
        self.assertFalse(os.path.lexists(C.ROOT / C.READBACK_CLAIM_PATH))

    def test_12_namespace_states_and_stale_temporary_names_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claim = root / C.READBACK_CLAIM_PATH
            receipt = root / C.READBACK_RECEIPT_PATH
            manifest = root / C.READBACK_MANIFEST_PATH
            claim.parent.mkdir(parents=True)
            receipt.parent.mkdir(parents=True)

            def clear():
                for path in (claim, receipt, manifest):
                    path.unlink(missing_ok=True)
                for child in receipt.parent.iterdir():
                    if C.has_portable_prefix(
                        [child.name],
                        C.READBACK_TEMP_PREFIXES,
                    ):
                        child.unlink()

            self.assertEqual(C.readback_namespace_state(root), "absent")
            for expected, occupied in (
                ("claim_only", (claim,)),
                ("receipt_only", (claim, receipt)),
                ("complete", (claim, receipt, manifest)),
                ("inconsistent", (receipt,)),
            ):
                clear()
                for path in occupied:
                    path.write_bytes(b"x")
                self.assertEqual(C.readback_namespace_state(root), expected)
                with self.assertRaises(C.PermitError) as caught:
                    C.readback_namespace_absent(root)
                self.assertEqual(caught.exception.code, "E_CONSUMED")
                self.assertEqual(caught.exception.state, expected)

            clear()
            for prefix in C.READBACK_TEMP_PREFIXES:
                stale = receipt.parent / (prefix + "stale")
                stale.symlink_to(root / "missing")
                self.assertEqual(
                    C.readback_namespace_state(root),
                    "stale_temporary_namespace",
                )
                with self.assertRaises(C.PermitError) as caught:
                    C.readback_namespace_absent(root)
                self.assertEqual(
                    caught.exception.state,
                    "stale_temporary_namespace",
                )
                stale.unlink()

                nfd = (
                    prefix.upper()
                    + unicodedata.normalize("NFD", "é")
                )
                nfc = (
                    prefix.upper()
                    + unicodedata.normalize("NFC", "é")
                )
                self.assertEqual(
                    C.portable_name(nfd),
                    C.portable_name(nfc),
                )
                self.assertTrue(
                    C.has_portable_prefix(
                        [C.STAGING_PREFIX.upper() + nfd[-2:]],
                        [C.STAGING_PREFIX],
                    )
                )
                for variant in (nfd, nfc):
                    candidate = receipt.parent / variant
                    candidate.symlink_to(root / "missing")
                    self.assertEqual(
                        C.readback_namespace_state(root),
                        "stale_temporary_namespace",
                    )
                    candidate.unlink()

    def test_13_intermediate_component_replacement_fails_barrier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "a" / "b"
            nested.mkdir(parents=True, mode=0o700)
            traversal = C.HeldTraversal(root)
            try:
                traversal.directory("a/b")
                (root / "a").rename(root / "old-a")
                (root / "a" / "b").mkdir(parents=True, mode=0o700)
                with self.assertRaises(C.PermitError) as caught:
                    traversal.barrier()
                self.assertEqual(caught.exception.code, "E_PATH")
            finally:
                traversal.close()

    def test_14_partial_component_open_and_restore_error_close_all_fds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a" / "b").mkdir(parents=True, mode=0o700)
            before = len(os.listdir("/dev/fd"))
            traversal = C.HeldTraversal(root)
            original = traversal._validate_directory
            calls = 0

            def reject_second(info):
                nonlocal calls
                calls += 1
                original(info)
                if calls == 2:
                    raise C.PermitError("E_SYNTHETIC")

            try:
                with mock.patch.object(
                    traversal,
                    "_validate_directory",
                    side_effect=reject_second,
                ):
                    with self.assertRaises(C.PermitError):
                        traversal.directory("a/b")
            finally:
                traversal.close()
            self.assertEqual(len(os.listdir("/dev/fd")), before)

            traversal = C.HeldTraversal(root)
            traversal.directory("a/b")
            owned = tuple(traversal.owned)
            real_mask = C.signal.pthread_sigmask

            def restore_then_raise(how, mask):
                result = real_mask(how, mask)
                if how == C.signal.SIG_SETMASK:
                    raise RuntimeError("synthetic restore error")
                return result

            with mock.patch.object(
                C.signal,
                "pthread_sigmask",
                side_effect=restore_then_raise,
            ):
                with self.assertRaises(RuntimeError):
                    traversal.close()
            for fd in owned:
                with self.assertRaises(OSError):
                    os.fstat(fd)

    def test_15_close_retains_observably_open_fd_and_is_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traversal = C.HeldTraversal(root)
            root_fd = traversal.root_fd
            real_close = C.os.close

            def refuse_root_close(fd):
                if fd == root_fd:
                    raise OSError(errno.EIO, "synthetic close failure")
                return real_close(fd)

            with mock.patch.object(
                C.os,
                "close",
                side_effect=refuse_root_close,
            ):
                with self.assertRaises(OSError):
                    traversal.close()
            self.assertFalse(traversal.closed)
            self.assertIn(root_fd, traversal.owned)
            os.fstat(root_fd)

            traversal.close()
            self.assertTrue(traversal.closed)
            self.assertEqual(traversal.owned, [])
            with self.assertRaises(OSError):
                os.fstat(root_fd)

    def test_16_claim_observation_survives_traversal_close_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claim = root / C.READBACK_CLAIM_PATH
            claim.parent.mkdir(parents=True, mode=0o700)
            (root / C.BASE).mkdir(parents=True, mode=0o700)
            claim.write_bytes(b"observed")
            real_close = C.HeldTraversal.close

            def close_then_fail(traversal):
                real_close(traversal)
                raise RuntimeError("synthetic traversal cleanup")

            with mock.patch.object(
                C.HeldTraversal,
                "close",
                side_effect=close_then_fail,
                autospec=True,
            ):
                with self.assertRaises(C.PermitError) as caught:
                    C.readback_namespace_state(root)
            self.assertEqual(caught.exception.code, "E_CONSUMED")
            self.assertEqual(caught.exception.state, "claim_only")


if __name__ == "__main__":
    unittest.main(verbosity=2)
