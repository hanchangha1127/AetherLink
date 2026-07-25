#!/usr/bin/env python3
"""Recompute the bounded Wave1+Wave2+Wave3+Wave4+Wave5 graph without publishing.

Run only with ``python3 -I -B -S``.  This checker holds the exact v1
read-only checker and its exact graph provider, the terminal evidence, and
163 source inputs by descriptor.  It writes only one canonical candidate to
stdout.  It grants no authority and performs no network, subprocess, source
execution, extraction, authentication, or file-write operation.

The only source-inspection change from v1 is deliberately narrow: a Go file
whose relative path has an exact lowercase ``testdata`` directory component
is retained in the byte/hash/archive inventory but is not strictly decoded or
parsed for graph build expressions or imports.  The existing lossy prefix scan
for special-class telemetry still runs.  Case variants, suffix variants, test
files, examples, and tools retain the strict v1 parsing behaviour.
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
            "combined fixed-point v4 checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v4.py"
SELF_NORMALIZED_SHA256 = (
    "bbd67ceacb71af6b4228fd3ce524b120dd836a2a9e01f552f09ffcd80e479785"
)
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
V1_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v1.py"
V1_CHECKER_RAW_SHA256 = (
    "b11047fd74e8ba4b41d66590975270921a5835bf444ad2e942af357d56764f15"
)
V2_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v2.py"
V2_CHECKER_RAW_SHA256 = (
    "1d42ffae2945bde3406bfab577ff361286859e9815e487a20cbc14282e83acf4"
)
V3_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v3.py"
V3_CHECKER_RAW_SHA256 = (
    "94835190c28e2bb815ed033ee9b3732630ab5ce1782dd94382ead208e97f10ac"
)
V1_PROVIDER_PATH = (
    "script/run_p2p_nat_g2_pion_dependency_source_review_wave1_once.py"
)
V1_PROVIDER_RAW_SHA256 = (
    "3ee8a2dbb067b31a3f0cdd02f75413ef7de33a8279b97e2100189cdb576049d3"
)
CHECKER_ID = (
    "g2-pion-ice-v4.3.0-combined-wave1-wave2-wave3-wave4-wave5-check-v4"
)
SOURCE_INSPECTION_POLICY = (
    "exact_lowercase_testdata_component_preparse_exclusion_v3"
)
CODE_MAXIMUM_BYTES = 4 * 1024 * 1024
JSON_MAXIMUM_BYTES = 8 * 1024 * 1024

WAVE3_IDENTITY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave3-v2.json"
)
WAVE3_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-decision-v1.json"
)
WAVE3_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "execution-permit-v1.json"
)
WAVE3_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-receipt-v1.json"
)
WAVE3_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-manifest-v1.json"
)
WAVE3_READBACK_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "readback-execution-permit-v1.json"
)
WAVE3_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-readback-v1.json"
)
WAVE3_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "readback-manifest-v1.json"
)
WAVE3_ACCEPTED_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-3-v1/accepted"
)

WAVE3_CONTROL_SHA256 = {
    WAVE3_IDENTITY_DECISION_PATH:
        "34d07a07dffe0c480f965192d8d81bc1961fd1ea2847e5ec5b0a2ca361d1c350",
    WAVE3_DECISION_PATH:
        "05ecc22e13fab8a0b213d27d17b4a728fa5bc8bebd088b2b2a7204fdedc03071",
    WAVE3_PERMIT_PATH:
        "8c3c0b56f96e856b7098d414f46294c9d587da7525222d8b2b707a730c12f657",
    WAVE3_RECEIPT_PATH:
        "c0d1c4a4c7a658418976446237e45e0f3955fcc600f8c5b82b51295313e14f18",
    WAVE3_MANIFEST_PATH:
        "7e1508a1fbd6e927377a1aeb709ffe44f484efcabe95c7fb739db42b56207552",
    WAVE3_READBACK_PERMIT_PATH:
        "079095911df26a7d7428b7edb212f832a9e840ba1eb18f8d8f1365e809180076",
    WAVE3_READBACK_PATH:
        "a8cce2871287fccf8d75a42abb472b75b0940e13faa6c7b10528c92b235aafca",
    WAVE3_READBACK_MANIFEST_PATH:
        "7a750e64465f762fa8160539b084565ba01e2ffd63cbe65b10fad477db3f961a",
}
WAVE3_CONTENT_SHA256 = {
    WAVE3_IDENTITY_DECISION_PATH:
        "83f97eeece6f5802f4b2fc807469a8abd08971cc8712a3bad415e801258d2e9f",
    WAVE3_DECISION_PATH:
        "0ae8b961c0aada02c3a10a9fae231e03baa7d23928abf5b14488d30b88c9de78",
    WAVE3_PERMIT_PATH:
        "a93ca38a634153feda1479fd93963b08811d20df90d7300c5bf9216c7cb66548",
    WAVE3_READBACK_PERMIT_PATH:
        "e0822ad22140a8a104e3f6a4a017e93dd7b8f7beb111ae2e54c56402ef3c4183",
    WAVE3_READBACK_PATH:
        "4fee6c64579133e67fb084242c335ca666267e73f87653fc8d899c78405df462",
    WAVE3_READBACK_MANIFEST_PATH:
        "067cac261cd7b6c5ba962a5ae53e77a85b0311cf7808e2a700cb25ecc38154c5",
}
WAVE3_RESOURCE_SET_SHA256 = (
    "38c6d44eb855352164d4a3360435c8b6a41b1e5e42c2898085643c0d8defdcf3"
)
WAVE3_ATTEMPT_ID = "47d76c38d865e40c7f16961c6fe8b31a"

WAVE4_IDENTITY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave4-v1.json"
)
WAVE4_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-"
    "execution-permit-v1.json"
)
WAVE4_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-receipt-v1.json"
)
WAVE4_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-manifest-v1.json"
)
WAVE4_READBACK_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-"
    "readback-execution-permit-v1.json"
)
WAVE4_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-readback-v1.json"
)
WAVE4_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-"
    "readback-manifest-v1.json"
)
WAVE4_ACCEPTED_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-4-v1/accepted"
)

WAVE4_CONTROL_SHA256 = {
    WAVE4_IDENTITY_DECISION_PATH:
        "7be65d39144ca8eea0180e94d0902733e9f475edbb81de792f8c57733fb27e5d",
    WAVE4_PERMIT_PATH:
        "7e2ae57e349ee1b55a58a17dd0ceda487ec400a5998b2eefa37f77d898b5c141",
    WAVE4_RECEIPT_PATH:
        "65c123fc7d256c670e5e1eba01470f26c8b2ca23d52ce31236841dcb78cae2fe",
    WAVE4_MANIFEST_PATH:
        "3132c743399611314aa8f6dce80f4864da25920f0ab9570136301cfb64716312",
    WAVE4_READBACK_PERMIT_PATH:
        "af95c2381c5225ba28bcdac206f83bbf24a466906cd716b986bfcb40161622ec",
    WAVE4_READBACK_PATH:
        "8b01cb1cde772f352aa0c9e8bdc88adf899024acbd1f13e1b807749a4f575364",
    WAVE4_READBACK_MANIFEST_PATH:
        "90c830737f302f76a02bad7ee11daf7ac3a7faa011a3530fad10b86faa4c981e",
}
WAVE4_CONTENT_SHA256 = {
    WAVE4_IDENTITY_DECISION_PATH:
        "9433ed0eb93e5b342fe1f9f9ffdb2ebcf31a3955b9c5fbc582f6af393ce28cb3",
    WAVE4_PERMIT_PATH:
        "a20c2d0da85682818076b6a6a820d36243ae95bb15ff7446f23602e45a427a7e",
    WAVE4_READBACK_PERMIT_PATH:
        "b9547b5e328de6fe1c4f6bebf87095848f958b71e70815c446cf3da457aed2ff",
    WAVE4_READBACK_PATH:
        "fbde4bb5a74fac37651bed9c6a724ff051d5ec35d585947e6225c52cadd1c728",
    WAVE4_READBACK_MANIFEST_PATH:
        "22a132d155cfd149ed3f051de6121e1309da4e73ca0abfaf695de11bfaa57e7a",
}
WAVE4_RESOURCE_SET_SHA256 = (
    "ea06da68a776c78888f95393576f68b2fd89496862176274984d2302fa57c825"
)
WAVE4_PERMIT_RESOURCES_SHA256 = (
    "2bbaa3fc7f37d6066223464e5c643a8575afc1b40aee81bd49fa963310b84a88"
)
WAVE4_SOURCE_REQUEST_SET_SHA256 = (
    "6557dc9b235c73f6453d253049a66a6f08b3a1cc6423c64e3d0e841e4da34c8b"
)
WAVE4_COMPACT_IDENTITY_SHA256 = (
    "7018a78754932244c8bc1449ad9079d19d0c48bcdb287b0109178cb3709895b2"
)
WAVE4_FULL_WITNESS_SHA256 = (
    "338069b9666561cc23dd859a202b72e45e0c7fa2f94b69d6b976777dbd148d86"
)
WAVE4_HELD_SOURCE_BINDINGS_SHA256 = (
    "b985bd0346d66beaa80381056d6650c8bb275f7ebdc9df59c861832b5655868e"
)
WAVE4_PREDECESSOR_CONTENT_SHA256 = (
    "fa67dfc9a8d49304bcc9b001e0233582e547313cc17b61934674f776ab9df215"
)
WAVE4_PREDECESSOR_INPUT_SET_SHA256 = (
    "5d79f81dfdc835c0552c0c301a2ef8e669ebcb7d13c0674d9d9cc47929d21a97"
)
WAVE4_PREDECESSOR_GRAPH_SHA256 = (
    "a824e5e3bf5fe0ede2c795192c3102a5f8d607309b3409073163de1313a23fb5"
)
WAVE4_PREDECESSOR_FRONTIER_SHA256 = (
    "568ad0362707a384511c9e23e870bd34ae2ff58faa1043e3afe7e0273227491d"
)
WAVE4_CANDIDATE_CONTENT_SHA256 = (
    "59e530d1c040e29eb7c3fb8cdde25925648c70e34d41e66559c2ef2b1d82c718"
)
WAVE4_CANDIDATE_CHECKER_SHA256 = (
    "9401a9c87f2f2e0ee563b46366c97b2fa2dcb35980a469d242be60d749f4391e"
)
WAVE4_CANDIDATE_TEST_SHA256 = (
    "a058f9ac56a44047269b5366160b942f5dead407894461c1fc80040f283ffb59"
)
WAVE4_FROZEN_FILE_SET_SHA256 = (
    "8f371bccdeedea4792b63301ff1421efc4fe58cd9b2c194c815e42676dc4c356"
)
WAVE4_ACQUISITION_CLAIM_SHA256 = (
    "999587886ba015e2c008385df68e7c2ce9c622d18e493a5a45615db5b6db8629"
)
WAVE4_EVIDENCE_SHA256 = (
    "3a1af1bc9468817dde925661ad506c5522c83c68c53058e0f200a05d1705a762"
)
WAVE4_READBACK_CHECKER_SHA256 = (
    "bfdc28ba61ccca37e626571d137718077eb20075122fb55db67ab000365087ca"
)
WAVE4_READBACK_RECORDER_SHA256 = (
    "7a9a4f67b13a73f055a8be0dbcbf8fd33120dab01bf6f85139655bd6d63cca05"
)
WAVE4_ATTEMPT_ID = "4cda3d86462fff445d6e69bce4b92dec"
WAVE4_READBACK_ATTEMPT_ID = "abab55937e110dc0a77018509db6ecca"
WAVE4_ACQUISITION_AUTHORITY = {
    "compileAuthorized": False,
    "deploymentAuthorized": False,
    "deviceAuthorized": False,
    "dnsTcpTlsHttpsToExactProxyAuthorized": True,
    "externalAuthenticationRequired": False,
    "gitOperationAuthorized": False,
    "packageManagerAuthorized": False,
    "passwordRequired": False,
    "privateKeyRequired": False,
    "productRuntimeNetworkAuthorized": False,
    "repositoryOwnerIdentityProofRequired": False,
    "signatureRequired": False,
    "sourceExtractionAuthorized": False,
    "sourceLoadOrExecutionAuthorized": False,
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
    "wave4SourceAcquisitionAuthorizedOnce": True,
}
WAVE4_READBACK_AUTHORITY = {
    "authenticationRequired": False,
    "compileAuthorized": False,
    "credentialRequired": False,
    "deploymentAuthorized": False,
    "deviceAuthorized": False,
    "dnsAuthorized": False,
    "externalAuthenticationRequired": False,
    "failedTemporaryCleanupAuthorized": True,
    "frozenInputWritesAuthorized": False,
    "gitOperationAuthorized": False,
    "networkAuthorized": False,
    "offlineReadbackAuthorizedOnce": True,
    "otherRepositoryWritesAuthorized": False,
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
    "subprocessAuthorized": False,
    "tokenRequired": False,
    "userActionRequired": False,
}
WAVE4_ACQUISITION_CHECKER_SHA256 = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
WAVE4_ACQUISITION_RUNNER_SHA256 = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)

WAVE5_IDENTITY_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave5-v1.json"
)
WAVE5_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "execution-permit-v1.json"
)
WAVE5_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-receipt-v1.json"
)
WAVE5_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-manifest-v1.json"
)
WAVE5_READBACK_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "readback-execution-permit-v1.json"
)
WAVE5_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-readback-v1.json"
)
WAVE5_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "readback-manifest-v1.json"
)
WAVE5_ACCEPTED_DIRECTORY = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    "wave-5-v1/accepted"
)
WAVE5_CONTROL_SHA256 = {
    WAVE5_IDENTITY_DECISION_PATH:
        "fb2d6ec8e29f50e7d6198d452366cce98c4414e4d7a409634ad1daffe02d195e",
    WAVE5_PERMIT_PATH:
        "9a99858e73a0c6bf8142ce8d3927abb84cf2290dfd0b595ea818ed5ad423fd49",
    WAVE5_RECEIPT_PATH:
        "5063004755ac2cf50eeea9b03be6de9ad361ccb2917edd8f864baba5409362a7",
    WAVE5_MANIFEST_PATH:
        "e52ffcf5c8c0b04e76a7ecb6cb5610dc30307d3fc03f1dfb0f6d91a8edae9d52",
    WAVE5_READBACK_PERMIT_PATH:
        "dd8a38e0a0bf875b3bc6ddb7949b5bda61c1016304ccbe19b952b310a494edb1",
    WAVE5_READBACK_PATH:
        "dcd2f6703e770c453ded369f8c4b1b082bbbe8162bb785ba84885e1c70a16cc2",
    WAVE5_READBACK_MANIFEST_PATH:
        "1f9eea4c306e6f59c21e5a6dc66b23f1e530b9d006075f7b3a6199dcebc79059",
}
WAVE5_CONTENT_SHA256 = {
    WAVE5_IDENTITY_DECISION_PATH:
        "042360fe15b03240341e4f7e80aa59b630dbc6647ea3d05f4980881e09a6f912",
    WAVE5_PERMIT_PATH:
        "215e422bf431cca958086116efc8e712ef5c2b0b64ad5f84950939c66176144e",
    WAVE5_READBACK_PERMIT_PATH:
        "e207b799ee361aa3c7dec6eae520083914bba4b5ed112082fd6c6df460714e3e",
    WAVE5_READBACK_PATH:
        "8dfdaeb88fc2e08044893cde3a2f638d3bf091ec08f410aa6765d9cb7d619297",
    WAVE5_READBACK_MANIFEST_PATH:
        "d8be371ff7f038b33fd5ecb69ecda27398d526fde2713717b66c1b964c88eee4",
}
WAVE5_RESOURCE_SET_SHA256 = (
    "b929d977644f7502a27340f2817957a95fb0ddcc885ee9222a525132939fa226"
)
WAVE5_PERMIT_RESOURCES_SHA256 = (
    "7901f7b3556e9443eb9f16dd8e733b24e15c2ac72d48e84d56e45572f8c16b63"
)
WAVE5_SOURCE_REQUEST_SET_SHA256 = (
    "1197fd5d5e7f6bdaccb3b4538fd999bc4995fe34890cd8472f3df68fa00b0fae"
)
WAVE5_COMPACT_IDENTITY_SHA256 = (
    "52567cdead3fcd8029f9c1676a7f83af86a5d0110c52851b47e55b2f09af8a7d"
)
WAVE5_FULL_WITNESS_SHA256 = (
    "af51e067ccf3388561bfe0e2b38dae744792625cdc5f7a37b55208b41d4a5fb4"
)
WAVE5_HELD_SOURCE_BINDINGS_SHA256 = (
    "025e9a401eda9fac4687ed4c2cdbefd07a0b0489d31c1b43fe9744350579ff78"
)
WAVE5_PREDECESSOR_CONTENT_SHA256 = (
    "a752f444042290e51ee794db76b2ab18c9d3269bb2fb0d5c1abae11ee80b10ce"
)
WAVE5_PREDECESSOR_INPUT_SET_SHA256 = (
    "b2d981dae1576f27ae5cd292e218b0a0eb35f5bdc0d98734fb1b350408ce4eca"
)
WAVE5_PREDECESSOR_GRAPH_SHA256 = (
    "ee330142d77874457cccf78d5a9fe51652c81916f1d7aabb390f321dff51e03a"
)
WAVE5_PREDECESSOR_FRONTIER_SHA256 = (
    "026810f158d7a8cfcef61f7a09d9a9bc964bd41e4b2f529994fce6d70cbce960"
)
WAVE5_CANDIDATE_CONTENT_SHA256 = (
    "18ccc0e179cdc5d7ab28b5ffd9ea38f16a4fdab3d79d2bd9d0ebd0219b22a0d9"
)
WAVE5_CANDIDATE_CHECKER_SHA256 = (
    "03bab08c5aee4bfe2a952a848f209ace174bc1d00dea4ec4912805f9ab7f8e66"
)
WAVE5_CANDIDATE_TEST_SHA256 = (
    "b8086f00c8d3d4ebc372415bc68714fb7a01abb57c4292dc1bd0fde296359faf"
)
WAVE5_FROZEN_FILE_SET_SHA256 = (
    "2248f787514d4456d0bd8fde9bcba35a04b0d75613f0c4131a9898d456f4782c"
)
WAVE5_ACQUISITION_CLAIM_SHA256 = (
    "704b24ac42dd34e22550619315fc4c80732bf494dcd687e97ff321d3ac360909"
)
WAVE5_EVIDENCE_SHA256 = (
    "93b14f30d0bcd24ee628d7d2ab39a083312ee837d345bd673e7983f12895bb29"
)
WAVE5_READBACK_CHECKER_SHA256 = (
    "23de57b5b29d4f86f944a604fd1194e9c763627d7ebc25ce87e689e599292180"
)
WAVE5_READBACK_RECORDER_SHA256 = (
    "db6dd945cb8a3f585b733739eec29a4d7d26278de4b87b5ece1db8bad68763af"
)
WAVE5_READBACK_CLAIM_SHA256 = (
    "135ac7b186781732e6c1f36d77a42d4d32fb4dbe7ea46aa85504a54180965145"
)
WAVE5_READBACK_CLAIM_CONTENT_SHA256 = (
    "f85c54394d3950a931f84d90535d85845383c151da84a5fd3d03c88989cd9a4e"
)
WAVE5_ATTEMPT_ID = "ed050bd13835ab1f9fecc0dd3cfb6e12"
WAVE5_READBACK_ATTEMPT_ID = "8f3813a784359883b4d93370c9041809"
WAVE5_ACQUISITION_CHECKER_SHA256 = (
    "0e004d35822f41a2ffa271c5175bdde5a51a786fb86965de320d23a2227f129f"
)
WAVE5_ACQUISITION_RUNNER_SHA256 = (
    "464afe4978486858fee622c885f35c94d65c9eb115e340832afb1e1a76327923"
)
WAVE5_ACQUISITION_AUTHORITY = {
    **WAVE4_ACQUISITION_AUTHORITY,
    "wave5SourceAcquisitionAuthorizedOnce": True,
}
WAVE5_ACQUISITION_AUTHORITY.pop("wave4SourceAcquisitionAuthorizedOnce")
WAVE5_READBACK_AUTHORITY = dict(WAVE4_READBACK_AUTHORITY)


class CombinedCheckFailure(RuntimeError):
    """A content-free, fail-closed checker error."""


class CliUsageFailure(RuntimeError):
    """An intentionally content-free command-line usage failure."""


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CliUsageFailure("E_CLI_USAGE")


def check(condition: bool, code: str) -> None:
    if not condition:
        raise CombinedCheckFailure(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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
    return (
        raw[:payload_start]
        + (b"0" * 64)
        + raw[payload_end:]
    )


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


def combined_identity_barrier(
    root: Path,
    held_inputs: Sequence[Any],
) -> None:
    """Bind every held input set to the same currently named workspace root."""

    try:
        named_before = os.stat(root, follow_symlinks=False)
        check(stat.S_ISDIR(named_before.st_mode), "E_ROOT_IDENTITY")
        expected = directory_identity(named_before)
        for held in held_inputs:
            root_fd = getattr(held, "root_fd", -1)
            check(
                type(root_fd) is int
                and root_fd >= 0
                and directory_identity(os.fstat(root_fd)) == expected,
                "E_ROOT_IDENTITY",
            )
        for held in held_inputs:
            held.final_barrier()
        named_after = os.stat(root, follow_symlinks=False)
        check(
            directory_identity(named_after) == expected,
            "E_ROOT_IDENTITY",
        )
    except OSError as error:
        raise CombinedCheckFailure("E_ROOT_IDENTITY") from error


class PinnedCodeFile:
    """Open, hold, verify, and later re-check one exact Python source file."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        expected_sha256: str,
        normalizer: Any = None,
    ) -> None:
        self.relative_path = relative_path
        self.expected_sha256 = expected_sha256
        self.normalizer = normalizer
        self.root_fd = -1
        self.parent_fd = -1
        self.fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.raw = b""
        try:
            parts = relative_path.split("/")
            check(
                parts
                and all(part not in {"", ".", ".."} for part in parts),
                "E_V1_CHECKER_IDENTITY",
            )
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self._validate_directory(os.fstat(self.root_fd))
            current = os.dup(self.root_fd)
            for component in parts[:-1]:
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    dir_fd=current,
                )
                info = os.fstat(child)
                self._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.parent_fd = current
            self.name = parts[-1]
            self.fd = os.open(
                self.name,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=self.parent_fd,
            )
            self.initial = os.fstat(self.fd)
            self._validate_file(self.initial)
            first = self._read_pass()
            second = self._read_pass()
            checked = (
                first
                if self.normalizer is None
                else self.normalizer(first)
            )
            check(
                first == second
                and sha256_bytes(checked) == self.expected_sha256,
                "E_V1_CHECKER_IDENTITY",
            )
            self.raw = first
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        check(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_V1_CHECKER_IDENTITY",
        )

    @staticmethod
    def _validate_file(info: os.stat_result) -> None:
        check(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= CODE_MAXIMUM_BYTES,
            "E_V1_CHECKER_IDENTITY",
        )

    def _read_pass(self) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            check(bool(chunk), "E_V1_CHECKER_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        check(os.read(self.fd, 1) == b"", "E_V1_CHECKER_IDENTITY")
        after = os.fstat(self.fd)
        check(
            file_identity(before) == file_identity(after),
            "E_V1_CHECKER_IDENTITY",
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
            file_identity(current) == file_identity(self.initial)
            and file_identity(named) == file_identity(self.initial),
            "E_V1_CHECKER_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            check(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                and directory_identity(
                    os.stat(component, dir_fd=parent, follow_symlinks=False)
                )
                == directory_identity(initial),
                "E_V1_CHECKER_IDENTITY",
            )

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directories):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directories.clear()
        if self.parent_fd >= 0 and self.parent_fd not in seen:
            os.close(self.parent_fd)
        self.parent_fd = -1
        if self.root_fd >= 0:
            os.close(self.root_fd)
            self.root_fd = -1

    def __enter__(self) -> "PinnedCodeFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_v1_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_checker_v1_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V1_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_checker_v1_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V1_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V1_CHECKER_LOAD") from error
    for name in (
        "PinnedRunnerFile",
        "load_pinned_runner",
        "control_bindings",
        "parse_control_documents",
        "validate_terminal_documents",
        "source_bindings",
        "graph_limits",
        "route_for_graph",
        "source_projection",
    ):
        check(callable(getattr(module, name, None)), "E_V1_CHECKER_API")
    check(
        module.RUNNER_PATH == V1_PROVIDER_PATH
        and module.RUNNER_SHA256 == V1_PROVIDER_RAW_SHA256,
        "E_V1_CHECKER_API",
    )
    return module


