#!/usr/bin/env python3
"""Recompute the exact 317-input Wave1..Wave11 graph without publishing.

Run only with ``python3 -I -B -S``. The checker pins the immutable v9
combined checker, all Wave11 decision/acquisition/readback controls, and the
root archive plus 158 mod and 158 zip inputs. Every source input is opened
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
            "combined fixed-point v10 checker requires unoptimized "
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
SELF_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py"
SELF_NORMALIZED_SHA256 = (
    "ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751"
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
    for version in range(1, 10)
}
CHECKER_ID = (
    "g2-pion-ice-v4.3.0-combined-wave1-wave2-wave3-wave4-wave5-wave6-"
    "wave7-wave8-wave9-wave10-wave11-check-v10"
)
CODE_MAXIMUM_BYTES = 4 * 1024 * 1024
JSON_MAXIMUM_BYTES = 8 * 1024 * 1024
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)

WAVE11_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave11-v1.json"
)
WAVE11_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave11-"
    "execution-permit-v1.json"
)
WAVE11_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave11-receipt-v1.json"
)
WAVE11_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave11-manifest-v1.json"
)
WAVE11_READBACK_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave11-"
    "readback-execution-permit-v1.json"
)
WAVE11_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave11-readback-v1.json"
)
WAVE11_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave11-"
    "readback-manifest-v1.json"
)
WAVE11_ACCEPTED_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-11-v1/accepted"
)
WAVE11_ACQUISITION_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-11-v1.claim"
)
WAVE11_EVIDENCE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-11-v1/evidence.json"
)
WAVE11_READBACK_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-11-v1-readback.claim"
)
WAVE11_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave11-failure-v1.json"
)
WAVE11_STAGING_PREFIX = ".wave-11-v1-staging-"
WAVE11_READBACK_TEMP_PREFIXES = (
    ".bounded-dependency-source-acquisition-wave11-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave11-readback-"
        "manifest-v1.json.tmp-"
    ),
)

WAVE11_CONTROL_SHA256 = {
    WAVE11_DECISION_PATH:
        "e1f3a82025c711694cb6551a53407aa1164493396a65f383eacf95dbf90b881a",
    WAVE11_PERMIT_PATH:
        "9d8d2aa4d5be23575ef42aecf3fd2dffb37a1af56e86a208bc85a63f167f342e",
    WAVE11_RECEIPT_PATH:
        "0c35d330476362fdaba23192229d8aa0fa096c0f47fddb39955f8976db6115a8",
    WAVE11_MANIFEST_PATH:
        "ac247bed91f7cbe50c90d8a640b885ca1adaa2888fa8447f6ea0baeb4a046a15",
    WAVE11_READBACK_PERMIT_PATH:
        "9ea9f661983668efc648bae0d854e225dfd04252b41fef0782dbd7e4a628408b",
    WAVE11_READBACK_PATH:
        "f89904b359aed770e89ed8de25b775d6b920d7eef3d32bdc464a486a862cc5ca",
    WAVE11_READBACK_MANIFEST_PATH:
        "0bda6e5da9609ddd375e20a6692a4cec46aaf930acee4861c5168efde1f18c0e",
}
WAVE11_CONTROL_METADATA = {
    WAVE11_DECISION_PATH: (21_635, 0o644),
    WAVE11_PERMIT_PATH: (24_733, 0o644),
    WAVE11_RECEIPT_PATH: (1_669, 0o600),
    WAVE11_MANIFEST_PATH: (465, 0o600),
    WAVE11_READBACK_PERMIT_PATH: (20_834, 0o644),
    WAVE11_READBACK_PATH: (11_284, 0o600),
    WAVE11_READBACK_MANIFEST_PATH: (2_302, 0o600),
}
WAVE11_CONTENT_SHA256 = {
    WAVE11_DECISION_PATH:
        "1bdb93f69c6a44d977a701dab83ea847a5ff473bb18e41bf093ed45bc4c1647f",
    WAVE11_PERMIT_PATH:
        "54886d2f90038608b21169806cc59dfad4038a0901031c1e7a514107ede5fe82",
    WAVE11_READBACK_PERMIT_PATH:
        "7300bdf634e665b9493609b5554e9cf239098d78d852456907698116297e9eed",
    WAVE11_READBACK_PATH:
        "3de4c751bc8eba2939650e9dd4390d9deab2c63d3b998b916917941395beab14",
    WAVE11_READBACK_MANIFEST_PATH:
        "e7ba4f973d9721c19b13797c99fa910501cb05cd8f27bbaa6cab49510b18a25f",
}
WAVE11_REQUEST_SET_SHA256 = (
    "bbde21b5f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8"
)
WAVE11_PERMIT_RESOURCES_SHA256 = (
    "9b317cf532f33691bb13b5f7dfa26e06cbc56cf10bb62e306afad73dd069df74"
)
WAVE11_RESOURCE_SET_SHA256 = (
    "0758fe642e04c87effccded19eeb00651147b93121708100fe8f416a2bff16bc"
)
WAVE11_FROZEN_FILE_SET_SHA256 = (
    "de68dee0b6b2157ac3d30726cc876fb7cd13e9c1556e44f1d3f8d56b3521dc0f"
)
WAVE11_ATTEMPT_ID = "ac18b8fda0a80a132510efd5dd17d5b7"
WAVE11_READBACK_ATTEMPT_ID = "9b4dac65f66ce9e5d53dcd8edaf4d1d4"
WAVE11_COMPACT_IDENTITY_SHA256 = (
    "8e6e8473c3938f40dbbffb090c26a73bf965c247df33c8ead5c04341b74adbc4"
)
WAVE11_FULL_WITNESS_SHA256 = (
    "ea353c9595bbe020bd908347b9576bc7e8c820047735e768cc2d7ac37dc2713e"
)
WAVE11_HELD_SOURCE_BINDINGS_SHA256 = (
    "2455ab16e4c1dd6a68127c38f25d49275d9ef955d4d12ad711d644f0d745839f"
)
WAVE11_ACQUISITION_CLAIM_RAW_SHA256 = (
    "a41663bd827b8f07e0e04e887b21a7306c0ba286396e43d854ea3f2369a3e985"
)
WAVE11_ACQUISITION_EVIDENCE_RAW_SHA256 = (
    "c4194219b35723fb61ee41fca23a10ffe5f2c18f01f82fb70856a404019fb797"
)
WAVE11_ACQUISITION_CHECKER_RAW_SHA256 = (
    "72c6709e51dff3753f7ca92b2a64bcb6ed3057573798e05c829184f627b8fd87"
)
WAVE11_ACQUISITION_RUNNER_RAW_SHA256 = (
    "ca6849f3ca9a47c4bb3f1e1efe477dd24e21419895fdc7ce738bbe41737b55a0"
)
WAVE11_READBACK_CLAIM_RAW_SHA256 = (
    "752c0fdc006688a4c22dc26f54be1c9bb4498e9a94f196217aebfaff8e61dc13"
)
WAVE11_READBACK_CLAIM_CONTENT_SHA256 = (
    "26ee90e890eedfebd6ac4d840871b153fcd4de7b6213613d782f63644b2b8510"
)
WAVE11_READBACK_CHECKER_RAW_SHA256 = (
    "895fad76d8563ebd57d7f8ca31d8cb44d15724414550d1eb1bc22c4f3d4cc124"
)
WAVE11_READBACK_RECORDER_RAW_SHA256 = (
    "5917493ad7506ce214a4df545b2326673d535969d2455cf310a019aff0a2e1d3"
)
WAVE11_READBACK_RECORDER_NORMALIZED_SHA256 = (
    "5c636671fd20c63141bf73e3ef82a317fb06fad035fa62c959ec8480a9825727"
)
WAVE11_RETAINED_BARRIERS = [
    "complete_snapshot_and_claim_immediately_before_receipt",
    "complete_snapshot_claim_and_receipt_after_receipt",
    (
        "complete_snapshot_claim_and_receipt_immediately_before_"
        "manifest_publication"
    ),
]
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
V10_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES = 1_098_221_637
V9_CANDIDATE_CONTENT_SHA256 = (
    "9c9e995f853a8dbbc07d55d41ce1c5660cb616d879b3565803e13b6aaf4532ba"
)
V9_GRAPH_SHA256 = (
    "4367fc6c4c5efb69f948d8e040c2cfa496345102631719692d31feabb794a6b5"
)
V9_FRONTIER_SHA256 = (
    "171af951e3a67405b62ddceface1341bb6f64b08f370d3d216ede541bd011f06"
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
WAVE11_DECISION_AUTHORITY = {
    "acquisitionAuthorityGranted": False,
    "authenticationRequired": False,
    "compileAuthorized": False,
    "decisionAuthorityGranted": False,
    "dependencySourceExecutionAuthorized": False,
    "dnsAuthorized": False,
    "executionAuthorityGranted": False,
    "externalAuthenticationRequired": False,
    "fileWriteAuthorized": False,
    "filesystemExtractionAuthorized": False,
    "gitWriteAuthorized": False,
    "networkAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "publicationAuthorityGranted": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "socketAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}

WAVE11_ACQUISITION_AUTHORITY = {
    "accountRequired": False,
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
    "wave11PublicProxy18GetAcquisitionAuthorizedOnce": True,
}
WAVE11_READBACK_AUTHORITY = {
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
WAVE11_READBACK_AUTHORITY_BINDING = {
    "checker": {
        "path": (
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave11_"
            "readback_execution_permit_v1.py"
        ),
        "rawSha256": WAVE11_READBACK_CHECKER_RAW_SHA256,
    },
    "permit": {
        "contentSha256": WAVE11_CONTENT_SHA256[WAVE11_READBACK_PERMIT_PATH],
        "path": WAVE11_READBACK_PERMIT_PATH,
        "rawSha256": WAVE11_CONTROL_SHA256[WAVE11_READBACK_PERMIT_PATH],
    },
    "recorder": {
        "path": (
            "script/record_p2p_nat_g2_pion_rung3_dependency_wave11_"
            "readback_v1_once.py"
        ),
        "rawSha256": WAVE11_READBACK_RECORDER_RAW_SHA256,
    },
}
WAVE11_DECISION_TOOL_BINDINGS = [
    {
        "normalizedSha256":
            "5b4cf2878c2f659815876965bd8ff5aefe7853e01180103854455ee06faabe4f",
        "path":
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave11_decision_v1.py",
        "role": "current_wave11_decision_checker",
    },
    {
        "path":
            "script/test_p2p_nat_g2_pion_rung3_dependency_wave11_decision_v1.py",
        "rawSha256":
            "b124eb04e26faa66ab9a194ae945583e8eedf3f4788fa23122f50e86b46a35cc",
        "role": "current_wave11_decision_tests",
    },
    {
        "normalizedSha256": V9_CHECKER_NORMALIZED_SHA256,
        "path": V9_CHECKER_PATH,
        "rawSha256": V9_CHECKER_RAW_SHA256,
        "role": "immutable_combined_v9_checker",
    },
    {
        "path": V9_TESTS_PATH,
        "rawSha256": V9_TESTS_RAW_SHA256,
        "role": "immutable_combined_v9_tests",
    },
]
WAVE11_ACQUISITION_TOOL_BINDINGS = [
    {
        "path":
            "script/check_p2p_nat_g2_pion_rung3_dependency_wave11_acquisition_v1.py",
        "rawSha256": WAVE11_ACQUISITION_CHECKER_RAW_SHA256,
    },
    {
        "path":
            "script/test_p2p_nat_g2_pion_rung3_dependency_wave11_acquisition_v1.py",
        "rawSha256":
            "77ea295e4c8c1b60854cfec0170655a22c0b7f5ced09324bedda9805e18a1ac2",
    },
    {
        "path":
            "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave11_v1_once.py",
        "rawSha256": WAVE11_ACQUISITION_RUNNER_RAW_SHA256,
    },
    {
        "path":
            "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave11_v1_once.py",
        "rawSha256":
            "79ae96707650e63dfcc73e8825e53ceb51283069b9958bf3af0949681b684aca",
    },
]
WAVE11_READBACK_TOOL_BINDINGS = [
    WAVE11_READBACK_AUTHORITY_BINDING["checker"],
    {
        "path": (
            "script/test_p2p_nat_g2_pion_rung3_dependency_wave11_"
            "readback_execution_permit_v1.py"
        ),
        "rawSha256":
            "3b8dc394bc59da6b613848b6f9f20dde3fcf4fe9fc996f73ccd5e0a94e7b7bb5",
    },
    WAVE11_READBACK_AUTHORITY_BINDING["recorder"],
    {
        "path": (
            "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave11_"
            "readback_v1_once.py"
        ),
        "rawSha256":
            "c32893bb1473d102e27fa19db150839c80683f24932b48affb56da1ed58f8179",
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


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wave11_digest_bytes(value: Any) -> bytes:
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

    if module.__dict__.get("_v10_safe_hardened") is True:
        return module
    module.__dict__["_v10_safe_hardened"] = True
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


def wave11_control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": WAVE11_CONTROL_METADATA[path][1] == 0o600,
            "kind": "terminal_evidence",
        }
        for path, digest in WAVE11_CONTROL_SHA256.items()
    ]


def parse_wave11_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in WAVE11_CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_WAVE11_JSON")
        result[path] = value
    return result


def wave11_auxiliary_evidence_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": WAVE11_ACQUISITION_CLAIM_PATH,
            "rawSha256": WAVE11_ACQUISITION_CLAIM_RAW_SHA256,
            "maximumBytes": 417,
            "ownerOnly": True,
            "kind": "consumed_acquisition_claim",
        },
        {
            "path": WAVE11_EVIDENCE_PATH,
            "rawSha256": WAVE11_ACQUISITION_EVIDENCE_RAW_SHA256,
            "maximumBytes": 7_405,
            "ownerOnly": True,
            "kind": "frozen_acquisition_evidence",
        },
        {
            "path": WAVE11_READBACK_CLAIM_PATH,
            "rawSha256": WAVE11_READBACK_CLAIM_RAW_SHA256,
            "maximumBytes": 1_255,
            "ownerOnly": True,
            "kind": "consumed_readback_claim",
        },
    ]


def portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def validate_wave11_completed_namespace(
    control_held: Any,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    acquisition_claim = control_held.files[WAVE11_ACQUISITION_CLAIM_PATH]
    readback_claim = control_held.files[WAVE11_READBACK_CLAIM_PATH]
    evidence = control_held.files[WAVE11_EVIDENCE_PATH]
    readback = control_held.files[WAVE11_READBACK_PATH]
    readback_manifest = control_held.files[WAVE11_READBACK_MANIFEST_PATH]
    for path, (expected_bytes, expected_mode) in WAVE11_CONTROL_METADATA.items():
        info = os.fstat(control_held.files[path].fd)
        check(
            info.st_uid == os.geteuid()
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == expected_mode
            and info.st_size == expected_bytes,
            "E_WAVE11_CONTROL_METADATA",
        )
    for held, expected_bytes in (
        (acquisition_claim, 417),
        (evidence, 7_405),
        (readback_claim, 1_255),
    ):
        info = os.fstat(held.fd)
        check(
            info.st_uid == os.geteuid()
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == expected_bytes,
            "E_WAVE11_AUXILIARY_METADATA",
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
        Path(WAVE11_ACQUISITION_CLAIM_PATH).name,
        Path(WAVE11_READBACK_CLAIM_PATH).name,
    }
    exact_base_names = {
        Path(path).name for path in WAVE11_CONTROL_SHA256
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
            name.startswith(portable_name(WAVE11_STAGING_PREFIX))
            for name in normalized_dependency_names
        )
        and portable_name(Path(WAVE11_FAILURE_PATH).name)
        not in normalized_base_names
        and not any(
            name.startswith(portable_name(prefix))
            for name in normalized_base_names
            for prefix in WAVE11_READBACK_TEMP_PREFIXES
        )
        and len(final_names) == len(exact_final_names)
        and set(final_names) == exact_final_names
        and len(set(normalized_final_names)) == len(exact_final_names),
        "E_WAVE11_NAMESPACE",
    )
    check(
        readback.parent_fd == readback_manifest.parent_fd
        or directory_identity(os.fstat(readback.parent_fd))
        == directory_identity(os.fstat(readback_manifest.parent_fd)),
        "E_WAVE11_NAMESPACE",
    )
    final_info = os.fstat(evidence.parent_fd)
    check(
        final_info.st_uid == os.geteuid()
        and final_info.st_nlink == 4
        and stat.S_IMODE(final_info.st_mode) == 0o700,
        "E_WAVE11_NAMESPACE",
    )

    readback_permit = documents[WAVE11_READBACK_PERMIT_PATH]
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
        type(accepted_files) is list and len(accepted_files) == 18,
        "E_WAVE11_NAMESPACE",
    )
    expected_accepted_names = {
        Path(row.get("path", "")).name
        for row in accepted_files
        if type(row) is dict and type(row.get("path")) is str
    }
    check(
        len(expected_accepted_names) == 18
        and all(
            Path(row["path"]).parent.as_posix() == WAVE11_ACCEPTED_DIRECTORY
            for row in accepted_files
        ),
        "E_WAVE11_NAMESPACE",
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
            and accepted_info.st_nlink == 20
            and stat.S_IMODE(accepted_info.st_mode) == 0o700
            and len(accepted_names) == 18
            and set(accepted_names) == expected_accepted_names
            and len(set(normalized_accepted_names)) == 18,
            "E_WAVE11_NAMESPACE",
        )
    finally:
        if accepted_fd >= 0:
            os.close(accepted_fd)


def validate_wave11_consumed_claims(
    runner: types.ModuleType,
    acquisition_raw: bytes,
    readback_raw: bytes,
) -> None:
    acquisition_claim = runner.strict_json(
        acquisition_raw,
        WAVE11_ACQUISITION_CLAIM_PATH,
    )
    readback_claim = runner.strict_json(
        readback_raw,
        WAVE11_READBACK_CLAIM_PATH,
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
            "attemptId": WAVE11_ATTEMPT_ID,
            "checkerRawSha256": WAVE11_ACQUISITION_CHECKER_RAW_SHA256,
            "documentType": "aetherlink.wave11-source-acquisition-claim",
            "externalAuthenticationRequired": False,
            "permitContentSha256": WAVE11_CONTENT_SHA256[WAVE11_PERMIT_PATH],
            "requestCount": 18,
            "schemaVersion": "1.0",
            "status": "consumed_active",
            "userActionRequired": False,
        },
        "E_WAVE11_ACQUISITION_CLAIM",
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
            "sha256": WAVE11_READBACK_CLAIM_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == WAVE11_READBACK_CLAIM_CONTENT_SHA256
        and readback_claim.get("acquisitionAttemptId") == WAVE11_ATTEMPT_ID
        and readback_claim.get("readbackAttemptId")
        == WAVE11_READBACK_ATTEMPT_ID
        and readback_claim.get("authorityBinding")
        == WAVE11_READBACK_AUTHORITY_BINDING
        and readback_claim.get("documentType")
        == "aetherlink.wave11-acquisition-readback-one-use-claim"
        and readback_claim.get(
            "claimPersistsAfterSuccessFailureOrUncertainty"
        )
        is True
        and readback_claim.get("retryAllowed") is False
        and readback_claim.get("schemaVersion") == "1.0"
        and readback_claim.get("status") == "consumed_active"
        and readback_claim.get("externalAuthenticationRequired") is False
        and readback_claim.get("userActionRequired") is False,
        "E_WAVE11_READBACK_CLAIM",
    )


def validate_wave11_evidence(
    runner: types.ModuleType,
    raw: bytes,
    evidence_document: Mapping[str, Any],
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    check(type(evidence_document) is dict, "E_WAVE11_EVIDENCE")
    readback = documents[WAVE11_READBACK_PATH]
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
        and sha256_bytes(raw) == WAVE11_ACQUISITION_EVIDENCE_RAW_SHA256
        and evidence_document.get("documentType")
        == "aetherlink.wave11-source-acquisition-evidence"
        and evidence_document.get("schemaVersion") == "1.0"
        and evidence_document.get("attemptId") == WAVE11_ATTEMPT_ID
        and evidence_document.get("requestCount") == 18
        and evidence_document.get("aggregateResponseBytes") == 16_363_894
        and evidence_document.get("aggregateModResponseBytes") == 617
        and evidence_document.get("aggregateZipResponseBytes") == 16_363_277
        and evidence_document.get("aggregateZipEntryCount") == 3_329
        and evidence_document.get("aggregateZipUncompressedBytes")
        == 64_428_507
        and type(evidence_resources) is list
        and len(evidence_resources) == 18
        and type(verified_resources) is list
        and runner.canonical_json_bytes(evidence_resources)
        == runner.canonical_json_bytes(verified_resources),
        "E_WAVE11_EVIDENCE",
    )


def verify_wave11_content_bindings(
    v4: types.ModuleType,
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    v4.verify_modern_content_binding(
        runner,
        documents[WAVE11_DECISION_PATH],
        WAVE11_CONTENT_SHA256[WAVE11_DECISION_PATH],
        "decision_without_contentBinding",
    )
    v4.verify_modern_content_binding(
        runner,
        documents[WAVE11_PERMIT_PATH],
        WAVE11_CONTENT_SHA256[WAVE11_PERMIT_PATH],
        "permit_without_contentBinding",
    )
    for path in (
        WAVE11_READBACK_PERMIT_PATH,
        WAVE11_READBACK_PATH,
        WAVE11_READBACK_MANIFEST_PATH,
    ):
        v4.verify_content_binding(
            runner,
            documents[path],
            WAVE11_CONTENT_SHA256[path],
        )


def validate_v9_predecessor_candidate(
    runner: types.ModuleType,
    candidate: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    predecessor = decision.get("predecessorBindings", {}).get(
        "combinedFixedPointV9"
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
        type(source_bindings) is list
        and len(source_bindings) == 299
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
        "E_V9_PREDECESSOR",
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
        == V9_CANDIDATE_CONTENT_SHA256
        and predecessor.get("combinedInputSetSha256")
        == V9_INPUT_SET_SHA256
        and predecessor.get("sourceBindingsSha256")
        == V9_SOURCE_BINDINGS_SHA256
        and predecessor.get("graphSha256") == V9_GRAPH_SHA256
        and predecessor.get("frontierSha256") == V9_FRONTIER_SHA256
        and predecessor.get("frontierTupleCount") == 9
        and predecessor.get("fixedPointReached") is False
        and predecessor.get("checkerPath") == V9_CHECKER_PATH
        and predecessor.get("checkerRawSha256") == V9_CHECKER_RAW_SHA256
        and predecessor.get("checkerNormalizedSha256")
        == V9_CHECKER_NORMALIZED_SHA256
        and predecessor.get("testsPath") == V9_TESTS_PATH
        and predecessor.get("testsRawSha256") == V9_TESTS_RAW_SHA256
        and predecessor.get("totalFullSourceReconstructionCount") == 16
        and predecessor.get("totalGraphArchiveOpenCount") == 1_666
        and predecessor.get("trustedPinnedNormalPathFileWriteCount") == 0
        and predecessor.get("osSyscallSandboxProvided") is False
        and predecessor.get("providerFacadeVerificationScope")
        == "trusted_pinned_normal_reconstruction_path"
        and predecessor.get("v8TestsBindingScope")
        == "historical_metadata_only_not_live_held"
        and predecessor.get("v8TestsLiveHeld") is False
        and predecessor.get("wave9PinnedLegacyBuildCompatibilityCount") == 4
        and predecessor.get("wave9LegacyBuildCompatibilityPolicy")
        == candidate.get("wave9LegacyBuildCompatibilityPolicy")
        and candidate.get("checkerVerification", {}).get(
            "wave9PinnedLegacyBuildCompatibilityCount"
        ) == 4
        and candidate.get("operationCounters", {}).get(
            "wave9PinnedLegacyBuildCompatibilityCount"
        ) == 4
        and retained_boundary
        == {
            "completionAppliesToRetainedSnapshot": True,
            "currentPathIdentityGuaranteedThroughManifestPublication": False,
            "finalNamespaceReverifiedAfterCombinedV9Reconstruction": True,
            "historicalExact40FrozenSnapshotDescriptorSetBound": True,
            "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV9Barrier": True,
            "liveTerminalControlMetadataVerifiedAtCombinedV9Barrier": True,
            "retainedFdPreManifestBarrierCount": 3,
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                False,
        }
        and type(binding) is dict
        and binding
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "candidate_without_contentBinding",
            "sha256": V9_CANDIDATE_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == V9_CANDIDATE_CONTENT_SHA256
        and candidate.get("schemaVersion") == "9.0"
        and candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
            "wave5-wave6-wave7-wave8-wave9-wave10-fixed-point-candidate"
        )
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and candidate.get("result")
        == (
            "combined_graph_recomputed_twice_from_exact_"
            "wave1_through_wave10_source_bytes"
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
            "frontierTupleCount": 9,
            "frontierSha256": V9_FRONTIER_SHA256,
        }
        and type(inputs) is dict
        and inputs.get("heldSourceInputCount") == 299
        and inputs.get("combinedInputSetSha256") == V9_INPUT_SET_SHA256
        and sha256_bytes(runner.canonical_json_bytes(source_bindings))
        == V9_INPUT_SET_SHA256
        and sha256_bytes(wave11_digest_bytes(source_bindings))
        == V9_SOURCE_BINDINGS_SHA256
        and len({row["path"] for row in source_bindings}) == 299
        and sum(row["kind"] == "root_zip" for row in source_bindings) == 1
        and sum(row["kind"] == "mod" for row in source_bindings) == 149
        and sum(row["kind"] == "zip" for row in source_bindings) == 149
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
        and len(source_pairs) == 149
        and all(kinds == {"mod", "zip"} for kinds in source_pairs.values())
        and sorted(order for _, _, order in source_pairs)
        == list(range(1, 150))
        and type(graph) is dict
        and graph.get("fixedPointReached") is False
        and graph.get("newTupleCount") == 9
        and graph.get("graphSha256") == V9_GRAPH_SHA256
        and type(frontier) is list
        and len(frontier) == 9
        and sha256_bytes(runner.canonical_json_bytes(frontier))
        == V9_FRONTIER_SHA256
        and candidate.get("authority") == V9_AUTHORITY,
        "E_V9_PREDECESSOR",
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
        "wave10CompletionAppliesToRetainedSnapshot": True,
        "wave10CurrentPathIdentityGuaranteedThroughManifestPublication": False,
        "wave10SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
            False,
        "v9TestsBindingScope": "historical_metadata_only_not_live_held",
        "v9TestsLiveHeld": False,
    }


def wave11_request_resources(
    v4: types.ModuleType,
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    decision = documents[WAVE11_DECISION_PATH]
    permit = documents[WAVE11_PERMIT_PATH]
    receipt = documents[WAVE11_RECEIPT_PATH]
    manifest = documents[WAVE11_MANIFEST_PATH]
    readback_permit = documents[WAVE11_READBACK_PERMIT_PATH]
    readback = documents[WAVE11_READBACK_PATH]
    readback_manifest = documents[WAVE11_READBACK_MANIFEST_PATH]
    verify_wave11_content_bindings(v4, runner, documents)

    resolution = decision.get("identityResolution")
    held_set = decision.get("heldSourceInputSet")
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
                "heldSourceInputSet", "identityResolution", "nextAction",
                "nonClaims", "operationCounters", "predecessorBindings",
                "readerDocumentBinding", "recordModeExposed", "result",
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
            held_set,
            (
                "allInputsHeldThroughFinalBarrier",
                "allInputsReadTwiceBeforeUse", "archiveCount",
                "embeddedRootGoModCount", "externalModCount",
                "goSumEntryCount",
                "sourceBindingCount", "sourceBindingsSha256",
            ),
        )
        and exact_keys(
            preparation,
            (
                "acceptedDirectoryPath",
                "acquisitionAuthorizedByThisDecision",
                "acquisitionReady", "atomicNoReplacePromotionRequired",
                "claimPath", "independentPostConsumptionReadbackRequired",
                "modulePathEncoding", "oneUseNoOverwriteRequired",
                "namespaceCheckIsPointInTimeOnly",
                "namespaceCleanAtDecisionCheck",
                "namespaceReservationClaimed",
                "proxyHost", "requestCount", "requestOrder", "requestSet",
                "requestSetCanonicalSha256",
                "separateOneUseExecutionPermitRequired",
                "stagingDirectoryPrefix",
            ),
        ),
        "E_WAVE11_DECISION",
    )
    check(
        decision.get("contentBinding")
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "decision_without_contentBinding",
            "sha256": WAVE11_CONTENT_SHA256[WAVE11_DECISION_PATH],
        }
        and decision.get("status")
        == (
            "wave11_exact_9_frontier_identity_classified_9_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and decision.get("authority") == WAVE11_DECISION_AUTHORITY
        and decision.get("toolBindings") == WAVE11_DECISION_TOOL_BINDINGS
        and type(resolution) is dict
        and resolution.get("tupleCount") == 9
        and resolution.get("completeIdentityPairCount") == 9
        and resolution.get("blockedTupleCount") == 0
        and resolution.get("graphSelectedTupleCount") == 0
        and resolution.get("versionSpecificNonSelectedTupleCount") == 9
        and resolution.get("compactIdentitySha256")
        == WAVE11_COMPACT_IDENTITY_SHA256
        and resolution.get("fullWitnessSha256")
        == WAVE11_FULL_WITNESS_SHA256
        and type(held_set) is dict
        and held_set.get("sourceBindingCount") == 299
        and held_set.get("sourceBindingsSha256")
        == WAVE11_HELD_SOURCE_BINDINGS_SHA256
        and type(preparation) is dict
        and preparation.get("acquisitionReady") is True
        and preparation.get("acquisitionAuthorizedByThisDecision") is False
        and preparation.get("namespaceCheckIsPointInTimeOnly") is True
        and preparation.get("namespaceCleanAtDecisionCheck") is True
        and preparation.get("namespaceReservationClaimed") is False
        and preparation.get("requestCount") == 18
        and preparation.get("requestOrder")
        == "tuple_order_ascending_mod_then_zip"
        and preparation.get("acceptedDirectoryPath")
        == WAVE11_ACCEPTED_DIRECTORY
        and preparation.get("requestSetCanonicalSha256")
        == WAVE11_REQUEST_SET_SHA256
        and type(identity_tuples) is list
        and len(identity_tuples) == 9
        and type(source_requests) is list
        and len(source_requests) == 18
        and sha256_bytes(wave11_digest_bytes(source_requests))
        == WAVE11_REQUEST_SET_SHA256,
        "E_WAVE11_DECISION",
    )

    contract = permit.get("requestContract")
    resources = contract.get("resources") if type(contract) is dict else None
    permit_decision_binding = permit.get("decisionBinding")
    permit_identity_binding = permit.get("identityBinding")
    permit_predecessor = permit.get("predecessorBindings", {}).get(
        "combinedFixedPointV9"
    )
    check(
        exact_keys(
            permit,
            (
                "absoluteResourceLimits", "authority", "contentBinding",
                "decisionBinding", "documentType", "filesystemAuthority",
                "identityBinding", "invocationContract", "nextAction",
                "nonClaims",
                "oneUseContract", "permitId", "predecessorBindings",
                "primitiveBindings",
                "readerDocumentBinding", "recordedDate", "requestContract",
                "result", "runnerNormalizedSha256", "schemaVersion",
                "status", "terminalContract", "toolBindings",
                "verificationContract", "zipLimits",
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
                "heldSourceBindingsSha256",
            ),
        )
        and exact_keys(
            contract,
            (
                "acceptedStatusCode", "alternateHostAllowed",
                "ambientProxyAllowed", "authenticationAllowed",
                "authorizationHeaderAllowed", "clientCertificateAllowed",
                "cookieAllowed", "directHttpsOnly", "host",
                "identityContentEncodingRequired", "method", "order",
                "port", "proxyAuthorizationHeaderAllowed",
                "queryOrFragmentAllowed", "rangeHeaderAllowed",
                "redirectAllowed", "requestBodyAllowed", "requestCount",
                "resources", "resourcesCanonicalSha256",
                "retryResumeOrBackfillAllowed",
                "sourceRequestSetCanonicalSha256",
                "tlsCertificateAndHostnameValidationRequired",
                "tupleCount",
            ),
        ),
        "E_WAVE11_PERMIT",
    )
    check(
        permit.get("contentBinding")
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "permit_without_contentBinding",
            "sha256": WAVE11_CONTENT_SHA256[WAVE11_PERMIT_PATH],
        }
        and permit.get("status") == "authorized_not_consumed"
        and permit.get("authority") == WAVE11_ACQUISITION_AUTHORITY
        and permit.get("toolBindings") == WAVE11_ACQUISITION_TOOL_BINDINGS
        and permit.get("decisionBinding", {}).get("rawSha256")
        == WAVE11_CONTROL_SHA256[WAVE11_DECISION_PATH]
        and permit.get("decisionBinding", {}).get("contentSha256")
        == WAVE11_CONTENT_SHA256[WAVE11_DECISION_PATH]
        and permit.get("identityBinding", {}).get("compactIdentitySha256")
        == WAVE11_COMPACT_IDENTITY_SHA256
        and permit.get("identityBinding", {}).get("fullWitnessSha256")
        == WAVE11_FULL_WITNESS_SHA256
        and permit.get("identityBinding", {}).get(
            "heldSourceBindingsSha256"
        )
        == WAVE11_HELD_SOURCE_BINDINGS_SHA256
        and permit_predecessor
        == {
            "checkerNormalizedSha256": V9_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V9_CHECKER_PATH,
            "checkerRawSha256": V9_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V9_INPUT_SET_SHA256,
            "contentSha256": V9_CANDIDATE_CONTENT_SHA256,
            "frontierSha256": V9_FRONTIER_SHA256,
            "graphSha256": V9_GRAPH_SHA256,
            "sourceBindingsSha256": V9_SOURCE_BINDINGS_SHA256,
            "testsPath": V9_TESTS_PATH,
            "testsRawSha256": V9_TESTS_RAW_SHA256,
            "v8TestsBindingScope":
                "historical_metadata_only_not_live_held",
            "v8TestsLiveHeld": False,
        }
        and type(contract) is dict
        and contract.get("requestCount") == 18
        and contract.get("tupleCount") == 9
        and contract.get("order") == "tuple_order_ascending_mod_then_zip"
        and contract.get("sourceRequestSetCanonicalSha256")
        == WAVE11_REQUEST_SET_SHA256
        and contract.get("resourcesCanonicalSha256")
        == WAVE11_PERMIT_RESOURCES_SHA256
        and type(resources) is list
        and len(resources) == 18
        and sha256_bytes(runner.canonical_json_bytes(resources))
        == WAVE11_PERMIT_RESOURCES_SHA256,
        "E_WAVE11_PERMIT",
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
        "E_WAVE11_RECEIPT",
    )
    check(
        receipt.get("status")
        == "consumed_success_pending_independent_readback"
        and receipt.get("attemptId") == WAVE11_ATTEMPT_ID
        and receipt.get("acceptedPath") == WAVE11_ACCEPTED_DIRECTORY
        and receipt.get("acceptedResourceCount") == 18
        and receipt.get("modCount") == 9
        and receipt.get("zipCount") == 9
        and receipt.get("aggregateResponseBytes") == 16_363_894
        and receipt.get("aggregateModResponseBytes") == 617
        and receipt.get("aggregateZipResponseBytes") == 16_363_277
        and receipt.get("aggregateZipEntryCount") == 3_329
        and receipt.get("aggregateZipUncompressedBytes") == 64_428_507
        and receipt.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE11_RESOURCE_SET_SHA256
        and receipt.get("claimRawSha256")
        == WAVE11_ACQUISITION_CLAIM_RAW_SHA256
        and receipt.get("acceptedEvidenceRawSha256")
        == WAVE11_ACQUISITION_EVIDENCE_RAW_SHA256
        and receipt.get("checkerRawSha256")
        == WAVE11_ACQUISITION_CHECKER_RAW_SHA256
        and receipt.get("runnerRawSha256")
        == WAVE11_ACQUISITION_RUNNER_RAW_SHA256
        and receipt.get("decisionContentSha256")
        == WAVE11_CONTENT_SHA256[WAVE11_DECISION_PATH]
        and receipt.get("permitContentSha256")
        == WAVE11_CONTENT_SHA256[WAVE11_PERMIT_PATH]
        and receipt.get("sourceAcquired") is True
        and receipt.get("sourceExtracted") is False
        and receipt.get("sourceLoadedOrExecuted") is False
        and receipt.get("compiled") is False
        and receipt.get("externalAuthenticationRequired") is False
        and receipt.get("userActionRequired") is False,
        "E_WAVE11_RECEIPT",
    )
    check(
        manifest
        == {
            "attemptId": WAVE11_ATTEMPT_ID,
            "documentType": "aetherlink.wave11-source-acquisition-manifest",
            "manifestWrittenLast": True,
            "receiptPath": WAVE11_RECEIPT_PATH,
            "receiptRawSha256": WAVE11_CONTROL_SHA256[WAVE11_RECEIPT_PATH],
            "schemaVersion": "1.0",
            "status": "consumed_success_pending_independent_readback",
        },
        "E_WAVE11_MANIFEST",
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
        snapshot.get("predecessorBindings", {}).get("combinedFixedPointV9")
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
                "combinedFixedPointV9PredecessorBindingRecomputed",
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
                "exact18ResourceOrderAndAggregateRecomputed",
                "exact36FrozenFileSnapshotRequired",
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
                "v8TestsLiveHeld", "v9TestsLiveHeld",
                "zipStructurePathCrcAndModParityRecomputed",
            ),
        ),
        "E_WAVE11_READBACK_PERMIT",
    )
    check(
        readback_permit.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE11_CONTENT_SHA256[WAVE11_READBACK_PERMIT_PATH],
        }
        and readback_permit.get("status") == "authorized_not_consumed"
        and readback_permit.get("authority") == WAVE11_READBACK_AUTHORITY
        and readback_permit.get("toolBindings")
        == WAVE11_READBACK_TOOL_BINDINGS
        and readback_permit.get("recorderNormalizedSha256")
        == WAVE11_READBACK_RECORDER_NORMALIZED_SHA256
        and type(verification_contract) is dict
        and verification_contract.get("completeVerificationPassCount") == 2
        and verification_contract.get("allFrozenFilesOpenedNoFollowAndHeld")
        is True
        and verification_contract.get("exact36FrozenFileSnapshotRequired")
        is True
        and verification_contract.get(
            "combinedFixedPointV9PredecessorBindingRecomputed"
        ) is True
        and verification_contract.get(
            "exact18ResourceOrderAndAggregateRecomputed"
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
        and verification_contract.get("requiredFallibleBarrierAfterManifest")
        is False
        and verification_contract.get("v8TestsLiveHeld") is False
        and verification_contract.get("v9TestsLiveHeld") is True
        and verification_contract.get(
            "requestResourcesCanonicalSha256Recomputed"
        ) is True
        and verification_contract.get("retainedFdPreManifestBarrierCount")
        == 3
        and verification_contract.get("retainedFdPreManifestBarriers")
        == WAVE11_RETAINED_BARRIERS
        and verification_contract.get("completionAppliesToRetainedSnapshot")
        is True
        and verification_contract.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and verification_contract.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and type(snapshot) is dict
        and snapshot.get("attemptId") == WAVE11_ATTEMPT_ID
        and identity_bindings
        == {
            "compactIdentitySha256": WAVE11_COMPACT_IDENTITY_SHA256,
            "fullWitnessSha256": WAVE11_FULL_WITNESS_SHA256,
            "heldSourceBindingsSha256":
                WAVE11_HELD_SOURCE_BINDINGS_SHA256,
            "resourcesCanonicalSha256":
                WAVE11_PERMIT_RESOURCES_SHA256,
            "sourceRequestSetCanonicalSha256":
                WAVE11_REQUEST_SET_SHA256,
        }
        and snapshot_predecessor
        == {
            "checkerNormalizedSha256": V9_CHECKER_NORMALIZED_SHA256,
            "checkerPath": V9_CHECKER_PATH,
            "checkerRawSha256": V9_CHECKER_RAW_SHA256,
            "combinedInputSetSha256": V9_INPUT_SET_SHA256,
            "contentSha256": V9_CANDIDATE_CONTENT_SHA256,
            "frontierSha256": V9_FRONTIER_SHA256,
            "graphSha256": V9_GRAPH_SHA256,
            "sourceBindingsSha256": V9_SOURCE_BINDINGS_SHA256,
            "testsPath": V9_TESTS_PATH,
            "testsRawSha256": V9_TESTS_RAW_SHA256,
            "v8TestsBindingScope":
                "historical_metadata_only_not_live_held",
            "v8TestsLiveHeld": False,
        }
        and snapshot.get("acquisitionDecisionContentSha256")
        == WAVE11_CONTENT_SHA256[WAVE11_DECISION_PATH]
        == decision.get("contentBinding", {}).get("sha256")
        == permit.get("decisionBinding", {}).get("contentSha256")
        == receipt.get("decisionContentSha256")
        and snapshot.get("acquisitionPermitContentSha256")
        == WAVE11_CONTENT_SHA256[WAVE11_PERMIT_PATH]
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
                "wave-11-v1"
            ),
        }
        and absence_contract
        == {
            "failureAbsent": True,
            "failurePath": (
                f"{BASE}/bounded-dependency-source-acquisition-wave11-"
                "failure-v1.json"
            ),
            "portableNameComparison": "NFC_casefold",
            "stagingAbsent": True,
            "stagingParent": (
                "build/offline-source/pion-ice-v4.3.0/dependencies"
            ),
            "stagingPrefix": ".wave-11-v1-staging-",
        }
        and snapshot.get("frozenFileCount") == 36
        and snapshot.get("frozenFilesCanonicalSha256")
        == WAVE11_FROZEN_FILE_SET_SHA256
        and snapshot.get("acceptedResourceCount") == 18
        and snapshot.get("selectedTupleCount") == 0
        and snapshot.get("selectedRequestOrdinals") == []
        and snapshot.get("modCount") == 9
        and snapshot.get("zipCount") == 9
        and snapshot.get("aggregateAcceptedBytes") == 16_363_894
        and snapshot.get("aggregateModBytes") == 617
        and snapshot.get("aggregateZipBytes") == 16_363_277
        and snapshot.get("aggregateZipEntryCount") == 3_329
        and snapshot.get("aggregateZipUncompressedBytes") == 64_428_507
        and snapshot.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE11_RESOURCE_SET_SHA256
        and type(acquisition_authority) is list
        and len(acquisition_authority) == 14
        and len(acquisition_authority_by_path) == 14
        and acquisition_authority_by_path.get(
            (
                "script/check_p2p_nat_g2_pion_rung3_dependency_wave11_"
                "acquisition_v1.py"
            ),
            {},
        ).get("rawSha256")
        == WAVE11_ACQUISITION_CHECKER_RAW_SHA256
        and acquisition_authority_by_path.get(
            (
                "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave11_"
                "v1_once.py"
            ),
            {},
        ).get("rawSha256")
        == WAVE11_ACQUISITION_RUNNER_RAW_SHA256
        and acquisition_claim
        == {
            "bytes": 417,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-11-v1.claim"
            ),
            "rawSha256": WAVE11_ACQUISITION_CLAIM_RAW_SHA256,
        }
        and evidence
        == {
            "bytes": 7_405,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                "wave-11-v1/evidence.json"
            ),
            "rawSha256": WAVE11_ACQUISITION_EVIDENCE_RAW_SHA256,
        }
        and acquisition_receipt
        == {
            "bytes": 1_669,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE11_RECEIPT_PATH,
            "rawSha256": WAVE11_CONTROL_SHA256[WAVE11_RECEIPT_PATH],
        }
        and acquisition_manifest
        == {
            "bytes": 465,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE11_MANIFEST_PATH,
            "rawSha256": WAVE11_CONTROL_SHA256[WAVE11_MANIFEST_PATH],
        }
        and manifest.get("receiptPath") == acquisition_receipt["path"]
        and manifest.get("receiptRawSha256")
        == acquisition_receipt["rawSha256"]
        and type(accepted) is dict
        and accepted.get("path") == WAVE11_ACCEPTED_DIRECTORY
        and accepted.get("mode") == "0700"
        and accepted.get("ownerUid") == os.geteuid()
        and accepted.get("linkCount") == 20
        and accepted.get("exactFileCount") == 18
        and type(accepted_files) is list
        and len(accepted_files) == 18
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
        == WAVE11_FROZEN_FILE_SET_SHA256,
        "E_WAVE11_READBACK_PERMIT",
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
            "combinedFixedPointV9ContentSha256",
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
        "E_WAVE11_READBACK",
    )
    check(
        readback.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE11_CONTENT_SHA256[WAVE11_READBACK_PATH],
        }
        and readback.get("status")
        == "wave11_acquisition_retained_snapshot_independently_read_back"
        and readback.get("acquisitionAttemptId") == WAVE11_ATTEMPT_ID
        and readback.get("readbackAttemptId") == WAVE11_READBACK_ATTEMPT_ID
        and readback.get("authorityBinding")
        == WAVE11_READBACK_AUTHORITY_BINDING
        and readback.get("verificationPassCount") == 2
        and readback.get("offline") is True
        and readback.get("networkRequestAttemptCount") == 0
        and readback.get("sourceAcquisitionCount") == 0
        and readback.get("sourceExtracted") is False
        and readback.get("sourceLoadedOrExecuted") is False
        and readback.get("compiled") is False
        and readback.get("externalAuthenticationRequired") is False
        and readback.get("userActionRequired") is False
        and readback.get("readbackClaim")
        == {
            "bytes": 1_255,
            "contentSha256": WAVE11_READBACK_CLAIM_CONTENT_SHA256,
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": (
                "build/offline-source/pion-ice-v4.3.0/dependencies/"
                ".wave-11-v1-readback.claim"
            ),
            "rawSha256": WAVE11_READBACK_CLAIM_RAW_SHA256,
        }
        and readback.get("allRequiredPreManifestBarriersRequired") is True
        and readback.get("allRequiredPreManifestBarriersCompleteAtReceipt")
        is False
        and readback.get("requiredRetainedFdPreManifestBarrierCount") == 3
        and readback.get(
            "completedRetainedFdPreManifestBarrierCountAtReceipt"
        ) == 1
        and readback.get("remainingRetainedFdPreManifestBarrierCount") == 2
        and readback.get("retainedFdPreManifestBarriers")
        == WAVE11_RETAINED_BARRIERS
        and readback.get("completionAppliesToRetainedSnapshot") is True
        and readback.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and readback.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and type(verified) is dict
        and verified.get("status")
        == "wave11_acquisition_retained_snapshot_independently_verified"
        and verified.get("acquisitionAttemptId")
        == snapshot.get("attemptId")
        == receipt.get("attemptId")
        == manifest.get("attemptId")
        and verified.get("authorityFileCount")
        == len(acquisition_authority)
        and verified.get("acceptedResourceCount") == 18
        == snapshot.get("acceptedResourceCount")
        == receipt.get("acceptedResourceCount")
        and verified.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE11_RESOURCE_SET_SHA256
        == snapshot.get("acceptedResourceHashSetCanonicalSha256")
        == receipt.get("acceptedResourceHashSetCanonicalSha256")
        and verified.get("selectedTupleCount") == 0
        == snapshot.get("selectedTupleCount")
        and verified.get("selectedRequestOrdinals") == []
        == snapshot.get("selectedRequestOrdinals")
        and verified.get("modCount")
        == snapshot.get("modCount")
        == receipt.get("modCount")
        == 9
        and verified.get("zipCount")
        == snapshot.get("zipCount")
        == receipt.get("zipCount")
        == 9
        and verified.get("aggregateAcceptedBytes")
        == snapshot.get("aggregateAcceptedBytes")
        == receipt.get("aggregateResponseBytes")
        == 16_363_894
        and verified.get("aggregateModBytes")
        == snapshot.get("aggregateModBytes")
        == receipt.get("aggregateModResponseBytes")
        == 617
        and verified.get("aggregateZipBytes")
        == snapshot.get("aggregateZipBytes")
        == receipt.get("aggregateZipResponseBytes")
        == 16_363_277
        and verified.get("aggregateZipEntryCount")
        == snapshot.get("aggregateZipEntryCount")
        == receipt.get("aggregateZipEntryCount")
        == 3_329
        and verified.get("aggregateZipUncompressedBytes")
        == snapshot.get("aggregateZipUncompressedBytes")
        == receipt.get("aggregateZipUncompressedBytes")
        == 64_428_507
        and verified.get("combinedFixedPointV9ContentSha256")
        == V9_CANDIDATE_CONTENT_SHA256
        and verified.get("resourcesCanonicalSha256")
        == identity_bindings["resourcesCanonicalSha256"]
        == contract.get("resourcesCanonicalSha256")
        == WAVE11_PERMIT_RESOURCES_SHA256
        and verified.get("decisionContentSha256")
        == snapshot.get("acquisitionDecisionContentSha256")
        == receipt.get("decisionContentSha256")
        == WAVE11_CONTENT_SHA256[WAVE11_DECISION_PATH]
        and verified.get("permitContentSha256")
        == snapshot.get("acquisitionPermitContentSha256")
        == receipt.get("permitContentSha256")
        == WAVE11_CONTENT_SHA256[WAVE11_PERMIT_PATH]
        and verified.get("sourceRequestSetCanonicalSha256")
        == identity_bindings["sourceRequestSetCanonicalSha256"]
        == contract.get("sourceRequestSetCanonicalSha256")
        == WAVE11_REQUEST_SET_SHA256
        and verified.get("compactIdentitySha256")
        == identity_bindings["compactIdentitySha256"]
        == resolution.get("compactIdentitySha256")
        == WAVE11_COMPACT_IDENTITY_SHA256
        and verified.get("fullWitnessSha256")
        == identity_bindings["fullWitnessSha256"]
        == resolution.get("fullWitnessSha256")
        == WAVE11_FULL_WITNESS_SHA256
        and verified.get("heldSourceBindingsSha256")
        == identity_bindings["heldSourceBindingsSha256"]
        == held_set.get("sourceBindingsSha256")
        == WAVE11_HELD_SOURCE_BINDINGS_SHA256
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
        and len(verified_resources) == 18,
        "E_WAVE11_READBACK",
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
        "E_WAVE11_READBACK_MANIFEST",
    )
    check(
        readback_manifest.get("contentBinding")
        == {
            "algorithm":
                "sha256(canonical-json-without-contentBinding)",
            "sha256": WAVE11_CONTENT_SHA256[
                WAVE11_READBACK_MANIFEST_PATH
            ],
        }
        and readback_manifest.get("status")
        == "wave11_acquisition_retained_snapshot_readback_publication_complete"
        and readback_manifest.get("acquisitionAttemptId") == WAVE11_ATTEMPT_ID
        and readback_manifest.get("readbackAttemptId")
        == WAVE11_READBACK_ATTEMPT_ID
        and readback_manifest.get("authorityBinding")
        == WAVE11_READBACK_AUTHORITY_BINDING
        and readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("allRequiredPreManifestBarriersCompleted")
        is True
        and readback_manifest.get(
            "completedPreManifestCurrentPathIdentityBarrierCount"
        ) == 3
        and readback_manifest.get("lastCurrentPathIdentityBarrierTiming")
        == "immediately_before_manifest_publication"
        and readback_manifest.get("retainedFdPreManifestBarriers")
        == WAVE11_RETAINED_BARRIERS
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
            "bytes": 11_284,
            "contentSha256": WAVE11_CONTENT_SHA256[WAVE11_READBACK_PATH],
            "linkCount": 1,
            "mode": "0600",
            "ownerUid": os.geteuid(),
            "path": WAVE11_READBACK_PATH,
            "rawSha256": WAVE11_CONTROL_SHA256[WAVE11_READBACK_PATH],
        }
        and readback_manifest.get("offline") is True
        and readback_manifest.get("networkRequestAttemptCount") == 0
        and readback_manifest.get("sourceAcquisitionCount") == 0
        and readback_manifest.get("externalAuthenticationRequired") is False
        and readback_manifest.get("userActionRequired") is False,
        "E_WAVE11_READBACK_MANIFEST",
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
        len(accepted_by_name) == 18
        and len(verified_by_name) == 18
        and len(identity_by_order) == 9,
        "E_WAVE11_RESOURCE",
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
            and value.get("requestOrdinal") == index
            and value.get("tupleOrder") == tuple_order
            and value.get("kind") == expected_kind
            and value.get("selectedByGraphAlgorithm")
            is False
            and value.get("tupleDigestSha256") == digest
            and value.get("tupleId")
            == f"wave11-{tuple_order:03}-{digest[:12]}"
            and value.get("acceptedFileName")
            == f"{tuple_order:03}-{digest[:20]}.{expected_kind}"
            and type(source_value) is dict
            and source_value.get("requestOrdinal") == index
            and source_value.get("tupleOrder") == tuple_order
            and source_value.get("resourceKind") == expected_kind
            and source_value.get("module") == value.get("module")
            and source_value.get("version") == value.get("version")
            and source_value.get("url") == value.get("url")
            and source_value.get("expectedH1") == value.get("expectedH1")
            and source_value.get("selectedByGraphAlgorithm")
            is False
            and type(identity_tuple) is dict
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
            "E_WAVE11_RESOURCE",
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
            == f"{WAVE11_ACCEPTED_DIRECTORY}/{name}"
            and accepted_row.get("mode") == "0600"
            and accepted_row.get("ownerUid") == os.geteuid()
            and accepted_row.get("linkCount") == 1
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
            and verified_row.get("requestOrdinal") == index
            and verified_row.get("tupleId") == value.get("tupleId")
            and verified_row.get("kind") == expected_kind
            and verified_row.get("url") == value.get("url")
            and verified_row.get("verifiedH1") == value.get("expectedH1")
            and verified_row.get("byteCount") == accepted_row["bytes"]
            and verified_row.get("rawSha256")
            == accepted_row.get("rawSha256"),
            "E_WAVE11_RESOURCE",
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
                and verified_row.get("rootGoModPresent")
                is (tuple_order not in {5, 9})
                and type(verified_row.get("uncompressedBytes")) is int
                and verified_row["uncompressedBytes"] > 0,
                "E_WAVE11_RESOURCE",
            )
            totals["entries"] += verified_row.get("entryCount", -1)
            totals["expanded"] += verified_row.get("uncompressedBytes", -1)
        row = {
            "wave": "wave11",
            "path": accepted_row["path"],
            "rawSha256": accepted_row["rawSha256"],
            "maximumBytes": accepted_row["bytes"],
            "ownerOnly": True,
            "kind": expected_kind,
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 149 + tuple_order,
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
        len(tuple_rows) == 9
        and all(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len({(row["module"], row["version"]) for row in rows}) == 1
            for rows in tuple_rows.values()
        )
        and totals
        == {
            "all": 16_363_894,
            "mod": 617,
            "zip": 16_363_277,
            "entries": 3_329,
            "expanded": 64_428_507,
        }
        and sha256_bytes(
            runner.canonical_json_bytes(accepted_hash_projection)
        )
        == WAVE11_RESOURCE_SET_SHA256,
        "E_WAVE11_AGGREGATE",
    )
    return result


def combined_source_bindings(
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
) -> list[dict[str, Any]]:
    bindings = v9.combined_source_bindings(
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
    )
    bindings.extend(wave11_request_resources(v4, runner, wave11_documents))
    check(
        len(bindings) == 317
        and sum(row["kind"] == "root_zip" for row in bindings) == 1
        and sum(row["kind"] == "mod" for row in bindings) == 158
        and sum(row["kind"] == "zip" for row in bindings) == 158
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
        and sum(row["wave"] == "wave11" for row in bindings) == 18,
        "E_COMBINED_INPUT",
    )
    check(
        len({row["path"] for row in bindings}) == 317
        and len(
            {
                (row["module"], row["version"])
                for row in bindings
                if row["kind"] != "root_zip"
            }
        )
        == 158,
        "E_COMBINED_INPUT",
    )
    pair_kinds: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in bindings:
        if row["kind"] != "root_zip":
            pair_kinds[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        len(pair_kinds) == 158
        and all(kinds == {"mod", "zip"} for kinds in pair_kinds.values())
        and sorted(order for _, _, order in pair_kinds) == list(range(1, 159)),
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
    v9: types.ModuleType,
    predecessor_candidate: Mapping[str, Any],
    direct_tool_bindings: list[dict[str, Any]],
    direct_tool_inputs: tuple[Any, ...],
) -> tuple[set[str], set[str]]:
    """Bind counters to actual held tools and the pinned predecessor chain."""

    declared_v9_paths = v9.TRANSITIVE_CHECKER_PATHS
    expected_declared_paths = {
        f"script/check_p2p_nat_g2_pion_combined_fixed_point_v{version}.py"
        for version in range(1, 10)
    }
    v1_checker_path = (
        "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
    )
    expected_direct_paths = {
        SELF_PATH,
        V9_CHECKER_PATH,
        V8_CHECKER_PATH,
        V7_CHECKER_PATH,
        V6_CHECKER_PATH,
        V5_CHECKER_PATH,
        V4_CHECKER_PATH,
        v1_checker_path,
        v9.V1_PROVIDER_PATH,
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
        and type(declared_v9_paths) is set
        and declared_v9_paths
        == TRANSITIVE_CHECKER_PATHS - {V9_CHECKER_PATH}
        and direct_binding_paths == expected_direct_paths
        and len(held_paths) == len(expected_direct_paths)
        and len(set(held_paths)) == len(held_paths)
        and set(held_paths) == expected_direct_paths
        and predecessor_binding_paths
        == expected_direct_paths - {SELF_PATH}
        and type(predecessor_counters) is dict
        and predecessor_counters.get("heldToolInputCount")
        == len(predecessor_binding_paths)
        and predecessor_counters.get("transitiveDistinctToolPathCount")
        == len(
            declared_v9_paths
            | {V9_CHECKER_PATH, v9.V1_PROVIDER_PATH}
        )
        and V9_TESTS_PATH not in direct_binding_paths
        and V9_TESTS_PATH not in predecessor_binding_paths,
        "E_TOOL_BINDINGS",
    )
    transitive_paths = direct_binding_paths | declared_v9_paths
    check(
        transitive_paths
        == TRANSITIVE_CHECKER_PATHS | {SELF_PATH, V1_PROVIDER_PATH}
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
    wave11_documents: Mapping[str, Mapping[str, Any]],
) -> ReconstructionProtocolState:
    """Run namespace-pre, barriers, both reconstructions, and equality."""

    validate_wave11_completed_namespace(control_held, wave11_documents)
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
    wave11_documents: Mapping[str, Mapping[str, Any]],
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
    validate_wave11_completed_namespace(control_held, wave11_documents)
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
        v9 = load_v9_checker(v9_held)
        predecessor_candidate = v9.generate_candidate(root)
        v9 = harden_checker_module(v9)
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
                        "role": "current_v10_combined_checker",
                        "path": SELF_PATH,
                        "normalizedSha256": SELF_NORMALIZED_SHA256,
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
                        v9,
                        predecessor_candidate,
                        direct_tool_bindings,
                        direct_tool_inputs,
                    )
                )
                expected_direct_hardened_paths = {
                    str(root / path)
                    for path in (
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
                    v9.PinnedCodeFile is PinnedCodeFile
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
                    ] == 8
                    and predecessor_candidate["checkerVerification"][
                        "providerFacadeLoadCount"
                    ] == 8
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
                    + wave11_control_bindings()
                )
                auxiliary_evidence = wave11_auxiliary_evidence_bindings()
                check(
                    len(controls) == 73
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
                    wave11_documents = parse_wave11_documents(
                        runner,
                        control_held,
                    )
                    predecessor_verification = (
                        validate_v9_predecessor_candidate(
                            runner,
                            predecessor_candidate,
                            wave11_documents[WAVE11_DECISION_PATH],
                        )
                    )
                    bindings = combined_source_bindings(
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
                    )
                    wave11_evidence_raw = control_held.raw[WAVE11_EVIDENCE_PATH]
                    wave11_evidence_document = runner.strict_json(
                        wave11_evidence_raw,
                        WAVE11_EVIDENCE_PATH,
                    )
                    validate_wave11_evidence(
                        runner,
                        wave11_evidence_raw,
                        wave11_evidence_document,
                        wave11_documents,
                    )
                    validate_wave11_consumed_claims(
                        runner,
                        control_held.raw[WAVE11_ACQUISITION_CLAIM_PATH],
                        control_held.raw[WAVE11_READBACK_CLAIM_PATH],
                    )
                    with runner.HeldInputSet(root, bindings) as source_held:
                        held_inputs = (
                            self_held,
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
                                V10_MAXIMUM_AGGREGATE_UNCOMPRESSED_BYTES,
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
                                wave11_documents,
                            )
                        )
                        first_graph = reconstruction_state.first_graph
                        first_coverage = reconstruction_state.first_coverage
                        validate_wave9_legacy_build_compatibility_count(
                            WAVE9_LEGACY_BUILD_COMPATIBILITY_COUNT
                        )
                        projection = v1.source_projection(bindings)
                        check(
                            len(projection) == 317
                            and sum(
                                row["maximumBytes"] for row in bindings
                            ) == 287_352_740
                            and sha256_bytes(
                                runner.canonical_json_bytes(projection)
                            ) == V10_INPUT_SET_SHA256
                            and sha256_bytes(wave11_digest_bytes(projection))
                            == V10_SOURCE_BINDINGS_SHA256,
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
                                "wave9-wave10-wave11-"
                                "fixed-point-candidate"
                            ),
                            "schemaVersion": "10.0",
                            "checkerId": CHECKER_ID,
                            "status": route["status"],
                            "result": (
                                "combined_graph_recomputed_twice_from_exact_"
                                "wave1_through_wave11_source_bytes"
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
                                "resourceCount": 316,
                                "modCount": 158,
                                "zipCount": 158,
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
                                "uniqueModuleVersionTupleCount": 158,
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
                                    WAVE11_RESOURCE_SET_SHA256,
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
                                "pinnedV9PredecessorExecuted": True,
                                "v9TestsBindingScope":
                                    "historical_metadata_only_not_live_held",
                                "v9TestsLiveHeld": False,
                                "canonicalGraphEqualityVerified": True,
                                "barrierBeforeReconstructionCompleted": True,
                                "barrierBetweenReconstructionsCompleted": True,
                                "barrierAfterReconstructionCompleted": True,
                                "workspaceRootIdentityBoundAcrossAllInputs":
                                    True,
                                "calculatedFixedPointCandidate": fixed_point,
                                "wave11HistoricalExact36FrozenSnapshotDescriptorSetBound":
                                    True,
                                "wave11LiveTerminalControlMetadataVerified":
                                    True,
                                "wave11LiveFinalAndAcceptedInventoriesVerified":
                                    True,
                                "wave11FinalNamespaceReverifiedAfterReconstruction":
                                    True,
                                "wave11RetainedFdPreManifestBarrierCount": 3,
                                "wave11CompletionAppliesToRetainedSnapshot":
                                    True,
                                "wave11CurrentPathIdentityGuaranteedThroughManifestPublication":
                                    False,
                                "wave11SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
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
                            wave11_documents,
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
                    "aetherlink.g2-pion-combined-wave1-through-wave11-"
                    "fixed-point-check-error"
                ),
                "schemaVersion": "10.0",
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
