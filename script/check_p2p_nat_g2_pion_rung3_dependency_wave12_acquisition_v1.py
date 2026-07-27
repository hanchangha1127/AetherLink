#!/usr/bin/env python3
"""Validate the Wave12 identity decision and one-use acquisition permit."""

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
    raise RuntimeError("Wave12 acquisition checker requires `python3 -I -B -S`")

import argparse
import ast
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import types
from typing import Any, Mapping, Sequence
import unicodedata
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave12-v1.json"
)
DECISION_READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave12-v1.md"
)
PERMIT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave12-"
    "execution-permit-v1.json"
)
PERMIT_READER_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave12-"
    "execution-permit-v1.md"
)
DECISION_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave12_decision_v1.py"
)
DECISION_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave12_decision_v1.py"
)
V10_CHECKER_PATH = "script/check_p2p_nat_g2_pion_combined_fixed_point_v10.py"
V10_TESTS_PATH = "script/test_p2p_nat_g2_pion_combined_fixed_point_v10.py"
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave12_acquisition_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave12_acquisition_v1.py"
)
RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave12_v1_once.py"
)
RUNNER_TESTS_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave12_v1_once.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_acquisition_v1.py"
)
WAVE4_RUNNER_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave4_v1_once.py"
)

EXPECTED_DECISION_CHECKER_RAW = (
    "bb9d62377d676cc6de7678db6be8e64b6d65a088c4c508269fdd51f6f9ca9b53"
)
EXPECTED_DECISION_CHECKER_NORMALIZED = (
    "b8702241e4455fb49d7bcae13857d6d3c2a4cad181390ecea8009d229e3d9051"
)
EXPECTED_V10_CHECKER_RAW = (
    "11d0c2743f92d59a8417870db279edeb6a1b6c0a1af9db577e5cec4c50350985"
)
EXPECTED_V10_CHECKER_NORMALIZED = (
    "ccb5430b1c41e5fcd39e00b7345ba285a427b1b25d48c299f81f1be8ca25f751"
)
EXPECTED_V10_TESTS_RAW = (
    "ab00dbe4d70fbfc596ee6553e2d87f94f75370f07ff38b93d5c5fb5652bfac35"
)
EXPECTED_V10_CONTENT = (
    "d7feddd3b291756c36359b013ea05aaa2f25cb83605daaeb493c0395ff9cc4f7"
)
EXPECTED_V10_INPUT_SET = (
    "f946c625334ac8cf42d42c9f45f0f051eb7f89fb9ecf5dfc576114b1cba990be"
)
EXPECTED_V10_SOURCE_BINDINGS = (
    "067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c"
)
EXPECTED_V10_GRAPH = (
    "77813f467c7452290f35c4ecaa6a1041a0988d563ea37660bb6cc902bb95cdc4"
)
EXPECTED_V10_FRONTIER = (
    "8b84bd2fd9201d33f4424b9dd1018aee7f8470a87306c2ba23eba0c8b6d4ff05"
)
EXPECTED_DECISION_TESTS_RAW = (
    "196fcdaf9a20a60d1b29b628492d1c3f0164805adc5df05678921437e7243def"
)
EXPECTED_DECISION_RAW = (
    "230d4329170a27fd27f8eef4c33337971441726837693526b732a4847a779c0a"
)
EXPECTED_DECISION_CONTENT = (
    "9da32d6de84064039bce0438d75fb0ae7b5c9a22faff6b956c0e443f923a09a9"
)
EXPECTED_DECISION_READER_RAW = (
    "31036c0f25364c5f316c30a4541a6a649a13cdcc9952ec9df9cf2c94a1de5398"
)
EXPECTED_SOURCE_REQUEST_SET_CANONICAL = (
    "6531872e99da0c94746cbdb53fe9f5302ebc71bc82bfde1705b5e2300b2a2ee5"
)
EXPECTED_RESOURCES_CANONICAL = (
    "c8ca9bc4559bea59a5a52fbceaaf068fe82ab9211fa0a888d3918aaa2dec55a2"
)
EXPECTED_COMPACT_IDENTITY = (
    "23b6b188a88c5bdb87abe99325ec7a6d4580605ca69869f2614e36e134c07752"
)
EXPECTED_FULL_WITNESS = (
    "2b13a602a2faf12ea2eb5f6d578a562033148ccded4035799756d969b96bdfa0"
)
EXPECTED_HELD_SOURCE_BINDINGS = (
    "067808934056712884a75ea669d61189bb5d5d722d2a961c8b8c5d25345bb75c"
)
EXPECTED_PERMIT_READER_RAW = (
    "fa09ad2834fb1a145ab606a4251769a5321d17d97e6bdfb4477dd500de7ad047"
)
EXPECTED_RUNNER_NORMALIZED_SHA256 = (
    "985d611f46e62e89341ff250aeb66849a2fc1943ae8aa45a4f31b19397567e90"
)
EXPECTED_WAVE4_CHECKER_RAW = (
    "37a0266f3b4310f1980c70d26cfd10b98bb32ebf4e81f96193e40d4ebb9c0dbd"
)
EXPECTED_WAVE4_RUNNER_RAW = (
    "ad611c379020c5dfc502547d80cb89eb9ed2d89a0585e0abe03357d3163f177b"
)

PROXY_HOST = "proxy.golang.org"
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-12-v1.claim"
STAGING_PREFIX = ".wave-12-v1-staging-"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-12-v1"
FINAL_ACCEPTED = f"{FINAL_ROOT}/accepted"
EVIDENCE_PATH = f"{FINAL_ROOT}/evidence.json"
RECEIPT_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave12-receipt-v1.json"
)
FAILURE_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave12-failure-v1.json"
)
MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave12-manifest-v1.json"
)
READBACK_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave12-readback-v1.json"
)
READBACK_MANIFEST_PATH = (
    f"{BASE}/bounded-dependency-source-acquisition-wave12-"
    "readback-manifest-v1.json"
)

