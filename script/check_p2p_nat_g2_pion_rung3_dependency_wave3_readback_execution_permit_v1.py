#!/usr/bin/env python3
"""Validate the one-use offline Wave3 acquisition readback permit."""

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
    raise RuntimeError("Wave3 readback checker requires `python3 -I -B -S`")

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
    raise RuntimeError("Wave3 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave3_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave3_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-3-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave3-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave3-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-3-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-3-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-failure-v1.json"
)
STAGING_PREFIX = ".wave-3-v1-staging-"
ATTEMPT_ID = "47d76c38d865e40c7f16961c6fe8b31a"
EXPECTED_DECISION_CONTENT = (
    "0ae8b961c0aada02c3a10a9fae231e03baa7d23928abf5b14488d30b88c9de78"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "a93ca38a634153feda1479fd93963b08811d20df90d7300c5bf9216c7cb66548"
)
EXPECTED_READER_RAW = "a045987d06026ecea18ed0baf93a04c00c7b86fc1acf291613a505e362190a55"
EXPECTED_RECORDER_NORMALIZED_SHA256 = "17fb6ddd0d59db04eb300d0d5bf36f39f237340b491bff27e10b2edea418e351"
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
        f"{BASE}/bounded-dependency-source-acquisition-wave3-decision-v1.md",
        "3ea8982d4d7b552eacf351ad9261b33f5aa54242022923f77ae19b12f3951ae5",
        894,
        "0644",
    ),
    frozen(
        f"{BASE}/bounded-dependency-source-acquisition-wave3-decision-v1.json",
        "05ecc22e13fab8a0b213d27d17b4a728fa5bc8bebd088b2b2a7204fdedc03071",
        18_985,
        "0644",
    ),
    frozen(
        f"{BASE}/bounded-dependency-source-acquisition-wave3-execution-permit-v1.md",
        "9a66ffadad94742208681b1b67123ecff9b7fdfdc8c980ff5008efce544fc6d9",
        3_012,
        "0644",
    ),
    frozen(
        f"{BASE}/bounded-dependency-source-acquisition-wave3-execution-permit-v1.json",
        "8c3c0b56f96e856b7098d414f46294c9d587da7525222d8b2b707a730c12f657",
        19_869,
        "0644",
    ),
    frozen(
        "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition_v1.py",
        "ca1cb2a766c4fcb4c6d1cec036352ff0529400554006e8129af4f9eb30f1be2a",
        25_604,
        "0644",
    ),
    frozen(
        "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition_v1.py",
        "db394321581b5e2f9ef7e3f67050576e5866c7a19eedc914226fe16ed9bad1b4",
        8_285,
        "0644",
    ),
    frozen(
        "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave3_v1_once.py",
        "df814f53063392d872f6523dca2b60fe33c91cd2f907e23d5257eccd1db7d5b6",
        43_029,
        "0644",
    ),
    frozen(
        "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave3_v1_once.py",
        "af71726ff01233ac315c88f29d7f0d2ae0026ac1bf433c2fd084edce16daa819",
        34_154,
        "0644",
    ),
]
ACQUISITION_CLAIM = frozen(
    ACQUISITION_CLAIM_PATH,
    "a2bd2ceda89172fd1fbe5d578abf4e3239a8712aacbcd7ca65a666d5d8861692",
    350,
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
    "49dae7e5820452509de78179cfb6cc5700eba90e5974d1cfae6df013b03f8858",
    12_445,
    "0600",
)


