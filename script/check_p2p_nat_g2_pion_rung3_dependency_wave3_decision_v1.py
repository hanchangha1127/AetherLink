#!/usr/bin/env python3
"""Validate the read-only Wave3 dependency identity decision."""

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
    raise RuntimeError("Wave3 checker requires `python3 -I -B -S`")

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import types
from typing import Any, Mapping, Sequence
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave3-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave3-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v1.py"
)
PERMIT_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_combined_fixed_point_"
    "readback_recovery_execution_permit_v3.py"
)
EXPECTED_PERMIT_CHECKER_RAW = (
    "0635504df96981c8e27b0ee3b4b677dd5a1811332b7b67554d90836ac72cc1c6"
)
EXPECTED_READER_RAW = (
    "9ed3ad459aa88c2ff559c8bfb96689dd5e3ca16be3cbe5a3e62d72c9aabb43fd"
)
RESULT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-result-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-manifest-v1.json"
)
ORIGINAL_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".combined-fixed-point-v1.claim"
)
V3_DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-decision-v3.json"
)
V3_PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-recovery-execution-permit-v3.json"
)
V3_CLAIM_PATH = (
    "build/offline-source/pion-ice-v4.3.0/dependencies/"
    ".combined-fixed-point-readback-v3.claim"
)
V3_RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-readback-v3.json"
)
V3_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-combined-fixed-point-"
    "readback-manifest-v3.json"
)
EXPECTED_TERMINAL_RAW = {
    ORIGINAL_CLAIM_PATH: (
        "fe362569ffcd4f4256e88338fd4f2b0d96b35c8cd443af47ac5c92a73d7d0c03"
    ),
    RESULT_PATH: (
        "6fcf6f231455d4e83d1144215234c056d15a9677fe9956c1ee4f134735c99b36"
    ),
    MANIFEST_PATH: (
        "d1c45eb7cca1645ba49e3a4974d77074ada7b195aaaeee62f448c9348cff8dd8"
    ),
    V3_CLAIM_PATH: (
        "9f317960dfb9aedc81fd170afdacd1b2210284231ceb8e1148136a6363e2e96b"
    ),
    V3_RECEIPT_PATH: (
        "cdca35b55c81d943a10bcf82bbad10a158e9711a97297baeac880f8ad206ac05"
    ),
    V3_MANIFEST_PATH: (
        "6ae787ec2f9c45d91dd658933c6adb0572301a3eafde2445d5db6895c1bdb90f"
    ),
}
EXPECTED_RESULT_CONTENT = (
    "3de4a5c0e1024c97c8e2e5f1e89041bc57d66d0a43c0ee7571b34b8185f0face"
)
EXPECTED_V3_DECISION_RAW = (
    "0b650f466e2ef2df2362d11747d15b34db96ef6a63e70556f443137fd43390df"
)
EXPECTED_V3_DECISION_CONTENT = (
    "7600954f9887ffdd629a56eca6f3eed20542c0843787a3b8f5cfb240b17781ff"
)
EXPECTED_V3_PERMIT_RAW = (
    "0484a20f26411a5526740c6c327f305c8480214d629e69abee53c66f9532cdaf"
)
EXPECTED_V3_PERMIT_CONTENT = (
    "111d0a2357aa31321a559aad38202c66c6e6f1f8eb324e86fb9e24d3531da018"
)
EXPECTED_V3_RECEIPT_CONTENT = (
    "755c7d377f171435ddd39f6d63fd2dc8fa5207e23ee89e0c21f698c7c9a5f1d8"
)
EXPECTED_V3_MANIFEST_CONTENT = (
    "7a7403e3eef8091598b7e7238701de5582c1188d874f6677504ef1c90037da3b"
)
EXPECTED_GRAPH_SHA256 = (
    "541fc40bcfe87640033db54948911972dab9a6cab7e0b26d8021a89660be69d8"
)
EXPECTED_MODULE_FRONTIER_SHA256 = (
    "21043c3939299d0dee7676009e178c1938e243114d90a3d0c217a564aed02f1e"
)
EXPECTED_FRONTIER_SHA256 = (
    "92defc23ccb192a6cb88a0ea3ecb399f00580f39fea41d34eb2125313a61569a"
)
EXPECTED_SOURCE_SET_SHA256 = (
    "c744597d53e9bf50611f154421f661aec19f95a767dcbb9a80aa653fe83f2036"
)
MAXIMUM_TOOL_BYTES = 4 * 1024 * 1024
MAXIMUM_JSON_BYTES = 8 * 1024 * 1024
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
WAVE3_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-3-v1.claim"
WAVE3_STAGING_PREFIX = ".wave-3-v1-staging-"
WAVE3_FINAL_PATH = f"{DEPENDENCY_ROOT}/wave-3-v1"
WAVE3_FUTURE_DOCS = (
    f"{BASE}/bounded-dependency-source-acquisition-wave3-receipt-v1.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave3-failure-v1.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave3-manifest-v1.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave3-readback-v1.json",
    f"{BASE}/bounded-dependency-source-acquisition-wave3-readback-manifest-v1.json",
)

