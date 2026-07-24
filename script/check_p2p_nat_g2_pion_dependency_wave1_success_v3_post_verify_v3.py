#!/usr/bin/env python3
"""Verification-only fixed-hash audit of the completed v3 readback.

This v3 verifier preserves the consumed acquisition, the original readback
checker, the v2 recovery reader, and both published readback documents.  It
closes the v2 dispatch/TOCTOU gap by enforcing fixed raw SHA-256 values inside
the original checker's held-file validation pass.  It exposes no record mode
and performs no network, source extraction, or Git operation.
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
            "dependency wave-one v3 post-verifier requires unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import os
from pathlib import Path
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3_post_verify_v3.py"
)
TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3_post_verify_v3.py"
)
V2_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_wave1_success_v3_recovery_v2.py"
)
V2_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_dependency_wave1_success_v3_recovery_v2.py"
)
V2_DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-recovery-decision-v2.json"
)
V2_CHECKER_RAW_SHA256 = (
    "c201733f8c87224dabdebb7392209014a10f089d62f6473b52349f511a223933"
)
V2_TESTS_RAW_SHA256 = (
    "854b3ab38f53d93c7b0a856bf5aa3fc5649f602d2d554a0bb84ab1a08e610dfe"
)
V2_DECISION_RAW_SHA256 = (
    "3f04fac4cae49d4e65669fcb2d09bb0852f9c5fe757e6981b8fd17fcb772e395"
)
POST_VERIFICATION_DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-acquisition-wave1-readback-"
    "post-verification-decision-v3.json"
)
POST_VERIFICATION_DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-dependency-wave1-readback-"
    "post-verification-decision-v3"
)
MAXIMUM_TOOL_BYTES = 2_097_152
MAXIMUM_JSON_BYTES = 2_097_152


class PostVerificationError(RuntimeError):
    """A closed post-verification failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PostVerificationError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_v2_checker() -> types.ModuleType:
    path = ROOT / V2_CHECKER_PATH
    raw = path.read_bytes()
    require(
        len(raw) <= MAXIMUM_TOOL_BYTES
        and sha256_bytes(raw) == V2_CHECKER_RAW_SHA256,
        "v2 recovery reader identity mismatch",
    )
    module = types.ModuleType("aetherlink_wave1_v3_immutable_recovery_reader_v2")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(path),
            "__loader__": None,
            "__package__": None,
        }
    )
    exec(
        compile(raw, V2_CHECKER_PATH, "exec", dont_inherit=True, optimize=0),
        module.__dict__,
        module.__dict__,
    )
    return module


V2 = load_v2_checker()
LEGACY = V2.LEGACY
ORIGINAL_STRICT_JSON = V2.ORIGINAL_STRICT_JSON

RELAXED_PREDECESSOR_BINDINGS: Mapping[str, Mapping[str, str]] = {
    label: dict(binding) for label, binding in V2.PREDECESSOR_BINDINGS.items()
}
CANONICAL_ARTIFACT_BINDINGS: Mapping[str, Mapping[str, str]] = {
    "v3 claim": {
        "path": V2.CLAIM_PATH,
        "rawSha256": V2.CLAIM_RAW_SHA256,
    },
    "v3 success receipt": {
        "path": V2.SUCCESS_RECEIPT_PATH,
        "rawSha256": V2.SUCCESS_RECEIPT_RAW_SHA256,
    },
    "v3 acquisition manifest": {
        "path": V2.ACQUISITION_MANIFEST_PATH,
        "rawSha256": V2.ACQUISITION_MANIFEST_RAW_SHA256,
    },
    "readback receipt": {
        "path": V2.READBACK_RECEIPT_PATH,
        "rawSha256": (
            "63c7db8fce4a1c5c26dba84c22be9ea79afda95afb76506a10457e1ac9e910e0"
        ),
    },
    "readback manifest": {
        "path": V2.READBACK_MANIFEST_PATH,
        "rawSha256": (
            "a62e1cc1508a127fa1f5cb4a5009cf7ddeae87ef40172d1c7327c51f8cbc3b96"
        ),
    },
}


def hardened_strict_json(raw: bytes, label: str) -> Any:
    if label in RELAXED_PREDECESSOR_BINDINGS:
        return V2.parse_exact_bound_predecessor(raw, label)
    binding = CANONICAL_ARTIFACT_BINDINGS.get(label)
    require(binding is not None, f"{label}: unbound JSON parser label")
    require(
        sha256_bytes(raw) == binding["rawSha256"],
        f"{label}: fixed raw SHA-256 mismatch",
    )
    return ORIGINAL_STRICT_JSON(raw, label)


