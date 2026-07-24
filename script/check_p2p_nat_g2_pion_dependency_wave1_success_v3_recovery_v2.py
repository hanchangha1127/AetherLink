#!/usr/bin/env python3
"""Versioned recovery reader for the completed dependency-wave-one v3 acquisition.

The consumed v3 permit binds the original independent readback checker byte for
byte, so that checker remains immutable.  Its predecessor parser accidentally
required three already-bound, pretty-printed JSON documents to use the compact
encoding that only their content bindings require.  This recovery reader loads
the original checker by fixed SHA-256 and relaxes raw encoding only for the
three exact predecessor byte strings.  Generated acquisition and readback
artifacts retain the original canonical-JSON checks.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "dependency wave-one v3 recovery reader requires unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3_recovery_v2.py"
)
TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3_recovery_v2.py"
)
ORIGINAL_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
)
ORIGINAL_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3.py"
)
ORIGINAL_CHECKER_RAW_SHA256 = (
    "f3015f91fac37bc6b139b68e7b663780c00b7b208cfecfeff67208f8b57586b6"
)
ORIGINAL_TESTS_RAW_SHA256 = (
    "0c990d98bd7bdb9f62c35a5fbb5a18f0cf4082661e84f5dddfb3aa72dc4c6163"
)
RECOVERY_DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-recovery-decision-v2.json"
)
RECOVERY_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-readback-recovery-decision-v2"
)
MAXIMUM_TOOL_BYTES = 2_097_152
MAXIMUM_JSON_BYTES = 2_097_152

PREDECESSOR_BINDINGS: Mapping[str, Mapping[str, str]] = {
    "source decision": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-three/"
            "bounded-dependency-source-identity-and-acquisition-decision-v1.json"
        ),
        "rawSha256": (
            "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e"
        ),
        "contentSha256": (
            "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201"
        ),
    },
    "recovery decision": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-three/"
            "bounded-dependency-source-acquisition-wave1-recovery-decision-v2.json"
        ),
        "rawSha256": (
            "c03ca34315226ad8a59d8857448657c3be2565b22c0583085eb93c6c65ad72fd"
        ),
        "contentSha256": (
            "5a41d5bcf7dccb25bb5e558d892620748ea72e12e9f90244242ffdb44e092a93"
        ),
    },
    "v3 permit": {
        "path": (
            "docs/security-hardening/production-p2p-nat-v1/"
            "g2-pion-restricted-fork-v1/rung-three/"
            "bounded-dependency-source-acquisition-wave1-execution-permit-v3.json"
        ),
        "rawSha256": (
            "7687dc158ff796f5b1f1423fb7dce208d00ccd2de7d3e9e3b6cd2b7abfc83a40"
        ),
        "contentSha256": (
            "89d6b8eba9e4b94a7ede09cd804d1474b2b13da8aae84cc3b3cdaf9824cf8e7c"
        ),
    },
}

CLAIM_PATH = "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-1-v3.claim"
SUCCESS_RECEIPT_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-receipt-v3.json"
)
ACQUISITION_MANIFEST_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-manifest-v3.json"
)
FINAL_DIRECTORY_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/wave-1-v3/accepted"
)
READBACK_RECEIPT_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-manifest-v1.json"
)
CLAIM_RAW_SHA256 = (
    "0f414c9bc25a15ef55d17c24162868d11210b5add5b969f9cffb277baea715fb"
)
SUCCESS_RECEIPT_RAW_SHA256 = (
    "10d63291813d66c1d7c9edaf7108842113bccbc2a84f799ddafe3f02a820f3b3"
)
ACQUISITION_MANIFEST_RAW_SHA256 = (
    "9763dd83e46a57404bbd3d4c18ecf2f151bdf4e1c17ba3131e4b726b32a54e6b"
)
ORDERED_SOURCE_SET_SHA256 = (
    "2b0176d6d2b800c9a2abd34bf06279403e6f008bd3475ff45970abf11e843246"
)


class RecoveryError(RuntimeError):
    """A closed recovery-reader validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_held(
    root: Path,
    relative: str,
    *,
    maximum_bytes: int,
    owner_only: bool = False,
) -> bytes:
    root_fd = LEGACY.open_root(root)
    held = None
    try:
        held = LEGACY.HeldFile(
            root_fd,
            relative,
            maximum_bytes=maximum_bytes,
            owner_only=owner_only,
        )
        first = held.read_pass()
        second = held.read_pass()
        require(first == second, f"{relative}: unstable bytes")
        held.final_name_barrier()
        return first
    finally:
        if held is not None:
            held.close()
        os.close(root_fd)


def load_original_checker() -> types.ModuleType:
    path = ROOT / ORIGINAL_CHECKER_PATH
    raw = path.read_bytes()
    require(
        len(raw) <= MAXIMUM_TOOL_BYTES
        and sha256_bytes(raw) == ORIGINAL_CHECKER_RAW_SHA256,
        "original readback checker identity mismatch",
    )
    module = types.ModuleType("aetherlink_wave1_v3_immutable_readback_checker")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(path),
            "__loader__": None,
            "__package__": None,
        }
    )
    exec(
        compile(raw, ORIGINAL_CHECKER_PATH, "exec", dont_inherit=True, optimize=0),
        module.__dict__,
        module.__dict__,
    )
    return module