READER_BYTES = b"""# Bounded dependency source identity and acquisition decision Wave3 v1

This decision records the exact 16-tuple frontier reproduced from the frozen
69-source Wave1/Wave2 input set. Four tuples are graph-selected and twelve are
version-specific non-selected vertices; none may be dropped, replaced by a
higher version, or rejected.

The held evidence provides all 16 `go.mod` H1 identities and 15 module ZIP H1
identities. `github.com/kr/pty@v1.1.1` has the exact held `go.mod` H1
`h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ=` but no held ZIP H1.
Therefore Wave3 is not acquisition-ready and this document is not an execution
permit.

No dependency request, SumDB lookup, network access, file mutation, source
loading or execution, archive extraction, compilation, package-manager use,
subprocess, Git operation, device action, deployment, authentication,
credential, key, token, password, signature, or user action is authorized.
The only next action is to prepare a separate authentication-free public
checksum identity-resolution decision for the missing ZIP identity.
"""


class DecisionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_OPERATION_COUNTERS = {
    "heldArchiveOpenCount": 0,
    "heldGoSumMemberDecodeCount": 0,
    "futureResponseDecodeCount": 0,
}


def reset_operation_counters() -> None:
    for key in _OPERATION_COUNTERS:
        _OPERATION_COUNTERS[key] = 0


def operation_counters() -> dict[str, int]:
    return dict(_OPERATION_COUNTERS)


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
            parse_float=lambda _: (_ for _ in ()).throw(DecisionError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(
                DecisionError("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def bootstrap_read(path: str, expected: str) -> bytes:
    current = ROOT
    for component in path.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_BOOTSTRAP",
        )
    fd = os.open(
        ROOT / path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
    )
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_BOOTSTRAP",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_BOOTSTRAP")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(fd, 1) == b"", "E_BOOTSTRAP")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_nlink,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_nlink,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            and sha256(raw) == expected,
            "E_BOOTSTRAP",
        )
        return raw
    finally:
        os.close(fd)


def execute_module(name: str, path: str, raw: bytes) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / path),
            "__loader__": None,
            "__name__": name,
            "__package__": None,
        }
    )
    exec(
        compile(raw, path, "exec", dont_inherit=True, optimize=0),
        module.__dict__,
        module.__dict__,
    )
    return module


PERMIT = execute_module(
    "wave3_frozen_v3_permit",
    PERMIT_CHECKER_PATH,
    bootstrap_read(PERMIT_CHECKER_PATH, EXPECTED_PERMIT_CHECKER_RAW),
)