MAX_MOD_BYTES = 1 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_AGGREGATE_MOD_BYTES = 8 * 1024 * 1024
MAX_AGGREGATE_ZIP_BYTES = 128 * 1024 * 1024
MAX_AGGREGATE_BYTES = 128 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
PER_REQUEST_DEADLINE_MS = 30_000
WHOLE_ATTEMPT_DEADLINE_MS = 600_000
MAX_ZIP_FILES = 20_000
MAX_ZIP_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ZIP_FILE_BYTES = 128 * 1024 * 1024
MAX_ZIP_NAME_BYTES = 1_024
MAX_ALL_ZIP_FILES = 300_000
MAX_ALL_ZIP_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAXIMUM_PACKAGE_BYTES = 8 * 1024 * 1024
INTERPRETER_PATH = (
    "/Applications/Xcode.app/Contents/Developer/usr/bin/python3"
)
KERNEL_EXECUTABLE_PATH = (
    "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/"
    "Python3.framework/Versions/3.9/Resources/Python.app/Contents/"
    "MacOS/Python"
)
EXACT_RUNNER_ARGV = ["--execute"]
EXACT_INVOCATION_COMMAND = [
    INTERPRETER_PATH,
    "-I",
    "-B",
    "-S",
    RUNNER_PATH,
    *EXACT_RUNNER_ARGV,
]
EXACT_KERNEL_ARGV = [
    KERNEL_EXECUTABLE_PATH,
    "-I",
    "-B",
    "-S",
    RUNNER_PATH,
    *EXACT_RUNNER_ARGV,
]


class CheckError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise CheckError("E_ARGUMENT")


def require(value: bool, code: str) -> None:
    if not value:
        raise CheckError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode() + b"\n"


def digest_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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
            parse_float=lambda _: (_ for _ in ()).throw(CheckError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(CheckError("E_JSON")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    require("contentBinding" not in result, "E_CONTENT")
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": "permit_without_contentBinding",
        "sha256": sha256(canonical_bytes(result)),
    }
    return result


def _bootstrap_module(
    root: Path,
    path: str,
    expected_sha256: str,
    module_name: str,
) -> tuple[types.ModuleType, bytes]:
    target = root / path
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        previous_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGINT},
        )
        try:
            fd = os.open(target, flags)
        finally:
            signal.pthread_sigmask(
                signal.SIG_SETMASK,
                previous_mask,
            )
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_PACKAGE_BYTES,
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
        fields = (
            "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
            "st_size", "st_mtime_ns", "st_ctime_ns",
        )
        require(
            all(getattr(before, name) == getattr(after, name) for name in fields)
            and sha256(raw) == expected_sha256,
            "E_BOOTSTRAP",
        )
    finally:
        if fd >= 0:
            os.close(fd)
    module = types.ModuleType(module_name)
    module.__file__ = str(target)
    module.__package__ = ""
    exec(compile(raw, path, "exec"), module.__dict__)
    return module, raw


DECISION, DECISION_CHECKER_RAW = _bootstrap_module(
    ROOT,
    DECISION_CHECKER_PATH,
    EXPECTED_DECISION_CHECKER_RAW,
    "wave12_identity_decision_v1",
)


def _portable(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _open_owned_directory(
    owner: list[int],
    path: str | os.PathLike[str],
    *,
    dir_fd: int | None = None,
) -> int:
    previous_mask = signal.pthread_sigmask(
        signal.SIG_BLOCK,
        {signal.SIGALRM, signal.SIGINT},
    )
    fd = -1
    transferred = False
    try:
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | os.O_CLOEXEC
        )
        if dir_fd is None:
            fd = os.open(path, flags)
        else:
            fd = os.open(path, flags, dir_fd=dir_fd)
        try:
            owner.append(fd)
            transferred = True
        except BaseException:
            try:
                os.close(fd)
            finally:
                fd = -1
            raise
        return fd
    finally:
        if fd >= 0 and not transferred:
            try:
                os.close(fd)
            except OSError:
                pass
        signal.pthread_sigmask(
            signal.SIG_SETMASK,
            previous_mask,
        )


