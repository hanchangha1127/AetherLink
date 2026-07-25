#!/usr/bin/env python3
"""Validate the offline Wave4 source-identity and acquisition-ready decision.

Run only with ``python3 -I -B -S``.  The checker replays the externally
pinned combined graph candidate, holds every already-acquired source byte by
descriptor, and derives the exact Wave4 parent declarations and module/go.mod
H1 pairs twice.  It performs no network, subprocess, authentication, archive
extraction, dependency-source execution, or filesystem write.
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
            "Wave4 decision checker requires unoptimized "
            "`python3 -I -B -S`"
        )


import argparse
import base64
from contextlib import ExitStack
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
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave4-v1.json"
)
READER_PATH = (
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-"
    "decision-wave4-v1.md"
)
THIS_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_decision_v1.py"
)
THIS_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave4_decision_v1.py"
)
WAVE4_CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave4_candidate_v1.py"
)
WAVE4_CHECKER_RAW_SHA256 = (
    "9401a9c87f2f2e0ee563b46366c97b2fa2dcb35980a469d242be60d749f4391e"
)
WAVE4_TESTS_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave4_candidate_v1.py"
)
WAVE4_TESTS_RAW_SHA256 = (
    "a058f9ac56a44047269b5366160b942f5dead407894461c1fc80040f283ffb59"
)
WAVE4_CANDIDATE_CONTENT_SHA256 = (
    "59e530d1c040e29eb7c3fb8cdde25925648c70e34d41e66559c2ef2b1d82c718"
)
COMBINED_V2_CONTENT_SHA256 = (
    "fa67dfc9a8d49304bcc9b001e0233582e547313cc17b61934674f776ab9df215"
)
COMBINED_INPUT_SET_SHA256 = (
    "5d79f81dfdc835c0552c0c301a2ef8e669ebcb7d13c0674d9d9cc47929d21a97"
)
COMBINED_GRAPH_SHA256 = (
    "a824e5e3bf5fe0ede2c795192c3102a5f8d607309b3409073163de1313a23fb5"
)
COMBINED_FRONTIER_SHA256 = (
    "568ad0362707a384511c9e23e870bd34ae2ff58faa1043e3afe7e0273227491d"
)
COMPACT_IDENTITY_SHA256 = (
    "7018a78754932244c8bc1449ad9079d19d0c48bcdb287b0109178cb3709895b2"
)
FULL_WITNESS_SHA256 = (
    "338069b9666561cc23dd859a202b72e45e0c7fa2f94b69d6b976777dbd148d86"
)
EXPECTED_READER_RAW_SHA256 = (
    "f7176713c9759ec54a21f0cbe77ae2ab5424a8361c256e6af50ad6a43bbba196"
)
CHECKER_ID = "g2-pion-ice-v4.3.0-wave4-identity-acquisition-decision-check-v1"
DECISION_ID = (
    "g2-pion-ice-v4.3.0-rung3-bounded-dependency-source-"
    "identity-and-acquisition-decision-wave4-v1"
)
MAXIMUM_CODE_BYTES = 4 * 1024 * 1024
MAXIMUM_DECISION_BYTES = 8 * 1024 * 1024
MAXIMUM_SOURCE_BYTES = 16 * 1024 * 1024
MAXIMUM_GO_METADATA_BYTES = 1024 * 1024
MAXIMUM_ARCHIVE_ENTRIES = 100_000
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
WAVE4_CLAIM_PATH = f"{DEPENDENCY_ROOT}/.wave-4-v1.claim"
WAVE4_STAGING_PREFIX = ".wave-4-v1-staging-"
WAVE4_FINAL_NAME = "wave-4-v1"
WAVE4_ACCEPTED_PATH = f"{DEPENDENCY_ROOT}/wave-4-v1/accepted"


class DecisionFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise DecisionFailure("E_ARGUMENT")


def require(condition: bool, code: str) -> None:
    if not condition:
        raise DecisionFailure(code)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def digest_json_bytes(value: Any) -> bytes:
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
            parse_float=lambda _: (_ for _ in ()).throw(
                DecisionFailure("E_JSON")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                DecisionFailure("E_JSON")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DecisionFailure("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    require("contentBinding" not in result, "E_CONTENT")
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": (
            "utf8_ascii_escaped_sorted_keys_compact_single_lf"
        ),
        "scope": "decision_without_contentBinding",
        "sha256": sha256_bytes(canonical_json_bytes(result)),
    }
    return result


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


class PinnedFile:
    """Hold one exact, immutable-by-name file beneath the workspace root."""

    def __init__(
        self,
        root: Path,
        relative_path: str,
        *,
        expected_sha256: str | None = None,
        maximum_bytes: int = MAXIMUM_CODE_BYTES,
    ) -> None:
        self.root_path = root
        self.relative_path = relative_path
        self.root_fd = -1
        self.parent_fd = -1
        self.fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        self.raw = b""
        try:
            parts = relative_path.split("/")
            require(
                bool(parts)
                and all(part not in {"", ".", ".."} for part in parts),
                "E_FILE_IDENTITY",
            )
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self.root_initial = os.fstat(self.root_fd)
            self._validate_directory(self.root_initial)
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
            self._validate_file(self.initial, maximum_bytes)
            first = self._read_pass(maximum_bytes)
            second = self._read_pass(maximum_bytes)
            require(first == second, "E_FILE_IDENTITY")
            if expected_sha256 is not None:
                require(
                    sha256_bytes(first) == expected_sha256,
                    "E_FILE_IDENTITY",
                )
            self.raw = first
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _validate_directory(info: os.stat_result) -> None:
        require(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_FILE_IDENTITY",
        )

    @staticmethod
    def _validate_file(
        info: os.stat_result,
        maximum_bytes: int,
    ) -> None:
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0
            and 0 < info.st_size <= maximum_bytes,
            "E_FILE_IDENTITY",
        )

    def _read_pass(self, maximum_bytes: int) -> bytes:
        os.lseek(self.fd, 0, os.SEEK_SET)
        before = os.fstat(self.fd)
        self._validate_file(before, maximum_bytes)
        remaining = before.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_FILE_IDENTITY")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(os.read(self.fd, 1) == b"", "E_FILE_IDENTITY")
        after = os.fstat(self.fd)
        require(
            file_identity(before) == file_identity(after),
            "E_FILE_IDENTITY",
        )
        return b"".join(chunks)

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root_path, follow_symlinks=False)
            current = os.fstat(self.fd)
            named = os.stat(
                self.name,
                dir_fd=self.parent_fd,
                follow_symlinks=False,
            )
        except OSError as error:
            raise DecisionFailure("E_FILE_IDENTITY") from error
        require(
            directory_identity(held_root)
            == directory_identity(self.root_initial)
            == directory_identity(named_root),
            "E_ROOT_IDENTITY",
        )
        require(
            file_identity(current)
            == file_identity(self.initial)
            == file_identity(named),
            "E_FILE_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            require(
                directory_identity(os.fstat(child))
                == directory_identity(initial)
                == directory_identity(
                    os.stat(
                        component,
                        dir_fd=parent,
                        follow_symlinks=False,
                    )
                ),
                "E_FILE_IDENTITY",
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

    def __enter__(self) -> "PinnedFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class HeldNamespace:
    """Hold the dependency directory and prove the Wave4 namespace absent."""

    def __init__(self, root: Path) -> None:
        self.root_path = root
        self.root_fd = -1
        self.namespace_fd = -1
        self.directories: list[tuple[int, os.stat_result, int, str]] = []
        try:
            self.root_fd = os.open(
                root,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
            )
            self.root_initial = os.fstat(self.root_fd)
            PinnedFile._validate_directory(self.root_initial)
            current = os.dup(self.root_fd)
            for component in DEPENDENCY_ROOT.split("/"):
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
                PinnedFile._validate_directory(info)
                self.directories.append((child, info, current, component))
                current = child
            self.namespace_fd = current
            self.final_barrier()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _portable(value: str) -> str:
        return unicodedata.normalize("NFC", value).casefold()

    def observe_absent(self) -> None:
        try:
            names = os.listdir(self.namespace_fd)
        except OSError as error:
            raise DecisionFailure("E_NAMESPACE") from error
        claim = self._portable(Path(WAVE4_CLAIM_PATH).name)
        final = self._portable(WAVE4_FINAL_NAME)
        staging = self._portable(WAVE4_STAGING_PREFIX)
        portable_names = [self._portable(name) for name in names]
        require(
            claim not in portable_names
            and final not in portable_names
            and not any(name.startswith(staging) for name in portable_names),
            "E_NAMESPACE",
        )

    def final_barrier(self) -> None:
        try:
            held_root = os.fstat(self.root_fd)
            named_root = os.stat(self.root_path, follow_symlinks=False)
        except OSError as error:
            raise DecisionFailure("E_NAMESPACE") from error
        require(
            directory_identity(held_root)
            == directory_identity(self.root_initial)
            == directory_identity(named_root),
            "E_ROOT_IDENTITY",
        )
        for child, initial, parent, component in self.directories:
            try:
                held = os.fstat(child)
                named = os.stat(
                    component,
                    dir_fd=parent,
                    follow_symlinks=False,
                )
            except OSError as error:
                raise DecisionFailure("E_NAMESPACE") from error
            require(
                directory_identity(held)
                == directory_identity(initial)
                == directory_identity(named),
                "E_NAMESPACE",
            )
        self.observe_absent()

    def close(self) -> None:
        seen: set[int] = set()
        for child, _, parent, _ in reversed(self.directories):
            if child not in seen:
                os.close(child)
                seen.add(child)
            if parent not in seen:
                os.close(parent)
                seen.add(parent)
        self.directories.clear()
        self.namespace_fd = -1
        if self.root_fd >= 0 and self.root_fd not in seen:
            os.close(self.root_fd)
        self.root_fd = -1

    def __enter__(self) -> "HeldNamespace":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def identity_barrier(root: Path, held: Sequence[Any]) -> None:
    try:
        named_before = os.stat(root, follow_symlinks=False)
        require(stat.S_ISDIR(named_before.st_mode), "E_ROOT_IDENTITY")
        expected = directory_identity(named_before)
        for item in held:
            root_fd = getattr(item, "root_fd", -1)
            require(
                type(root_fd) is int
                and root_fd >= 0
                and directory_identity(os.fstat(root_fd)) == expected,
                "E_ROOT_IDENTITY",
            )
        for item in held:
            item.final_barrier()
        require(
            directory_identity(os.stat(root, follow_symlinks=False))
            == expected,
            "E_ROOT_IDENTITY",
        )
    except OSError as error:
        raise DecisionFailure("E_ROOT_IDENTITY") from error


def load_wave4_checker(held: PinnedFile) -> types.ModuleType:
    module = types.ModuleType("aetherlink_wave4_candidate_checker_pinned")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(ROOT / WAVE4_CHECKER_PATH),
            "__loader__": None,
            "__name__": "aetherlink_wave4_candidate_checker_pinned",
            "__package__": None,
        }
    )
    try:
        code = compile(
            held.raw,
            WAVE4_CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise DecisionFailure("E_WAVE4_CHECKER_LOAD") from error
    for name in (
        "BootstrapPinnedCodeFile",
        "canonical_json_bytes",
        "content_bound",
        "load_v2_checker",
        "validate_v2_candidate",
        "wave4_rows",
    ):
        require(callable(getattr(module, name, None)), "E_WAVE4_CHECKER_API")
    require(
        module.CHECKER_ID
        == "g2-pion-ice-v4.3.0-wave4-frontier-candidate-check-v1"
        and module.V2_CANDIDATE_CONTENT_SHA256
        == COMBINED_V2_CONTENT_SHA256
        and module.V2_INPUT_SET_SHA256 == COMBINED_INPUT_SET_SHA256
        and module.V2_GRAPH_SHA256 == COMBINED_GRAPH_SHA256
        and module.V2_FRONTIER_SHA256 == COMBINED_FRONTIER_SHA256,
        "E_WAVE4_CHECKER_API",
    )
    return module


def strict_text_lines(raw: bytes, code: str) -> list[str]:
    require(
        len(raw) <= MAXIMUM_GO_METADATA_BYTES
        and b"\x00" not in raw
        and b"\r" not in raw,
        code,
    )
    try:
        return raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise DecisionFailure(code) from error


def valid_h1(value: str) -> bool:
    if not value.startswith("h1:"):
        return False
    try:
        decoded = base64.b64decode(value[3:], validate=True)
    except (ValueError, base64.binascii.Error):
        return False
    return len(decoded) == 32


def capture_declarations(
    *,
    raw: bytes,
    runner: types.ModuleType,
    targets: Mapping[tuple[str, str], Mapping[str, Any]],
    holder_module: str,
    holder_version: str,
    holder_wave: str,
    container_kind: str,
    path: str,
    container_raw_sha256: str,
    entry_raw_sha256: str | None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    try:
        runner.parse_go_mod(raw, holder_module)
    except Exception as error:
        raise DecisionFailure("E_GO_MOD") from error
    lines = strict_text_lines(raw, "E_GO_MOD")
    result = {key: [] for key in targets}
    block: str | None = None
    for line_number, text in enumerate(lines, 1):
        try:
            tokens = runner.tokenize_mod_line(text)
        except Exception as error:
            raise DecisionFailure("E_GO_MOD") from error
        if not tokens:
            continue
        pair: tuple[str, str] | None = None
        if block is not None:
            if tokens == [")"]:
                block = None
                continue
            if block == "require":
                require(len(tokens) == 2, "E_GO_MOD")
                pair = (tokens[0], tokens[1])
        elif len(tokens) == 2 and tokens[1] == "(":
            block = tokens[0]
        elif tokens[0] == "require":
            require(len(tokens) == 3, "E_GO_MOD")
            pair = (tokens[1], tokens[2])
        if pair in targets:
            result[pair].append(
                {
                    "containerKind": container_kind,
                    "holderModule": holder_module,
                    "holderVersion": holder_version,
                    "holderWave": holder_wave,
                    "path": path,
                    "line": line_number,
                    "text": text,
                    "containerRawSha256": container_raw_sha256,
                    "entryRawSha256": entry_raw_sha256,
                }
            )
    require(block is None, "E_GO_MOD")
    return result


def parse_go_sum_entry(
    *,
    raw: bytes,
    targets: Mapping[tuple[str, str], Mapping[str, Any]],
    holder_module: str,
    holder_version: str,
    holder_wave: str,
    archive_path: str,
    archive_raw_sha256: str,
    entry_path: str,
) -> tuple[
    dict[tuple[str, str], list[dict[str, Any]]],
    dict[tuple[str, str], list[dict[str, Any]]],
]:
    lines = strict_text_lines(raw, "E_GO_SUM")
    zip_result = {key: [] for key in targets}
    mod_result = {key: [] for key in targets}
    entry_hash = sha256_bytes(raw)
    for line_number, text in enumerate(lines, 1):
        tokens = text.split()
        if not tokens:
            continue
        require(len(tokens) == 3 and valid_h1(tokens[2]), "E_GO_SUM")
        module, version_token, h1 = tokens
        if version_token.endswith("/go.mod"):
            version = version_token[:-7]
            bucket = mod_result
        else:
            version = version_token
            bucket = zip_result
        pair = (module, version)
        if pair in targets:
            bucket[pair].append(
                {
                    "holderModule": holder_module,
                    "holderVersion": holder_version,
                    "holderWave": holder_wave,
                    "archivePath": archive_path,
                    "archiveRawSha256": archive_raw_sha256,
                    "entryPath": entry_path,
                    "entryRawSha256": entry_hash,
                    "line": line_number,
                    "text": text,
                    "h1": h1,
                }
            )
    return zip_result, mod_result


def merge_witnesses(
    destination: dict[tuple[str, str], list[dict[str, Any]]],
    source: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
) -> None:
    for pair, rows in source.items():
        destination[pair].extend(dict(row) for row in rows)


def validate_archive_names(infos: Sequence[zipfile.ZipInfo]) -> None:
    require(0 < len(infos) <= MAXIMUM_ARCHIVE_ENTRIES, "E_ZIP")
    exact: set[str] = set()
    portable: set[str] = set()
    for info in infos:
        name = info.filename
        require(
            type(name) is str
            and bool(name)
            and "\x00" not in name
            and "\\" not in name
            and not name.startswith("/")
            and not (info.flag_bits & 0x1),
            "E_ZIP",
        )
        components = name[:-1].split("/") if name.endswith("/") else name.split("/")
        require(
            bool(components)
            and all(component not in {"", ".", ".."} for component in components),
            "E_ZIP",
        )
        normalized = unicodedata.normalize("NFC", name).casefold()
        require(name not in exact and normalized not in portable, "E_ZIP")
        exact.add(name)
        portable.add(normalized)
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        require(
            file_type in {0, stat.S_IFREG, stat.S_IFDIR}
            and not stat.S_ISLNK(mode),
            "E_ZIP",
        )


def scan_source_identity(
    *,
    source_bindings: Sequence[Mapping[str, Any]],
    source_raw: Mapping[str, bytes],
    wave_rows: Sequence[Mapping[str, Any]],
    runner: types.ModuleType,
) -> dict[str, Any]:
    targets = {
        (row["module"], row["version"]): row
        for row in wave_rows
    }
    require(len(targets) == len(wave_rows) == 16, "E_TARGETS")
    declarations = {key: [] for key in targets}
    zip_h1 = {key: [] for key in targets}
    mod_h1 = {key: [] for key in targets}
    archive_count = 0
    external_mod_count = 0
    embedded_root_go_mod_count = 0

    for binding in source_bindings:
        path = binding["path"]
        raw = source_raw[path]
        require(
            sha256_bytes(raw) == binding["rawSha256"],
            "E_SOURCE_BINDING",
        )
        if binding["kind"] == "mod":
            external_mod_count += 1
            found = capture_declarations(
                raw=raw,
                runner=runner,
                targets=targets,
                holder_module=binding["module"],
                holder_version=binding["version"],
                holder_wave=binding["wave"],
                container_kind="external_mod",
                path=path,
                container_raw_sha256=binding["rawSha256"],
                entry_raw_sha256=None,
            )
            merge_witnesses(declarations, found)
            continue
        require(binding["kind"] in {"zip", "root_zip"}, "E_SOURCE_BINDING")
        archive_count += 1
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                infos = archive.infolist()
                validate_archive_names(infos)
                if binding["kind"] == "root_zip":
                    expected_go_mod = (
                        f"{binding['module']}@{binding['version']}/go.mod"
                    )
                    matches = [
                        info for info in infos
                        if info.filename == expected_go_mod
                    ]
                    require(len(matches) == 1, "E_ROOT_GO_MOD")
                    info = matches[0]
                    require(
                        not info.is_dir()
                        and info.file_size <= MAXIMUM_GO_METADATA_BYTES,
                        "E_ROOT_GO_MOD",
                    )
                    embedded = archive.read(info)
                    embedded_root_go_mod_count += 1
                    found = capture_declarations(
                        raw=embedded,
                        runner=runner,
                        targets=targets,
                        holder_module=binding["module"],
                        holder_version=binding["version"],
                        holder_wave=binding["wave"],
                        container_kind="embedded_root_mod",
                        path=f"{path}!/{info.filename}",
                        container_raw_sha256=binding["rawSha256"],
                        entry_raw_sha256=sha256_bytes(embedded),
                    )
                    merge_witnesses(declarations, found)
                for info in infos:
                    if not info.filename.endswith("/go.sum"):
                        continue
                    require(
                        not info.is_dir()
                        and info.file_size <= MAXIMUM_GO_METADATA_BYTES,
                        "E_GO_SUM",
                    )
                    entry = archive.read(info)
                    found_zip, found_mod = parse_go_sum_entry(
                        raw=entry,
                        targets=targets,
                        holder_module=binding["module"],
                        holder_version=binding["version"],
                        holder_wave=binding["wave"],
                        archive_path=path,
                        archive_raw_sha256=binding["rawSha256"],
                        entry_path=info.filename,
                    )
                    merge_witnesses(zip_h1, found_zip)
                    merge_witnesses(mod_h1, found_mod)
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            raise DecisionFailure("E_ZIP") from error

    rows = build_identity_rows(
        wave_rows=wave_rows,
        declarations=declarations,
        module_zip_h1=zip_h1,
        go_mod_h1=mod_h1,
    )
    compact = [
        {
            "tupleOrder": row["tupleOrder"],
            "module": row["module"],
            "version": row["version"],
            "selectedByGraphAlgorithm": row["selectedByGraphAlgorithm"],
            "moduleZipH1": row["moduleZipH1Values"][0],
            "goModH1": row["goModH1Values"][0],
        }
        for row in rows
    ]
    return {
        "archiveCount": archive_count,
        "externalModCount": external_mod_count,
        "embeddedRootGoModCount": embedded_root_go_mod_count,
        "tuples": rows,
        "compactIdentity": compact,
        "compactIdentitySha256": sha256_bytes(digest_json_bytes(compact)),
        "fullWitnessSha256": sha256_bytes(digest_json_bytes(rows)),
    }


def build_identity_rows(
    *,
    wave_rows: Sequence[Mapping[str, Any]],
    declarations: Mapping[
        tuple[str, str],
        Sequence[Mapping[str, Any]],
    ],
    module_zip_h1: Mapping[
        tuple[str, str],
        Sequence[Mapping[str, Any]],
    ],
    go_mod_h1: Mapping[
        tuple[str, str],
        Sequence[Mapping[str, Any]],
    ],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for expected_order, wave_row in enumerate(wave_rows, 1):
        require(wave_row["tupleOrder"] == expected_order, "E_TARGETS")
        pair = (wave_row["module"], wave_row["version"])
        declaration_rows = sorted(
            (dict(row) for row in declarations[pair]),
            key=lambda row: (
                row["path"],
                "",
                row["line"],
                row["text"],
            ),
        )
        zip_rows = sorted(
            (dict(row) for row in module_zip_h1[pair]),
            key=lambda row: (
                row["archivePath"],
                row["entryPath"],
                row["line"],
                row["text"],
            ),
        )
        mod_rows = sorted(
            (dict(row) for row in go_mod_h1[pair]),
            key=lambda row: (
                row["archivePath"],
                row["entryPath"],
                row["line"],
                row["text"],
            ),
        )
        zip_values = sorted({row["h1"] for row in zip_rows})
        mod_values = sorted({row["h1"] for row in mod_rows})
        row = {
            "module": pair[0],
            "version": pair[1],
            "selectedByGraphAlgorithm":
                wave_row["selectedByGraphAlgorithm"],
            "declarations": declaration_rows,
            "moduleZipH1Witnesses": zip_rows,
            "goModH1Witnesses": mod_rows,
            "tupleOrder": expected_order,
            "declarationCount": len(declaration_rows),
            "moduleZipH1WitnessCount": len(zip_rows),
            "goModH1WitnessCount": len(mod_rows),
            "moduleZipH1Values": zip_values,
            "goModH1Values": mod_values,
            "declarationComplete": bool(declaration_rows),
            "moduleZipH1Complete": len(zip_values) == 1,
            "goModH1Complete": len(mod_values) == 1,
            "moduleZipH1Conflict": len(zip_values) > 1,
            "goModH1Conflict": len(mod_values) > 1,
            "identityPairComplete":
                len(zip_values) == 1 and len(mod_values) == 1,
        }
        result.append(row)
    return result


def require_closed_identity(scan: Mapping[str, Any]) -> None:
    rows = scan["tuples"]
    require(
        len(rows) == 16
        and scan["archiveCount"] == 51
        and scan["externalModCount"] == 50
        and scan["embeddedRootGoModCount"] == 1
        and sum(row["declarationCount"] for row in rows) == 22
        and sum(row["moduleZipH1WitnessCount"] for row in rows) == 24
        and sum(row["goModH1WitnessCount"] for row in rows) == 26
        and all(
            row["declarationComplete"]
            and row["identityPairComplete"]
            and not row["moduleZipH1Conflict"]
            and not row["goModH1Conflict"]
            for row in rows
        )
        and scan["compactIdentitySha256"] == COMPACT_IDENTITY_SHA256
        and scan["fullWitnessSha256"] == FULL_WITNESS_SHA256,
        "E_IDENTITY_CLOSURE",
    )


def request_set(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        tuple_digest = sha256_bytes(
            f"{row['module']}\n{row['version']}\n".encode("utf-8")
        )
        for kind, expected_h1, maximum_bytes in (
            ("mod", row["goModH1Values"][0], 1024 * 1024),
            ("zip", row["moduleZipH1Values"][0], 16 * 1024 * 1024),
        ):
            result.append(
                {
                    "requestOrdinal": len(result) + 1,
                    "tupleOrder": row["tupleOrder"],
                    "module": row["module"],
                    "version": row["version"],
                    "selectedByGraphAlgorithm":
                        row["selectedByGraphAlgorithm"],
                    "resourceKind": kind,
                    "method": "GET",
                    "host": "proxy.golang.org",
                    "url": (
                        f"https://proxy.golang.org/{row['module']}/"
                        f"@v/{row['version']}.{kind}"
                    ),
                    "expectedH1": expected_h1,
                    "maximumResponseBytes": maximum_bytes,
                    "acceptedFileName": (
                        f"{row['tupleOrder']:03d}-"
                        f"{tuple_digest[:20]}.{kind}"
                    ),
                    "authenticationRequired": False,
                    "networkAuthorized": False,
                    "acquisitionAuthorized": False,
                }
            )
    require(
        len(result) == 32
        and [row["requestOrdinal"] for row in result]
        == list(range(1, 33)),
        "E_REQUEST_SET",
    )
    return result


def validate_source_bindings(
    candidate: Mapping[str, Any],
) -> list[dict[str, Any]]:
    input_set = candidate["inputSet"]
    bindings = input_set["sourceBindings"]
    require(
        type(bindings) is list
        and len(bindings) == 101
        and bindings[0]["kind"] == "root_zip"
        and sum(row["kind"] == "mod" for row in bindings) == 50
        and sum(row["kind"] == "zip" for row in bindings) == 50
        and len({row["path"] for row in bindings}) == 101
        and input_set["combinedInputSetSha256"]
        == COMBINED_INPUT_SET_SHA256,
        "E_SOURCE_BINDING",
    )
    for row in bindings:
        require(
            set(row)
            == {
                "kind",
                "module",
                "path",
                "rawSha256",
                "tupleId",
                "tupleOrder",
                "version",
                "wave",
            }
            and type(row["path"]) is str
            and len(row["rawSha256"]) == 64,
            "E_SOURCE_BINDING",
        )
    return [dict(row) for row in bindings]


def reconstruct_wave4_candidate(
    *,
    wave4: types.ModuleType,
    combined_candidate: Mapping[str, Any],
    wave_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild the exact pinned Wave4 candidate without a second graph run."""

    require(
        combined_candidate["contentBinding"]["sha256"]
        == COMBINED_V2_CONTENT_SHA256,
        "E_WAVE4_CANDIDATE_CONTENT",
    )
    body = {
        "documentType": (
            "aetherlink.g2-pion-rung3-wave4-frontier-"
            "identity-candidate"
        ),
        "schemaVersion": "1.0",
        "checkerId": wave4.CHECKER_ID,
        "status": (
            "exact_16_wave4_frontier_identity_candidates_"
            "prepared_without_authority"
        ),
        "result": (
            "externally_pinned_v2_frontier_projected_"
            "to_wave4_identity_candidates"
        ),
        "verificationOnly": True,
        "recordModeExposed": False,
        "producerPackageBindings": [
            {
                "role": "combined_fixed_point_v2_checker",
                "path": wave4.V2_CHECKER_PATH,
                "rawSha256": wave4.V2_CHECKER_RAW_SHA256,
            },
            {
                "role": "combined_fixed_point_v2_tests",
                "path": wave4.V2_TESTS_PATH,
                "rawSha256": wave4.V2_TESTS_RAW_SHA256,
            },
        ],
        "sourceCandidateBinding": {
            "contentSha256": wave4.V2_CANDIDATE_CONTENT_SHA256,
            "combinedInputSetSha256": wave4.V2_INPUT_SET_SHA256,
            "graphSha256": wave4.V2_GRAPH_SHA256,
            "moduleGraphAndFrontierSha256":
                wave4.V2_MODULE_GRAPH_AND_FRONTIER_SHA256,
            "exactFrontierCanonicalSha256": wave4.V2_FRONTIER_SHA256,
            "route": "next_wave_required",
            "newTupleCount": 16,
            "fixedPointReached": False,
        },
        "wave": {
            "waveId": (
                "g2-pion-ice-v4.3.0-dependency-source-wave4-"
                "candidate-v1"
            ),
            "tupleCount": 16,
            "graphSelectedTupleCount": 3,
            "versionSpecificNonSelectedTupleCount": 13,
            "identityResolvedTupleCount": 0,
            "acquisitionReadyTupleCount": 0,
            "tuples": [dict(row) for row in wave_rows],
        },
        "nextAction": (
            "prepare_separate_wave4_identity_and_acquisition_"
            "decision"
        ),
        "operationCounters": {
            "v2CandidateInvocationCount": 1,
            "inheritedFullSourceReconstructionCount": 2,
            "inheritedArchiveOpenCount": 102,
            "networkOperationCount": 0,
            "subprocessCount": 0,
            "dependencySourceExecutionCount": 0,
            "archiveExtractionCount": 0,
            "fileWriteCount": 0,
        },
        "closure": {
            "dependencyFixedPointReached": False,
            "dependencyClosureComplete": False,
            "wave4IdentityResolved": False,
            "wave4AcquisitionReady": False,
            "semanticClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "releaseReady": False,
        },
        "authority": {
            "decisionAuthorityGranted": False,
            "executionAuthorityGranted": False,
            "identityResolutionAuthorityGranted": False,
            "acquisitionAuthorityGranted": False,
            "publicationAuthorityGranted": False,
            "networkAuthorized": False,
            "dependencySourceExecutionAuthorized": False,
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
        "nonClaims": {
            "frontierIdentityResolved": False,
            "sourceAcquisitionAuthorized": False,
            "dependencyClosureComplete": False,
            "fixedPointReached": False,
            "candidateOrLibrarySelected": False,
            "releaseReady": False,
        },
    }
    projected = wave4.content_bound(
        body,
        "wave4_candidate_without_contentBinding",
    )
    binding = projected.get("contentBinding")
    without = dict(projected)
    without.pop("contentBinding", None)
    require(
        type(binding) is dict
        and binding.get("sha256") == WAVE4_CANDIDATE_CONTENT_SHA256
        and sha256_bytes(wave4.canonical_json_bytes(without))
        == WAVE4_CANDIDATE_CONTENT_SHA256,
        "E_WAVE4_CANDIDATE_CONTENT",
    )
    return projected


def expected_payload(
    *,
    package_raw: Mapping[str, bytes],
    wave4_candidate: Mapping[str, Any],
    wave_rows: Sequence[Mapping[str, Any]],
    source_bindings: Sequence[Mapping[str, Any]],
    scan: Mapping[str, Any],
) -> dict[str, Any]:
    rows = scan["tuples"]
    requests = request_set(rows)
    decision_rows = [
        {
            "tupleOrder": row["tupleOrder"],
            "module": row["module"],
            "version": row["version"],
            "selectedByGraphAlgorithm":
                row["selectedByGraphAlgorithm"],
            "parentDeclarationCount": row["declarationCount"],
            "moduleZipH1WitnessCount":
                row["moduleZipH1WitnessCount"],
            "goModH1WitnessCount": row["goModH1WitnessCount"],
            "moduleZipH1": row["moduleZipH1Values"][0],
            "goModH1": row["goModH1Values"][0],
            "parentDeclarationComplete":
                row["declarationComplete"],
            "identityPairComplete": row["identityPairComplete"],
            "identityConflict": (
                row["moduleZipH1Conflict"]
                or row["goModH1Conflict"]
            ),
            "acquisitionReady": True,
            "acquisitionAuthorized": False,
        }
        for row in rows
    ]
    return {
        "documentType": (
            "aetherlink.g2-pion-rung3-bounded-dependency-source-"
            "identity-and-acquisition-decision-wave4"
        ),
        "schemaVersion": "1.0",
        "checkerId": CHECKER_ID,
        "decisionId": DECISION_ID,
        "date": "2026-07-25",
        "status": (
            "wave4_exact_16_frontier_identity_classified_"
            "16_complete_0_blocked_acquisition_ready_not_authorized"
        ),
        "result": (
            "exact_16_version_vertices_3_selected_13_nonselected_"
            "16_complete_h1_pairs_acquisition_ready_not_authorized"
        ),
        "verificationOnly": True,
        "recordModeExposed": False,
        "predecessorBindings": {
            "wave4Candidate": {
                "checkerPath": WAVE4_CHECKER_PATH,
                "checkerRawSha256": WAVE4_CHECKER_RAW_SHA256,
                "testsPath": WAVE4_TESTS_PATH,
                "testsRawSha256": WAVE4_TESTS_RAW_SHA256,
                "contentSha256":
                    wave4_candidate["contentBinding"]["sha256"],
                "tupleCount": 16,
            },
            "combinedFixedPointV2": {
                "contentSha256": COMBINED_V2_CONTENT_SHA256,
                "combinedInputSetSha256": COMBINED_INPUT_SET_SHA256,
                "graphSha256": COMBINED_GRAPH_SHA256,
                "frontierSha256": COMBINED_FRONTIER_SHA256,
                "fixedPointReached": False,
            },
        },
        "heldSourceInputSet": {
            "sourceBindingCount": len(source_bindings),
            "sourceBindingsSha256": sha256_bytes(
                digest_json_bytes(source_bindings)
            ),
            "archiveCount": scan["archiveCount"],
            "externalModCount": scan["externalModCount"],
            "embeddedRootGoModCount": scan["embeddedRootGoModCount"],
            "allInputsReadTwiceBeforeUse": True,
            "allInputsHeldThroughFinalBarrier": True,
        },
        "identityResolution": {
            "tupleCount": len(rows),
            "graphSelectedTupleCount": sum(
                row["selectedByGraphAlgorithm"] for row in rows
            ),
            "versionSpecificNonSelectedTupleCount": sum(
                not row["selectedByGraphAlgorithm"] for row in rows
            ),
            "parentDeclarationCount": sum(
                row["declarationCount"] for row in rows
            ),
            "moduleZipH1WitnessCount": sum(
                row["moduleZipH1WitnessCount"] for row in rows
            ),
            "goModH1WitnessCount": sum(
                row["goModH1WitnessCount"] for row in rows
            ),
            "completeIdentityPairCount": sum(
                row["identityPairComplete"] for row in rows
            ),
            "blockedTupleCount": sum(
                not (
                    row["declarationComplete"]
                    and row["identityPairComplete"]
                )
                for row in rows
            ),
            "conflictingIdentityCount": sum(
                row["moduleZipH1Conflict"] or row["goModH1Conflict"]
                for row in rows
            ),
            "compactIdentityCanonicalization": (
                "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
            ),
            "compactIdentitySha256": scan["compactIdentitySha256"],
            "fullWitnessCanonicalization": (
                "utf8_unescaped_sorted_keys_compact_no_trailing_lf"
            ),
            "fullWitnessSha256": scan["fullWitnessSha256"],
            "fullWitnessMaterializedInDecision": False,
            "fullWitnessReproducibleByPinnedChecker": True,
            "tuples": decision_rows,
        },
        "sourceAcquisitionPreparation": {
            "acquisitionReady": True,
            "acquisitionAuthorizedByThisDecision": False,
            "separateOneUseExecutionPermitRequired": True,
            "requestCount": len(requests),
            "requestOrder": "tuple_order_ascending_mod_then_zip",
            "requestSet": requests,
            "proxyHost": "proxy.golang.org",
            "modulePathEncoding": (
                "current_wave4_lowercase_ascii_direct_proxy_path"
            ),
            "claimPath": WAVE4_CLAIM_PATH,
            "stagingDirectoryPrefix": WAVE4_STAGING_PREFIX,
            "acceptedDirectoryPath": WAVE4_ACCEPTED_PATH,
            "oneUseNoOverwriteRequired": True,
            "atomicNoReplacePromotionRequired": True,
            "independentPostConsumptionReadbackRequired": True,
        },
        "readerDocumentBinding": {
            "path": READER_PATH,
            "rawSha256": EXPECTED_READER_RAW_SHA256,
        },
        "toolBindings": [
            {
                "role": "wave4_identity_decision_checker",
                "path": THIS_CHECKER_PATH,
                "rawSha256": sha256_bytes(package_raw[THIS_CHECKER_PATH]),
            },
            {
                "role": "wave4_identity_decision_tests",
                "path": THIS_TESTS_PATH,
                "rawSha256": sha256_bytes(package_raw[THIS_TESTS_PATH]),
            },
        ],
        "operationCounters": {
            "combinedV2CandidateInvocationCount": 1,
            "inheritedFullSourceReconstructionCount": 2,
            "identityWitnessScanCount": 2,
            "identityWitnessArchiveOpenCount": 102,
            "networkOperationCount": 0,
            "subprocessCount": 0,
            "authenticationOperationCount": 0,
            "dependencySourceExecutionCount": 0,
            "archiveExtractionCount": 0,
            "fileWriteCount": 0,
        },
        "closure": {
            "wave4IdentityResolved": True,
            "wave4AcquisitionReady": True,
            "wave4AcquisitionComplete": False,
            "dependencyFixedPointReached": False,
            "dependencyClosureComplete": False,
            "semanticClosureComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "rungThreeComplete": False,
            "releaseReady": False,
        },
        "authority": {
            "decisionAuthorityGranted": False,
            "executionAuthorityGranted": False,
            "acquisitionAuthorityGranted": False,
            "networkAuthorized": False,
            "dnsAuthorized": False,
            "socketAuthorized": False,
            "subprocessAuthorized": False,
            "dependencySourceExecutionAuthorized": False,
            "filesystemExtractionAuthorized": False,
            "fileWriteAuthorized": False,
            "gitWriteAuthorized": False,
            "publicationAuthorityGranted": False,
            "repositoryOwnerIdentityProofRequired": False,
            "externalAuthenticationRequired": False,
            "passwordRequired": False,
            "privateKeyRequired": False,
            "signatureRequired": False,
            "tokenRequired": False,
            "userActionRequired": False,
        },
        "nonClaims": [
            "this decision is not a network or source-acquisition execution permit",
            "held H1 pairs establish deterministic acquisition inputs, not source authorship or repository ownership",
            "selectedByGraphAlgorithm false does not remove a version-specific graph vertex",
            "no Wave4 source byte was downloaded, extracted, loaded, executed, reviewed, or compiled",
            "identity readiness is not dependency fixed point, semantic closure, candidate selection, library selection, rung-three completion, or release readiness",
            "no account, owner, SSH, GPG, password, private key, signature, token, or user authentication is required",
        ],
        "nextAction": (
            "prepare_separate_one_use_32_resource_wave4_source_"
            "acquisition_permit_checker_runner_and_tests"
        ),
    }


def evaluate(
    root: Path = ROOT,
    *,
    verify_disk: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    require_isolated_interpreter()
    package_specs = [
        (THIS_CHECKER_PATH, None, MAXIMUM_CODE_BYTES),
        (THIS_TESTS_PATH, None, MAXIMUM_CODE_BYTES),
        (
            READER_PATH,
            EXPECTED_READER_RAW_SHA256,
            MAXIMUM_CODE_BYTES,
        ),
        (
            WAVE4_CHECKER_PATH,
            WAVE4_CHECKER_RAW_SHA256,
            MAXIMUM_CODE_BYTES,
        ),
        (
            WAVE4_TESTS_PATH,
            WAVE4_TESTS_RAW_SHA256,
            MAXIMUM_CODE_BYTES,
        ),
    ]
    if verify_disk:
        package_specs.append(
            (DECISION_PATH, None, MAXIMUM_DECISION_BYTES)
        )
    with ExitStack() as stack:
        namespace_held = stack.enter_context(HeldNamespace(root))
        package_held = {
            path: stack.enter_context(
                PinnedFile(
                    root,
                    path,
                    expected_sha256=expected,
                    maximum_bytes=maximum,
                )
            )
            for path, expected, maximum in package_specs
        }
        wave4 = load_wave4_checker(package_held[WAVE4_CHECKER_PATH])
        v2_held = stack.enter_context(
            wave4.BootstrapPinnedCodeFile(
                root,
                wave4.V2_CHECKER_PATH,
                wave4.V2_CHECKER_RAW_SHA256,
            )
        )
        v2 = wave4.load_v2_checker(v2_held)
        v2_tests_held = stack.enter_context(
            v2.PinnedCodeFile(
                root,
                wave4.V2_TESTS_PATH,
                wave4.V2_TESTS_RAW_SHA256,
            )
        )
        held: list[Any] = [
            namespace_held,
            *package_held.values(),
            v2_held,
            v2_tests_held,
        ]
        identity_barrier(root, held)
        candidate = v2.generate_candidate(root)
        identity_barrier(root, held)
        frontier = wave4.validate_v2_candidate(candidate)
        wave_rows = wave4.wave4_rows(frontier)
        wave4_candidate = reconstruct_wave4_candidate(
            wave4=wave4,
            combined_candidate=candidate,
            wave_rows=wave_rows,
        )
        source_bindings = validate_source_bindings(candidate)

        v1_held = stack.enter_context(
            v2.PinnedCodeFile(
                root,
                v2.V1_CHECKER_PATH,
                v2.V1_CHECKER_RAW_SHA256,
            )
        )
        v1 = v2.load_v1_checker(v1_held)
        provider_held = stack.enter_context(v1.PinnedRunnerFile(root))
        runner = v1.load_pinned_runner(provider_held)
        source_held = stack.enter_context(
            runner.HeldInputSet(
                root,
                [
                    {
                        "path": row["path"],
                        "rawSha256": row["rawSha256"],
                        "maximumBytes": MAXIMUM_SOURCE_BYTES,
                        "ownerOnly": False,
                    }
                    for row in source_bindings
                ],
            )
        )
        held.extend((v1_held, provider_held, source_held))
        identity_barrier(root, held)
        first_scan = scan_source_identity(
            source_bindings=source_bindings,
            source_raw=source_held.raw,
            wave_rows=wave_rows,
            runner=runner,
        )
        identity_barrier(root, held)
        second_scan = scan_source_identity(
            source_bindings=source_bindings,
            source_raw=source_held.raw,
            wave_rows=wave_rows,
            runner=runner,
        )
        require(
            digest_json_bytes(first_scan) == digest_json_bytes(second_scan),
            "E_REPRODUCTION",
        )
        require_closed_identity(first_scan)
        identity_barrier(root, held)
        package_raw = {
            path: item.raw for path, item in package_held.items()
        }
        expected = content_bound(
            expected_payload(
                package_raw=package_raw,
                wave4_candidate=wave4_candidate,
                wave_rows=wave_rows,
                source_bindings=source_bindings,
                scan=first_scan,
            )
        )
        if verify_disk:
            decision_raw = package_raw[DECISION_PATH]
            actual = strict_json(decision_raw)
            require(
                decision_raw == canonical_json_bytes(actual)
                and actual == expected,
                "E_DECISION",
            )
        identity_barrier(root, held)
    return expected, {
        "documentType": "aetherlink.wave4-identity-acquisition-decision-check",
        "schemaVersion": "1.0",
        "status": "validated_16_of_16_acquisition_ready_not_authorized",
        "validationPassed": True,
        "tupleCount": 16,
        "parentDeclarationCount": 22,
        "moduleZipH1WitnessCount": 24,
        "goModH1WitnessCount": 26,
        "completeIdentityPairCount": 16,
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


def error_document(code: str) -> dict[str, Any]:
    return {
        "documentType": "aetherlink.wave4-identity-acquisition-decision-error",
        "schemaVersion": "1.0",
        "status": "failed_closed",
        "failureCode": code,
        "acquisitionAuthorized": False,
        "networkUsed": False,
        "fileWriteCount": 0,
        "sourceAcquired": False,
        "sourceExecutionUsed": False,
        "subprocessCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        parser.add_argument("--print-expected", action="store_true")
        args = parser.parse_args(argv)
        expected, summary = evaluate(
            ROOT,
            verify_disk=not args.print_expected,
        )
        sys.stdout.buffer.write(
            canonical_json_bytes(expected if args.print_expected else summary)
        )
        return 0
    except DecisionFailure as error:
        sys.stdout.buffer.write(canonical_json_bytes(error_document(error.code)))
        return 1
    except Exception:
        sys.stdout.buffer.write(canonical_json_bytes(error_document("E_INTERNAL")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