FRONTIER = (
    ("github.com/kr/pty", "v1.1.1", True),
    ("github.com/pion/transport/v4", "v4.0.1", False),
    ("github.com/stretchr/testify", "v1.8.4", False),
    ("golang.org/x/crypto", "v0.32.0", False),
    ("golang.org/x/crypto", "v0.33.0", False),
    ("golang.org/x/mod", "v0.31.0", False),
    ("golang.org/x/mod", "v0.32.0", True),
    ("golang.org/x/net", "v0.48.0", False),
    ("golang.org/x/sync", "v0.19.0", True),
    ("golang.org/x/sys", "v0.29.0", False),
    ("golang.org/x/term", "v0.28.0", False),
    ("golang.org/x/term", "v0.29.0", False),
    ("golang.org/x/text", "v0.21.0", False),
    ("golang.org/x/text", "v0.22.0", False),
    ("golang.org/x/tools", "v0.40.0", False),
    ("golang.org/x/tools", "v0.41.0", True),
)
PARENTS = {
    ("github.com/kr/pty", "v1.1.1"): (("github.com/kr/text", "v0.1.0"),),
    ("github.com/pion/transport/v4", "v4.0.1"): (
        ("github.com/pion/dtls/v3", "v3.1.4"),
    ),
    ("github.com/stretchr/testify", "v1.8.4"): (
        ("github.com/stretchr/objx", "v0.5.2"),
    ),
    ("golang.org/x/crypto", "v0.32.0"): (("golang.org/x/net", "v0.34.0"),),
    ("golang.org/x/crypto", "v0.33.0"): (("golang.org/x/net", "v0.35.0"),),
    ("golang.org/x/mod", "v0.31.0"): (("golang.org/x/text", "v0.33.0"),),
    ("golang.org/x/mod", "v0.32.0"): (("golang.org/x/text", "v0.34.0"),),
    ("golang.org/x/net", "v0.48.0"): (("golang.org/x/crypto", "v0.47.0"),),
    ("golang.org/x/sync", "v0.19.0"): (
        ("golang.org/x/text", "v0.33.0"),
        ("golang.org/x/text", "v0.34.0"),
    ),
    ("golang.org/x/sys", "v0.29.0"): (
        ("github.com/pion/transport/v3", "v3.1.1"),
        ("golang.org/x/net", "v0.34.0"),
    ),
    ("golang.org/x/term", "v0.28.0"): (("golang.org/x/net", "v0.34.0"),),
    ("golang.org/x/term", "v0.29.0"): (("golang.org/x/net", "v0.35.0"),),
    ("golang.org/x/text", "v0.21.0"): (("golang.org/x/net", "v0.34.0"),),
    ("golang.org/x/text", "v0.22.0"): (("golang.org/x/net", "v0.35.0"),),
    ("golang.org/x/tools", "v0.40.0"): (("golang.org/x/text", "v0.33.0"),),
    ("golang.org/x/tools", "v0.41.0"): (("golang.org/x/text", "v0.34.0"),),
}
H1 = {
    ("github.com/kr/pty", "v1.1.1"): (
        "h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ=",
        None,
    ),
    ("github.com/pion/transport/v4", "v4.0.1"): (
        "h1:nEuEA4AD5lPdcIegQDpVLgNoDGreqM/YqmEx3ovP4jM=",
        "h1:sdROELU6BZ63Ab7FrOLn13M6YdJLY20wldXW2Cu2k8o=",
    ),
    ("github.com/stretchr/testify", "v1.8.4"): (
        "h1:sz/lmYIOXD/1dqDmKjjqLyZ2RngseejIcXlSw2iwfAo=",
        "h1:CcVxjf3Q8PM0mHUKJCdn+eZZtm5yQwehR5yeSVQQcUk=",
    ),
    ("golang.org/x/crypto", "v0.32.0"): (
        "h1:ZnnJkOaASj8g0AjIduWNlq2NRxL0PlBrbKVyZ6V/Ugc=",
        "h1:euUpcYgM8WcP71gNpTqQCn6rC2t6ULUPiOzfWaXVVfc=",
    ),
    ("golang.org/x/crypto", "v0.33.0"): (
        "h1:bVdXmD7IV/4GdElGPozy6U7lWdRXA4qyRVGJV57uQ5M=",
        "h1:IOBPskki6Lysi0lo9qQvbxiQ+FvsCC/YWOecCHAixus=",
    ),
    ("golang.org/x/mod", "v0.31.0"): (
        "h1:43JraMp9cGx1Rx3AqioxrbrhNsLl2l/iNAvuBkrezpg=",
        "h1:HaW9xtz0+kOcWKwli0ZXy79Ix+UW/vOfmWI5QVd2tgI=",
    ),
    ("golang.org/x/mod", "v0.32.0"): (
        "h1:SgipZ/3h2Ci89DlEtEXWUk/HteuRin+HHhN+WbNhguU=",
        "h1:9F4d3PHLljb6x//jOyokMv3eX+YDeepZSEo3mFJy93c=",
    ),
    ("golang.org/x/net", "v0.48.0"): (
        "h1:+ndRgGjkh8FGtu1w1FGbEC31if4VrNVMuKTgcAAnQRY=",
        "h1:zyQRTTrjc33Lhh0fBgT/H3oZq9WuvRR5gPC70xpDiQU=",
    ),
    ("golang.org/x/sync", "v0.19.0"): (
        "h1:9KTHXmSnoGruLpwFjVSX0lNNA75CykiMECbovNTZqGI=",
        "h1:vV+1eWNmZ5geRlYjzm2adRgW2/mcpevXNg50YZtPCE4=",
    ),
    ("golang.org/x/sys", "v0.29.0"): (
        "h1:/VUhepiaJMQUp4+oa/7Zr1D23ma6VTLIYjOOTFZPUcA=",
        "h1:TPYlXGxvx1MGTn2GiZDhnjPA9wZzZeGKHHmKhHYvgaU=",
    ),
    ("golang.org/x/term", "v0.28.0"): (
        "h1:Sw/lC2IAUZ92udQNf3WodGtn4k/XoLyZoh8v/8uiwek=",
        "h1:/Ts8HFuMR2E6IP/jlo7QVLZHggjKQbhu/7H0LJFr3Gg=",
    ),
    ("golang.org/x/term", "v0.29.0"): (
        "h1:6bl4lRlvVuDgSf3179VpIxBF0o10JUpXWOnI7nErv7s=",
        "h1:L6pJp37ocefwRRtYPKSWOWzOtWSxVajvz2ldH/xi3iU=",
    ),
    ("golang.org/x/text", "v0.21.0"): (
        "h1:4IBbMaMmOPCJ8SecivzSH54+73PCFmPWxNTLm+vZkEQ=",
        "h1:zyQAAkrwaneQ066sspRyJaG9VNi/YJ1NfzcGB3hZ/qo=",
    ),
    ("golang.org/x/text", "v0.22.0"): (
        "h1:YRoo4H8PVmsu+E3Ou7cqLVH8oXWIHVoX0jqUWALQhfY=",
        "h1:bofq7m3/HAFvbF51jz3Q9wLg3jkvSPuiZu/pD1XwgtM=",
    ),
    ("golang.org/x/tools", "v0.40.0"): (
        "h1:Ik/tzLRlbscWpqqMRjyWYDisX8bG13FrdXp3o4Sr9lc=",
        "h1:yLkxfA+Qnul4cs9QA3KnlFu0lVmd8JJfoq+E41uSutA=",
    ),
    ("golang.org/x/tools", "v0.41.0"): (
        "h1:XSY6eDqxVNiYgezAVqqCeihT4j1U2CCsqvH3WhQpnlg=",
        "h1:a9b8iMweWG+S0OBnlU36rzLp20z1Rp10w+IY2czHTQc=",
    ),
}