class HeldTerminalNamespace:
    """Hold the documentation directory and prove terminal names absent."""

    def __init__(self, root: Path) -> None:
        self.root_path = root
        self.root_fd = -1
        self.directory_fd = -1
        self.owned_directory_fds: list[int] = []
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        try:
            self.root_fd = _open_owned_directory(
                self.owned_directory_fds,
                root,
            )
            self.root_initial = os.fstat(self.root_fd)
            DECISION.BootstrapPinnedCodeFile._validate_directory(
                self.root_initial
            )
            current = self.root_fd
            for component in BASE.split("/"):
                child = _open_owned_directory(
                    self.owned_directory_fds,
                    component,
                    dir_fd=current,
                )
                info = os.fstat(child)
                DECISION.BootstrapPinnedCodeFile._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.directory_fd = current
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def observe_absent(self) -> None:
        forbidden = {
            _portable(Path(path).name)
            for path in (
                RECEIPT_PATH,
                FAILURE_PATH,
                MANIFEST_PATH,
                READBACK_PATH,
                READBACK_MANIFEST_PATH,
            )
        }
        try:
            raw_names = os.listdir(self.directory_fd)
            names = {_portable(name) for name in raw_names}
        except OSError as error:
            raise CheckError("E_TERMINAL_NAMESPACE") from error
        require(
            len(names) == len(raw_names) and not forbidden & names,
            "E_TERMINAL_NAMESPACE",
        )

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root_path, follow_symlinks=False)
            require(
                DECISION.directory_identity(held_root)
                == DECISION.directory_identity(self.root_initial)
                == DECISION.directory_identity(named_root),
                "E_ROOT_IDENTITY",
            )
            for child, initial, parent, component in self.directories:
                require(
                    DECISION.directory_identity(os.fstat(child))
                    == DECISION.directory_identity(initial)
                    == DECISION.directory_identity(
                        os.stat(
                            component,
                            dir_fd=parent,
                            follow_symlinks=False,
                        )
                    ),
                    "E_TERMINAL_NAMESPACE",
                )
        except OSError as error:
            raise CheckError("E_TERMINAL_NAMESPACE") from error
        self.observe_absent()

    def close(self) -> None:
        seen: set[int] = set()
        errors: list[OSError] = []
        for fd in reversed(self.owned_directory_fds):
            if fd in seen:
                continue
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
            seen.add(fd)
        self.owned_directory_fds.clear()
        self.directories.clear()
        self.root_fd = -1
        self.directory_fd = -1
        if errors:
            raise CheckError("E_TERMINAL_NAMESPACE") from errors[0]

    def __enter__(self) -> "HeldTerminalNamespace":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class HeldReservedNamespace:
    """Hold the dependency directory and prove Wave12 names absent."""

    def __init__(self, root: Path) -> None:
        self.root_path = root
        self.root_fd = -1
        self.namespace_fd = -1
        self.owned_directory_fds: list[int] = []
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        try:
            self.root_fd = _open_owned_directory(
                self.owned_directory_fds,
                root,
            )
            self.root_initial = os.fstat(self.root_fd)
            DECISION.BootstrapPinnedCodeFile._validate_directory(
                self.root_initial
            )
            current = self.root_fd
            for component in DEPENDENCY_ROOT.split("/"):
                child = _open_owned_directory(
                    self.owned_directory_fds,
                    component,
                    dir_fd=current,
                )
                info = os.fstat(child)
                DECISION.BootstrapPinnedCodeFile._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.namespace_fd = current
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    def observe_absent(self) -> None:
        try:
            raw_names = os.listdir(self.namespace_fd)
        except OSError as error:
            raise CheckError("E_NAMESPACE") from error
        names = [_portable(name) for name in raw_names]
        claim = _portable(Path(CLAIM_PATH).name)
        final = _portable(Path(FINAL_ROOT).name)
        staging = _portable(STAGING_PREFIX)
        require(
            len(set(names)) == len(raw_names)
            and claim not in names
            and final not in names
            and not any(name.startswith(staging) for name in names),
            "E_NAMESPACE",
        )

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root_path, follow_symlinks=False)
            require(
                DECISION.directory_identity(held_root)
                == DECISION.directory_identity(self.root_initial)
                == DECISION.directory_identity(named_root),
                "E_ROOT_IDENTITY",
            )
            for child, initial, parent, component in self.directories:
                require(
                    DECISION.directory_identity(os.fstat(child))
                    == DECISION.directory_identity(initial)
                    == DECISION.directory_identity(
                        os.stat(
                            component,
                            dir_fd=parent,
                            follow_symlinks=False,
                        )
                    ),
                    "E_NAMESPACE",
                )
        except OSError as error:
            raise CheckError("E_NAMESPACE") from error
        self.observe_absent()

    def close(self) -> None:
        seen: set[int] = set()
        errors: list[OSError] = []
        for fd in reversed(self.owned_directory_fds):
            if fd in seen:
                continue
            try:
                os.close(fd)
            except OSError as error:
                errors.append(error)
            seen.add(fd)
        self.owned_directory_fds.clear()
        self.directories.clear()
        self.root_fd = -1
        self.namespace_fd = -1
        if errors:
            raise CheckError("E_NAMESPACE") from errors[0]

    def __enter__(self) -> "HeldReservedNamespace":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


_SNAPSHOT_SHA256 = sha256(b"")


def _snapshot_normalizer(_: bytes) -> bytes:
    return b""


def _pin_package_file(
    root: Path,
    path: str,
    expected_sha256: str | None,
) -> Any:
    """Hold exact bytes; an untrusted snapshot is bound by the permit later."""

    if expected_sha256 is None:
        return DECISION.BootstrapPinnedCodeFile(
            root,
            path,
            _SNAPSHOT_SHA256,
            _snapshot_normalizer,
        )
    return DECISION.BootstrapPinnedCodeFile(
        root,
        path,
        expected_sha256,
    )


def _tuple_digest(module: str, version: str) -> str:
    return sha256(f"{module}\n{version}\n".encode("utf-8"))


