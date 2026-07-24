#!/usr/bin/env python3
"""Validate the Wave3 32/32 checksum-identity successor decision."""

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
    raise RuntimeError("Wave3 v2 checker requires `python3 -I -B -S`")

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave3-v2.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave3-v2.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v2.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v2.py"
)
EXPECTED_READER_RAW = (
    "220ee4b2f702da254c18b4985112928edc5bea42a8896a5527ed9c684772df4a"
)
MAXIMUM_FILE_BYTES = 8 * 1024 * 1024
EXPECTED_UID = 501
TARGET_MODULE = "github.com/kr/pty"
TARGET_VERSION = "v1.1.1"
TARGET_MOD_H1 = "h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ="
TARGET_ZIP_H1 = "h1:VkoXIwSboBpnk99O/KFauAEILuNHv5DVFKZMBN/gUgw="
EXECUTION_ATTEMPT_ID = "02e6be7ab4a6ebb6d8beba2142c81406"
READBACK_ATTEMPT_ID = "d1d280285070f6226c03be0dba7c39be"
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
WAVE3_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-3-v1.claim"
WAVE3_STAGING_PREFIX = ".wave-3-v1-staging-"
WAVE3_FINAL_PATH = f"{DEPENDENCY_ROOT}/wave-3-v1"


class DecisionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(value: bool, code: str) -> None:
    if not value:
        raise DecisionError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
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


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(
                DecisionError("E_JSON")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                DecisionError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    require("contentBinding" not in result, "E_CONTENT")
    result["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(result)),
    }
    return result


def verify_content_bound(
    raw: bytes,
    expected_content: str,
    code: str,
) -> dict[str, Any]:
    value = strict_json(raw)
    require(raw == canonical_bytes(value), code)
    binding = value.pop("contentBinding", None)
    digest = sha256(canonical_bytes(value))
    require(
        type(binding) is dict
        and binding.get("sha256") == digest == expected_content
        and (
            binding
            == {
                "algorithm": "sha256(canonical-json-without-contentBinding)",
                "sha256": digest,
            }
            or binding
            == {
                "algorithm": "sha256",
                "canonicalization": (
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf"
                ),
                "scope": "decision_without_contentBinding",
                "sha256": digest,
            }
        ),
        "E_CONTENT",
    )
    value["contentBinding"] = binding
    return value


def artifact(
    path: str,
    raw_sha256: str,
    size: int,
    mode: str,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    result = {
        "path": path,
        "rawSha256": raw_sha256,
        "bytes": size,
        "mode": mode,
    }
    if content_sha256 is not None:
        result["contentSha256"] = content_sha256
    return result


V1_PACKAGE = (
    artifact(
        f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
        "decision-wave3-v1.json",
        "c2a1e1d7c0e4936edb8eb20c92d62859c9ee047da4adf9f31a0a458363df732e",
        59_981,
        "0644",
        "e31e1bb96802082047e1a9c9d1c1cb43d8a8415f72294282d3b97c97b1cafc2a",
    ),
    artifact(
        f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
        "decision-wave3-v1.md",
        "9ed3ad459aa88c2ff559c8bfb96689dd5e3ca16be3cbe5a3e62d72c9aabb43fd",
        1_076,
        "0644",
    ),
    artifact(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v1.py",
        "3f16e928847005bb6b1a328345738dd3f1cae7a372f3dc6c900d87e80e802cf4",
        43_002,
        "0644",
    ),
    artifact(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v1.py",
        "7bab19d302cc488c1492f95cacbe7d60b710c72d9a32f004c9fb74f1eae91acd",
        18_617,
        "0644",
    ),
)

PUBLIC_DECISION_PACKAGE = (
    artifact(
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "decision-v1.json",
        "dfc141d996b213e5d172041341aa37bc43efac4f9e4d6c27aea415d8e69a840e",
        12_754,
        "0644",
        "12eea2f9608f00c1953e41a9845669f396223fcaa561736aeb96b6ce2e37a0db",
    ),
    artifact(
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "decision-v1.md",
        "57c8df5364e577f85f88e4da0538ddd3b6a318ae62b71ea2a894983bedfd85f8",
        2_258,
        "0644",
    ),
    artifact(
        "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_decision_v1.py",
        "47de3381f59aad75cec5639fff2eb5f1d3be2cd0bd06e3a47953430943fc4422",
        32_214,
        "0644",
    ),
    artifact(
        "script/test_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_decision_v1.py",
        "ca59173e6c0fd3ec0692db12a63febd3b1f07f9d261fdb4484016ab512c8f9c4",
        15_555,
        "0644",
    ),
)

EXECUTION_PERMIT_PACKAGE = (
    artifact(
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "execution-permit-v1.json",
        "6d0669afbc24509609360952c3010726d71492832df69dabb1fccf0aaf1f2197",
        13_134,
        "0644",
        "41f2050c3e8a702da66adfdf5c890604756c7fa0e708d4b9fb062c8f5693a7fb",
    ),
    artifact(
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "execution-permit-v1.md",
        "8c421f586af85580571cf123a0917b4505d8ee5ee2f72eb0a7e0d398bb8d4493",
        2_809,
        "0644",
    ),
    artifact(
        "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_execution_permit_v1.py",
        "14b628e788dcd216e9102596f95681dfe1fbb6e97e6b6170ece19fee6499ab6c",
        34_410,
        "0644",
    ),
    artifact(
        "script/test_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_execution_permit_v1.py",
        "97c4fb9f3ecb8a239c52d047e35820ef7df32472beac4f81bfd7b82454fee7ea",
        16_122,
        "0644",
    ),
    artifact(
        "script/resolve_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_v1_once.py",
        "c2771f68a8d73076e3175b9791f7b03a988c2b0e4f289bad7a352c110debe25d",
        50_459,
        "0644",
    ),
    artifact(
        "script/test_resolve_p2p_nat_g2_pion_rung3_dependency_public_"
        "checksum_identity_v1_once.py",
        "0a3ec5e01427614aa2774acd470afd4645ecca7202edbbd1272ff3e719a1004a",
        33_490,
        "0644",
    ),
)

READBACK_PERMIT_PACKAGE = (
    artifact(
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "readback-execution-permit-v1.json",
        "df3360848065976c37484d48b137ec37121496f13b99250c51914b85e9de62d6",
        11_370,
        "0644",
        "15baa1db7b2446b1514a314cb5d5bed9abb4e20342e34110f74ac0d707a84f1c",
    ),
    artifact(
        f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
        "readback-execution-permit-v1.md",
        "474018e98b351ae0dea7431cae0957296fca9c182d3233f37b4d794b1e9b7c77",
        2_125,
        "0644",
    ),
    artifact(
        "script/check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_readback_execution_permit_v1.py",
        "7b741d232b4d0e64b5c6cffcc1fab2f2942b421089f8ddf117e9399b4f5a8bfa",
        27_077,
        "0644",
    ),
    artifact(
        "script/test_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_readback_execution_permit_v1.py",
        "327bd302bc759ecc4302ce1e8680795ea816ee01a0dd795e3816a930c345fb69",
        11_146,
        "0644",
    ),
    artifact(
        "script/record_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
        "identity_resolution_readback_v1_once.py",
        "6cf6cece86a10748fca01cc451fca2b0117505835cbec3b8195642ecb6b52a05",
        48_227,
        "0644",
    ),
    artifact(
        "script/test_record_p2p_nat_g2_pion_rung3_dependency_public_"
        "checksum_identity_resolution_readback_v1_once.py",
        "0d4250738d9079d01e6dcb8e187c49cca4307e3b89bf307b2a4641f103c5c13f",
        19_275,
        "0644",
    ),
)

EXECUTION_CLAIM = artifact(
    f"{DEPENDENCY_ROOT}/.wave-3-kr-pty-sumdb-identity-v1.claim",
    "f38054ca652a53d56e30766fc869728a14b42ac5dd8e20943f391a96a374d288",
    1_098,
    "0600",
)
EXECUTION_RECEIPT = artifact(
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "receipt-v1.json",
    "f51c1caa62bb22bafda09d856bb7c1e9b3f0d4ee527f83dd0dcebe9ee6a18b36",
    1_806,
    "0600",
    "d9fd832fe31822d1023ed858c98bc1dece403977237f72ecf0cb059f40feafc7",
)
EXECUTION_MANIFEST = artifact(
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "manifest-v1.json",
    "e45d49d459cd7542e2544d9d9607a5f040f8af95c24a999780ed08d64ee1577b",
    1_547,
    "0600",
    "38d0da0b0aa31183a3140cb4c85b32b5f8cf5dc11ceac00586b09d43f9cc2d27",
)
EVIDENCE_ROOT = (
    f"{DEPENDENCY_ROOT}/wave-3-kr-pty-sumdb-identity-v1/evidence"
)
EVIDENCE_FILES = (
    artifact(
        f"{EVIDENCE_ROOT}/evidence.json",
        "043e1f13a9c7c13624f3de622adff99965ddeee7ef41b539b41d1068cfd7f204",
        7_615,
        "0600",
        "79a36a5b2858eb3bd4b1c2e60ecb675e18f3717e897f97e2e5f030d69ba92321",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/lookup.response",
        "a091017a6258e8994466556d69cdfe0d2f2255dbe04adfd706f582806204cd34",
        346,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-001-433f370775408752.bin",
        "a683cc7097dd2305c76c2876650c12041496b8fe82aad2000ee9a3e40d2485e2",
        8_192,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-002-a942e5993ab9ac53.bin",
        "3b186038695f392b628e89576b24c7d4c081ffd421b22343e68755ae0f64ac3a",
        8_192,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-003-11e688bd3f4b0938.bin",
        "231e112efd062aabddbc853b6c7df64770a4004b576743203a83ffafb451b74d",
        3_584,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-004-784dcfa494c65600.bin",
        "91c70bde50c7f65306f9ec9680e94e6eb64be27682e4ab1575a19d1d8ddf175b",
        8_192,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-005-46424d628236beba.bin",
        "eb451cb9245be0e322e5406fefe779df43746579228d93a2386c90bd173933f0",
        8_192,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-006-27561b7ea9397973.bin",
        "f1c008dfc4bb3302a4fd02ba16b27a4b47b7a151b33a339231364d9425239702",
        5_408,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-007-39dff99d869ebfa2.bin",
        "e31db8423668ce64d4153f4edea5cbb473825e7ba7aae501130c9c1f83948333",
        8_192,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-008-17efcc63092f321b.bin",
        "a4d3e65a383cf02ef96b63e850890a093e8e451b8011103ad9b662319eed4074",
        3_712,
        "0600",
    ),
    artifact(
        f"{EVIDENCE_ROOT}/tile-009-63afe683110cb0e6.bin",
        "0572a23f83541b9701b37b8862c189ca3a9c83e08f183cde38ccdf894f43a375",
        96,
        "0600",
    ),
)

READBACK_CLAIM = artifact(
    f"{DEPENDENCY_ROOT}/.wave-3-kr-pty-sumdb-identity-readback-v1.claim",
    "ab3da8c9d692c0b091fca257cdee82e5c44f95e223986e49572ab73c3d79d56d",
    1_222,
    "0600",
    "e6bc2768cfd2825c6858455b72ea3265ed008ea3d9b4d85247f0e7fbe1958726",
)
READBACK_RECEIPT = artifact(
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-v1.json",
    "5c42f2adb3e6b8cf03a97325c24ae5fc17d99cab028f061fb9a9601a04068df2",
    2_907,
    "0600",
    "140bf5d1dc7538ffad6f1f79008330c489e6e9f45f917481c23aa8111c97c1b5",
)
READBACK_MANIFEST = artifact(
    f"{BASE}/bounded-dependency-public-checksum-identity-resolution-"
    "readback-manifest-v1.json",
    "f977c862c6c6428d722522e0d33732ce79ca19c394e032853ab85e08c1aa79ef",
    1_662,
    "0600",
    "1f10eb041f3cdb377f6f4d3bd58ff47a0f0caf9877412fbe95ca5bf5a4590e26",
)

ALL_EXTERNAL = (
    *V1_PACKAGE,
    *PUBLIC_DECISION_PACKAGE,
    *EXECUTION_PERMIT_PACKAGE,
    EXECUTION_CLAIM,
    *EVIDENCE_FILES,
    EXECUTION_RECEIPT,
    EXECUTION_MANIFEST,
    *READBACK_PERMIT_PACKAGE,
    READBACK_CLAIM,
    READBACK_RECEIPT,
    READBACK_MANIFEST,
)


def stable_read(binding: Mapping[str, Any]) -> bytes:
    path = binding["path"]
    current = ROOT
    for component in path.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, EXPECTED_UID}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_PATH",
        )
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(ROOT / path, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid == EXPECTED_UID
            and f"{stat.S_IMODE(before.st_mode):04o}" == binding["mode"]
            and before.st_size == binding["bytes"]
            and 0 < before.st_size <= MAXIMUM_FILE_BYTES,
            "E_SHAPE",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(fd, 1), "E_READ")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        require(
            before == after and sha256(raw) == binding["rawSha256"],
            "E_BINDING",
        )
        return raw
    finally:
        os.close(fd)