def package_bindings(include_decision: bool) -> list[dict[str, Any]]:
    paths = [READER_PATH, THIS_CHECKER_PATH, THIS_TESTS_PATH]
    if include_decision:
        paths.append(DECISION_PATH)
    return [
        {
            "path": path,
            "maximumBytes": (
                MAXIMUM_JSON_BYTES if path.startswith("docs/") else MAXIMUM_TOOL_BYTES
            ),
            "ownerOnly": False,
        }
        for path in paths
    ]


def output_bindings() -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "rawSha256": digest,
            "maximumBytes": MAXIMUM_JSON_BYTES,
            "ownerOnly": True,
        }
        for path, digest in (
            (V3_CLAIM_PATH, EXPECTED_TERMINAL_RAW[V3_CLAIM_PATH]),
            (V3_RECEIPT_PATH, EXPECTED_TERMINAL_RAW[V3_RECEIPT_PATH]),
            (V3_MANIFEST_PATH, EXPECTED_TERMINAL_RAW[V3_MANIFEST_PATH]),
        )
    ]


class DecisionContext:
    def __init__(self, root: Path, *, include_decision: bool) -> None:
        self.root = root
        self.lineage = None
        self.outputs = None
        self.package = None
        try:
            self.lineage = PERMIT.PermitContext(
                root,
                include_permit=True,
                phase="complete",
            )
            held_type = self.lineage.authority.decision_checker.HeldSet
            self.outputs = held_type(root, output_bindings())
            self.package = held_type(root, package_bindings(include_decision))
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def final_barrier(self) -> None:
        require(
            self.lineage is not None
            and self.outputs is not None
            and self.package is not None,
            "E_CONTEXT",
        )
        self.lineage.final_barrier("complete")
        self.outputs.final_barrier()
        self.package.final_barrier()
        recovery = PERMIT.DECISION.V2.RECOVERY
        namespace = self.lineage.namespace
        for path in (WAVE3_CLAIM_PATH, WAVE3_FINAL_PATH, *WAVE3_FUTURE_DOCS):
            require(
                recovery.absent_from_held_namespace(namespace, path),
                "E_NAMESPACE",
            )
        require(
            not any(
                name.startswith(WAVE3_STAGING_PREFIX)
                for name in recovery.held_dependency_names(namespace)
            ),
            "E_NAMESPACE",
        )
        self.outputs.final_barrier()
        self.lineage.final_barrier("complete")

    def close(self) -> None:
        if self.package is not None:
            self.package.close()
        if self.outputs is not None:
            self.outputs.close()
        if self.lineage is not None:
            self.lineage.close()


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "decision_without_contentBinding",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def normalize_declaration(line: str) -> str:
    value = line.split("//", 1)[0].strip().replace('"', "")
    if value.startswith("require "):
        value = value[len("require ") :].strip()
    return value


def parent_declarations(
    source_rows: Sequence[Mapping[str, Any]],
    raw: Mapping[str, bytes],
    module: str,
    version: str,
) -> list[dict[str, Any]]:
    by_identity = {
        (row["module"], row["version"], row["kind"]): row
        for row in source_rows
    }
    result: list[dict[str, Any]] = []
    for parent_module, parent_version in PARENTS[(module, version)]:
        row = by_identity[(parent_module, parent_version, "mod")]
        expected = f"{module} {version}"
        hits = [
            (number, line.strip())
            for number, line in enumerate(
                raw[row["path"]].decode("utf-8", errors="strict").splitlines(),
                1,
            )
            if normalize_declaration(line) == expected
        ]
        require(len(hits) == 1, "E_PARENT")
        result.append(
            {
                "parentModule": parent_module,
                "parentVersion": parent_version,
                "sourcePath": row["path"],
                "sourceRawSha256": row["rawSha256"],
                "line": hits[0][0],
                "declaration": hits[0][1],
            }
        )
    return result


