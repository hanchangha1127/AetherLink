#!/usr/bin/env python3
"""Recompute the exact 359-input Wave1..Wave17 graph without publishing.

Run only with ``python3 -I -B -S``. The checker pins the immutable v15
combined checker, all Wave17 decision/acquisition/readback controls, and the
root archive plus 179 mod and 179 zip inputs. Every source input is opened
no-follow, held by descriptor, read twice, and used for two full graph
reconstructions. Fixed-point and frontier results are derived only from those
reconstructions. No dependency source is extracted, loaded, executed, or
compiled. The exact trusted pinned normal reconstruction path invokes zero
network, subprocess, authentication, device, Git, or file-write operations.
The provider proxy is defense-in-depth; it is not an OS syscall sandbox.
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
            "combined fixed-point v16 checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
from collections import defaultdict
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import types
from typing import Any, Mapping, Sequence
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[1]
# FINAL SELF-SEAL PLACEHOLDER: replace after the checker freezes.
SELF_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v16.py"
SELF_NORMALIZED_SHA256 = (
    "4dfb9f6ccd7a05d1d564aaafab0d3ab4c908d80a5301b1f0948f5056cde17466"
)
V15_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v15.py"
V15_CHECKER_RAW_SHA256 = (
    "e0a8353e5bd4f40b587c2b62c563c0b679ca5261345e577d71d00fb868f08fb5"
)
V15_CHECKER_NORMALIZED_SHA256 = (
    "63198050500264a07082d205172c21993a309289649a5459e1c638b53fb22bf7"
)
V15_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v15.py"
V15_TESTS_RAW_SHA256 = (
    "65d7f435cef11da2cccae7e31a3c410d7a3038f6bc3261552753801a0de431b1"
)
V14_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v14.py"
V14_CHECKER_RAW_SHA256 = (
    "bf729f8dbfc0508fa977893eb1c7c30e07d15fa751a29856d4c4d386f1001292"
)
V14_CHECKER_NORMALIZED_SHA256 = (
    "8be3cf62cc66c2aaf780c658acf5b6e242fcbd52e44dd6fd90a11e3eeba505ec"
)
V14_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v14.py"
V14_TESTS_RAW_SHA256 = (
    "17adc7ea0f75eff26108187bb50a2f250655f0e190f5b51cbe1f5ea9c57896e3"
)
V13_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v13.py"
V13_CHECKER_RAW_SHA256 = (
    "0b0ea7d68ef5fc11b8c0defe56bf443c681a6952a27e2c9b6c41d9702241a80b"
)
V13_CHECKER_NORMALIZED_SHA256 = (
    "73a778e53bdc1d15ffd34109ff02297e85eb6a91b52d1577acefe9bc1383e674"
)
V13_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v13.py"
V13_TESTS_RAW_SHA256 = (
    "dffb5e24cfd2ba4c561f5e8c6302c4502a75f917c1ac9d15216fd7f2ac045327"
)
V12_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v12.py"
V12_CHECKER_RAW_SHA256 = (
    "cc693cb0126267962813a418a53ece371aec0172d24a75ea70cf6dbe89a1db45"
)
V12_CHECKER_NORMALIZED_SHA256 = (
    "cfcf095861bd753e3cfb7521e339e2bb5a3e59b5a75258ff5b8ee5cfc8ba43f2"
)
V12_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v12.py"
V12_TESTS_RAW_SHA256 = (
    "43dea4e06f07a304b620f33cf9aa647e39839dc5365705756fa10433e9bd60bd"
)
V11_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v11.py"
V11_CHECKER_RAW_SHA256 = (
    "d330a2f7dd4f12bd4f972e6c34749e10701c594cad75308ccc7de4d3e6aba176"
)
V11_CHECKER_NORMALIZED_SHA256 = (
    "1ef7c9fb874c33b8b25c02f0024e6d85e3df070718c0de9861c60173697af82e"
)
V11_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v11.py"
V11_TESTS_RAW_SHA256 = (
    "7d753c0406210ca7e7bb07905533084fdba8a5ed626d23d913211021c719e922"
)
V10_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py"
V10_CHECKER_RAW_SHA256 = (
    "11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985"
)
V10_CHECKER_NORMALIZED_SHA256 = (
    "ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751"
)
V10_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v10.py"
V10_TESTS_RAW_SHA256 = (
    "ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35"
)
V9_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v9.py"
V9_CHECKER_RAW_SHA256 = (
    "c0f098cf0a047c4d1aca03f5b7f16f327306b56ed8e656d67afe32503eb117da"
)
V9_CHECKER_NORMALIZED_SHA256 = (
    "b4cdbfd385e0606fa2ca37017983bd80b6856dd69dfafb46df6579e76c618684"
)
V9_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v9.py"
V9_TESTS_RAW_SHA256 = (
    "fca6a0ca437356185d287816bcfaf5e110794207b3413addf95e9eb24038c217"
)
V8_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v8.py"
V8_CHECKER_RAW_SHA256 = (
    "798a055a9a4c3957c0edd75ecbad35f0cfa9f17bf39e63cd262876dcb6103e32"
)
V8_CHECKER_NORMALIZED_SHA256 = (
    "cfd83cdd00b6daee857cbff915ec48fd78390bbf06098ccab963a54e8748ba4b"
)
V8_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v8.py"
V8_TESTS_RAW_SHA256 = (
    "347a1e0083d2daedb40deba5fca491b63ee3137b5a7c18a56886be694ded16a0"
)
V7_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v7.py"
V7_CHECKER_RAW_SHA256 = (
    "7264d85e1948bc8f86e8238192663706e7bf7472153d37fe812bd118620e99c7"
)
V7_CHECKER_NORMALIZED_SHA256 = (
    "cf4fd9d25efe04c2ecb3eea882bb24d6c40b02f2f258c4ab01d824d1373d1c02"
)
V7_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v7.py"
V7_TESTS_RAW_SHA256 = (
    "bb992db8e2d649dd982255f21c2c719ee4d0437818eb0495c9a11fe81f5ea79f"
)
V6_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v6.py"
V6_CHECKER_RAW_SHA256 = (
    "eee3d6bd5ec0857bc4832895f4c2d463b608ffc0a59436ebc2cde507cd9750e4"
)
V6_CHECKER_NORMALIZED_SHA256 = (
    "3f2a9866a185d157ab4fca021b52bc55aecac914fd5a08003e2f2f34e9522eef"
)
V6_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v6.py"
V6_TESTS_RAW_SHA256 = (
    "4ce508661695fd63c0e1c578a99cbfa9f369943283186958bf26b998839c7837"
)
V5_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v5.py"
V5_CHECKER_RAW_SHA256 = (
    "b63047c6867175655cf95710767dd930783dae5d99883dfb731aedeb59459e92"
)
V5_CHECKER_NORMALIZED_SHA256 = (
    "63587ee84ebe68aeb579c1bf85478e3c818ceaeaa8770e499d36b05ee41fe1aa"
)
V4_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v4.py"
V4_CHECKER_RAW_SHA256 = (
    "2576f7d2e0f0c8dffd2f4956254af3f62b39fdabb25b793242315f50b1373a52"
)
V1_PROVIDER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
V1_PROVIDER_RAW_SHA256 = (
    "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
)
WAVE9_LEGACY_BUILD_SOURCE_SHA256 = (
    "042948d42899becd3c158c680d9c491ca9a57629cc893edea31ef2aae2666443"
)
WAVE9_LEGACY_BUILD_NORMALIZED_SHA256 = (
    "a46760412870548bd5bf6cfb011129769545623276e3b0385f85deb3206045f2"
)
WAVE9_LEGACY_BUILD_ORIGINAL_LINE = (
    "// +build go1.8,!go1.9 // TODO(adonovan) determine which versions "
    "we need to test here"
)
WAVE9_LEGACY_BUILD_NORMALIZED_LINE = "// +build go1.8,!go1.9"
WAVE9_LEGACY_BUILD_EXPRESSION = (
    "((go1.8 && !go1.9)) && ((!windows))"
)
WAVE9_LEGACY_BUILD_TRAILING_OR_OPTIONS = (
    "//",
    "TODO(adonovan)",
    "determine",
    "which",
    "versions",
    "we",
    "need",
    "to",
    "test",
    "here",
)
TRANSITIVE_CHECKER_PATHS = {
    f"script/check_p2p_nat_g2_pion_combined_fixed_point_v{version}.py"
    for version in range(1, 16)
}
CHECKER_ID = (
    "g2-pion-ice-v4.3.0-combined-wave1-wave2-wave3-wave4-wave5-wave6-"
    "wave7-wave8-wave9-wave10-wave11-wave12-wave13-wave14-wave15-"
    "wave16-wave17-check-v16"
)
CODE_MAXIMUM_BYTES = 4 * 1024 * 1024
JSON_MAXIMUM_BYTES = 8 * 1024 * 1024
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)

WAVE17_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave17-v1.json"
)
WAVE17_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "execution-permit-v1.json"
)
WAVE17_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-receipt-v1.json"
)
WAVE17_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-manifest-v1.json"
)
WAVE17_READBACK_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "readback-execution-permit-v1.json"
)
WAVE17_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-readback-v1.json"
)
WAVE17_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-"
    "readback-manifest-v1.json"
)
WAVE17_ACCEPTED_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-17-v1/accepted"
)
WAVE17_ACQUISITION_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-17-v1.claim"
)
WAVE17_EVIDENCE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-17-v1/evidence.json"
)
WAVE17_READBACK_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-17-v1-readback.claim"
)
WAVE17_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave17-failure-v1.json"
)
WAVE17_STAGING_PREFIX = ".wave-17-v1-staging-"
WAVE17_READBACK_TEMP_PREFIXES = (
    ".bounded-dependency-source-acquisition-wave17-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave17-readback-"
        "manifest-v1.json.tmp-"
    ),
)

WAVE17_CONTROL_SHA256 = {
    WAVE17_DECISION_PATH:
        "659e9ce6f079701cab68e337d2746959741ef4868ffff6392fcdbf26ae692f93",
    WAVE17_PERMIT_PATH:
        "8376c5daef8a9e8970b03b15cda5861a2d16c237024d97cb00e1dfeac275baaa",
    WAVE17_RECEIPT_PATH:
        "0736a577af59b621483694c8f9fa36ce3c8f06bfd7c48d2b204b6a94a6d8f4c5",
    WAVE17_MANIFEST_PATH:
        "3c9a6d92ca6b967a5fdc3997793cf90456836923a8460e2816271be6c57a7733",
    WAVE17_READBACK_PERMIT_PATH:
        "05e71da5b47544728c74fb8eb9b4bb665179dde420b48211a5f9dfb5ad2d3bcd",
    WAVE17_READBACK_PATH:
        "9f21afa4c98081d95228d217e60eec66961b85ee5b23ab11e51f19c6f9865958",
    WAVE17_READBACK_MANIFEST_PATH:
        "05bd78ba52abac67c3eec63a180c7e815a7528709f4b8e58b40c2e948ff4f3e4",
}
WAVE17_CONTROL_METADATA = {
    WAVE17_DECISION_PATH: (8_801, 0o644),
    WAVE17_PERMIT_PATH: (16_139, 0o644),
    WAVE17_RECEIPT_PATH: (1_659, 0o600),
    WAVE17_MANIFEST_PATH: (465, 0o600),
    WAVE17_READBACK_PERMIT_PATH: (17_498, 0o644),
    WAVE17_READBACK_PATH: (4_980, 0o600),
    WAVE17_READBACK_MANIFEST_PATH: (2_301, 0o600),
}
WAVE17_CONTENT_SHA256 = {
    WAVE17_DECISION_PATH:
        "867a2ba1a7da54b5466951b1caea9b09eb355d2325a58fa552037047d3fad7df",
    WAVE17_PERMIT_PATH:
        "1731bfc92d04b15db9419167ce3279eed567d9154019da03f595f6556ccd98e4",
    WAVE17_READBACK_PERMIT_PATH:
        "04a0e2397b574fb3ad1b60b3c3cc42500f28640e2d08f7fd924af05d35f81e0e",
    WAVE17_READBACK_PATH:
        "d71a8dd363817a605179fa490bf42fe81fbc494c3f19faed3d3d2d5c31b2e8dd",
    WAVE17_READBACK_MANIFEST_PATH:
        "1612a5eab4181ff2fba8772077434cd973c220893b9febf2ebc19afee0f7d98c",
}
WAVE17_REQUEST_SET_SHA256 = (
    "acf64af2352fb4d82325f3e5bd2a3e913b8ef95db553fa0015bc71a239f3fb35"
)
WAVE17_PERMIT_RESOURCES_SHA256 = (
    "4920d020b6a4df4adc890a8eb2a0290e1343938483e396cc7e21447728f14686"
)
WAVE17_RESOURCE_SET_SHA256 = (
    "7bee498b9c53d5d834fad61a2862162791ad46f45471199389046fb466c16cfa"
)
WAVE17_FROZEN_FILE_SET_SHA256 = (
    "bea9d0c6a260407e34524b5aced01cf9a334c36a6f882350e57f02107b1008c8"
)
WAVE17_ATTEMPT_ID = "117fb836380658986632911b9508e274"
WAVE17_READBACK_ATTEMPT_ID = "01f3117be3154e37f7f791b49002c490"
WAVE17_COMPACT_IDENTITY_SHA256 = (
    "813ac6030c903b716fb5f68852468a53ebb0bcfe60c7c11582d2f2ffb18041ca"
)
WAVE17_FULL_WITNESS_SHA256 = (
    "ee3f4b0e1072a8bc0e1eb6e53b83fe8d749fdfd8c13bec54c60774dc3755dc54"
)
WAVE17_HELD_SOURCE_BINDINGS_SHA256 = (
    "86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd"
)
WAVE17_ACQUISITION_CLAIM_RAW_SHA256 = (
    "3090e729d99c46c4b4d1e4242d6f25c08e2345062dfb6c15e1e87d3edf632fad"
)
WAVE17_ACQUISITION_EVIDENCE_RAW_SHA256 = (
    "bfe3e3cb97d5ed20d5c95e83344cc79f8f16de09b2cafb924cf59cbe64da6175"
)
WAVE17_ACQUISITION_CHECKER_RAW_SHA256 = (
    "acd6af5f174569c0b3d988d4528cf9b6219c9b5c5b6ba9205db982506b0e7b81"
)
WAVE17_ACQUISITION_RUNNER_RAW_SHA256 = (
    "8e9ec1a6633754f27566e065899c2dbf492b4707dc562ccdccd4e56a94e96fb8"
)
WAVE17_READBACK_CLAIM_RAW_SHA256 = (
    "51857e48f14271386627fe222f8e094bc6c0347563a15b663d37772378fbaba7"
)
WAVE17_READBACK_CLAIM_CONTENT_SHA256 = (
    "41d7d468c1018a33f75cf1a4f23d6d1697900ff0c9a755e32e2b3085e662ebca"
)
WAVE17_READBACK_CHECKER_RAW_SHA256 = (
    "f9ceb4756e2ef7cf3c13cd5c3b21399d1f5f44aef3f0c8781ba6dfa67d11bb3f"
)
WAVE17_READBACK_RECORDER_RAW_SHA256 = (
    "ab448a2479f35b1013c32451489c477d6f1742208debd5145b101acf0b2e7434"
)
WAVE17_READBACK_RECORDER_NORMALIZED_SHA256 = (
    "e7095acf4dfd443469bf75e1c58a3a77038dcff278b41e91f179cf655a9baff1"
)
WAVE17_RETAINED_BARRIERS = [
    "complete_snapshot_and_claim_immediately_before_receipt",
    "complete_snapshot_claim_and_receipt_after_receipt",
    (
        "complete_snapshot_claim_and_receipt_immediately_before_"
        "manifest_publication"
    ),
]
WAVE17_ABSOLUTE_RESOURCE_LIMITS = {
    "callerBlockedSigalrmRejectedBeforePreflight": True,
    "maximumAggregateModResponseBodyBytes": 1_048_576,
    "maximumAggregateResponseBodyBytes": 17_825_792,
    "maximumAggregateZipResponseBodyBytes": 16_777_216,
    "maximumHeaderBytesPerResponse": 16_384,
    "maximumModResponseBodyBytes": 1_048_576,
    "maximumRequestCount": 2,
    "maximumZipEntryBytes": 134_217_728,
    "maximumZipEntryCount": 20_000,
    "maximumZipResponseBodyBytes": 16_777_216,
    "maximumZipUncompressedBytes": 134_217_728,
    "originalSignalMaskRestoredExactlyOrUncertaintyReported": True,
    "pendingInstalledSigalrmSynchronouslyConsumedBeforePriorHandlerRestoration":
        True,
    "pendingSigalrmDrainFailureContainedWithoutPriorAlarmStateRestoration":
        True,
    "perRequestDeadlineMilliseconds": 30_000,
    "perRequestDeadlinePassedToPinnedFetchPrimitive": True,
    "preexistingRealTimerRestoredWithElapsedAdjustment": True,
    "priorHandlerRestoredBeforePriorTimerArmed": True,
    "processSetupAndRestorationUseGuardedSignalState": True,
    "processStateRestorationStepsAreIndependentBestEffort": True,
    "sigalrmUnblockedDuringFetchValidationWriteAndFsync": True,
    "wholeAttemptDeadlineMilliseconds": 600_000,
    "wholeAttemptSigalrmDeadlineRequired": True,
}
WAVE17_ZIP_LIMITS = {
    "encryptedSymlinkDirectoryDuplicateOrUnsafeEntriesAllowed": False,
    "maximumEntryCountAcrossAllZips": 20_000,
    "maximumEntryCountPerZip": 20_000,
    "maximumEntryNameBytes": 1_024,
    "maximumSingleEntryBytes": 134_217_728,
    "maximumUncompressedBytesAcrossAllZips": 134_217_728,
    "maximumUncompressedBytesPerZip": 134_217_728,
}
WAVE17_READBACK_RESOURCE_LIMITS = {
    "maximumAcceptedResourceCount": 2,
    "maximumAggregateAcceptedBytes": 17_825_792,
    "maximumAggregateModBytes": 1_048_576,
    "maximumAggregateZipBytes": 16_777_216,
    "maximumModBytes": 1_048_576,
    "maximumPackageFileBytes": 8_388_608,
    "maximumZipBytes": 16_777_216,
    "maximumZipEntriesAcrossAll": 20_000,
    "maximumZipEntriesPerZip": 20_000,
    "maximumZipEntryBytes": 134_217_728,
    "maximumZipEntryNameBytes": 1_024,
    "maximumZipUncompressedBytesAcrossAll": 134_217_728,
    "maximumZipUncompressedBytesPerZip": 134_217_728,
}
V6_CANDIDATE_CONTENT_SHA256 = (
    "b33ef7a10de32dc99cea1dbbbcab1dac3a549eb466ef80b0229d2a0381ab9052"
)
V6_INPUT_SET_SHA256 = (
    "f7ad0b43d571da61edd4941f8e504d54d014b01f3395aeca8d0d10b9b3c22349"
)
V6_GRAPH_SHA256 = (
    "3648bdf037e316e69e155615edd5748c2bb653238579216ddd8b8dce4beb9f09"
)
V6_FRONTIER_SHA256 = (
    "d3c3788d6a1144bf04ea2c68e6aa4b9fdd17859bc625e2c2c51019bb3c61ff92"
)
V7_CANDIDATE_CONTENT_SHA256 = (
    "c71188f8d648a0f020a164002644f825e018f4c01b56d90e57011e05cc2e5202"
)
V7_INPUT_SET_SHA256 = (
    "d389c84ae3b6d2d3d7dbb38d7003711972a75db3a558b9d6e0d79856249ef528"
)
V7_GRAPH_SHA256 = (
    "c7889fbf06a01e08ba75150b85bb2cb2860ea71ce205cead432cf0a37e0d89b9"
)
V7_FRONTIER_SHA256 = (
    "03058e3aea23aca0c6208dd0023361f90421d394272f212d80bf61d587baff4e"
)
V8_CANDIDATE_CONTENT_SHA256 = (
    "f9f683d3afbe65a77626577428c0f9ce94219e39529d0c5811b49172c51e3b37"
)
V8_INPUT_SET_SHA256 = (
    "030743c3959a6e7466385e9f89255fcb03d65576676a1e5cd7e5e2929e9f6339"
)
V8_GRAPH_SHA256 = (
    "721d045a10cdf015e865a84db7026115ac63462217dbb5349504fed9f1bae7b7"
)
V8_FRONTIER_SHA256 = (
    "780501bca37fbeb953590004ca7e5aad7f206083f749b920e2a9842b63675f82"
)
V9_INPUT_SET_SHA256 = (
    "5a08d28573b68ddd031eff34a8b6afad8f7cd9e01966f4516c22a410bbb51b71"
)
V9_SOURCE_BINDINGS_SHA256 = (
    "2455ab16e4c1dd6a68127c38f25d49275d9ef955d4d12ad711d644f0d745839f"
)
V10_INPUT_SET_SHA256 = (
    "f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be"
)
V10_SOURCE_BINDINGS_SHA256 = (
    "067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c"
)
V11_INPUT_SET_SHA256 = (
    "124995740eb0d95e83c77f078a334bd55ac491a14453098fa70da26cf52d6caa"
)
V11_SOURCE_BINDINGS_SHA256 = (
    "504b3ed2a6182db6464c93999c3bd073381ee181c7238ca62da5afd2ca87269f"
)
V11_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_154_162_168
V12_INPUT_SET_SHA256 = (
    "656dcf1c1e94b09649041fa6d99b0db1d3997914dc40eba5e7ca840b35b9760d"
)
V12_SOURCE_BINDINGS_SHA256 = (
    "bf043a07c5fa6d26f28de9954b8f676e583f625ccf28ca5a39d6fe23c6678592"
)
V12_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_174_227_650
V13_INPUT_SET_SHA256 = (
    "285cfb3e8b4a73beffa551429058611a606b00ad447d75599c77fb18895a2f91"
)
V13_SOURCE_BINDINGS_SHA256 = (
    "fbd023d2ee5f372ef90d06d92e48c7dfa9828212e38bf942e1741aca322b9996"
)
V13_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_230_182_064
V14_INPUT_SET_SHA256 = (
    "c62222562f7a248398aa8677c5c4b81c41a74f3b48dbae7a1da54eea887f9d7d"
)
V14_SOURCE_BINDINGS_SHA256 = (
    "a360afdc5d94502f53f5e393503198bb7ce6adf4d21a0c64245a1b7e49be9eae"
)
V14_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_250_144_441
V15_INPUT_SET_SHA256 = (
    "4b12b7ca7f0a8b1556c692522e8832af033f9d2a1f00fbeb7469623a00541f1e"
)
V15_SOURCE_BINDINGS_SHA256 = (
    "86512fdc6c5b8ff8b1d79e500e32c6c35c36f6c097aca5385f8ff1e06ffe18fd"
)
V15_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_296_608_653
V16_EXPECTED_HELD_SOURCE_INPUT_COUNT = 359
V16_EXPECTED_ARCHIVE_COUNT = 180
V16_EXPECTED_AGGREGATE_ENTRY_COUNT = 70_402
V16_EXPECTED_AGGREGATE_RAW_BYTE_SIZE = 342_529_585
V16_EXPECTED_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_305_716_657
V16_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = (
    V16_EXPECTED_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES
)
V16_INPUT_SET_SHA256 = (
    "15705de20633cdf4bf473c82a634136f481a2c131e7960a0a6cbdeccf10397a7"
)
V16_SOURCE_BINDINGS_SHA256 = (
    "401a3e85faacc150944d883495fca4b22e4cac1933c0308aedaec228a7c872ea"
)
V9_CANDIDATE_CONTENT_SHA256 = (
    "9c9e995f853a8dbbc07d55d41ce1c5660cb616d879b3565803e13b6aaf4532ba"
)
V9_GRAPH_SHA256 = (
    "4367fc6c4c5efb69f948d8e040c2cfa496345102631719692d31feabb794a6b5"
)
V9_FRONTIER_SHA256 = (
    "171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06"
)
V10_CANDIDATE_CONTENT_SHA256 = (
    "d7feddd3b291756c36359b013ea05aaa2f25cb83605daaeb493c0395ff9cc4f7"
)
V10_GRAPH_SHA256 = (
    "77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4"
)
V10_FRONTIER_SHA256 = (
    "8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05"
)
V11_CANDIDATE_CONTENT_SHA256 = (
    "1976ed89f18f28b0b3440a693581f171bdd574bc615f2054bea2cba1cf85b837"
)
V11_GRAPH_SHA256 = (
    "b4b0ec50d5538e80de93e89574249ca0d49b411443ebd2c78827928704b0a44d"
)
V11_FRONTIER_SHA256 = (
    "3528abe3579eb1d06ba01f66f56002a6e193fe1e25e233f03eab9b8ac3e4fc32"
)
V12_CANDIDATE_CONTENT_SHA256 = (
    "176f5802b4bb56a6136f930a02ddd648774416945984af04bae4438de4e2bc17"
)
V12_GRAPH_SHA256 = (
    "0ab3b47d6b4fc628a3bf83e648308591c84ddce8ad46ce8f8d6aca1797cf1e26"
)
V12_FRONTIER_SHA256 = (
    "a149da341952b398d71c9a9395cb18aac2c711bb8a8d72e1eb53ca710377df63"
)
V13_CANDIDATE_CONTENT_SHA256 = (
    "e1f711b558642ad2167da48f25184cd4c3235314c67f06a60cfd14ceecea1988"
)
V13_GRAPH_SHA256 = (
    "a35d9bd389a6fb9e04052eb411e4c9701a76ff0fd699e1c2d2a113d86439dfd5"
)
V13_FRONTIER_SHA256 = (
    "1d143e954c48cb48172cf61975868c3c76852f152d100a04745b16b02fa5e911"
)
V14_CANDIDATE_CONTENT_SHA256 = (
    "e77b120d6e367e03beb847eb36cbf64b37d32fe00539b029ae809310818d5b9c"
)
V14_GRAPH_SHA256 = (
    "7458344c93152bea86360d2742456a28ebfc6849994bf68db30214611f020798"
)
V14_FRONTIER_SHA256 = (
    "5544db5bdf34f4afadce7d91f7c56998988e68810ed96b454048bf62dc07c452"
)
V15_CANDIDATE_CONTENT_SHA256 = (
    "4666c802e40734bb1b5b91489eb24aa782cb346710caec9605be4e0e005553ee"
)
V15_GRAPH_SHA256 = (
    "ffe9f910669401198b88752663055ca2e6622d19e171f2d20a2b303d06c989d7"
)
V15_FRONTIER_SHA256 = (
    "ce1be1152aabf580a211f038d80aeaf9249418117b7d12ff26ffc909f1e4d593"
)
V6_AUTHORITY = {
    "decisionAuthorityGranted": False,
    "executionAuthorityGranted": False,
    "acquisitionAuthorityGranted": False,
    "publicationAuthorityGranted": False,
    "networkAuthorized": False,
    "sourceExecutionAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "subprocessAuthorized": False,
    "fileWriteAuthorized": False,
    "gitWriteAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "externalAuthenticationRequired": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "signatureRequired": False,
    "tokenRequired": False,
    "userActionRequired": False,
    "osSyscallSandboxProvided": False,
}
V7_AUTHORITY = dict(V6_AUTHORITY)
V8_AUTHORITY = dict(V7_AUTHORITY)
V9_AUTHORITY = dict(V8_AUTHORITY)
V10_AUTHORITY = dict(V9_AUTHORITY)
V11_AUTHORITY = dict(V10_AUTHORITY)
V12_AUTHORITY = dict(V11_AUTHORITY)
V13_AUTHORITY = dict(V12_AUTHORITY)
V14_AUTHORITY = dict(V13_AUTHORITY)
V15_AUTHORITY = dict(V14_AUTHORITY)
WAVE17_DECISION_AUTHORITY = {
    "acquisitionAuthorityGranted": False,
    "authenticationRequired": False,
    "compileAuthorized": False,
    "decisionAuthorityGranted": False,
    "dependencySourceExecutionAuthorized": False,
    "deploymentAuthorized": False,
    "deviceInteractionRequired": False,
    "dnsAuthorized": False,
    "executionAuthorityGranted": False,
    "externalAuthenticationRequired": False,
    "fileWriteAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "gitWriteAuthorized": False,
    "networkAuthorized": False,
    "ownerProofRequired": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "productRuntimeNetworkAuthorized": False,
    "publicationAuthorityGranted": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}

WAVE17_ACQUISITION_AUTHORITY = {
    "accountRequired": False,
    "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized": False,
    "authenticationRequired": False,
    "clientCertificateRequired": False,
    "compileAuthorized": False,
    "cookieRequired": False,
    "deploymentAuthorized": False,
    "deviceAuthorized": False,
    "dnsTcpTlsHttpsToExactProxyAuthorized": True,
    "externalAuthenticationRequired": False,
    "gitOperationAuthorized": False,
    "gpgRequired": False,
    "ownerProofRequired": False,
    "ownerRequired": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "productRuntimeNetworkAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "sshRequired": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
    "publicationAuthorized": False,
    "wave17PublicProxy2GetAcquisitionAuthorizedOnce": True,
}
WAVE17_READBACK_AUTHORITY = {
    "accountRequired": False,
    "authenticationRequired": False,
    "clientCertificateRequired": False,
    "compileAuthorized": False,
    "cookieRequired": False,
    "credentialRequired": False,
    "deploymentAuthorized": False,
    "deviceAuthorized": False,
    "dnsAuthorized": False,
    "externalAuthenticationRequired": False,
    "failedTemporaryCleanupAuthorized": True,
    "frozenInputWritesAuthorized": False,
    "gitOperationAuthorized": False,
    "gpgRequired": False,
    "networkAuthorized": False,
    "offlineReadbackAuthorizedOnce": True,
    "otherRepositoryWritesAuthorized": False,
    "ownerProofRequired": False,
    "ownerRequired": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "proxyAuthorized": False,
    "readbackClaimWriteAuthorized": True,
    "readbackManifestWriteAuthorized": True,
    "readbackReceiptWriteAuthorized": True,
    "repositoryOwnerIdentityProofRequired": False,
    "sameDirectoryTemporaryPublicationAuthorized": True,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceAcquisitionAuthorized": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "sshRequired": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}
WAVE17_READBACK_AUTHORITY_BINDING = {
    "checker": {
        "path": (
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_"
            "readback_execution_permit_v1.py"
        ),
        "rawSha256": WAVE17_READBACK_CHECKER_RAW_SHA256,
    },
    "permit": {
        "contentSha256": WAVE17_CONTENT_SHA256[WAVE17_READBACK_PERMIT_PATH],
        "path": WAVE17_READBACK_PERMIT_PATH,
        "rawSha256": WAVE17_CONTROL_SHA256[WAVE17_READBACK_PERMIT_PATH],
    },
    "recorder": {
        "path": (
            "script/record_p2p_nat_g2_pion_rung3_dependency_wave17_"
            "readback_v1_once.py"
        ),
        "rawSha256": WAVE17_READBACK_RECORDER_RAW_SHA256,
    },
}
WAVE17_DECISION_TOOL_BINDINGS = [
    {
        "normalizedSha256":
            "226cb948492708f50e695c9d5e849c4f0acff11143625f473372c1bb59cec269",
        "path":
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_decision_v1.py",
        "role": "current_wave17_decision_checker",
    },
    {
        "normalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
        "path": V15_CHECKER_PATH,
        "rawSha256": V15_CHECKER_RAW_SHA256,
        "role": "immutable_combined_v15_checker",
    },
    {
        "path": V15_TESTS_PATH,
        "rawSha256": V15_TESTS_RAW_SHA256,
        "role": "immutable_combined_v15_tests",
    },
]
WAVE17_ACQUISITION_TOOL_BINDINGS = [
    {
        "path":
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py",
        "rawSha256": WAVE17_ACQUISITION_CHECKER_RAW_SHA256,
        "normalizedSha256":
            "6e653ff394c5e6f7d1dae9048ec34daecb9b7420121d19db01e772009acef959",
        "role": "wave17_acquisition_checker",
    },
    {
        "path":
            "script/test_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py",
        "rawSha256":
            "46e4508695dba47cfdb899a5f1ca5a4f9d2c1cb8e3e288babf0036daf632827c",
        "role": "wave17_acquisition_checker_tests",
    },
    {
        "path":
            "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py",
        "rawSha256": WAVE17_ACQUISITION_RUNNER_RAW_SHA256,
        "normalizedSha256":
            "4842e63aefaf6c1d0a07abbe9705a4c203ba398e4e7cfba3b698489f53a3f5f2",
        "role": "wave17_one_use_runner",
    },
    {
        "path":
            "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py",
        "rawSha256":
            "edaaf7e0c557ab9648b6caf651276cdf406da338eca03fb7ee77ecaefa7e283e",
        "role": "wave17_one_use_runner_tests",
    },
]
WAVE17_READBACK_TOOL_BINDINGS = [
    WAVE17_READBACK_AUTHORITY_BINDING["checker"],
    {
        "path": (
            "script/test_p2p_nat_g2_pion_rung3_dependency_wave17_"
            "readback_execution_permit_v1.py"
        ),
        "rawSha256":
            "30806750c7c9cdfadb59eded1f0449b79d9f119f687b246f02daed41c0c82831",
    },
    WAVE17_READBACK_AUTHORITY_BINDING["recorder"],
    {
        "path": (
            "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave17_"
            "readback_v1_once.py"
        ),
        "rawSha256":
            "83a4cb9e238d8feac4c518f11b53cee70da059990b521d87cc62c72ae5fa9727",
    },
]


class CombinedCheckFailure(RuntimeError):
    """A content-free, fail-closed checker error."""


class CliUsageFailure(RuntimeError):
    """A content-free command-line error."""


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise CliUsageFailure("E_ARGUMENT")


def check(condition: bool, code: str) -> None:
    if not condition:
        raise CombinedCheckFailure(code)


def exact_keys(value: Any, keys: Sequence[str]) -> bool:
    return type(value) is dict and set(value) == set(keys)


def exact_int(value: Any, expected: int) -> bool:
    return type(value) is int and value == expected


def exact_integer_items(
    value: Any,
    expected: Mapping[str, Any],
) -> bool:
    return (
        type(value) is dict
        and all(
            exact_int(value.get(key), expected_value)
            for key, expected_value in expected.items()
            if type(expected_value) is int
        )
    )


def exact_boolean_items(
    value: Any,
    expected: Mapping[str, Any],
) -> bool:
    return (
        type(value) is dict
        and all(
            value.get(key) is expected_value
            for key, expected_value in expected.items()
            if type(expected_value) is bool
        )
    )


def exact_boolean_map(value: Any, expected: Mapping[str, bool]) -> bool:
    return (
        type(value) is dict
        and set(value) == set(expected)
        and exact_boolean_items(value, expected)
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wave17_digest_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def normalized_self_bytes(raw: bytes) -> bytes:
    marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
    start = raw.find(marker)
    check(start >= 0, "E_SELF_IDENTITY")
    payload_start = start + len(marker)
    payload_end = raw.find(b'"\n)', payload_start)
    check(
        payload_end - payload_start == 64
        and raw.find(marker, payload_start) < 0,
        "E_SELF_IDENTITY",
    )
    return raw[:payload_start] + (b"0" * 64) + raw[payload_end:]


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def directory_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_gid,
    )


def retry_constructor_cleanup(resource: Any) -> None:
    """Retry once when a close failure leaves constructor-owned state."""

    for _ in range(2):
        try:
            resource.close()
        except BaseException:
            continue
        break


class PinnedCodeFile:
    """Open and retain one exact no-follow Python tool input."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str,
        normalizer: Any = None,
    ) -> None:
        self.root = root.absolute()
        self.relative_path = relative_path
        self.normalizer = normalizer
        self.root_fd = -1
        self.parent_fd = -1
        self.fd = -1
        self.owned_fds: list[int] = []
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.raw = b""
        try:
            parts = relative_path.split("/")
            check(
                parts
                and all(part not in {"", ".", ".."} for part in parts),
                "E_TOOL_IDENTITY",
            )
            self.root_fd = self._own(
                os.open(
                    self.root,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                )
            )
            self._validate_directory(os.fstat(self.root_fd))
            current = self._own(os.dup(self.root_fd))
            for component in parts[:-1]:
                child = self._own(
                    os.open(
                        component,
                        os.O_RDONLY
                        | os.O_DIRECTORY
                        | os.O_NOFOLLOW
                        | os.O_NONBLOCK
                        | os.O_CLOEXEC,
                        dir_fd=current,
                    )
                )
                info = os.fstat(child)
                self._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = parts[-1]
            self.fd = self._own(
                os.open(
                    self.name,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    dir_fd=self.parent_fd,
                )
            )
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial)
            first = self._read_pass()
            second = self._read_pass()
            checked = first if normalizer is None else normalizer(first)
            check(
                first == second
                and sha256_bytes(checked) == expected_sha256,
                "E_TOOL_IDENTITY",
            )
            self.raw = first
            self.final_barrier()
        except BaseException:
            retry_constructor_cleanup(self)
            raise

    def _own(self, fd: int) -> int:
        self.owned_fds.append(fd)
        return fd

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        check(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_TOOL_IDENTITY",
        )

    @staticmethod
    def _validate_file(info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= CODE_MAXIMUM_BYTES,
            "E_TOOL_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_TOOL_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_TOOL_IDENTITY")
        check(
            file_identity(os.fstat(self.fd)) == file_identity(before),
            "E_TOOL_IDENTITY",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        current = os.fstat(self.fd)
        named = os.stat(
            self.name,
            dir_fd=self.parent_fd,
            follow_symlinks=False,
        )
        check(
            file_identity(current)
            == file_identity(named)
            == file_identity(self.initial),
            "E_TOOL_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            check(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                == directory_identity(
                    os.stat(
                        component,
                        dir_fd=parent,
                        follow_symlinks=False,
                    )
                ),
                "E_TOOL_IDENTITY",
            )

    def close(self) -> None:
        errors: list[OSError] = []
        seen: set[int] = set()
        remaining: set[int] = set()

        def close_once(fd: int) -> None:
            if fd < 0 or fd in seen:
                return
            seen.add(fd)
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
                try:
                    os.fstat(fd)
                except OSError as probe_error:
                    if probe_error.errno != errno.EBADF:
                        remaining.add(fd)
                else:
                    remaining.add(fd)

        previous_owned = list(self.owned_fds)
        for owned_fd in reversed(previous_owned):
            close_once(owned_fd)
        self.owned_fds = [
            owned_fd
            for owned_fd in previous_owned
            if owned_fd in remaining
        ]
        self.directories.clear()
        self.fd = self.fd if self.fd in remaining else -1
        self.parent_fd = (
            self.parent_fd if self.parent_fd in remaining else -1
        )
        self.root_fd = self.root_fd if self.root_fd in remaining else -1
        if errors:
            raise errors[0]

    def __enter__(self) -> "PinnedCodeFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def safe_relative_path(value: Any) -> str:
    check(
        type(value) is str
        and bool(value)
        and not value.startswith("/")
        and "\x00" not in value
        and "\\" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/")),
        "E_HELD_SET",
    )
    return value


