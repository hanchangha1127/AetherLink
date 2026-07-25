#!/usr/bin/env python3
"""Validate the one-use offline Wave5 acquisition readback permit."""

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
    raise RuntimeError("Wave5 readback checker requires `python3 -I -B -S`")

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", None)
if O_NOFOLLOW is None:
    raise RuntimeError("Wave5 readback checker requires O_NOFOLLOW")
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "readback-execution-permit-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "readback-execution-permit-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave5_"
    "readback_execution_permit_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave5_"
    "readback_execution_permit_v1.py"
)
RECORDER_PATH = (
    "script/record_p2p_nat_g2_pion_rung3_dependency_wave5_"
    "readback_v1_once.py"
)
RECORDER_TESTS_PATH = (
    "script/test_record_p2p_nat_g2_pion_rung3_dependency_wave5_"
    "readback_v1_once.py"
)
READBACK_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-5-v1-readback.claim"
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-"
    "readback-manifest-v1.json"
)
READBACK_TEMP_PREFIXES = [
    ".bounded-dependency-source-acquisition-wave5-readback-v1.json.tmp-",
    (
        ".bounded-dependency-source-acquisition-wave5-readback-"
        "manifest-v1.json.tmp-"
    ),
]
ACQUISITION_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-5-v1.claim"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-5-v1"
ACCEPTED_ROOT = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
ACQUISITION_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-receipt-v1.json"
)
ACQUISITION_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-manifest-v1.json"
)
ACQUISITION_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave5-failure-v1.json"
)
STAGING_PREFIX = ".wave-5-v1-staging-"
ATTEMPT_ID = "ed050bd13835ab1f9fecc0dd3cfb6e12"
EXPECTED_DECISION_CONTENT = (
    "042360fe15b03240341e4f7e80aa59b630dbc6647ea3d05f4980881e09a6f912"
)
EXPECTED_ACQUISITION_PERMIT_CONTENT = (
    "215e422bf431cca958086116efc8e712ef5c2b0b64ad5f84950939c66176144e"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "1197fd5d5e7f6bdaccb3b4538fd999bc4995fe34890cd8472f3df68fa00b0fae"
)
EXPECTED_COMPACT_IDENTITY = (
    "52567cdead3fcd8029f9c1676a7f83af86a5d0110c52851b47e55b2f09af8a7d"
)
EXPECTED_FULL_WITNESS = (
    "af51e067ccf3388561bfe0e2b38dae744792625cdc5f7a37b55208b41d4a5fb4"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "025e9a401eda9fac4687ed4c2cdbefd07a0b0489d31c1b43fe9744350579ff78"
)
EXPECTED_ACCEPTED_RESOURCE_HASH_SET = (
    "b929d977644f7502a27340f2817957a95fb0ddcc885ee9222a525132939fa226"
)
EXPECTED_READER_RAW = "9d4d32d022e74c16f47eb2f38a3171f7a7fe54bed1d314e52f60f72ca43cc551"
EXPECTED_RECORDER_NORMALIZED_SHA256 = "575b8da3736bd9b7d3ea69323c9e30e904130aaa81fd2caea7ceedd95f7b48fd"
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
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave5-v1.json',
        'fb2d6ec8e29f50e7d6198d452366cce98c4414e4d7a409634ad1daffe02d195e',
        27_719,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-identity-and-acquisition-decision-wave5-v1.md',
        'ce974c3590a40db23a54cd450dbf7282fb1cd172fc416cfcb8aeabd3ab86956c',
        1_406,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave5_decision_v1.py',
        'db5ef0a6477282c6a8d97d582b785f6dfbb9c9a10831456964e02981a46e8d2e',
        58_520,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave5_decision_v1.py',
        '6e580c5d96f3ea5870f07ed94cdcbd6bb1736b523ee851faea3ecf8e2477e5e2',
        25_637,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-execution-permit-v1.md',
        '1da05139619a7aa017d33aa2b082154de25cdc665246941db630433321833ebf',
        2_157,
        "0644",
    ),
    frozen(
        'docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1/rung-three/bounded-dependency-source-acquisition-wave5-execution-permit-v1.json',
        '9a99858e73a0c6bf8142ce8d3927abb84cf2290dfd0b595ea818ed5ad423fd49',
        26_303,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave5_acquisition_v1.py',
        '0e004d35822f41a2ffa271c5175bdde5a51a786fb86965de320d23a2227f129f',
        34_771,
        "0644",
    ),
    frozen(
        'script/test_p2p_nat_g2_pion_rung3_dependency_wave5_acquisition_v1.py',
        '1b066ee09ec1760df8ba68cd88a2059901e7be709ce0694bf2d10a51a28c7f40',
        10_549,
        "0644",
    ),
    frozen(
        'script/acquire_p2p_nat_g2_pion_rung3_dependency_wave5_v1_once.py',
        '464afe4978486858fee622c885f35c94d65c9eb115e340832afb1e1a76327923',
        54_892,
        "0644",
    ),
    frozen(
        'script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave5_v1_once.py',
        '0c19870b53faf332bc8f944f559b4b538a24c7e3f63ad3aba0156f3e505bd89a',
        27_623,
        "0644",
    ),
    frozen(
        'script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py',
        '37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd',
        34_617,
        "0644",
    ),
    frozen(
        'script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py',
        'ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b',
        54_352,
        "0644",
    ),
]
ACQUISITION_CLAIM = frozen(
    ACQUISITION_CLAIM_PATH,
    "704b24ac42dd34e22550619315fc4c80732bf494dcd687e97ff321d3ac360909",
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
    "linkCount": 32,
    "exactFileCount": 30,
}
EVIDENCE_FILE = frozen(
    EVIDENCE_PATH,
    "93b14f30d0bcd24ee628d7d2ab39a083312ee837d345bd673e7983f12895bb29",
    11_859,
    "0600",
)