def stable_new_read(path: str) -> bytes:
    target = ROOT / path
    info = target.lstat()
    require(
        stat.S_ISREG(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and info.st_nlink == 1
        and info.st_uid == EXPECTED_UID
        and stat.S_IMODE(info.st_mode) == 0o644
        and 0 < info.st_size <= MAXIMUM_FILE_BYTES,
        "E_PACKAGE",
    )
    binding = artifact(
        path,
        sha256(target.read_bytes()),
        info.st_size,
        "0644",
    )
    return stable_read(binding)


def verify_directory_inventory() -> None:
    path = ROOT / EVIDENCE_ROOT
    info = path.lstat()
    require(
        stat.S_ISDIR(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and info.st_uid == EXPECTED_UID
        and stat.S_IMODE(info.st_mode) == 0o700,
        "E_EVIDENCE",
    )
    expected_names = {
        Path(row["path"]).name for row in EVIDENCE_FILES
    }
    require(
        {child.name for child in path.iterdir()} == expected_names,
        "E_EVIDENCE",
    )


def external_snapshot() -> dict[str, bytes]:
    verify_directory_inventory()
    raw = {row["path"]: stable_read(row) for row in ALL_EXTERNAL}
    for row in ALL_EXTERNAL:
        if "contentSha256" in row:
            verify_content_bound(
                raw[row["path"]],
                row["contentSha256"],
                "E_EXTERNAL_CONTENT",
            )
    return raw


def package_binding(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"files": [dict(row) for row in rows]}


def validate_external_facts(
    raw: Mapping[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    v1 = verify_content_bound(
        raw[V1_PACKAGE[0]["path"]],
        V1_PACKAGE[0]["contentSha256"],
        "E_V1",
    )
    require(
        v1["status"]
        == (
            "wave3_exact_16_frontier_identity_classified_"
            "15_complete_1_blocked_acquisition_not_authorized"
        )
        and v1["wave"]["identityRecordCount"] == 31
        and v1["wave"]["requiredIdentityRecordCount"] == 32
        and v1["wave"]["acquisitionReady"] is False,
        "E_V1",
    )
    evidence = verify_content_bound(
        raw[EVIDENCE_FILES[0]["path"]],
        EVIDENCE_FILES[0]["contentSha256"],
        "E_EXECUTION",
    )
    receipt = verify_content_bound(
        raw[EXECUTION_RECEIPT["path"]],
        EXECUTION_RECEIPT["contentSha256"],
        "E_EXECUTION",
    )
    manifest = verify_content_bound(
        raw[EXECUTION_MANIFEST["path"]],
        EXECUTION_MANIFEST["contentSha256"],
        "E_EXECUTION",
    )
    readback = verify_content_bound(
        raw[READBACK_RECEIPT["path"]],
        READBACK_RECEIPT["contentSha256"],
        "E_READBACK",
    )
    readback_manifest = verify_content_bound(
        raw[READBACK_MANIFEST["path"]],
        READBACK_MANIFEST["contentSha256"],
        "E_READBACK",
    )
    require(
        evidence["attemptId"] == EXECUTION_ATTEMPT_ID
        and evidence["status"]
        == "locally_verified_pending_independent_readback"
        and evidence["target"]
        == {
            "module": TARGET_MODULE,
            "version": TARGET_VERSION,
            "goModH1": TARGET_MOD_H1,
            "moduleZipH1": TARGET_ZIP_H1,
        }
        and evidence["proof"]["recordInclusionVerified"] is True
        and evidence["proof"]["oldToNewConsistencyVerified"] is True
        and evidence["proof"]["canonicalProofBundleSha256"]
        == "be19078ad07d9db15349d47b33ea1b5a99bb79085258d2b6affc438ea31acfcf"
        and evidence["counters"]["networkRequestAttemptCount"] == 10
        and evidence["counters"]["derivedUniqueTileCount"] == 9
        and evidence["counters"]["aggregateResponseBodyBytes"] == 54_106
        and evidence["boundary"]["sourceAcquired"] is False,
        "E_EXECUTION",
    )
    require(
        receipt["attemptId"] == EXECUTION_ATTEMPT_ID
        and receipt["status"]
        == "identity_resolved_pending_independent_readback"
        and receipt["evidence"]["resolvedModuleZipH1"] == TARGET_ZIP_H1
        and receipt["sourceAcquired"] is False
        and manifest["attemptId"] == EXECUTION_ATTEMPT_ID
        and manifest["receipt"]["rawSha256"]
        == EXECUTION_RECEIPT["rawSha256"]
        and manifest["manifestWrittenLast"] is True
        and manifest["sourceAcquired"] is False,
        "E_EXECUTION",
    )
    verified = readback["verified"]
    require(
        readback["status"] == "identity_resolution_independently_read_back"
        and readback["offline"] is True
        and readback["networkRequestAttemptCount"] == 0
        and readback["sourceAcquired"] is False
        and readback["executionAttemptId"] == EXECUTION_ATTEMPT_ID
        and readback["readbackAttemptId"] == READBACK_ATTEMPT_ID
        and verified["executionAttemptId"] == EXECUTION_ATTEMPT_ID
        and verified["resolvedModuleZipH1"] == TARGET_ZIP_H1
        and verified["recordNumber"] == 468
        and verified["treeSize"] == 57_977_200
        and verified["rootHashBase64"]
        == "0kI+rwgqD/6bAhK44aKUcZElkWFQ15U9rsUn5SDRzLg="
        and verified["canonicalProofBundleSha256"]
        == "be19078ad07d9db15349d47b33ea1b5a99bb79085258d2b6affc438ea31acfcf"
        and verified["evidenceFileCount"] == 11
        and verified["tileFileCount"] == 9
        and verified["inclusionProofHashCount"] == 26
        and verified["consistencyProofHashCount"] == 25
        and verified["aggregateResponseBodyBytes"] == 54_106
        and readback_manifest["status"]
        == "identity_resolution_readback_publication_complete"
        and readback_manifest["readbackAttemptId"] == READBACK_ATTEMPT_ID
        and readback_manifest["executionAttemptId"] == EXECUTION_ATTEMPT_ID
        and readback_manifest["receipt"]["rawSha256"]
        == READBACK_RECEIPT["rawSha256"]
        and readback_manifest["manifestWrittenLast"] is True
        and readback_manifest["sourceAcquired"] is False,
        "E_READBACK",
    )
    return v1, evidence, readback


def require_wave3_namespace_absent() -> None:
    require(
        not (ROOT / WAVE3_CLAIM_PATH).exists()
        and not (ROOT / WAVE3_FINAL_PATH).exists(),
        "E_NAMESPACE",
    )
    dependency = ROOT / DEPENDENCY_ROOT
    require(
        not any(
            child.name.startswith(WAVE3_STAGING_PREFIX)
            for child in dependency.iterdir()
        ),
        "E_NAMESPACE",
    )
    for suffix in (
        "receipt-v1.json",
        "failure-v1.json",
        "manifest-v1.json",
        "readback-v1.json",
        "readback-manifest-v1.json",
    ):
        require(
            not (
                ROOT
                / (
                    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
                    f"{suffix}"
                )
            ).exists(),
            "E_NAMESPACE",
        )


def expected_payload(
    package_raw: Mapping[str, bytes],
    external_raw: Mapping[str, bytes],
) -> dict[str, Any]:
    v1, evidence, readback = validate_external_facts(external_raw)
    payload = copy.deepcopy(v1)
    payload.pop("contentBinding")
    payload["documentType"] = (
        "aetherlink.g2-pion-rung3-bounded-dependency-source-"
        "identity-and-acquisition-decision-wave3-successor"
    )
    payload["decisionId"] = (
        "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-"
        "identity-and-acquisition-decision-wave3-v2"
    )
    payload["status"] = (
        "wave3_exact_16_frontier_identity_classified_"
        "16_complete_0_blocked_acquisition_ready_not_authorized"
    )
    wave = payload["wave"]
    pty = wave["tuples"][0]
    require(
        pty["tupleOrder"] == 1
        and pty["module"] == TARGET_MODULE
        and pty["version"] == TARGET_VERSION
        and pty["checksumIdentity"]["goModH1"] == TARGET_MOD_H1
        and pty["checksumIdentity"]["moduleZipH1"] is None,
        "E_TUPLE",
    )
    pty["checksumIdentity"]["moduleZipH1"] = TARGET_ZIP_H1
    pty["checksumIdentity"]["moduleZipH1Present"] = True
    pty["checksumIdentity"]["completePair"] = True
    pty["checksumIdentity"]["canonicalEvidenceSelection"] = (
        "held_go_mod_h1_plus_independently_read_back_sumdb_zip_h1"
    )
    pty["checksumIdentity"]["moduleZipEvidence"] = {
        "checksumKind": "module_zip_h1",
        "evidenceKind": "independent_sumdb_readback",
        "module": TARGET_MODULE,
        "version": TARGET_VERSION,
        "h1": TARGET_ZIP_H1,
        "executionAttemptId": EXECUTION_ATTEMPT_ID,
        "readbackAttemptId": READBACK_ATTEMPT_ID,
        "recordNumber": readback["verified"]["recordNumber"],
        "treeSize": readback["verified"]["treeSize"],
        "rootHashBase64": readback["verified"]["rootHashBase64"],
        "canonicalProofBundleSha256": readback["verified"][
            "canonicalProofBundleSha256"
        ],
        "executionEvidence": {
            "path": EVIDENCE_FILES[0]["path"],
            "rawSha256": EVIDENCE_FILES[0]["rawSha256"],
            "contentSha256": EVIDENCE_FILES[0]["contentSha256"],
        },
        "independentReadback": {
            "path": READBACK_RECEIPT["path"],
            "rawSha256": READBACK_RECEIPT["rawSha256"],
            "contentSha256": READBACK_RECEIPT["contentSha256"],
        },
    }
    pty["acquisitionReady"] = True
    wave.update(
        {
            "goModH1Count": 16,
            "moduleZipH1Count": 16,
            "completeH1PairCount": 16,
            "identityRecordCount": 32,
            "requiredIdentityRecordCount": 32,
            "blockedTupleCount": 0,
            "acquisitionReady": True,
        }
    )
    payload.pop("identityGap")
    payload["identityClosure"] = {
        "module": TARGET_MODULE,
        "version": TARGET_VERSION,
        "goModH1": TARGET_MOD_H1,
        "moduleZipH1": TARGET_ZIP_H1,
        "identityPairComplete": True,
        "closedByConsumedIndependentOfflineReadback": True,
        "executionAttemptId": EXECUTION_ATTEMPT_ID,
        "readbackAttemptId": READBACK_ATTEMPT_ID,
        "sourceAcquired": False,
        "sourceAuthorOrRepositoryAttested": False,
    }
    payload["successorBindings"] = {
        "wave3V1DecisionPackage": package_binding(V1_PACKAGE),
        "publicChecksumDecisionPackage": package_binding(
            PUBLIC_DECISION_PACKAGE
        ),
        "sumDbExecutionPermitPackage": package_binding(
            EXECUTION_PERMIT_PACKAGE
        ),
        "sumDbExecution": {
            "claim": dict(EXECUTION_CLAIM),
            "evidenceDirectory": {
                "path": EVIDENCE_ROOT,
                "mode": "0700",
                "fileCount": 11,
                "files": [dict(row) for row in EVIDENCE_FILES],
            },
            "receipt": dict(EXECUTION_RECEIPT),
            "manifest": dict(EXECUTION_MANIFEST),
            "executionAttemptId": EXECUTION_ATTEMPT_ID,
            "recordNumber": evidence["lookup"]["recordNumber"],
            "treeSize": evidence["lookup"]["treeSize"],
            "rootHashBase64": evidence["lookup"]["rootHashBase64"],
            "canonicalProofBundleSha256": evidence["proof"][
                "canonicalProofBundleSha256"
            ],
            "networkRequestAttemptCount": 10,
            "tileRequestCount": 9,
            "aggregateResponseBodyBytes": 54_106,
            "sourceAcquired": False,
        },
        "independentReadbackPermitPackage": package_binding(
            READBACK_PERMIT_PACKAGE
        ),
        "consumedIndependentReadback": {
            "claim": dict(READBACK_CLAIM),
            "receipt": dict(READBACK_RECEIPT),
            "manifest": dict(READBACK_MANIFEST),
            "executionAttemptId": EXECUTION_ATTEMPT_ID,
            "readbackAttemptId": READBACK_ATTEMPT_ID,
            "offline": True,
            "networkRequestAttemptCount": 0,
            "sourceAcquired": False,
        },
    }
    require(
        all(
            row["acquisitionReady"]
            and row["checksumIdentity"]["completePair"]
            and row["checksumIdentity"]["goModH1Present"]
            and row["checksumIdentity"]["moduleZipH1Present"]
            and row["acquisitionAuthorized"] is False
            for row in wave["tuples"]
        )
        and sum(
            int(row["checksumIdentity"]["goModH1Present"])
            + int(row["checksumIdentity"]["moduleZipH1Present"])
            for row in wave["tuples"]
        )
        == 32,
        "E_IDENTITY",
    )
    payload["sourceAcquisitionPreparation"] = {
        "separateExecutionPermitRequired": True,
        "oneUsePermitRequired": True,
        "tupleCount": 16,
        "resourcesPerTuple": 2,
        "resourceCount": 32,
        "requestOrder": "tuple_order_ascending_mod_then_zip",
        "claimPath": WAVE3_CLAIM_PATH,
        "stagingPrefix": WAVE3_STAGING_PREFIX,
        "acceptedDirectoryPath": f"{WAVE3_FINAL_PATH}/accepted",
        "acquisitionAuthorizedByThisDecision": False,
        "independentPostConsumptionReadbackRequired": True,
    }
    payload["nonClaims"] = [
        "this successor decision is not a network or acquisition execution permit",
        "32 of 32 checksum identities is acquisition readiness not acquisition authority",
        "SumDB inclusion proves checksum identity not source author or repository attestation",
        "the independently read back ZIP H1 is not guessed inferred or source bytes",
        "selectedByGraphAlgorithm false does not remove a version vertex",
        "no tuple is rejected reordered dropped or replaced by a higher version",
        "no source bytes were acquired reviewed loaded extracted executed or compiled",
        "identity completion is not dependency fixed point or source closure",
        "no semantic closure candidate library release or rung three completion is established",
        "roadmap and handoff text are not execution authority",
    ]
    payload["readerDocumentBinding"] = {
        "path": READER_PATH,
        "rawSha256": EXPECTED_READER_RAW,
    }
    payload["toolBindings"] = [
        {
            "path": path,
            "rawSha256": sha256(package_raw[path]),
        }
        for path in (THIS_CHECKER_PATH, THIS_TESTS_PATH)
    ]
    payload["result"] = (
        "exact_16_version_vertices_4_selected_12_nonselected_"
        "16_complete_h1_pairs_32_of_32_identity_records_"
        "acquisition_ready_not_authorized"
    )
    payload["nextAction"] = (
        "prepare_separate_one_use_32_resource_wave3_source_"
        "acquisition_permit_checker_runner_and_tests"
    )
    return payload


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    require_wave3_namespace_absent()
    package_paths = [READER_PATH, THIS_CHECKER_PATH, THIS_TESTS_PATH]
    if verify_disk:
        package_paths.append(DECISION_PATH)
    package_raw = {path: stable_new_read(path) for path in package_paths}
    require(
        sha256(package_raw[READER_PATH]) == EXPECTED_READER_RAW,
        "E_READER",
    )
    external_raw = external_snapshot()
    expected = content_bound(expected_payload(package_raw, external_raw))
    if verify_disk:
        actual = verify_content_bound(
            package_raw[DECISION_PATH],
            expected["contentBinding"]["sha256"],
            "E_DECISION",
        )
        require(
            package_raw[DECISION_PATH] == canonical_bytes(expected)
            and actual == expected,
            "E_DECISION",
        )
    require_wave3_namespace_absent()
    final_external = external_snapshot()
    require(
        {
            path: sha256(raw) for path, raw in external_raw.items()
        }
        == {
            path: sha256(raw) for path, raw in final_external.items()
        },
        "E_FINAL_BARRIER",
    )
    return expected, {
        "documentType": "aetherlink.wave3-identity-successor-decision-check",
        "schemaVersion": "1.0",
        "status": "validated_32_of_32_acquisition_ready_not_authorized",
        "validationPassed": True,
        "tupleCount": 16,
        "identityRecordCount": 32,
        "requiredIdentityRecordCount": 32,
        "blockedTupleCount": 0,
        "acquisitionReady": True,
        "acquisitionAuthorized": False,
        "networkUsed": False,
        "fileWriteCount": 0,
        "sourceAcquired": False,
        "sourceExecutionUsed": False,
        "subprocessCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise DecisionError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        parser.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        expected, summary = evaluate(not args.print_expected)
        sys.stdout.buffer.write(
            canonical_bytes(expected if args.print_expected else summary)
        )
        return 0
    except DecisionError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.wave3-identity-successor-decision-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "acquisitionAuthorized": False,
                    "networkUsed": False,
                    "fileWriteCount": 0,
                    "sourceAcquired": False,
                    "sourceExecutionUsed": False,
                    "subprocessCount": 0,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.wave3-identity-successor-decision-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "acquisitionAuthorized": False,
                    "networkUsed": False,
                    "fileWriteCount": 0,
                    "sourceAcquired": False,
                    "sourceExecutionUsed": False,
                    "subprocessCount": 0,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