def load_v3_checker(held: PinnedCodeFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_combined_fixed_point_checker_v3_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / V3_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_combined_fixed_point_checker_v3_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            V3_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise CombinedCheckFailure("E_V3_CHECKER_LOAD") from error
    check(
        callable(getattr(module, "generate_candidate", None))
        and module.V1_CHECKER_PATH == V1_CHECKER_PATH
        and module.V1_CHECKER_RAW_SHA256 == V1_CHECKER_RAW_SHA256
        and module.V2_CHECKER_PATH == V2_CHECKER_PATH
        and module.V2_CHECKER_RAW_SHA256 == V2_CHECKER_RAW_SHA256
        and module.V1_PROVIDER_PATH == V1_PROVIDER_PATH
        and module.V1_PROVIDER_RAW_SHA256 == V1_PROVIDER_RAW_SHA256,
        "E_V3_CHECKER_API",
    )
    return module


def validate_v3_predecessor_candidate(
    runner: types.ModuleType,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    binding = candidate.get("contentBinding")
    without = dict(candidate)
    without.pop("contentBinding", None)
    input_set = candidate.get("inputSet")
    graph = candidate.get("graphDiscovery")
    frontier = graph.get("exactFrontier") if type(graph) is dict else None
    authority = candidate.get("authority")
    check(
        type(binding) is dict
        and binding
        == {
            "algorithm": "sha256",
            "canonicalization":
                "utf8_ascii_escaped_sorted_keys_compact_single_lf",
            "scope": "candidate_without_contentBinding",
            "sha256": WAVE5_PREDECESSOR_CONTENT_SHA256,
        }
        and sha256_bytes(runner.canonical_json_bytes(without))
        == WAVE5_PREDECESSOR_CONTENT_SHA256
        and candidate.get("documentType")
        == (
            "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
            "fixed-point-candidate"
        )
        and candidate.get("schemaVersion") == "3.0"
        and candidate.get("status")
        == "combined_graph_discovery_complete_next_wave_required"
        and type(input_set) is dict
        and input_set.get("heldSourceInputCount") == 133
        and input_set.get("combinedInputSetSha256")
        == WAVE5_PREDECESSOR_INPUT_SET_SHA256
        and type(graph) is dict
        and graph.get("fixedPointReached") is False
        and graph.get("newTupleCount") == 15
        and graph.get("graphSha256") == WAVE5_PREDECESSOR_GRAPH_SHA256
        and type(frontier) is list
        and len(frontier) == 15
        and sha256_bytes(runner.canonical_json_bytes(frontier))
        == WAVE5_PREDECESSOR_FRONTIER_SHA256
        and type(authority) is dict
        and authority
        and all(value is False for value in authority.values()),
        "E_V3_PREDECESSOR",
    )
    return {
        "checkerExecutedFromPinnedBytes": True,
        "candidateContentSha256": WAVE5_PREDECESSOR_CONTENT_SHA256,
        "combinedInputSetSha256": WAVE5_PREDECESSOR_INPUT_SET_SHA256,
        "graphSha256": WAVE5_PREDECESSOR_GRAPH_SHA256,
        "frontierSha256": WAVE5_PREDECESSOR_FRONTIER_SHA256,
        "fixedPointReached": False,
        "frontierTupleCount": 15,
    }


def wave3_control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": False,
            "kind": "terminal_evidence",
        }
        for path, digest in WAVE3_CONTROL_SHA256.items()
    ]