class SafeHeldFile:
    """Retain one provider input with immediate descriptor ownership."""

    def __init__(
        self,
        root_fd: int,
        relative: str,
        *,
        maximum_bytes: int,
        owner_only: bool,
    ) -> None:
        self.relative = safe_relative_path(relative)
        check(
            type(maximum_bytes) is int
            and maximum_bytes >= 1
            and type(owner_only) is bool,
            "E_HELD_SET",
        )
        self.maximum_bytes = maximum_bytes
        self.owner_only = owner_only
        self.directory_fds: list[
            tuple[int, os.stat_result, int, str]
        ] = []
        self.owned_fds: list[int] = []
        self.fd = -1
        self.parent_fd = -1
        try:
            current = self._own(os.dup(root_fd))
            for component in self.relative.split("/")[:-1]:
                child = self._own(
                    os.open(
                        component,
                        os.O_RDONLY
                        | os.O_DIRECTORY
                        | os.O_NOFOLLOW
                        | os.O_NONBLOCK
                        | os.O_CLOEXEC,
                        dir_fd=current,
                    )
                )
                info = os.fstat(child)
                self._validate_directory(info)
                self.directory_fds.append(
                    (child, info, current, component)
                )
                current = child
            self.parent_fd = current
            self.name = self.relative.rsplit("/", 1)[-1]
            self.fd = self._own(
                os.open(
                    self.name,
                    os.O_RDONLY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    dir_fd=self.parent_fd,
                )
            )
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial)
        except BaseException:
            retry_constructor_cleanup(self)
            raise

    def _own(self, fd: int) -> int:
        self.owned_fds.append(fd)
        return fd

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        check(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_HELD_SET",
        )

    def _validate_file(self, info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and 0 <= info.st_size <= self.maximum_bytes,
            "E_HELD_SET",
        )
        mode = stat.S_IMODE(info.st_mode)
        check(
            mode == 0o600 if self.owner_only else mode & 0o022 == 0,
            "E_HELD_SET",
        )

    def read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_HELD_SET")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_HELD_SET")
        check(
            file_identity(os.fstat(self.fd)) == file_identity(before),
            "E_HELD_SET",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        check(
            file_identity(os.fstat(self.fd))
            == file_identity(self.initial)
            == file_identity(
                os.stat(
                    self.name,
                    dir_fd=self.parent_fd,
                    follow_symlinks=False,
                )
            ),
            "E_HELD_SET",
        )
        for child, initial, parent, component in self.directory_fds:
            check(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                == directory_identity(
                    os.stat(
                        component,
                        dir_fd=parent,
                        follow_symlinks=False,
                    )
                ),
                "E_HELD_SET",
            )

    def close(self) -> None:
        errors: list[OSError] = []
        remaining: set[int] = set()
        for fd in reversed(self.owned_fds):
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
                try:
                    os.fstat(fd)
                except OSError as probe_error:
                    if probe_error.errno != errno.EBADF:
                        remaining.add(fd)
                else:
                    remaining.add(fd)
        self.owned_fds = [
            fd for fd in self.owned_fds if fd in remaining
        ]
        self.directory_fds.clear()
        self.fd = self.fd if self.fd in remaining else -1
        self.parent_fd = (
            self.parent_fd if self.parent_fd in remaining else -1
        )
        if errors:
            raise errors[0]


class SafeHeldInputSet:
    """Provider-compatible held set using only safe held files."""

    def __init__(
        self,
        root: Path,
        bindings: Sequence[Mapping[str, Any]],
    ) -> None:
        self.root = root
        self.root_fd = -1
        self.files: dict[str, SafeHeldFile] = {}
        self.raw: dict[str, bytes] = {}
        try:
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            SafeHeldFile._validate_directory(os.fstat(self.root_fd))
            paths: set[str] = set()
            for binding in bindings:
                path = safe_relative_path(binding.get("path"))
                check(path not in paths, "E_INPUT_INVENTORY")
                paths.add(path)
                expected = binding.get("rawSha256")
                maximum = binding.get("maximumBytes")
                owner_only = binding.get("ownerOnly")
                check(
                    type(expected) is str
                    and len(expected) == 64
                    and all(
                        character in "0123456789abcdef"
                        for character in expected
                    )
                    and type(maximum) is int
                    and maximum >= 1
                    and type(owner_only) is bool,
                    "E_INPUT_INVENTORY",
                )
                held = SafeHeldFile(
                    self.root_fd,
                    path,
                    maximum_bytes=maximum,
                    owner_only=owner_only,
                )
                self.files[path] = held
                first = held.read_pass()
                second = held.read_pass()
                check(
                    first == second and sha256_bytes(first) == expected,
                    "E_PREDECESSOR_IDENTITY",
                )
                self.raw[path] = first
            self.final_barrier()
        except BaseException:
            retry_constructor_cleanup(self)
            raise

    def final_barrier(self) -> None:
        for held in self.files.values():
            held.final_barrier()

    def close(self) -> None:
        errors: list[OSError] = []
        retained: dict[str, SafeHeldFile] = {}
        for path, held in list(self.files.items()):
            try:
                held.close()
            except OSError as error:
                errors.append(error)
                if held.owned_fds:
                    retained[path] = held
        self.files = retained
        if self.root_fd >= 0:
            root_fd = self.root_fd
            try:
                os.close(root_fd)
            except OSError as error:
                errors.append(error)
                try:
                    os.fstat(root_fd)
                except OSError as probe_error:
                    if probe_error.errno == errno.EBADF:
                        self.root_fd = -1
                else:
                    pass
            else:
                self.root_fd = -1
        if errors:
            raise errors[0]

    def __enter__(self) -> "SafeHeldInputSet":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class SafePinnedRunnerFile(PinnedCodeFile):
    """Provider pin adapter with the v1 constructor signature."""

    def __init__(self, root: Path) -> None:
        super().__init__(
            root,
            V1_PROVIDER_PATH,
            V1_PROVIDER_RAW_SHA256,
        )


class ReadOnlyOSProxy:
    """Expose provider filesystem reads while rejecting every write surface."""

    __slots__ = ()

    _READ_ATTRIBUTES = {
        "O_CLOEXEC",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_NONBLOCK",
        "O_RDONLY",
        "SEEK_SET",
        "close",
        "dup",
        "fstat",
        "geteuid",
        "listdir",
        "lseek",
        "lstat",
        "read",
        "stat",
        "stat_result",
    }
    _MUTATION_ATTRIBUTES = {
        "O_APPEND",
        "O_CREAT",
        "O_EXCL",
        "O_RDWR",
        "O_TMPFILE",
        "O_TRUNC",
        "O_WRONLY",
        "fchmod",
        "fsync",
        "link",
        "mkdir",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "symlink",
        "truncate",
        "unlink",
        "write",
    }

    @staticmethod
    def open(
        path: Any,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        write_mask = 0
        for name in (
            "O_APPEND",
            "O_CREAT",
            "O_EXCL",
            "O_RDWR",
            "O_TMPFILE",
            "O_TRUNC",
            "O_WRONLY",
        ):
            write_mask |= getattr(os, name, 0)
        check(
            type(flags) is int and flags & write_mask == 0,
            "E_TRANSITIVE_WRITE",
        )
        if dir_fd is None:
            return os.open(path, flags, mode)
        return os.open(path, flags, mode, dir_fd=dir_fd)

    def __getattr__(self, name: str) -> Any:
        if name in self._MUTATION_ATTRIBUTES:
            raise CombinedCheckFailure("E_TRANSITIVE_WRITE")
        if name in self._READ_ATTRIBUTES:
            return getattr(os, name)
        raise AttributeError(name)

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_TRANSITIVE_WRITE")


class ReadOnlyZipArchive:
    """Minimal read-only ZipFile view used by graph reconstruction."""

    def __init__(
        self,
        file: Any,
        mode: str = "r",
        *,
        allowZip64: bool = True,
    ) -> None:
        check(mode == "r", "E_TRANSITIVE_WRITE")
        self._archive = zipfile.ZipFile(
            file,
            mode="r",
            allowZip64=allowZip64,
        )

    def infolist(self) -> list[zipfile.ZipInfo]:
        return self._archive.infolist()

    def read(
        self,
        name: str | zipfile.ZipInfo,
        pwd: bytes | None = None,
    ) -> bytes:
        return self._archive.read(name, pwd=pwd)

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> "ReadOnlyZipArchive":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class ReadOnlyZipFacade:
    __slots__ = ("ZipFile",)
    BadZipFile = zipfile.BadZipFile
    ZIP_DEFLATED = zipfile.ZIP_DEFLATED
    ZIP_STORED = zipfile.ZIP_STORED

    def __init__(self) -> None:
        object.__setattr__(
            self,
            "ZipFile",
            ReadOnlyProviderCallable(ReadOnlyZipArchive),
        )

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_PROVIDER_FACADE")


class ReadOnlyIOFacade:
    __slots__ = ()
    BytesIO = io.BytesIO


class SafeReviewFailure(RuntimeError):
    """Provider-compatible error without provider-module globals."""

    def __init__(
        self,
        code: str,
        phase: str,
        *,
        tuple_id: str | None = None,
        tuple_order: int | None = None,
        resource_kind: str | None = None,
        observations: Mapping[str, int] | None = None,
    ) -> None:
        safe_code = code if type(code) is str else "E_INTERNAL"
        safe_phase = phase if type(phase) is str else "runner"
        super().__init__(safe_code)
        self.code = safe_code
        self.phase = safe_phase
        self.tuple_id = tuple_id if type(tuple_id) is str else None
        self.tuple_order = (
            tuple_order if type(tuple_order) is int else None
        )
        self.resource_kind = (
            resource_kind if type(resource_kind) is str else None
        )
        self.observations = dict(
            sorted(
                (key, value)
                for key, value in (observations or {}).items()
                if type(key) is str
                and type(value) is int
                and 0 <= value <= (1 << 53) - 1
            )
        )


class ReadOnlyProviderCallable:
    """Callable wrapper that does not expose raw provider globals."""

    __slots__ = ("__target",)

    def __init__(self, target: Any) -> None:
        object.__setattr__(
            self,
            "_ReadOnlyProviderCallable__target",
            target,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        target = object.__getattribute__(
            self,
            "_ReadOnlyProviderCallable__target",
        )
        return target(*args, **kwargs)

    def __getattribute__(self, name: str) -> Any:
        if name in {
            "__closure__",
            "__code__",
            "__defaults__",
            "__globals__",
            "__kwdefaults__",
            "_ReadOnlyProviderCallable__target",
            "_target",
        }:
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_PROVIDER_FACADE")


class ReadOnlyProviderFacade:
    """Immutable allow-list facade over pinned provider functions."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        object.__setattr__(
            self,
            "_values",
            types.MappingProxyType(dict(values)),
        )

    def __getattr__(self, name: str) -> Any:
        values = object.__getattribute__(self, "_values")
        try:
            return values[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __getattribute__(self, name: str) -> Any:
        if name == "_values":
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __setattr__(self, _: str, __: Any) -> None:
        raise CombinedCheckFailure("E_PROVIDER_FACADE")

    def __dir__(self) -> list[str]:
        values = object.__getattribute__(self, "_values")
        return sorted(values)


PROVIDER_API = (
    "DEFAULT_MAXIMUM_AGGREGATE_ENTRIES",
    "DEFAULT_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES",
    "DEFAULT_MAXIMUM_ARCHIVE_BYTES",
    "DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE",
    "DEFAULT_MAXIMUM_ENTRY_BYTES",
    "DEFAULT_MAXIMUM_GRAPH_EDGES",
    "DEFAULT_MAXIMUM_GRAPH_NODES",
    "GRAPH_ALGORITHM",
    "ReviewFailure",
    "_eocd_exact",
    "build_graph",
    "canonical_json_bytes",
    "content_bound",
    "exact_int",
    "extract_build_expression",
    "go_proxy_escape",
    "has_zip64_extra",
    "inspect_zip_bytes",
    "is_license_path",
    "parse_go_imports",
    "parse_go_mod",
    "profile_rows",
    "require",
    "safe_archive_name",
    "source_class",
    "special_classes",
    "strict_json",
)


WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT = 0


def pinned_wave9_extract_build_expression(target: Any) -> Any:
    """Permit one exact legacy trailing-comment parser compatibility case."""

    def extract(text: str) -> str | None:
        global WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
        try:
            return target(text)
        except SafeReviewFailure as error:
            raw = text.encode("utf-8", errors="strict")
            if not (
                error.code == "E_BUILD_CONSTRAINT"
                and error.phase == "source_inventory"
                and sha256_bytes(raw) == WAVE9_LEGACY_BUILD_SOURCE_SHA256
                and text.count(WAVE9_LEGACY_BUILD_ORIGINAL_LINE) == 1
            ):
                raise
            normalized = text.replace(
                WAVE9_LEGACY_BUILD_ORIGINAL_LINE,
                WAVE9_LEGACY_BUILD_NORMALIZED_LINE,
            )
            check(
                sha256_bytes(normalized.encode("utf-8", errors="strict"))
                == WAVE9_LEGACY_BUILD_NORMALIZED_SHA256,
                "E_WAVE9_BUILD_COMPATIBILITY",
            )
            expression = target(normalized)
            check(
                expression == WAVE9_LEGACY_BUILD_EXPRESSION,
                "E_WAVE9_BUILD_COMPATIBILITY",
            )
            WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT += 1
            return expression

    return extract


def validate_wave9_legacy_build_profile_equivalence(
    profiles: Sequence[Mapping[str, Any]],
) -> None:
    """Prove the pinned compatibility edit cannot change profile inclusion."""

    check(
        type(profiles) is list
        and len(profiles) == 2
        and {
            row.get("profileId")
            for row in profiles
            if type(row) is dict
        }
        == {
            "android_api_26_through_36_arm64_v8a",
            "macos_14_or_newer_arm64",
        },
        "E_WAVE9_BUILD_COMPATIBILITY",
    )
    for profile in profiles:
        tags_value = profile.get("tags")
        check(
            type(tags_value) is list
            and all(type(tag) is str for tag in tags_value),
            "E_WAVE9_BUILD_COMPATIBILITY",
        )
        tags = set(tags_value)
        stripped_active = (
            "go1.8" in tags
            and "go1.9" not in tags
            and "windows" not in tags
        )
        trailing_or_active = any(
            option in tags
            for option in WAVE9_LEGACY_BUILD_TRAILING_OR_OPTIONS
        )
        go111_legacy_active = (
            (
                ("go1.8" in tags and "go1.9" not in tags)
                or trailing_or_active
            )
            and "windows" not in tags
        )
        check(
            stripped_active is False
            and go111_legacy_active is False
            and stripped_active is go111_legacy_active,
            "E_WAVE9_BUILD_COMPATIBILITY",
        )


def validate_wave9_legacy_build_compatibility_count(value: Any) -> None:
    check(
        type(value) is int
        and not isinstance(value, bool)
        and value == 4,
        "E_WAVE9_BUILD_COMPATIBILITY",
    )


def load_provider_facade(held: SafePinnedRunnerFile) -> ReadOnlyProviderFacade:
    check(
        type(held) is SafePinnedRunnerFile
        and sha256_bytes(held.raw) == V1_PROVIDER_RAW_SHA256,
        "E_PROVIDER_IDENTITY",
    )
    module = types.ModuleType("aetherlink_read_only_graph_provider_v1")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V1_PROVIDER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_read_only_graph_provider_v1",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V1_PROVIDER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_PROVIDER_LOAD") from error
    check(
        all(hasattr(module, name) for name in PROVIDER_API),
        "E_PROVIDER_API",
    )
    os_proxy = ReadOnlyOSProxy()
    io_facade = ReadOnlyIOFacade()
    zip_facade = ReadOnlyZipFacade()
    module.os = os_proxy
    module.io = io_facade
    module.zipfile = zip_facade
    module.ReviewFailure = SafeReviewFailure
    module.HeldFile = SafeHeldFile
    module.HeldInputSet = SafeHeldInputSet
    values: dict[str, Any] = {}
    for name in PROVIDER_API:
        value = getattr(module, name)
        if name == "extract_build_expression":
            value = pinned_wave9_extract_build_expression(value)
        values[name] = (
            ReadOnlyProviderCallable(value)
            if callable(value) and name != "ReviewFailure"
            else value
        )
    values.update(
        {
            "HeldInputSet": ReadOnlyProviderCallable(SafeHeldInputSet),
            "io": io_facade,
            "zipfile": zip_facade,
        }
    )
    return ReadOnlyProviderFacade(values)


HARDENED_CHECKER_PATHS: set[str] = set()
PROVIDER_FACADE_LOAD_COUNT = 0


def harden_checker_module(module: types.ModuleType) -> types.ModuleType:
    """Recursively replace every transitive pin and provider loader."""

    if module.__dict__.get("_v16_safe_hardened") is True:
        return module
    module.__dict__["_v16_safe_hardened"] = True
    module_path = str(module.__dict__.get("__file__", ""))
    HARDENED_CHECKER_PATHS.add(module_path)
    if "PinnedCodeFile" in module.__dict__:
        module.PinnedCodeFile = PinnedCodeFile
    for name, value in list(module.__dict__.items()):
        if not (
            name.startswith("load_v")
            and name.endswith("_checker")
            and callable(value)
        ):
            continue

        def recursive_loader(
            held: PinnedCodeFile,
            *,
            _loader: Any = value,
        ) -> types.ModuleType:
            child = _loader(held)
            check(type(child) is types.ModuleType, "E_CHECKER_HARDENING")
            return harden_checker_module(child)

        recursive_loader.__name__ = name
        module.__dict__[name] = recursive_loader
    if "load_pinned_runner" in module.__dict__:
        module.PinnedRunnerFile = SafePinnedRunnerFile

        def safe_provider_loader(
            held: SafePinnedRunnerFile,
        ) -> ReadOnlyProviderFacade:
            global PROVIDER_FACADE_LOAD_COUNT
            PROVIDER_FACADE_LOAD_COUNT += 1
            return load_provider_facade(held)

        module.load_pinned_runner = safe_provider_loader
    return module


def load_v15_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v15_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V15_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v15_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V15_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V15_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v14_checker",
        "wave16_control_bindings",
        "parse_wave16_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V15_CHECKER_API")
    check(
        module.SELF_PATH == V15_CHECKER_PATH
        and sha256_bytes(held.raw) == V15_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V15_CHECKER_NORMALIZED_SHA256,
        "E_V15_CHECKER_PIN",
    )
    return module


def load_v14_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v14_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V14_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v14_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V14_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V14_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v13_checker",
        "wave15_control_bindings",
        "parse_wave15_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V14_CHECKER_API")
    check(
        module.SELF_PATH == V14_CHECKER_PATH
        and sha256_bytes(held.raw) == V14_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V14_CHECKER_NORMALIZED_SHA256,
        "E_V14_CHECKER_PIN",
    )
    return module


def load_v13_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v13_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V13_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v13_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V13_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V13_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v12_checker",
        "wave14_control_bindings",
        "parse_wave14_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V13_CHECKER_API")
    check(
        module.SELF_PATH == V13_CHECKER_PATH
        and sha256_bytes(held.raw) == V13_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V13_CHECKER_NORMALIZED_SHA256,
        "E_V13_CHECKER_PIN",
    )
    return module


def load_v12_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v12_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V12_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v12_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V12_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V12_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v11_checker",
        "wave13_control_bindings",
        "parse_wave13_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V12_CHECKER_API")
    check(
        module.SELF_PATH == V12_CHECKER_PATH
        and sha256_bytes(held.raw) == V12_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V12_CHECKER_NORMALIZED_SHA256,
        "E_V12_CHECKER_PIN",
    )
    return module


def load_v11_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v11_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V11_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v11_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V11_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V11_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v10_checker",
        "wave12_control_bindings",
        "parse_wave12_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V11_CHECKER_API")
    check(
        module.SELF_PATH == V11_CHECKER_PATH
        and sha256_bytes(held.raw) == V11_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V11_CHECKER_NORMALIZED_SHA256,
        "E_V11_CHECKER_PIN",
    )
    return module


def load_v10_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v10_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V10_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v10_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V10_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V10_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v9_checker",
        "wave11_control_bindings",
        "parse_wave11_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V10_CHECKER_API")
    check(
        module.SELF_PATH == V10_CHECKER_PATH
        and sha256_bytes(held.raw) == V10_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V10_CHECKER_NORMALIZED_SHA256,
        "E_V10_CHECKER_PIN",
    )
    return module


def load_v9_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v9_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V9_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v9_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V9_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V9_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v8_checker",
        "wave10_control_bindings",
        "parse_wave10_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V9_CHECKER_API")
    check(
        module.SELF_PATH == V9_CHECKER_PATH
        and sha256_bytes(held.raw) == V9_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V9_CHECKER_NORMALIZED_SHA256,
        "E_V9_CHECKER_PIN",
    )
    return module


def load_v8_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v8_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V8_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v8_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V8_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V8_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v7_checker",
        "wave9_control_bindings",
        "parse_wave9_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V8_CHECKER_API")
    check(
        module.SELF_PATH == V8_CHECKER_PATH
        and sha256_bytes(held.raw) == V8_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V8_CHECKER_NORMALIZED_SHA256,
        "E_V8_CHECKER_PIN",
    )
    return module


def load_v7_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v7_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V7_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v7_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V7_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V7_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v6_checker",
        "wave8_control_bindings",
        "parse_wave8_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V7_CHECKER_API")
    check(
        module.SELF_PATH == V7_CHECKER_PATH
        and sha256_bytes(held.raw) == V7_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V7_CHECKER_NORMALIZED_SHA256,
        "E_V7_CHECKER_PIN",
    )
    return module


def load_v6_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_v6_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V6_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_v6_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V6_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V6_CHECKER_LOAD") from error
    for name in (
        "PinnedCodeFile",
        "load_v5_checker",
        "wave7_control_bindings",
        "parse_wave7_documents",
        "combined_source_bindings",
        "generate_candidate",
    ):
        check(callable(getattr(module, name, None)), "E_V6_CHECKER_API")
    check(
        module.SELF_PATH == V6_CHECKER_PATH
        and sha256_bytes(held.raw) == V6_CHECKER_RAW_SHA256
        and sha256_bytes(normalized_self_bytes(held.raw))
        == V6_CHECKER_NORMALIZED_SHA256,
        "E_V6_CHECKER_API",
    )
    return module


def wave17_control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": WAVE17_CONTROL_METADATA[path][1] == 0o600,
            "kind": "terminal_evidence",
        }
        for path, digest in WAVE17_CONTROL_SHA256.items()
    ]


def parse_wave17_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in WAVE17_CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_WAVE17_JSON")
        result[path] = value
    return result


def wave17_auxiliary_evidence_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": WAVE17_ACQUISITION_CLAIM_PATH,
            "rawSha256": WAVE17_ACQUISITION_CLAIM_RAW_SHA256,
            "maximumBytes": 416,
            "ownerOnly": True,
            "kind": "consumed_acquisition_claim",
        },
        {
            "path": WAVE17_EVIDENCE_PATH,
            "rawSha256": WAVE17_ACQUISITION_EVIDENCE_RAW_SHA256,
            "maximumBytes": 1_100,
            "ownerOnly": True,
            "kind": "frozen_acquisition_evidence",
        },
        {
            "path": WAVE17_READBACK_CLAIM_PATH,
            "rawSha256": WAVE17_READBACK_CLAIM_RAW_SHA256,
            "maximumBytes": 1_255,
            "ownerOnly": True,
            "kind": "consumed_readback_claim",
        },
    ]


def portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def validate_wave17_completed_namespace(
    control_held: Any,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    acquisition_claim = control_held.files[WAVE17_ACQUISITION_CLAIM_PATH]
    readback_claim = control_held.files[WAVE17_READBACK_CLAIM_PATH]
    evidence = control_held.files[WAVE17_EVIDENCE_PATH]
    readback = control_held.files[WAVE17_READBACK_PATH]
    readback_manifest = control_held.files[WAVE17_READBACK_MANIFEST_PATH]
    for path, (expected_bytes, expected_mode) in WAVE17_CONTROL_METADATA.items():
        info = os.fstat(control_held.files[path].fd)
        check(
            info.st_uid == os.geteuid()
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == expected_mode
            and info.st_size == expected_bytes,
            "E_WAVE17_CONTROL_METADATA",
        )
    for held, expected_bytes in (
        (acquisition_claim, 416),
        (evidence, 1_100),
        (readback_claim, 1_255),
    ):
        info = os.fstat(held.fd)
        check(
            info.st_uid == os.geteuid()
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == expected_bytes,
            "E_WAVE17_AUXILIARY_METADATA",
        )

    dependency_names = os.listdir(acquisition_claim.parent_fd)
    base_names = os.listdir(readback.parent_fd)
    final_names = os.listdir(evidence.parent_fd)
    normalized_dependency_names = [
        portable_name(name) for name in dependency_names
    ]
    normalized_base_names = [portable_name(name) for name in base_names]
    normalized_final_names = [portable_name(name) for name in final_names]
    exact_dependency_names = {
        Path(WAVE17_ACQUISITION_CLAIM_PATH).name,
        Path(WAVE17_READBACK_CLAIM_PATH).name,
    }
    exact_base_names = {
        Path(path).name for path in WAVE17_CONTROL_SHA256
    }
    exact_final_names = {"accepted", "evidence.json"}
    check(
        all(
            normalized_dependency_names.count(portable_name(name)) == 1
            for name in exact_dependency_names
        )
        and all(
            normalized_base_names.count(portable_name(name)) == 1
            for name in exact_base_names
        )
        and not any(
            name.startswith(portable_name(WAVE17_STAGING_PREFIX))
            for name in normalized_dependency_names
        )
        and portable_name(Path(WAVE17_FAILURE_PATH).name)
        not in normalized_base_names
        and not any(
            name.startswith(portable_name(prefix))
            for name in normalized_base_names
            for prefix in WAVE17_READBACK_TEMP_PREFIXES
        )
        and len(final_names) == len(exact_final_names)
        and set(final_names) == exact_final_names
        and len(set(normalized_final_names)) == len(exact_final_names),
        "E_WAVE17_NAMESPACE",
    )
    check(
        readback.parent_fd == readback_manifest.parent_fd
        or directory_identity(os.fstat(readback.parent_fd))
        == directory_identity(os.fstat(readback_manifest.parent_fd)),
        "E_WAVE17_NAMESPACE",
    )
    final_info = os.fstat(evidence.parent_fd)
    check(
        final_info.st_uid == os.geteuid()
        and final_info.st_nlink == 4
        and stat.S_IMODE(final_info.st_mode) == 0o700,
        "E_WAVE17_NAMESPACE",
    )

    readback_permit = documents[WAVE17_READBACK_PERMIT_PATH]
    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    accepted = (
        snapshot.get("acceptedDirectory")
        if type(snapshot) is dict
        else None
    )
    accepted_files = (
        accepted.get("files") if type(accepted) is dict else None
    )
    check(
        type(accepted_files) is list and len(accepted_files) == 2,
        "E_WAVE17_NAMESPACE",
    )
    expected_accepted_names = {
        Path(row.get("path", "")).name
        for row in accepted_files
        if type(row) is dict and type(row.get("path")) is str
    }
    check(
        len(expected_accepted_names) == 2
        and all(
            Path(row["path"]).parent.as_posix() == WAVE17_ACCEPTED_DIRECTORY
            for row in accepted_files
        ),
        "E_WAVE17_NAMESPACE",
    )
    accepted_fd = -1
    try:
        accepted_fd = os.open(
            "accepted",
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC,
            dir_fd=evidence.parent_fd,
        )
        accepted_info = os.fstat(accepted_fd)
        accepted_names = os.listdir(accepted_fd)
        normalized_accepted_names = [
            portable_name(name) for name in accepted_names
        ]
        check(
            accepted_info.st_uid == os.geteuid()
            and accepted_info.st_nlink == 4
            and stat.S_IMODE(accepted_info.st_mode) == 0o700
            and len(accepted_names) == 2
            and set(accepted_names) == expected_accepted_names
            and len(set(normalized_accepted_names)) == 2,
            "E_WAVE17_NAMESPACE",
        )
    finally:
        if accepted_fd >= 0:
            os.close(accepted_fd)


def validate_wave17_consumed_claims(
    runner: types.ModuleType,
    acquisition_raw: bytes,
    readback_raw: bytes,
) -> None:
    acquisition_claim = runner.strict_json(
        acquisition_raw,
        WAVE17_ACQUISITION_CLAIM_PATH,
    )
    readback_claim = runner.strict_json(
        readback_raw,
        WAVE17_READBACK_CLAIM_PATH,
    )
    check(
        acquisition_raw == runner.canonical_json_bytes(acquisition_claim)
        and exact_keys(
            acquisition_claim,
            (
                "attemptId", "checkerRawSha256", "documentType",
                "externalAuthenticationRequired", "permitContentSha256",
                "requestCount", "schemaVersion", "status",
                "userActionRequired",
            ),
        )
        and acquisition_claim
        == {
            "attemptId": WAVE17_ATTEMPT_ID,
            "checkerRawSha256": WAVE17_ACQUISITION_CHECKER_RAW_SHA256,
            "documentType": "aetherlink.wave17-source-acquisition-claim",
            "externalAuthenticationRequired": False,
            "permitContentSha256": WAVE17_CONTENT_SHA256[WAVE17_PERMIT_PATH],
            "requestCount": 2,
            "schemaVersion": "1.0",
            "status": "consumed_active",
            "userActionRequired": False,
        },
        "E_WAVE17_ACQUISITION_CLAIM",
    )
    check(
        exact_int(acquisition_claim.get("requestCount"), 2)
        and exact_boolean_items(
            acquisition_claim,
            {
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            },
        ),
        "E_WAVE17_ACQUISITION_CLAIM",
    )
    without = dict(readback_claim)
    without.pop("contentBinding", None)
    check(
        readback_raw == runner.canonical_json_bytes(readback_claim)
        and exact_keys(
            readback_claim,
            (
                "acquisitionAttemptId", "authorityBinding",
                "claimPersistsAfterSuccessFailureOrUncertainty",
                "contentBinding", "documentType",
                "externalAuthenticationRequired", "readbackAttemptId",
                "retryAllowed", "schemaVersion", "status",
                "userActionRequired",
            ),
        )
        and readback_claim.get("contentBinding")
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE17_READBACK_CLAIM_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == WAVE17_READBACK_CLAIM_CONTENT_SHA256
        and readback_claim.get("acquisitionAttemptId") == WAVE17_ATTEMPT_ID
        and readback_claim.get("readbackAttemptId")
        == WAVE17_READBACK_ATTEMPT_ID
        and readback_claim.get("authorityBinding")
        == WAVE17_READBACK_AUTHORITY_BINDING
        and readback_claim.get("documentType")
        == "aetherlink.wave17-acquisition-readback-one-use-claim"
        and readback_claim.get(
            "claimPersistsAfterSuccessFailureOrUncertainty"
        )
        is True
        and readback_claim.get("retryAllowed") is False
        and readback_claim.get("schemaVersion") == "1.0"
        and readback_claim.get("status") == "consumed_active"
        and readback_claim.get("externalAuthenticationRequired") is False
        and readback_claim.get("userActionRequired") is False,
        "E_WAVE17_READBACK_CLAIM",
    )


def validate_wave17_evidence(
    runner: types.ModuleType,
    raw: bytes,
    evidence_document: Mapping[str, Any],
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    check(type(evidence_document) is dict, "E_WAVE17_EVIDENCE")
    readback = documents[WAVE17_READBACK_PATH]
    verified = readback.get("verified")
    evidence_resources = evidence_document.get("resources")
    verified_resources = (
        verified.get("resources") if type(verified) is dict else None
    )
    check(
        exact_keys(
            evidence_document,
            (
                "aggregateModResponseBytes", "aggregateResponseBytes",
                "aggregateZipEntryCount", "aggregateZipResponseBytes",
                "aggregateZipUncompressedBytes", "attemptId",
                "documentType", "requestCount", "resources",
                "schemaVersion",
            ),
        )
        and raw == runner.canonical_json_bytes(evidence_document)
        and sha256_bytes(raw) == WAVE17_ACQUISITION_EVIDENCE_RAW_SHA256
        and evidence_document.get("documentType")
        == "aetherlink.wave17-source-acquisition-evidence"
        and evidence_document.get("schemaVersion") == "1.0"
        and evidence_document.get("attemptId") == WAVE17_ATTEMPT_ID
        and exact_int(evidence_document.get("requestCount"), 2)
        and exact_int(
            evidence_document.get("aggregateResponseBytes"),
            3_450_700,
        )
        and exact_int(
            evidence_document.get("aggregateModResponseBytes"),
            301,
        )
        and exact_int(
            evidence_document.get("aggregateZipResponseBytes"),
            3_450_399,
        )
        and exact_int(
            evidence_document.get("aggregateZipEntryCount"),
            1_550,
        )
        and exact_int(
            evidence_document.get("aggregateZipUncompressedBytes"),
            9_108_004,
        )
        and type(evidence_resources) is list
        and len(evidence_resources) == 2
        and type(verified_resources) is list
        and runner.canonical_json_bytes(evidence_resources)
        == runner.canonical_json_bytes(verified_resources),
        "E_WAVE17_EVIDENCE",
    )


def verify_wave17_content_bindings(
    v4: types.ModuleType,
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    v4.verify_modern_content_binding(
        runner,
        documents[WAVE17_DECISION_PATH],
        WAVE17_CONTENT_SHA256[WAVE17_DECISION_PATH],
        "decision_without_contentBinding",
    )
    v4.verify_modern_content_binding(
        runner,
        documents[WAVE17_PERMIT_PATH],
        WAVE17_CONTENT_SHA256[WAVE17_PERMIT_PATH],
        "permit_without_contentBinding",
    )
    for path in (
        WAVE17_READBACK_PERMIT_PATH,
        WAVE17_READBACK_PATH,
        WAVE17_READBACK_MANIFEST_PATH,
    ):
        v4.verify_content_binding(
            runner,
            documents[path],
            WAVE17_CONTENT_SHA256[path],
        )


def validate_v15_predecessor_candidate(
    runner: types.ModuleType,
    candidate: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    predecessor = decision.get("predecessorBindings", {}).get(
        "combinedFixedPointV15"
    )
    binding = candidate.get("contentBinding")
    without = dict(candidate)
    without.pop("contentBinding", None)
    inputs = candidate.get("inputSet")
    source_bindings = (
        inputs.get("sourceBindings") if type(inputs) is dict else None
    )
    graph = candidate.get("graphDiscovery")
    frontier = graph.get("exactFrontier") if type(graph) is dict else None
    identity_resolution = decision.get("identityResolution")
    identity_tuples = (
        identity_resolution.get("tuples")
        if type(identity_resolution) is dict
        else None
    )
    source_keys = {
        "kind",
        "module",
        "path",
        "rawSha256",
        "tupleId",
        "tupleOrder",
        "version",
        "wave",
    }
    check(
        exact_keys(
            decision.get("predecessorBindings"),
            ("combinedFixedPointV15",),
        )
        and type(source_bindings) is list
        and len(source_bindings) == 357
        and all(
            type(row) is dict
            and set(row) == source_keys
            and row["kind"] in {"root_zip", "mod", "zip"}
            and type(row["module"]) is str
            and type(row["path"]) is str
            and type(row["rawSha256"]) is str
            and len(row["rawSha256"]) == 64
            and all(
                character in "0123456789abcdef"
                for character in row["rawSha256"]
            )
            and type(row["tupleId"]) is str
            and type(row["tupleOrder"]) is int
            and type(row["version"]) is str
            and type(row["wave"]) is str
            for row in source_bindings
        ),
        "E_V15_PREDECESSOR",
    )
    source_pairs: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in source_bindings:
        if row["kind"] != "root_zip":
            source_pairs[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        type(predecessor) is dict
        and exact_keys(
            predecessor,
            (
                "checkerNormalizedSha256", "checkerPath",
                "checkerRawSha256", "combinedInputSetSha256",
                "contentSha256", "fixedPointReached",
                "frontierSha256", "frontierTupleCount", "graphSha256",
                "sourceBindingCount", "sourceBindingsSha256",
                "testsPath", "testsRawSha256",
                "totalFullSourceReconstructionCount",
                "totalGraphArchiveOpenCount", "wave16NamespaceAnchor",
            ),
        )
        and predecessor.get("contentSha256")
        == V15_CANDIDATE_CONTENT_SHA256
        and predecessor.get("combinedInputSetSha256")
        == V15_INPUT_SET_SHA256
        and predecessor.get("sourceBindingsSha256")
        == V15_SOURCE_BINDINGS_SHA256
        and predecessor.get("graphSha256") == V15_GRAPH_SHA256
        and predecessor.get("frontierSha256") == V15_FRONTIER_SHA256
        and exact_int(predecessor.get("frontierTupleCount"), 1)
        and predecessor.get("fixedPointReached") is False
        and predecessor.get("checkerPath") == V15_CHECKER_PATH
        and predecessor.get("checkerRawSha256") == V15_CHECKER_RAW_SHA256
        and predecessor.get("checkerNormalizedSha256")
        == V15_CHECKER_NORMALIZED_SHA256
        and predecessor.get("testsPath") == V15_TESTS_PATH
        and predecessor.get("testsRawSha256") == V15_TESTS_RAW_SHA256
        and exact_int(
            predecessor.get("totalFullSourceReconstructionCount"),
            28,
        )
        and exact_int(
            predecessor.get("totalGraphArchiveOpenCount"),
            3_696,
        )
        and exact_int(predecessor.get("sourceBindingCount"), 357)
        and predecessor.get("wave16NamespaceAnchor")
        == {
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-16-v1.claim"
            ),
            "rawSha256": (
                "df97f5d9bf8c56f3bbf08635b8332bbc18b25babd0e5f35742fee3657555f4b8"
            ),
        }
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "wave9PinnedLegacyBuildCompatibilityCount"
            ),
            4,
        )
        and candidate.get("checkerVerification", {}).get(
            "pinnedV14PredecessorExecuted"
        ) is True
        and candidate.get("checkerVerification", {}).get(
            "v14TestsBindingScope"
        ) == "historical_metadata_only_not_live_held"
        and candidate.get("checkerVerification", {}).get(
            "v14TestsLiveHeld"
        ) is False
        and candidate.get("checkerVerification", {}).get(
            "wave16HistoricalExact25FrozenSnapshotDescriptorSetBound"
        ) is True
        and candidate.get("checkerVerification", {}).get(
            "wave16LiveTerminalControlMetadataVerified"
        ) is True
        and candidate.get("checkerVerification", {}).get(
            "wave16LiveFinalAndAcceptedInventoriesVerified"
        ) is True
        and candidate.get("checkerVerification", {}).get(
            "wave16FinalNamespaceReverifiedAfterReconstruction"
        ) is True
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "wave16RetainedFdPreManifestBarrierCount"
            ),
            3,
        )
        and candidate.get("checkerVerification", {}).get(
            "wave16CompletionAppliesToRetainedSnapshot"
        ) is True
        and candidate.get("checkerVerification", {}).get(
            "wave16CurrentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and candidate.get("checkerVerification", {}).get(
            "wave16SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and candidate.get("checkerVerification", {}).get(
            "providerFacadeVerificationScope"
        ) == "trusted_pinned_normal_reconstruction_path"
        and exact_int(
            candidate.get("operationCounters", {}).get(
                "wave9PinnedLegacyBuildCompatibilityCount"
            ),
            4,
        )
        and exact_int(
            candidate.get("operationCounters", {}).get("fileWriteCount"),
            0,
        )
        and candidate.get("authority", {}).get("osSyscallSandboxProvided")
        is False
        and type(binding) is dict
        and binding
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "candidate_without_contentBinding",
            "sha256": V15_CANDIDATE_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == V15_CANDIDATE_CONTENT_SHA256
        and candidate.get("schemaVersion") == "15.0"
        and candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
            "wave5-wave6-wave7-wave8-wave9-wave10-wave11-wave12-wave13-"
            "wave14-wave15-wave16-"
            "fixed-point-candidate"
        )
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and candidate.get("result")
        == (
            "combined_graph_recomputed_twice_from_exact_"
            "wave1_through_wave16_source_bytes"
        )
        and candidate.get("route") == "next_wave_required"
        and candidate.get("nextAction")
        == (
            "prepare_separate_versioned_dependency_wave_identity_and_"
            "acquisition_decision"
        )
        and candidate.get("derivedResult")
        == {
            "fixedPointReached": False,
            "frontierTupleCount": 1,
            "frontierSha256": V15_FRONTIER_SHA256,
        }
        and candidate.get("derivedResult", {}).get("fixedPointReached")
        is False
        and exact_int(
            candidate.get("derivedResult", {}).get("frontierTupleCount"),
            1,
        )
        and type(inputs) is dict
        and exact_int(inputs.get("heldSourceInputCount"), 357)
        and inputs.get("combinedInputSetSha256") == V15_INPUT_SET_SHA256
        and sha256_bytes(runner.canonical_json_bytes(source_bindings))
        == V15_INPUT_SET_SHA256
        and sha256_bytes(wave17_digest_bytes(source_bindings))
        == V15_SOURCE_BINDINGS_SHA256
        and len({row["path"] for row in source_bindings}) == 357
        and sum(row["kind"] == "root_zip" for row in source_bindings) == 1
        and sum(row["kind"] == "mod" for row in source_bindings) == 178
        and sum(row["kind"] == "zip" for row in source_bindings) == 178
        and sum(row["wave"] == "wave1" for row in source_bindings) == 38
        and sum(row["wave"] == "wave2" for row in source_bindings) == 30
        and sum(row["wave"] == "wave3" for row in source_bindings) == 32
        and sum(row["wave"] == "wave4" for row in source_bindings) == 32
        and sum(row["wave"] == "wave5" for row in source_bindings) == 30
        and sum(row["wave"] == "wave6" for row in source_bindings) == 36
        and sum(row["wave"] == "wave7" for row in source_bindings) == 30
        and sum(row["wave"] == "wave8" for row in source_bindings) == 28
        and sum(row["wave"] == "wave9" for row in source_bindings) == 20
        and sum(row["wave"] == "wave10" for row in source_bindings) == 22
        and sum(row["wave"] == "wave11" for row in source_bindings) == 18
        and sum(row["wave"] == "wave12" for row in source_bindings) == 8
        and sum(row["wave"] == "wave13" for row in source_bindings) == 8
        and sum(row["wave"] == "wave14" for row in source_bindings) == 8
        and sum(row["wave"] == "wave15" for row in source_bindings) == 10
        and sum(row["wave"] == "wave16" for row in source_bindings) == 6
        and len(source_pairs) == 178
        and all(kinds == {"mod", "zip"} for kinds in source_pairs.values())
        and sorted(order for _, _, order in source_pairs)
        == list(range(1, 179))
        and type(graph) is dict
        and graph.get("fixedPointReached") is False
        and exact_int(graph.get("newTupleCount"), 1)
        and graph.get("graphSha256") == V15_GRAPH_SHA256
        and type(frontier) is list
        and len(frontier) == 1
        and all(
            exact_keys(
                row,
                (
                    "acquisitionAuthorized",
                    "module",
                    "requiresSeparateWaveDecision",
                    "selectedByGraphAlgorithm",
                    "version",
                ),
            )
            and type(row["module"]) is str
            and type(row["version"]) is str
            and type(row["selectedByGraphAlgorithm"]) is bool
            and row["requiresSeparateWaveDecision"] is True
            and row["acquisitionAuthorized"] is False
            for row in frontier
        )
        and frontier
        == sorted(
            frontier,
            key=lambda row: (
                row["module"],
                row["version"],
                row["selectedByGraphAlgorithm"],
            ),
        )
        and len(
            {
                (row["module"], row["version"])
                for row in frontier
            }
        )
        == 1
        and type(identity_tuples) is list
        and len(identity_tuples) == 1
        and all(
            type(row) is dict
            and type(row.get("selectedByGraphAlgorithm")) is bool
            for row in identity_tuples
        )
        and [
            {
                "module": row["module"],
                "version": row["version"],
                "selectedByGraphAlgorithm":
                    row["selectedByGraphAlgorithm"],
            }
            for row in frontier
        ]
        == [
            {
                "module": row.get("module"),
                "version": row.get("version"),
                "selectedByGraphAlgorithm":
                    row.get("selectedByGraphAlgorithm"),
            }
            for row in identity_tuples
            if type(row) is dict
        ]
        and sha256_bytes(runner.canonical_json_bytes(frontier))
        == V15_FRONTIER_SHA256
        and exact_boolean_map(candidate.get("authority"), V15_AUTHORITY)
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "totalFullInputReconstructionCount"
            ),
            28,
        )
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "underlyingIndependentGraphAlgorithmCount"
            ),
            56,
        )
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "hardenedCheckerModuleCount"
            ),
            14,
        )
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "providerFacadeLoadCount"
            ),
            14,
        )
        and exact_int(
            candidate.get("operationCounters", {}).get(
                "totalFullSourceReconstructionCount"
            ),
            28,
        )
        and exact_int(
            candidate.get("operationCounters", {}).get("archiveOpenCount"),
            3_696,
        ),
        "E_V15_PREDECESSOR",
    )
    return {
        "checkerExecutedFromPinnedBytes": True,
        "candidateContentSha256": binding["sha256"],
        "combinedInputSetSha256": inputs["combinedInputSetSha256"],
        "graphSha256": graph["graphSha256"],
        "frontierSha256": sha256_bytes(
            runner.canonical_json_bytes(frontier)
        ),
        "fixedPointReached": graph["fixedPointReached"],
        "frontierTupleCount": len(frontier),
        "wave16CompletionAppliesToRetainedSnapshot": True,
        "wave16CurrentPathIdentityGuaranteedThroughManifestPublication": False,
        "wave16SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
            False,
        "v15TestsBindingScope": "historical_metadata_only_not_live_held",
        "v15TestsLiveHeld": False,
    }

def validate_v14_predecessor_candidate(
    runner: types.ModuleType,
    candidate: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    """Retained historical contract oracle; V16 never calls this helper."""
    predecessor = decision.get("predecessorBindings", {}).get(
        "combinedFixedPointV14"
    )
    binding = candidate.get("contentBinding")
    without = dict(candidate)
    without.pop("contentBinding", None)
    inputs = candidate.get("inputSet")
    source_bindings = (
        inputs.get("sourceBindings") if type(inputs) is dict else None
    )
    graph = candidate.get("graphDiscovery")
    frontier = graph.get("exactFrontier") if type(graph) is dict else None
    identity_resolution = decision.get("identityResolution")
    identity_tuples = (
        identity_resolution.get("tuples")
        if type(identity_resolution) is dict
        else None
    )
    retained_boundary = (
        predecessor.get("retainedSnapshotBoundary")
        if type(predecessor) is dict
        else None
    )
    source_keys = {
        "kind",
        "module",
        "path",
        "rawSha256",
        "tupleId",
        "tupleOrder",
        "version",
        "wave",
    }
    check(
        exact_keys(
            decision.get("predecessorBindings"),
            ("combinedFixedPointV14",),
        )
        and type(source_bindings) is list
        and len(source_bindings) == 351
        and all(
            type(row) is dict
            and set(row) == source_keys
            and row["kind"] in {"root_zip", "mod", "zip"}
            and type(row["module"]) is str
            and type(row["path"]) is str
            and type(row["rawSha256"]) is str
            and len(row["rawSha256"]) == 64
            and all(
                character in "0123456789abcdef"
                for character in row["rawSha256"]
            )
            and type(row["tupleId"]) is str
            and type(row["tupleOrder"]) is int
            and type(row["version"]) is str
            and type(row["wave"]) is str
            for row in source_bindings
        ),
        "E_V14_PREDECESSOR",
    )
    source_pairs: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in source_bindings:
        if row["kind"] != "root_zip":
            source_pairs[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        type(predecessor) is dict
        and predecessor.get("contentSha256")
        == V14_CANDIDATE_CONTENT_SHA256
        and predecessor.get("combinedInputSetSha256")
        == V14_INPUT_SET_SHA256
        and predecessor.get("sourceBindingsSha256")
        == V14_SOURCE_BINDINGS_SHA256
        and predecessor.get("graphSha256") == V14_GRAPH_SHA256
        and predecessor.get("frontierSha256") == V14_FRONTIER_SHA256
        and exact_int(predecessor.get("frontierTupleCount"), 3)
        and predecessor.get("fixedPointReached") is False
        and predecessor.get("checkerPath") == V14_CHECKER_PATH
        and predecessor.get("checkerRawSha256") == V14_CHECKER_RAW_SHA256
        and predecessor.get("checkerNormalizedSha256")
        == V14_CHECKER_NORMALIZED_SHA256
        and predecessor.get("testsPath") == V14_TESTS_PATH
        and predecessor.get("testsRawSha256") == V14_TESTS_RAW_SHA256
        and exact_int(
            predecessor.get("totalFullSourceReconstructionCount"),
            26,
        )
        and exact_int(
            predecessor.get("totalGraphArchiveOpenCount"),
            3_338,
        )
        and exact_int(
            predecessor.get("trustedPinnedNormalPathFileWriteCount"),
            0,
        )
        and predecessor.get("osSyscallSandboxProvided") is False
        and predecessor.get("providerFacadeVerificationScope")
        == "trusted_pinned_normal_reconstruction_path"
        and predecessor.get("v13TestsBindingScope")
        == "historical_metadata_only_not_live_held"
        and predecessor.get("v13TestsLiveHeld") is False
        and predecessor.get("wave15NamespaceAnchor")
        == {
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-15-v1.claim"
            ),
            "rawSha256": (
                "88e55eda37f5186f373ca402f574789fde93405ad588cab8f5c865c3831837a5"
            ),
        }
        and exact_int(
            predecessor.get("wave9PinnedLegacyBuildCompatibilityCount"),
            4,
        )
        and predecessor.get("wave9LegacyBuildCompatibilityPolicy")
        == candidate.get("wave9LegacyBuildCompatibilityPolicy")
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "wave9PinnedLegacyBuildCompatibilityCount"
            ),
            4,
        )
        and exact_int(
            candidate.get("operationCounters", {}).get(
                "wave9PinnedLegacyBuildCompatibilityCount"
            ),
            4,
        )
        and retained_boundary
        == {
            "completionAppliesToRetainedSnapshot": True,
            "currentPathIdentityGuaranteedThroughManifestPublication": False,
            "finalNamespaceReverifiedAfterCombinedV14Reconstruction": True,
            "historicalExact29FrozenSnapshotDescriptorSetBound": True,
            "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV14Barrier":
                True,
            "liveTerminalControlMetadataVerifiedAtCombinedV14Barrier": True,
            "retainedFdPreManifestBarrierCount": 3,
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                False,
        }
        and exact_int(
            retained_boundary.get("retainedFdPreManifestBarrierCount"),
            3,
        )
        and exact_boolean_items(
            retained_boundary,
            {
                "completionAppliesToRetainedSnapshot": True,
                (
                    "currentPathIdentityGuaranteedThroughManifest"
                    "Publication"
                ): False,
                (
                    "finalNamespaceReverifiedAfterCombinedV14"
                    "Reconstruction"
                ): True,
                (
                    "historicalExact29FrozenSnapshotDescriptorSetBound"
                ): True,
                (
                    "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV14"
                    "Barrier"
                ): True,
                (
                    "liveTerminalControlMetadataVerifiedAtCombinedV14"
                    "Barrier"
                ): True,
                (
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrier"
                    "Prevented"
                ): False,
            },
        )
        and type(binding) is dict
        and binding
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "candidate_without_contentBinding",
            "sha256": V14_CANDIDATE_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == V14_CANDIDATE_CONTENT_SHA256
        and candidate.get("schemaVersion") == "14.0"
        and candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
            "wave5-wave6-wave7-wave8-wave9-wave10-wave11-wave12-wave13-"
            "wave14-wave15-"
            "fixed-point-candidate"
        )
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and candidate.get("result")
        == (
            "combined_graph_recomputed_twice_from_exact_"
            "wave1_through_wave15_source_bytes"
        )
        and candidate.get("route") == "next_wave_required"
        and candidate.get("nextAction")
        == (
            "prepare_separate_versioned_dependency_wave_identity_and_"
            "acquisition_decision"
        )
        and candidate.get("derivedResult")
        == {
            "fixedPointReached": False,
            "frontierTupleCount": 3,
            "frontierSha256": V14_FRONTIER_SHA256,
        }
        and candidate.get("derivedResult", {}).get("fixedPointReached")
        is False
        and exact_int(
            candidate.get("derivedResult", {}).get("frontierTupleCount"),
            3,
        )
        and type(inputs) is dict
        and exact_int(inputs.get("heldSourceInputCount"), 351)
        and inputs.get("combinedInputSetSha256") == V14_INPUT_SET_SHA256
        and sha256_bytes(runner.canonical_json_bytes(source_bindings))
        == V14_INPUT_SET_SHA256
        and sha256_bytes(wave17_digest_bytes(source_bindings))
        == V14_SOURCE_BINDINGS_SHA256
        and len({row["path"] for row in source_bindings}) == 351
        and sum(row["kind"] == "root_zip" for row in source_bindings) == 1
        and sum(row["kind"] == "mod" for row in source_bindings) == 175
        and sum(row["kind"] == "zip" for row in source_bindings) == 175
        and sum(row["wave"] == "wave1" for row in source_bindings) == 38
        and sum(row["wave"] == "wave2" for row in source_bindings) == 30
        and sum(row["wave"] == "wave3" for row in source_bindings) == 32
        and sum(row["wave"] == "wave4" for row in source_bindings) == 32
        and sum(row["wave"] == "wave5" for row in source_bindings) == 30
        and sum(row["wave"] == "wave6" for row in source_bindings) == 36
        and sum(row["wave"] == "wave7" for row in source_bindings) == 30
        and sum(row["wave"] == "wave8" for row in source_bindings) == 28
        and sum(row["wave"] == "wave9" for row in source_bindings) == 20
        and sum(row["wave"] == "wave10" for row in source_bindings) == 22
        and sum(row["wave"] == "wave11" for row in source_bindings) == 18
        and sum(row["wave"] == "wave12" for row in source_bindings) == 8
        and sum(row["wave"] == "wave13" for row in source_bindings) == 8
        and sum(row["wave"] == "wave14" for row in source_bindings) == 8
        and sum(row["wave"] == "wave15" for row in source_bindings) == 10
        and len(source_pairs) == 175
        and all(kinds == {"mod", "zip"} for kinds in source_pairs.values())
        and sorted(order for _, _, order in source_pairs)
        == list(range(1, 176))
        and type(graph) is dict
        and graph.get("fixedPointReached") is False
        and exact_int(graph.get("newTupleCount"), 3)
        and graph.get("graphSha256") == V14_GRAPH_SHA256
        and type(frontier) is list
        and len(frontier) == 3
        and all(
            exact_keys(
                row,
                (
                    "acquisitionAuthorized",
                    "module",
                    "requiresSeparateWaveDecision",
                    "selectedByGraphAlgorithm",
                    "version",
                ),
            )
            and type(row["module"]) is str
            and type(row["version"]) is str
            and type(row["selectedByGraphAlgorithm"]) is bool
            and row["requiresSeparateWaveDecision"] is True
            and row["acquisitionAuthorized"] is False
            for row in frontier
        )
        and frontier
        == sorted(
            frontier,
            key=lambda row: (
                row["module"],
                row["version"],
                row["selectedByGraphAlgorithm"],
            ),
        )
        and len(
            {
                (row["module"], row["version"])
                for row in frontier
            }
        )
        == 3
        and type(identity_tuples) is list
        and len(identity_tuples) == 3
        and all(
            type(row) is dict
            and type(row.get("selectedByGraphAlgorithm")) is bool
            for row in identity_tuples
        )
        and [
            {
                "module": row["module"],
                "version": row["version"],
                "selectedByGraphAlgorithm":
                    row["selectedByGraphAlgorithm"],
            }
            for row in frontier
        ]
        == [
            {
                "module": row.get("module"),
                "version": row.get("version"),
                "selectedByGraphAlgorithm":
                    row.get("selectedByGraphAlgorithm"),
            }
            for row in identity_tuples
            if type(row) is dict
        ]
        and sha256_bytes(runner.canonical_json_bytes(frontier))
        == V14_FRONTIER_SHA256
        and exact_boolean_map(candidate.get("authority"), V14_AUTHORITY)
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "totalFullInputReconstructionCount"
            ),
            26,
        )
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "underlyingIndependentGraphAlgorithmCount"
            ),
            52,
        )
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "hardenedCheckerModuleCount"
            ),
            13,
        )
        and exact_int(
            candidate.get("checkerVerification", {}).get(
                "providerFacadeLoadCount"
            ),
            13,
        )
        and exact_int(
            candidate.get("operationCounters", {}).get(
                "totalFullSourceReconstructionCount"
            ),
            26,
        )
        and exact_int(
            candidate.get("operationCounters", {}).get("archiveOpenCount"),
            3_338,
        ),
        "E_V14_PREDECESSOR",
    )
    return {
        "checkerExecutedFromPinnedBytes": True,
        "candidateContentSha256": binding["sha256"],
        "combinedInputSetSha256": inputs["combinedInputSetSha256"],
        "graphSha256": graph["graphSha256"],
        "frontierSha256": sha256_bytes(
            runner.canonical_json_bytes(frontier)
        ),
        "fixedPointReached": graph["fixedPointReached"],
        "frontierTupleCount": len(frontier),
        "wave15CompletionAppliesToRetainedSnapshot": True,
        "wave15CurrentPathIdentityGuaranteedThroughManifestPublication": False,
        "wave15SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
            False,
        "v14TestsBindingScope": "historical_metadata_only_not_live_held",
        "v14TestsLiveHeld": False,
    }


def wave17_request_resources(
    v4: types.ModuleType,
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    decision = documents[WAVE17_DECISION_PATH]
    permit = documents[WAVE17_PERMIT_PATH]
    receipt = documents[WAVE17_RECEIPT_PATH]
    manifest = documents[WAVE17_MANIFEST_PATH]
    readback_permit = documents[WAVE17_READBACK_PERMIT_PATH]
    readback = documents[WAVE17_READBACK_PATH]
    readback_manifest = documents[WAVE17_READBACK_MANIFEST_PATH]
    verify_wave17_content_bindings(v4, runner, documents)

    resolution = decision.get("identityResolution")
    retained_metadata = decision.get("retainedMetadataEvidence")
    preparation = decision.get("sourceAcquisitionPreparation")
    identity_tuples = (
        resolution.get("tuples") if type(resolution) is dict else None
    )
    source_requests = (
        preparation.get("requestSet") if type(preparation) is dict else None
    )
    check(
        exact_keys(
            decision,
            (
                "authority", "checkerId", "closure", "contentBinding",
                "date", "decisionId", "documentType",
                "identityResolution", "nextAction",
                "nonClaims", "operationCounters", "predecessorBindings",
                "readerDocumentBinding", "recordModeExposed", "result",
                "retainedMetadataEvidence",
                "schemaVersion", "sourceAcquisitionPreparation", "status",
                "toolBindings", "verificationOnly",
            ),
        )
        and exact_keys(
            resolution,
            (
                "blockedTupleCount", "compactIdentityCanonicalization",
                "compactIdentitySha256", "completeIdentityPairCount",
                "conflictingIdentityCount", "fullWitnessCanonicalization",
                "fullWitnessMaterializedInDecision",
                "fullWitnessReproducibleByPinnedChecker",
                "fullWitnessSha256", "goModH1WitnessCount",
                "graphSelectedTupleCount", "moduleZipH1WitnessCount",
                "parentDeclarationCount", "tupleCount", "tuples",
                "versionSpecificNonSelectedTupleCount",
            ),
        )
        and exact_keys(
            retained_metadata,
            (
                "allEvidenceInputsReadTwice", "goSumEntryPath",
                "metadataScanCount", "retainedModPath",
                "retainedModRawSha256", "retainedZipPath",
                "retainedZipRawSha256", "sourceCodeInspected",
                "sourceReconstructionPerformed",
            ),
        )
        and exact_keys(
            preparation,
            (
                "acceptedDirectoryPath",
                "acquisitionAuthorizedByThisDecision",
                "acquisitionReady", "claimPath",
                "namespaceCheckIsPointInTimeOnly",
                "namespaceCleanAtDecisionCheck",
                "namespaceReservationClaimed",
                "permitOrRunnerCreated",
                "proxyHost", "requestCount", "requestOrder", "requestSet",
                "requestSetCanonicalSha256",
                "separateOneUseExecutionPermitRequired",
                "stagingDirectoryPrefix",
            ),
        )
        and exact_keys(
            decision.get("predecessorBindings"),
            ("combinedFixedPointV15",),
        ),
        "E_WAVE17_DECISION",
    )
    check(
        decision.get("contentBinding")
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "decision_without_contentBinding",
            "sha256": WAVE17_CONTENT_SHA256[WAVE17_DECISION_PATH],
        }
        and decision.get("status")
        == (
            "wave17_exact_1_frontier_identity_classified_1_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and exact_boolean_map(
            decision.get("authority"),
            WAVE17_DECISION_AUTHORITY,
        )
        and decision.get("toolBindings") == WAVE17_DECISION_TOOL_BINDINGS
        and type(resolution) is dict
        and exact_int(resolution.get("tupleCount"), 1)
        and exact_int(resolution.get("completeIdentityPairCount"), 1)
        and exact_int(resolution.get("blockedTupleCount"), 0)
        and exact_int(resolution.get("conflictingIdentityCount"), 0)
        and exact_int(resolution.get("goModH1WitnessCount"), 1)
        and exact_int(resolution.get("graphSelectedTupleCount"), 0)
        and exact_int(resolution.get("moduleZipH1WitnessCount"), 1)
        and exact_int(resolution.get("parentDeclarationCount"), 1)
        and exact_int(
            resolution.get("versionSpecificNonSelectedTupleCount"),
            1,
        )
        and resolution.get("compactIdentitySha256")
        == WAVE17_COMPACT_IDENTITY_SHA256
        and resolution.get("fullWitnessSha256")
        == WAVE17_FULL_WITNESS_SHA256
        and type(retained_metadata) is dict
        and retained_metadata.get("allEvidenceInputsReadTwice") is True
        and exact_int(retained_metadata.get("metadataScanCount"), 2)
        and retained_metadata.get("sourceCodeInspected") is False
        and retained_metadata.get("sourceReconstructionPerformed") is False
        and type(preparation) is dict
        and preparation.get("acquisitionReady") is True
        and preparation.get("acquisitionAuthorizedByThisDecision") is False
        and preparation.get("namespaceCheckIsPointInTimeOnly") is True
        and preparation.get("namespaceCleanAtDecisionCheck") is True
        and preparation.get("namespaceReservationClaimed") is False
        and exact_int(preparation.get("requestCount"), 2)
        and preparation.get("requestOrder")
        == "tuple_order_ascending_mod_then_zip"
        and preparation.get("acceptedDirectoryPath")
        == WAVE17_ACCEPTED_DIRECTORY
        and preparation.get("requestSetCanonicalSha256")
        == WAVE17_REQUEST_SET_SHA256
        and type(identity_tuples) is list
        and len(identity_tuples) == 1
        and all(
            exact_keys(
                row,
                (
                    "acquisitionAuthorized", "acquisitionReady",
                    "goModH1", "goModH1WitnessCount",
                    "identityConflict", "identityPairComplete",
                    "module", "moduleZipH1",
                    "moduleZipH1WitnessCount",
                    "parentDeclarationComplete",
                    "parentDeclarationCount",
                    "selectedByGraphAlgorithm", "tupleOrder", "version",
                ),
            )
            and exact_int(row.get("goModH1WitnessCount"), 1)
            and exact_int(row.get("moduleZipH1WitnessCount"), 1)
            and exact_int(row.get("parentDeclarationCount"), 1)
            and exact_int(row.get("tupleOrder"), 1)
            and row.get("acquisitionAuthorized") is False
            and row.get("acquisitionReady") is True
            and row.get("identityConflict") is False
            and row.get("identityPairComplete") is True
            and row.get("parentDeclarationComplete") is True
            and row.get("selectedByGraphAlgorithm") is False
            for row in identity_tuples
        )
        and type(source_requests) is list
        and len(source_requests) == 2
        and sha256_bytes(wave17_digest_bytes(source_requests))
        == WAVE17_REQUEST_SET_SHA256,
        "E_WAVE17_DECISION",
    )

    contract = permit.get("requestContract")
    resources = contract.get("resources") if type(contract) is dict else None
    permit_decision_binding = permit.get("decisionBinding")
    permit_identity_binding = permit.get("identityBinding")
    permit_predecessor = permit.get("predecessorBindings", {}).get(
        "combinedFixedPointV15"
    )
    check(
        exact_keys(
            permit,
            (
                "absoluteResourceLimits", "authority", "contentBinding",
                "decisionBinding", "documentType", "filesystemAuthority",
                "executionReady", "identityBinding", "invocationContract",
                "nextAction",
                "nonClaims",
                "oneUseContract", "permitId", "predecessorBindings",
                "primitiveBindings",
                "readerDocumentBinding", "recordedDate", "requestContract",
                "result", "runnerBinding", "runnerNormalizedSha256",
                "schemaVersion",
                "status", "structurePreparationOnly", "terminalContract",
                "toolBindings",
                "verificationContract", "verificationOnly", "zipLimits",
            ),
        )
        and exact_keys(
            permit_decision_binding,
            (
                "contentSha256", "files", "path", "rawSha256",
                "requiredStatus",
            ),
        )
        and exact_keys(
            permit_identity_binding,
            (
                "blockedTupleCount", "compactIdentitySha256",
                "completeTupleCount", "fullWitnessSha256",
                "requestSetCanonicalSha256",
            ),
        )
        and exact_keys(
            contract,
            (
                "acceptedStatusCode", "alternateHostAllowed",
                "ambientProxyAllowed", "authenticationAllowed",
                "authorizationHeaderAllowed", "clientCertificateAllowed",
                "contentEncoding", "cookieAllowed", "directHttpsOnly", "host",
                "identityContentEncodingRequired", "method", "order",
                "port", "proxyAuthorizationHeaderAllowed",
                "queryOrFragmentAllowed", "rangeHeaderAllowed",
                "redirectAllowed", "requestBodyAllowed", "requestCount",
                "resources", "resourcesCanonicalSha256",
                "retryAllowed",
                "retryResumeOrBackfillAllowed",
                "sourceRequestSetCanonicalSha256",
                "tlsCertificateAndHostnameValidationRequired",
                "tupleCount",
            ),
        )
        and exact_keys(
            permit.get("predecessorBindings"),
            ("combinedFixedPointV15",),
        ),
        "E_WAVE17_PERMIT",
    )
    check(
        permit.get("contentBinding")
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "permit_without_contentBinding",
            "sha256": WAVE17_CONTENT_SHA256[WAVE17_PERMIT_PATH],
        }
        and permit.get("status") == "authorized_not_consumed"
        and exact_boolean_map(
            permit.get("authority"),
            WAVE17_ACQUISITION_AUTHORITY,
        )
        and permit.get("toolBindings") == WAVE17_ACQUISITION_TOOL_BINDINGS
        and permit.get("decisionBinding", {}).get("rawSha256")
        == WAVE17_CONTROL_SHA256[WAVE17_DECISION_PATH]
        and permit.get("decisionBinding", {}).get("contentSha256")
        == WAVE17_CONTENT_SHA256[WAVE17_DECISION_PATH]
        and permit.get("identityBinding", {}).get("compactIdentitySha256")
        == WAVE17_COMPACT_IDENTITY_SHA256
        and permit.get("identityBinding", {}).get("fullWitnessSha256")
        == WAVE17_FULL_WITNESS_SHA256
        and permit.get("identityBinding", {}).get(
            "requestSetCanonicalSha256"
        )
        == WAVE17_REQUEST_SET_SHA256
        and permit.get("absoluteResourceLimits")
        == WAVE17_ABSOLUTE_RESOURCE_LIMITS
        and exact_integer_items(
            permit.get("absoluteResourceLimits"),
            WAVE17_ABSOLUTE_RESOURCE_LIMITS,
        )
        and exact_boolean_items(
            permit.get("absoluteResourceLimits"),
            WAVE17_ABSOLUTE_RESOURCE_LIMITS,
        )
        and permit.get("zipLimits") == WAVE17_ZIP_LIMITS
        and exact_integer_items(
            permit.get("zipLimits"),
            WAVE17_ZIP_LIMITS,
        )
        and exact_boolean_items(
            permit.get("zipLimits"),
            WAVE17_ZIP_LIMITS,
        )
        and permit_predecessor
        == {
            "checkerNormalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V15_CHECKER_PATH,
            "checkerRawSha256": V15_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V15_INPUT_SET_SHA256,
            "contentSha256": V15_CANDIDATE_CONTENT_SHA256,
            "frontierSha256": V15_FRONTIER_SHA256,
            "graphSha256": V15_GRAPH_SHA256,
            "sourceBindingsSha256": V15_SOURCE_BINDINGS_SHA256,
            "testsPath": V15_TESTS_PATH,
            "testsRawSha256": V15_TESTS_RAW_SHA256,
            "totalFullSourceReconstructionCount": 28,
            "totalGraphArchiveOpenCount": 3_696,
            "wave16NamespaceAnchor": {
                "path": (
                    "build/offline-source/pion-ice-v4.3.0/dependencies/"
                    ".wave-16-v1.claim"
                ),
                "rawSha256": (
                    "df97f5d9bf8c56f3bbf08635b8332bbc18b25babd0e5f35742fee3657555f4b8"
                ),
            },
        }
        and type(contract) is dict
        and exact_int(
            permit.get("identityBinding", {}).get("blockedTupleCount"),
            0,
        )
        and exact_int(
            permit.get("identityBinding", {}).get("completeTupleCount"),
            1,
        )
        and exact_int(contract.get("acceptedStatusCode"), 200)
        and exact_int(contract.get("port"), 443)
        and exact_int(contract.get("requestCount"), 2)
        and exact_int(contract.get("tupleCount"), 1)
        and contract.get("order") == "tuple_order_ascending_mod_then_zip"
        and contract.get("sourceRequestSetCanonicalSha256")
        == WAVE17_REQUEST_SET_SHA256
        and contract.get("resourcesCanonicalSha256")
        == WAVE17_PERMIT_RESOURCES_SHA256
        and type(resources) is list
        and len(resources) == 2
        and sha256_bytes(runner.canonical_json_bytes(resources))
        == WAVE17_PERMIT_RESOURCES_SHA256,
        "E_WAVE17_PERMIT",
    )

    check(
        exact_keys(
            receipt,
            (
                "acceptedEvidenceRawSha256", "acceptedPath",
                "acceptedResourceCount",
                "acceptedResourceHashSetCanonicalSha256",
                "additionalCompletionUncertain",
                "aggregateModResponseBytes", "aggregateResponseBytes",
                "aggregateZipEntryCount", "aggregateZipResponseBytes",
                "aggregateZipUncompressedBytes", "attemptId",
                "checkerRawSha256", "claimRawSha256", "compiled",
                "currentOperationPhase", "currentResourceOrdinal",
                "decisionContentSha256", "dispatchBoundaryCount",
                "documentType", "externalAuthenticationRequired",
                "modCount", "operationCountSemantics",
                "permitContentSha256", "persistenceCommittedCount",
                "requestCount", "responseCommittedBytes",
                "responseCommittedCount", "runnerRawSha256",
                "schemaVersion", "sourceAcquired",
                "sourceAcquisitionState", "sourceExtracted",
                "sourceLoadedOrExecuted", "status", "userActionRequired",
                "validationCommittedCount", "zipCount",
            ),
        ),
        "E_WAVE17_RECEIPT",
    )
    check(
        receipt.get("status")
        == "consumed_success_pending_independent_readback"
        and receipt.get("attemptId") == WAVE17_ATTEMPT_ID
        and receipt.get("acceptedPath") == WAVE17_ACCEPTED_DIRECTORY
        and exact_int(receipt.get("acceptedResourceCount"), 2)
        and exact_int(receipt.get("modCount"), 1)
        and exact_int(receipt.get("zipCount"), 1)
        and exact_int(receipt.get("requestCount"), 2)
        and exact_int(receipt.get("dispatchBoundaryCount"), 2)
        and exact_int(receipt.get("responseCommittedCount"), 2)
        and exact_int(receipt.get("validationCommittedCount"), 2)
        and exact_int(receipt.get("persistenceCommittedCount"), 2)
        and exact_int(receipt.get("responseCommittedBytes"), 3_450_700)
        and exact_int(receipt.get("aggregateResponseBytes"), 3_450_700)
        and exact_int(receipt.get("aggregateModResponseBytes"), 301)
        and exact_int(receipt.get("aggregateZipResponseBytes"), 3_450_399)
        and exact_int(receipt.get("aggregateZipEntryCount"), 1_550)
        and exact_int(
            receipt.get("aggregateZipUncompressedBytes"),
            9_108_004,
        )
        and receipt.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE17_RESOURCE_SET_SHA256
        and receipt.get("claimRawSha256")
        == WAVE17_ACQUISITION_CLAIM_RAW_SHA256
        and receipt.get("acceptedEvidenceRawSha256")
        == WAVE17_ACQUISITION_EVIDENCE_RAW_SHA256
        and receipt.get("checkerRawSha256")
        == WAVE17_ACQUISITION_CHECKER_RAW_SHA256
        and receipt.get("runnerRawSha256")
        == WAVE17_ACQUISITION_RUNNER_RAW_SHA256
        and receipt.get("decisionContentSha256")
        == WAVE17_CONTENT_SHA256[WAVE17_DECISION_PATH]
        and receipt.get("permitContentSha256")
        == WAVE17_CONTENT_SHA256[WAVE17_PERMIT_PATH]
        and receipt.get("sourceAcquired") is True
        and receipt.get("sourceExtracted") is False
        and receipt.get("sourceLoadedOrExecuted") is False
        and receipt.get("compiled") is False
        and receipt.get("externalAuthenticationRequired") is False
        and receipt.get("userActionRequired") is False,
        "E_WAVE17_RECEIPT",
    )
    check(
        manifest
        == {
            "attemptId": WAVE17_ATTEMPT_ID,
            "documentType": "aetherlink.wave17-source-acquisition-manifest",
            "manifestWrittenLast": True,
            "receiptPath": WAVE17_RECEIPT_PATH,
            "receiptRawSha256": WAVE17_CONTROL_SHA256[WAVE17_RECEIPT_PATH],
            "schemaVersion": "1.0",
            "status": "consumed_success_pending_independent_readback",
        }
        and exact_boolean_items(
            manifest,
            {"manifestWrittenLast": True},
        ),
        "E_WAVE17_MANIFEST",
    )

    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    verification_contract = readback_permit.get("verificationContract")
    accepted = snapshot.get("acceptedDirectory") if type(snapshot) is dict else None
    accepted_files = accepted.get("files") if type(accepted) is dict else None
    acquisition_authority = (
        snapshot.get("acquisitionAuthority")
        if type(snapshot) is dict
        else None
    )
    acquisition_authority_by_path = {
        row.get("path"): row
        for row in (
            acquisition_authority
            if type(acquisition_authority) is list
            else []
        )
        if type(row) is dict
    }
    acquisition_claim = (
        snapshot.get("acquisitionClaim")
        if type(snapshot) is dict
        else None
    )
    evidence = snapshot.get("evidence") if type(snapshot) is dict else None
    acquisition_receipt = (
        snapshot.get("acquisitionReceipt")
        if type(snapshot) is dict
        else None
    )
    acquisition_manifest = (
        snapshot.get("acquisitionManifest")
        if type(snapshot) is dict
        else None
    )
    identity_bindings = (
        snapshot.get("identityBindings")
        if type(snapshot) is dict
        else None
    )
    snapshot_predecessor = (
        snapshot.get("predecessorBindings", {}).get("combinedFixedPointV15")
        if type(snapshot) is dict
        else None
    )
    final_directory = (
        snapshot.get("finalDirectory")
        if type(snapshot) is dict
        else None
    )
    absence_contract = (
        snapshot.get("absenceContract")
        if type(snapshot) is dict
        else None
    )
    check(
        exact_keys(
            readback_permit,
            (
                "authority", "contentBinding", "documentType",
                "frozenAcquisitionSnapshot", "interpreterContract",
                "nextAction", "nonClaims", "oneUseConsumption",
                "outputContract", "permitId", "readerDocumentBinding",
                "recordedDate", "recorderNormalizedSha256",
                "resourceLimits", "result", "schemaVersion", "status",
                "toolBindings", "verificationContract",
            ),
        )
        and exact_keys(
            snapshot,
            (
                "absenceContract", "acceptedDirectory",
                "acceptedResourceCount",
                "acceptedResourceHashSetCanonicalSha256",
                "acquisitionAuthority", "acquisitionClaim",
                "acquisitionDecisionContentSha256", "acquisitionManifest",
                "acquisitionPermitContentSha256", "acquisitionReceipt",
                "aggregateAcceptedBytes", "aggregateModBytes",
                "aggregateZipBytes", "aggregateZipEntryCount",
                "aggregateZipUncompressedBytes", "attemptId", "evidence",
                "finalDirectory", "frozenFileCount",
                "frozenFilesCanonicalSha256", "identityBindings",
                "modCount", "predecessorBindings",
                "selectedRequestOrdinals", "selectedTupleCount", "zipCount",
            ),
        )
        and exact_keys(
            verification_contract,
            (
                "acceptedResourceHashSetCanonicalSha256Recomputed",
                "acquisitionCheckerOrRunnerImportAllowed",
                "acquisitionCheckerOrRunnerInvocationAllowed",
                "allFrozenFilesOpenedNoFollowAndHeld",
                (
                    "allRequiredPreManifestBarriersCompleteImmediatelyBefore"
                    "ManifestPublication"
                ),
                "attemptAndAuthorityBindingsRecomputed",
                "authorityFilesOpenedAndHeldFirst",
                (
                    "claimCreationFdHeldAtImmediatelyBeforeManifestBarrier"
                ),
                "claimDurableBeforeAnyFrozenAcquisitionInputOpen",
                "cleanupClosesEveryOwnedFdBeforeSignalMaskRestore",
                "combinedFixedPointV15PredecessorBindingRecomputed",
                "completeVerificationPassCount",
                "completionAppliesToRetainedSnapshot",
                (
                    "currentPathDeviceAndInodeMustMatchHeldObjectAtEachPre"
                    "ManifestBarrier"
                ),
                (
                    "currentPathIdentityGuaranteedThroughManifest"
                    "Publication"
                ),
                "decisionAndPermitContentBindingsRecomputed",
                "eachPreManifestBarrierReopensEveryCurrentPathNoFollow",
                "exact2ResourceOrderAndAggregateRecomputed",
                "exact21FrozenFileSnapshotRequired",
                "exactFinalAndAcceptedDirectoryInventoriesRequired",
                "executeSuccessRecordedBeforeStdoutReporting",
                (
                    "frozenSnapshotHeldFdBytesReverifiedImmediatelyBefore"
                    "ManifestPublication"
                ),
                "goModH1RecomputedIndependently",
                "identityAndSourceRequestSetBindingsRecomputed",
                "intermediateDirectoryComponentsOpenedNoFollowAndHeld",
                "moduleZipH1RecomputedIndependently",
                "openToOwnershipTransferDefersOnlySigalrmAndSigint",
                "pathSha256BytesModeOwnerAndLinkCountRequired",
                "postSuccessReportingFailure",
                "publishedOutputsReopenedAndVerifiedBeforePublishReturns",
                (
                    "readbackClaimCurrentPathIdentityReverifiedImmediately"
                    "BeforeManifestPublication"
                ),
                (
                    "readbackReceiptCurrentPathIdentityReverifiedImmediately"
                    "BeforeManifestPublication"
                ),
                "requestResourcesCanonicalSha256Recomputed",
                "requiredFallibleBarrierAfterManifest",
                "retainedFdPreManifestBarrierCount",
                "retainedFdPreManifestBarriers",
                (
                    "retainedProjectRootCurrentPathIdentityCheckedAtEachPre"
                    "ManifestBarrier"
                ),
                (
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrier"
                    "Prevented"
                ),
                "sourceExtractionAllowed",
                "strictCanonicalTerminalAndEvidenceJsonRequired",
                "v14TestsLiveHeld", "v15TestsLiveHeld",
                "zipStructurePathCrcAndModParityRecomputed",
            ),
        )
        and exact_keys(
            snapshot.get("predecessorBindings")
            if type(snapshot) is dict
            else None,
            ("combinedFixedPointV15",),
        ),
        "E_WAVE17_READBACK_PERMIT",
    )
    check(
        readback_permit.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE17_CONTENT_SHA256[WAVE17_READBACK_PERMIT_PATH],
        }
        and readback_permit.get("status") == "authorized_not_consumed"
        and exact_boolean_map(
            readback_permit.get("authority"),
            WAVE17_READBACK_AUTHORITY,
        )
        and readback_permit.get("toolBindings")
        == WAVE17_READBACK_TOOL_BINDINGS
        and readback_permit.get("recorderNormalizedSha256")
        == WAVE17_READBACK_RECORDER_NORMALIZED_SHA256
        and readback_permit.get("resourceLimits")
        == WAVE17_READBACK_RESOURCE_LIMITS
        and exact_integer_items(
            readback_permit.get("resourceLimits"),
            WAVE17_READBACK_RESOURCE_LIMITS,
        )
        and exact_boolean_items(
            readback_permit.get("resourceLimits"),
            WAVE17_READBACK_RESOURCE_LIMITS,
        )
        and type(verification_contract) is dict
        and exact_int(
            verification_contract.get("completeVerificationPassCount"),
            2,
        )
        and verification_contract.get("allFrozenFilesOpenedNoFollowAndHeld")
        is True
        and verification_contract.get("exact21FrozenFileSnapshotRequired")
        is True
        and verification_contract.get(
            "combinedFixedPointV15PredecessorBindingRecomputed"
        ) is True
        and verification_contract.get(
            "exact2ResourceOrderAndAggregateRecomputed"
        ) is True
        and verification_contract.get(
            "executeSuccessRecordedBeforeStdoutReporting"
        ) is True
        and verification_contract.get("postSuccessReportingFailure")
        == {
            "completionAppliesToRetainedSnapshot": True,
            "failureCode": "E_POST_SUCCESS_REPORTING",
            "failurePhase": "reporting",
            "readbackPublicationComplete": True,
            "retryAllowed": False,
            "status": "consumed_success_reporting_failed",
        }
        and exact_boolean_items(
            verification_contract.get("postSuccessReportingFailure"),
            {
                "completionAppliesToRetainedSnapshot": True,
                "readbackPublicationComplete": True,
                "retryAllowed": False,
            },
        )
        and verification_contract.get("requiredFallibleBarrierAfterManifest")
        is False
        and verification_contract.get("v14TestsLiveHeld") is False
        and verification_contract.get("v15TestsLiveHeld") is True
        and verification_contract.get(
            "requestResourcesCanonicalSha256Recomputed"
        ) is True
        and exact_int(
            verification_contract.get(
                "retainedFdPreManifestBarrierCount"
            ),
            3,
        )
        and verification_contract.get("retainedFdPreManifestBarriers")
        == WAVE17_RETAINED_BARRIERS
        and verification_contract.get("completionAppliesToRetainedSnapshot")
        is True
        and verification_contract.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and verification_contract.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and type(snapshot) is dict
        and snapshot.get("attemptId") == WAVE17_ATTEMPT_ID
        and identity_bindings
        == {
            "compactIdentitySha256": WAVE17_COMPACT_IDENTITY_SHA256,
            "fullWitnessSha256": WAVE17_FULL_WITNESS_SHA256,
            "heldSourceBindingsSha256":
                WAVE17_HELD_SOURCE_BINDINGS_SHA256,
            "resourcesCanonicalSha256":
                WAVE17_PERMIT_RESOURCES_SHA256,
            "sourceRequestSetCanonicalSha256":
                WAVE17_REQUEST_SET_SHA256,
        }
        and snapshot_predecessor
        == {
            "checkerNormalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V15_CHECKER_PATH,
            "checkerRawSha256": V15_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V15_INPUT_SET_SHA256,
            "contentSha256": V15_CANDIDATE_CONTENT_SHA256,
            "frontierSha256": V15_FRONTIER_SHA256,
            "graphSha256": V15_GRAPH_SHA256,
            "sourceBindingsSha256": V15_SOURCE_BINDINGS_SHA256,
            "testsPath": V15_TESTS_PATH,
            "testsRawSha256": V15_TESTS_RAW_SHA256,
            "totalFullSourceReconstructionCount": 28,
            "totalGraphArchiveOpenCount": 3_696,
            "wave16NamespaceAnchor": {
                "path": (
                    "build/offline-source/pion-ice-v4.3.0/dependencies/"
                    ".wave-16-v1.claim"
                ),
                "rawSha256": (
                    "df97f5d9bf8c56f3bbf08635b8332bbc18b25babd0e5f35742fee3657555f4b8"
                ),
            },
        }
        and snapshot.get("acquisitionDecisionContentSha256")
        == WAVE17_CONTENT_SHA256[WAVE17_DECISION_PATH]
        == decision.get("contentBinding", {}).get("sha256")
        == permit.get("decisionBinding", {}).get("contentSha256")
        == receipt.get("decisionContentSha256")
        and snapshot.get("acquisitionPermitContentSha256")
        == WAVE17_CONTENT_SHA256[WAVE17_PERMIT_PATH]
        == permit.get("contentBinding", {}).get("sha256")
        == receipt.get("permitContentSha256")
        and final_directory
        == {
            "exactEntries": ["accepted", "evidence.json"],
            "linkCount": 4,
            "mode": "0700",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-17-v1"
            ),
        }
        and exact_int(final_directory.get("linkCount"), 4)
        and exact_int(final_directory.get("ownerUid"), os.geteuid())
        and absence_contract
        == {
            "failureAbsent": True,
            "failurePath": (
                f"{BASE}/bounded-dependency-source-acquisition-wave17-"
                "failure-v1.json"
            ),
            "portableNameComparison": "NFC_casefold",
            "stagingAbsent": True,
            "stagingParent": (
                "build/offline-source/pion-ice-v4.3.0/dependencies"
            ),
            "stagingPrefix": ".wave-17-v1-staging-",
        }
        and exact_boolean_items(
            absence_contract,
            {
                "failureAbsent": True,
                "stagingAbsent": True,
            },
        )
        and exact_int(snapshot.get("frozenFileCount"), 21)
        and snapshot.get("frozenFilesCanonicalSha256")
        == WAVE17_FROZEN_FILE_SET_SHA256
        and exact_int(snapshot.get("acceptedResourceCount"), 2)
        and exact_int(snapshot.get("selectedTupleCount"), 0)
        and snapshot.get("selectedRequestOrdinals") == []
        and exact_int(snapshot.get("modCount"), 1)
        and exact_int(snapshot.get("zipCount"), 1)
        and exact_int(snapshot.get("aggregateAcceptedBytes"), 3_450_700)
        and exact_int(snapshot.get("aggregateModBytes"), 301)
        and exact_int(snapshot.get("aggregateZipBytes"), 3_450_399)
        and exact_int(snapshot.get("aggregateZipEntryCount"), 1_550)
        and exact_int(
            snapshot.get("aggregateZipUncompressedBytes"),
            9_108_004,
        )
        and snapshot.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE17_RESOURCE_SET_SHA256
        and type(acquisition_authority) is list
        and len(acquisition_authority) == 15
        and len(acquisition_authority_by_path) == 15
        and acquisition_authority_by_path.get(
            (
                "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_"
                "acquisition_v1.py"
            ),
            {},
        ).get("rawSha256")
        == WAVE17_ACQUISITION_CHECKER_RAW_SHA256
        and acquisition_authority_by_path.get(
            (
                "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave17_"
                "v1_once.py"
            ),
            {},
        ).get("rawSha256")
        == WAVE17_ACQUISITION_RUNNER_RAW_SHA256
        and acquisition_claim
        == {
            "bytes": 416,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-17-v1.claim"
            ),
            "rawSha256": WAVE17_ACQUISITION_CLAIM_RAW_SHA256,
        }
        and exact_int(acquisition_claim.get("bytes"), 416)
        and exact_int(acquisition_claim.get("linkCount"), 1)
        and exact_int(acquisition_claim.get("ownerUid"), os.geteuid())
        and evidence
        == {
            "bytes": 1_100,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-17-v1/evidence.json"
            ),
            "rawSha256": WAVE17_ACQUISITION_EVIDENCE_RAW_SHA256,
        }
        and exact_int(evidence.get("bytes"), 1_100)
        and exact_int(evidence.get("linkCount"), 1)
        and exact_int(evidence.get("ownerUid"), os.geteuid())
        and acquisition_receipt
        == {
            "bytes": 1_659,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE17_RECEIPT_PATH,
            "rawSha256": WAVE17_CONTROL_SHA256[WAVE17_RECEIPT_PATH],
        }
        and exact_int(acquisition_receipt.get("bytes"), 1_659)
        and exact_int(acquisition_receipt.get("linkCount"), 1)
        and exact_int(
            acquisition_receipt.get("ownerUid"),
            os.geteuid(),
        )
        and acquisition_manifest
        == {
            "bytes": 465,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE17_MANIFEST_PATH,
            "rawSha256": WAVE17_CONTROL_SHA256[WAVE17_MANIFEST_PATH],
        }
        and exact_int(acquisition_manifest.get("bytes"), 465)
        and exact_int(acquisition_manifest.get("linkCount"), 1)
        and exact_int(
            acquisition_manifest.get("ownerUid"),
            os.geteuid(),
        )
        and manifest.get("receiptPath") == acquisition_receipt["path"]
        and manifest.get("receiptRawSha256")
        == acquisition_receipt["rawSha256"]
        and type(accepted) is dict
        and accepted.get("path") == WAVE17_ACCEPTED_DIRECTORY
        and accepted.get("mode") == "0700"
        and exact_int(accepted.get("ownerUid"), os.geteuid())
        and exact_int(accepted.get("linkCount"), 4)
        and exact_int(accepted.get("exactFileCount"), 2)
        and type(accepted_files) is list
        and len(accepted_files) == 2
        and sha256_bytes(
            runner.canonical_json_bytes(
                [
                    *acquisition_authority,
                    acquisition_claim,
                    evidence,
                    *accepted_files,
                    acquisition_receipt,
                    acquisition_manifest,
                ]
            )
        )
        == WAVE17_FROZEN_FILE_SET_SHA256,
        "E_WAVE17_READBACK_PERMIT",
    )

    verified = readback.get("verified")
    verified_resources = (
        verified.get("resources") if type(verified) is dict else None
    )
    check(
        set(readback)
        == {
            "acquisitionAttemptId",
            "allRequiredPreManifestBarriersCompleteAtReceipt",
            "allRequiredPreManifestBarriersRequired",
            "authorityBinding",
            "compiled",
            "completedRetainedFdPreManifestBarrierCountAtReceipt",
            "completionAppliesToRetainedSnapshot",
            "contentBinding",
            "currentPathIdentityGuaranteedThroughManifestPublication",
            "documentType",
            "externalAuthenticationRequired",
            "networkRequestAttemptCount",
            "offline",
            "readbackAttemptId",
            "readbackClaim",
            "remainingRetainedFdPreManifestBarrierCount",
            "requiredRetainedFdPreManifestBarrierCount",
            "retainedFdPreManifestBarriers",
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
            "schemaVersion",
            "sourceAcquisitionCount",
            "sourceExtracted",
            "sourceLoadedOrExecuted",
            "status",
            "userActionRequired",
            "verificationPassCount",
            "verified",
        }
        and type(verified) is dict
        and set(verified)
        == {
            "acceptedResourceCount",
            "acceptedResourceHashSetCanonicalSha256",
            "acquisitionAttemptId",
            "acquisitionClaimRawSha256",
            "acquisitionManifestRawSha256",
            "acquisitionReceiptRawSha256",
            "aggregateAcceptedBytes",
            "aggregateModBytes",
            "aggregateZipBytes",
            "aggregateZipEntryCount",
            "aggregateZipUncompressedBytes",
            "authorityFileCount",
            "combinedFixedPointV15ContentSha256",
            "compactIdentitySha256",
            "compiled",
            "decisionContentSha256",
            "evidenceRawSha256",
            "externalAuthenticationRequired",
            "failureAbsent",
            "fullWitnessSha256",
            "heldSourceBindingsSha256",
            "modCount",
            "permitContentSha256",
            "resources",
            "resourcesCanonicalSha256",
            "selectedRequestOrdinals",
            "selectedTupleCount",
            "sourceExtracted",
            "sourceLoadedOrExecuted",
            "sourceRequestSetCanonicalSha256",
            "stagingAbsent",
            "status",
            "userActionRequired",
            "zipCount",
        },
        "E_WAVE17_READBACK",
    )
    check(
        readback.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE17_CONTENT_SHA256[WAVE17_READBACK_PATH],
        }
        and readback.get("status")
        == "wave17_acquisition_retained_snapshot_independently_read_back"
        and readback.get("acquisitionAttemptId") == WAVE17_ATTEMPT_ID
        and readback.get("readbackAttemptId") == WAVE17_READBACK_ATTEMPT_ID
        and readback.get("authorityBinding")
        == WAVE17_READBACK_AUTHORITY_BINDING
        and exact_int(readback.get("verificationPassCount"), 2)
        and readback.get("offline") is True
        and exact_int(readback.get("networkRequestAttemptCount"), 0)
        and exact_int(readback.get("sourceAcquisitionCount"), 0)
        and readback.get("sourceExtracted") is False
        and readback.get("sourceLoadedOrExecuted") is False
        and readback.get("compiled") is False
        and readback.get("externalAuthenticationRequired") is False
        and readback.get("userActionRequired") is False
        and readback.get("readbackClaim")
        == {
            "bytes": 1_255,
            "contentSha256": WAVE17_READBACK_CLAIM_CONTENT_SHA256,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-17-v1-readback.claim"
            ),
            "rawSha256": WAVE17_READBACK_CLAIM_RAW_SHA256,
        }
        and exact_int(
            readback.get("readbackClaim", {}).get("bytes"),
            1_255,
        )
        and exact_int(
            readback.get("readbackClaim", {}).get("linkCount"),
            1,
        )
        and exact_int(
            readback.get("readbackClaim", {}).get("ownerUid"),
            os.geteuid(),
        )
        and readback.get("allRequiredPreManifestBarriersRequired") is True
        and readback.get("allRequiredPreManifestBarriersCompleteAtReceipt")
        is False
        and exact_int(
            readback.get("requiredRetainedFdPreManifestBarrierCount"),
            3,
        )
        and exact_int(
            readback.get(
                "completedRetainedFdPreManifestBarrierCountAtReceipt"
            ),
            1,
        )
        and exact_int(
            readback.get("remainingRetainedFdPreManifestBarrierCount"),
            2,
        )
        and readback.get("retainedFdPreManifestBarriers")
        == WAVE17_RETAINED_BARRIERS
        and readback.get("completionAppliesToRetainedSnapshot") is True
        and readback.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and readback.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and type(verified) is dict
        and verified.get("status")
        == "wave17_acquisition_retained_snapshot_independently_verified"
        and verified.get("acquisitionAttemptId")
        == snapshot.get("attemptId")
        == receipt.get("attemptId")
        == manifest.get("attemptId")
        and exact_int(
            verified.get("authorityFileCount"),
            len(acquisition_authority),
        )
        and verified.get("authorityFileCount")
        == len(acquisition_authority)
        and exact_int(verified.get("acceptedResourceCount"), 2)
        and verified.get("acceptedResourceCount") == 2
        == snapshot.get("acceptedResourceCount")
        == receipt.get("acceptedResourceCount")
        and verified.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE17_RESOURCE_SET_SHA256
        == snapshot.get("acceptedResourceHashSetCanonicalSha256")
        == receipt.get("acceptedResourceHashSetCanonicalSha256")
        and exact_int(verified.get("selectedTupleCount"), 0)
        and verified.get("selectedTupleCount") == 0
        == snapshot.get("selectedTupleCount")
        and verified.get("selectedRequestOrdinals") == []
        == snapshot.get("selectedRequestOrdinals")
        and exact_int(verified.get("modCount"), 1)
        and verified.get("modCount")
        == snapshot.get("modCount")
        == receipt.get("modCount")
        == 1
        and exact_int(verified.get("zipCount"), 1)
        and verified.get("zipCount")
        == snapshot.get("zipCount")
        == receipt.get("zipCount")
        == 1
        and exact_int(
            verified.get("aggregateAcceptedBytes"),
            3_450_700,
        )
        and verified.get("aggregateAcceptedBytes")
        == snapshot.get("aggregateAcceptedBytes")
        == receipt.get("aggregateResponseBytes")
        == 3_450_700
        and exact_int(verified.get("aggregateModBytes"), 301)
        and verified.get("aggregateModBytes")
        == snapshot.get("aggregateModBytes")
        == receipt.get("aggregateModResponseBytes")
        == 301
        and exact_int(verified.get("aggregateZipBytes"), 3_450_399)
        and verified.get("aggregateZipBytes")
        == snapshot.get("aggregateZipBytes")
        == receipt.get("aggregateZipResponseBytes")
        == 3_450_399
        and exact_int(verified.get("aggregateZipEntryCount"), 1_550)
        and verified.get("aggregateZipEntryCount")
        == snapshot.get("aggregateZipEntryCount")
        == receipt.get("aggregateZipEntryCount")
        == 1_550
        and exact_int(
            verified.get("aggregateZipUncompressedBytes"),
            9_108_004,
        )
        and verified.get("aggregateZipUncompressedBytes")
        == snapshot.get("aggregateZipUncompressedBytes")
        == receipt.get("aggregateZipUncompressedBytes")
        == 9_108_004
        and verified.get("combinedFixedPointV15ContentSha256")
        == V15_CANDIDATE_CONTENT_SHA256
        and verified.get("resourcesCanonicalSha256")
        == identity_bindings["resourcesCanonicalSha256"]
        == contract.get("resourcesCanonicalSha256")
        == WAVE17_PERMIT_RESOURCES_SHA256
        and verified.get("decisionContentSha256")
        == snapshot.get("acquisitionDecisionContentSha256")
        == receipt.get("decisionContentSha256")
        == WAVE17_CONTENT_SHA256[WAVE17_DECISION_PATH]
        and verified.get("permitContentSha256")
        == snapshot.get("acquisitionPermitContentSha256")
        == receipt.get("permitContentSha256")
        == WAVE17_CONTENT_SHA256[WAVE17_PERMIT_PATH]
        and verified.get("sourceRequestSetCanonicalSha256")
        == identity_bindings["sourceRequestSetCanonicalSha256"]
        == contract.get("sourceRequestSetCanonicalSha256")
        == WAVE17_REQUEST_SET_SHA256
        and verified.get("compactIdentitySha256")
        == identity_bindings["compactIdentitySha256"]
        == resolution.get("compactIdentitySha256")
        == WAVE17_COMPACT_IDENTITY_SHA256
        and verified.get("fullWitnessSha256")
        == identity_bindings["fullWitnessSha256"]
        == resolution.get("fullWitnessSha256")
        == WAVE17_FULL_WITNESS_SHA256
        and verified.get("heldSourceBindingsSha256")
        == identity_bindings["heldSourceBindingsSha256"]
        == WAVE17_HELD_SOURCE_BINDINGS_SHA256
        and verified.get("acquisitionClaimRawSha256")
        == acquisition_claim["rawSha256"]
        == receipt.get("claimRawSha256")
        and verified.get("evidenceRawSha256")
        == evidence["rawSha256"]
        == receipt.get("acceptedEvidenceRawSha256")
        and verified.get("acquisitionReceiptRawSha256")
        == acquisition_receipt["rawSha256"]
        == manifest.get("receiptRawSha256")
        and verified.get("acquisitionManifestRawSha256")
        == acquisition_manifest["rawSha256"]
        and verified.get("failureAbsent")
        is absence_contract["failureAbsent"]
        is True
        and verified.get("stagingAbsent")
        is absence_contract["stagingAbsent"]
        is True
        and verified.get("sourceExtracted")
        is receipt.get("sourceExtracted")
        is readback.get("sourceExtracted")
        is False
        and verified.get("sourceLoadedOrExecuted")
        is receipt.get("sourceLoadedOrExecuted")
        is readback.get("sourceLoadedOrExecuted")
        is False
        and verified.get("compiled")
        is receipt.get("compiled")
        is readback.get("compiled")
        is False
        and verified.get("externalAuthenticationRequired")
        is receipt.get("externalAuthenticationRequired")
        is readback.get("externalAuthenticationRequired")
        is False
        and verified.get("userActionRequired")
        is receipt.get("userActionRequired")
        is readback.get("userActionRequired")
        is False
        and type(verified_resources) is list
        and len(verified_resources) == 2,
        "E_WAVE17_READBACK",
    )
    check(
        set(readback_manifest)
        == {
            "acquisitionAttemptId",
            "allRequiredPreManifestBarriersCompleted",
            "authorityBinding",
            "completedPreManifestCurrentPathIdentityBarrierCount",
            "completionAppliesToRetainedSnapshot",
            "contentBinding",
            "currentPathIdentityGuaranteedThroughManifestPublication",
            "documentType",
            "externalAuthenticationRequired",
            "lastCurrentPathIdentityBarrierTiming",
            "manifestWrittenLast",
            "networkRequestAttemptCount",
            "offline",
            "readbackAttemptId",
            "receipt",
            "retainedFdPreManifestBarriers",
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
            "schemaVersion",
            "sourceAcquisitionCount",
            "status",
            "userActionRequired",
        },
        "E_WAVE17_READBACK_MANIFEST",
    )
    check(
        readback_manifest.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE17_CONTENT_SHA256[
                WAVE17_READBACK_MANIFEST_PATH
            ],
        }
        and readback_manifest.get("status")
        == "wave17_acquisition_retained_snapshot_readback_publication_complete"
        and readback_manifest.get("acquisitionAttemptId") == WAVE17_ATTEMPT_ID
        and readback_manifest.get("readbackAttemptId")
        == WAVE17_READBACK_ATTEMPT_ID
        and readback_manifest.get("authorityBinding")
        == WAVE17_READBACK_AUTHORITY_BINDING
        and readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("allRequiredPreManifestBarriersCompleted")
        is True
        and exact_int(
            readback_manifest.get(
                "completedPreManifestCurrentPathIdentityBarrierCount"
            ),
            3,
        )
        and readback_manifest.get("lastCurrentPathIdentityBarrierTiming")
        == "immediately_before_manifest_publication"
        and readback_manifest.get("retainedFdPreManifestBarriers")
        == WAVE17_RETAINED_BARRIERS
        and readback_manifest.get("completionAppliesToRetainedSnapshot")
        is True
        and readback_manifest.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and readback_manifest.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and readback_manifest.get("receipt")
        == {
            "bytes": 4_980,
            "contentSha256": WAVE17_CONTENT_SHA256[WAVE17_READBACK_PATH],
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE17_READBACK_PATH,
            "rawSha256": WAVE17_CONTROL_SHA256[WAVE17_READBACK_PATH],
        }
        and exact_int(
            readback_manifest.get("receipt", {}).get("bytes"),
            4_980,
        )
        and exact_int(
            readback_manifest.get("receipt", {}).get("linkCount"),
            1,
        )
        and exact_int(
            readback_manifest.get("receipt", {}).get("ownerUid"),
            os.geteuid(),
        )
        and readback_manifest.get("offline") is True
        and exact_int(
            readback_manifest.get("networkRequestAttemptCount"),
            0,
        )
        and exact_int(
            readback_manifest.get("sourceAcquisitionCount"),
            0,
        )
        and readback_manifest.get("externalAuthenticationRequired") is False
        and readback_manifest.get("userActionRequired") is False,
        "E_WAVE17_READBACK_MANIFEST",
    )

    accepted_by_name = {
        Path(row["path"]).name: row
        for row in accepted_files
        if type(row) is dict and type(row.get("path")) is str
    }
    verified_by_name = {
        row.get("acceptedFileName"): row
        for row in verified_resources
        if type(row) is dict
    }
    identity_by_order = {
        row.get("tupleOrder"): row
        for row in identity_tuples
        if type(row) is dict
    }
    check(
        len(accepted_by_name) == 2
        and len(verified_by_name) == 2
        and len(identity_by_order) == 1,
        "E_WAVE17_RESOURCE",
    )
    result: list[dict[str, Any]] = []
    tuple_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    totals = {"all": 0, "mod": 0, "zip": 0, "entries": 0, "expanded": 0}
    accepted_hash_projection: list[dict[str, Any]] = []
    for index, value in enumerate(resources, start=1):
        source_value = source_requests[index - 1]
        expected_kind = "mod" if index % 2 else "zip"
        tuple_order = (index + 1) // 2
        identity_tuple = identity_by_order.get(tuple_order)
        digest = sha256_bytes(
            f"{value.get('module')}\n{value.get('version')}\n".encode()
        )
        check(
            type(value) is dict
            and exact_keys(
                value,
                (
                    "acceptedFileName", "expectedH1", "host", "kind",
                    "maximumResponseBodyBytes", "method", "module",
                    "path", "port", "requestOrdinal",
                    "selectedByGraphAlgorithm", "tupleDigestSha256",
                    "tupleId", "tupleOrder", "url", "version",
                ),
            )
            and exact_int(value.get("requestOrdinal"), index)
            and exact_int(value.get("tupleOrder"), tuple_order)
            and exact_int(value.get("port"), 443)
            and exact_int(
                value.get("maximumResponseBodyBytes"),
                1_048_576 if expected_kind == "mod" else 16_777_216,
            )
            and value.get("kind") == expected_kind
            and value.get("selectedByGraphAlgorithm")
            is False
            and value.get("tupleDigestSha256") == digest
            and value.get("tupleId")
            == f"wave17-{tuple_order:03}-{digest[:12]}"
            and value.get("acceptedFileName")
            == f"{tuple_order:03}-{digest[:20]}.{expected_kind}"
            and type(source_value) is dict
            and exact_keys(
                source_value,
                (
                    "acceptedFileName", "acquisitionAuthorized",
                    "authenticationRequired", "expectedH1", "host",
                    "maximumResponseBytes", "method", "module",
                    "networkAuthorized", "requestOrdinal",
                    "resourceKind", "selectedByGraphAlgorithm",
                    "tupleOrder", "url", "version",
                ),
            )
            and exact_int(source_value.get("requestOrdinal"), index)
            and exact_int(source_value.get("tupleOrder"), tuple_order)
            and exact_int(
                source_value.get("maximumResponseBytes"),
                1_048_576 if expected_kind == "mod" else 16_777_216,
            )
            and source_value.get("resourceKind") == expected_kind
            and source_value.get("module") == value.get("module")
            and source_value.get("version") == value.get("version")
            and source_value.get("url") == value.get("url")
            and source_value.get("expectedH1") == value.get("expectedH1")
            and source_value.get("acquisitionAuthorized") is False
            and source_value.get("authenticationRequired") is False
            and source_value.get("networkAuthorized") is False
            and source_value.get("selectedByGraphAlgorithm")
            is False
            and type(identity_tuple) is dict
            and exact_int(identity_tuple.get("tupleOrder"), tuple_order)
            and identity_tuple.get("module") == value.get("module")
            and identity_tuple.get("version") == value.get("version")
            and (
                identity_tuple.get("goModH1")
                if expected_kind == "mod"
                else identity_tuple.get("moduleZipH1")
            )
            == value.get("expectedH1")
            and identity_tuple.get("selectedByGraphAlgorithm")
            is False,
            "E_WAVE17_RESOURCE",
        )
        name = value["acceptedFileName"]
        accepted_row = accepted_by_name.get(name)
        verified_row = verified_by_name.get(name)
        check(
            type(accepted_row) is dict
            and set(accepted_row)
            == {
                "bytes",
                "linkCount",
                "mode",
                "ownerUid",
                "path",
                "rawSha256",
            }
            and accepted_row.get("path")
            == f"{WAVE17_ACCEPTED_DIRECTORY}/{name}"
            and accepted_row.get("mode") == "0600"
            and exact_int(
                accepted_row.get("ownerUid"),
                os.geteuid(),
            )
            and exact_int(accepted_row.get("linkCount"), 1)
            and type(accepted_row.get("bytes")) is int
            and accepted_row["bytes"] > 0
            and type(verified_row) is dict
            and set(verified_row)
            == (
                {
                    "acceptedFileName",
                    "byteCount",
                    "entryCount",
                    "kind",
                    "rawSha256",
                    "requestOrdinal",
                    "rootGoModPresent",
                    "tupleId",
                    "uncompressedBytes",
                    "url",
                    "verifiedH1",
                }
                if expected_kind == "zip"
                else {
                    "acceptedFileName",
                    "byteCount",
                    "kind",
                    "rawSha256",
                    "requestOrdinal",
                    "tupleId",
                    "url",
                    "verifiedH1",
                }
            )
            and verified_row.get("acceptedFileName") == name
            and exact_int(verified_row.get("requestOrdinal"), index)
            and verified_row.get("tupleId") == value.get("tupleId")
            and verified_row.get("kind") == expected_kind
            and verified_row.get("url") == value.get("url")
            and verified_row.get("verifiedH1") == value.get("expectedH1")
            and exact_int(
                verified_row.get("byteCount"),
                accepted_row["bytes"],
            )
            and verified_row.get("rawSha256")
            == accepted_row.get("rawSha256"),
            "E_WAVE17_RESOURCE",
        )
        accepted_hash_projection.append(
            {
                "requestOrdinal": index,
                "acceptedFileName": name,
                "rawSha256": accepted_row["rawSha256"],
                "verifiedH1": verified_row["verifiedH1"],
            }
        )
        totals["all"] += accepted_row["bytes"]
        totals[expected_kind] += accepted_row["bytes"]
        if expected_kind == "zip":
            check(
                type(verified_row.get("entryCount")) is int
                and verified_row["entryCount"] > 0
                and verified_row.get("rootGoModPresent") is True
                and type(verified_row.get("uncompressedBytes")) is int
                and verified_row["uncompressedBytes"] > 0,
                "E_WAVE17_RESOURCE",
            )
            totals["entries"] += verified_row.get("entryCount", -1)
            totals["expanded"] += verified_row.get("uncompressedBytes", -1)
        row = {
            "wave": "wave17",
            "path": accepted_row["path"],
            "rawSha256": accepted_row["rawSha256"],
            "maximumBytes": accepted_row["bytes"],
            "ownerOnly": True,
            "kind": expected_kind,
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 178 + tuple_order,
            "order": index,
        }
        if expected_kind == "zip":
            row["modulePrefix"] = (
                f"{runner.go_proxy_escape(value['module'])}@"
                f"{runner.go_proxy_escape(value['version'])}/"
            )
        tuple_rows[value["tupleId"]].append(row)
        result.append(row)
    check(
        len(tuple_rows) == 1
        and all(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len({(row["module"], row["version"]) for row in rows}) == 1
            for rows in tuple_rows.values()
        )
        and totals
        == {
            "all": 3_450_700,
            "mod": 301,
            "zip": 3_450_399,
            "entries": 1_550,
            "expanded": 9_108_004,
        }
        and sha256_bytes(
            runner.canonical_json_bytes(accepted_hash_projection)
        )
        == WAVE17_RESOURCE_SET_SHA256,
        "E_WAVE17_AGGREGATE",
    )
    return result


def combined_source_bindings(
    v15: types.ModuleType,
    v14: types.ModuleType,
    v13: types.ModuleType,
    v12: types.ModuleType,
    v11: types.ModuleType,
    v10: types.ModuleType,
    v9: types.ModuleType,
    v8: types.ModuleType,
    v7: types.ModuleType,
    v6: types.ModuleType,
    v5: types.ModuleType,
    v4: types.ModuleType,
    v1: types.ModuleType,
    runner: types.ModuleType,
    v1_documents: Mapping[str, Mapping[str, Any]],
    wave3_documents: Mapping[str, Mapping[str, Any]],
    wave4_documents: Mapping[str, Mapping[str, Any]],
    wave5_documents: Mapping[str, Mapping[str, Any]],
    wave6_documents: Mapping[str, Mapping[str, Any]],
    wave7_documents: Mapping[str, Mapping[str, Any]],
    wave8_documents: Mapping[str, Mapping[str, Any]],
    wave9_documents: Mapping[str, Mapping[str, Any]],
    wave10_documents: Mapping[str, Mapping[str, Any]],
    wave11_documents: Mapping[str, Mapping[str, Any]],
    wave12_documents: Mapping[str, Mapping[str, Any]],
    wave13_documents: Mapping[str, Mapping[str, Any]],
    wave14_documents: Mapping[str, Mapping[str, Any]],
    wave15_documents: Mapping[str, Mapping[str, Any]],
    wave16_documents: Mapping[str, Mapping[str, Any]],
    wave17_documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    bindings = v15.combined_source_bindings(
        v14,
        v13,
        v12,
        v11,
        v10,
        v9,
        v8,
        v7,
        v6,
        v5,
        v4,
        v1,
        runner,
        v1_documents,
        wave3_documents,
        wave4_documents,
        wave5_documents,
        wave6_documents,
        wave7_documents,
        wave8_documents,
        wave9_documents,
        wave10_documents,
        wave11_documents,
        wave12_documents,
        wave13_documents,
        wave14_documents,
        wave15_documents,
        wave16_documents,
    )
    bindings.extend(wave17_request_resources(v4, runner, wave17_documents))
    check(
        len(bindings) == V16_EXPECTED_HELD_SOURCE_INPUT_COUNT
        and sum(row["kind"] == "root_zip" for row in bindings) == 1
        and sum(row["kind"] == "mod" for row in bindings) == 179
        and sum(row["kind"] == "zip" for row in bindings) == 179
        and sum(row["wave"] == "wave1" for row in bindings) == 38
        and sum(row["wave"] == "wave2" for row in bindings) == 30
        and sum(row["wave"] == "wave3" for row in bindings) == 32
        and sum(row["wave"] == "wave4" for row in bindings) == 32
        and sum(row["wave"] == "wave5" for row in bindings) == 30
        and sum(row["wave"] == "wave6" for row in bindings) == 36
        and sum(row["wave"] == "wave7" for row in bindings) == 30
        and sum(row["wave"] == "wave8" for row in bindings) == 28
        and sum(row["wave"] == "wave9" for row in bindings) == 20
        and sum(row["wave"] == "wave10" for row in bindings) == 22
        and sum(row["wave"] == "wave11" for row in bindings) == 18
        and sum(row["wave"] == "wave12" for row in bindings) == 8
        and sum(row["wave"] == "wave13" for row in bindings) == 8
        and sum(row["wave"] == "wave14" for row in bindings) == 8
        and sum(row["wave"] == "wave15" for row in bindings) == 10
        and sum(row["wave"] == "wave16" for row in bindings) == 6
        and sum(row["wave"] == "wave17" for row in bindings) == 2,
        "E_COMBINED_INPUT",
    )
    check(
        len({row["path"] for row in bindings})
        == V16_EXPECTED_HELD_SOURCE_INPUT_COUNT
        and len(
            {
                (row["module"], row["version"])
                for row in bindings
                if row["kind"] != "root_zip"
            }
        )
        == 179,
        "E_COMBINED_INPUT",
    )
    pair_kinds: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in bindings:
        if row["kind"] != "root_zip":
            pair_kinds[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        len(pair_kinds) == 179
        and all(kinds == {"mod", "zip"} for kinds in pair_kinds.values())
        and sorted(order for _, _, order in pair_kinds) == list(range(1, 180)),
        "E_COMBINED_INPUT",
    )
    return bindings


def derive_and_validate_graph_result(
    runner: types.ModuleType,
    graph: Mapping[str, Any],
    route: Mapping[str, Any],
) -> dict[str, Any]:
    frontier = graph.get("exactFrontier")
    new_tuple_count = graph.get("newTupleCount")
    unmapped_count = graph.get("unmappedExternalImportCount")
    unresolved_count = graph.get(
        "unresolvedDeclaredExternalImportCount"
    )
    fixed_point = graph.get("fixedPointReached")
    check(
        type(frontier) is list
        and type(new_tuple_count) is int
        and not isinstance(new_tuple_count, bool)
        and new_tuple_count >= 0
        and type(unmapped_count) is int
        and not isinstance(unmapped_count, bool)
        and unmapped_count >= 0
        and type(unresolved_count) is int
        and not isinstance(unresolved_count, bool)
        and unresolved_count >= 0
        and type(fixed_point) is bool
        and new_tuple_count == len(frontier),
        "E_DERIVED_RESULT",
    )
    logically_fixed = (
        len(frontier) == 0
        and unmapped_count == 0
        and unresolved_count == 0
    )
    if new_tuple_count > 0:
        expected_route = {
            "route": "next_wave_required",
            "status": "combined_graph_discovery_complete_next_wave_required",
            "nextAction": (
                "prepare_separate_versioned_dependency_wave_identity_and_"
                "acquisition_decision"
            ),
        }
    elif unmapped_count > 0 or unresolved_count > 0:
        expected_route = {
            "route": "external_import_resolution_required",
            "status": (
                "combined_graph_discovery_complete_external_import_"
                "resolution_required"
            ),
            "nextAction": (
                "prepare_separate_external_import_resolution_decision"
            ),
        }
    else:
        expected_route = {
            "route": "fixed_point_candidate",
            "status": (
                "combined_graph_discovery_complete_fixed_point_candidate"
            ),
            "nextAction": (
                "prepare_separate_combined_fixed_point_closure_review_"
                "decision"
            ),
        }
    check(
        fixed_point is logically_fixed
        and type(route) is dict
        and route == expected_route,
        "E_DERIVED_RESULT",
    )
    return {
        "fixedPointReached": fixed_point,
        "frontierTupleCount": len(frontier),
        "frontierSha256": sha256_bytes(
            runner.canonical_json_bytes(frontier)
        ),
    }


def validated_tool_binding_paths(
    bindings: Any,
    error_code: str,
) -> set[str]:
    """Return the unique exact paths from one closed tool-binding list."""

    allowed_keys = {
        frozenset({"role", "path", "rawSha256"}),
        frozenset({"role", "path", "normalizedSha256"}),
        frozenset(
            {"role", "path", "rawSha256", "normalizedSha256"}
        ),
    }
    check(type(bindings) is list and len(bindings) > 0, error_code)
    paths: list[str] = []
    roles: list[str] = []
    for row in bindings:
        check(
            type(row) is dict
            and frozenset(row) in allowed_keys
            and type(row.get("role")) is str
            and row["role"] != ""
            and type(row.get("path")) is str
            and row["path"] != ""
            and row["path"].split("/")
            and all(
                part not in {"", ".", ".."}
                for part in row["path"].split("/")
            ),
            error_code,
        )
        for key in ("rawSha256", "normalizedSha256"):
            if key in row:
                digest = row[key]
                check(
                    type(digest) is str
                    and len(digest) == 64
                    and all(
                        character in "0123456789abcdef"
                        for character in digest
                    ),
                    error_code,
                )
        roles.append(row["role"])
        paths.append(row["path"])
    check(
        len(set(roles)) == len(roles)
        and len(set(paths)) == len(paths),
        error_code,
    )
    return set(paths)


def derive_and_validate_tool_paths(
    v15: types.ModuleType,
    predecessor_candidate: Mapping[str, Any],
    direct_tool_bindings: list[dict[str, Any]],
    direct_tool_inputs: tuple[Any, ...],
) -> tuple[set[str], set[str]]:
    """Bind counters to actual held tools and the pinned predecessor chain."""

    declared_v15_paths = v15.TRANSITIVE_CHECKER_PATHS
    expected_declared_paths = {
        f"script/check_p2p_nat_g2_pion_combined_fixed_point_v{version}.py"
        for version in range(1, 16)
    }
    v1_checker_path = (
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
    )
    expected_direct_paths = {
        SELF_PATH,
        V15_CHECKER_PATH,
        V14_CHECKER_PATH,
        V13_CHECKER_PATH,
        V12_CHECKER_PATH,
        V11_CHECKER_PATH,
        V10_CHECKER_PATH,
        V9_CHECKER_PATH,
        V8_CHECKER_PATH,
        V7_CHECKER_PATH,
        V6_CHECKER_PATH,
        V5_CHECKER_PATH,
        V4_CHECKER_PATH,
        v1_checker_path,
        v15.V1_PROVIDER_PATH,
    }
    direct_binding_paths = validated_tool_binding_paths(
        direct_tool_bindings,
        "E_TOOL_BINDINGS",
    )
    predecessor_binding_paths = validated_tool_binding_paths(
        predecessor_candidate.get("toolBindings"),
        "E_TOOL_BINDINGS",
    )
    held_paths = [held.relative_path for held in direct_tool_inputs]
    predecessor_counters = predecessor_candidate.get("operationCounters")
    check(
        type(TRANSITIVE_CHECKER_PATHS) is set
        and TRANSITIVE_CHECKER_PATHS == expected_declared_paths
        and type(declared_v15_paths) is set
        and declared_v15_paths
        == TRANSITIVE_CHECKER_PATHS - {V15_CHECKER_PATH}
        and direct_binding_paths == expected_direct_paths
        and len(held_paths) == len(expected_direct_paths)
        and len(set(held_paths)) == len(held_paths)
        and set(held_paths) == expected_direct_paths
        and predecessor_binding_paths
        == expected_direct_paths - {SELF_PATH}
        and type(predecessor_counters) is dict
        and exact_int(
            predecessor_counters.get("heldToolInputCount"),
            len(predecessor_binding_paths),
        )
        and exact_int(
            predecessor_counters.get("transitiveDistinctToolPathCount"),
            len(
                declared_v15_paths
                | {V15_CHECKER_PATH, v15.V1_PROVIDER_PATH}
            ),
        )
        and V15_TESTS_PATH not in direct_binding_paths
        and V15_TESTS_PATH not in predecessor_binding_paths
        and V14_TESTS_PATH not in direct_binding_paths
        and V14_TESTS_PATH not in predecessor_binding_paths
        and V13_TESTS_PATH not in direct_binding_paths
        and V13_TESTS_PATH not in predecessor_binding_paths
        and V12_TESTS_PATH not in direct_binding_paths
        and V12_TESTS_PATH not in predecessor_binding_paths
        and V11_TESTS_PATH not in direct_binding_paths
        and V11_TESTS_PATH not in predecessor_binding_paths
        and V10_TESTS_PATH not in direct_binding_paths
        and V10_TESTS_PATH not in predecessor_binding_paths
        and V9_TESTS_PATH not in direct_binding_paths
        and V9_TESTS_PATH not in predecessor_binding_paths,
        "E_TOOL_BINDINGS",
    )
    transitive_paths = direct_binding_paths | declared_v15_paths
    check(
        transitive_paths
        == TRANSITIVE_CHECKER_PATHS | {SELF_PATH, V1_PROVIDER_PATH}
        and V15_TESTS_PATH not in transitive_paths
        and V14_TESTS_PATH not in transitive_paths
        and V13_TESTS_PATH not in transitive_paths
        and V12_TESTS_PATH not in transitive_paths
        and V11_TESTS_PATH not in transitive_paths
        and V10_TESTS_PATH not in transitive_paths
        and V9_TESTS_PATH not in transitive_paths,
        "E_TOOL_BINDINGS",
    )
    return direct_binding_paths, transitive_paths


class ReconstructionProtocolState:
    """Opaque proof that the live two-pass reconstruction prefix completed."""

    __slots__ = ("first_graph", "first_coverage", "held_inputs")

    def __init__(
        self,
        first_graph: Mapping[str, Any],
        first_coverage: Mapping[str, Any],
        held_inputs: tuple[Any, ...],
    ) -> None:
        self.first_graph = first_graph
        self.first_coverage = first_coverage
        self.held_inputs = held_inputs


def execute_reconstruction_protocol_prefix(
    root: Path,
    held_inputs: tuple[Any, ...],
    v4: types.ModuleType,
    runner: types.ModuleType,
    wave1_permit: Mapping[str, Any],
    bindings: list[dict[str, Any]],
    source_held: Any,
    limits: Any,
    control_held: Any,
    wave17_documents: Mapping[str, Mapping[str, Any]],
) -> ReconstructionProtocolState:
    """Run namespace-pre, barriers, both reconstructions, and equality."""

    validate_wave17_completed_namespace(control_held, wave17_documents)
    v4.combined_identity_barrier(root, held_inputs)
    first_graph, first_coverage = v4.reconstruct_graph_v3(
        runner,
        wave1_permit,
        bindings,
        source_held,
        limits,
    )
    v4.combined_identity_barrier(root, held_inputs)
    second_graph, second_coverage = v4.reconstruct_graph_v3(
        runner,
        wave1_permit,
        bindings,
        source_held,
        limits,
    )
    check(
        runner.canonical_json_bytes(first_graph)
        == runner.canonical_json_bytes(second_graph)
        and first_coverage == second_coverage,
        "E_REPRODUCTION",
    )
    v4.combined_identity_barrier(root, held_inputs)
    return ReconstructionProtocolState(
        first_graph,
        first_coverage,
        held_inputs,
    )


def finalize_reconstruction_protocol(
    root: Path,
    held_inputs: tuple[Any, ...],
    v4: types.ModuleType,
    control_held: Any,
    wave17_documents: Mapping[str, Mapping[str, Any]],
    state: ReconstructionProtocolState,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Run the final retained-input barrier and namespace-post check."""

    check(
        type(state) is ReconstructionProtocolState
        and state.held_inputs is held_inputs
        and type(candidate) is dict,
        "E_REPRODUCTION_STATE",
    )
    v4.combined_identity_barrier(root, held_inputs)
    validate_wave17_completed_namespace(control_held, wave17_documents)
    return candidate


def generate_candidate(root: Path = ROOT) -> dict[str, Any]:
    global PROVIDER_FACADE_LOAD_COUNT
    global WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
    require_isolated_interpreter()
    HARDENED_CHECKER_PATHS.clear()
    PROVIDER_FACADE_LOAD_COUNT = 0
    WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT = 0
    with (
        PinnedCodeFile(
            root,
            SELF_PATH,
            SELF_NORMALIZED_SHA256,
            normalized_self_bytes,
        ) as self_held,
        PinnedCodeFile(
            root,
            V15_CHECKER_PATH,
            V15_CHECKER_RAW_SHA256,
        ) as v15_held,
        PinnedCodeFile(
            root,
            V14_CHECKER_PATH,
            V14_CHECKER_RAW_SHA256,
        ) as v14_held,
        PinnedCodeFile(
            root,
            V13_CHECKER_PATH,
            V13_CHECKER_RAW_SHA256,
        ) as v13_held,
        PinnedCodeFile(
            root,
            V12_CHECKER_PATH,
            V12_CHECKER_RAW_SHA256,
        ) as v12_held,
        PinnedCodeFile(
            root,
            V11_CHECKER_PATH,
            V11_CHECKER_RAW_SHA256,
        ) as v11_held,
        PinnedCodeFile(
            root,
            V10_CHECKER_PATH,
            V10_CHECKER_RAW_SHA256,
        ) as v10_held,
        PinnedCodeFile(
            root,
            V9_CHECKER_PATH,
            V9_CHECKER_RAW_SHA256,
        ) as v9_held,
        PinnedCodeFile(
            root,
            V8_CHECKER_PATH,
            V8_CHECKER_RAW_SHA256,
        ) as v8_held,
        PinnedCodeFile(
            root,
            V7_CHECKER_PATH,
            V7_CHECKER_RAW_SHA256,
        ) as v7_held,
        PinnedCodeFile(
            root,
            V6_CHECKER_PATH,
            V6_CHECKER_RAW_SHA256,
        ) as v6_held,
        PinnedCodeFile(
            root,
            V5_CHECKER_PATH,
            V5_CHECKER_RAW_SHA256,
        ) as v5_held,
        PinnedCodeFile(
            root,
            V4_CHECKER_PATH,
            V4_CHECKER_RAW_SHA256,
        ) as v4_held,
    ):
        v15 = load_v15_checker(v15_held)
        predecessor_candidate = v15.generate_candidate(root)
        v15 = harden_checker_module(v15)
        v14 = v15.load_v14_checker(v14_held)
        v14 = harden_checker_module(v14)
        v13 = v14.load_v13_checker(v13_held)
        v13 = harden_checker_module(v13)
        v12 = v13.load_v12_checker(v12_held)
        v11 = v12.load_v11_checker(v11_held)
        v10 = v11.load_v10_checker(v10_held)
        v9 = v10.load_v9_checker(v9_held)
        v8 = v9.load_v8_checker(v8_held)
        v7 = v8.load_v7_checker(v7_held)
        v6 = v7.load_v6_checker(v6_held)
        v5 = v6.load_v5_checker(v5_held)
        v4 = v5.load_v4_checker(v4_held)
        with v4.PinnedCodeFile(
            root,
            v4.V1_CHECKER_PATH,
            v4.V1_CHECKER_RAW_SHA256,
        ) as v1_held:
            v1 = v4.load_v1_checker(v1_held)
            with v1.PinnedRunnerFile(root) as provider_held:
                runner = v1.load_pinned_runner(provider_held)
                direct_tool_bindings = [
                    {
                        "role": "current_v16_combined_checker",
                        "path": SELF_PATH,
                        "normalizedSha256": SELF_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v15_combined_checker",
                        "path": V15_CHECKER_PATH,
                        "rawSha256": V15_CHECKER_RAW_SHA256,
                        "normalizedSha256": V15_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v14_combined_checker",
                        "path": V14_CHECKER_PATH,
                        "rawSha256": V14_CHECKER_RAW_SHA256,
                        "normalizedSha256": V14_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v13_combined_checker",
                        "path": V13_CHECKER_PATH,
                        "rawSha256": V13_CHECKER_RAW_SHA256,
                        "normalizedSha256": V13_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v12_combined_checker",
                        "path": V12_CHECKER_PATH,
                        "rawSha256": V12_CHECKER_RAW_SHA256,
                        "normalizedSha256": V12_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v11_combined_checker",
                        "path": V11_CHECKER_PATH,
                        "rawSha256": V11_CHECKER_RAW_SHA256,
                        "normalizedSha256": V11_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v10_combined_checker",
                        "path": V10_CHECKER_PATH,
                        "rawSha256": V10_CHECKER_RAW_SHA256,
                        "normalizedSha256": V10_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v9_combined_checker",
                        "path": V9_CHECKER_PATH,
                        "rawSha256": V9_CHECKER_RAW_SHA256,
                        "normalizedSha256": V9_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v8_combined_checker",
                        "path": V8_CHECKER_PATH,
                        "rawSha256": V8_CHECKER_RAW_SHA256,
                        "normalizedSha256": V8_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v7_combined_checker",
                        "path": V7_CHECKER_PATH,
                        "rawSha256": V7_CHECKER_RAW_SHA256,
                        "normalizedSha256": V7_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v6_combined_checker",
                        "path": V6_CHECKER_PATH,
                        "rawSha256": V6_CHECKER_RAW_SHA256,
                        "normalizedSha256": V6_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v5_combined_checker",
                        "path": V5_CHECKER_PATH,
                        "rawSha256": V5_CHECKER_RAW_SHA256,
                        "normalizedSha256": V5_CHECKER_NORMALIZED_SHA256,
                    },
                    {
                        "role": "immutable_v4_combined_checker",
                        "path": V4_CHECKER_PATH,
                        "rawSha256": V4_CHECKER_RAW_SHA256,
                    },
                    {
                        "role": "immutable_v1_combined_checker",
                        "path": v4.V1_CHECKER_PATH,
                        "rawSha256": v4.V1_CHECKER_RAW_SHA256,
                    },
                    {
                        "role": "immutable_wave1_graph_provider",
                        "path": v4.V1_PROVIDER_PATH,
                        "rawSha256": v4.V1_PROVIDER_RAW_SHA256,
                    },
                ]
                direct_tool_inputs = (
                    self_held,
                    v15_held,
                    v14_held,
                    v13_held,
                    v12_held,
                    v11_held,
                    v10_held,
                    v9_held,
                    v8_held,
                    v7_held,
                    v6_held,
                    v5_held,
                    v4_held,
                    v1_held,
                    provider_held,
                )
                direct_tool_paths, transitive_tool_paths = (
                    derive_and_validate_tool_paths(
                        v15,
                        predecessor_candidate,
                        direct_tool_bindings,
                        direct_tool_inputs,
                    )
                )
                expected_direct_hardened_paths = {
                    str(root / path)
                    for path in (
                        V15_CHECKER_PATH,
                        V14_CHECKER_PATH,
                        V13_CHECKER_PATH,
                        V12_CHECKER_PATH,
                        V11_CHECKER_PATH,
                        V10_CHECKER_PATH,
                        V9_CHECKER_PATH,
                        V8_CHECKER_PATH,
                        V7_CHECKER_PATH,
                        V6_CHECKER_PATH,
                        V5_CHECKER_PATH,
                        V4_CHECKER_PATH,
                        v4.V1_CHECKER_PATH,
                    )
                }
                check(
                    v15.PinnedCodeFile is PinnedCodeFile
                    and v14.PinnedCodeFile is PinnedCodeFile
                    and v13.PinnedCodeFile is PinnedCodeFile
                    and v12.PinnedCodeFile is PinnedCodeFile
                    and v11.PinnedCodeFile is PinnedCodeFile
                    and v10.PinnedCodeFile is PinnedCodeFile
                    and v9.PinnedCodeFile is PinnedCodeFile
                    and v8.PinnedCodeFile is PinnedCodeFile
                    and v7.PinnedCodeFile is PinnedCodeFile
                    and v6.PinnedCodeFile is PinnedCodeFile
                    and v5.PinnedCodeFile is PinnedCodeFile
                    and v4.PinnedCodeFile is PinnedCodeFile
                    and v1.PinnedRunnerFile is SafePinnedRunnerFile
                    and type(runner) is ReadOnlyProviderFacade
                    and HARDENED_CHECKER_PATHS
                    == expected_direct_hardened_paths
                    and predecessor_candidate["checkerVerification"][
                        "hardenedCheckerModuleCount"
                    ] == 14
                    and predecessor_candidate["checkerVerification"][
                        "providerFacadeLoadCount"
                    ] == 14
                    and len(direct_tool_paths) == 15
                    and len(transitive_tool_paths) == 17
                    and PROVIDER_FACADE_LOAD_COUNT == 1,
                    "E_CHECKER_HARDENING",
                )
                controls = (
                    v1.control_bindings()
                    + v4.wave3_control_bindings()
                    + v4.wave4_control_bindings()
                    + v4.wave5_control_bindings()
                    + v5.wave6_control_bindings()
                    + v6.wave7_control_bindings()
                    + v7.wave8_control_bindings()
                    + v8.wave9_control_bindings()
                    + v9.wave10_control_bindings()
                    + v10.wave11_control_bindings()
                    + v11.wave12_control_bindings()
                    + v12.wave13_control_bindings()
                    + v13.wave14_control_bindings()
                    + v14.wave15_control_bindings()
                    + v15.wave16_control_bindings()
                    + wave17_control_bindings()
                )
                auxiliary_evidence = wave17_auxiliary_evidence_bindings()
                check(
                    len(controls) == 115
                    and len(auxiliary_evidence) == 3,
                    "E_CONTROL_CARDINALITY",
                )
                with runner.HeldInputSet(
                    root,
                    controls + auxiliary_evidence,
                ) as control_held:
                    v1_documents = v1.parse_control_documents(
                        runner,
                        control_held,
                    )
                    v1.validate_terminal_documents(runner, v1_documents)
                    wave3_documents = v4.parse_wave3_documents(
                        runner,
                        control_held,
                    )
                    wave4_documents = v4.parse_wave4_documents(
                        runner,
                        control_held,
                    )
                    wave5_documents = v4.parse_wave5_documents(
                        runner,
                        control_held,
                    )
                    wave6_documents = v5.parse_wave6_documents(
                        runner,
                        control_held,
                    )
                    wave7_documents = v6.parse_wave7_documents(
                        runner,
                        control_held,
                    )
                    wave8_documents = v7.parse_wave8_documents(
                        runner,
                        control_held,
                    )
                    wave9_documents = v8.parse_wave9_documents(
                        runner,
                        control_held,
                    )
                    wave10_documents = v9.parse_wave10_documents(
                        runner,
                        control_held,
                    )
                    wave11_documents = v10.parse_wave11_documents(
                        runner,
                        control_held,
                    )
                    wave12_documents = v11.parse_wave12_documents(
                        runner,
                        control_held,
                    )
                    wave13_documents = v12.parse_wave13_documents(
                        runner,
                        control_held,
                    )
                    wave14_documents = v13.parse_wave14_documents(
                        runner,
                        control_held,
                    )
                    wave15_documents = v14.parse_wave15_documents(
                        runner,
                        control_held,
                    )
                    wave16_documents = v15.parse_wave16_documents(
                        runner,
                        control_held,
                    )
                    wave17_documents = parse_wave17_documents(
                        runner,
                        control_held,
                    )
                    predecessor_verification = (
                        validate_v15_predecessor_candidate(
                            runner,
                            predecessor_candidate,
                            wave17_documents[WAVE17_DECISION_PATH],
                        )
                    )
                    bindings = combined_source_bindings(
                        v15,
                        v14,
                        v13,
                        v12,
                        v11,
                        v10,
                        v9,
                        v8,
                        v7,
                        v6,
                        v5,
                        v4,
                        v1,
                        runner,
                        v1_documents,
                        wave3_documents,
                        wave4_documents,
                        wave5_documents,
                        wave6_documents,
                        wave7_documents,
                        wave8_documents,
                        wave9_documents,
                        wave10_documents,
                        wave11_documents,
                        wave12_documents,
                        wave13_documents,
                        wave14_documents,
                        wave15_documents,
                        wave16_documents,
                        wave17_documents,
                    )
                    wave17_evidence_raw = control_held.raw[WAVE17_EVIDENCE_PATH]
                    wave17_evidence_document = runner.strict_json(
                        wave17_evidence_raw,
                        WAVE17_EVIDENCE_PATH,
                    )
                    validate_wave17_evidence(
                        runner,
                        wave17_evidence_raw,
                        wave17_evidence_document,
                        wave17_documents,
                    )
                    validate_wave17_consumed_claims(
                        runner,
                        control_held.raw[WAVE17_ACQUISITION_CLAIM_PATH],
                        control_held.raw[WAVE17_READBACK_CLAIM_PATH],
                    )
                    with runner.HeldInputSet(root, bindings) as source_held:
                        held_inputs = (
                            self_held,
                            v15_held,
                            v14_held,
                            v13_held,
                            v12_held,
                            v11_held,
                            v10_held,
                            v9_held,
                            v8_held,
                            v7_held,
                            v6_held,
                            v5_held,
                            v4_held,
                            v1_held,
                            provider_held,
                            control_held,
                            source_held,
                        )
                        limits = {
                            **v1.graph_limits(runner),
                            "maximumAggregateUncompressedBytes":
                                V16_EXPECTED_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
                        }
                        reconstruction_state = (
                            execute_reconstruction_protocol_prefix(
                                root,
                                held_inputs,
                                v4,
                                runner,
                                v1_documents[v1.WAVE1_PERMIT_PATH],
                                bindings,
                                source_held,
                                limits,
                                control_held,
                                wave17_documents,
                            )
                        )
                        first_graph = reconstruction_state.first_graph
                        first_coverage = reconstruction_state.first_coverage
                        check(
                            exact_int(
                                first_coverage.get("archiveCount"),
                                V16_EXPECTED_ARCHIVE_COUNT,
                            )
                            and exact_int(
                                first_coverage.get("aggregateEntryCount"),
                                V16_EXPECTED_AGGREGATE_ENTRY_COUNT,
                            )
                            and exact_int(
                                first_coverage.get(
                                    "aggregateUncompressedByteCount"
                                ),
                                (
                                    V16_EXPECTED_MAXIMUM_AGGREGATE_
                                    UNCOMPRESSED_BYTES
                                ),
                            )
                            ),
                            "E_COMBINED_INPUT",
                        )
                        validate_wave9_legacy_build_compatibility_count(
                            WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
                        )
                        projection = v1.source_projection(bindings)
                        check(
                            len(projection)
                            == V16_EXPECTED_HELD_SOURCE_INPUT_COUNT
                            and sum(
                                row["maximumBytes"] for row in bindings
                            ) == V16_EXPECTED_AGGREGATE_RAW_BYTE_SIZE
                            and sha256_bytes(
                                runner.canonical_json_bytes(projection)
                            ) == V16_INPUT_SET_SHA256
                            and sha256_bytes(wave17_digest_bytes(projection))
                            == V16_SOURCE_BINDINGS_SHA256,
                            "E_COMBINED_INPUT",
                        )
                        route = v1.route_for_graph(first_graph)
                        frontier = first_graph["exactFrontier"]
                        derived_result = derive_and_validate_graph_result(
                            runner,
                            first_graph,
                            route,
                        )
                        fixed_point = derived_result["fixedPointReached"]
                        profiles = runner.profile_rows(
                            v1_documents[v1.WAVE1_PERMIT_PATH]
                        )
                        validate_wave9_legacy_build_profile_equivalence(
                            profiles
                        )
                        inherited_reconstructions = predecessor_candidate[
                            "checkerVerification"
                        ]["totalFullInputReconstructionCount"]
                        inherited_source_reconstructions = (
                            predecessor_candidate["operationCounters"][
                                "totalFullSourceReconstructionCount"
                            ]
                        )
                        body = {
                            "documentType": (
                                "aetherlink.g2-pion-combined-wave1-wave2-"
                                "wave3-wave4-wave5-wave6-wave7-wave8-"
                                "wave9-wave10-wave11-wave12-wave13-wave14-"
                                "wave15-wave16-wave17-"
                                "fixed-point-candidate"
                            ),
                            "schemaVersion": "16.0",
                            "checkerId": CHECKER_ID,
                            "status": route["status"],
                            "result": (
                                "combined_graph_recomputed_twice_from_exact_"
                                "wave1_through_wave17_source_bytes"
                            ),
                            "verificationOnly": True,
                            "recordModeExposed": False,
                            "sourceInspectionPolicy": (
                                predecessor_candidate[
                                    "sourceInspectionPolicy"
                                ]
                            ),
                            "wave9LegacyBuildCompatibilityPolicy": {
                                "configuredProfileInclusionEquivalent": True,
                                "directReconstructionApplicationCount": 4,
                                "expectedExpression":
                                    WAVE9_LEGACY_BUILD_EXPRESSION,
                                "fallbackErrorCode":
                                    "E_BUILD_CONSTRAINT",
                                "fallbackErrorPhase": "source_inventory",
                                "go111TrailingWordOrSemanticsChecked": True,
                                "normalizedSourceSha256":
                                    WAVE9_LEGACY_BUILD_NORMALIZED_SHA256,
                                "originalLineOccurrenceCount": 1,
                                "originalProviderParserTriedFirst": True,
                                "rawSourceSha256":
                                    WAVE9_LEGACY_BUILD_SOURCE_SHA256,
                                "sourceBytesModified": False,
                            },
                            "inputSet": {
                                "heldSourceInputCount": len(bindings),
                                "rootArchiveCount": 1,
                                "resourceCount": 358,
                                "modCount": 179,
                                "zipCount": 179,
                                "wave1ResourceCount": 38,
                                "wave2ResourceCount": 30,
                                "wave3ResourceCount": 32,
                                "wave4ResourceCount": 32,
                                "wave5ResourceCount": 30,
                                "wave6ResourceCount": 36,
                                "wave7ResourceCount": 30,
                                "wave8ResourceCount": 28,
                                "wave9ResourceCount": 20,
                                "wave10ResourceCount": 22,
                                "wave11ResourceCount": 18,
                                "wave12ResourceCount": 8,
                                "wave13ResourceCount": 8,
                                "wave14ResourceCount": 8,
                                "wave15ResourceCount": 10,
                                "wave16ResourceCount": 6,
                                "wave17ResourceCount": 2,
                                "uniqueModuleVersionTupleCount": 179,
                                "aggregateRawByteSize": sum(
                                    row["maximumBytes"] for row in bindings
                                ),
                                "sourceBindings": projection,
                                "combinedInputSetSha256": sha256_bytes(
                                    runner.canonical_json_bytes(projection)
                                ),
                                "wave1OrderedSourceSetSha256": v1_documents[
                                    v1.WAVE1_PERMIT_PATH
                                ]["inputBindings"]["orderedSourceSetSha256"],
                                "wave2OrderedSourceSetSha256": v1_documents[
                                    v1.WAVE2_RECEIPT_PATH
                                ]["orderedSourceSetSha256"],
                                "wave3AcceptedResourceSetSha256":
                                    v4.WAVE3_RESOURCE_SET_SHA256,
                                "wave4AcceptedResourceSetSha256":
                                    v4.WAVE4_RESOURCE_SET_SHA256,
                                "wave5AcceptedResourceSetSha256":
                                    v4.WAVE5_RESOURCE_SET_SHA256,
                                "wave6AcceptedResourceSetSha256":
                                    v5.WAVE6_RESOURCE_SET_SHA256,
                                "wave7AcceptedResourceSetSha256":
                                    v6.WAVE7_RESOURCE_SET_SHA256,
                                "wave8AcceptedResourceSetSha256":
                                    v7.WAVE8_RESOURCE_SET_SHA256,
                                "wave9AcceptedResourceSetSha256":
                                    v8.WAVE9_RESOURCE_SET_SHA256,
                                "wave10AcceptedResourceSetSha256":
                                    v9.WAVE10_RESOURCE_SET_SHA256,
                                "wave11AcceptedResourceSetSha256":
                                    v10.WAVE11_RESOURCE_SET_SHA256,
                                "wave12AcceptedResourceSetSha256":
                                    v11.WAVE12_RESOURCE_SET_SHA256,
                                "wave13AcceptedResourceSetSha256":
                                    v12.WAVE13_RESOURCE_SET_SHA256,
                                "wave14AcceptedResourceSetSha256":
                                    v13.WAVE14_RESOURCE_SET_SHA256,
                                "wave15AcceptedResourceSetSha256":
                                    v14.WAVE15_RESOURCE_SET_SHA256,
                                "wave16AcceptedResourceSetSha256":
                                    v15.WAVE16_RESOURCE_SET_SHA256,
                                "wave17AcceptedResourceSetSha256":
                                    WAVE17_RESOURCE_SET_SHA256,
                            },
                            "toolBindings": direct_tool_bindings,
                            "terminalEvidenceBindings": [
                                {
                                    "path": row["path"],
                                    "rawSha256": row["rawSha256"],
                                }
                                for row in controls
                            ],
                            "auxiliaryEvidenceBindings": [
                                {
                                    "path": row["path"],
                                    "rawSha256": row["rawSha256"],
                                }
                                for row in auxiliary_evidence
                            ],
                            "predecessorVerification":
                                predecessor_verification,
                            "coverage": first_coverage,
                            "profiles": profiles,
                            "graphDiscovery": first_graph,
                            "derivedResult": derived_result,
                            "checkerVerification": {
                                "directFullInputReconstructionCount": 2,
                                "inheritedFullInputReconstructionCount":
                                    inherited_reconstructions,
                                "totalFullInputReconstructionCount":
                                    inherited_reconstructions + 2,
                                "underlyingIndependentGraphAlgorithmCount":
                                    predecessor_candidate[
                                        "checkerVerification"
                                    ][
                                        "underlyingIndependentGraphAlgorithmCount"
                                    ]
                                    + 4,
                                "pinnedV15PredecessorExecuted": True,
                                "v15TestsBindingScope":
                                    "historical_metadata_only_not_live_held",
                                "v15TestsLiveHeld": False,
                                "canonicalGraphEqualityVerified": True,
                                "barrierBeforeReconstructionCompleted": True,
                                "barrierBetweenReconstructionsCompleted": True,
                                "barrierAfterReconstructionCompleted": True,
                                "workspaceRootIdentityBoundAcrossAllInputs":
                                    True,
                                "calculatedFixedPointCandidate": fixed_point,
                                "wave17HistoricalExact21FrozenSnapshotDescriptorSetBound":
                                    True,
                                "wave17LiveTerminalControlMetadataVerified":
                                    True,
                                "wave17LiveFinalAndAcceptedInventoriesVerified":
                                    True,
                                "wave17FinalNamespaceReverifiedAfterReconstruction":
                                    True,
                                "wave17RetainedFdPreManifestBarrierCount": 3,
                                "wave17CompletionAppliesToRetainedSnapshot":
                                    True,
                                "wave17CurrentPathIdentityGuaranteedThroughManifestPublication":
                                    False,
                                "wave17SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                                    False,
                                "transitiveSafePinnedClassesVerified":
                                    True,
                                "readOnlyProviderFacadeVerified": True,
                                "providerFacadeVerificationScope": (
                                    "trusted_pinned_normal_reconstruction_path"
                                ),
                                "hardenedCheckerModuleCount":
                                    predecessor_candidate[
                                        "checkerVerification"
                                    ]["hardenedCheckerModuleCount"] + 1,
                                "providerFacadeLoadCount":
                                    predecessor_candidate[
                                        "checkerVerification"
                                    ]["providerFacadeLoadCount"]
                                    + PROVIDER_FACADE_LOAD_COUNT,
                                "wave9PinnedLegacyBuildCompatibilityCount":
                                    WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
                            },
                            "route": route["route"],
                            "nextAction": route["nextAction"],
                            "operationCounters": {
                                "heldSourceInputCount": len(bindings),
                                "heldTerminalEvidenceCount": len(controls),
                                "heldAuxiliaryEvidenceCount":
                                    len(auxiliary_evidence),
                                "heldToolInputCount":
                                    len(direct_tool_paths),
                                "transitiveDistinctToolPathCount":
                                    len(transitive_tool_paths),
                                "stableReadPassesPerHeldInput": 2,
                                "directFullSourceReconstructionCount": 2,
                                "inheritedFullSourceReconstructionCount":
                                    inherited_source_reconstructions,
                                "totalFullSourceReconstructionCount":
                                    inherited_source_reconstructions + 2,
                                "directArchiveOpenCount":
                                    first_coverage["archiveCount"] * 2,
                                "inheritedArchiveOpenCount":
                                    predecessor_candidate[
                                        "operationCounters"
                                    ]["archiveOpenCount"],
                                "totalArchiveOpenCount": (
                                    predecessor_candidate[
                                        "operationCounters"
                                    ]["archiveOpenCount"]
                                    + first_coverage["archiveCount"] * 2
                                ),
                                "archiveOpenCount": (
                                    predecessor_candidate[
                                        "operationCounters"
                                    ]["archiveOpenCount"]
                                    + first_coverage["archiveCount"] * 2
                                ),
                                "archiveExtractionCount": 0,
                                "dependencySourceLoadCount": 0,
                                "dependencySourceExecutionCount": 0,
                                "dependencySourceCompileCount": 0,
                                "subprocessCount": 0,
                                "networkOperationCount": 0,
                                "fileWriteCount": 0,
                                "wave9PinnedLegacyBuildCompatibilityCount":
                                    WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT,
                            },
                            "closure": {
                                "dependencyFixedPointReached": fixed_point,
                                "dependencySourceReviewed": False,
                                "dependencyClosureComplete": False,
                                "semanticClosureComplete": False,
                                "licenseCompatibilityReviewed": False,
                                "securityReviewComplete": False,
                                "rungThreeComplete": False,
                                "candidateSelected": False,
                                "librarySelected": False,
                                "releaseReady": False,
                            },
                            "authority": {
                                "decisionAuthorityGranted": False,
                                "executionAuthorityGranted": False,
                                "acquisitionAuthorityGranted": False,
                                "publicationAuthorityGranted": False,
                                "networkAuthorized": False,
                                "sourceExecutionAuthorized": False,
                                "filesystemExtractionAuthorized": False,
                                "subprocessAuthorized": False,
                                "fileWriteAuthorized": False,
                                "gitWriteAuthorized": False,
                                "repositoryOwnerIdentityProofRequired": False,
                                "externalAuthenticationRequired": False,
                                "passwordRequired": False,
                                "privateKeyRequired": False,
                                "signatureRequired": False,
                                "tokenRequired": False,
                                "userActionRequired": False,
                                "osSyscallSandboxProvided": False,
                            },
                        }
                        candidate = runner.content_bound(
                            body,
                            "candidate_without_contentBinding",
                        )
                        return finalize_reconstruction_protocol(
                            root,
                            held_inputs,
                            v4,
                            control_held,
                            wave17_documents,
                            reconstruction_state,
                            candidate,
                        )


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def error_document_bytes() -> bytes:
    return (
        json.dumps(
            {
                "documentType": (
                    "aetherlink.g2-pion-combined-wave1-through-wave17-"
                    "fixed-point-check-error"
                ),
                "schemaVersion": "16.0",
                "status": "verification_failed",
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def emit_error_document() -> int:
    try:
        sys.stdout.buffer.write(error_document_bytes())
    except Exception:
        pass
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parse_arguments(argv)
        candidate = generate_candidate(ROOT)
        sys.stdout.buffer.write(
            json.dumps(
                candidate,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        return 0
    except (CombinedCheckFailure, CliUsageFailure, OSError, ValueError):
        return emit_error_document()
    except Exception:
        return emit_error_document()


if __name__ == "__main__":
    raise SystemExit(main())
