#!/usr/bin/env python3
"""Validate the one-use offline Wave4 acquisition readback permit."""

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
    raise RuntimeError("Wave4 readback checker requires `python3 -I -B -S`")

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", None)
if O_NOFOLLOW is None:
    raise RuntimeError("Wave4 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave4_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave4_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave4_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-4-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave4-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave4-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-4-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-4-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave4-failure-v1.json"
)
STAGING_PREFIX = ".wave-4-v1-staging-"
ATTEMPT_ID = "4cda3d86462fff445d6e69bce4b92dec"
EXPECTED_DECISION_CONTENT = (
    "9433ed0eb93e5b342fe1f9f9ffdb2ebcf31a3955b9c5fbc582f6af393ce28cb3"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "a20c2d0da85682818076b6a6a820d36243ae95bb15ff7446f23602e45a427a7e"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "6557dc9b235c73f6453d253049a66a6f08b3a1cc6423c64e3d0e841e4da34c8b"
)
EXPECTED_COMPACT_IDENTITY = (
    "7018a78754932244c8bc1449ad9079d19d0c48bcdb287b0109178cb3709895b2"
)
EXPECTED_FULL_WITNESS = (
    "338069b9666561cc23dd859a202b72e45e0c7fa2f94b69d6b976777dbd148d86"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "b985bd0346d66beaa80381056d6650c8bb275f7ebdc9df59c861832b5655868e"
)
EXPECTED_READER_RAW = "1d703d737cc0de5aca2bbdefbaffa887365a1e3eb1f9eb9faa4752341e4e9760"
EXPECTED_RECORDER_NORMALIZED_SHA256 = "75a84af6d5430a803e39b52ac366a92f1111095ca0c093e6bfd88d713b8b32d9"
MAXIMUM_PACKAGE_FILE_BYTES = 8 * 1024 * 1024


def frozen(
    path: str,
    digest: str,
    size: int,
    mode: str,
    owner_uid: int = 501,
    link_count: int = 1,
) -> dict[str, Any]:
    return {
        "path": path,
        "rawSha256": digest,
        "bytes": size,
        "mode": mode,
        "ownerUid": owner_uid,
        "linkCount": link_count,
    }


ACQUISITION_AUTHORITY = [
    frozen(
        (
            f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
            "decision-wave4-v1.json"
        ),
        "7be65d39144ca8eea0180e94d0902733e9f475edbb81de792f8c57733fb27e5d",
        28_996,
        "0644",
    ),
    frozen(
        (
            f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
            "decision-wave4-v1.md"
        ),
        "f7176713c9759ec54a21f0cbe77ae2ab5424a8361c256e6af50ad6a43bbba196",
        1_230,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_decision_v1.py",
        "5ef1a37ac6006ab05675a1e3afa44b01f7bb684ce525976bb182c8fcafbd4852",
        56_356,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave4_decision_v1.py",
        "d49564ecf7867d2bc24e795988a3677497a7c37378c9d9a92673c395ec11a941",
        20_167,
        "0644",
    ),
    frozen(
        f"{BASE}/bounded-dependency-source-acquisition-wave4-execution-permit-v1.md",
        "c14352d13acd10b8b93ff3f62b2aab41c60d1571594dbabb58257e432f56f358",
        1_883,
        "0644",
    ),
    frozen(
        f"{BASE}/bounded-dependency-source-acquisition-wave4-execution-permit-v1.json",
        "7e2ae57e349ee1b55a58a17dd0ceda487ec400a5998b2eefa37f77d898b5c141",
        27_658,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py",
        "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd",
        34_617,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py",
        "f2a8b3f5d2ea99ceb1709d67f57d945182c7ac0b099bc984a8abe4b7c0f2cbe8",
        7_277,
        "0644",
    ),
    frozen(
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py",
        "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b",
        54_352,
        "0644",
    ),
    frozen(
        "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py",
        "5d9b3b983137f1986279c4c7b6f9a926658228b87a6e259627c25be57e751714",
        24_012,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition_v1.py",
        "ca1cb2a766c4fcb4c6d1cec036352ff0529400554006e8129af4f9eb30f1be2a",
        25_604,
        "0644",
    ),
    frozen(
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave3_v1_once.py",
        "df814f53063392d872f6523dca2b60fe33c91cd2f907e23d5257eccd1db7d5b6",
        43_029,
        "0644",
    ),
]
ACQUISITION_CLAIM = frozen(
    ACQUISITION_CLAIM_PATH,
    "999587886ba015e2c008385df68e7c2ce9c622d18e493a5a45615db5b6db8629",
    416,
    "0600",
)
FINAL_DIRECTORY = {
    "path": FINAL_ROOT,
    "mode": "0700",
    "ownerUid": 501,
    "linkCount": 4,
    "exactEntries": ["accepted", "evidence.json"],
}
ACCEPTED_DIRECTORY = {
    "path": ACCEPTED_ROOT,
    "mode": "0700",
    "ownerUid": 501,
    "linkCount": 34,
    "exactFileCount": 32,
}
EVIDENCE_FILE = frozen(
    EVIDENCE_PATH,
    "3a1af1bc9468817dde925661ad506c5522c83c68c53058e0f200a05d1705a762",
    12_697,
    "0600",
)