LEGACY = load_original_checker()
ORIGINAL_STRICT_JSON = LEGACY.strict_json


def parse_exact_bound_predecessor(raw: bytes, label: str) -> Any:
    binding = PREDECESSOR_BINDINGS.get(label)
    require(binding is not None, f"{label}: relaxed parser is not authorized")
    require(
        sha256_bytes(raw) == binding["rawSha256"],
        f"{label}: fixed raw SHA-256 mismatch",
    )
    require(
        raw.endswith(b"\n")
        and not raw.endswith(b"\n\n")
        and b"\r" not in raw,
        f"{label}: exact single trailing LF required",
    )

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"{label}: duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                RecoveryError(f"{label}: invalid constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecoveryError(f"{label}: invalid JSON") from error

    def reject_nonfinite(item: Any) -> None:
        if type(item) is float:
            require(math.isfinite(item), f"{label}: non-finite number")
        elif type(item) is list:
            for child in item:
                reject_nonfinite(child)
        elif type(item) is dict:
            for key, child in item.items():
                require(type(key) is str, f"{label}: non-string key")
                reject_nonfinite(child)

    reject_nonfinite(value)
    require(type(value) is dict, f"{label}: object required")
    return value


def corrected_strict_json(raw: bytes, label: str) -> Any:
    if label not in PREDECESSOR_BINDINGS:
        return ORIGINAL_STRICT_JSON(raw, label)
    try:
        return ORIGINAL_STRICT_JSON(raw, label)
    except LEGACY.CheckError:
        return parse_exact_bound_predecessor(raw, label)


LEGACY.strict_json = corrected_strict_json


def expected_recovery_decision(
    checker_raw_sha256: str,
    tests_raw_sha256: str,
) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v3-readback-recovery-decision"
        ),
        "schemaVersion": "2.0",
        "decisionId": RECOVERY_DECISION_ID,
        "recordedDate": "2026-07-24",
        "status": (
            "wave1_v3_acquired_readback_v1_checker_contract_mismatch_"
            "recovery_authorized"
        ),
        "result": (
            "preserve_acquisition_and_use_fixed_raw_sha_guarded_"
            "predecessor_parser"
        ),
        "incident": {
            "failedCheckerPath": ORIGINAL_CHECKER_PATH,
            "failedCheckerRawSha256": ORIGINAL_CHECKER_RAW_SHA256,
            "failedCheckerTestsPath": ORIGINAL_TESTS_PATH,
            "failedCheckerTestsRawSha256": ORIGINAL_TESTS_RAW_SHA256,
            "observedError": "source decision: non-canonical JSON",
            "rootCause": (
                "whole_file_compact_canonical_requirement_exceeded_the_"
                "predecessor_content_binding_contract"
            ),
            "readbackReceiptAbsentAtDecision": True,
            "readbackManifestAbsentAtDecision": True,
        },
        "immutablePredecessorBindings": [
            {
                "label": label,
                "path": binding["path"],
                "rawSha256": binding["rawSha256"],
                "contentSha256": binding["contentSha256"],
            }
            for label, binding in PREDECESSOR_BINDINGS.items()
        ],
        "acquisitionSuccessBindings": {
            "claim": {
                "path": CLAIM_PATH,
                "rawSha256": CLAIM_RAW_SHA256,
            },
            "successReceipt": {
                "path": SUCCESS_RECEIPT_PATH,
                "rawSha256": SUCCESS_RECEIPT_RAW_SHA256,
            },
            "acquisitionManifest": {
                "path": ACQUISITION_MANIFEST_PATH,
                "rawSha256": ACQUISITION_MANIFEST_RAW_SHA256,
            },
            "acceptedDirectoryPath": FINAL_DIRECTORY_PATH,
            "retainedResourceCount": 38,
            "orderedSourceSetSha256": ORDERED_SOURCE_SET_SHA256,
        },
        "selectedRecoveryReader": {
            "checkerPath": SELF_PATH,
            "checkerRawSha256": checker_raw_sha256,
            "checkerTestsPath": TESTS_PATH,
            "checkerTestsRawSha256": tests_raw_sha256,
            "underlyingCheckerPath": ORIGINAL_CHECKER_PATH,
            "underlyingCheckerRawSha256": ORIGINAL_CHECKER_RAW_SHA256,
            "relaxedRawEncodingLabels": list(PREDECESSOR_BINDINGS),
            "fixedRawShaRequired": True,
            "canonicalValidationRetainedForGeneratedArtifacts": True,
            "networkAllowed": False,
            "sourceExtractionAllowed": False,
            "readbackReceiptPath": READBACK_RECEIPT_PATH,
            "readbackManifestPath": READBACK_MANIFEST_PATH,
        },
        "authorization": {
            "recordReadbackAuthorized": True,
            "acquisitionRetryAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "nextAction": (
            "run_versioned_readback_recovery_preflight_then_record_once"
        ),
    }


