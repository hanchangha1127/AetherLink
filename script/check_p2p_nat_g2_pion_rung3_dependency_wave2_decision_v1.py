#!/usr/bin/env python3
"""Validate the preparation-only G2 dependency wave-two decision.

The checker is deliberately read-only. It binds the independently read-back
wave-one graph frontier to exact, already-held go.sum identities. It does not
perform network I/O, acquire source, extract source, invoke a package manager,
compile, execute source, or mutate Git state.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Callable
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[1]

BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave2-v1.json"
)
READER_PATH = (
    f"{BASE}/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave2-v1.md"
)
WAVE1_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-v1.json"
)
WAVE1_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave1_decision_v1.py"
)
WAVE1_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave1_decision_v1.py"
)
REVIEW_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-execution-permit-v3.json"
)
REVIEW_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-v3.claim"
)
REVIEW_RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-result-v3.json"
)
REVIEW_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-manifest-v3.json"
)
READBACK_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".wave-1-review-readback-v3.claim"
)
READBACK_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-v3.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-review-wave1-readback-manifest-v3.json"
)
READBACK_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_dependency_source_review_wave1_readback_v1.py"
)
READBACK_TESTS_PATH = (
    "script/test_check_p2p_nat_g2_pion_dependency_source_review_wave1_readback_v1.py"
)

DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
WAVE2_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-2-v1.claim"
WAVE2_STAGING_PREFIX = ".wave-2-v1-staging-"
WAVE2_PARENT_PATH = f"{DEPENDENCY_ROOT}/wave-2-v1"
WAVE2_FINAL_PATH = f"{DEPENDENCY_ROOT}/wave-2-v1/accepted"
WAVE2_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-receipt-v1.json"
)
WAVE2_FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-failure-v1.json"
)
WAVE2_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-manifest-v1.json"
)
WAVE2_READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-v1.json"
)
WAVE2_READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave2-readback-manifest-v1.json"
)

EXPECTED_READER_RAW_SHA256 = (
    "3f9615f2c7228014163f00b42cd0bb7cfed2283342399d39fbc94d7de0f6d023"
)


class CheckError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise CheckError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def strict_equal(actual: Any, expected: Any, code: str, label: str) -> None:
    if type(actual) is not type(expected) or actual != expected:
        fail(code, f"{label} drift")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("E_JSON", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    fail("E_JSON", f"non-finite JSON constant: {value}")


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("E_JSON", f"{label}: {exc}")
    require(type(value) is dict, "E_JSON", f"{label}: object required")
    return value


def verify_content_binding(
    document: dict[str, Any],
    label: str,
    expected_scope: str,
    expected_digest: str | None = None,
) -> None:
    binding = document.get("contentBinding")
    require(type(binding) is dict, "E_BINDING", f"{label}: binding required")
    strict_equal(
        set(binding),
        {"algorithm", "canonicalization", "scope", "sha256"},
        "E_BINDING",
        f"{label}.contentBinding.keys",
    )
    strict_equal(binding["algorithm"], "sha256", "E_BINDING", f"{label}.algorithm")
    strict_equal(
        binding["canonicalization"],
        "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "E_BINDING",
        f"{label}.canonicalization",
    )
    strict_equal(binding["scope"], expected_scope, "E_BINDING", f"{label}.scope")
    payload = dict(document)
    payload.pop("contentBinding")
    computed = sha256(canonical_bytes(payload))
    strict_equal(binding["sha256"], computed, "E_BINDING", f"{label}.sha256")
    if expected_digest is not None:
        strict_equal(
            computed,
            expected_digest,
            "E_BINDING",
            f"{label}.expectedSha256",
        )


@dataclass
class Snapshot:
    relative: str
    fd: int
    state: tuple[int, int, int, int, int, int, int]
    data: bytes


def file_state(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def validate_relative_path(relative: str) -> tuple[str, ...]:
    require(type(relative) is str, "E_PATH", "path must be a string")
    require(
        relative
        and "\x00" not in relative
        and "\n" not in relative
        and "\r" not in relative
        and "\\" not in relative,
        "E_PATH",
        f"unsafe path: {relative!r}",
    )
    pure = PurePosixPath(relative)
    require(not pure.is_absolute(), "E_PATH", f"absolute path: {relative}")
    parts = pure.parts
    require(
        parts and all(part not in {"", ".", ".."} for part in parts),
        "E_PATH",
        f"non-canonical path: {relative}",
    )
    require(
        unicodedata.normalize("NFC", relative) == relative,
        "E_PATH",
        f"non-NFC path: {relative}",
    )
    return parts


def secure_read(relative: str, limit: int = 16 * 1024 * 1024) -> Snapshot:
    parts = validate_relative_path(relative)
    current = ROOT
    for part in parts[:-1]:
        current /= part
        try:
            info = current.lstat()
        except OSError as exc:
            fail("E_FILESYSTEM", f"{relative}: parent unavailable: {exc}")
        require(
            stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
            "E_FILESYSTEM",
            f"{relative}: real parent directory required",
        )
    path = ROOT.joinpath(*parts)
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        fail("E_FILESYSTEM", f"{relative}: open failed: {exc}")
    try:
        opened = os.fstat(fd)
        linked = path.lstat()
        require(
            stat.S_ISREG(opened.st_mode)
            and not stat.S_ISLNK(linked.st_mode)
            and opened.st_nlink == 1
            and file_state(opened) == file_state(linked),
            "E_FILESYSTEM",
            f"{relative}: stable single-link regular file required",
        )
        require(
            0 <= opened.st_size <= limit,
            "E_LIMIT",
            f"{relative}: size limit exceeded",
        )
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            require(chunk != b"", "E_TOCTOU", f"{relative}: premature EOF")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_TOCTOU", f"{relative}: grew while read")
        data = b"".join(chunks)
        require(
            file_state(os.fstat(fd)) == file_state(opened),
            "E_TOCTOU",
            f"{relative}: changed while read",
        )
        return Snapshot(relative, fd, file_state(opened), data)
    except Exception:
        os.close(fd)
        raise


def verify_snapshot(snapshot: Snapshot) -> None:
    path = ROOT.joinpath(*validate_relative_path(snapshot.relative))
    try:
        current = path.lstat()
        opened = os.fstat(snapshot.fd)
    except OSError as exc:
        fail("E_TOCTOU", f"{snapshot.relative}: final barrier failed: {exc}")
    require(
        file_state(current) == snapshot.state
        and file_state(opened) == snapshot.state
        and not stat.S_ISLNK(current.st_mode),
        "E_TOCTOU",
        f"{snapshot.relative}: changed before final barrier",
    )


def close_snapshots(snapshots: dict[str, Snapshot]) -> None:
    for snapshot in snapshots.values():
        try:
            os.close(snapshot.fd)
        except OSError:
            pass


def tuple_digest(module: str, version: str) -> str:
    return sha256(f"{module}\n{version}\n".encode("utf-8"))


def proxy_escape(value: str) -> str:
    output: list[str] = []
    for char in value:
        if "A" <= char <= "Z":
            output.extend(("!", char.lower()))
        else:
            output.append(char)
    return "".join(output)


MOD_ROOT = f"{DEPENDENCY_ROOT}/wave-1-v3/accepted"


def parent(
    module: str,
    version: str,
    filename: str,
    raw_sha256: str,
    line: int,
) -> dict[str, Any]:
    return {
        "module": module,
        "version": version,
        "modPath": f"{MOD_ROOT}/{filename}",
        "modRawSha256": raw_sha256,
        "requireLine": line,
    }


def checksum(
    source_order: int,
    source_module: str,
    source_version: str,
    archive_path: str,
    archive_raw_sha256: str,
    member: str,
    member_raw_sha256: str,
    zip_line: int,
    mod_line: int,
    zip_h1: str,
    mod_h1: str,
    pair_source_count: int,
    direct_parent: bool,
) -> dict[str, Any]:
    return {
        "selectionPolicy": (
            "direct_parent_then_lowest_source_tuple_order_then_lexical_path_member"
        ),
        "sourceIsDirectParent": direct_parent,
        "sourceTupleOrder": source_order,
        "sourceModule": source_module,
        "sourceVersion": source_version,
        "archivePath": archive_path,
        "archiveRawSha256": archive_raw_sha256,
        "goSumMember": member,
        "goSumRawSha256": member_raw_sha256,
        "moduleZipLine": zip_line,
        "moduleModLine": mod_line,
        "moduleZipH1": zip_h1,
        "moduleModH1": mod_h1,
        "heldPairSourceCount": pair_source_count,
        "conflictingHeldH1PairCount": 0,
        "freshChecksumDatabaseProof": False,
    }


TUPLE_INPUTS: tuple[dict[str, Any], ...] = (
    {
        "module": "github.com/kr/text",
        "version": "v0.1.0",
        "selected": True,
        "parents": (
            parent(
                "github.com/kr/pretty",
                "v0.1.0",
                "012-2055c3218667fc22d930.mod",
                "e3d5d46d2f6ac94a666a54b5e867ec16bf199d9f4b700827cd731607efdd109a",
                3,
            ),
        ),
        "checksum": checksum(
            0,
            "github.com/pion/ice/v4",
            "v4.3.0",
            (
                "build/offline-source/pion-ice-v4.3.0/original/"
                "github.com-pion-ice-v4@v4.3.0.zip"
            ),
            "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c",
            "github.com/pion/ice/v4@v4.3.0/go.sum",
            "b47d7d5f3bb8c8b85b3283585f97ea6bd0a8b97427b49068b9f5685ddd953887",
            8,
            9,
            "h1:45sCR5RtlFHMR4UwH9sdQ5TC8v0qDQCHnXt+kaKSTVE=",
            "h1:4Jbv+DJW3UT/LiOwJeYQe1efqtUx/iVham/4vfdArNI=",
            1,
            False,
        ),
    },
    {
        "module": "github.com/pion/dtls/v3",
        "version": "v3.1.4",
        "selected": False,
        "parents": (
            parent(
                "github.com/pion/stun/v3",
                "v3.1.6",
                "006-d21718efc602b3f97741.mod",
                "80524764e19eec76482f062b040c31b7e38fbf2c30f0e651f019e452190406a1",
                6,
            ),
            parent(
                "github.com/pion/turn/v5",
                "v5.0.12",
                "008-233d1d4c3997850aea8c.mod",
                "cefb40fc2863641ddb262966329b26f62b913f01af3830d8d687ba069812991a",
                17,
            ),
        ),
        "checksum": checksum(
            6,
            "github.com/pion/stun/v3",
            "v3.1.6",
            f"{MOD_ROOT}/006-d21718efc602b3f97741.zip",
            "ab69bf22421e9c89c97768ee7627f4a1edf8262bc526ee62bb24354d96d6adb8",
            "github.com/pion/stun/v3@v3.1.6/go.sum",
            "996faae6f0b7148212200a1e74bf258f56dc09e4d002ac8233e4429a676df77a",
            3,
            4,
            "h1:QhvtMflMfu9Kf0RcDC5BJBle4caPskByrKQR6uuYqpY=",
            "h1:cr/qotLISUw/9C1m83ZPNZtj9WnXkYLpfCptPqbkInc=",
            2,
            True,
        ),
    },
    {
        "module": "github.com/pion/transport/v3",
        "version": "v3.1.1",
        "selected": True,
        "parents": (
            parent(
                "github.com/pion/mdns/v2",
                "v2.1.0",
                "004-73c3ff091d7cba5359a8.mod",
                "db929a17960a3f3e3c71b9b71a726150db2cdbad8a224cf976c59b0376f0fa22",
                7,
            ),
        ),
        "checksum": checksum(
            4,
            "github.com/pion/mdns/v2",
            "v2.1.0",
            f"{MOD_ROOT}/004-73c3ff091d7cba5359a8.zip",
            "275bed51350805c787bdfc7917ecfaa3a8c705b8eb767ba0116c96110410b566",
            "github.com/pion/mdns/v2@v2.1.0/go.sum",
            "1d521895a91b882ccf7adbe806b8a76e0764089ff75ee0212f2cd7369a926f47",
            5,
            6,
            "h1:Tr684+fnnKlhPceU+ICdrw6KKkTms+5qHMgw6bIkYOM=",
            "h1:+c2eewC5WJQHiAA46fkMMzoYZSuGzA/7E2FPrOYHctQ=",
            2,
            True,
        ),
    },
    {
        "module": "github.com/stretchr/objx",
        "version": "v0.5.2",
        "selected": True,
        "parents": (
            parent(
                "github.com/stretchr/testify",
                "v1.11.1",
                "009-f106745b2c482a4bb91d.mod",
                "5846af204043f29df285026109bf32db6519c3d7e1d5c3a65fefb174f9d81d33",
                10,
            ),
        ),
        "checksum": checksum(
            9,
            "github.com/stretchr/testify",
            "v1.11.1",
            f"{MOD_ROOT}/009-f106745b2c482a4bb91d.zip",
            "b7325b561ead5304b72b9f32aebc871ff49b3823667d530a49fd6c8f3adfc96e",
            "github.com/stretchr/testify@v1.11.1/go.sum",
            "44c80bfb4bd03f14d790cf693fedf82cf3097be6f65b8e52b7131f73ca50aa28",
            5,
            6,
            "h1:xuMeJ0Sdp5ZMRXx/aWO6RZxdr3beISkG5/G/aIRr3pY=",
            "h1:FRsXN1f5AsAjCGJKqEizvkpNtU+EGNCLh3NxZ/8L+MA=",
            1,
            True,
        ),
    },
    {
        "module": "github.com/stretchr/testify",
        "version": "v1.10.0",
        "selected": False,
        "parents": (
            parent(
                "github.com/pion/logging",
                "v0.2.4",
                "003-86cd416af67cef255d1a.mod",
                "bfbce8d81a9eaf0b1ba6d3c4d0a58f7e7d6d1be06bec518db96f62f7feeb3d6f",
                5,
            ),
        ),
        "checksum": checksum(
            3,
            "github.com/pion/logging",
            "v0.2.4",
            f"{MOD_ROOT}/003-86cd416af67cef255d1a.zip",
            "b904074dd76009e71b4e4e0e004a2c7862bff0a8690b4f47410c46b172b3830c",
            "github.com/pion/logging@v0.2.4/go.sum",
            "871ef9c601b2af3da7a7323074c9d9f647d29ab0cbd0acd282adebbf38d84207",
            5,
            6,
            "h1:Xv5erBjTwe/5IxqUQTdXv5kgmIvbHo3QQyRwhJsOfJA=",
            "h1:r2ic/lqez/lEtzL7wO/rwa5dbSLXVDPFyf8C91i36aY=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/crypto",
        "version": "v0.47.0",
        "selected": False,
        "parents": (
            parent(
                "golang.org/x/net",
                "v0.49.0",
                "010-ec8b158caf646682189e.mod",
                "f63b9720c6d87ef05662d4641e78531af98e6a13be08611bfba7128e9b2de970",
                6,
            ),
        ),
        "checksum": checksum(
            10,
            "golang.org/x/net",
            "v0.49.0",
            f"{MOD_ROOT}/010-ec8b158caf646682189e.zip",
            "c07a4d56c3db52dc2b29c65b134f96c2cb071e8a50e4f488ac7facb46005cc85",
            "golang.org/x/net@v0.49.0/go.sum",
            "9dbac9e591ee261e99a8549c4f7994d6cb1ef2f597ded6054853e33f59f91739",
            1,
            2,
            "h1:V6e3FRj+n4dbpw86FJ8Fv7XVOql7TEwpHapKoMJ/GO8=",
            "h1:ff3Y9VzzKbwSSEzWqJsJVBnWmRwRSHt/6Op5n9bQc4A=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/net",
        "version": "v0.34.0",
        "selected": False,
        "parents": (
            parent(
                "github.com/pion/transport/v4",
                "v4.0.2",
                "007-6312023846b9c2bcc844.mod",
                "a3cbbcdfef23c4b414bc2584260dc4e1935f7dc7d4daf726e477707b357d086a",
                9,
            ),
        ),
        "checksum": checksum(
            7,
            "github.com/pion/transport/v4",
            "v4.0.2",
            f"{MOD_ROOT}/007-6312023846b9c2bcc844.zip",
            "5c44f0562179e9e2761f7d3c2d68ac030fdbd3be565771e536e88444666d73b5",
            "github.com/pion/transport/v4@v4.0.2/go.sum",
            "180dbcbf12f833e87b4d7b41b01973b94ad5e9319091416a0f3404421342cab5",
            11,
            12,
            "h1:Mb7Mrk043xzHgnRM88suvJFwzVrRfHEHJEl5/71CKw0=",
            "h1:di0qlW3YNM5oh6GqDGQr92MyTozJPmybPK4Ev/Gm31k=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/net",
        "version": "v0.35.0",
        "selected": False,
        "parents": (
            parent(
                "github.com/pion/mdns/v2",
                "v2.1.0",
                "004-73c3ff091d7cba5359a8.mod",
                "db929a17960a3f3e3c71b9b71a726150db2cdbad8a224cf976c59b0376f0fa22",
                9,
            ),
        ),
        "checksum": checksum(
            4,
            "github.com/pion/mdns/v2",
            "v2.1.0",
            f"{MOD_ROOT}/004-73c3ff091d7cba5359a8.zip",
            "275bed51350805c787bdfc7917ecfaa3a8c705b8eb767ba0116c96110410b566",
            "github.com/pion/mdns/v2@v2.1.0/go.sum",
            "1d521895a91b882ccf7adbe806b8a76e0764089ff75ee0212f2cd7369a926f47",
            11,
            12,
            "h1:T5GQRQb2y08kTAByq9L4/bz8cipCdA8FbRTXewonqY8=",
            "h1:EglIi67kWsHKlRzzVMUD93VMSWGFOMSZgxFjparz1Qk=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/sys",
        "version": "v0.30.0",
        "selected": False,
        "parents": (
            parent(
                "github.com/pion/mdns/v2",
                "v2.1.0",
                "004-73c3ff091d7cba5359a8.mod",
                "db929a17960a3f3e3c71b9b71a726150db2cdbad8a224cf976c59b0376f0fa22",
                15,
            ),
        ),
        "checksum": checksum(
            4,
            "github.com/pion/mdns/v2",
            "v2.1.0",
            f"{MOD_ROOT}/004-73c3ff091d7cba5359a8.zip",
            "275bed51350805c787bdfc7917ecfaa3a8c705b8eb767ba0116c96110410b566",
            "github.com/pion/mdns/v2@v2.1.0/go.sum",
            "1d521895a91b882ccf7adbe806b8a76e0764089ff75ee0212f2cd7369a926f47",
            13,
            14,
            "h1:QjkSwP/36a20jFYWkSue1YwXzLmsV5Gfq7Eiy72C1uc=",
            "h1:/VUhepiaJMQUp4+oa/7Zr1D23ma6VTLIYjOOTFZPUcA=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/sys",
        "version": "v0.40.0",
        "selected": False,
        "parents": (
            parent(
                "golang.org/x/net",
                "v0.49.0",
                "010-ec8b158caf646682189e.mod",
                "f63b9720c6d87ef05662d4641e78531af98e6a13be08611bfba7128e9b2de970",
                7,
            ),
        ),
        "checksum": checksum(
            10,
            "golang.org/x/net",
            "v0.49.0",
            f"{MOD_ROOT}/010-ec8b158caf646682189e.zip",
            "c07a4d56c3db52dc2b29c65b134f96c2cb071e8a50e4f488ac7facb46005cc85",
            "golang.org/x/net@v0.49.0/go.sum",
            "9dbac9e591ee261e99a8549c4f7994d6cb1ef2f597ded6054853e33f59f91739",
            3,
            4,
            "h1:DBZZqJ2Rkml6QMQsZywtnjnnGvHza6BTfYFWY9kjEWQ=",
            "h1:OgkHotnGiDImocRcuBABYBEXf8A9a87e/uXjp9XT3ks=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/term",
        "version": "v0.39.0",
        "selected": False,
        "parents": (
            parent(
                "golang.org/x/net",
                "v0.49.0",
                "010-ec8b158caf646682189e.mod",
                "f63b9720c6d87ef05662d4641e78531af98e6a13be08611bfba7128e9b2de970",
                8,
            ),
        ),
        "checksum": checksum(
            10,
            "golang.org/x/net",
            "v0.49.0",
            f"{MOD_ROOT}/010-ec8b158caf646682189e.zip",
            "c07a4d56c3db52dc2b29c65b134f96c2cb071e8a50e4f488ac7facb46005cc85",
            "golang.org/x/net@v0.49.0/go.sum",
            "9dbac9e591ee261e99a8549c4f7994d6cb1ef2f597ded6054853e33f59f91739",
            5,
            6,
            "h1:RclSuaJf32jOqZz74CkPA9qFuVTX7vhLlpfj/IGWlqY=",
            "h1:yxzUCTP/U+FzoxfdKmLaA0RV1WgE0VY7hXBwKtY/4ww=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/term",
        "version": "v0.40.0",
        "selected": True,
        "parents": (
            parent(
                "golang.org/x/crypto",
                "v0.48.0",
                "015-fcd48846ebac09f78d86.mod",
                "c591925f226a3dd387d4b6023287760fbafdbd9175bed7c5c28ca498f7c2fce7",
                8,
            ),
        ),
        "checksum": checksum(
            15,
            "golang.org/x/crypto",
            "v0.48.0",
            f"{MOD_ROOT}/015-fcd48846ebac09f78d86.zip",
            "837297a50ca77a6a18ea2f2936bfe31aaf2ad36d5bcd8c545709da3b6c600fd2",
            "golang.org/x/crypto@v0.48.0/go.sum",
            "5c6ddd64c307a607d8904487cb029cf74a3e02c6a5b246122c43d76d16cd6341",
            5,
            6,
            "h1:36e4zGLqU4yhjlmxEaagx2KuYbJq3EwY8K943ZsHcvg=",
            "h1:w2P8uVp06p2iyKKuvXIm7N/y0UCRt3UfJTfZ7oOpglM=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/text",
        "version": "v0.33.0",
        "selected": False,
        "parents": (
            parent(
                "golang.org/x/net",
                "v0.49.0",
                "010-ec8b158caf646682189e.mod",
                "f63b9720c6d87ef05662d4641e78531af98e6a13be08611bfba7128e9b2de970",
                9,
            ),
        ),
        "checksum": checksum(
            10,
            "golang.org/x/net",
            "v0.49.0",
            f"{MOD_ROOT}/010-ec8b158caf646682189e.zip",
            "c07a4d56c3db52dc2b29c65b134f96c2cb071e8a50e4f488ac7facb46005cc85",
            "golang.org/x/net@v0.49.0/go.sum",
            "9dbac9e591ee261e99a8549c4f7994d6cb1ef2f597ded6054853e33f59f91739",
            7,
            8,
            "h1:B3njUFyqtHDUI5jMn1YIr5B0IE2U0qck04r6d4KPAxE=",
            "h1:LuMebE6+rBincTi9+xWTY8TztLzKHc/9C1uBCG27+q8=",
            1,
            True,
        ),
    },
    {
        "module": "golang.org/x/text",
        "version": "v0.34.0",
        "selected": True,
        "parents": (
            parent(
                "golang.org/x/crypto",
                "v0.48.0",
                "015-fcd48846ebac09f78d86.mod",
                "c591925f226a3dd387d4b6023287760fbafdbd9175bed7c5c28ca498f7c2fce7",
                11,
            ),
        ),
        "checksum": checksum(
            15,
            "golang.org/x/crypto",
            "v0.48.0",
            f"{MOD_ROOT}/015-fcd48846ebac09f78d86.zip",
            "837297a50ca77a6a18ea2f2936bfe31aaf2ad36d5bcd8c545709da3b6c600fd2",
            "golang.org/x/crypto@v0.48.0/go.sum",
            "5c6ddd64c307a607d8904487cb029cf74a3e02c6a5b246122c43d76d16cd6341",
            7,
            8,
            "h1:oL/Qq0Kdaqxa1KbNeMKwQq0reLCCaFtqu2eNuSeNHbk=",
            "h1:homfLqTYRFyVYemLBFl5GgL/DWEiH5wcsQ5gSh1yziA=",
            1,
            True,
        ),
    },
    {
        "module": "gopkg.in/check.v1",
        "version": "v0.0.0-20161208181325-20d25e280405",
        "selected": False,
        "parents": (
            parent(
                "gopkg.in/yaml.v3",
                "v3.0.1",
                "019-495087f35325ae50e341.mod",
                "21579860a20306fcf43b1bd234d1fba319499c77611b71c05f9bf3ba90dab939",
                4,
            ),
        ),
        "checksum": checksum(
            2,
            "github.com/pion/dtls/v3",
            "v3.1.5",
            f"{MOD_ROOT}/002-c4e8ffbb48deb188a3c2.zip",
            "447358c3191774c809538a061ecb89effb4a7257b22213e19f35a62faa37cdf5",
            "github.com/pion/dtls/v3@v3.1.5/go.sum",
            "680768fb177ddf8d071337472b5c76d3c15d1b95928d1ec2fe747b524575b21f",
            17,
            18,
            "h1:yhCVgyC4o1eVCa2tZl7eS0r+SDo693bJlVdllGtEeKM=",
            "h1:Co6ibVJAznAaIkqp8huTwlJQCZ016jof/cbN4VW5Yz0=",
            7,
            False,
        ),
    },
)


BINDING_INPUTS: tuple[dict[str, Any], ...] = (
    {
        "role": "wave1IdentityAndAcquisitionDecision",
        "path": WAVE1_DECISION_PATH,
        "rawSha256": "03bd5cac4793d379160a9c316d726c9d30d7a4aa00384d5687b1659acfb8943e",
        "contentSha256": "13571495b1533d62073d25aed5abc342391a4cc147d26f1e6df375e6a2b33201",
        "scope": "decision_without_contentBinding",
        "requiredStatus": (
            "wave1_source_identity_and_request_contract_prepared_"
            "acquisition_not_authorized"
        ),
    },
    {
        "role": "wave1DecisionChecker",
        "path": WAVE1_CHECKER_PATH,
        "rawSha256": "207775b8f0b2c22cf50bb5f62d7e64657cf1ed73cca540b46cac36ea2da5c74b",
    },
    {
        "role": "wave1DecisionTests",
        "path": WAVE1_TESTS_PATH,
        "rawSha256": "1fe982561a61d9f73e0d2eb2b3f9d35b07b080ea042835de57e78c2c6ab95249",
    },
    {
        "role": "wave1ReviewExecutionPermitV3",
        "path": REVIEW_PERMIT_PATH,
        "rawSha256": "e9b92730e558fc128ab919f8b1e1da73625d2a14df8288f119a1802f269a63ef",
        "contentSha256": "dd2237e3bd34a254c2dd8567bd7cc70685a012fceb34315615bfa7beb03b25de",
        "scope": "permit_without_contentBinding",
        "requiredStatus": (
            "dependency_source_review_wave1_execution_authorized_not_consumed"
        ),
    },
    {
        "role": "wave1ReviewClaimV3",
        "path": REVIEW_CLAIM_PATH,
        "rawSha256": "b4cc9d630e706b7a2adfee8c63bf27f9f98a535dfb896d917053f5fffcb11f22",
        "contentSha256": "d86e6c870775bcbc03a4cd0f7742e481f98a0aac5f83d7c515e7870c17400979",
        "scope": "claim_without_contentBinding",
    },
    {
        "role": "wave1ReviewResultV3",
        "path": REVIEW_RESULT_PATH,
        "rawSha256": "cd7bba257995bb98199a336d343bf98859e661a1abc0dbac5666c314d8fd519f",
        "contentSha256": "87d5357b1def504b5a4d1608fe412f6931af2ef75ffd16b3260a9e3487707c46",
        "scope": "result_without_contentBinding",
        "requiredStatus": "wave1_graph_discovery_complete_new_wave_required",
    },
    {
        "role": "wave1ReviewManifestV3",
        "path": REVIEW_MANIFEST_PATH,
        "rawSha256": "4559c8fc207cad88b2d963e23b4132b7a053aeb77bfc7aa758fb58199c58b933",
        "contentSha256": "c988c56744170bb20e4d8f4e98aeb902009da757d776f6ec03de5f6086573e84",
        "scope": "manifest_without_contentBinding",
    },
    {
        "role": "wave1ReviewReadbackClaimV3",
        "path": READBACK_CLAIM_PATH,
        "rawSha256": "22b41464dfad474a3155c12e57d2f6b70f2331bd5a11bd8b4160b679f01e724d",
        "contentSha256": "027c01452ad7a7c6975c91e56de87d2502f591d46631caae80ed559affac7751",
        "scope": "readback_claim_without_contentBinding",
    },
    {
        "role": "wave1ReviewReadbackReceiptV3",
        "path": READBACK_RECEIPT_PATH,
        "rawSha256": "938ab9dc83e3580c6801c8d569a25389eae591c21b3a82df03980a06db812a5a",
        "contentSha256": "fd26296ad715b9bded8a4715e7d36aa1c285623fa746780f6349ff170c54853a",
        "scope": "readback_receipt_without_contentBinding",
        "requiredStatus": (
            "dependency_source_review_wave1_readback_complete_"
            "new_tuple_wave_required_manifest_pending"
        ),
    },
    {
        "role": "wave1ReviewReadbackManifestV3",
        "path": READBACK_MANIFEST_PATH,
        "rawSha256": "ad5a633713f45d273f905cb7f02a5b08f884b1b98e48eb1ba478e6bce59b479c",
        "contentSha256": "6605c2ea18b9471ca6b8c7768cd77288ba9b7a96a2482a8b685275a01a8b5e05",
        "scope": "readback_manifest_without_contentBinding",
        "requiredStatus": (
            "dependency_source_review_wave1_readback_published_"
            "new_tuple_wave_required"
        ),
    },
    {
        "role": "wave1ReviewReadbackChecker",
        "path": READBACK_CHECKER_PATH,
        "rawSha256": "75dfcfd4b81844d67deb3ecac9a60c834d820034afcac930a91624d5402be86a",
    },
    {
        "role": "wave1ReviewReadbackTests",
        "path": READBACK_TESTS_PATH,
        "rawSha256": "d9c57a9188f2ddd21b60676ffd3e642213534ddcdb79e59a615a320eefda62f1",
    },
)


def public_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in binding.items()
        if key not in {"scope"}
    }


def expected_resource(
    tuple_order: int,
    stem: str,
    module: str,
    version: str,
    kind: str,
    h1: str,
) -> dict[str, Any]:
    ordinal = 2 * tuple_order - (1 if kind == "mod" else 0)
    return {
        "order": ordinal,
        "kind": kind,
        "checksumKind": "go_mod_h1" if kind == "mod" else "module_zip_h1",
        "url": (
            "https://proxy.golang.org/"
            f"{proxy_escape(module)}/@v/{proxy_escape(version)}.{kind}"
        ),
        "expectedH1": h1,
        "identityStatus": "held_go_sum_h1_bound_future_bytes_unverified",
        "outputPath": f"{WAVE2_FINAL_PATH}/{stem}.{kind}",
    }


def expected_tuples() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, source in enumerate(TUPLE_INPUTS, start=1):
        module = source["module"]
        version = source["version"]
        digest = tuple_digest(module, version)
        stem = f"{order:03d}-{digest[:20]}"
        evidence = source["checksum"]
        rows.append(
            {
                "tupleOrder": order,
                "tupleId": f"wave2-{order:03d}-{digest[:12]}",
                "tupleDigestAlgorithm": "sha256(module_lf_version_lf)",
                "tupleDigestSha256": digest,
                "module": module,
                "version": version,
                "selectedByGraphAlgorithm": source["selected"],
                "acquisitionAuthorized": False,
                "requiresSeparateWaveDecision": True,
                "parentDeclarations": list(source["parents"]),
                "checksumEvidence": evidence,
                "resources": [
                    expected_resource(
                        order,
                        stem,
                        module,
                        version,
                        "mod",
                        evidence["moduleModH1"],
                    ),
                    expected_resource(
                        order,
                        stem,
                        module,
                        version,
                        "zip",
                        evidence["moduleZipH1"],
                    ),
                ],
            }
        )
    return rows


def graph_binding() -> dict[str, Any]:
    return {
        "route": "new_tuple_wave_required",
        "sourceGraphAlgorithm": "go1.24_mvs_profile_union_fixed_point_v1",
        "readbackAlgorithm": "stored_eight_field_projection_byte_reconstruction_v1",
        "independentReconstructionAlgorithms": [
            "version_vertex_breadth_first_search",
            "version_vertex_monotone_full_set_scan",
        ],
        "independentReconstructionCount": 2,
        "storedProjectionEqualityVerified": True,
        "sourceGraphAlgorithmsReexecutedByReadback": False,
        "graphSha256": (
            "2c94906a07a40737e30ca832c215fa88d2233297c9fb0ea25755488d9a72408b"
        ),
        "moduleGraphAndFrontierSha256": (
            "0010de782d5d423be594d711ffcd0dc4b34aa02509bdb10947e606a16578ff53"
        ),
        "graphNodeCount": 132,
        "graphEdgeCount": 1047,
        "moduleNodeCount": 35,
        "moduleEdgeCount": 86,
        "selectedVersionCount": 25,
        "newTupleCount": 15,
        "selectedFrontierTupleCount": 5,
        "versionSpecificNonSelectedFrontierTupleCount": 10,
        "unmappedExternalImportCount": 0,
        "unresolvedDeclaredExternalImportCount": 0,
        "versionSpecificVertexTraversal": True,
        "fixedPointReached": False,
    }


def expected_decision_payload() -> dict[str, Any]:
    tuples = expected_tuples()
    resources = [
        resource
        for tuple_row in tuples
        for resource in tuple_row["resources"]
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave2"
        ),
        "schemaVersion": "1.0",
        "decisionId": (
            "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave2-v1"
        ),
        "recordedDate": "2026-07-24",
        "status": (
            "wave2_local_checksum_identity_and_30_resource_contract_"
            "prepared_future_bytes_unverified_acquisition_not_authorized"
        ),
        "predecessorBindings": [
            public_binding(binding) for binding in BINDING_INPUTS
        ],
        "graphBinding": graph_binding(),
        "sourceIdentityPolicy": {
            "tupleIdentity": "exact_module_and_exact_version",
            "versionSpecificVerticesPreserved": True,
            "lowerVersionTuplesMayNotBeDeduplicatedIntoSelectedVersions": True,
            "resourceIdentityCount": 30,
            "identityInputs": (
                "already_held_module_root_go_sum_module_and_go_mod_h1_pairs"
            ),
            "canonicalEvidenceSelection": (
                "direct_parent_then_lowest_source_tuple_order_then_"
                "lexical_path_member"
            ),
            "heldH1PairIsFutureByteExpectation": True,
            "futureModAndZipBytesMustEachMatchTheirBoundH1": True,
            "heldEvidenceIsFreshChecksumDatabaseProof": False,
            "freshChecksumDatabaseProofEstablishedByThisDecision": False,
            "sourceBytesAcquiredByThisDecision": False,
            "contentReviewEstablishedByThisDecision": False,
        },
        "wave": {
            "waveId": "g2-pion-ice-v4.3.0-dependency-source-wave2-v1",
            "tupleCount": 15,
            "selectedTupleCount": 5,
            "versionSpecificNonSelectedTupleCount": 10,
            "resourcesPerTuple": 2,
            "resourceCount": 30,
            "requestCount": 30,
            "requestOrder": "tuple_order_ascending_mod_then_zip",
            "orderedTupleSetSha256": sha256(canonical_bytes(tuples)),
            "orderedResourceSetSha256": sha256(canonical_bytes(resources)),
            "tuples": tuples,
        },
        "plannedAcquisitionContract": {
            "executionAuthorized": False,
            "separateOneUseExecutionPermitRequired": True,
            "networkAuthorizedByThisDecision": False,
            "requestMethod": "GET",
            "origin": "https://proxy.golang.org",
            "acceptedStatusCodes": [200],
            "exactOrderedRequestCount": 30,
            "redirectAllowed": False,
            "retryAllowed": False,
            "maximumRetryCount": 0,
            "queryAllowed": False,
            "fragmentAllowed": False,
            "alternateMirrorAllowed": False,
            "ambientProxyAllowed": False,
            "credentialsAllowed": False,
            "authorizationHeaderAllowed": False,
            "cookieAllowed": False,
            "userAuthenticationRequired": False,
            "responseBytesMustMatchBoundH1BeforeAcceptance": True,
            "modMustPrecedeZipForEachTuple": True,
            "automaticContinuationIntoReviewAllowed": False,
        },
        "resourceLimits": {
            "maximumRequestCount": 30,
            "maximumSingleModBytes": 1048576,
            "maximumSingleZipBytes": 16777216,
            "maximumAggregateResponseBytes": 67108864,
            "maximumZipEntryCountPerArchive": 20000,
            "maximumZipUncompressedBytesPerArchive": 134217728,
            "maximumCompressionRatio": 200,
        },
        "filesystemContract": {
            "claimPath": WAVE2_CLAIM_PATH,
            "stagingParentPath": DEPENDENCY_ROOT,
            "stagingNamePrefix": WAVE2_STAGING_PREFIX,
            "finalDirectoryPath": WAVE2_FINAL_PATH,
            "existingWave1NamespaceReusable": False,
            "claimMustBeCreatedExclusivelyByFutureRunner": True,
            "stagingMustBeSameFilesystemAsFinal": True,
            "symlinkAllowed": False,
            "hardlinkAllowed": False,
            "specialFileAllowed": False,
            "archiveExtractionAuthorized": False,
            "sourceLoadAuthorized": False,
            "sourceExecutionAuthorized": False,
        },
        "receiptContract": {
            "successReceiptPath": WAVE2_RECEIPT_PATH,
            "failureReceiptPath": WAVE2_FAILURE_PATH,
            "manifestPath": WAVE2_MANIFEST_PATH,
            "independentReadbackReceiptPath": WAVE2_READBACK_PATH,
            "independentReadbackManifestPath": WAVE2_READBACK_MANIFEST_PATH,
            "successReceiptRequiredBeforeManifest": True,
            "manifestWrittenLast": True,
            "independentReadbackRequired": True,
            "fixedPointGraphRerunRequiredAfterFutureReadback": True,
        },
        "namespaceContract": {
            "namespace": "wave-2-v1",
            "preparationPreflightRequiresEmptyNamespace": True,
            "wave1ClaimPathReused": False,
            "wave1StagingPrefixReused": False,
            "wave1FinalDirectoryReused": False,
            "collisionFailsBeforeNetwork": True,
        },
        "authority": {
            "personalProject": True,
            "userActionRequired": False,
            "externalAuthenticationRequired": False,
            "repositoryOwnerIdentityProofRequired": False,
            "accountLoginRequired": False,
            "privateKeyRequired": False,
            "tokenRequired": False,
            "productEndpointAuthenticationEvaluatedByThisDecision": False,
            "productEndpointAuthenticationIsSeparateRuntimeInvariant": True,
            "decisionIsExecutionPermit": False,
            "acquisitionAuthorized": False,
            "networkAuthorized": False,
            "filesystemMutationAuthorized": False,
            "gitOperationAuthorized": False,
        },
        "execution": {
            "decisionRecorded": True,
            "acquisitionExecuted": False,
            "permitConsumed": False,
            "requestCount": 0,
            "validatedModResourceCount": 0,
            "validatedZipResourceCount": 0,
            "validatedAndStagedResourceCount": 0,
            "acceptedTupleCount": 0,
            "acceptedArtifactCount": 0,
            "networkUsed": False,
            "successReceiptCreated": False,
            "failureReceiptCreated": False,
            "manifestCreated": False,
            "independentReadbackPassed": False,
            "sourceLoaded": False,
            "sourceExecuted": False,
            "packageManagerInvoked": False,
            "compileAttempted": False,
            "gitOperationPerformed": False,
        },
        "closure": {
            "dependencyFixedPointReached": False,
            "dependencySourceClosureComplete": False,
            "dependencySourceReviewed": False,
            "semanticClosureComplete": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "openFindingCount": 19,
            "findingsClosedByThisDecision": 0,
        },
        "nonClaims": [
            "this preparation decision is not an acquisition execution permit",
            "this preparation decision is not source acquisition or success evidence",
            "held go.sum h1 pairs are not fresh checksum database inclusion proofs",
            "future mod and zip response bytes remain unverified",
            "the 15 version-specific frontier tuples are not a dependency fixed point",
            "selectedByGraphAlgorithm false does not remove a frontier intake tuple",
            "proxy origin alone does not approve content",
            "wave1 claims outputs and namespaces are neither changed nor reused",
            "acquisition does not establish license security or semantic review",
            "this decision does not select a production library",
            "this decision does not close any finding or complete rung three",
            "product endpoint authentication is outside this preparation decision",
            "no repository account key signature token password or user authentication is required",
        ],
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW_SHA256,
        },
        "result": (
            "exact_15_graph_frontier_tuples_30_mod_zip_requests_and_"
            "held_h1_expectations_prepared_future_bytes_unverified"
        ),
        "nextAction": (
            "prepare_separate_versioned_wave2_checker_runner_tests_"
            "and_one_use_execution_permit"
        ),
    }


def expected_decision() -> dict[str, Any]:
    payload = expected_decision_payload()
    document = dict(payload)
    document["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return document


def normalize_require_line(line: str) -> tuple[str, str]:
    normalized = line.split("//", 1)[0].strip()
    if normalized.startswith("require "):
        normalized = normalized[len("require ") :].strip()
    normalized = normalized.replace('"', "")
    parts = normalized.split()
    require(len(parts) >= 2, "E_PARENT", "invalid go.mod require line")
    return parts[0], parts[1]


def safe_zip_members(data: bytes, label: str) -> list[tuple[zipfile.ZipInfo, bytes]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            infos = archive.infolist()
            require(len(infos) <= 20000, "E_ARCHIVE", f"{label}: entry limit")
            names: set[str] = set()
            output: list[tuple[zipfile.ZipInfo, bytes]] = []
            total = 0
            for info in infos:
                name = info.filename
                require(
                    type(name) is str
                    and name not in names
                    and "\x00" not in name
                    and "\n" not in name
                    and "\r" not in name
                    and "\\" not in name,
                    "E_ARCHIVE",
                    f"{label}: unsafe or duplicate member",
                )
                names.add(name)
                pure = PurePosixPath(name)
                require(
                    not pure.is_absolute()
                    and all(part not in {"", ".", ".."} for part in pure.parts),
                    "E_ARCHIVE",
                    f"{label}: non-canonical member",
                )
                require(
                    not (info.flag_bits & 0x1)
                    and info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED},
                    "E_ARCHIVE",
                    f"{label}: encrypted or unsupported member",
                )
                total += info.file_size
                require(
                    info.file_size <= 134217728 and total <= 268435456,
                    "E_ARCHIVE",
                    f"{label}: uncompressed limit",
                )
                if name.endswith("/go.sum"):
                    require(
                        not info.is_dir() and info.file_size <= 1048576,
                        "E_ARCHIVE",
                        f"{label}: go.sum member limit",
                    )
                    if info.compress_size > 0:
                        require(
                            info.file_size <= max(1, info.compress_size) * 200,
                            "E_ARCHIVE",
                            f"{label}: go.sum compression ratio",
                        )
                    body = archive.read(info)
                    require(
                        len(body) == info.file_size,
                        "E_ARCHIVE",
                        f"{label}: go.sum size drift",
                    )
                    output.append((info, body))
            return output
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        fail("E_ARCHIVE", f"{label}: {exc}")


def read_cached(
    relative: str,
    snapshots: dict[str, Snapshot],
    limit: int = 16 * 1024 * 1024,
) -> bytes:
    if relative not in snapshots:
        snapshots[relative] = secure_read(relative, limit)
    return snapshots[relative].data


def verify_parent_declarations(
    result: dict[str, Any],
    snapshots: dict[str, Snapshot],
) -> None:
    modules = {
        (row["module"], row["version"]): row
        for row in result["moduleMetadata"]["modules"]
    }
    for source in TUPLE_INPUTS:
        target = (source["module"], source["version"])
        expected_parents = {
            (edge["module"], edge["version"]) for edge in source["parents"]
        }
        observed_parents = {
            parent_tuple
            for parent_tuple, row in modules.items()
            if any(
                (requirement["module"], requirement["version"]) == target
                for requirement in row["metadata"]["requires"]
            )
        }
        strict_equal(
            observed_parents,
            expected_parents,
            "E_PARENT",
            f"parent set for {target[0]}@{target[1]}",
        )
        for edge in source["parents"]:
            body = read_cached(edge["modPath"], snapshots, 1024 * 1024)
            strict_equal(
                sha256(body),
                edge["modRawSha256"],
                "E_PARENT",
                f"parent mod raw hash {edge['modPath']}",
            )
            try:
                lines = body.decode("utf-8").splitlines()
            except UnicodeDecodeError as exc:
                fail("E_PARENT", f"{edge['modPath']}: {exc}")
            line_number = edge["requireLine"]
            require(
                type(line_number) is int
                and not isinstance(line_number, bool)
                and 1 <= line_number <= len(lines),
                "E_PARENT",
                f"{edge['modPath']}: line out of range",
            )
            strict_equal(
                normalize_require_line(lines[line_number - 1]),
                target,
                "E_PARENT",
                f"{edge['modPath']}:{line_number}",
            )


def archive_descriptors(permit: dict[str, Any]) -> list[dict[str, Any]]:
    bindings = permit["inputBindings"]
    root_archive = bindings["rootArchive"]
    descriptors = [
        {
            "sourceTupleOrder": 0,
            "sourceModule": "github.com/pion/ice/v4",
            "sourceVersion": "v4.3.0",
            "path": root_archive["path"],
            "rawSha256": root_archive["rawSha256"],
        }
    ]
    for resource in bindings["resources"]:
        if resource["kind"] != "zip":
            continue
        descriptors.append(
            {
                "sourceTupleOrder": resource["tupleOrder"],
                "sourceModule": resource["module"],
                "sourceVersion": resource["version"],
                "path": resource["path"],
                "rawSha256": resource["rawSha256"],
            }
        )
    strict_equal(len(descriptors), 20, "E_CHECKSUM", "held archive count")
    return descriptors


def matching_h1_sources(
    module: str,
    version: str,
    descriptors: list[dict[str, Any]],
    snapshots: dict[str, Snapshot],
) -> list[dict[str, Any]]:
    zip_prefix = f"{module} {version} "
    mod_prefix = f"{module} {version}/go.mod "
    matches: list[dict[str, Any]] = []
    for descriptor in descriptors:
        body = read_cached(descriptor["path"], snapshots)
        strict_equal(
            sha256(body),
            descriptor["rawSha256"],
            "E_CHECKSUM",
            f"archive raw hash {descriptor['path']}",
        )
        for info, member_body in safe_zip_members(body, descriptor["path"]):
            try:
                lines = member_body.decode("utf-8").splitlines()
            except UnicodeDecodeError as exc:
                fail("E_CHECKSUM", f"{descriptor['path']}::{info.filename}: {exc}")
            zip_rows = [
                (index, line.split()[-1])
                for index, line in enumerate(lines, start=1)
                if line.startswith(zip_prefix)
            ]
            mod_rows = [
                (index, line.split()[-1])
                for index, line in enumerate(lines, start=1)
                if line.startswith(mod_prefix)
            ]
            for zip_row in zip_rows:
                for mod_row in mod_rows:
                    matches.append(
                        {
                            **descriptor,
                            "goSumMember": info.filename,
                            "goSumRawSha256": sha256(member_body),
                            "moduleZipLine": zip_row[0],
                            "moduleModLine": mod_row[0],
                            "moduleZipH1": zip_row[1],
                            "moduleModH1": mod_row[1],
                        }
                    )
    return matches


def verify_checksum_evidence(
    permit: dict[str, Any],
    snapshots: dict[str, Snapshot],
) -> None:
    descriptors = archive_descriptors(permit)
    for source in TUPLE_INPUTS:
        module = source["module"]
        version = source["version"]
        expected = source["checksum"]
        matches = matching_h1_sources(module, version, descriptors, snapshots)
        require(matches, "E_CHECKSUM", f"no held h1 pair: {module}@{version}")
        pairs = {
            (row["moduleZipH1"], row["moduleModH1"]) for row in matches
        }
        strict_equal(
            len(matches),
            expected["heldPairSourceCount"],
            "E_CHECKSUM",
            f"held h1 pair source count: {module}@{version}",
        )
        strict_equal(
            pairs,
            {(expected["moduleZipH1"], expected["moduleModH1"])},
            "E_CHECKSUM",
            f"conflicting held h1 pairs: {module}@{version}",
        )
        parents = {
            (edge["module"], edge["version"]) for edge in source["parents"]
        }
        matches.sort(
            key=lambda row: (
                0
                if (row["sourceModule"], row["sourceVersion"]) in parents
                else 1,
                row["sourceTupleOrder"],
                row["path"],
                row["goSumMember"],
            )
        )
        selected = matches[0]
        expected_projection = {
            "sourceTupleOrder": expected["sourceTupleOrder"],
            "sourceModule": expected["sourceModule"],
            "sourceVersion": expected["sourceVersion"],
            "path": expected["archivePath"],
            "rawSha256": expected["archiveRawSha256"],
            "goSumMember": expected["goSumMember"],
            "goSumRawSha256": expected["goSumRawSha256"],
            "moduleZipLine": expected["moduleZipLine"],
            "moduleModLine": expected["moduleModLine"],
            "moduleZipH1": expected["moduleZipH1"],
            "moduleModH1": expected["moduleModH1"],
        }
        strict_equal(
            selected,
            expected_projection,
            "E_CHECKSUM",
            f"canonical checksum evidence: {module}@{version}",
        )
        strict_equal(
            (selected["sourceModule"], selected["sourceVersion"]) in parents,
            expected["sourceIsDirectParent"],
            "E_CHECKSUM",
            f"direct-parent evidence flag: {module}@{version}",
        )


def verify_graph(
    result: dict[str, Any],
    readback: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    graph = result["graphDiscovery"]
    expected = graph_binding()
    projection = {
        "route": manifest["route"],
        "sourceGraphAlgorithm": graph["algorithm"],
        "readbackAlgorithm": readback["graphVerification"]["algorithm"],
        "independentReconstructionAlgorithms": readback["graphVerification"][
            "independentReconstructionAlgorithms"
        ],
        "independentReconstructionCount": readback["graphVerification"][
            "independentReconstructionCount"
        ],
        "storedProjectionEqualityVerified": readback["graphVerification"][
            "storedProjectionEqualityVerified"
        ],
        "sourceGraphAlgorithmsReexecutedByReadback": readback[
            "graphVerification"
        ]["sourceGraphAlgorithmsReexecuted"],
        "graphSha256": graph["graphSha256"],
        "moduleGraphAndFrontierSha256": graph["moduleGraphAndFrontierSha256"],
        "graphNodeCount": graph["graphNodeCount"],
        "graphEdgeCount": graph["graphEdgeCount"],
        "moduleNodeCount": graph["moduleNodeCount"],
        "moduleEdgeCount": graph["moduleEdgeCount"],
        "selectedVersionCount": len(graph["selectedVersions"]),
        "newTupleCount": graph["newTupleCount"],
        "selectedFrontierTupleCount": sum(
            row["selectedByGraphAlgorithm"] for row in graph["exactFrontier"]
        ),
        "versionSpecificNonSelectedFrontierTupleCount": sum(
            not row["selectedByGraphAlgorithm"] for row in graph["exactFrontier"]
        ),
        "unmappedExternalImportCount": graph["unmappedExternalImportCount"],
        "unresolvedDeclaredExternalImportCount": graph[
            "unresolvedDeclaredExternalImportCount"
        ],
        "versionSpecificVertexTraversal": graph["versionSpecificVertexTraversal"],
        "fixedPointReached": graph["fixedPointReached"],
    }
    strict_equal(projection, expected, "E_GRAPH", "graph binding")
    expected_frontier = [
        {
            "module": source["module"],
            "version": source["version"],
            "selectedByGraphAlgorithm": source["selected"],
            "acquisitionAuthorized": False,
            "requiresSeparateWaveDecision": True,
        }
        for source in TUPLE_INPUTS
    ]
    strict_equal(
        graph["exactFrontier"],
        expected_frontier,
        "E_GRAPH",
        "exact version-specific frontier",
    )
    strict_equal(
        graph["newlyReachableTuples"],
        expected_frontier,
        "E_GRAPH",
        "newly reachable tuples",
    )


def verify_predecessors(
    documents: dict[str, dict[str, Any]],
    snapshots: dict[str, Snapshot],
) -> None:
    for binding in BINDING_INPUTS:
        path = binding["path"]
        data = read_cached(path, snapshots)
        strict_equal(
            sha256(data),
            binding["rawSha256"],
            "E_LINEAGE",
            f"rawSha256:{path}",
        )
        if "contentSha256" not in binding:
            continue
        document = parse_json(data, path)
        documents[path] = document
        verify_content_binding(
            document,
            path,
            binding["scope"],
            binding["contentSha256"],
        )
        if "requiredStatus" in binding:
            strict_equal(
                document.get("status"),
                binding["requiredStatus"],
                "E_LINEAGE",
                f"status:{path}",
            )


def verify_namespace_empty() -> None:
    exact_paths = (
        WAVE2_CLAIM_PATH,
        WAVE2_PARENT_PATH,
        WAVE2_FINAL_PATH,
        WAVE2_RECEIPT_PATH,
        WAVE2_FAILURE_PATH,
        WAVE2_MANIFEST_PATH,
        WAVE2_READBACK_PATH,
        WAVE2_READBACK_MANIFEST_PATH,
    )
    for relative in exact_paths:
        path = ROOT.joinpath(*validate_relative_path(relative))
        require(
            not path.exists() and not path.is_symlink(),
            "E_NAMESPACE",
            f"premature wave2 artifact: {relative}",
        )
    parent_path = ROOT.joinpath(*validate_relative_path(DEPENDENCY_ROOT))
    try:
        entries = list(os.scandir(parent_path))
    except OSError as exc:
        fail("E_NAMESPACE", f"could not inventory wave2 staging parent: {exc}")
    for entry in entries:
        require(
            not entry.name.startswith(WAVE2_STAGING_PREFIX),
            "E_NAMESPACE",
            f"premature wave2 staging artifact: {entry.name}",
        )


def check(
    root: Path,
    *,
    require_namespace_preflight: bool = False,
    before_final_barrier: Callable[[dict[str, Snapshot]], None] | None = None,
) -> dict[str, Any]:
    global ROOT
    ROOT = root
    snapshots: dict[str, Snapshot] = {}
    documents: dict[str, dict[str, Any]] = {}
    try:
        decision_data = read_cached(DECISION_PATH, snapshots, 4 * 1024 * 1024)
        reader_data = read_cached(READER_PATH, snapshots, 1024 * 1024)
        strict_equal(
            sha256(reader_data),
            EXPECTED_READER_RAW_SHA256,
            "E_READER",
            "reader raw sha256",
        )
        verify_predecessors(documents, snapshots)
        decision = parse_json(decision_data, DECISION_PATH)
        strict_equal(
            decision,
            expected_decision(),
            "E_DECISION",
            "wave2 decision",
        )
        verify_content_binding(
            decision,
            DECISION_PATH,
            "decision_without_contentBinding",
        )
        result = documents[REVIEW_RESULT_PATH]
        readback = documents[READBACK_RECEIPT_PATH]
        manifest = documents[READBACK_MANIFEST_PATH]
        verify_graph(result, readback, manifest)
        verify_parent_declarations(result, snapshots)
        verify_checksum_evidence(documents[REVIEW_PERMIT_PATH], snapshots)
        if require_namespace_preflight:
            verify_namespace_empty()
        if before_final_barrier is not None:
            before_final_barrier(snapshots)
        for snapshot in snapshots.values():
            verify_snapshot(snapshot)
        if require_namespace_preflight:
            verify_namespace_empty()
        return {
            "status": decision["status"],
            "result": decision["result"],
            "nextAction": decision["nextAction"],
            "tupleCount": decision["wave"]["tupleCount"],
            "resourceCount": decision["wave"]["resourceCount"],
            "selectedTupleCount": decision["wave"]["selectedTupleCount"],
            "versionSpecificNonSelectedTupleCount": decision["wave"][
                "versionSpecificNonSelectedTupleCount"
            ],
            "graphSha256": decision["graphBinding"]["graphSha256"],
            "orderedTupleSetSha256": decision["wave"][
                "orderedTupleSetSha256"
            ],
            "orderedResourceSetSha256": decision["wave"][
                "orderedResourceSetSha256"
            ],
            "namespacePreflightChecked": require_namespace_preflight,
            "externalAuthenticationRequired": decision["authority"][
                "externalAuthenticationRequired"
            ],
            "userActionRequired": decision["authority"]["userActionRequired"],
            "acquisitionAuthorized": decision["authority"][
                "acquisitionAuthorized"
            ],
            "networkUsed": decision["execution"]["networkUsed"],
            "gitOperationPerformed": decision["execution"][
                "gitOperationPerformed"
            ],
        }
    finally:
        close_snapshots(snapshots)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="also require every future wave2-v1 output namespace to be absent",
    )
    parser.add_argument(
        "--print-expected",
        action="store_true",
        help="print the canonical expected JSON without reading repository files",
    )
    args = parser.parse_args()
    if args.print_expected:
        print(json.dumps(expected_decision(), indent=2, ensure_ascii=True))
        return 0
    try:
        result = check(
            args.root.resolve(),
            require_namespace_preflight=args.preflight,
        )
    except CheckError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