_ACCEPTED_ROWS = [
    ('001-799ad663ec0afa54c678.mod', 'e076074c1560ad1dda98b8b00fea6308c4b6ccd06ddd088d22db4626ed68f738', 188),
    ('001-799ad663ec0afa54c678.zip', 'd880adf449449120b459a2220f539c69648fd797ded5b745cf3add60ec84081e', 113_507),
    ('002-8e73b6b31cdfee8f479a.mod', 'f8b595e5c961093c6877b96af679f43322254a53087b11fd2645642e693befd5', 190),
    ('002-8e73b6b31cdfee8f479a.zip', '73ee31242e1134ff983083b25a915a6fa1e5742658972259cf5fb4c12db2cd86', 1_797_936),
    ('003-f41d9058bfdfff2cf62e.mod', '8b27ec1214a37527158dd20611e4b684081c0b8c6056959b7cc3ecd7b2570674', 86),
    ('003-f41d9058bfdfff2cf62e.zip', 'dffdae50c0a7903e522053e8e9880069ed1854446326f954cf903f713678c3a2', 172_652),
    ('004-8d29107240a336c2979a.mod', '137ee52b54c10b479ebe6b887a0206fb4f54581f54ba293b7f4bb682cf529f67', 155),
    ('004-8d29107240a336c2979a.zip', '7fd8464681c3011736f2c75beb20f88fff553a17f4f574325bce5ca5dc1fcf83', 1_891_278),
    ('005-8edf197c072cd830f9a3.mod', 'da7ab98f71cb7ee5dd3766ed0f29d7088c9d62bc137b8fd286ebdb3d236c67c4', 157),
    ('005-8edf197c072cd830f9a3.zip', '3444c04eff1dc7a41a6386cb6a0b0b1facebfc7e222bae523043ed4b14039f76', 1_934_428),
    ('006-29815ebff680721efaed.mod', 'd333c54b74af8a0b8ec748d37c5972d27b9d088b9e45c8bf5c3ab520d2113090', 36),
    ('006-29815ebff680721efaed.zip', '939a1a573cd83df56836b637052a45f6a60f78b86a5a375fc0c6c298a868a14d', 25_708),
    ('007-8b2712973066d9a8f6c0.mod', '700e5db00dd26aa19a17dce5fc552436d60f68c5606c85b821f24c3d6072a151', 34),
    ('007-8b2712973066d9a8f6c0.zip', '20b01085240e661bffc7f59383f21b90f112d669784220c6e59c801243216d22', 26_990),
    ('008-10fe96968b9a13bc1eac.mod', 'd227b325f621f4ebe28d39ba773ea99b870f393b7c09c34592c365b16dd560de', 33),
    ('008-10fe96968b9a13bc1eac.zip', 'b49fb9baa2cd133596927ef070ce74bf38223d97e7c81ef73fe1e8b2ab3639cd', 1_905_235),
    ('009-9084328e2adc72e3a1b7.mod', 'd227b325f621f4ebe28d39ba773ea99b870f393b7c09c34592c365b16dd560de', 33),
    ('009-9084328e2adc72e3a1b7.zip', '3f826b191eab1ebda925feb551d334e37e1b5865d1aa790fade46598811a8b1a', 1_956_163),
    ('010-61ed969458c6638f5ced.mod', 'f411814d83a96e86781b1dee41c125b9504da5422dba37cc1d63b016ae39cfe2', 35),
    ('010-61ed969458c6638f5ced.zip', 'dacd7c9aa2b298f966822da214c6d601da08f14d41b29032bcac4bc503887a49', 2_002_991),
    ('011-178675e1f276fe14b85e.mod', '804303f8b1c302436bc448c6517cf3f32216611f1c7ffd72b52df2a69565a5c6', 138),
    ('011-178675e1f276fe14b85e.zip', 'b8408ce169cee1bde49308c632a41084224ec3c8f4a5c0950e9e98e032140e01', 951_048),
    ('012-ec3a4fc7356d3802f69f.mod', 'b0ba178180a686d4a0f5421a59fe3c25ab80cfe056277eb50e460939e94a2653', 133),
    ('012-ec3a4fc7356d3802f69f.zip', '964c76120c73c1f94ee0d38a9307b19949eaa314dcccfeff6db43d63e21f57cd', 1_017_761),
    ('013-b4332a5404ca337d3407.mod', 'dbea02254aac2cf3fd0f72c7c602e543c5fbad2d00dafc2f819c28a935258199', 68),
    ('013-b4332a5404ca337d3407.zip', 'a38f40301a9ca1154edc70dcbfc6dd2a2ce55abbd49dad8031fb15c1a5e62459', 19_883),
    ('014-fcf5bae248b8d1188b82.mod', '971579f17e9abc5926ab76214f533bd517cf4925c885243ac4755a1a0a7c69ef', 197),
    ('014-fcf5bae248b8d1188b82.zip', 'b9814897e0e09cd576a7a013f066c7db537a3d538d2e0f60f0caee9bc1b3f4af', 9_235_236),
    ('015-96c96a72c345967b1eae.mod', '142b3416b00e8213b409e279a434b97a6ce09531c914c1b4717878157d579a3f', 214),
    ('015-96c96a72c345967b1eae.zip', '6fd1e250112215709454468ead53c31c524b05cc90a62ed817d0d4780fdb6429', 3_071_376),
]
ACCEPTED_FILES = [
    frozen(f"{ACCEPTED_ROOT}/{name}", digest, size, "0600")
    for name, digest, size in _ACCEPTED_ROWS
]
ACQUISITION_RECEIPT = frozen(
    ACQUISITION_RECEIPT_PATH,
    "5063004755ac2cf50eeea9b03be6de9ad361ccb2917edd8f864baba5409362a7",
    1_322,
    "0600",
)
ACQUISITION_MANIFEST = frozen(
    ACQUISITION_MANIFEST_PATH,
    "e52ffcf5c8c0b04e76a7ecb6cb5610dc30307d3fc03f1dfb0f6d91a8edae9d52",
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


def portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def has_portable_prefix(
    names: Sequence[str],
    prefixes: Sequence[str],
) -> bool:
    portable_prefixes = [portable_name(prefix) for prefix in prefixes]
    return any(
        portable_name(name).startswith(prefix)
        for name in names
        for prefix in portable_prefixes
    )


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
            "acquire_p2p_nat_g2_pion_rung3_dependency_wave5" in name
            or "check_p2p_nat_g2_pion_rung3_dependency_wave5_acquisition"
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
            "portableNameComparison": "NFC_casefold",
            "failureAbsent": True,
            "stagingAbsent": True,
        },
        "frozenFileCount": len(frozen_canonical),
        "frozenFilesCanonicalSha256": sha256(canonical_bytes(frozen_canonical)),
        "aggregateModBytes": 1_697,
        "aggregateZipBytes": 26_122_192,
        "aggregateAcceptedBytes": 26_123_889,
        "aggregateZipEntryCount": 6_038,
        "aggregateZipUncompressedBytes": 101_774_573,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "acceptedResourceCount": 30,
        "selectedTupleCount": 0,
        "modCount": 15,
        "zipCount": 15,
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
            "aetherlink.wave5-source-acquisition-readback-execution-permit"
        ),
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave5-source-acquisition-readback-"
            "execution-permit-v1"
        ),
        "recordedDate": "2026-07-25",
        "status": "authorized_not_consumed",
        "frozenAcquisitionSnapshot": frozen_snapshot_payload(),
        "verificationContract": {
            "claimDurableBeforeAnyFrozenAcquisitionInputOpen": True,
            "authorityFilesOpenedAndHeldFirst": True,
            "allFrozenFilesOpenedNoFollowAndHeld": True,
            "retainedProjectRootCurrentPathIdentityCheckedAtEachPreManifestBarrier": True,
            "eachPreManifestBarrierReopensEveryCurrentPathNoFollow": True,
            "currentPathDeviceAndInodeMustMatchHeldObjectAtEachPreManifestBarrier": True,
            "frozenSnapshotHeldFdBytesReverifiedImmediatelyBeforeManifestPublication": True,
            "readbackClaimCurrentPathIdentityReverifiedImmediatelyBeforeManifestPublication": True,
            "readbackReceiptCurrentPathIdentityReverifiedImmediatelyBeforeManifestPublication": True,
            "claimCreationFdHeldAtImmediatelyBeforeManifestBarrier": True,
            "currentPathIdentityGuaranteedThroughManifestPublication": False,
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
            "completionAppliesToRetainedSnapshot": True,
            "publishedOutputsReopenedAndVerifiedBeforePublishReturns": True,
            "pathSha256BytesModeOwnerAndLinkCountRequired": True,
            "exactFinalAndAcceptedDirectoryInventoriesRequired": True,
            "strictCanonicalTerminalAndEvidenceJsonRequired": True,
            "decisionAndPermitContentBindingsRecomputed": True,
            "attemptAndAuthorityBindingsRecomputed": True,
            "exact30ResourceOrderAndAggregateRecomputed": True,
            "exact46FrozenFileSnapshotRequired": True,
            "acceptedResourceHashSetCanonicalSha256Recomputed": True,
            "identityAndSourceRequestSetBindingsRecomputed": True,
            "goModH1RecomputedIndependently": True,
            "moduleZipH1RecomputedIndependently": True,
            "zipStructurePathCrcAndModParityRecomputed": True,
            "completeVerificationPassCount": 2,
            "retainedFdPreManifestBarrierCount": 3,
            "retainedFdPreManifestBarriers": [
                "complete_snapshot_and_claim_immediately_before_receipt",
                "complete_snapshot_claim_and_receipt_after_receipt",
                (
                    "complete_snapshot_claim_and_receipt_"
                    "immediately_before_manifest_publication"
                ),
            ],
            "allRequiredPreManifestBarriersCompleteImmediatelyBeforeManifestPublication": True,
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
            "temporaryNameComparison": "NFC_casefold",
            "preflightRejectsAnyStaleTemporaryName": True,
            "manifestPublicationFollowsLastPreManifestBarrierWithoutFrozenInputRecheck": True,
            "fallibleFrozenClaimOrReceiptBarrierAfterManifest": False,
            "currentPathIdentityGuaranteedThroughManifestPublication": False,
            "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
            "completionAppliesToRetainedSnapshot": True,
            "publicationOrder": [
                "rename_no_replace",
                "parent_directory_fsync",
                "final_name_no_follow_reopen_and_source_inode_verification",
                "return",
            ],
        },
        "resourceLimits": {
            "maximumPackageFileBytes": MAXIMUM_PACKAGE_FILE_BYTES,
            "maximumAcceptedResourceCount": 30,
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
        "result": (
            "exact_offline_wave5_retained_snapshot_readback_"
            "authorized_not_consumed"
        ),
        "nextAction": "execute_bound_offline_readback_once",
        "nonClaims": [
            "this permit does not authorize another source acquisition",
            "readback success is not source review or dependency closure",
            "readback success is not library selection release approval or V1 completion",
            (
                "the standalone live permit checker is a sequential diagnostic, "
                "not an atomic concurrent snapshot; execution safety relies on "
                "the recorder retained-FD and pre-manifest current-path barriers"
            ),
            (
                "same-UID rename or replacement after the last pre-manifest "
                "barrier is not prevented; completion applies to the retained "
                "snapshot, not continuous current-path identity"
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
        not has_portable_prefix(
            [path.name for path in dependency.iterdir()],
            [STAGING_PREFIX],
        ),
        "E_TERMINAL",
    )


def readback_namespace_state(root: Path = ROOT) -> str:
    claim = os.path.lexists(root / READBACK_CLAIM_PATH)
    receipt = os.path.lexists(root / READBACK_RECEIPT_PATH)
    manifest = os.path.lexists(root / READBACK_MANIFEST_PATH)
    names = os.listdir(root / BASE)
    if has_portable_prefix(names, READBACK_TEMP_PREFIXES):
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
        "documentType": "aetherlink.wave5-acquisition-readback-permit-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "acquisitionAttemptId": ATTEMPT_ID,
        "frozenAuthorityFileCount": 12,
        "acceptedResourceCount": 30,
        "selectedTupleCount": 0,
        "aggregateAcceptedBytes": 26_123_889,
        "aggregateZipEntryCount": 6_038,
        "aggregateZipUncompressedBytes": 101_774_573,
        "acceptedResourceHashSetCanonicalSha256": (
            EXPECTED_ACCEPTED_RESOURCE_HASH_SET
        ),
        "frozenSnapshotVerified": verify_frozen,
        "readbackClaimExists": False,
        "lastCurrentPathIdentityBarrierTiming":
            "immediately_before_manifest_publication",
        "currentPathIdentityGuaranteedThroughManifestPublication": False,
        "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented": False,
        "completionAppliesToRetainedSnapshot": True,
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
                    "documentType": "aetherlink.wave5-acquisition-readback-permit-error",
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
                    "documentType": "aetherlink.wave5-acquisition-readback-permit-error",
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