def verify_content_binding(
    runner: types.ModuleType,
    document: Mapping[str, Any],
    expected_sha256: str,
) -> None:
    binding = document.get("contentBinding")
    check(
        type(binding) is dict
        and set(binding) == {"algorithm", "sha256"}
        and binding.get("algorithm")
        == "sha256(canonical-json-without-contentBinding)"
        and binding.get("sha256") == expected_sha256,
        "E_WAVE3_CONTENT_BINDING",
    )
    without = dict(document)
    without.pop("contentBinding", None)
    check(
        sha256_bytes(runner.canonical_json_bytes(without)) == expected_sha256,
        "E_WAVE3_CONTENT_BINDING",
    )


def parse_wave3_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in WAVE3_CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_WAVE3_JSON")
        result[path] = value
    return result


def wave3_request_resources(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    identity = documents[WAVE3_IDENTITY_DECISION_PATH]
    decision = documents[WAVE3_DECISION_PATH]
    permit = documents[WAVE3_PERMIT_PATH]
    receipt = documents[WAVE3_RECEIPT_PATH]
    manifest = documents[WAVE3_MANIFEST_PATH]
    readback_permit = documents[WAVE3_READBACK_PERMIT_PATH]
    readback = documents[WAVE3_READBACK_PATH]
    readback_manifest = documents[WAVE3_READBACK_MANIFEST_PATH]

    for path, expected in WAVE3_CONTENT_SHA256.items():
        verify_content_binding(runner, documents[path], expected)
    check(
        identity.get("status")
        == (
            "wave3_exact_16_frontier_identity_classified_16_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and identity.get("graphBinding", {}).get("newTupleCount") == 16
        and identity.get("graphBinding", {}).get("fixedPointReached") is False,
        "E_WAVE3_IDENTITY",
    )
    identity_binding = decision.get("wave3IdentityDecisionBinding")
    check(
        type(identity_binding) is dict
        and identity_binding.get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_IDENTITY_DECISION_PATH]
        and any(
            type(row) is dict
            and row.get("path") == WAVE3_IDENTITY_DECISION_PATH
            and row.get("rawSha256")
            == WAVE3_CONTROL_SHA256[WAVE3_IDENTITY_DECISION_PATH]
            for row in identity_binding.get("files", [])
        ),
        "E_WAVE3_IDENTITY",
    )
    request_set = decision.get("requestSet")
    permit_contract = permit.get("requestContract")
    check(
        decision.get("status")
        == "exact_32_resource_contract_prepared_acquisition_not_authorized"
        and type(request_set) is dict
        and request_set.get("requestCount") == 32
        and request_set.get("tupleCount") == 16
        and request_set.get("resourcesPerTuple") == 2
        and request_set.get("order") == "tuple_order_ascending_mod_then_zip"
        and type(permit_contract) is dict
        and permit_contract.get("requestCount") == 32
        and permit_contract.get("resources")
        == request_set.get("resources"),
        "E_WAVE3_REQUEST",
    )
    resources = request_set["resources"]
    check(type(resources) is list and len(resources) == 32, "E_WAVE3_REQUEST")

    decision_binding = permit.get("decisionBinding")
    check(
        permit.get("status") == "authorized_not_consumed"
        and type(decision_binding) is dict
        and decision_binding.get("path") == WAVE3_DECISION_PATH
        and decision_binding.get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_DECISION_PATH]
        and decision_binding.get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_DECISION_PATH],
        "E_WAVE3_PERMIT",
    )
    check(
        receipt.get("status") == "consumed_success_pending_readback"
        and receipt.get("attemptId") == WAVE3_ATTEMPT_ID
        and receipt.get("acceptedResourceCount") == 32
        and receipt.get("modCount") == 16
        and receipt.get("zipCount") == 16
        and receipt.get("aggregateResponseBytes") == 32_425_130
        and receipt.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE3_RESOURCE_SET_SHA256,
        "E_WAVE3_RECEIPT",
    )
    check(
        manifest.get("status") == "consumed_success_pending_readback"
        and manifest.get("attemptId") == WAVE3_ATTEMPT_ID
        and manifest.get("manifestWrittenLast") is True
        and manifest.get("receiptPath") == WAVE3_RECEIPT_PATH
        and manifest.get("receiptRawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_RECEIPT_PATH],
        "E_WAVE3_MANIFEST",
    )

    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    check(
        readback_permit.get("status") == "authorized_not_consumed"
        and type(snapshot) is dict
        and snapshot.get("attemptId") == WAVE3_ATTEMPT_ID
        and snapshot.get("acceptedResourceCount") == 32
        and snapshot.get("modCount") == 16
        and snapshot.get("zipCount") == 16
        and snapshot.get("aggregateAcceptedBytes") == 32_425_130
        and snapshot.get("aggregateModBytes") == 2_555
        and snapshot.get("aggregateZipBytes") == 32_422_575
        and snapshot.get("acquisitionReceipt", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_RECEIPT_PATH]
        and snapshot.get("acquisitionManifest", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_MANIFEST_PATH],
        "E_WAVE3_READBACK_PERMIT",
    )
    accepted = snapshot.get("acceptedDirectory")
    accepted_files = accepted.get("files") if type(accepted) is dict else None
    check(
        type(accepted) is dict
        and accepted.get("path") == WAVE3_ACCEPTED_DIRECTORY
        and accepted.get("exactFileCount") == 32
        and type(accepted_files) is list
        and len(accepted_files) == 32,
        "E_WAVE3_READBACK_PERMIT",
    )
    verified = readback.get("verified")
    check(
        readback.get("status") == "wave3_acquisition_independently_read_back"
        and readback.get("offline") is True
        and readback.get("externalAuthenticationRequired") is False
        and readback.get("userActionRequired") is False
        and readback.get("networkRequestAttemptCount") == 0
        and readback.get("sourceAcquisitionCount") == 0
        and readback.get("verificationPassCount") == 2
        and readback.get("sourceExtracted") is False
        and readback.get("sourceLoadedOrExecuted") is False
        and readback.get("compiled") is False
        and type(verified) is dict
        and verified.get("status") == "wave3_acquisition_independently_verified"
        and verified.get("acceptedResourceCount") == 32
        and verified.get("modCount") == 16
        and verified.get("zipCount") == 16
        and verified.get("aggregateAcceptedBytes") == 32_425_130
        and verified.get("aggregateModBytes") == 2_555
        and verified.get("aggregateZipBytes") == 32_422_575
        and verified.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE3_RESOURCE_SET_SHA256,
        "E_WAVE3_READBACK",
    )
    authority = readback.get("authorityBinding")
    manifest_authority = readback_manifest.get("authorityBinding")
    check(
        authority == manifest_authority
        and type(authority) is dict
        and authority.get("permit", {}).get("path")
        == WAVE3_READBACK_PERMIT_PATH
        and authority.get("permit", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_READBACK_PERMIT_PATH]
        and authority.get("permit", {}).get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_READBACK_PERMIT_PATH],
        "E_WAVE3_READBACK",
    )
    check(
        readback_manifest.get("status")
        == "wave3_acquisition_readback_publication_complete"
        and readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("offline") is True
        and readback_manifest.get("externalAuthenticationRequired") is False
        and readback_manifest.get("userActionRequired") is False
        and readback_manifest.get("networkRequestAttemptCount") == 0
        and readback_manifest.get("sourceAcquisitionCount") == 0
        and readback_manifest.get("receipt", {}).get("path")
        == WAVE3_READBACK_PATH
        and readback_manifest.get("receipt", {}).get("rawSha256")
        == WAVE3_CONTROL_SHA256[WAVE3_READBACK_PATH]
        and readback_manifest.get("receipt", {}).get("contentSha256")
        == WAVE3_CONTENT_SHA256[WAVE3_READBACK_PATH],
        "E_WAVE3_READBACK_MANIFEST",
    )

    accepted_by_name = {
        PurePosixPath(row.get("path", "")).name: row
        for row in accepted_files
        if type(row) is dict
    }
    verified_rows = verified.get("resources")
    check(
        len(accepted_by_name) == 32
        and type(verified_rows) is list
        and len(verified_rows) == 32,
        "E_WAVE3_RESOURCE",
    )
    verified_by_name = {
        row.get("acceptedFileName"): row
        for row in verified_rows
        if type(row) is dict
    }
    check(len(verified_by_name) == 32, "E_WAVE3_RESOURCE")

    result: list[dict[str, Any]] = []
    tuple_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, value in enumerate(resources, 1):
        check(
            type(value) is dict
            and value.get("requestOrdinal") == index
            and value.get("tupleOrder") == (index + 1) // 2
            and value.get("kind") == ("mod" if index % 2 else "zip")
            and type(value.get("module")) is str
            and type(value.get("version")) is str
            and type(value.get("tupleId")) is str
            and type(value.get("acceptedFileName")) is str
            and "/" not in value["acceptedFileName"],
            "E_WAVE3_RESOURCE",
        )
        accepted_row = accepted_by_name.get(value["acceptedFileName"])
        verified_row = verified_by_name.get(value["acceptedFileName"])
        check(
            type(accepted_row) is dict
            and type(verified_row) is dict
            and accepted_row.get("path")
            == f"{WAVE3_ACCEPTED_DIRECTORY}/{value['acceptedFileName']}"
            and accepted_row.get("mode") == "0600"
            and accepted_row.get("linkCount") == 1
            and type(accepted_row.get("bytes")) is int
            and accepted_row["bytes"] > 0
            and verified_row.get("requestOrdinal") == index
            and verified_row.get("tupleId") == value["tupleId"]
            and verified_row.get("kind") == value["kind"]
            and verified_row.get("url") == value["url"]
            and verified_row.get("byteCount") == accepted_row["bytes"]
            and verified_row.get("rawSha256") == accepted_row.get("rawSha256"),
            "E_WAVE3_RESOURCE",
        )
        row = {
            "wave": "wave3",
            "path": accepted_row["path"],
            "rawSha256": accepted_row["rawSha256"],
            "maximumBytes": accepted_row["bytes"],
            "ownerOnly": True,
            "kind": value["kind"],
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 34 + value["tupleOrder"],
            "order": index,
        }
        if value["kind"] == "zip":
            row["modulePrefix"] = (
                f"{runner.go_proxy_escape(value['module'])}@"
                f"{runner.go_proxy_escape(value['version'])}/"
            )
        tuple_rows[value["tupleId"]].append(row)
        result.append(row)
    check(
        len(tuple_rows) == 16
        and all(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len({(row["module"], row["version"]) for row in rows}) == 1
            for rows in tuple_rows.values()
        ),
        "E_WAVE3_RESOURCE",
    )
    return result