_ACCEPTED_ROWS = [
    ("001-3d0c2194ff45cb046eed.mod", "e7c7669d4a1dd589ba3e024ba27f43f293db611fe075ce20d7b884370d63febd", 41),
    ("001-3d0c2194ff45cb046eed.zip", "4b4e9bf6c48211080651b491dfb48d68b736c66a305bcf94605606e1ba2eaa4a", 129_773),
    ("002-66ac9e16151b89ea310c.mod", "cb326540efcb1274a6e4e970d7fc9de2e8062f08a058fc296d859025e62e807a", 85),
    ("002-66ac9e16151b89ea310c.zip", "1a00b3bb5ad41cb72634ace06b7eb7df857404d77a7cab4e401a7c729561fe4c", 44_362),
    ("003-cbcfb285b10903409cd4.mod", "ee7fe4466203a01d3ac19adc134cdec99bc6de71992c28f3dd9a74480bff0603", 41),
    ("003-cbcfb285b10903409cd4.zip", "bb41a602b174345fda392c8ad83fcc93217c285c763699677630be90feb7a5e3", 229_017),
    ("004-370465550e93fc46d02b.mod", "89305830a1cd4c1c42601b8d22b7f37b5166a092823fd195e9d41e79ac56d11e", 192),
    ("004-370465550e93fc46d02b.zip", "5f2921ccdf7252ffbe26046948c6044ab0917e500a34710e0ba6664260d6a460", 2_223_740),
    ("005-052e10bed8fa86ef5bc5.mod", "5c4ac0310a25330757039ccf3a98e75fefdbcb7d444ddd049230003a44945bde", 84),
    ("005-052e10bed8fa86ef5bc5.zip", "a72fe5b79554a8993df9512d05e237908d3ad0b48001c1ab92b7fa5339ecf440", 165_172),
    ("006-dd9ee19885a5f9f824d3.mod", "0eef3e9fe7f668be5b4d24c8f1251c6c502d1168953c8081ac9dc3f399c64f06", 155),
    ("006-dd9ee19885a5f9f824d3.zip", "4e9cb4bded1957e73fe709741c29879eab05047617c9b14b7237314ff9024913", 1_868_726),
    ("007-e57403db334cc016a4c0.mod", "700e5db00dd26aa19a17dce5fc552436d60f68c5606c85b821f24c3d6072a151", 34),
    ("007-e57403db334cc016a4c0.zip", "94ea75ea625ecb8d81ab473a2d7e03433e63083768cd27d48a03f8c1c9da3d8d", 26_934),
    ("008-5d261a812d24f668c214.mod", "700e5db00dd26aa19a17dce5fc552436d60f68c5606c85b821f24c3d6072a151", 34),
    ("008-5d261a812d24f668c214.zip", "0906a8026217a4e31c30ea5fc2514f18fc13480c62fe6bfae7a57e7ce0313de9", 26_960),
    ("009-30743249da916d4d998f.mod", "f411814d83a96e86781b1dee41c125b9504da5422dba37cc1d63b016ae39cfe2", 35),
    ("009-30743249da916d4d998f.zip", "65444efd299ce78bc457588bc2061e69fb5ceadec70220eeda39657402ad4b1b", 2_003_190),
    ("010-7cbea927c20c50f2a1de.mod", "b0ba178180a686d4a0f5421a59fe3c25ab80cfe056277eb50e460939e94a2653", 133),
    ("010-7cbea927c20c50f2a1de.zip", "d72f400df09038546866bb70f35f79de254a8610826e3f087c7cbc2d9e852a87", 1_017_825),
    ("011-1d20c42eae6fe0384f84.mod", "9aea1c46f945812996f9eb66daeceef749e49fddff1d6402d6523de50fe99f35", 133),
    ("011-1d20c42eae6fe0384f84.zip", "c1e4362e01a81acb6c71452ce40302608628a7c11ad4d63e4cbc4c0062efa269", 1_017_976),
    ("012-cf4ecf07d97219c9e736.mod", "cbd467d0bff5b8681473eea51abcae91727adce37618d9ad9760babf97ad9a6c", 70),
    ("012-cf4ecf07d97219c9e736.zip", "00cec8beae98bb5a15c9ee9e8e705b7cab9c50269e7858bff98df0533b317363", 21_158),
    ("013-1890d1a8d1b4918c8624.mod", "b48867b19ec17888bcec2ca36add98973bd262e5a94f973104db32d68a16989a", 190),
    ("013-1890d1a8d1b4918c8624.zip", "bc6c70d37c37bc625a83abd48ee32372b459a8c559a1cf5f25dfbf7c7941f81b", 9_236_390),
    ("014-32f1ec99ae53325aa940.mod", "226a6cc982bae02ff1e168de8c3e45a2f3f986c69edbc1f416c58b6081ef262e", 34),
    ("014-32f1ec99ae53325aa940.zip", "7420a12017bb47bd85ccab81f9d1f7a3ff6daf8da768256292bc1dbb3bf9ba63", 14_927),
    ("015-c97ec7349de82704c109.mod", "4525dad4f5723d1e409f6a398c1ae7fd5e2c637d43a5caeb49844077b91c9eeb", 339),
    ("015-c97ec7349de82704c109.zip", "80beec66ba124d6d097ac4ee77e54db0ecd47ecc9bf3474a04c81f4e8fd2dd4a", 3_236_577),
    ("016-61750643721566e1a4fc.mod", "b479807449df634074dd08e8e15065ed90bb91e123a1664e4ef34ca07fd4c0ac", 301),
    ("016-61750643721566e1a4fc.zip", "498ead1f3de646754a152c14fcaade9b03f86114b2746b65367e3540c1acbcde", 2_854_184),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "65c123fc7d256c670e5e1eba01470f26c8b2ca23d52ce31236841dcb78cae2fe",
    1_321,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "3132c743399611314aa8f6dce80f4864da25920f0ab9570136301cfb64716312",
    463,
    "0600",
)
ALL_FROZEN_FILES = [
    *ACQUISITION_AUTHORITY,
    ACQUISITION_CLAIM,
    EVIDENCE_FILE,
    *ACCEPTED_FILES,
    ACQUISITION_RECEIPT,
    ACQUISITION_MANIFEST,
]