_ACCEPTED_ROWS = [
    ("001-7d131ac8caff7db202b0.mod", "6da4c9c7364446894e5ef877e19f985cd51d671ce6e8f4ca87862b449f6dd7f6", 25),
    ("001-7d131ac8caff7db202b0.zip", "10474d7a875cbd2b9d74c9bb8fb99264b7863f204c7610607797ff18d580bf00", 14_199),
    ("002-aa9ea6f942228c249daf.mod", "7e8b6a9c16e30843f7f7962742c7b435b83b8d039cee052ac53651d2e5368a17", 384),
    ("002-aa9ea6f942228c249daf.zip", "0388cdbc1a1b101d1e726a221de442c4868f458b5be04950c6f0f712e3c63477", 154_242),
    ("003-93b04ce10c46c5cb73e5.mod", "05e26cd069285a33cf2af46fdacdef569d5ae185e7963a76c0178328f68e97f9", 188),
    ("003-93b04ce10c46c5cb73e5.zip", "e206daaede0bd03de060bdfbeb984ac2c49b83058753fffc93fe0c220ea87532", 120_537),
    ("004-62af64e1ee2b256ded1a.mod", "3fd4eb73b16b0075765c7cb518da5350b48e923a324a36ca70bef89c17d331d5", 190),
    ("004-62af64e1ee2b256ded1a.zip", "959d6b2fb5ee7d50113a0cb26dbdd8fa06710d4e97fae709be2d2755e827ede7", 1_792_521),
    ("005-7c4f2aef071992f46502.mod", "f6dad481462711b0c41f147aa175087f3656591c59336242fdc9fae95d0fc59e", 190),
    ("005-7c4f2aef071992f46502.zip", "3b0c19c1d259e93464f540165470de872721e5fc66ce3f0d36ffd27d307ec5bb", 1_793_598),
    ("006-afb6d23d14b0548725f4.mod", "1ec2b9183f0adf8dc4d6d5dffb6eaece5457f5fb88fa3e8843941389e72f2977", 86),
    ("006-afb6d23d14b0548725f4.zip", "9b43daca51525bd50289c742999fe66336a653c90a23d2c55561b6fffd656e46", 172_422),
    ("007-35842467dc0e55a77ea1.mod", "841f7e156252cbae1db18f2b7f48b522af1cf0d3cf8fa3710390dd156657c885", 86),
    ("007-35842467dc0e55a77ea1.zip", "c0fcee2c1ef1a0a817e81056342bc6cb8b12d11be1addfe3ba87434a2e3044cf", 172_421),
    ("008-3d77358abcf59344b938.mod", "6c73f852a18bfd280a960e8dae1fa9192c3d3c55f199371faedff56b666747d5", 157),
    ("008-3d77358abcf59344b938.zip", "cf5206797e66bbe72fc13542d53a57d069a563cebb6d045c07a870eb4fd888c9", 1_935_796),
    ("009-1964b534f94c4bf17e91.mod", "d333c54b74af8a0b8ec748d37c5972d27b9d088b9e45c8bf5c3ab520d2113090", 36),
    ("009-1964b534f94c4bf17e91.zip", "25211fe2cffd8020bb405b9adb7a90f5e06760f2818b8fb2e74aaaa21a66ed9e", 25_714),
    ("010-4c6f0fb13283f2a9381b.mod", "d227b325f621f4ebe28d39ba773ea99b870f393b7c09c34592c365b16dd560de", 33),
    ("010-4c6f0fb13283f2a9381b.zip", "1d759c017d09328a4dacdd4a1a0170cf21641995c6e3ca1f96213369d73c6846", 1_983_637),
    ("011-b391a061f64831b69e0a.mod", "147d1695aedd7e89544bc821b911608903547070e6a4d6b8ac658b718a51bee6", 68),
    ("011-b391a061f64831b69e0a.zip", "ede5a49eac0946d10051703fa19f9f05c4cac3a217e55b7313e24b6c15ade914", 19_810),
    ("012-56e059019f24550b949e.mod", "d9fe2c313121a1a0f1ea8028e6c4bfbd8afbd8f34e67eacfd2d1d37964a4c89d", 68),
    ("012-56e059019f24550b949e.zip", "9d92c583d222113ac653848b3319ff559d2dba92f8232baff03d08fc9c0b8619", 19_810),
    ("013-1f378c3582c8000916fa.mod", "c015af74697b915ad4190be27cf6f5bbe02a158accef0dbcd4a42a10002df496", 221),
    ("013-1f378c3582c8000916fa.zip", "be3db791651af6f2cb0225aa5d5578c23149b2017246ba8e59586080baadd612", 9_233_989),
    ("014-95efdd30141dce84bd92.mod", "b26a1f71dc41b9992bafec38867987652d1293d046c652df549eed687149d862", 221),
    ("014-95efdd30141dce84bd92.zip", "939cb4c202aa8fa302f2ba6f9d29165ce82fce9c665d9a1a0bb0d9e51b79e6f5", 9_233_999),
    ("015-53735f6a9d44c4e909ce.mod", "c75122d17c58778ae79480a393bbe3281820a0fb9cca327fee767108f43e2de2", 301),
    ("015-53735f6a9d44c4e909ce.zip", "5b8ea096f9184a9df7a4852818ea35d9f9a8f50b68a5558f5078f23a39459780", 2_873_030),
    ("016-646df04c323b6f489013.mod", "1fb6786f6acfe1a5e80fee4f9c9957735e771dab52cf516ed412ab1b4b794ccf", 301),
    ("016-646df04c323b6f489013.zip", "7cc6adbaad471e4a1850cace50c56227f78b06a077f0e9154b27e23e199d7a84", 2_876_850),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "c0d1c4a4c7a658418976446237e45e0f3955fcc600f8c5b82b51295313e14f18",
    1_172,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "7e1508a1fbd6e927377a1aeb709ffe44f484efcabe95c7fb739db42b56207552",
    451,
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
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave3" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition"
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
        "aggregateModBytes": 2_555,
        "aggregateZipBytes": 32_422_575,
        "aggregateAcceptedBytes": 32_425_130,
        "acceptedResourceCount": 32,
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
            "aetherlink.wave3-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave3-source-acquisition-readback-"
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
        "result": "exact_offline_wave3_acquisition_readback_authorized_not_consumed",
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
        "documentType": "aetherlink.wave3-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 8,
        "acceptedResourceCount": 32,
        "aggregateAcceptedBytes": 32_425_130,
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
                    "documentType": "aetherlink.wave3-acquisition-readback-permit-error",
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
                    "documentType": "aetherlink.wave3-acquisition-readback-permit-error",
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