def normalized_resources(decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    preparation = decision["sourceAcquisitionPreparation"]
    source = preparation["requestSet"]
    require(
        type(preparation["requestCount"]) is int
        and preparation["requestCount"] == 8
        and preparation["requestOrder"] == "tuple_order_ascending_mod_then_zip"
        and preparation["proxyHost"] == PROXY_HOST
        and preparation["acquisitionReady"] is True
        and preparation["acquisitionAuthorizedByThisDecision"] is False
        and preparation["claimPath"] == CLAIM_PATH
        and preparation["stagingDirectoryPrefix"] == STAGING_PREFIX
        and preparation["acceptedDirectoryPath"] == FINAL_ACCEPTED
        and type(source) is list
        and len(source) == 8
        and preparation["requestSetCanonicalSha256"]
        == EXPECTED_SOURCE_REQUEST_SET_CANONICAL
        and sha256(digest_bytes(source))
        == EXPECTED_SOURCE_REQUEST_SET_CANONICAL,
        "E_REQUEST_SET",
    )
    return _normalize_request_rows(source)


def _normalize_request_rows(
    source: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    require(type(source) is list and len(source) == 8, "E_REQUEST_SET")
    expected_keys = {
        "acceptedFileName",
        "acquisitionAuthorized",
        "authenticationRequired",
        "expectedH1",
        "host",
        "maximumResponseBytes",
        "method",
        "module",
        "networkAuthorized",
        "requestOrdinal",
        "resourceKind",
        "selectedByGraphAlgorithm",
        "tupleOrder",
        "url",
        "version",
    }
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(source):
        require(type(item) is dict and set(item) == expected_keys, "E_REQUEST_SET")
        ordinal = index + 1
        tuple_order = index // 2 + 1
        kind = "mod" if index % 2 == 0 else "zip"
        module = item["module"]
        version = item["version"]
        components = module.split("/") if type(module) is str else []
        require(
            type(module) is str
            and type(version) is str
            and module.isascii()
            and version.isascii()
            and bool(components)
            and all(
                re.fullmatch(r"[a-z0-9][a-z0-9._-]*", component)
                is not None
                for component in components
            )
            and re.fullmatch(r"v[0-9][a-z0-9.+_-]*", version) is not None,
            "E_REQUEST_IDENTITY",
        )
        digest = _tuple_digest(module, version)
        expected_path = f"/{module}/@v/{version}.{kind}"
        parsed = urlsplit(item["url"])
        maximum = MAX_MOD_BYTES if kind == "mod" else MAX_ZIP_BYTES
        require(
            type(item["requestOrdinal"]) is int
            and item["requestOrdinal"] == ordinal
            and type(item["tupleOrder"]) is int
            and item["tupleOrder"] == tuple_order
            and item["resourceKind"] == kind
            and item["method"] == "GET"
            and item["host"] == PROXY_HOST
            and type(item["maximumResponseBytes"]) is int
            and item["maximumResponseBytes"] == maximum
            and item["acceptedFileName"]
            == f"{tuple_order:03d}-{digest[:20]}.{kind}"
            and item["acquisitionAuthorized"] is False
            and item["networkAuthorized"] is False
            and item["authenticationRequired"] is False
            and type(item["selectedByGraphAlgorithm"]) is bool
            and parsed.scheme == "https"
            and parsed.hostname == PROXY_HOST
            and parsed.port is None
            and parsed.path == expected_path
            and not parsed.query
            and not parsed.fragment
            and item["url"] == f"https://{PROXY_HOST}{expected_path}"
            and re.fullmatch(r"h1:[A-Za-z0-9+/]{43}=", item["expectedH1"])
            is not None,
            "E_REQUEST_CONTRACT",
        )
        rows.append(
            {
                "requestOrdinal": ordinal,
                "tupleOrder": tuple_order,
                "tupleId": f"wave12-{tuple_order:03d}-{digest[:12]}",
                "tupleDigestSha256": digest,
                "selectedByGraphAlgorithm": item["selectedByGraphAlgorithm"],
                "module": module,
                "version": version,
                "kind": kind,
                "method": "GET",
                "host": PROXY_HOST,
                "port": 443,
                "path": expected_path,
                "url": item["url"],
                "expectedH1": item["expectedH1"],
                "maximumResponseBodyBytes": maximum,
                "acceptedFileName": item["acceptedFileName"],
            }
        )
    for index in range(0, 8, 2):
        first, second = rows[index:index + 2]
        require(
            first["tupleOrder"] == second["tupleOrder"]
            and first["tupleId"] == second["tupleId"]
            and first["module"] == second["module"]
            and first["version"] == second["version"]
            and first["selectedByGraphAlgorithm"]
            == second["selectedByGraphAlgorithm"],
            "E_REQUEST_PAIR",
        )
    require(
        all(row["selectedByGraphAlgorithm"] is False for row in rows)
        and sum(
            bool(row["selectedByGraphAlgorithm"])
            for row in rows[::2]
        )
        == 0,
        "E_REQUEST_SELECTION",
    )
    return rows


def normalized_runner(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    pattern = re.compile(r'EXPECTED_CHECKER_RAW = "[0-9a-f]{64}"')
    require(len(pattern.findall(text)) == 1, "E_RUNNER")
    return pattern.sub(
        'EXPECTED_CHECKER_RAW = "' + "0" * 64 + '"',
        text,
    ).encode()


def invocation_contract() -> dict[str, Any]:
    return {
        "canonicalDirectCommand": EXACT_INVOCATION_COMMAND,
        "canonicalDirectCommandExclusive": False,
        "cwd": "repository_root",
        "interpreterAbsolutePath": INTERPRETER_PATH,
        "runnerPath": RUNNER_PATH,
        "exactArgv": EXACT_RUNNER_ARGV,
        "additionalArgumentsAllowed": False,
        "abbreviatedArgumentsAllowed": False,
        "duplicateArgumentsAllowed": False,
        "testSeamMayDispatchExecution": False,
        "executionEntryPointRevalidatesInvocationShape": True,
        "exactKernelArgv": EXACT_KERNEL_ARGV,
        "kernelExecutableAbsolutePath": KERNEL_EXECUTABLE_PATH,
        "kernelArgvSource": "macos_sysctl_kern_procargs2",
        "kernelArgvRevalidatedBeforePreflight": True,
        "pythonInvocationStatePurpose":
            "accidental_misconfiguration_guard_only",
        "kernelArgvPurpose": "accidental_misconfiguration_guard_only",
        "localSameUserProcessTrusted": True,
        "sameProcessWrapperWithinTrustBoundary": True,
        "invocationChecksAuthenticateOrigin": False,
        "invocationOriginAttestationProvided": False,
        "externalLauncherReceiptRequired": False,
    }


def validate_invocation_contract(permit: Mapping[str, Any]) -> None:
    require(
        permit.get("invocationContract") == invocation_contract(),
        "E_INVOCATION",
    )


def validate_runner(runner_raw: bytes, checker_raw: bytes) -> None:
    require(
        sha256(normalized_runner(runner_raw))
        == EXPECTED_RUNNER_NORMALIZED_SHA256,
        "E_RUNNER",
    )
    source = runner_raw.decode("utf-8", errors="strict")
    tree = ast.parse(source)
    imports: set[str] = set()
    functions: set[str] = set()
    execute_default_bound = False
    execute_revalidates_first = False
    main_has_no_parameters = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
            if node.name == "execute" and node.args.defaults:
                default = node.args.defaults[-1]
                execute_default_bound = (
                    isinstance(default, ast.Name)
                    and default.id == "direct_fetch"
                )
                first = node.body[0] if node.body else None
                execute_revalidates_first = (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Call)
                    and isinstance(first.value.func, ast.Name)
                    and first.value.func.id
                    == "validate_production_invocation"
                    and not first.value.args
                    and not first.value.keywords
                )
            elif node.name == "main":
                main_has_no_parameters = not (
                    node.args.posonlyargs
                    or node.args.args
                    or node.args.vararg
                    or node.args.kwonlyargs
                    or node.args.kwarg
                )
    require(
        not {
            "subprocess",
            "requests",
            "urllib.request",
            "socket",
        } & imports
        and execute_default_bound
        and execute_revalidates_first
        and main_has_no_parameters
        and {
            "direct_fetch",
            "create_claim",
            "rename_exclusive",
            "preflight",
            "_attempt",
            "execute",
            "validate_execution_context",
            "validate_argument_vector",
            "validate_production_invocation",
            "_parse_kernel_procargs2",
            "_read_kernel_invocation",
        } <= functions,
        "E_RUNNER",
    )
    for token in (
        "signal.setitimer",
        "signal.pthread_sigmask",
        "signal.sigpending",
        "signal.sigwait",
        "EXPECTED_WAVE4_RUNNER_RAW",
        "os.O_EXCL",
        "os.fsync",
        "os.pread",
        "renameatx_np",
        "dir_fd=",
        "HeldEntry",
        "ExecutionNamespace",
        "directory_steps",
        "_namespace_barrier",
        "ImmutablePhaseLedger",
        "ProcessStateGuard",
        "_open_owned_directory",
        "exists_observed",
        "claim_creation_attempted",
        "claim_creation_may_have_consumed",
        "claim_known_consumed",
        "after_claim_create_returned_before_assignment",
        "cleanup_consumed",
        "body_is_known_consumed",
        "dispatchBoundaryCount",
        "responseCommittedCount",
        "validationCommittedCount",
        "persistenceCommittedCount",
        "additionalCompletionUncertain",
        "unknown_after_dispatch",
        "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
        "externalAuthenticationRequired",
        "retryAllowed",
        "allow_abbrev=False",
        "validate_argument_vector",
        "validate_production_invocation",
        "sys.executable",
        "sys.argv",
        "sys.modules",
        '__name__ == "__main__"',
        "Path.cwd()",
        "ctypes.CDLL",
        "os.getpid",
        "KERN_PROCARGS2",
    ):
        require(token in source, "E_RUNNER")
    for token in (
        "subprocess",
        "shell=True",
        "shutil.rmtree",
        "Authorization",
        "Proxy-Authorization",
        "Cookie",
        "ResourceOperationBoundary",
        "CommittedOperationCounters",
    ):
        require(token not in source, "E_RUNNER")
    reverse = re.findall(r'EXPECTED_CHECKER_RAW = "([0-9a-f]{64})"', source)
    require(reverse == [sha256(checker_raw)], "E_RUNNER")


def _decision_package_bindings() -> list[dict[str, str]]:
    return [
        {"path": DECISION_PATH, "rawSha256": EXPECTED_DECISION_RAW},
        {
            "path": DECISION_READER_PATH,
            "rawSha256": EXPECTED_DECISION_READER_RAW,
        },
        {
            "path": DECISION_CHECKER_PATH,
            "rawSha256": EXPECTED_DECISION_CHECKER_RAW,
        },
        {
            "path": DECISION_TESTS_PATH,
            "rawSha256": EXPECTED_DECISION_TESTS_RAW,
        },
    ]


def permit_payload(
    decision: Mapping[str, Any],
    package_raw: Mapping[str, bytes],
) -> dict[str, Any]:
    resources = normalized_resources(decision)
    resources_canonical = sha256(canonical_bytes(resources))
    require(
        resources_canonical == EXPECTED_RESOURCES_CANONICAL,
        "E_RESOURCE_BINDING",
    )
    validate_runner(package_raw[RUNNER_PATH], package_raw[THIS_CHECKER_PATH])
    tool_paths = (
        THIS_CHECKER_PATH,
        THIS_TESTS_PATH,
        RUNNER_PATH,
        RUNNER_TESTS_PATH,
    )
    tool_bindings = [
        {"path": path, "rawSha256": sha256(package_raw[path])}
        for path in tool_paths
    ]
    primitive_bindings = [
        {
            "path": WAVE4_CHECKER_PATH,
            "rawSha256": EXPECTED_WAVE4_CHECKER_RAW,
            "use": "constants_and_validation_contract_only",
        },
        {
            "path": WAVE4_RUNNER_PATH,
            "rawSha256": EXPECTED_WAVE4_RUNNER_RAW,
            "use": (
                "h1_go_mod_zip_and_direct_https_"
                "validation_primitives_only"
            ),
        },
    ]
    return {
        "documentType": "aetherlink.wave12-source-acquisition-execution-permit",
        "schemaVersion": "1.0",
        "permitId": (
            "g2-pion-rung3-wave12-8-resource-source-acquisition-"
            "execution-permit-v1"
        ),
        "recordedDate": "2026-07-27",
        "status": "authorized_not_consumed",
        "structurePreparationOnly": False,
        "executionReady": True,
        "invocationContract": invocation_contract(),
        "decisionBinding": {
            "path": DECISION_PATH,
            "rawSha256": EXPECTED_DECISION_RAW,
            "contentSha256": EXPECTED_DECISION_CONTENT,
            "requiredStatus": decision["status"],
            "files": _decision_package_bindings(),
        },
        "predecessorBindings": {
            "combinedFixedPointV10": {
                "checkerPath": V10_CHECKER_PATH,
                "checkerRawSha256": EXPECTED_V10_CHECKER_RAW,
                "checkerNormalizedSha256":
                    EXPECTED_V10_CHECKER_NORMALIZED,
                "testsPath": V10_TESTS_PATH,
                "testsRawSha256": EXPECTED_V10_TESTS_RAW,
                "contentSha256": EXPECTED_V10_CONTENT,
                "combinedInputSetSha256": EXPECTED_V10_INPUT_SET,
                "sourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
                "graphSha256": EXPECTED_V10_GRAPH,
                "frontierSha256": EXPECTED_V10_FRONTIER,
                "v9TestsBindingScope":
                    "historical_metadata_only_not_live_held",
                "v9TestsLiveHeld": False,
            },
        },
        "identityBinding": {
            "compactIdentitySha256": EXPECTED_COMPACT_IDENTITY,
            "fullWitnessSha256": EXPECTED_FULL_WITNESS,
            "heldSourceBindingsSha256": EXPECTED_HELD_SOURCE_BINDINGS,
            "completeTupleCount": 4,
            "blockedTupleCount": 0,
        },
        "requestContract": {
            "tupleCount": 4,
            "requestCount": 8,
            "order": "tuple_order_ascending_mod_then_zip",
            "method": "GET",
            "host": PROXY_HOST,
            "port": 443,
            "sourceRequestSetCanonicalSha256":
                EXPECTED_SOURCE_REQUEST_SET_CANONICAL,
            "resources": resources,
            "resourcesCanonicalSha256": resources_canonical,
            "directHttpsOnly": True,
            "tlsCertificateAndHostnameValidationRequired": True,
            "identityContentEncodingRequired": True,
            "acceptedStatusCode": 200,
            "requestBodyAllowed": False,
            "redirectAllowed": False,
            "ambientProxyAllowed": False,
            "alternateHostAllowed": False,
            "authenticationAllowed": False,
            "authorizationHeaderAllowed": False,
            "proxyAuthorizationHeaderAllowed": False,
            "cookieAllowed": False,
            "clientCertificateAllowed": False,
            "rangeHeaderAllowed": False,
            "queryOrFragmentAllowed": False,
            "retryResumeOrBackfillAllowed": False,
        },
        "oneUseContract": {
            "claimPath": CLAIM_PATH,
            "claimCreatedOExcl0600AndFsyncedBeforeDnsOrNetwork": True,
            "claimPersistsAfterSuccessFailureTimeoutOrUncertainty": True,
            "existingClaimState": "already_consumed",
            "claimAbsentAtPermitPublication": True,
            "claimCreationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "claimCreationAttemptRecordedBeforeExclusiveCreate": True,
            "claimCreationMayHaveConsumedDefaultsTrueUntilDefinitiveNotCreated":
                True,
            "baseExceptionAfterExclusiveCreateFailsClosedAsClaimStateUncertain":
                True,
            "postCreatePreAssignmentInterruptionTreatedAsConsumedPossible":
                True,
            "preAssignmentInterruptionClosesUnboundHeldEntry": True,
            "knownExistingClaimPreservesAlreadyConsumedClassification": True,
            "fileExistsObservedBeforeUnmaskPreservesKnownConsumed": True,
            "fileExistsObservedOverridesUnmaskAcquisitionError": True,
            "restoreFailureAfterKnownConsumedIsConsumedUncertain": True,
            "knownConsumedSurvivesNamespaceOrAuthorityTeardownError": True,
            "secondExecutionAllowed": False,
            "stagingPrefix": STAGING_PREFIX,
            "finalRootPath": FINAL_ROOT,
            "finalAcceptedPath": FINAL_ACCEPTED,
            "evidencePath": EVIDENCE_PATH,
            "failureRetainsStaging": True,
            "retryResumeBackfillOverwriteOrCleanupAllowed": False,
            "heldRootRelativeComponentTraversalRequired": True,
            "intermediateDirectoryIdentityHeldThroughExecution": True,
            "localFdOwnershipTransferAndCloseCleanupDefersOnlySigalrmAndSigint":
                True,
            "networkValidationWriteAndFsyncOutsideLocalSignalDeferral":
                True,
            "closeCleanupCompletesBeforePriorSignalMaskRestoration": True,
        },
        "verificationContract": {
            "goModH1Algorithm":
                "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod",
            "moduleZipH1Algorithm":
                "golang.org/x/mod/sumdb/dirhash.HashZip(Hash1)_v1",
            "rawSha256RecordedSeparately": True,
            "zipExactModuleVersionPrefixRequired": True,
            "zipSafetyShapeCrcAndModParityRequired": True,
            "sourceExtractionAllowed": False,
        },
        "zipLimits": {
            "maximumEntryCountPerZip": MAX_ZIP_FILES,
            "maximumUncompressedBytesPerZip":
                MAX_ZIP_UNCOMPRESSED_BYTES,
            "maximumSingleEntryBytes": MAX_ZIP_FILE_BYTES,
            "maximumEntryNameBytes": MAX_ZIP_NAME_BYTES,
            "maximumEntryCountAcrossAllZips": MAX_ALL_ZIP_FILES,
            "maximumUncompressedBytesAcrossAllZips":
                MAX_ALL_ZIP_UNCOMPRESSED_BYTES,
            "encryptedSymlinkDirectoryDuplicateOrUnsafeEntriesAllowed": False,
        },
        "absoluteResourceLimits": {
            "maximumRequestCount": 8,
            "maximumModResponseBodyBytes": MAX_MOD_BYTES,
            "maximumZipResponseBodyBytes": MAX_ZIP_BYTES,
            "maximumAggregateModResponseBodyBytes":
                MAX_AGGREGATE_MOD_BYTES,
            "maximumAggregateZipResponseBodyBytes":
                MAX_AGGREGATE_ZIP_BYTES,
            "maximumAggregateResponseBodyBytes": MAX_AGGREGATE_BYTES,
            "maximumHeaderBytesPerResponse": MAX_HEADER_BYTES,
            "perRequestDeadlineMilliseconds": PER_REQUEST_DEADLINE_MS,
            "wholeAttemptDeadlineMilliseconds":
                WHOLE_ATTEMPT_DEADLINE_MS,
            "wholeAttemptSigalrmDeadlineRequired": True,
            "preexistingRealTimerRestoredWithElapsedAdjustment": True,
            "callerBlockedSigalrmRejectedBeforePreflight": True,
            "sigalrmUnblockedDuringFetchValidationWriteAndFsync": True,
            "perRequestDeadlinePassedToPinnedFetchPrimitive": True,
            "processSetupAndRestorationUseGuardedSignalState": True,
            "processStateRestorationStepsAreIndependentBestEffort": True,
            "originalSignalMaskRestoredExactlyOrUncertaintyReported": True,
            "pendingInstalledSigalrmSynchronouslyConsumedBeforePriorHandlerRestoration":
                True,
            "pendingSigalrmDrainFailureContainedWithoutPriorAlarmStateRestoration":
                True,
            "priorHandlerRestoredBeforePriorTimerArmed": True,
        },
        "filesystemAuthority": {
            "claimWriteAuthorized": True,
            "ownerOnlyStagingWriteAuthorized": True,
            "verifiedModAndZipWriteAuthorized": True,
            "receiptFailureAndManifestWriteAuthorized": True,
            "acquisitionArtifactPublicationAuthorized": True,
            "atomicNoReplacePublicationRequired": True,
            "manifestWrittenLast": True,
            "newFileMode": "0600",
            "newDirectoryMode": "0700",
            "sourceExtractionAuthorized": False,
            "otherRepositoryWritesAuthorized": False,
        },
        "authority": {
            "wave12PublicProxy8GetAcquisitionAuthorizedOnce": True,
            "dnsTcpTlsHttpsToExactProxyAuthorized": True,
            "sourceExtractionAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "productRuntimeNetworkAuthorized": False,
            "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized": False,
            "publicationAuthorized": False,
            "repositoryOwnerIdentityProofRequired": False,
            "accountRequired": False,
            "ownerRequired": False,
            "sshRequired": False,
            "gpgRequired": False,
            "externalAuthenticationRequired": False,
            "authenticationRequired": False,
            "passwordRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
            "cookieRequired": False,
            "clientCertificateRequired": False,
            "userActionRequired": False,
        },
        "terminalContract": {
            "receiptPath": RECEIPT_PATH,
            "failurePath": FAILURE_PATH,
            "manifestPath": MANIFEST_PATH,
            "readbackPath": READBACK_PATH,
            "readbackManifestPath": READBACK_MANIFEST_PATH,
            "successAndFailureMutuallyExclusive": True,
            "failurePublishesFailureOnly": True,
            "failurePublicationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "postPublicationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "manifestWrittenLast": True,
            "independentReadbackRequired": True,
            "failureOperationCountsAreCommittedLowerBounds": True,
            "inFlightOrdinalPhaseAndAdditionalCompletionUncertainRecorded":
                True,
            "zeroCommittedResponsesWithActiveFetchState":
                "unknown_after_dispatch",
            "successRequiresNoActiveOperationAndExact8CommittedCounts":
                True,
            "processStateRestorationUncertaintyState":
                "consumed_terminal_state_uncertain",
            "terminalTeardownUncertaintyState":
                "consumed_terminal_state_uncertain",
            "terminalTeardownUncertaintyFailureCode":
                "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
        },
        "readerDocumentBinding": {
            "path": PERMIT_READER_PATH,
            "rawSha256": EXPECTED_PERMIT_READER_RAW,
        },
        "toolBindings": tool_bindings,
        "primitiveBindings": primitive_bindings,
        "runnerNormalizedSha256": EXPECTED_RUNNER_NORMALIZED_SHA256,
        "nonClaims": [
            "no account owner SSH GPG password private key signature token cookie client certificate or user authentication is required",
            "the Python-state and kernel-argv checks guard accidental misconfiguration and do not authenticate invocation origin",
            "no invocation-origin attestation or external launcher receipt is provided or required",
            "materializing or validating this package does not invoke the runner or execute network socket subprocess or filesystem write operations",
            "the permit does not authorize source extraction loading execution compilation package-manager use Git device deployment or product runtime networking",
            "the permit does not establish dependency fixed point semantic closure candidate selection library selection rung-three completion or release readiness",
        ],
        "result":
            "exact_8_resource_one_use_wave12_acquisition_authorized_not_consumed",
        "nextAction": "execute_bound_wave12_source_acquisition_once",
    }


def _package_specs(include_permit: bool) -> list[tuple[str, str | None]]:
    specs = [
        (DECISION_PATH, EXPECTED_DECISION_RAW),
        (DECISION_READER_PATH, EXPECTED_DECISION_READER_RAW),
        (DECISION_CHECKER_PATH, EXPECTED_DECISION_CHECKER_RAW),
        (DECISION_TESTS_PATH, EXPECTED_DECISION_TESTS_RAW),
        (V10_CHECKER_PATH, EXPECTED_V10_CHECKER_RAW),
        (V10_TESTS_PATH, EXPECTED_V10_TESTS_RAW),
        (PERMIT_READER_PATH, EXPECTED_PERMIT_READER_RAW),
        (THIS_CHECKER_PATH, None),
        (THIS_TESTS_PATH, None),
        (RUNNER_PATH, None),
        (RUNNER_TESTS_PATH, None),
        (WAVE4_CHECKER_PATH, EXPECTED_WAVE4_CHECKER_RAW),
        (WAVE4_RUNNER_PATH, EXPECTED_WAVE4_RUNNER_RAW),
    ]
    if include_permit:
        specs.append((PERMIT_PATH, None))
    return specs


class AuthorityFiles:
    """Pin every byte that grants or implements one Wave12 attempt."""

    def __init__(
        self,
        root: Path,
        permit: Mapping[str, Any],
    ) -> None:
        self.root = root
        self.permit = permit
        self.stack = ExitStack()
        self.held: list[Any] = []

    def __enter__(self) -> "AuthorityFiles":
        expected = {
            row["path"]: row["rawSha256"]
            for row in (
                list(self.permit["decisionBinding"]["files"])
                + list(self.permit["toolBindings"])
                + list(self.permit["primitiveBindings"])
            )
        }
        expected[PERMIT_READER_PATH] = self.permit[
            "readerDocumentBinding"
        ]["rawSha256"]
        expected[PERMIT_PATH] = sha256(canonical_bytes(self.permit))
        predecessor = self.permit["predecessorBindings"][
            "combinedFixedPointV10"
        ]
        expected[predecessor["checkerPath"]] = predecessor[
            "checkerRawSha256"
        ]
        expected[predecessor["testsPath"]] = predecessor["testsRawSha256"]
        try:
            self.held = [
                self.stack.enter_context(
                    DECISION.BootstrapPinnedCodeFile(
                        self.root,
                        path,
                        digest,
                    )
                )
                for path, digest in sorted(expected.items())
            ]
            self.barrier()
            return self
        except BaseException:
            self.stack.close()
            raise

    def barrier(self) -> None:
        DECISION.identity_barrier(self.root, self.held)

    def __exit__(self, *_: object) -> None:
        self.stack.close()


def evaluate(
    verify_disk: bool,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with ExitStack() as stack:
        reserved = stack.enter_context(HeldReservedNamespace(root))
        terminal = stack.enter_context(HeldTerminalNamespace(root))
        pinned = {
            path: stack.enter_context(
                _pin_package_file(root, path, expected)
            )
            for path, expected in _package_specs(verify_disk)
        }
        held = [reserved, terminal, *pinned.values()]
        DECISION.identity_barrier(root, held)
        decision_raw = pinned[DECISION_PATH].raw
        expected_decision = strict_json(decision_raw)
        package_raw = {path: item.raw for path, item in pinned.items()}
        decision_package_raw = {
            DECISION.SELF_PATH: package_raw[DECISION_CHECKER_PATH],
            DECISION.TESTS_PATH: package_raw[DECISION_TESTS_PATH],
            DECISION.READER_PATH: package_raw[DECISION_READER_PATH],
            DECISION.V10_CHECKER_PATH: package_raw[V10_CHECKER_PATH],
            DECISION.V10_TESTS_PATH: package_raw[V10_TESTS_PATH],
        }
        DECISION.validate_materialized_decision(
            decision_raw,
            expected_decision,
            decision_package_raw,
        )
        identity = expected_decision["identityResolution"]
        preparation = expected_decision["sourceAcquisitionPreparation"]
        predecessor = expected_decision["predecessorBindings"][
            "combinedFixedPointV10"
        ]
        require(
            sha256(decision_raw) == EXPECTED_DECISION_RAW
            and expected_decision["contentBinding"]["sha256"]
            == EXPECTED_DECISION_CONTENT
            and identity["tupleCount"] == 4
            and identity["completeIdentityPairCount"] == 4
            and identity["blockedTupleCount"] == 0
            and identity["compactIdentitySha256"]
            == EXPECTED_COMPACT_IDENTITY
            and identity["fullWitnessSha256"] == EXPECTED_FULL_WITNESS
            and expected_decision["heldSourceInputSet"][
                "sourceBindingsSha256"
            ]
            == EXPECTED_HELD_SOURCE_BINDINGS
            and preparation["requestCount"] == 8
            and preparation["acquisitionReady"] is True
            and preparation["acquisitionAuthorizedByThisDecision"] is False
            and expected_decision["authority"][
                "externalAuthenticationRequired"
            ]
            is False
            and not any(expected_decision["authority"].values())
            and predecessor["checkerPath"] == V10_CHECKER_PATH
            and predecessor["checkerRawSha256"] == EXPECTED_V10_CHECKER_RAW
            and predecessor["checkerNormalizedSha256"]
            == EXPECTED_V10_CHECKER_NORMALIZED
            and predecessor["testsPath"] == V10_TESTS_PATH
            and predecessor["testsRawSha256"] == EXPECTED_V10_TESTS_RAW
            and predecessor["contentSha256"] == EXPECTED_V10_CONTENT
            and predecessor["combinedInputSetSha256"]
            == EXPECTED_V10_INPUT_SET
            and predecessor["sourceBindingsSha256"]
            == EXPECTED_HELD_SOURCE_BINDINGS
            and predecessor["graphSha256"] == EXPECTED_V10_GRAPH
            and predecessor["frontierSha256"] == EXPECTED_V10_FRONTIER
            and predecessor["v9TestsBindingScope"]
            == "historical_metadata_only_not_live_held"
            and predecessor["v9TestsLiveHeld"] is False,
            "E_DECISION",
        )
        permit = content_bound(permit_payload(expected_decision, package_raw))
        validate_invocation_contract(permit)
        if verify_disk:
            permit_raw = pinned[PERMIT_PATH].raw
            require(
                permit_raw == canonical_bytes(permit)
                and strict_json(permit_raw) == permit,
                "E_PERMIT",
            )
        DECISION.identity_barrier(root, held)
    return {
        "decision": expected_decision,
        "permit": permit,
    }, {
        "documentType": "aetherlink.wave12-source-acquisition-package-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "structurePreparationOnly": False,
        "executionReady": True,
        "tupleCount": 4,
        "requestCount": 8,
        "claimExists": False,
        "permitConsumed": False,
        "runnerInvoked": False,
        "networkUsed": False,
        "productRuntimeNetworkUsed": False,
        "ambientOrDirectSocketUseOutsidePinnedFetchUsed": False,
        "subprocessCount": 0,
        "fileWriteCount": 0,
        "sourceAcquired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def error_document(code: str) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.wave12-source-acquisition-package-error",
        "schemaVersion": "1.0",
        "status": "failed_closed",
        "failureCode": code,
        "networkAuthorized": False,
        "productRuntimeNetworkAuthorized": False,
        "ambientOrDirectSocketUseOutsidePinnedFetchAuthorized": False,
        "subprocessAuthorized": False,
        "fileWriteAuthorized": False,
        "permitConsumed": False,
        "runnerInvoked": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False)
        parser.add_argument("--print-permit", action="store_true")
        args = parser.parse_args(argv)
        values, summary = evaluate(not args.print_permit)
        sys.stdout.buffer.write(
            canonical_bytes(values["permit"] if args.print_permit else summary)
        )
        return 0
    except (CheckError, DECISION.DecisionFailure) as error:
        code = getattr(error, "code", "E_DECISION")
        sys.stdout.buffer.write(canonical_bytes(error_document(code)))
        return 1
    except Exception:
        sys.stdout.buffer.write(canonical_bytes(error_document("E_INTERNAL")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