class PermitError(RuntimeError):
    def __init__(self, code: str, state: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.state = state


def require(value: bool, code: str) -> None:
    if not value:
        raise PermitError(code)


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
            parse_float=lambda _: (_ for _ in ()).throw(PermitError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(PermitError("E_JSON")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermitError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    require("contentBinding" not in payload, "E_CONTENT")
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def verify_bound(raw: bytes, expected: Mapping[str, Any]) -> None:
    observed = strict_json(raw)
    require(raw == canonical_bytes(observed) and observed == expected, "E_PERMIT")
    binding = observed["contentBinding"]
    unbound = dict(observed)
    del unbound["contentBinding"]
    require(
        binding
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": sha256(canonical_bytes(unbound)),
        },
        "E_CONTENT",
    )


def stable_read(path: str) -> bytes:
    current = ROOT
    for component in path.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_PATH",
        )
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= O_NOFOLLOW
    fd = os.open(ROOT / path, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_PACKAGE_FILE_BYTES,
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
        raw = b"".join(chunks)
        require(os.fstat(fd) == before, "E_CHANGED")
        return raw
    finally:
        os.close(fd)


def normalized_recorder(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    pattern = re.compile(r'EXPECTED_READBACK_CHECKER_RAW = "[0-9a-f]{64}"')
    require(len(pattern.findall(text)) == 1, "E_RECORDER")
    return pattern.sub(
        'EXPECTED_READBACK_CHECKER_RAW = "' + "0" * 64 + '"',
        text,
        count=1,
    ).encode()


def validate_recorder(recorder_raw: bytes, checker_raw: bytes) -> None:
    try:
        source = recorder_raw.decode("utf-8", errors="strict")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise PermitError("E_RECORDER") from error
    imports: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
    forbidden = {
        "http",
        "socket",
        "ssl",
        "urllib",
        "requests",
        "subprocess",
        "importlib",
        "runpy",
    }
    require(not imports.intersection(forbidden), "E_RECORDER")
    require(
        not any(
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave4" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition"
            in name
            for name in imports
        ),
        "E_RECORDER",
    )
    require(
        {
            "load_readback_checker",
            "create_readback_claim",
            "verify_snapshot",
            "validate_mod",
            "validate_zip",
            "atomic_publish",
            "preflight",
            "execute",
        }
        <= functions,
        "E_RECORDER",
    )
    for token in (
        "http.client",
        "HTTPSConnection",
        "urlopen",
        "socket.",
        "subprocess",
        "os.system",
    ):
        require(token not in source, "E_RECORDER")
    for token in (
        "os.O_EXCL",
        "O_NOFOLLOW",
        "os.fsync",
        "renameatx_np",
        "ZIP_CENTRAL_HEADER",
        "zlib.decompressobj",
    ):
        require(token in source, "E_RECORDER")
    pin = re.findall(
        r'EXPECTED_READBACK_CHECKER_RAW = "([0-9a-f]{64})"',
        source,
    )
    require(pin == [sha256(checker_raw)], "E_RECORDER")
    require(
        sha256(normalized_recorder(recorder_raw))
        == EXPECTED_RECORDER_NORMALIZED_SHA256,
        "E_RECORDER",
    )


def package_raw(include_permit: bool) -> dict[str, bytes]:
    paths = [
        READER_PATH,
        THIS_CHECKER_PATH,
        THIS_TESTS_PATH,
        RECORDER_PATH,
        RECORDER_TESTS_PATH,
    ]
    if include_permit:
        paths.append(PERMIT_PATH)
    return {path: stable_read(path) for path in paths}


def frozen_snapshot_payload() -> dict[str, Any]:
    frozen_canonical = [
        *ACQUISITION_AUTHORITY,
        ACQUISITION_CLAIM,
        EVIDENCE_FILE,
        *ACCEPTED_FILES,
        ACQUISITION_RECEIPT,
        ACQUISITION_MANIFEST,
    ]
    return {
        "attemptId": ATTEMPT_ID,
        "acquisitionAuthority": ACQUISITION_AUTHORITY,
        "acquisitionDecisionContentSha256": EXPECTED_DECISION_CONTENT,
        "acquisitionPermitContentSha256": EXPECTED_ACQUISITION_PERMIT_CONTENT,
        "identityBindings": {
            "sourceRequestSetCanonicalSha256": (
                EXPECTED_SOURCE_REQUEST_SET_CANONICAL
            ),
            "compactIdentitySha256": EXPECTED_COMPACT_IDENTITY,
            "fullWitnessSha256": EXPECTED_FULL_WITNESS,
            "heldSourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
        },
        "acquisitionClaim": ACQUISITION_CLAIM,
        "finalDirectory": FINAL_DIRECTORY,
        "evidence": EVIDENCE_FILE,
        "acceptedDirectory": {
            **ACCEPTED_DIRECTORY,
            "files": ACCEPTED_FILES,
        },
        "acquisitionReceipt": ACQUISITION_RECEIPT,
        "acquisitionManifest": ACQUISITION_MANIFEST,
        "absenceContract": {
            "failurePath": ACQUISITION_FAILURE_PATH,
            "stagingParent": DEPENDENCY_ROOT,
            "stagingPrefix": STAGING_PREFIX,
            "failureAbsent": True,
            "stagingAbsent": True,
        },
        "frozenFileCount": len(frozen_canonical),
        "frozenFilesCanonicalSha256": sha256(canonical_bytes(frozen_canonical)),
        "aggregateModBytes": 1_901,
        "aggregateZipBytes": 24_116_911,
        "aggregateAcceptedBytes": 24_118_812,
        "aggregateZipEntryCount": 5_936,
        "aggregateZipUncompressedBytes": 87_874_800,
        "acceptedResourceCount": 32,
        "selectedTupleCount": 3,
        "modCount": 16,
        "zipCount": 16,
    }


def expected_payload_from_package(raw: Mapping[str, bytes]) -> dict[str, Any]:
    require(sha256(raw[READER_PATH]) == EXPECTED_READER_RAW, "E_READER")
    validate_recorder(raw[RECORDER_PATH], raw[THIS_CHECKER_PATH])
    tools = [
        {"path": path, "rawSha256": sha256(raw[path])}
        for path in (
            THIS_CHECKER_PATH,
            THIS_TESTS_PATH,
            RECORDER_PATH,
            RECORDER_TESTS_PATH,
        )
    ]
    return {
        "documentType": (
            "aetherlink.wave4-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave4-source-acquisition-readback-"
            "execution-permit-v1"
        ),
        "recordedDate": "2026-07-25",
        "status": "authorized_not_consumed",
        "frozenAcquisitionSnapshot": frozen_snapshot_payload(),
        "verificationContract": {
            "claimDurableBeforeAnyFrozenAcquisitionInputOpen": True,
            "authorityFilesOpenedAndHeldFirst": True,
            "allFrozenFilesOpenedNoFollowAndHeld": True,
            "retainedProjectRootCurrentPathIdentityRequired": True,
            "everyBarrierReopensEveryCurrentPathNoFollow": True,
            "currentPathDeviceAndInodeMustMatchHeldObject": True,
            "readbackClaimHeldThroughManifestPublication": True,
            "claimCreationFdContinuouslyHeldThroughManifestPublication": True,
            "claimCurrentNameMustMatchCreationDeviceAndInode": True,
            "readbackReceiptHeldThroughManifestPublication": True,
            "publishedOutputsReopenedAndVerifiedBeforePublishReturns": True,
            "pathSha256BytesModeOwnerAndLinkCountRequired": True,
            "exactFinalAndAcceptedDirectoryInventoriesRequired": True,
            "strictCanonicalTerminalAndEvidenceJsonRequired": True,
            "decisionAndPermitContentBindingsRecomputed": True,
            "attemptAndAuthorityBindingsRecomputed": True,
            "exact32ResourceOrderAndAggregateRecomputed": True,
            "exact48FrozenFileSnapshotRequired": True,
            "identityAndSourceRequestSetBindingsRecomputed": True,
            "goModH1RecomputedIndependently": True,
            "moduleZipH1RecomputedIndependently": True,
            "zipStructurePathCrcAndModParityRecomputed": True,
            "completeVerificationPassCount": 2,
            "retainedFdPublicationBarrierCount": 3,
            "retainedFdPublicationBarriers": [
                "complete_snapshot_and_claim_immediately_before_receipt",
                "complete_snapshot_claim_and_receipt_after_receipt",
                "complete_snapshot_claim_and_receipt_immediately_before_manifest",
            ],
            "allRequiredPublicationBarriersCompleteBeforeManifest": True,
            "requiredFallibleBarrierAfterManifest": False,
            "acquisitionCheckerOrRunnerImportAllowed": False,
            "acquisitionCheckerOrRunnerInvocationAllowed": False,
            "sourceExtractionAllowed": False,
        },
        "oneUseConsumption": {
            "claimPath": READBACK_CLAIM_PATH,
            "claimCreatedOExclNoFollow0600AndFsynced": True,
            "claimParentFsyncedBeforeFrozenInputOpen": True,
            "claimCreatedReadWriteAndCreationFdTransferredToHold": True,
            "claimPersistsAfterSuccessFailureOrUncertainty": True,
            "existingClaimState": "already_consumed",
            "claimDurabilityAmbiguityState": "consumed_terminal_state_uncertain",
            "secondExecutionAllowed": False,
            "retryAllowed": False,
            "resumeAllowed": False,
            "replacementAllowed": False,
            "backfillAllowed": False,
            "namespaceStates": {
                "claimOnly": "claim_only",
                "receiptOnly": "receipt_only",
                "complete": "complete",
                "inconsistent": "inconsistent",
                "staleTemporary": "stale_temporary_namespace",
            },
        },
        "outputContract": {
            "receiptPath": READBACK_RECEIPT_PATH,
            "manifestPath": READBACK_MANIFEST_PATH,
            "receiptWrittenBeforeManifest": True,
            "manifestWrittenLast": True,
            "atomicNoReplaceRequired": True,
            "fileMode": "0600",
            "fileAndParentFsyncRequired": True,
            "ordinaryFailurePublishesSuccess": False,
            "failureOutputAuthorized": False,
            "receiptOnlyGapState": "consumed_terminal_state_uncertain",
            "publicationDurabilityAmbiguityState": (
                "consumed_terminal_state_uncertain"
            ),
            "temporaryNamePrefixes": READBACK_TEMP_PREFIXES,
            "preflightRejectsAnyStaleTemporaryName": True,
            "manifestPublicationBeginsAfterAllRequiredBarriers": True,
            "fallibleFrozenClaimOrReceiptBarrierAfterManifest": False,
            "publicationOrder": [
                "rename_no_replace",
                "parent_directory_fsync",
                "final_name_no_follow_reopen_and_source_inode_verification",
                "return",
            ],
        },
        "resourceLimits": {
            "maximumPackageFileBytes": MAXIMUM_PACKAGE_FILE_BYTES,
            "maximumAcceptedResourceCount": 32,
            "maximumModBytes": 1_048_576,
            "maximumZipBytes": 16_777_216,
            "maximumAggregateAcceptedBytes": 134_217_728,
            "maximumZipEntries": 20_000,
            "maximumZipEntryNameBytes": 1_024,
            "maximumZipEntryBytes": 134_217_728,
            "maximumZipUncompressedBytes": 134_217_728,
        },
        "authority": {
            "offlineReadbackAuthorizedOnce": True,
            "readbackClaimWriteAuthorized": True,
            "readbackReceiptWriteAuthorized": True,
            "readbackManifestWriteAuthorized": True,
            "sameDirectoryTemporaryPublicationAuthorized": True,
            "failedTemporaryCleanupAuthorized": True,
            "otherRepositoryWritesAuthorized": False,
            "frozenInputWritesAuthorized": False,
            "networkAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "proxyAuthorized": False,
            "authenticationRequired": False,
            "credentialRequired": False,
            "externalAuthenticationRequired": False,
            "repositoryOwnerIdentityProofRequired": False,
            "passwordRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
            "sourceAcquisitionAuthorized": False,
            "sourceExtractionAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "userActionRequired": False,
        },
        "interpreterContract": {
            "command": [
                "python3",
                "-I",
                "-B",
                "-S",
                RECORDER_PATH,
                "--execute",
            ],
            "isolated": True,
            "sitePackagesAllowed": False,
            "environmentOverridesAllowed": False,
            "bytecodeWritesAllowed": False,
            "processUmask": "077",
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW,
        },
        "toolBindings": tools,
        "recorderNormalizedSha256": EXPECTED_RECORDER_NORMALIZED_SHA256,
        "result": "exact_offline_wave4_acquisition_readback_authorized_not_consumed",
        "nextAction": "execute_bound_offline_readback_once",
        "nonClaims": [
            "this permit does not authorize another source acquisition",
            "readback success is not source review or dependency closure",
            "readback success is not library selection release approval or V1 completion",
            (
                "the standalone live permit checker is a sequential diagnostic, "
                "not an atomic concurrent snapshot; execution safety relies on "
                "the recorder retained-FD and current-path barriers"
            ),
        ],
    }


def expected_package(include_permit: bool) -> tuple[dict[str, Any], dict[str, bytes]]:
    raw = package_raw(include_permit)
    return content_bound(expected_payload_from_package(raw)), raw


def _audit_file(spec: Mapping[str, Any]) -> None:
    path = ROOT / spec["path"]
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_size == spec["bytes"]
            and stat.S_IMODE(before.st_mode) == int(spec["mode"], 8)
            and before.st_uid == spec["ownerUid"]
            and before.st_nlink == spec["linkCount"],
            "E_FROZEN",
        )
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_READ")
            digest.update(chunk)
            remaining -= len(chunk)
        require(
            not os.read(fd, 1)
            and digest.hexdigest() == spec["rawSha256"]
            and os.fstat(fd) == before,
            "E_FROZEN",
        )
    finally:
        os.close(fd)


def _audit_directory(spec: Mapping[str, Any], expected: set[str]) -> None:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    flags |= O_NOFOLLOW
    fd = os.open(ROOT / spec["path"], flags)
    try:
        info = os.fstat(fd)
        require(
            stat.S_ISDIR(info.st_mode)
            and stat.S_IMODE(info.st_mode) == int(spec["mode"], 8)
            and info.st_uid == spec["ownerUid"]
            and info.st_nlink == spec["linkCount"]
            and set(os.listdir(fd)) == expected,
            "E_INVENTORY",
        )
    finally:
        os.close(fd)


def audit_frozen_snapshot() -> None:
    for spec in ALL_FROZEN_FILES:
        _audit_file(spec)
    _audit_directory(FINAL_DIRECTORY, set(FINAL_DIRECTORY["exactEntries"]))
    accepted_names = {Path(row["path"]).name for row in ACCEPTED_FILES}
    _audit_directory(ACCEPTED_DIRECTORY, accepted_names)
    require(not os.path.lexists(ROOT / ACQUISITION_FAILURE_PATH), "E_TERMINAL")
    dependency = ROOT / DEPENDENCY_ROOT
    require(
        not any(path.name.startswith(STAGING_PREFIX) for path in dependency.iterdir()),
        "E_TERMINAL",
    )


def readback_namespace_state(root: Path = ROOT) -> str:
    claim = os.path.lexists(root / READBACK_CLAIM_PATH)
    receipt = os.path.lexists(root / READBACK_RECEIPT_PATH)
    manifest = os.path.lexists(root / READBACK_MANIFEST_PATH)
    names = os.listdir(root / BASE)
    if any(
        name.startswith(prefix)
        for name in names
        for prefix in READBACK_TEMP_PREFIXES
    ):
        return "stale_temporary_namespace"
    if not claim and not receipt and not manifest:
        return "absent"
    if claim and not receipt and not manifest:
        return "claim_only"
    if claim and receipt and not manifest:
        return "receipt_only"
    if claim and receipt and manifest:
        return "complete"
    return "inconsistent"


def readback_namespace_absent(root: Path = ROOT) -> None:
    state = readback_namespace_state(root)
    if state != "absent":
        raise PermitError("E_CONSUMED", state)


def package_preflight_for_recorder() -> dict[str, Any]:
    """Validate only the readback package and reserved names, not frozen inputs."""
    expected, raw = expected_package(True)
    verify_bound(raw[PERMIT_PATH], expected)
    readback_namespace_absent()
    return {
        "permit": expected,
        "permitRawSha256": sha256(raw[PERMIT_PATH]),
        "permitContentSha256": expected["contentBinding"]["sha256"],
        "checkerRawSha256": sha256(raw[THIS_CHECKER_PATH]),
        "recorderRawSha256": sha256(raw[RECORDER_PATH]),
        "frozenAcquisitionInputOpened": False,
        "networkRequestAttemptCount": 0,
    }


def evaluate(verify_disk: bool, verify_frozen: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    expected, raw = expected_package(verify_disk)
    if verify_disk:
        verify_bound(raw[PERMIT_PATH], expected)
    readback_namespace_absent()
    if verify_frozen:
        audit_frozen_snapshot()
    return expected, {
        "documentType": "aetherlink.wave4-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 12,
        "acceptedResourceCount": 32,
        "selectedTupleCount": 3,
        "aggregateAcceptedBytes": 24_118_812,
        "aggregateZipEntryCount": 5_936,
        "aggregateZipUncompressedBytes": 87_874_800,
        "frozenSnapshotVerified": verify_frozen,
        "readbackClaimExists": False,
        "networkRequestAttemptCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise PermitError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--preflight", action="store_true")
        group.add_argument("--package-only", action="store_true")
        group.add_argument("--print-permit", action="store_true")
        args = parser.parse_args(argv)
        if args.package_only:
            result = package_preflight_for_recorder()
        else:
            permit, summary = evaluate(
                verify_disk=not args.print_permit,
                verify_frozen=not args.print_permit,
            )
            result = permit if args.print_permit else summary
        sys.stdout.buffer.write(canonical_bytes(result))
        return 0
    except PermitError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": "aetherlink.wave4-acquisition-readback-permit-error",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "networkAuthorized": False,
                    "fileWriteAuthorized": False,
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
                    "documentType": "aetherlink.wave4-acquisition-readback-permit-error",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "networkAuthorized": False,
                    "fileWriteAuthorized": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