def choose_h1_evidence(
    occurrences: Sequence[Mapping[str, Any]],
    parents: set[tuple[str, str]],
    expected_h1: str | None,
) -> dict[str, Any] | None:
    values = {row["h1"] for row in occurrences}
    require(len(values) <= 1, "E_H1_CONFLICT")
    if expected_h1 is None:
        require(not occurrences, "E_H1_UNEXPECTED")
        return None
    require(values == {expected_h1}, "E_H1_MISSING")
    ordered = sorted(
        occurrences,
        key=lambda row: (
            0
            if (row["sourceModule"], row["sourceVersion"]) in parents
            else 1,
            row["sourceTupleOrder"],
            row["sourceArchivePath"],
            row["memberPath"],
            row["lineNumber"],
        ),
    )
    selected = ordered[0]
    return {
        key: selected[key]
        for key in (
            "sourceModule",
            "sourceVersion",
            "sourceTupleOrder",
            "sourceArchivePath",
            "sourceArchiveRawSha256",
            "memberPath",
            "memberRawSha256",
            "lineNumber",
            "checksumKind",
            "exactRawLine",
            "module",
            "version",
            "h1",
        )
    }


def derive_h1_evidence(
    source_rows: Sequence[Mapping[str, Any]],
    source_raw: Mapping[str, bytes],
) -> tuple[dict[tuple[str, str], dict[str, Any]], int, int]:
    occurrences: list[dict[str, Any]] = []
    archive_open_count = 0
    member_decode_count = 0
    for row in source_rows:
        if row["kind"] not in {"root_zip", "zip"}:
            continue
        archive_open_count += 1
        _OPERATION_COUNTERS["heldArchiveOpenCount"] += 1
        raw = source_raw[row["path"]]
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                names = archive.namelist()
                require(len(names) == len(set(names)), "E_ARCHIVE")
                for member in sorted(names):
                    if not member.endswith("/go.sum"):
                        continue
                    info = archive.getinfo(member)
                    require(
                        not info.is_dir() and 0 <= info.file_size <= 1_048_576,
                        "E_ARCHIVE",
                    )
                    member_raw = archive.read(member)
                    require(len(member_raw) == info.file_size, "E_ARCHIVE")
                    member_decode_count += 1
                    _OPERATION_COUNTERS["heldGoSumMemberDecodeCount"] += 1
                    try:
                        lines = member_raw.decode(
                            "utf-8", errors="strict"
                        ).splitlines()
                    except UnicodeDecodeError as error:
                        raise DecisionError("E_H1_EVIDENCE") from error
                    for line_number, line in enumerate(lines, 1):
                        parts = line.strip().split()
                        if len(parts) != 3 or not parts[2].startswith("h1:"):
                            continue
                        version = parts[1]
                        kind = (
                            "go_mod_h1"
                            if version.endswith("/go.mod")
                            else "module_zip_h1"
                        )
                        version = version.removesuffix("/go.mod")
                        occurrences.append(
                            {
                                "sourceModule": row["module"],
                                "sourceVersion": row["version"],
                                "sourceTupleOrder": row["tupleOrder"],
                                "sourceArchivePath": row["path"],
                                "sourceArchiveRawSha256": row["rawSha256"],
                                "memberPath": member,
                                "memberRawSha256": sha256(member_raw),
                                "lineNumber": line_number,
                                "checksumKind": kind,
                                "exactRawLine": line,
                                "module": parts[0],
                                "version": version,
                                "h1": parts[2],
                            }
                        )
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            raise DecisionError("E_ARCHIVE") from error
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for module, version, _ in FRONTIER:
        parents = set(PARENTS[(module, version)])
        expected_mod, expected_zip = H1[(module, version)]
        matching = [
            row
            for row in occurrences
            if row["module"] == module and row["version"] == version
        ]
        result[(module, version)] = {
            "goMod": choose_h1_evidence(
                [
                    row
                    for row in matching
                    if row["checksumKind"] == "go_mod_h1"
                ],
                parents,
                expected_mod,
            ),
            "moduleZip": choose_h1_evidence(
                [
                    row
                    for row in matching
                    if row["checksumKind"] == "module_zip_h1"
                ],
                parents,
                expected_zip,
            ),
        }
    return result, archive_open_count, member_decode_count