def validate_recovery_authority(root: Path = ROOT) -> Mapping[str, Any]:
    checker_raw = read_held(
        root, SELF_PATH, maximum_bytes=MAXIMUM_TOOL_BYTES, owner_only=False
    )
    tests_raw = read_held(
        root, TESTS_PATH, maximum_bytes=MAXIMUM_TOOL_BYTES, owner_only=False
    )
    require(
        sha256_bytes(
            read_held(
                root,
                ORIGINAL_CHECKER_PATH,
                maximum_bytes=MAXIMUM_TOOL_BYTES,
                owner_only=False,
            )
        )
        == ORIGINAL_CHECKER_RAW_SHA256,
        "original checker drift",
    )
    require(
        sha256_bytes(
            read_held(
                root,
                ORIGINAL_TESTS_PATH,
                maximum_bytes=MAXIMUM_TOOL_BYTES,
                owner_only=False,
            )
        )
        == ORIGINAL_TESTS_RAW_SHA256,
        "original checker tests drift",
    )
    for label, binding in PREDECESSOR_BINDINGS.items():
        raw = read_held(
            root,
            binding["path"],
            maximum_bytes=MAXIMUM_JSON_BYTES,
            owner_only=False,
        )
        require(
            sha256_bytes(raw) == binding["rawSha256"],
            f"{label}: authority raw SHA-256 mismatch",
        )
    for relative, expected, owner_only in (
        (CLAIM_PATH, CLAIM_RAW_SHA256, True),
        (SUCCESS_RECEIPT_PATH, SUCCESS_RECEIPT_RAW_SHA256, True),
        (
            ACQUISITION_MANIFEST_PATH,
            ACQUISITION_MANIFEST_RAW_SHA256,
            True,
        ),
    ):
        require(
            sha256_bytes(
                read_held(
                    root,
                    relative,
                    maximum_bytes=MAXIMUM_JSON_BYTES,
                    owner_only=owner_only,
                )
            )
            == expected,
            f"{relative}: acquisition binding mismatch",
        )
    decision_raw = read_held(
        root,
        RECOVERY_DECISION_PATH,
        maximum_bytes=MAXIMUM_JSON_BYTES,
        owner_only=False,
    )
    decision = ORIGINAL_STRICT_JSON(decision_raw, "readback recovery decision")
    require(type(decision) is dict, "readback recovery decision: object required")
    expected = expected_recovery_decision(
        sha256_bytes(checker_raw),
        sha256_bytes(tests_raw),
    )
    binding = decision.get("contentBinding")
    require(
        type(binding) is dict
        and set(binding)
        == {"algorithm", "canonicalization", "scope", "sha256"},
        "readback recovery decision: content binding schema",
    )
    require(
        binding["algorithm"] == "sha256"
        and binding["canonicalization"]
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding["scope"] == "decision_without_contentBinding"
        and binding["sha256"]
        == sha256_bytes(LEGACY.canonical_json_bytes(expected)),
        "readback recovery decision: content binding mismatch",
    )
    without_binding = dict(decision)
    without_binding.pop("contentBinding")
    require(
        without_binding == expected,
        "readback recovery decision: exact contract mismatch",
    )
    return decision


def validate_state(root: Path = ROOT) -> dict[str, Any]:
    validate_recovery_authority(root)
    state = dict(LEGACY.validate_state(root))
    state["recoveryDecisionId"] = RECOVERY_DECISION_ID
    state["recoveryReaderVersion"] = "2.0"
    state["externalAuthenticationRequired"] = False
    state["repositoryOwnerIdentityProofRequired"] = False
    state["userActionRequired"] = False
    return state


def record_readback(root: Path = ROOT) -> dict[str, Any]:
    validate_recovery_authority(root)
    result = dict(LEGACY.record_readback(root))
    result["recoveryDecisionId"] = RECOVERY_DECISION_ID
    result["recoveryReaderVersion"] = "2.0"
    result["externalAuthenticationRequired"] = False
    result["repositoryOwnerIdentityProofRequired"] = False
    result["userActionRequired"] = False
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--record", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = record_readback(args.root) if args.record else validate_state(args.root)
    except (RecoveryError, LEGACY.CheckError, OSError) as error:
        print(
            LEGACY.canonical_json_bytes(
                {
                    "documentType": (
                        "aetherlink.g2-pion-dependency-wave1-v3-"
                        "readback-recovery-result"
                    ),
                    "schemaVersion": "2.0",
                    "status": "failed_closed",
                    "validationPassed": False,
                    "error": str(error),
                    "networkOperationCount": 0,
                    "externalAuthenticationRequired": False,
                    "repositoryOwnerIdentityProofRequired": False,
                    "userActionRequired": False,
                }
            ).decode("utf-8"),
            end="",
        )
        return 1
    printable = dict(result)
    printable.pop("readbackReceiptCandidate", None)
    print(LEGACY.canonical_json_bytes(printable).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