LEGACY.strict_json = hardened_strict_json


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


def expected_post_verification_decision(
    checker_raw_sha256: str,
    tests_raw_sha256: str,
) -> dict[str, Any]:
    return {
        "documentType": (
            "aetherlink.g2-pion-dependency-wave1-v3-"
            "readback-post-verification-decision"
        ),
        "schemaVersion": "3.0",
        "decisionId": POST_VERIFICATION_DECISION_ID,
        "recordedDate": "2026-07-24",
        "status": (
            "wave1_v3_readback_published_fixed_hash_post_verification_authorized"
        ),
        "result": (
            "preserve_v2_record_and_verify_all_json_inputs_at_held_parse_time"
        ),
        "predecessorRecoveryBindings": {
            "decisionPath": V2_DECISION_PATH,
            "decisionRawSha256": V2_DECISION_RAW_SHA256,
            "checkerPath": V2_CHECKER_PATH,
            "checkerRawSha256": V2_CHECKER_RAW_SHA256,
            "checkerTestsPath": V2_TESTS_PATH,
            "checkerTestsRawSha256": V2_TESTS_RAW_SHA256,
            "observedGap": (
                "canonical_predecessor_dispatch_bypassed_fixed_raw_sha_and_"
                "authority_validation_preceded_held_set_validation_and_"
                "decision_comparison_was_not_type_strict"
            ),
            "recordedReadbackInvalidated": False,
        },
        "fixedJsonInputBindings": [
            {
                "label": label,
                "path": binding["path"],
                "rawSha256": binding["rawSha256"],
                "encodingPolicy": "fixed_raw_sha_then_bounded_json",
            }
            for label, binding in RELAXED_PREDECESSOR_BINDINGS.items()
        ]
        + [
            {
                "label": label,
                "path": binding["path"],
                "rawSha256": binding["rawSha256"],
                "encodingPolicy": "fixed_raw_sha_then_compact_canonical_json",
            }
            for label, binding in CANONICAL_ARTIFACT_BINDINGS.items()
        ],
        "readbackResultBindings": {
            "receiptPath": V2.READBACK_RECEIPT_PATH,
            "receiptRawSha256": (
                "63c7db8fce4a1c5c26dba84c22be9ea79afda95afb76506a10457e1ac9e910e0"
            ),
            "receiptContentSha256": (
                "d79ad227a0bc34fd94a58c1bab95f5691cec1db42a9eaff7ed27fe37ee278916"
            ),
            "manifestPath": V2.READBACK_MANIFEST_PATH,
            "manifestRawSha256": (
                "a62e1cc1508a127fa1f5cb4a5009cf7ddeae87ef40172d1c7327c51f8cbc3b96"
            ),
            "manifestContentSha256": (
                "e8d9273ecec3dd2006364f6a6bc5a339075cc6807ae978e2b83e03d2d2e0b2eb"
            ),
            "retainedResourceCount": 38,
            "postReadbackRegularFileCount": 43,
            "orderedSourceSetSha256": V2.ORDERED_SOURCE_SET_SHA256,
        },
        "selectedPostVerifier": {
            "checkerPath": SELF_PATH,
            "checkerRawSha256": checker_raw_sha256,
            "checkerTestsPath": TESTS_PATH,
            "checkerTestsRawSha256": tests_raw_sha256,
            "underlyingCheckerPath": V2.ORIGINAL_CHECKER_PATH,
            "underlyingCheckerRawSha256": V2.ORIGINAL_CHECKER_RAW_SHA256,
            "fixedHashEnforcedInsideHeldValidation": True,
            "verificationOnly": True,
            "recordModeExposed": False,
            "networkAllowed": False,
            "sourceExtractionAllowed": False,
        },
        "authorization": {
            "postVerificationAuthorized": True,
            "readbackRecordAuthorized": False,
            "acquisitionRetryAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "nextAction": "run_fixed_hash_readback_post_verifier",
    }


def validate_decision_document(
    decision: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    binding = decision.get("contentBinding")
    require(
        type(binding) is dict
        and set(binding)
        == {"algorithm", "canonicalization", "scope", "sha256"},
        "readback post-verification decision: content binding schema",
    )
    require(
        type(binding["algorithm"]) is str
        and binding["algorithm"] == "sha256"
        and type(binding["canonicalization"]) is str
        and binding["canonicalization"]
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and type(binding["scope"]) is str
        and binding["scope"] == "decision_without_contentBinding"
        and type(binding["sha256"]) is str,
        "readback post-verification decision: content binding fields",
    )
    without_binding = dict(decision)
    without_binding.pop("contentBinding")
    actual_canonical = LEGACY.canonical_json_bytes(without_binding)
    expected_canonical = LEGACY.canonical_json_bytes(expected)
    require(
        binding["sha256"] == sha256_bytes(actual_canonical),
        "readback post-verification decision: actual content binding mismatch",
    )
    require(
        actual_canonical == expected_canonical,
        "readback post-verification decision: exact typed contract mismatch",
    )


def validate_post_verification_authority(
    root: Path = ROOT,
) -> Mapping[str, Any]:
    checker_raw = read_held(
        root, SELF_PATH, maximum_bytes=MAXIMUM_TOOL_BYTES, owner_only=False
    )
    tests_raw = read_held(
        root, TESTS_PATH, maximum_bytes=MAXIMUM_TOOL_BYTES, owner_only=False
    )
    for relative, expected in (
        (V2_CHECKER_PATH, V2_CHECKER_RAW_SHA256),
        (V2_TESTS_PATH, V2_TESTS_RAW_SHA256),
        (V2_DECISION_PATH, V2_DECISION_RAW_SHA256),
    ):
        require(
            sha256_bytes(
                read_held(
                    root,
                    relative,
                    maximum_bytes=MAXIMUM_TOOL_BYTES,
                    owner_only=False,
                )
            )
            == expected,
            f"{relative}: v2 recovery binding mismatch",
        )
    for label, binding in (
        list(RELAXED_PREDECESSOR_BINDINGS.items())
        + list(CANONICAL_ARTIFACT_BINDINGS.items())
    ):
        require(
            sha256_bytes(
                read_held(
                    root,
                    binding["path"],
                    maximum_bytes=MAXIMUM_JSON_BYTES,
                    owner_only=label
                    in {
                        "v3 claim",
                        "v3 success receipt",
                        "v3 acquisition manifest",
                        "readback receipt",
                        "readback manifest",
                    },
                )
            )
            == binding["rawSha256"],
            f"{label}: post-verification authority binding mismatch",
        )
    decision_raw = read_held(
        root,
        POST_VERIFICATION_DECISION_PATH,
        maximum_bytes=MAXIMUM_JSON_BYTES,
        owner_only=False,
    )
    decision = ORIGINAL_STRICT_JSON(
        decision_raw, "readback post-verification decision"
    )
    require(
        type(decision) is dict,
        "readback post-verification decision: object required",
    )
    expected = expected_post_verification_decision(
        sha256_bytes(checker_raw),
        sha256_bytes(tests_raw),
    )
    validate_decision_document(decision, expected)
    return decision


def validate_state(root: Path = ROOT) -> dict[str, Any]:
    validate_post_verification_authority(root)
    state = dict(LEGACY.validate_state(root))
    require(
        state.get("status") == "independent_readback_complete"
        and state.get("observedRegularFileCount") == 43
        and state.get("retainedResourceCount") == 38,
        "fixed-hash post-verification requires the complete readback set",
    )
    state["postVerificationDecisionId"] = POST_VERIFICATION_DECISION_ID
    state["postVerifierVersion"] = "3.0"
    state["fixedHashEnforcedInsideHeldValidation"] = True
    state["verificationOnly"] = True
    state["recordModeExposed"] = False
    state["externalAuthenticationRequired"] = False
    state["repositoryOwnerIdentityProofRequired"] = False
    state["userActionRequired"] = False
    return state


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = validate_state(args.root)
    except (
        PostVerificationError,
        V2.RecoveryError,
        LEGACY.CheckError,
        OSError,
    ) as error:
        print(
            LEGACY.canonical_json_bytes(
                {
                    "documentType": (
                        "aetherlink.g2-pion-dependency-wave1-v3-"
                        "readback-post-verification-result"
                    ),
                    "schemaVersion": "3.0",
                    "status": "failed_closed",
                    "validationPassed": False,
                    "error": str(error),
                    "networkOperationCount": 0,
                    "fileWriteCount": 0,
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