def wave4_control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": False,
            "kind": "terminal_evidence",
        }
        for path, digest in WAVE4_CONTROL_SHA256.items()
    ]


def verify_modern_content_binding(
    runner: types.ModuleType,
    document: Mapping[str, Any],
    expected_sha256: str,
    scope: str,
) -> None:
    binding = document.get("contentBinding")
    check(
        type(binding) is dict
        and set(binding)
        == {"algorithm", "canonicalization", "scope", "sha256"}
        and binding.get("algorithm") == "sha256"
        and binding.get("canonicalization")
        == "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        and binding.get("scope") == scope
        and binding.get("sha256") == expected_sha256,
        "E_WAVE4_CONTENT_BINDING",
    )
    without = dict(document)
    without.pop("contentBinding", None)
    check(
        sha256_bytes(runner.canonical_json_bytes(without)) == expected_sha256,
        "E_WAVE4_CONTENT_BINDING",
    )


def verify_wave4_content_bindings(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    verify_modern_content_binding(
        runner,
        documents[WAVE4_IDENTITY_DECISION_PATH],
        WAVE4_CONTENT_SHA256[WAVE4_IDENTITY_DECISION_PATH],
        "decision_without_contentBinding",
    )
    verify_modern_content_binding(
        runner,
        documents[WAVE4_PERMIT_PATH],
        WAVE4_CONTENT_SHA256[WAVE4_PERMIT_PATH],
        "permit_without_contentBinding",
    )
    for path in (
        WAVE4_READBACK_PERMIT_PATH,
        WAVE4_READBACK_PATH,
        WAVE4_READBACK_MANIFEST_PATH,
    ):
        verify_content_binding(
            runner,
            documents[path],
            WAVE4_CONTENT_SHA256[path],
        )


def parse_wave4_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in WAVE4_CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_WAVE4_JSON")
        result[path] = value
    return result


def wave4_request_resources(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    identity = documents[WAVE4_IDENTITY_DECISION_PATH]
    permit = documents[WAVE4_PERMIT_PATH]
    receipt = documents[WAVE4_RECEIPT_PATH]
    manifest = documents[WAVE4_MANIFEST_PATH]
    readback_permit = documents[WAVE4_READBACK_PERMIT_PATH]
    readback = documents[WAVE4_READBACK_PATH]
    readback_manifest = documents[WAVE4_READBACK_MANIFEST_PATH]

    verify_wave4_content_bindings(runner, documents)

    identity_resolution = identity.get("identityResolution")
    held_source_set = identity.get("heldSourceInputSet")
    preparation = identity.get("sourceAcquisitionPreparation")
    predecessors = identity.get("predecessorBindings")
    combined_v2 = (
        predecessors.get("combinedFixedPointV2")
        if type(predecessors) is dict
        else None
    )
    wave4_candidate = (
        predecessors.get("wave4Candidate")
        if type(predecessors) is dict
        else None
    )
    check(
        identity.get("status")
        == (
            "wave4_exact_16_frontier_identity_classified_16_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and type(identity_resolution) is dict
        and identity_resolution.get("tupleCount") == 16
        and identity_resolution.get("completeIdentityPairCount") == 16
        and identity_resolution.get("blockedTupleCount") == 0
        and identity_resolution.get("graphSelectedTupleCount") == 3
        and identity_resolution.get("versionSpecificNonSelectedTupleCount")
        == 13
        and identity_resolution.get("compactIdentitySha256")
        == WAVE4_COMPACT_IDENTITY_SHA256
        and identity_resolution.get("fullWitnessSha256")
        == WAVE4_FULL_WITNESS_SHA256
        and type(held_source_set) is dict
        and held_source_set.get("sourceBindingCount") == 101
        and held_source_set.get("sourceBindingsSha256")
        == WAVE4_HELD_SOURCE_BINDINGS_SHA256
        and type(preparation) is dict
        and preparation.get("acquisitionReady") is True
        and preparation.get("acquisitionAuthorizedByThisDecision") is False
        and preparation.get("requestCount") == 32
        and preparation.get("requestOrder")
        == "tuple_order_ascending_mod_then_zip"
        and preparation.get("acceptedDirectoryPath")
        == WAVE4_ACCEPTED_DIRECTORY
        and type(combined_v2) is dict
        and combined_v2.get("contentSha256")
        == WAVE4_PREDECESSOR_CONTENT_SHA256
        and combined_v2.get("combinedInputSetSha256")
        == WAVE4_PREDECESSOR_INPUT_SET_SHA256
        and combined_v2.get("graphSha256")
        == WAVE4_PREDECESSOR_GRAPH_SHA256
        and combined_v2.get("frontierSha256")
        == WAVE4_PREDECESSOR_FRONTIER_SHA256
        and combined_v2.get("fixedPointReached") is False
        and type(wave4_candidate) is dict
        and wave4_candidate.get("checkerPath")
        == "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_candidate_v1.py"
        and wave4_candidate.get("checkerRawSha256")
        == WAVE4_CANDIDATE_CHECKER_SHA256
        and wave4_candidate.get("testsPath")
        == "script/test_p2p_nat_g2_pion_rung3_dependency_wave4_candidate_v1.py"
        and wave4_candidate.get("testsRawSha256")
        == WAVE4_CANDIDATE_TEST_SHA256
        and wave4_candidate.get("contentSha256")
        == WAVE4_CANDIDATE_CONTENT_SHA256
        and wave4_candidate.get("tupleCount") == 16,
        "E_WAVE4_IDENTITY",
    )
    identity_tuples = identity_resolution.get("tuples")
    source_requests = preparation.get("requestSet")
    check(
        type(identity_tuples) is list
        and len(identity_tuples) == 16
        and sum(
            row.get("selectedByGraphAlgorithm") is True
            for row in identity_tuples
            if type(row) is dict
        )
        == 3
        and sum(
            row.get("selectedByGraphAlgorithm") is False
            for row in identity_tuples
            if type(row) is dict
        )
        == 13
        and type(source_requests) is list
        and len(source_requests) == 32
        and sha256_bytes(runner.canonical_json_bytes(source_requests))
        == WAVE4_SOURCE_REQUEST_SET_SHA256,
        "E_WAVE4_IDENTITY",
    )

    decision_binding = permit.get("decisionBinding")
    identity_binding = permit.get("identityBinding")
    request_contract = permit.get("requestContract")
    authority = permit.get("authority")
    check(
        permit.get("status") == "authorized_not_consumed"
        and type(decision_binding) is dict
        and decision_binding.get("path") == WAVE4_IDENTITY_DECISION_PATH
        and decision_binding.get("rawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_IDENTITY_DECISION_PATH]
        and decision_binding.get("contentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_IDENTITY_DECISION_PATH]
        and type(identity_binding) is dict
        and identity_binding.get("compactIdentitySha256")
        == WAVE4_COMPACT_IDENTITY_SHA256
        and identity_binding.get("fullWitnessSha256")
        == WAVE4_FULL_WITNESS_SHA256
        and identity_binding.get("heldSourceBindingsSha256")
        == WAVE4_HELD_SOURCE_BINDINGS_SHA256
        and identity_binding.get("completeTupleCount") == 16
        and identity_binding.get("blockedTupleCount") == 0
        and type(authority) is dict
        and authority == WAVE4_ACQUISITION_AUTHORITY,
        "E_WAVE4_PERMIT",
    )
    resources = (
        request_contract.get("resources")
        if type(request_contract) is dict
        else None
    )
    check(
        type(request_contract) is dict
        and request_contract.get("requestCount") == 32
        and request_contract.get("tupleCount") == 16
        and request_contract.get("order")
        == "tuple_order_ascending_mod_then_zip"
        and request_contract.get("sourceRequestSetCanonicalSha256")
        == WAVE4_SOURCE_REQUEST_SET_SHA256
        and request_contract.get("resourcesCanonicalSha256")
        == WAVE4_PERMIT_RESOURCES_SHA256
        and type(resources) is list
        and len(resources) == 32
        and sha256_bytes(runner.canonical_json_bytes(resources))
        == WAVE4_PERMIT_RESOURCES_SHA256,
        "E_WAVE4_REQUEST",
    )

    check(
        receipt.get("status")
        == "consumed_success_pending_independent_readback"
        and receipt.get("attemptId") == WAVE4_ATTEMPT_ID
        and receipt.get("acceptedResourceCount") == 32
        and receipt.get("modCount") == 16
        and receipt.get("zipCount") == 16
        and receipt.get("aggregateResponseBytes") == 24_118_812
        and receipt.get("aggregateModResponseBytes") == 1_901
        and receipt.get("aggregateZipResponseBytes") == 24_116_911
        and receipt.get("aggregateZipEntryCount") == 5_936
        and receipt.get("aggregateZipUncompressedBytes") == 87_874_800
        and receipt.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE4_RESOURCE_SET_SHA256
        and receipt.get("decisionContentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_IDENTITY_DECISION_PATH]
        and receipt.get("permitContentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_PERMIT_PATH]
        and receipt.get("claimRawSha256")
        == WAVE4_ACQUISITION_CLAIM_SHA256
        and receipt.get("acceptedEvidenceRawSha256")
        == WAVE4_EVIDENCE_SHA256
        and receipt.get("checkerRawSha256")
        == WAVE4_ACQUISITION_CHECKER_SHA256
        and receipt.get("runnerRawSha256")
        == WAVE4_ACQUISITION_RUNNER_SHA256
        and receipt.get("sourceAcquired") is True
        and receipt.get("sourceExtracted") is False
        and receipt.get("sourceLoadedOrExecuted") is False
        and receipt.get("compiled") is False
        and receipt.get("externalAuthenticationRequired") is False
        and receipt.get("userActionRequired") is False,
        "E_WAVE4_RECEIPT",
    )
    check(
        manifest.get("status")
        == "consumed_success_pending_independent_readback"
        and manifest.get("attemptId") == WAVE4_ATTEMPT_ID
        and manifest.get("manifestWrittenLast") is True
        and manifest.get("receiptPath") == WAVE4_RECEIPT_PATH
        and manifest.get("receiptRawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_RECEIPT_PATH],
        "E_WAVE4_MANIFEST",
    )

    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    readback_authority = readback_permit.get("authority")
    check(
        readback_permit.get("status") == "authorized_not_consumed"
        and type(snapshot) is dict
        and snapshot.get("attemptId") == WAVE4_ATTEMPT_ID
        and snapshot.get("frozenFileCount") == 48
        and snapshot.get("frozenFilesCanonicalSha256")
        == WAVE4_FROZEN_FILE_SET_SHA256
        and snapshot.get("acquisitionDecisionContentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_IDENTITY_DECISION_PATH]
        and snapshot.get("acquisitionPermitContentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_PERMIT_PATH]
        and type(snapshot.get("acquisitionAuthority")) is list
        and len(snapshot["acquisitionAuthority"]) == 12
        and snapshot.get("acceptedResourceCount") == 32
        and snapshot.get("selectedTupleCount") == 3
        and snapshot.get("modCount") == 16
        and snapshot.get("zipCount") == 16
        and snapshot.get("aggregateAcceptedBytes") == 24_118_812
        and snapshot.get("aggregateModBytes") == 1_901
        and snapshot.get("aggregateZipBytes") == 24_116_911
        and snapshot.get("aggregateZipEntryCount") == 5_936
        and snapshot.get("aggregateZipUncompressedBytes") == 87_874_800
        and snapshot.get("acquisitionReceipt", {}).get("rawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_RECEIPT_PATH]
        and snapshot.get("acquisitionManifest", {}).get("rawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_MANIFEST_PATH]
        and snapshot.get("acquisitionClaim", {}).get("rawSha256")
        == WAVE4_ACQUISITION_CLAIM_SHA256
        and snapshot.get("evidence", {}).get("rawSha256")
        == WAVE4_EVIDENCE_SHA256
        and snapshot.get("identityBindings", {}).get(
            "compactIdentitySha256"
        )
        == WAVE4_COMPACT_IDENTITY_SHA256
        and snapshot.get("identityBindings", {}).get("fullWitnessSha256")
        == WAVE4_FULL_WITNESS_SHA256
        and snapshot.get("identityBindings", {}).get(
            "heldSourceBindingsSha256"
        )
        == WAVE4_HELD_SOURCE_BINDINGS_SHA256
        and snapshot.get("identityBindings", {}).get(
            "sourceRequestSetCanonicalSha256"
        )
        == WAVE4_SOURCE_REQUEST_SET_SHA256
        and type(readback_authority) is dict
        and readback_authority == WAVE4_READBACK_AUTHORITY,
        "E_WAVE4_READBACK_PERMIT",
    )
    accepted = snapshot.get("acceptedDirectory")
    accepted_files = accepted.get("files") if type(accepted) is dict else None
    check(
        type(accepted) is dict
        and accepted.get("path") == WAVE4_ACCEPTED_DIRECTORY
        and accepted.get("exactFileCount") == 32
        and type(accepted_files) is list
        and len(accepted_files) == 32,
        "E_WAVE4_READBACK_PERMIT",
    )

    verified = readback.get("verified")
    check(
        readback.get("status") == "wave4_acquisition_independently_read_back"
        and readback.get("acquisitionAttemptId") == WAVE4_ATTEMPT_ID
        and readback.get("readbackAttemptId") == WAVE4_READBACK_ATTEMPT_ID
        and readback.get("offline") is True
        and readback.get("externalAuthenticationRequired") is False
        and readback.get("userActionRequired") is False
        and readback.get("networkRequestAttemptCount") == 0
        and readback.get("sourceAcquisitionCount") == 0
        and readback.get("verificationPassCount") == 2
        and type(verified) is dict
        and verified.get("status")
        == "wave4_acquisition_independently_verified"
        and verified.get("acquisitionAttemptId") == WAVE4_ATTEMPT_ID
        and verified.get("authorityFileCount") == 12
        and verified.get("acceptedResourceCount") == 32
        and verified.get("selectedTupleCount") == 3
        and verified.get("modCount") == 16
        and verified.get("zipCount") == 16
        and verified.get("aggregateAcceptedBytes") == 24_118_812
        and verified.get("aggregateModBytes") == 1_901
        and verified.get("aggregateZipBytes") == 24_116_911
        and verified.get("aggregateZipEntryCount") == 5_936
        and verified.get("aggregateZipUncompressedBytes") == 87_874_800
        and verified.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE4_RESOURCE_SET_SHA256
        and verified.get("acquisitionClaimRawSha256")
        == WAVE4_ACQUISITION_CLAIM_SHA256
        and verified.get("evidenceRawSha256") == WAVE4_EVIDENCE_SHA256
        and verified.get("acquisitionReceiptRawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_RECEIPT_PATH]
        and verified.get("acquisitionManifestRawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_MANIFEST_PATH]
        and verified.get("decisionContentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_IDENTITY_DECISION_PATH]
        and verified.get("permitContentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_PERMIT_PATH]
        and verified.get("compactIdentitySha256")
        == WAVE4_COMPACT_IDENTITY_SHA256
        and verified.get("fullWitnessSha256")
        == WAVE4_FULL_WITNESS_SHA256
        and verified.get("heldSourceBindingsSha256")
        == WAVE4_HELD_SOURCE_BINDINGS_SHA256
        and verified.get("sourceRequestSetCanonicalSha256")
        == WAVE4_SOURCE_REQUEST_SET_SHA256
        and verified.get("failureAbsent") is True
        and verified.get("stagingAbsent") is True
        and verified.get("sourceExtracted") is False
        and verified.get("sourceLoadedOrExecuted") is False
        and verified.get("compiled") is False
        and verified.get("externalAuthenticationRequired") is False
        and verified.get("userActionRequired") is False,
        "E_WAVE4_READBACK",
    )
    authority_binding = readback.get("authorityBinding")
    manifest_authority = readback_manifest.get("authorityBinding")
    check(
        authority_binding == manifest_authority
        and type(authority_binding) is dict
        and authority_binding.get("permit", {}).get("path")
        == WAVE4_READBACK_PERMIT_PATH
        and authority_binding.get("permit", {}).get("rawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_READBACK_PERMIT_PATH]
        and authority_binding.get("permit", {}).get("contentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_READBACK_PERMIT_PATH]
        and authority_binding.get("checker", {}).get("rawSha256")
        == WAVE4_READBACK_CHECKER_SHA256
        and authority_binding.get("checker", {}).get("path")
        == (
            "script/check_p2p_nat_g2_pion_rung3_dependency_"
            "wave4_readback_execution_permit_v1.py"
        )
        and authority_binding.get("recorder", {}).get("rawSha256")
        == WAVE4_READBACK_RECORDER_SHA256
        and authority_binding.get("recorder", {}).get("path")
        == (
            "script/record_p2p_nat_g2_pion_rung3_dependency_"
            "wave4_readback_v1_once.py"
        ),
        "E_WAVE4_READBACK",
    )
    check(
        readback_manifest.get("status")
        == "wave4_acquisition_readback_publication_complete"
        and readback_manifest.get("acquisitionAttemptId") == WAVE4_ATTEMPT_ID
        and readback_manifest.get("readbackAttemptId")
        == WAVE4_READBACK_ATTEMPT_ID
        and readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("allRequiredPublicationBarriersCompleted")
        is True
        and readback_manifest.get("offline") is True
        and readback_manifest.get("externalAuthenticationRequired") is False
        and readback_manifest.get("userActionRequired") is False
        and readback_manifest.get("networkRequestAttemptCount") == 0
        and readback_manifest.get("sourceAcquisitionCount") == 0
        and readback_manifest.get("receipt", {}).get("path")
        == WAVE4_READBACK_PATH
        and readback_manifest.get("receipt", {}).get("rawSha256")
        == WAVE4_CONTROL_SHA256[WAVE4_READBACK_PATH]
        and readback_manifest.get("receipt", {}).get("contentSha256")
        == WAVE4_CONTENT_SHA256[WAVE4_READBACK_PATH],
        "E_WAVE4_READBACK_MANIFEST",
    )

    accepted_by_name = {
        PurePosixPath(row.get("path", "")).name: row
        for row in accepted_files
        if type(row) is dict
    }
    verified_rows = verified.get("resources")
    verified_by_name = {
        row.get("acceptedFileName"): row
        for row in verified_rows
        if type(row) is dict
    } if type(verified_rows) is list else {}
    check(
        len(accepted_by_name) == 32
        and type(verified_rows) is list
        and len(verified_rows) == 32
        and len(verified_by_name) == 32,
        "E_WAVE4_RESOURCE",
    )

    result: list[dict[str, Any]] = []
    tuple_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    aggregate_bytes = 0
    aggregate_mod_bytes = 0
    aggregate_zip_bytes = 0
    aggregate_zip_entries = 0
    aggregate_zip_uncompressed = 0
    for index, value in enumerate(resources, 1):
        tuple_order = (index + 1) // 2
        expected_kind = "mod" if index % 2 else "zip"
        source_value = source_requests[index - 1]
        identity_tuple = identity_tuples[tuple_order - 1]
        check(
            type(value) is dict
            and value.get("requestOrdinal") == index
            and value.get("tupleOrder") == tuple_order
            and value.get("kind") == expected_kind
            and type(value.get("module")) is str
            and type(value.get("version")) is str
            and type(value.get("tupleId")) is str
            and type(value.get("acceptedFileName")) is str
            and "/" not in value["acceptedFileName"]
            and value.get("tupleDigestSha256")
            == sha256_bytes(
                f"{value['module']}\n{value['version']}\n".encode("utf-8")
            )
            and value.get("tupleId")
            == (
                f"wave4-{tuple_order:03d}-"
                f"{value['tupleDigestSha256'][:12]}"
            )
            and value.get("host") == "proxy.golang.org"
            and value.get("port") == 443
            and value.get("maximumResponseBodyBytes")
            == (1_048_576 if expected_kind == "mod" else 16_777_216)
            and type(source_value) is dict
            and source_value.get("requestOrdinal") == index
            and source_value.get("tupleOrder") == tuple_order
            and source_value.get("resourceKind") == expected_kind
            and source_value.get("module") == value["module"]
            and source_value.get("version") == value["version"]
            and source_value.get("acceptedFileName")
            == value["acceptedFileName"]
            and source_value.get("url") == value["url"]
            and source_value.get("expectedH1") == value["expectedH1"]
            and source_value.get("selectedByGraphAlgorithm")
            == value.get("selectedByGraphAlgorithm")
            and type(identity_tuple) is dict
            and identity_tuple.get("tupleOrder") == tuple_order
            and identity_tuple.get("module") == value["module"]
            and identity_tuple.get("version") == value["version"]
            and identity_tuple.get("selectedByGraphAlgorithm")
            == value.get("selectedByGraphAlgorithm"),
            "E_WAVE4_RESOURCE",
        )
        accepted_row = accepted_by_name.get(value["acceptedFileName"])
        verified_row = verified_by_name.get(value["acceptedFileName"])
        check(
            type(accepted_row) is dict
            and type(verified_row) is dict
            and accepted_row.get("path")
            == f"{WAVE4_ACCEPTED_DIRECTORY}/{value['acceptedFileName']}"
            and accepted_row.get("mode") == "0600"
            and accepted_row.get("linkCount") == 1
            and type(accepted_row.get("bytes")) is int
            and accepted_row["bytes"] > 0
            and verified_row.get("requestOrdinal") == index
            and verified_row.get("tupleId") == value["tupleId"]
            and verified_row.get("kind") == value["kind"]
            and verified_row.get("url") == value["url"]
            and verified_row.get("verifiedH1") == value["expectedH1"]
            and verified_row.get("byteCount") == accepted_row["bytes"]
            and verified_row.get("rawSha256")
            == accepted_row.get("rawSha256"),
            "E_WAVE4_RESOURCE",
        )
        byte_count = accepted_row["bytes"]
        aggregate_bytes += byte_count
        if value["kind"] == "mod":
            aggregate_mod_bytes += byte_count
        else:
            entry_count = verified_row.get("entryCount")
            uncompressed = verified_row.get("uncompressedBytes")
            check(
                type(entry_count) is int
                and entry_count > 0
                and type(uncompressed) is int
                and uncompressed > 0,
                "E_WAVE4_RESOURCE",
            )
            aggregate_zip_bytes += byte_count
            aggregate_zip_entries += entry_count
            aggregate_zip_uncompressed += uncompressed
        row = {
            "wave": "wave4",
            "path": accepted_row["path"],
            "rawSha256": accepted_row["rawSha256"],
            "maximumBytes": accepted_row["bytes"],
            "ownerOnly": True,
            "kind": value["kind"],
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 50 + value["tupleOrder"],
            "order": index,
        }
        if value["kind"] == "zip":
            row["modulePrefix"] = (
                f"{runner.go_proxy_escape(value['module'])}@"
                f"{runner.go_proxy_escape(value['version'])}/"
            )
        tuple_rows[value["tupleId"]].append(row)
        result.append(row)
    check(
        len(tuple_rows) == 16
        and all(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len({(row["module"], row["version"]) for row in rows}) == 1
            for rows in tuple_rows.values()
        ),
        "E_WAVE4_RESOURCE",
    )
    check(
        aggregate_bytes == 24_118_812
        and aggregate_mod_bytes == 1_901
        and aggregate_zip_bytes == 24_116_911
        and aggregate_mod_bytes + aggregate_zip_bytes == aggregate_bytes
        and aggregate_zip_entries == 5_936
        and aggregate_zip_uncompressed == 87_874_800,
        "E_WAVE4_AGGREGATE",
    )
    return result


def wave5_control_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": JSON_MAXIMUM_BYTES,
            "ownerOnly": False,
            "kind": "terminal_evidence",
        }
        for path, digest in WAVE5_CONTROL_SHA256.items()
    ]


def parse_wave5_documents(
    runner: types.ModuleType,
    held: Any,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in WAVE5_CONTROL_SHA256:
        value = runner.strict_json(held.raw[path], path)
        check(type(value) is dict, "E_WAVE5_JSON")
        result[path] = value
    return result


def verify_wave5_content_bindings(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> None:
    verify_modern_content_binding(
        runner,
        documents[WAVE5_IDENTITY_DECISION_PATH],
        WAVE5_CONTENT_SHA256[WAVE5_IDENTITY_DECISION_PATH],
        "decision_without_contentBinding",
    )
    verify_modern_content_binding(
        runner,
        documents[WAVE5_PERMIT_PATH],
        WAVE5_CONTENT_SHA256[WAVE5_PERMIT_PATH],
        "permit_without_contentBinding",
    )
    for path in (
        WAVE5_READBACK_PERMIT_PATH,
        WAVE5_READBACK_PATH,
        WAVE5_READBACK_MANIFEST_PATH,
    ):
        verify_content_binding(
            runner,
            documents[path],
            WAVE5_CONTENT_SHA256[path],
        )


def wave5_request_resources(
    runner: types.ModuleType,
    documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    identity = documents[WAVE5_IDENTITY_DECISION_PATH]
    permit = documents[WAVE5_PERMIT_PATH]
    receipt = documents[WAVE5_RECEIPT_PATH]
    manifest = documents[WAVE5_MANIFEST_PATH]
    readback_permit = documents[WAVE5_READBACK_PERMIT_PATH]
    readback = documents[WAVE5_READBACK_PATH]
    readback_manifest = documents[WAVE5_READBACK_MANIFEST_PATH]
    verify_wave5_content_bindings(runner, documents)

    resolution = identity.get("identityResolution")
    held_set = identity.get("heldSourceInputSet")
    preparation = identity.get("sourceAcquisitionPreparation")
    predecessors = identity.get("predecessorBindings")
    predecessor = (
        predecessors.get("combinedFixedPointV3")
        if type(predecessors) is dict else None
    )
    wave5_candidate = (
        predecessors.get("wave5Candidate")
        if type(predecessors) is dict else None
    )
    check(
        identity.get("status")
        == (
            "wave5_exact_15_frontier_identity_classified_15_complete_"
            "0_blocked_acquisition_ready_not_authorized"
        )
        and type(resolution) is dict
        and resolution.get("tupleCount") == 15
        and resolution.get("completeIdentityPairCount") == 15
        and resolution.get("blockedTupleCount") == 0
        and resolution.get("graphSelectedTupleCount") == 0
        and resolution.get("versionSpecificNonSelectedTupleCount") == 15
        and resolution.get("compactIdentitySha256")
        == WAVE5_COMPACT_IDENTITY_SHA256
        and resolution.get("fullWitnessSha256")
        == WAVE5_FULL_WITNESS_SHA256
        and type(held_set) is dict
        and held_set.get("sourceBindingCount") == 133
        and held_set.get("sourceBindingsSha256")
        == WAVE5_HELD_SOURCE_BINDINGS_SHA256
        and type(preparation) is dict
        and preparation.get("acquisitionReady") is True
        and preparation.get("acquisitionAuthorizedByThisDecision") is False
        and preparation.get("requestCount") == 30
        and preparation.get("requestOrder")
        == "tuple_order_ascending_mod_then_zip"
        and preparation.get("acceptedDirectoryPath")
        == WAVE5_ACCEPTED_DIRECTORY
        and type(predecessor) is dict
        and predecessor.get("contentSha256")
        == WAVE5_PREDECESSOR_CONTENT_SHA256
        and predecessor.get("combinedInputSetSha256")
        == WAVE5_PREDECESSOR_INPUT_SET_SHA256
        and predecessor.get("graphSha256")
        == WAVE5_PREDECESSOR_GRAPH_SHA256
        and predecessor.get("frontierSha256")
        == WAVE5_PREDECESSOR_FRONTIER_SHA256
        and predecessor.get("fixedPointReached") is False
        and type(wave5_candidate) is dict
        and wave5_candidate.get("checkerRawSha256")
        == WAVE5_CANDIDATE_CHECKER_SHA256
        and wave5_candidate.get("testsRawSha256")
        == WAVE5_CANDIDATE_TEST_SHA256
        and wave5_candidate.get("contentSha256")
        == WAVE5_CANDIDATE_CONTENT_SHA256
        and wave5_candidate.get("tupleCount") == 15,
        "E_WAVE5_IDENTITY",
    )
    identity_tuples = resolution.get("tuples")
    source_requests = preparation.get("requestSet")
    check(
        type(identity_tuples) is list
        and len(identity_tuples) == 15
        and all(
            type(row) is dict
            and row.get("selectedByGraphAlgorithm") is False
            for row in identity_tuples
        )
        and type(source_requests) is list
        and len(source_requests) == 30
        and sha256_bytes(runner.canonical_json_bytes(source_requests))
        == WAVE5_SOURCE_REQUEST_SET_SHA256,
        "E_WAVE5_IDENTITY",
    )

    decision_binding = permit.get("decisionBinding")
    identity_binding = permit.get("identityBinding")
    request_contract = permit.get("requestContract")
    resources = (
        request_contract.get("resources")
        if type(request_contract) is dict else None
    )
    check(
        permit.get("status") == "authorized_not_consumed"
        and type(decision_binding) is dict
        and decision_binding.get("path") == WAVE5_IDENTITY_DECISION_PATH
        and decision_binding.get("rawSha256")
        == WAVE5_CONTROL_SHA256[WAVE5_IDENTITY_DECISION_PATH]
        and decision_binding.get("contentSha256")
        == WAVE5_CONTENT_SHA256[WAVE5_IDENTITY_DECISION_PATH]
        and type(identity_binding) is dict
        and identity_binding.get("compactIdentitySha256")
        == WAVE5_COMPACT_IDENTITY_SHA256
        and identity_binding.get("fullWitnessSha256")
        == WAVE5_FULL_WITNESS_SHA256
        and identity_binding.get("heldSourceBindingsSha256")
        == WAVE5_HELD_SOURCE_BINDINGS_SHA256
        and identity_binding.get("completeTupleCount") == 15
        and identity_binding.get("blockedTupleCount") == 0
        and permit.get("authority") == WAVE5_ACQUISITION_AUTHORITY
        and type(request_contract) is dict
        and request_contract.get("requestCount") == 30
        and request_contract.get("tupleCount") == 15
        and request_contract.get("order")
        == "tuple_order_ascending_mod_then_zip"
        and request_contract.get("sourceRequestSetCanonicalSha256")
        == WAVE5_SOURCE_REQUEST_SET_SHA256
        and request_contract.get("resourcesCanonicalSha256")
        == WAVE5_PERMIT_RESOURCES_SHA256
        and type(resources) is list
        and len(resources) == 30
        and sha256_bytes(runner.canonical_json_bytes(resources))
        == WAVE5_PERMIT_RESOURCES_SHA256,
        "E_WAVE5_PERMIT",
    )
    check(
        receipt.get("status")
        == "consumed_success_pending_independent_readback"
        and receipt.get("attemptId") == WAVE5_ATTEMPT_ID
        and receipt.get("acceptedResourceCount") == 30
        and receipt.get("modCount") == 15
        and receipt.get("zipCount") == 15
        and receipt.get("aggregateResponseBytes") == 26_123_889
        and receipt.get("aggregateModResponseBytes") == 1_697
        and receipt.get("aggregateZipResponseBytes") == 26_122_192
        and receipt.get("aggregateZipEntryCount") == 6_038
        and receipt.get("aggregateZipUncompressedBytes") == 101_774_573
        and receipt.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE5_RESOURCE_SET_SHA256
        and receipt.get("decisionContentSha256")
        == WAVE5_CONTENT_SHA256[WAVE5_IDENTITY_DECISION_PATH]
        and receipt.get("permitContentSha256")
        == WAVE5_CONTENT_SHA256[WAVE5_PERMIT_PATH]
        and receipt.get("claimRawSha256")
        == WAVE5_ACQUISITION_CLAIM_SHA256
        and receipt.get("acceptedEvidenceRawSha256")
        == WAVE5_EVIDENCE_SHA256
        and receipt.get("checkerRawSha256")
        == WAVE5_ACQUISITION_CHECKER_SHA256
        and receipt.get("runnerRawSha256")
        == WAVE5_ACQUISITION_RUNNER_SHA256
        and receipt.get("sourceAcquired") is True
        and receipt.get("sourceExtracted") is False
        and receipt.get("sourceLoadedOrExecuted") is False
        and receipt.get("compiled") is False
        and receipt.get("externalAuthenticationRequired") is False
        and receipt.get("userActionRequired") is False,
        "E_WAVE5_RECEIPT",
    )
    check(
        manifest.get("status")
        == "consumed_success_pending_independent_readback"
        and manifest.get("attemptId") == WAVE5_ATTEMPT_ID
        and manifest.get("manifestWrittenLast") is True
        and manifest.get("receiptPath") == WAVE5_RECEIPT_PATH
        and manifest.get("receiptRawSha256")
        == WAVE5_CONTROL_SHA256[WAVE5_RECEIPT_PATH],
        "E_WAVE5_MANIFEST",
    )

    snapshot = readback_permit.get("frozenAcquisitionSnapshot")
    accepted = snapshot.get("acceptedDirectory") if type(snapshot) is dict else None
    accepted_files = accepted.get("files") if type(accepted) is dict else None
    check(
        readback_permit.get("status") == "authorized_not_consumed"
        and readback_permit.get("authority") == WAVE5_READBACK_AUTHORITY
        and type(snapshot) is dict
        and snapshot.get("attemptId") == WAVE5_ATTEMPT_ID
        and snapshot.get("frozenFileCount") == 46
        and snapshot.get("frozenFilesCanonicalSha256")
        == WAVE5_FROZEN_FILE_SET_SHA256
        and snapshot.get("acceptedResourceCount") == 30
        and snapshot.get("selectedTupleCount") == 0
        and snapshot.get("modCount") == 15
        and snapshot.get("zipCount") == 15
        and snapshot.get("aggregateAcceptedBytes") == 26_123_889
        and snapshot.get("aggregateModBytes") == 1_697
        and snapshot.get("aggregateZipBytes") == 26_122_192
        and snapshot.get("aggregateZipEntryCount") == 6_038
        and snapshot.get("aggregateZipUncompressedBytes") == 101_774_573
        and snapshot.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE5_RESOURCE_SET_SHA256
        and snapshot.get("acquisitionReceipt", {}).get("rawSha256")
        == WAVE5_CONTROL_SHA256[WAVE5_RECEIPT_PATH]
        and snapshot.get("acquisitionManifest", {}).get("rawSha256")
        == WAVE5_CONTROL_SHA256[WAVE5_MANIFEST_PATH]
        and snapshot.get("acquisitionClaim", {}).get("rawSha256")
        == WAVE5_ACQUISITION_CLAIM_SHA256
        and snapshot.get("evidence", {}).get("rawSha256")
        == WAVE5_EVIDENCE_SHA256
        and type(accepted) is dict
        and accepted.get("path") == WAVE5_ACCEPTED_DIRECTORY
        and accepted.get("exactFileCount") == 30
        and type(accepted_files) is list
        and len(accepted_files) == 30,
        "E_WAVE5_READBACK_PERMIT",
    )

    verified = readback.get("verified")
    readback_claim = readback.get("readbackClaim")
    check(
        readback.get("status")
        == "wave5_acquisition_retained_snapshot_independently_read_back"
        and readback.get("acquisitionAttemptId") == WAVE5_ATTEMPT_ID
        and readback.get("readbackAttemptId") == WAVE5_READBACK_ATTEMPT_ID
        and readback.get("offline") is True
        and readback.get("externalAuthenticationRequired") is False
        and readback.get("userActionRequired") is False
        and readback.get("networkRequestAttemptCount") == 0
        and readback.get("sourceAcquisitionCount") == 0
        and readback.get("verificationPassCount") == 2
        and readback.get("completionAppliesToRetainedSnapshot") is True
        and readback.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and readback.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and readback.get("allRequiredPreManifestBarriersRequired") is True
        and readback.get("allRequiredPreManifestBarriersCompleteAtReceipt")
        is False
        and readback.get("completedRetainedFdPreManifestBarrierCountAtReceipt")
        == 1
        and readback.get("remainingRetainedFdPreManifestBarrierCount") == 2
        and readback.get("requiredRetainedFdPreManifestBarrierCount") == 3
        and type(readback_claim) is dict
        and readback_claim.get("path")
        == (
            "build/offline-source/pion-ice-v4.3.0/dependencies/"
            ".wave-5-v1-readback.claim"
        )
        and readback_claim.get("rawSha256")
        == WAVE5_READBACK_CLAIM_SHA256
        and readback_claim.get("contentSha256")
        == WAVE5_READBACK_CLAIM_CONTENT_SHA256
        and readback_claim.get("mode") == "0600"
        and readback_claim.get("linkCount") == 1
        and type(verified) is dict
        and verified.get("status")
        == "wave5_acquisition_retained_snapshot_independently_verified"
        and verified.get("acceptedResourceCount") == 30
        and verified.get("selectedTupleCount") == 0
        and verified.get("acceptedResourceHashSetCanonicalSha256")
        == WAVE5_RESOURCE_SET_SHA256
        and verified.get("acquisitionClaimRawSha256")
        == WAVE5_ACQUISITION_CLAIM_SHA256
        and verified.get("evidenceRawSha256") == WAVE5_EVIDENCE_SHA256
        and verified.get("sourceExtracted") is False
        and verified.get("sourceLoadedOrExecuted") is False
        and verified.get("compiled") is False,
        "E_WAVE5_READBACK",
    )
    authority_binding = readback.get("authorityBinding")
    check(
        authority_binding == readback_manifest.get("authorityBinding")
        and type(authority_binding) is dict
        and authority_binding.get("permit", {}).get("path")
        == WAVE5_READBACK_PERMIT_PATH
        and authority_binding.get("permit", {}).get("rawSha256")
        == WAVE5_CONTROL_SHA256[WAVE5_READBACK_PERMIT_PATH]
        and authority_binding.get("permit", {}).get("contentSha256")
        == WAVE5_CONTENT_SHA256[WAVE5_READBACK_PERMIT_PATH]
        and authority_binding.get("checker", {}).get("rawSha256")
        == WAVE5_READBACK_CHECKER_SHA256
        and authority_binding.get("checker", {}).get("path")
        == (
            "script/check_p2p_nat_g2_pion_rung3_dependency_"
            "wave5_readback_execution_permit_v1.py"
        )
        and authority_binding.get("recorder", {}).get("rawSha256")
        == WAVE5_READBACK_RECORDER_SHA256
        and authority_binding.get("recorder", {}).get("path")
        == (
            "script/record_p2p_nat_g2_pion_rung3_dependency_"
            "wave5_readback_v1_once.py"
        ),
        "E_WAVE5_READBACK",
    )
    check(
        readback_manifest.get("status")
        == (
            "wave5_acquisition_retained_snapshot_readback_"
            "publication_complete"
        )
        and readback_manifest.get("acquisitionAttemptId")
        == WAVE5_ATTEMPT_ID
        and readback_manifest.get("readbackAttemptId")
        == WAVE5_READBACK_ATTEMPT_ID
        and readback_manifest.get("manifestWrittenLast") is True
        and readback_manifest.get("allRequiredPreManifestBarriersCompleted")
        is True
        and readback_manifest.get(
            "completedPreManifestCurrentPathIdentityBarrierCount"
        ) == 3
        and readback_manifest.get("lastCurrentPathIdentityBarrierTiming")
        == "immediately_before_manifest_publication"
        and readback_manifest.get("completionAppliesToRetainedSnapshot")
        is True
        and readback_manifest.get(
            "currentPathIdentityGuaranteedThroughManifestPublication"
        ) is False
        and readback_manifest.get(
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented"
        ) is False
        and readback_manifest.get("receipt", {}).get("path")
        == WAVE5_READBACK_PATH
        and readback_manifest.get("receipt", {}).get("rawSha256")
        == WAVE5_CONTROL_SHA256[WAVE5_READBACK_PATH]
        and readback_manifest.get("receipt", {}).get("contentSha256")
        == WAVE5_CONTENT_SHA256[WAVE5_READBACK_PATH],
        "E_WAVE5_READBACK_MANIFEST",
    )

    accepted_by_name = {
        PurePosixPath(row.get("path", "")).name: row
        for row in accepted_files if type(row) is dict
    }
    verified_rows = verified.get("resources")
    verified_by_name = {
        row.get("acceptedFileName"): row
        for row in verified_rows if type(row) is dict
    } if type(verified_rows) is list else {}
    check(
        len(accepted_by_name) == 30
        and type(verified_rows) is list
        and len(verified_rows) == 30
        and len(verified_by_name) == 30,
        "E_WAVE5_RESOURCE",
    )
    result: list[dict[str, Any]] = []
    tuple_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    totals = {"all": 0, "mod": 0, "zip": 0, "entries": 0, "expanded": 0}
    for index, value in enumerate(resources, 1):
        tuple_order = (index + 1) // 2
        expected_kind = "mod" if index % 2 else "zip"
        source_value = source_requests[index - 1]
        identity_tuple = identity_tuples[tuple_order - 1]
        check(
            type(value) is dict
            and value.get("requestOrdinal") == index
            and value.get("tupleOrder") == tuple_order
            and value.get("kind") == expected_kind
            and value.get("tupleId")
            == (
                f"wave5-{tuple_order:03d}-"
                f"{value.get('tupleDigestSha256', '')[:12]}"
            )
            and value.get("tupleDigestSha256")
            == sha256_bytes(
                f"{value.get('module')}\n{value.get('version')}\n".encode()
            )
            and type(source_value) is dict
            and source_value.get("requestOrdinal") == index
            and source_value.get("tupleOrder") == tuple_order
            and source_value.get("resourceKind") == expected_kind
            and source_value.get("module") == value.get("module")
            and source_value.get("version") == value.get("version")
            and source_value.get("url") == value.get("url")
            and source_value.get("expectedH1") == value.get("expectedH1")
            and source_value.get("selectedByGraphAlgorithm") is False
            and value.get("selectedByGraphAlgorithm") is False
            and type(identity_tuple) is dict
            and identity_tuple.get("tupleOrder") == tuple_order
            and identity_tuple.get("module") == value.get("module")
            and identity_tuple.get("version") == value.get("version")
            and identity_tuple.get("selectedByGraphAlgorithm") is False,
            "E_WAVE5_RESOURCE",
        )
        accepted_row = accepted_by_name.get(value.get("acceptedFileName"))
        verified_row = verified_by_name.get(value.get("acceptedFileName"))
        check(
            type(accepted_row) is dict
            and accepted_row.get("path")
            == f"{WAVE5_ACCEPTED_DIRECTORY}/{value.get('acceptedFileName')}"
            and accepted_row.get("mode") == "0600"
            and accepted_row.get("linkCount") == 1
            and type(accepted_row.get("bytes")) is int
            and accepted_row["bytes"] > 0
            and type(verified_row) is dict
            and verified_row.get("requestOrdinal") == index
            and verified_row.get("tupleId") == value.get("tupleId")
            and verified_row.get("kind") == expected_kind
            and verified_row.get("url") == value.get("url")
            and verified_row.get("verifiedH1") == value.get("expectedH1")
            and verified_row.get("byteCount") == accepted_row["bytes"]
            and verified_row.get("rawSha256")
            == accepted_row.get("rawSha256"),
            "E_WAVE5_RESOURCE",
        )
        totals["all"] += accepted_row["bytes"]
        totals[expected_kind] += accepted_row["bytes"]
        if expected_kind == "zip":
            totals["entries"] += verified_row.get("entryCount", -1)
            totals["expanded"] += verified_row.get("uncompressedBytes", -1)
        row = {
            "wave": "wave5",
            "path": accepted_row["path"],
            "rawSha256": accepted_row["rawSha256"],
            "maximumBytes": accepted_row["bytes"],
            "ownerOnly": True,
            "kind": expected_kind,
            "module": value["module"],
            "version": value["version"],
            "tupleId": value["tupleId"],
            "tupleOrder": 66 + tuple_order,
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
        len(tuple_rows) == 15
        and all(
            len(rows) == 2
            and {row["kind"] for row in rows} == {"mod", "zip"}
            and len({(row["module"], row["version"]) for row in rows}) == 1
            for rows in tuple_rows.values()
        )
        and totals == {
            "all": 26_123_889,
            "mod": 1_697,
            "zip": 26_122_192,
            "entries": 6_038,
            "expanded": 101_774_573,
        },
        "E_WAVE5_AGGREGATE",
    )
    return result


def exact_lowercase_testdata_component(relative: str) -> bool:
    parts = relative.split("/")
    return any(part == "testdata" for part in parts[:-1])


def inspect_zip_bytes_v3(
    runner: types.ModuleType,
    raw: bytes,
    binding: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> dict[str, Any]:
    """The v1 archive inspection with one pre-parse testdata exclusion."""

    tuple_id = binding.get("tupleId")
    tuple_order = binding.get("tupleOrder")
    kind = binding.get("kind")
    maximum_archive = runner.exact_int(
        limits.get("maximumArchiveBytes", runner.DEFAULT_MAXIMUM_ARCHIVE_BYTES),
        minimum=1,
    )
    runner.require(
        len(raw) <= maximum_archive and runner._eocd_exact(raw),
        "E_ARCHIVE_BOUND",
        "archive",
        tuple_id=tuple_id if type(tuple_id) is str else None,
        tuple_order=tuple_order if type(tuple_order) is int else None,
        resource_kind=kind if type(kind) is str else None,
    )
    expected_prefix = binding.get("modulePrefix")
    runner.require(
        type(expected_prefix) is str and expected_prefix.endswith("/"),
        "E_MODULE_IDENTITY",
        "archive",
    )
    max_entries = runner.exact_int(
        limits.get(
            "maximumEntriesPerArchive",
            runner.DEFAULT_MAXIMUM_ENTRIES_PER_ARCHIVE,
        ),
        minimum=1,
    )
    max_file = runner.exact_int(
        limits.get(
            "maximumSingleFileBytes",
            runner.DEFAULT_MAXIMUM_ENTRY_BYTES,
        ),
        minimum=1,
    )
    entries: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    licenses: list[dict[str, Any]] = []
    special: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    names: set[str] = set()
    folded: set[str] = set()
    total_uncompressed = 0
    embedded_mod: bytes | None = None
    try:
        with runner.zipfile.ZipFile(
            runner.io.BytesIO(raw),
            mode="r",
            allowZip64=False,
        ) as archive:
            infos = archive.infolist()
            runner.require(
                0 < len(infos) <= max_entries,
                "E_ARCHIVE_BOUND",
                "archive",
            )
            runner.require(
                min(info.header_offset for info in infos) == 0,
                "E_ARCHIVE_STRUCTURE",
                "archive",
            )
            for info in infos:
                name = runner.safe_archive_name(info.filename, expected_prefix)
                relative = name[len(expected_prefix) :]
                folded_name = name.casefold()
                runner.require(
                    name not in names and folded_name not in folded,
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                names.add(name)
                folded.add(folded_name)
                runner.require(
                    not (info.flag_bits & 0x1)
                    and info.compress_type
                    in {runner.zipfile.ZIP_STORED, runner.zipfile.ZIP_DEFLATED}
                    and not runner.has_zip64_extra(info.extra),
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                mode = (info.external_attr >> 16) & 0xFFFF
                runner.require(
                    mode == 0 or stat.S_ISREG(mode),
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                runner.require(
                    0 <= info.file_size <= max_file,
                    "E_ARCHIVE_BOUND",
                    "archive",
                )
                total_uncompressed += info.file_size
                payload = archive.read(info)
                runner.require(
                    len(payload) == info.file_size,
                    "E_ARCHIVE_STRUCTURE",
                    "archive",
                )
                row = {
                    "relativePath": relative,
                    "rawByteSize": len(payload),
                    "rawSha256": sha256_bytes(payload),
                }
                entries.append(row)
                if relative == "go.mod":
                    embedded_mod = payload
                if relative.endswith(".go"):
                    source_class = runner.source_class(relative)
                    if exact_lowercase_testdata_component(relative):
                        sources.append(
                            {
                                **row,
                                "sourceClass": source_class,
                                "buildExpression": None,
                                "imports": [],
                                "semanticParsingPerformed": False,
                                "graphExclusionReason": (
                                    "exact_lowercase_testdata_directory_"
                                    "component"
                                ),
                            }
                        )
                        exclusions.append(dict(row))
                    else:
                        try:
                            text = payload.decode("utf-8", errors="strict")
                        except UnicodeDecodeError as error:
                            raise runner.ReviewFailure(
                                "E_IMPORT_PARSE",
                                "source_inventory",
                                tuple_id=(
                                    tuple_id
                                    if type(tuple_id) is str
                                    else None
                                ),
                            ) from error
                        sources.append(
                            {
                                **row,
                                "sourceClass": source_class,
                                "buildExpression":
                                    runner.extract_build_expression(text),
                                "imports": runner.parse_go_imports(text),
                                "semanticParsingPerformed": True,
                                "graphExclusionReason": None,
                            }
                        )
                if runner.is_license_path(relative):
                    licenses.append(row)
                classes = runner.special_classes(relative, payload)
                if classes:
                    special.append({**row, "classes": classes})
    except runner.ReviewFailure as error:
        raise runner.ReviewFailure(
            error.code,
            error.phase,
            tuple_id=(
                error.tuple_id
                if error.tuple_id is not None
                else (tuple_id if type(tuple_id) is str else None)
            ),
            tuple_order=(
                error.tuple_order
                if error.tuple_order is not None
                else (tuple_order if type(tuple_order) is int else None)
            ),
            resource_kind=(
                error.resource_kind
                if error.resource_kind is not None
                else (kind if type(kind) is str else None)
            ),
            observations=error.observations,
        ) from error
    except (
        runner.zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
    ) as error:
        raise runner.ReviewFailure(
            "E_ARCHIVE_STRUCTURE",
            "archive",
            tuple_id=tuple_id if type(tuple_id) is str else None,
            tuple_order=tuple_order if type(tuple_order) is int else None,
            resource_kind=kind if type(kind) is str else None,
        ) from error
    return {
        "module": binding.get("module"),
        "version": binding.get("version"),
        "tupleId": tuple_id,
        "tupleOrder": tuple_order,
        "modulePrefix": expected_prefix,
        "entryCount": len(entries),
        "uncompressedByteCount": total_uncompressed,
        "entrySetSha256": sha256_bytes(runner.canonical_json_bytes(entries)),
        "sources": sources,
        "licenses": licenses,
        "special": special,
        "embeddedGoMod": embedded_mod,
        "testdataSemanticExclusions": exclusions,
    }


def reconstruct_graph_v3(
    runner: types.ModuleType,
    permit: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    held: Any,
    limits: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata_rows: list[dict[str, Any]] = []
    archive_rows: list[dict[str, Any]] = []
    pairs: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    aggregate_entries = 0
    aggregate_uncompressed = 0
    go_source_files = 0
    exclusions: list[dict[str, Any]] = []
    for binding in bindings:
        kind = binding["kind"]
        if kind in {"mod", "zip"}:
            pairs[binding["tupleId"]][kind] = binding
        if kind == "mod":
            metadata_rows.append(
                {
                    "tupleId": binding["tupleId"],
                    "tupleOrder": binding["tupleOrder"],
                    "module": binding["module"],
                    "version": binding["version"],
                    "metadata": runner.parse_go_mod(
                        held.raw[binding["path"]],
                        binding["module"],
                    ),
                    "externalModRawSha256": binding["rawSha256"],
                }
            )
        elif kind in {"zip", "root_zip"}:
            archive = inspect_zip_bytes_v3(
                runner,
                held.raw[binding["path"]],
                binding,
                limits,
            )
            archive["kind"] = kind
            go_source_files += len(archive["sources"])
            for row in archive.pop("testdataSemanticExclusions"):
                exclusions.append(
                    {
                        "archivePath": binding["path"],
                        "module": binding["module"],
                        "version": binding["version"],
                        **row,
                    }
                )
            archive_rows.append(archive)
            aggregate_entries += archive["entryCount"]
            aggregate_uncompressed += archive["uncompressedByteCount"]
    check(
        aggregate_entries <= limits["maximumAggregateEntries"]
        and aggregate_uncompressed
        <= limits["maximumAggregateUncompressedBytes"],
        "E_ARCHIVE_AGGREGATE",
    )
    root_archives = [row for row in archive_rows if row["kind"] == "root_zip"]
    check(len(root_archives) == 1, "E_ROOT_ARCHIVE")
    embedded_root = root_archives[0].pop("embeddedGoMod")
    check(type(embedded_root) is bytes, "E_ROOT_ARCHIVE")
    metadata_rows.append(
        {
            "tupleId": "root",
            "tupleOrder": 0,
            "module": root_archives[0]["module"],
            "version": root_archives[0]["version"],
            "metadata": runner.parse_go_mod(
                embedded_root,
                root_archives[0]["module"],
            ),
            "externalModRawSha256": None,
        }
    )
    for tuple_id, pair in pairs.items():
        check(set(pair) == {"mod", "zip"}, "E_TUPLE_PAIR")
        matches = [
            row for row in archive_rows if row.get("tupleId") == tuple_id
        ]
        check(len(matches) == 1, "E_TUPLE_PAIR")
        embedded = matches[0].pop("embeddedGoMod")
        if embedded is not None:
            check(
                embedded == held.raw[pair["mod"]["path"]],
                "E_EMBEDDED_MOD_PARITY",
            )
    graph = runner.build_graph(
        archive_rows,
        metadata_rows,
        runner.profile_rows(permit),
        limits,
    )
    exclusions.sort(
        key=lambda row: (
            row["archivePath"],
            row["relativePath"],
            row["rawSha256"],
        )
    )
    return graph, {
        "archiveCount": len(archive_rows),
        "aggregateEntryCount": aggregate_entries,
        "aggregateUncompressedByteCount": aggregate_uncompressed,
        "goSourceFileCount": go_source_files,
        "semanticParsedGoSourceCount": go_source_files - len(exclusions),
        "testdataSemanticExclusionCount": len(exclusions),
        "testdataSemanticExclusionSetSha256": sha256_bytes(
            runner.canonical_json_bytes(exclusions)
        ),
    }


def combined_source_bindings(
    v1: types.ModuleType,
    runner: types.ModuleType,
    v1_documents: Mapping[str, Mapping[str, Any]],
    wave3_documents: Mapping[str, Mapping[str, Any]],
    wave4_documents: Mapping[str, Mapping[str, Any]],
    wave5_documents: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    bindings = v1.source_bindings(runner, v1_documents)
    bindings.extend(
        wave3_request_resources(runner, wave3_documents)
    )
    bindings.extend(
        wave4_request_resources(runner, wave4_documents)
    )
    bindings.extend(
        wave5_request_resources(runner, wave5_documents)
    )
    check(
        len(bindings) == 163
        and sum(row["kind"] == "root_zip" for row in bindings) == 1
        and sum(row["kind"] == "mod" for row in bindings) == 81
        and sum(row["kind"] == "zip" for row in bindings) == 81
        and sum(row["wave"] == "wave1" for row in bindings) == 38
        and sum(row["wave"] == "wave2" for row in bindings) == 30
        and sum(row["wave"] == "wave3" for row in bindings) == 32
        and sum(row["wave"] == "wave4" for row in bindings) == 32
        and sum(row["wave"] == "wave5" for row in bindings) == 30,
        "E_COMBINED_INPUT",
    )
    check(
        len({row["path"] for row in bindings}) == 163
        and len(
            {
                (row["module"], row["version"])
                for row in bindings
                if row["kind"] != "root_zip"
            }
        )
        == 81,
        "E_COMBINED_INPUT",
    )
    pair_kinds: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in bindings:
        if row["kind"] != "root_zip":
            pair_kinds[
                (row["module"], row["version"], row["tupleOrder"])
            ].add(row["kind"])
    check(
        len(pair_kinds) == 81
        and all(kinds == {"mod", "zip"} for kinds in pair_kinds.values())
        and sorted(order for _, _, order in pair_kinds) == list(range(1, 82)),
        "E_COMBINED_INPUT",
    )
    return bindings


def generate_candidate(root: Path = ROOT) -> dict[str, Any]:
    require_isolated_interpreter()
    with (
        PinnedCodeFile(
            root,
            SELF_PATH,
            SELF_NORMALIZED_SHA256,
            normalized_self_bytes,
        ) as self_held,
        PinnedCodeFile(
            root,
            V1_CHECKER_PATH,
            V1_CHECKER_RAW_SHA256,
        ) as v1_held,
        PinnedCodeFile(
            root,
            V3_CHECKER_PATH,
            V3_CHECKER_RAW_SHA256,
        ) as v3_held,
    ):
        v1 = load_v1_checker(v1_held)
        v3 = load_v3_checker(v3_held)
        v3_candidate = v3.generate_candidate(root)
        with v1.PinnedRunnerFile(root) as provider_held:
            runner = v1.load_pinned_runner(provider_held)
            predecessor_verification = validate_v3_predecessor_candidate(
                runner,
                v3_candidate,
            )
            controls = (
                v1.control_bindings()
                + wave3_control_bindings()
                + wave4_control_bindings()
                + wave5_control_bindings()
            )
            with runner.HeldInputSet(root, controls) as control_held:
                v1_documents = v1.parse_control_documents(
                    runner,
                    control_held,
                )
                v1.validate_terminal_documents(runner, v1_documents)
                wave3_documents = parse_wave3_documents(
                    runner,
                    control_held,
                )
                wave4_documents = parse_wave4_documents(
                    runner,
                    control_held,
                )
                wave5_documents = parse_wave5_documents(
                    runner,
                    control_held,
                )
                bindings = combined_source_bindings(
                    v1,
                    runner,
                    v1_documents,
                    wave3_documents,
                    wave4_documents,
                    wave5_documents,
                )
                predecessor_verification.update(
                    {
                        "wave5ReadbackCompletionAppliesToRetainedSnapshot":
                            True,
                        "wave5CurrentPathIdentityGuaranteedThroughManifestPublication":
                            False,
                        "wave5SameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                            False,
                    }
                )
                with runner.HeldInputSet(root, bindings) as source_held:
                    held_inputs = (
                        self_held,
                        v1_held,
                        v3_held,
                        provider_held,
                        control_held,
                        source_held,
                    )
                    combined_identity_barrier(root, held_inputs)
                    limits = v1.graph_limits(runner)
                    first_graph, first_coverage = reconstruct_graph_v3(
                        runner,
                        v1_documents[v1.WAVE1_PERMIT_PATH],
                        bindings,
                        source_held,
                        limits,
                    )
                    combined_identity_barrier(root, held_inputs)
                    second_graph, second_coverage = reconstruct_graph_v3(
                        runner,
                        v1_documents[v1.WAVE1_PERMIT_PATH],
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
                    combined_identity_barrier(root, held_inputs)
                    projection = v1.source_projection(bindings)
                    route = v1.route_for_graph(first_graph)
                    fixed_point = first_graph["fixedPointReached"]
                    body = {
                        "documentType": (
                            "aetherlink.g2-pion-combined-wave1-wave2-"
                            "wave3-wave4-wave5-fixed-point-candidate"
                        ),
                        "schemaVersion": "4.0",
                        "checkerId": CHECKER_ID,
                        "status": route["status"],
                        "result": (
                            "combined_graph_recomputed_twice_from_exact_"
                            "wave1_wave2_wave3_wave4_and_wave5_source_bytes"
                        ),
                        "verificationOnly": True,
                        "recordModeExposed": False,
                        "sourceInspectionPolicy": {
                            "policyId": SOURCE_INSPECTION_POLICY,
                            "exactLowercaseTestdataDirectoryExcludedBeforeParsing":
                                True,
                            "excludedBytesRemainInArchiveInventory": True,
                            "caseVariantsExcludedBeforeParsing": False,
                            "testFilesExcludedBeforeParsing": False,
                            "exampleDirectoriesExcludedBeforeParsing": False,
                            "toolDirectoriesExcludedBeforeParsing": False,
                        },
                        "inputSet": {
                            "heldSourceInputCount": 163,
                            "rootArchiveCount": 1,
                            "resourceCount": 162,
                            "modCount": 81,
                            "zipCount": 81,
                            "wave1ResourceCount": 38,
                            "wave2ResourceCount": 30,
                            "wave3ResourceCount": 32,
                            "wave4ResourceCount": 32,
                            "wave5ResourceCount": 30,
                            "uniqueModuleVersionTupleCount": 81,
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
                                WAVE3_RESOURCE_SET_SHA256,
                            "wave4AcceptedResourceSetSha256":
                                WAVE4_RESOURCE_SET_SHA256,
                            "wave5AcceptedResourceSetSha256":
                                WAVE5_RESOURCE_SET_SHA256,
                        },
                        "toolBindings": [
                            {
                                "role": "current_v4_combined_checker",
                                "path": SELF_PATH,
                                "normalizedSha256":
                                    SELF_NORMALIZED_SHA256,
                            },
                            {
                                "role": "immutable_v1_combined_checker",
                                "path": V1_CHECKER_PATH,
                                "rawSha256": V1_CHECKER_RAW_SHA256,
                            },
                            {
                                "role": "immutable_v3_combined_checker_predecessor",
                                "path": V3_CHECKER_PATH,
                                "rawSha256": V3_CHECKER_RAW_SHA256,
                            },
                            {
                                "role": "immutable_wave1_graph_provider",
                                "path": V1_PROVIDER_PATH,
                                "rawSha256": V1_PROVIDER_RAW_SHA256,
                            },
                        ],
                        "terminalEvidenceBindings": [
                            {
                                "path": row["path"],
                                "rawSha256": row["rawSha256"],
                            }
                            for row in controls
                        ],
                        "predecessorVerification":
                            predecessor_verification,
                        "coverage": first_coverage,
                        "profiles": runner.profile_rows(
                            v1_documents[v1.WAVE1_PERMIT_PATH]
                        ),
                        "graphDiscovery": first_graph,
                        "checkerVerification": {
                            "directFullInputReconstructionCount": 2,
                            "inheritedFullInputReconstructionCount": 4,
                            "totalFullInputReconstructionCount": 6,
                            "underlyingIndependentGraphAlgorithmCount": 12,
                            "pinnedV3PredecessorExecuted": True,
                            "canonicalGraphEqualityVerified": True,
                            "barrierBeforeReconstructionCompleted": True,
                            "barrierBetweenReconstructionsCompleted": True,
                            "barrierAfterReconstructionCompleted": True,
                            "workspaceRootIdentityBoundAcrossAllInputs": True,
                            "calculatedFixedPointCandidate": fixed_point,
                        },
                        "route": route["route"],
                        "nextAction": route["nextAction"],
                        "operationCounters": {
                            "heldSourceInputCount": 163,
                            "heldTerminalEvidenceCount": len(controls),
                            "heldToolInputCount": 4,
                            "transitiveDistinctToolPathCount": 5,
                            "stableReadPassesPerHeldInput": 2,
                            "directFullSourceReconstructionCount": 2,
                            "inheritedFullSourceReconstructionCount": 4,
                            "totalFullSourceReconstructionCount": 6,
                            "archiveOpenCount": 400,
                            "archiveExtractionCount": 0,
                            "sourceExecutionCount": 0,
                            "subprocessCount": 0,
                            "networkOperationCount": 0,
                            "fileWriteCount": 0,
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
                        },
                    }
                    candidate = runner.content_bound(
                        body,
                        "candidate_without_contentBinding",
                    )
                    combined_identity_barrier(root, held_inputs)
                    return candidate


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = CanonicalArgumentParser(description=__doc__)
    return parser.parse_args(argv)


def error_document_bytes() -> bytes:
    return (
        json.dumps(
            {
                "documentType": (
                    "aetherlink.g2-pion-combined-wave1-wave2-wave3-wave4-"
                    "wave5-"
                    "fixed-point-check-error"
                ),
                "schemaVersion": "4.0",
                "status": "failed_closed_without_publication",
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "networkOperationCount": 0,
                "sourceExecutionCount": 0,
                "fileWriteCount": 0,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parse_arguments(argv)
    except CliUsageFailure:
        sys.stdout.buffer.write(error_document_bytes())
        return 2
    try:
        candidate = generate_candidate(ROOT)
    except Exception:
        sys.stdout.buffer.write(error_document_bytes())
        return 1
    sys.stdout.buffer.write(
        json.dumps(
            candidate,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