def expected_payload(context: DecisionContext) -> dict[str, Any]:
    require(context.package.raw[READER_PATH] == READER_BYTES, "E_READER")
    lineage = context.lineage
    permit_expected = PERMIT.content_bound(PERMIT.expected_payload(lineage))
    permit_raw = lineage.package.raw[V3_PERMIT_PATH]
    permit_actual = PERMIT.strict_json(permit_raw)
    require(
        permit_raw == PERMIT.canonical_bytes(permit_actual)
        and permit_actual == permit_expected,
        "E_LINEAGE",
    )
    authority = lineage.authority
    result_raw = authority.terminal.raw[RESULT_PATH]
    manifest_raw = authority.terminal.raw[MANIFEST_PATH]
    claim_raw = authority.terminal.raw[ORIGINAL_CLAIM_PATH]
    result = strict_json(result_raw)
    manifest = strict_json(manifest_raw)
    require(
        sha256(result_raw) == EXPECTED_TERMINAL_RAW[RESULT_PATH]
        and sha256(manifest_raw) == EXPECTED_TERMINAL_RAW[MANIFEST_PATH]
        and sha256(claim_raw) == EXPECTED_TERMINAL_RAW[ORIGINAL_CLAIM_PATH]
        and result_raw == canonical_bytes(result)
        and result["contentBinding"]["sha256"] == EXPECTED_RESULT_CONTENT,
        "E_TERMINAL",
    )
    graph = result["candidateProjection"]["graphDiscovery"]
    frontier = graph["exactFrontier"]
    expected_frontier = [
        {
            "module": module,
            "version": version,
            "selectedByGraphAlgorithm": selected,
            "acquisitionAuthorized": False,
            "requiresSeparateWaveDecision": True,
        }
        for module, version, selected in FRONTIER
    ]
    require(
        frontier == expected_frontier
        and sha256(canonical_bytes(frontier)) == EXPECTED_FRONTIER_SHA256
        and result["graphSha256"] == EXPECTED_GRAPH_SHA256
        and graph["graphSha256"] == EXPECTED_GRAPH_SHA256
        and graph["moduleGraphAndFrontierSha256"]
        == EXPECTED_MODULE_FRONTIER_SHA256
        and graph["newTupleCount"] == 16
        and graph["fixedPointReached"] is False,
        "E_FRONTIER",
    )
    source_rows = result["candidateProjection"]["inputSet"]["sourceBindings"]
    source_raw = authority.sources.raw
    require(
        len(source_rows) == 69
        and result["candidateSourceProjectionSha256"]
        == EXPECTED_SOURCE_SET_SHA256
        and result["candidateProjection"]["inputSet"]["combinedInputSetSha256"]
        == EXPECTED_SOURCE_SET_SHA256,
        "E_SOURCE_HOLD",
    )
    for row in source_rows:
        require(
            row["path"] in source_raw
            and sha256(source_raw[row["path"]]) == row["rawSha256"],
            "E_SOURCE_HOLD",
        )
    h1_evidence, archive_open_count, member_decode_count = derive_h1_evidence(
        source_rows,
        source_raw,
    )
    receipt = strict_json(context.outputs.raw[V3_RECEIPT_PATH])
    publication = strict_json(context.outputs.raw[V3_MANIFEST_PATH])
    v3_claim_raw = context.outputs.raw[V3_CLAIM_PATH]
    require(
        sha256(v3_claim_raw) == EXPECTED_TERMINAL_RAW[V3_CLAIM_PATH]
        and receipt["contentBinding"]["sha256"] == EXPECTED_V3_RECEIPT_CONTENT
        and publication["contentBinding"]["sha256"]
        == EXPECTED_V3_MANIFEST_CONTENT
        and receipt["status"] == "formal_replacement_recovery_readback_complete"
        and publication["status"]
        == "formal_replacement_recovery_readback_published"
        and receipt["graphSha256"] == EXPECTED_GRAPH_SHA256
        and receipt["newTupleCount"] == 16
        and receipt["fixedPointReached"] is False,
        "E_READBACK",
    )
    tuples: list[dict[str, Any]] = []
    for order, (module, version, selected) in enumerate(FRONTIER, 1):
        digest = sha256(f"{module}\n{version}\n".encode())
        mod_h1, zip_h1 = H1[(module, version)]
        evidence = h1_evidence[(module, version)]
        parents = parent_declarations(
            source_rows,
            source_raw,
            module,
            version,
        )
        tuples.append(
            {
                "tupleOrder": order,
                "tupleId": f"wave3-{order:03d}-{digest[:12]}",
                "tupleDigestAlgorithm": "sha256(module_lf_version_lf)",
                "tupleDigestSha256": digest,
                "module": module,
                "version": version,
                "selectedByGraphAlgorithm": selected,
                "versionSpecificVertexRetained": True,
                "rejected": False,
                "parentDeclarations": parents,
                "checksumIdentity": {
                    "goModH1": mod_h1,
                    "moduleZipH1": zip_h1,
                    "goModH1Present": True,
                    "moduleZipH1Present": zip_h1 is not None,
                    "completePair": zip_h1 is not None,
                    "canonicalEvidenceSelection": (
                        "direct_parent_then_lowest_combined_source_tuple_"
                        "order_then_lexical_archive_member_line"
                    ),
                    "goModEvidence": evidence["goMod"],
                    "moduleZipEvidence": evidence["moduleZip"],
                },
                "acquisitionReady": zip_h1 is not None,
                "acquisitionAuthorized": False,
            }
        )
    require(
        len(tuples) == 16
        and sum(len(row["parentDeclarations"]) for row in tuples) == 18
        and sum(
            int(row["checksumIdentity"]["goModH1Present"])
            + int(row["checksumIdentity"]["moduleZipH1Present"])
            for row in tuples
        )
        == 31
        and sum(bool(row["acquisitionReady"]) for row in tuples) == 15,
        "E_IDENTITY",
    )
    require(
        archive_open_count == 35
        and member_decode_count == 22
        and sum(
            int(row["checksumIdentity"]["goModEvidence"] is not None)
            + int(row["checksumIdentity"]["moduleZipEvidence"] is not None)
            for row in tuples
        )
        == 31,
        "E_H1_EVIDENCE",
    )
    pty = tuples[0]
    require(
        pty["module"] == "github.com/kr/pty"
        and pty["version"] == "v1.1.1"
        and pty["selectedByGraphAlgorithm"] is True
        and pty["checksumIdentity"]["goModH1"]
        == "h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ="
        and pty["checksumIdentity"]["moduleZipH1"] is None
        and pty["acquisitionReady"] is False,
        "E_H1_MISSING",
    )
    source_files = [
        {"path": row["path"], "rawSha256": row["rawSha256"]}
        for row in source_rows
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave3"
        ),
        "schemaVersion": "1.0",
        "decisionId": (
            "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave3-v1"
        ),
        "recordedDate": "2026-07-24",
        "status": (
            "wave3_exact_16_frontier_identity_classified_"
            "15_complete_1_blocked_acquisition_not_authorized"
        ),
        "predecessorBindings": {
            "combinedTerminal": {
                "claim": {
                    "path": ORIGINAL_CLAIM_PATH,
                    "rawSha256": EXPECTED_TERMINAL_RAW[ORIGINAL_CLAIM_PATH],
                },
                "result": {
                    "path": RESULT_PATH,
                    "rawSha256": EXPECTED_TERMINAL_RAW[RESULT_PATH],
                    "contentSha256": EXPECTED_RESULT_CONTENT,
                },
                "manifest": {
                    "path": MANIFEST_PATH,
                    "rawSha256": EXPECTED_TERMINAL_RAW[MANIFEST_PATH],
                },
            },
            "v3Recovery": {
                "decision": {
                    "path": V3_DECISION_PATH,
                    "rawSha256": EXPECTED_V3_DECISION_RAW,
                    "contentSha256": EXPECTED_V3_DECISION_CONTENT,
                },
                "permit": {
                    "path": V3_PERMIT_PATH,
                    "rawSha256": EXPECTED_V3_PERMIT_RAW,
                    "contentSha256": EXPECTED_V3_PERMIT_CONTENT,
                },
                "claim": {
                    "path": V3_CLAIM_PATH,
                    "rawSha256": EXPECTED_TERMINAL_RAW[V3_CLAIM_PATH],
                },
                "receipt": {
                    "path": V3_RECEIPT_PATH,
                    "rawSha256": EXPECTED_TERMINAL_RAW[V3_RECEIPT_PATH],
                    "contentSha256": EXPECTED_V3_RECEIPT_CONTENT,
                },
                "manifest": {
                    "path": V3_MANIFEST_PATH,
                    "rawSha256": EXPECTED_TERMINAL_RAW[V3_MANIFEST_PATH],
                    "contentSha256": EXPECTED_V3_MANIFEST_CONTENT,
                },
            },
            "heldSourceInputSet": {
                "fileCount": 69,
                "combinedInputSetSha256": EXPECTED_SOURCE_SET_SHA256,
                "allFilesHeldByDescriptorThroughFinalBarrier": True,
                "files": source_files,
            },
        },
        "graphBinding": {
            "algorithm": "go1.24_mvs_profile_union_fixed_point_v1",
            "graphSha256": EXPECTED_GRAPH_SHA256,
            "moduleGraphAndFrontierSha256": EXPECTED_MODULE_FRONTIER_SHA256,
            "exactFrontierCanonicalSha256": EXPECTED_FRONTIER_SHA256,
            "graphNodeCount": 132,
            "graphEdgeCount": 1047,
            "moduleNodeCount": 51,
            "moduleEdgeCount": 132,
            "newTupleCount": 16,
            "fixedPointReached": False,
        },
        "wave": {
            "waveId": "g2-pion-ice-v4.3.0-dependency-source-wave3-v1",
            "tupleCount": 16,
            "graphSelectedTupleCount": 4,
            "versionSpecificNonSelectedTupleCount": 12,
            "rejectedTupleCount": 0,
            "parentDeclarationCount": 18,
            "goModH1Count": 16,
            "moduleZipH1Count": 15,
            "completeH1PairCount": 15,
            "identityRecordCount": 31,
            "requiredIdentityRecordCount": 32,
            "acquisitionReady": False,
            "tuples": tuples,
        },
        "identityGap": {
            "module": "github.com/kr/pty",
            "version": "v1.1.1",
            "missingIdentity": "module_zip_h1",
            "heldGoModH1": (
                "h1:pFQYn66WHrOpPYNljwOMqo10TkYh1fy3cYio2l3bCsQ="
            ),
            "missingValueMayBeGuessedOrInferred": False,
            "publicIdentityResolutionPerformed": False,
            "sumDbLookupPerformed": False,
        },
        "futureNamespaceReservation": {
            "claimPath": WAVE3_CLAIM_PATH,
            "stagingPrefix": WAVE3_STAGING_PREFIX,
            "finalDirectoryPath": f"{WAVE3_FINAL_PATH}/accepted",
            "futureDocuments": list(WAVE3_FUTURE_DOCS),
            "allCurrentlyAbsent": True,
            "reservationIsWriteAuthority": False,
        },
        "authority": {
            "decisionRecorded": True,
            "decisionIsExecutionPermit": False,
            "acquisitionAuthorized": False,
            "networkAuthorized": False,
            "sumDbLookupAuthorized": False,
            "filesystemMutationAuthorized": False,
            "archiveExtractionAuthorized": False,
            "sourceLoadAuthorized": False,
            "sourceExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "externalAuthenticationRequired": False,
            "repositoryOwnerIdentityProofRequired": False,
            "accountLoginRequired": False,
            "credentialRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
            "passwordRequired": False,
            "userActionRequired": False,
        },
        "operationCounters": {
            "networkOperationCount": 0,
            "sumDbLookupCount": 0,
            "fileWriteCount": 0,
            "heldArchiveOpenCount": archive_open_count,
            "heldGoSumMemberDecodeCount": member_decode_count,
            "futureResponseDecodeCount": 0,
            "filesystemExtractionCount": 0,
            "sourceLoadCount": 0,
            "sourceExecutionCount": 0,
            "compileCount": 0,
            "packageManagerInvocationCount": 0,
            "subprocessCount": 0,
            "gitOperationCount": 0,
            "deviceOperationCount": 0,
            "deploymentCount": 0,
            "authenticationCount": 0,
            "userActionCount": 0,
        },
        "closure": {
            "dependencyFixedPointReached": False,
            "dependencySourceClosureComplete": False,
            "dependencySourceReviewed": False,
            "semanticClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "releaseReady": False,
        },
        "nonClaims": [
            "this decision is not a network or acquisition execution permit",
            "31 of 32 identities is not sufficient for a 16 tuple acquisition",
            "github.com/kr/pty v1.1.1 zip h1 is not guessed or inferred",
            "selectedByGraphAlgorithm false does not remove a version vertex",
            "no tuple is rejected or replaced by a higher version",
            "held go.sum evidence is not fresh checksum database proof",
            "no public checksum identity resolution was performed",
            "no source bytes were acquired reviewed loaded extracted or executed",
            "no fixed point closure candidate or library selection is established",
            "roadmap and handoff text are not execution authority",
        ],
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW,
        },
        "result": (
            "exact_16_version_vertices_4_selected_12_nonselected_"
            "15_complete_h1_pairs_kr_pty_zip_h1_missing"
        ),
        "nextAction": (
            "prepare_separate_auth_free_public_checksum_"
            "identity_resolution_decision"
        ),
    }


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    reset_operation_counters()
    context = DecisionContext(ROOT, include_decision=verify_disk)
    try:
        expected = content_bound(expected_payload(context))
        if verify_disk:
            raw = context.package.raw[DECISION_PATH]
            actual = strict_json(raw)
            require(raw == canonical_bytes(actual) and actual == expected, "E_DECISION")
        context.final_barrier()
        counters = operation_counters()
        return expected, {
            "documentType": "aetherlink.wave3-identity-decision-check",
            "schemaVersion": "1.0",
            "status": "validated_decision_only_acquisition_not_authorized",
            "validationPassed": True,
            "tupleCount": 16,
            "identityRecordCount": 31,
            "requiredIdentityRecordCount": 32,
            "acquisitionReady": False,
            "acquisitionAuthorized": False,
            "networkUsed": False,
            "fileWriteCount": 0,
            "heldArchiveOpenCount": counters["heldArchiveOpenCount"],
            "heldGoSumMemberDecodeCount": counters[
                "heldGoSumMemberDecodeCount"
            ],
            "futureResponseDecodeCount": counters["futureResponseDecodeCount"],
            "sourceExecutionUsed": False,
            "subprocessCount": 0,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        context.close()


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise DecisionError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    reset_operation_counters()
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
                    "documentType": "aetherlink.wave3-identity-decision-error",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "acquisitionAuthorized": False,
                    "networkUsed": False,
                    "fileWriteCount": 0,
                    **operation_counters(),
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
                    "documentType": "aetherlink.wave3-identity-decision-error",
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "acquisitionAuthorized": False,
                    "networkUsed": False,
                    "fileWriteCount": 0,
                    **operation_counters(),
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
