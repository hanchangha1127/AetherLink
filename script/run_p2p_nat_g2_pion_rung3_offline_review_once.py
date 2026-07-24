#!/usr/bin/env python3
"""Run the single-use, bounded Pion ICE v4.3.0 offline review permit.

The default mode validates the tracked permit only.  The explicit execution mode
consumes a durable local claim, reads the retained archive through one no-follow
file descriptor, performs a bytes-only static inventory, and publishes two
deterministic JSON reports without replacing existing files.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    """Require the exact interpreter boundary before any non-builtin import."""

    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "offline review runner requires unoptimized `python3 -I -B`"
        )


require_isolated_interpreter()

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG2 = f"{BASE}/rung-two"
RUNG3 = f"{BASE}/rung-three"
PERMIT_PATH = f"{RUNG3}/offline-source-review-execution-permit-v1.json"
RECEIPT_PATH = f"{RUNG2}/source-acquisition-receipt-v1.json"
CHECKER_SOURCE_PATH = "script/check_p2p_nat_g2_pion_rung3_execution_permit.py"
MAXIMUM_TRUST_ROOT_SOURCE_BYTES = 2_097_152

OUTPUT_PARENT = PurePosixPath("build/offline-source/pion-ice-v4.3.0/review-v1")
CLAIM_NAME = ".g2-pion-ice-v4.3.0-rung3-offline-review-v1.claim"
RESULT_NAME = "offline-source-review-result-v1.json"
MANIFEST_NAME = "offline-source-review-manifest-v1.json"
TEMP_RESULT_NAME = f".{RESULT_NAME}.tmp"
TEMP_MANIFEST_NAME = f".{MANIFEST_NAME}.tmp"

EXPECTED_ARCHIVE_PATH = (
    "build/offline-source/pion-ice-v4.3.0/original/"
    "github.com-pion-ice-v4@v4.3.0.zip"
)
MODULE_PREFIX = "github.com/pion/ice/v4@v4.3.0/"
EXPECTED_ARCHIVE_BYTES = 293_023
EXPECTED_ARCHIVE_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
EXPECTED_ENTRY_COUNT = 129
EXPECTED_FILE_COUNT = 129
EXPECTED_TOTAL_UNCOMPRESSED_BYTES = 1_131_286

MAXIMUM_ARCHIVE_BYTES = 524_288
MAXIMUM_ENTRIES = 4_096
MAXIMUM_CENTRAL_DIRECTORY_BYTES = 4_194_304
MAXIMUM_PATH_BYTES = 1_024
MAXIMUM_PATH_COMPONENTS = 32
MAXIMUM_COMPONENT_BYTES = 255
MAXIMUM_SINGLE_FILE_BYTES = 4_194_304
MAXIMUM_TEXT_FILE_BYTES = 2_097_152
MAXIMUM_TOTAL_UNCOMPRESSED_BYTES = 67_108_864
MAXIMUM_COMPRESSION_RATIO = 200
MAXIMUM_JSON_REPORT_BYTES = 2_097_152
MAXIMUM_RECORDED_HITS_PER_PATCH_UNIT = 512
MAXIMUM_DEPENDENCY_RECORDS = 4_096

PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)
VERIFICATION_IDS = (
    "g2-r3-egress-path-coverage",
    "g2-r3-ingress-path-coverage",
    "g2-r3-address-and-resolution-adversarial",
    "g2-r3-turn-tls-service-identity",
    "g2-r3-secure-session-promotion",
    "g2-r3-resource-and-event-bounds",
    "g2-r3-secret-free-diagnostics",
    "g2-r3-deadline-shutdown",
)
VERIFICATION_CROSSWALK: Mapping[str, tuple[str, ...]] = {
    VERIFICATION_IDS[0]: (PATCH_UNITS[0], PATCH_UNITS[4], PATCH_UNITS[5], PATCH_UNITS[6]),
    VERIFICATION_IDS[1]: (PATCH_UNITS[0], PATCH_UNITS[2], PATCH_UNITS[4], PATCH_UNITS[6]),
    VERIFICATION_IDS[2]: (PATCH_UNITS[4], PATCH_UNITS[5]),
    VERIFICATION_IDS[3]: (PATCH_UNITS[1], PATCH_UNITS[5]),
    VERIFICATION_IDS[4]: (PATCH_UNITS[6],),
    VERIFICATION_IDS[5]: (PATCH_UNITS[2], PATCH_UNITS[3]),
    VERIFICATION_IDS[6]: (PATCH_UNITS[1],),
    VERIFICATION_IDS[7]: (PATCH_UNITS[3],),
}

REVIEW_RULES: Mapping[str, tuple[tuple[str, str], ...]] = {
    PATCH_UNITS[0]: (
        ("egress-dial", r"\b(?:Dial|DialContext|DialUDP|WriteTo|WriteToUDP)\b"),
        ("egress-listen", r"\b(?:Listen|ListenPacket|ListenUDP|PacketConn)\b"),
        ("candidate-io", r"\b(?:Candidate|UDPMux|UniversalUDPMux|sendBindingRequest)\b"),
    ),
    PATCH_UNITS[1]: (
        ("diagnostic-call", r"\b(?:Tracef|Debugf|Infof|Warnf|Errorf|Logf|Logger)\b"),
        ("credential-token", r"(?i)\b(?:credential|password|username|ufrag|pwd|secret)\b"),
    ),
    PATCH_UNITS[2]: (
        ("callback", r"\bOn(?:ConnectionStateChange|SelectedCandidatePairChange)\b"),
        ("channel", r"\b(?:chan|close)\b|make\s*\(\s*chan\b"),
        ("event", r"(?i)\b(?:event|callback|handler)\b"),
    ),
    PATCH_UNITS[3]: (
        ("deadline", r"\b(?:SetDeadline|SetReadDeadline|SetWriteDeadline|WithTimeout)\b"),
        ("shutdown", r"\b(?:Close|cancel|WaitGroup|Done)\b"),
        ("time-bound", r"(?i)\b(?:deadline|timeout|shutdown)\b"),
    ),
    PATCH_UNITS[4]: (
        ("transport-path", r"(?i)\b(?:tcp|udp|mdns|proxy|relay|host|srflx|upnp)\b"),
        ("network-type", r"\b(?:NetworkType|CandidateType|TCPType)\b"),
    ),
    PATCH_UNITS[5]: (
        ("resolver", r"\b(?:Resolver|LookupIP|LookupHost|ResolveIPAddr)\b"),
        ("turn-tls", r"\b(?:ServerName|InsecureSkipVerify|TLSConfig|tls\.Config|TURN)\b"),
        ("network-injection", r"\b(?:Net|TransportNet|vnet)\b"),
    ),
    PATCH_UNITS[6]: (
        ("pre-auth", r"(?i)\b(?:auth|credential|username|password|ufrag|pwd)\b"),
        ("promotion-state", r"\b(?:ConnectionState|setState|validate|Validate)\b"),
        ("one-use", r"(?i)\b(?:one.?use|single.?use|nonce|replay)\b"),
    ),
}


class ReviewError(RuntimeError):
    """Fail-closed review error."""


class PublishedReportStateError(ReviewError):
    """A report was published but completion became uncertain."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def content_bound_document(document: dict[str, Any], scope: str) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("contentBinding", None)
    digest = sha256_bytes(canonical_json_bytes(payload))
    result = dict(document)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": digest,
    }
    return result


def strict_json(raw: bytes, label: str) -> Any:
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        raise ReviewError(f"{label} must use one terminal LF and no CR bytes")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewError(f"{label} is not strict UTF-8") from error

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise ReviewError(f"{label} contains duplicate JSON key {key!r}")
            output[key] = value
        return output

    try:
        return json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ReviewError(f"{label} contains non-finite value {value}")
            ),
        )
    except (json.JSONDecodeError, TypeError) as error:
        raise ReviewError(f"{label} is not valid strict JSON") from error


def directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def file_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def create_file_flags() -> int:
    return (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def validate_directory_descriptor(fd: int, label: str, *, owner_only: bool = False) -> None:
    metadata = os.fstat(fd)
    require(stat.S_ISDIR(metadata.st_mode), f"{label} is not a directory")
    require(metadata.st_uid == os.getuid(), f"{label} is not owned by the current user")
    require(not metadata.st_mode & 0o022, f"{label} is group- or world-writable")
    if owner_only:
        require(stat.S_IMODE(metadata.st_mode) == 0o700, f"{label} must have mode 0700")


def validate_relative_path(path: str) -> tuple[str, ...]:
    require(isinstance(path, str), "archive path must be a string")
    require("\\" not in path and "\x00" not in path, "archive path has a forbidden separator")
    pure = PurePosixPath(path)
    require(not pure.is_absolute(), "archive path must be repository-relative")
    parts = pure.parts
    require(parts and all(part not in ("", ".", "..") for part in parts), "archive path is unsafe")
    require(parts[0] == "build", "archive path must remain under the fixed build prefix")
    return parts


def open_root_directory() -> int:
    try:
        fd = os.open(ROOT, directory_open_flags())
    except OSError as error:
        raise ReviewError(f"unable to open repository root safely: {error}") from error
    try:
        validate_directory_descriptor(fd, "repository root")
        return fd
    except BaseException:
        os.close(fd)
        raise


def require_no_project_search_path_shadowing() -> None:
    """Fail if isolated import search unexpectedly includes this project."""

    root_path = os.path.realpath(os.fspath(ROOT))
    for entry in sys.path:
        candidate = os.getcwd() if entry == "" else entry
        try:
            resolved = os.path.realpath(os.fspath(candidate))
            inside_project = os.path.commonpath((root_path, resolved)) == root_path
        except (OSError, TypeError, ValueError):
            raise ReviewError("unable to validate the isolated module search path")
        require(
            not inside_project,
            "isolated module search path unexpectedly includes the project",
        )


def read_stable_checker_source() -> bytes:
    """Read the checker trust root once through a stable no-follow descriptor."""

    parts = PurePosixPath(CHECKER_SOURCE_PATH).parts
    require(
        parts == ("script", "check_p2p_nat_g2_pion_rung3_execution_permit.py"),
        "checker trust-root path drifted",
    )
    current_fd = open_root_directory()
    source_fd = -1
    try:
        for component in parts[:-1]:
            try:
                next_fd = os.open(component, directory_open_flags(), dir_fd=current_fd)
            except OSError as error:
                raise ReviewError(
                    f"unable to open checker ancestor {component!r}: {error}"
                ) from error
            validate_directory_descriptor(next_fd, f"checker ancestor {component!r}")
            os.close(current_fd)
            current_fd = next_fd
        try:
            source_fd = os.open(parts[-1], file_open_flags(), dir_fd=current_fd)
        except OSError as error:
            raise ReviewError(
                f"unable to open checker trust root safely: {error}"
            ) from error
        before = os.fstat(source_fd)
        require(stat.S_ISREG(before.st_mode), "checker trust root is not a regular file")
        require(
            before.st_uid == os.getuid(),
            "checker trust root is not owned by the current user",
        )
        require(before.st_nlink == 1, "checker trust-root link count drifted")
        require(
            not before.st_mode & 0o022,
            "checker trust root is group- or world-writable",
        )
        require(
            0 < before.st_size <= MAXIMUM_TRUST_ROOT_SOURCE_BYTES,
            "checker trust-root byte size is invalid",
        )
        chunks: list[bytes] = []
        remaining = before.st_size + 1
        while remaining > 0:
            chunk = os.read(source_fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(source_fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        require(
            len(raw) == before.st_size
            and all(
                getattr(before, field) == getattr(after, field)
                for field in stable_fields
            ),
            "checker trust root changed during its single read pass",
        )
        try:
            named = os.stat(parts[-1], dir_fd=current_fd, follow_symlinks=False)
        except OSError as error:
            raise ReviewError(
                f"checker trust-root directory entry changed: {error}"
            ) from error
        require(
            stat.S_ISREG(named.st_mode)
            and named.st_dev == after.st_dev
            and named.st_ino == after.st_ino,
            "checker trust-root path no longer names the reviewed descriptor",
        )
        require(b"\x00" not in raw, "checker trust root contains NUL")
        try:
            raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ReviewError("checker trust root is not strict UTF-8") from error
        return raw
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        os.close(current_fd)


def load_checker_trust_root() -> ModuleType:
    """Execute exact stable checker bytes as the explicit local trust root."""

    require_isolated_interpreter()
    require_no_project_search_path_shadowing()
    raw = read_stable_checker_source()
    try:
        code = compile(
            raw,
            CHECKER_SOURCE_PATH,
            "exec",
            flags=0,
            dont_inherit=True,
            optimize=0,
        )
        module = ModuleType("g2_pion_rung3_execution_permit_local_trust_root")
        module.__dict__.update(
            {
                "__cached__": None,
                "__file__": CHECKER_SOURCE_PATH,
                "__loader__": None,
                "__package__": None,
            }
        )
        exec(code, module.__dict__, module.__dict__)
    except Exception as error:
        raise ReviewError(
            f"unable to execute checker local trust-root bytes: {error}"
        ) from error
    require(
        callable(getattr(module, "validate_repository", None)),
        "checker trust root omitted validate_repository",
    )
    require(
        callable(getattr(module, "load_validated_pure_module", None)),
        "checker trust root omitted load_validated_pure_module",
    )
    return module


def open_relative_regular_file(path: str, *, maximum_bytes: int) -> tuple[int, int, str]:
    parts = validate_relative_path(path)
    current_fd = open_root_directory()
    file_fd = -1
    try:
        for component in parts[:-1]:
            try:
                next_fd = os.open(component, directory_open_flags(), dir_fd=current_fd)
            except OSError as error:
                raise ReviewError(f"unable to open safe ancestor {component!r}: {error}") from error
            validate_directory_descriptor(next_fd, f"archive ancestor {component!r}")
            os.close(current_fd)
            current_fd = next_fd
        name = parts[-1]
        try:
            file_fd = os.open(name, file_open_flags(), dir_fd=current_fd)
        except OSError as error:
            raise ReviewError(f"unable to open retained archive safely: {error}") from error
        metadata = os.fstat(file_fd)
        require(stat.S_ISREG(metadata.st_mode), "retained archive is not a regular file")
        require(metadata.st_uid == os.getuid(), "retained archive owner drifted")
        require(metadata.st_nlink == 1, "retained archive link count drifted")
        require(stat.S_IMODE(metadata.st_mode) == 0o600, "retained archive mode drifted")
        require(metadata.st_size <= maximum_bytes, "retained archive exceeds the permit bound")
        return file_fd, current_fd, name
    except BaseException:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(current_fd)
        raise


def read_one_stable_archive_fd(file_fd: int, parent_fd: int, name: str) -> tuple[bytes, os.stat_result]:
    before = os.fstat(file_fd)
    require(before.st_size == EXPECTED_ARCHIVE_BYTES, "retained archive byte size mismatch")
    chunks: list[bytes] = []
    remaining = EXPECTED_ARCHIVE_BYTES + 1
    while remaining > 0:
        chunk = os.read(file_fd, min(65_536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    raw = b"".join(chunks)
    require(len(raw) == EXPECTED_ARCHIVE_BYTES, "retained archive changed size during its one read pass")
    after = os.fstat(file_fd)
    stable_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_uid",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    require(
        all(getattr(before, field) == getattr(after, field) for field in stable_fields),
        "retained archive descriptor metadata changed during review",
    )
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise ReviewError(f"retained archive directory entry changed during review: {error}") from error
    require(
        stat.S_ISREG(named.st_mode)
        and named.st_dev == after.st_dev
        and named.st_ino == after.st_ino,
        "retained archive path no longer names the reviewed descriptor",
    )
    require(sha256_bytes(raw) == EXPECTED_ARCHIVE_SHA256, "retained archive SHA-256 mismatch")
    return raw, after


def write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise ReviewError("short write while publishing review evidence")
        offset += written


def open_secure_output_directory(*, create_missing: bool) -> int | None:
    current_fd = open_root_directory()
    try:
        for index, component in enumerate(OUTPUT_PARENT.parts):
            created = False
            try:
                next_fd = os.open(component, directory_open_flags(), dir_fd=current_fd)
            except FileNotFoundError:
                if not create_missing:
                    return None
                try:
                    os.mkdir(component, mode=0o700, dir_fd=current_fd)
                    created = True
                except FileExistsError:
                    pass
                next_fd = os.open(component, directory_open_flags(), dir_fd=current_fd)
            is_final = index == len(OUTPUT_PARENT.parts) - 1
            validate_directory_descriptor(
                next_fd,
                f"review output ancestor {component!r}",
                owner_only=is_final,
            )
            if created:
                os.fsync(next_fd)
                os.fsync(current_fd)
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    except OSError as error:
        raise ReviewError(f"unable to open secure review output directory: {error}") from error
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def name_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ReviewError(f"unable to inspect review output name {name!r}: {error}") from error
    return True


def create_claim(directory_fd: int, permit_sha256: str) -> tuple[bytes, str]:
    for name in (CLAIM_NAME, RESULT_NAME, MANIFEST_NAME, TEMP_RESULT_NAME, TEMP_MANIFEST_NAME):
        if name_exists(directory_fd, name):
            raise ReviewError(f"single-use review cannot start because {name!r} already exists")
    claim = {
        "claimType": "aetherlink.g2-pion-rung3-offline-review-one-use-claim",
        "schemaVersion": "1.0",
        "permitRawSha256": permit_sha256,
        "rule": (
            "claim_persists_after_successful_exclusive_creation_even_if_"
            "initialization_or_execution_fails_and_blocks_retry"
        ),
        "automaticRetryAllowed": False,
        "externalIdentityProofRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "userActionRequired": False,
    }
    payload = canonical_json_bytes(claim)
    fd = -1
    try:
        fd = os.open(CLAIM_NAME, create_file_flags(), mode=0o600, dir_fd=directory_fd)
        os.fchmod(fd, 0o600)
        write_all(fd, payload)
        metadata = os.fstat(fd)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and metadata.st_nlink == 1
            and stat.S_IMODE(metadata.st_mode) == 0o600,
            "one-use review claim failed ownership or mode validation",
        )
        os.fsync(fd)
        os.fsync(directory_fd)
        return payload, sha256_bytes(payload)
    except FileExistsError as error:
        raise ReviewError("one-use review permit was already consumed") from error
    finally:
        if fd >= 0:
            os.close(fd)


def create_temporary_report(directory_fd: int, name: str, payload: bytes) -> int:
    require(len(payload) <= MAXIMUM_JSON_REPORT_BYTES, f"report {name!r} exceeds its byte bound")
    try:
        fd = os.open(name, create_file_flags(), mode=0o600, dir_fd=directory_fd)
    except OSError as error:
        raise ReviewError(f"unable to create temporary review report {name!r}: {error}") from error
    try:
        os.fchmod(fd, 0o600)
        write_all(fd, payload)
        metadata = os.fstat(fd)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and metadata.st_nlink == 1
            and stat.S_IMODE(metadata.st_mode) == 0o600
            and metadata.st_size == len(payload),
            f"temporary review report {name!r} failed validation",
        )
        os.fsync(fd)
        return fd
    except BaseException:
        os.close(fd)
        try:
            os.unlink(name, dir_fd=directory_fd)
        except OSError:
            pass
        raise


def publish_no_replace(directory_fd: int, temporary_name: str, final_name: str) -> None:
    try:
        os.link(
            temporary_name,
            final_name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except FileExistsError as error:
        raise ReviewError(f"review report {final_name!r} already exists") from error
    except OSError as error:
        raise ReviewError(f"atomic no-replace publication failed for {final_name!r}: {error}") from error
    try:
        os.unlink(temporary_name, dir_fd=directory_fd)
        os.fsync(directory_fd)
        metadata = os.stat(final_name, dir_fd=directory_fd, follow_symlinks=False)
        require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and metadata.st_nlink == 1
            and stat.S_IMODE(metadata.st_mode) == 0o600,
            f"published review report {final_name!r} failed validation",
        )
    except BaseException as error:
        raise PublishedReportStateError(
            f"review report {final_name!r} was linked but publication completion is uncertain: {error}"
        ) from error


def read_pinned_receipt_archive_path(permit: Mapping[str, Any]) -> str:
    binding = permit.get("archiveIdentityBinding")
    require(isinstance(binding, Mapping), "validated permit omitted archiveIdentityBinding")
    receipt_path = binding.get("receiptPath")
    receipt_sha256 = binding.get("receiptRawSha256")
    require(receipt_path == RECEIPT_PATH, "validated permit receipt path drifted")
    require(isinstance(receipt_sha256, str) and len(receipt_sha256) == 64, "permit receipt hash is invalid")
    parts = PurePosixPath(RECEIPT_PATH).parts
    current_fd = open_root_directory()
    file_fd = -1
    try:
        for component in parts[:-1]:
            next_fd = os.open(component, directory_open_flags(), dir_fd=current_fd)
            validate_directory_descriptor(next_fd, f"receipt ancestor {component!r}")
            os.close(current_fd)
            current_fd = next_fd
        file_fd = os.open(parts[-1], file_open_flags(), dir_fd=current_fd)
        before = os.fstat(file_fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid()
            and before.st_nlink == 1
            and before.st_size <= MAXIMUM_JSON_REPORT_BYTES,
            "pinned acquisition receipt failed file validation",
        )
        chunks: list[bytes] = []
        remaining = before.st_size + 1
        while remaining > 0:
            chunk = os.read(file_fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(file_fd)
        require(len(raw) == before.st_size, "pinned acquisition receipt changed size")
        require(
            before.st_dev == after.st_dev
            and before.st_ino == after.st_ino
            and before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns,
            "pinned acquisition receipt changed while read",
        )
        require(sha256_bytes(raw) == receipt_sha256, "pinned acquisition receipt hash mismatch")
        receipt = strict_json(raw, RECEIPT_PATH)
        require(isinstance(receipt, Mapping), "pinned acquisition receipt must be an object")
        archive = receipt.get("archive")
        require(isinstance(archive, Mapping), "pinned acquisition receipt omitted archive metadata")
        path = archive.get("path")
        require(path == EXPECTED_ARCHIVE_PATH, "pinned acquisition receipt archive path drifted")
        return path
    except OSError as error:
        raise ReviewError(f"unable to read pinned acquisition receipt safely: {error}") from error
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(current_fd)


def load_validated_authority() -> tuple[ModuleType, dict[str, Any]]:
    checker = load_checker_trust_root()
    try:
        result = checker.validate_repository(ROOT)
    except Exception as error:
        if isinstance(error, ReviewError):
            raise
        raise ReviewError(f"rung-three execution permit validation failed: {error}") from error
    require(isinstance(result, dict), "permit checker returned an invalid result")
    require(set(result) == {"permit", "permitRawSha256", "permitSemanticSha256"}, "permit checker result schema drifted")
    require(isinstance(result["permit"], dict), "permit checker did not return the validated permit")
    require(
        isinstance(result["permitRawSha256"], str) and len(result["permitRawSha256"]) == 64,
        "permit checker returned an invalid raw digest",
    )
    return checker, result


def validate_authority() -> dict[str, Any]:
    _checker, result = load_validated_authority()
    return result


def classify_entry(path: str) -> str:
    lowered = path.casefold()
    name = PurePosixPath(path).name.casefold()
    if lowered.endswith(".go"):
        return "go_source"
    if name in {"go.mod", "go.sum"}:
        return "go_module_metadata"
    if name.startswith(("license", "licence", "notice", "copying")):
        return "license_or_notice"
    if lowered.endswith((".md", ".txt", ".yml", ".yaml", ".json", ".toml")):
        return "other_text"
    return "other"


def parse_go_mod(text: str) -> dict[str, Any]:
    module_path: str | None = None
    go_version: str | None = None
    toolchain: str | None = None
    dependencies: set[tuple[str, str, bool]] = set()
    in_require_block = False
    for line in text.splitlines():
        stripped = line.split("//", 1)[0].strip()
        if not stripped:
            continue
        if stripped.startswith("module "):
            module_path = stripped.split(None, 1)[1].strip()
        elif stripped.startswith("go "):
            go_version = stripped.split(None, 1)[1].strip()
        elif stripped.startswith("toolchain "):
            toolchain = stripped.split(None, 1)[1].strip()
        elif stripped == "require (":
            in_require_block = True
        elif in_require_block and stripped == ")":
            in_require_block = False
        elif stripped.startswith("require "):
            fields = stripped.split()
            if len(fields) >= 3:
                dependencies.add((fields[1], fields[2], "// indirect" in line))
        elif in_require_block:
            fields = stripped.split()
            if len(fields) >= 2:
                dependencies.add((fields[0], fields[1], "// indirect" in line))
        if len(dependencies) > MAXIMUM_DEPENDENCY_RECORDS:
            raise ReviewError("go.mod dependency inventory exceeds its record bound")
    require(module_path is not None, "go.mod omitted its module directive")
    return {
        "modulePath": module_path,
        "goVersion": go_version,
        "toolchain": toolchain,
        "requires": [
            {"module": module, "version": version, "indirect": indirect}
            for module, version, indirect in sorted(dependencies)
        ],
    }


def parse_go_sum(text: str) -> dict[str, Any]:
    records: set[tuple[str, str, str]] = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        require(len(fields) == 3, "go.sum contains an unexpected record shape")
        module, version, digest = fields
        require(digest.startswith("h1:"), "go.sum contains a non-h1 digest")
        records.add((module, version, digest))
        if len(records) > MAXIMUM_DEPENDENCY_RECORDS:
            raise ReviewError("go.sum inventory exceeds its record bound")
    return {
        "recordCount": len(records),
        "records": [
            {"module": module, "version": version, "h1": digest}
            for module, version, digest in sorted(records)
        ],
    }


def scan_go_source(path: str, raw: bytes, hits: dict[str, set[tuple[str, int, str]]]) -> None:
    require(len(raw) <= MAXIMUM_TEXT_FILE_BYTES, f"Go source {path!r} exceeds text bound")
    require(b"\x00" not in raw, f"Go source {path!r} contains NUL")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ReviewError(f"Go source {path!r} is not strict UTF-8") from error
    for line_number, line in enumerate(text.splitlines(), start=1):
        for patch_unit, rules in REVIEW_RULES.items():
            for rule_id, pattern in rules:
                if re.search(pattern, line):
                    hits[patch_unit].add((path, line_number, rule_id))
                    if len(hits[patch_unit]) > MAXIMUM_RECORDED_HITS_PER_PATCH_UNIT:
                        raise ReviewError(f"candidate inventory for {patch_unit!r} exceeds its hit bound")


def build_review_documents(
    *,
    authority: Mapping[str, Any],
    claim_sha256: str,
    archive_metadata: os.stat_result,
    inspection: Mapping[str, Any],
) -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    entries = inspection.get("entries")
    require(isinstance(entries, Sequence) and not isinstance(entries, (str, bytes)), "ZIP inspection omitted entries")
    require(inspection.get("entryCount") == EXPECTED_ENTRY_COUNT, "archive entry count mismatch")
    require(inspection.get("fileCount") == EXPECTED_FILE_COUNT, "archive file count mismatch")
    require(
        inspection.get("totalUncompressedBytes") == EXPECTED_TOTAL_UNCOMPRESSED_BYTES,
        "archive total uncompressed size mismatch",
    )

    inventory: list[dict[str, Any]] = []
    license_inventory: list[dict[str, Any]] = []
    hits: dict[str, set[tuple[str, int, str]]] = {unit: set() for unit in PATCH_UNITS}
    go_mod: dict[str, Any] | None = None
    go_sum: dict[str, Any] | None = None
    source_files_observed = 0
    tree_rows: list[bytes] = []

    for entry in entries:
        require(isinstance(entry, Mapping), "ZIP inspection returned a non-object entry")
        path = entry.get("relativePath")
        raw = entry.get("bytes")
        size = entry.get("size")
        digest = entry.get("sha256")
        require(isinstance(path, str) and isinstance(raw, bytes), "ZIP entry shape drifted")
        require(size == len(raw) and digest == sha256_bytes(raw), f"ZIP entry metadata mismatch for {path!r}")
        category = classify_entry(path)
        inventory.append({"path": path, "bytes": size, "sha256": digest, "category": category})
        tree_rows.append(f"{path}\0{size}\0{digest}\n".encode("utf-8"))
        if category == "license_or_notice":
            license_inventory.append({"path": path, "bytes": size, "sha256": digest})
        if category == "go_source":
            source_files_observed += 1
            scan_go_source(path, raw, hits)
        elif PurePosixPath(path).name == "go.mod":
            require(go_mod is None, "archive contains more than one root go.mod")
            require(len(raw) <= MAXIMUM_TEXT_FILE_BYTES and b"\x00" not in raw, "go.mod is invalid text")
            try:
                go_mod = parse_go_mod(raw.decode("utf-8", errors="strict"))
            except UnicodeDecodeError as error:
                raise ReviewError("go.mod is not strict UTF-8") from error
        elif PurePosixPath(path).name == "go.sum":
            require(go_sum is None, "archive contains more than one root go.sum")
            require(len(raw) <= MAXIMUM_TEXT_FILE_BYTES and b"\x00" not in raw, "go.sum is invalid text")
            try:
                go_sum = parse_go_sum(raw.decode("utf-8", errors="strict"))
            except UnicodeDecodeError as error:
                raise ReviewError("go.sum is not strict UTF-8") from error

    inventory.sort(key=lambda row: row["path"].encode("utf-8"))
    license_inventory.sort(key=lambda row: row["path"].encode("utf-8"))
    require(go_mod is not None, "root go.mod metadata was not found")
    require(go_mod["modulePath"] == "github.com/pion/ice/v4", "go.mod module path mismatch")
    require(source_files_observed > 0, "archive contains no observable Go source")
    require(all(hits[unit] for unit in PATCH_UNITS), "one or more patch units have no candidate locations")

    candidate_inventory = []
    for unit in PATCH_UNITS:
        rows = [
            {"path": path, "line": line, "ruleId": rule_id}
            for path, line, rule_id in sorted(hits[unit], key=lambda item: (item[0].encode("utf-8"), item[1], item[2]))
        ]
        candidate_inventory.append(
            {
                "patchUnit": unit,
                "meaning": "lexical_candidate_locations_only_not_type_control_or_data_flow_proof",
                "hitCount": len(rows),
                "hits": rows,
            }
        )

    permit = authority["permit"]
    result_document: dict[str, Any] = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-result",
        "schemaVersion": "1.0",
        "reviewId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-v1",
        "recordedDate": "2026-07-23",
        "status": "rung3_candidate_inventory_recorded_awaiting_completion_manifest",
        "result": (
            "bounded_candidate_location_inventory_recorded_"
            "semantic_review_not_performed"
        ),
        "nextAction": "publish_bound_completion_manifest",
        "contentBinding": {},
        "permitBinding": {
            "path": PERMIT_PATH,
            "permitId": permit.get("permitId"),
            "rawSha256": authority["permitRawSha256"],
            "semanticSha256": authority["permitSemanticSha256"],
            "consumed": True,
        },
        "claimBinding": {
            "path": (OUTPUT_PARENT / CLAIM_NAME).as_posix(),
            "sha256": claim_sha256,
            "retained": True,
            "automaticRetryAllowed": False,
        },
        "archiveEvidence": {
            "receiptPath": RECEIPT_PATH,
            "pathCopiedIntoReport": False,
            "archiveEvidenceId": "G2R2E009",
            "bytes": archive_metadata.st_size,
            "rawSha256": EXPECTED_ARCHIVE_SHA256,
            "mode": "0600",
            "linkCount": 1,
            "entryCount": inspection["entryCount"],
            "fileCount": inspection["fileCount"],
            "totalUncompressedBytes": inspection["totalUncompressedBytes"],
            "modulePrefix": MODULE_PREFIX,
            "readThroughOneStableNoFollowFileDescriptor": True,
            "filesystemExtracted": False,
        },
        "sourceInventory": {
            "treeSha256": sha256_bytes(b"".join(sorted(tree_rows))),
            "entryCount": len(inventory),
            "sourceFilesObserved": source_files_observed,
            "entries": inventory,
        },
        "dependencyMetadata": {
            "goMod": go_mod,
            "goSum": go_sum,
            "inventoryOnlyNoDependencyAcquisition": True,
        },
        "licenseAndNoticeInventory": {
            "meaning": "inventory_only_not_legal_conclusion",
            "fileCount": len(license_inventory),
            "files": license_inventory,
        },
        "patchUnitCandidateInventory": candidate_inventory,
        "profileVerificationUnits": [
            {
                "id": verification_id,
                "relatedPatchUnits": list(VERIFICATION_CROSSWALK[verification_id]),
                "status": (
                    "candidate_location_crosswalk_recorded_"
                    "required_check_not_executed"
                ),
                "meaning": (
                    "candidate_location_crosswalk_only_not_semantic_review_"
                    "or_required_check_evidence"
                ),
            }
            for verification_id in VERIFICATION_IDS
        ],
        "publicationCompletion": {
            "complete": False,
            "completionManifestRequired": True,
            "completionManifestPath": (OUTPUT_PARENT / MANIFEST_NAME).as_posix(),
            "meaning": (
                "this_result_is_explicitly_incomplete_without_the_"
                "bound_completion_manifest"
            ),
        },
        "operationCounters": {
            "claimCreateCount": 1,
            "archiveOpenCount": 1,
            "archiveReadPassCount": 1,
            "archiveEntryEnumerationCount": 1,
            "materializationCount": 0,
            "sourceObservationCount": source_files_observed,
            "reportPublicationCountBeforeResultPublication": 0,
            "requiredReportPublicationCountForCompletion": 2,
            "sourceWriteCount": 0,
            "sourceExecuteCount": 0,
            "subprocessCount": 0,
            "shellCount": 0,
            "dnsCount": 0,
            "networkOperationCount": 0,
            "socketCreateCount": 0,
            "gitOperationCount": 0,
            "packageManagerInvocationCount": 0,
            "reviewedSourceCompilerInvocationCount": 0,
            "verifiedAuxiliaryToolModulePythonCompileCount": 2,
            "deviceOperationCount": 0,
        },
        "executionBoundary": {
            "boundedCandidateLocationInventoryPerformed": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "candidateSelected": False,
            "librarySelected": False,
            "archiveExtracted": False,
            "sourceMaterialized": False,
            "sourcePatched": False,
            "sourceExecuted": False,
            "dependencyInstalled": False,
            "reviewedSourceCompiled": False,
            "verifiedPinnedReviewToolModulesCompiledInMemory": True,
            "reviewedSourceCodeLoaded": False,
            "verifiedPinnedReviewToolModulesLoaded": True,
            "subprocessInvoked": False,
            "shellInvoked": False,
            "dnsUsed": False,
            "networkUsed": False,
            "socketCreated": False,
            "gitOperationPerformed": False,
            "deviceExecutionPerformed": False,
            "productionDeploymentAuthorized": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationRequired": True,
        },
        "evidenceBoundary": {
            "evidenceClass": "bounded_offline_static_inventory_not_os_sandbox_attestation",
            "sourceBodiesRecorded": False,
            "absoluteArchivePathRecorded": False,
            "secretsOrCredentialsRecorded": False,
            "controlOrDataFlowProven": False,
            "typeCorrectnessProven": False,
            "coverageProven": False,
            "licenseConclusionMade": False,
            "reviewedSourceCompileOrRuntimeEvidencePresent": False,
        },
        "personalProjectBoundary": {
            "technicalSafetyGatesRemainRequired": True,
            "repositoryOwnerAuthenticationIsNotATechnicalGate": True,
            "noAuthenticationOrUserActionRequested": True,
        },
    }
    result_document = content_bound_document(result_document, "result_without_contentBinding")
    result_payload = canonical_json_bytes(result_document)
    require(len(result_payload) <= MAXIMUM_JSON_REPORT_BYTES, "review result exceeds its JSON byte bound")

    manifest_document: dict[str, Any] = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-runtime-manifest",
        "schemaVersion": "1.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-runtime-manifest-v1",
        "recordedDate": "2026-07-23",
        "status": (
            "rung3_candidate_location_inventory_committed_"
            "semantic_review_not_performed"
        ),
        "result": (
            "bounded_candidate_location_inventory_publication_committed_"
            "semantic_review_not_performed"
        ),
        "nextAction": (
            "prepare_separate_versioned_rung3_semantic_source_review_decision"
        ),
        "contentBinding": {},
        "permitRawSha256": authority["permitRawSha256"],
        "claimSha256": claim_sha256,
        "archiveRawSha256": EXPECTED_ARCHIVE_SHA256,
        "resultBinding": {
            "path": (OUTPUT_PARENT / RESULT_NAME).as_posix(),
            "bytes": len(result_payload),
            "rawSha256": sha256_bytes(result_payload),
            "requiredStatus": (
                "rung3_candidate_inventory_recorded_"
                "awaiting_completion_manifest"
            ),
        },
        "artifacts": [
            {
                "path": (OUTPUT_PARENT / RESULT_NAME).as_posix(),
                "role": "bounded_offline_static_review_result",
                "bytes": len(result_payload),
                "rawSha256": sha256_bytes(result_payload),
            }
        ],
        "publication": {
            "soleCompletionMarker": True,
            "boundResultPublicationComplete": True,
            "boundedCandidateLocationInventoryPerformed": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "ownerOnlyDirectoryMode": "0700",
            "fileMode": "0600",
            "atomicNoReplace": True,
            "directoryFsyncRequired": True,
            "sourceMaterializationCount": 0,
        },
    }
    manifest_document = content_bound_document(manifest_document, "manifest_without_contentBinding")
    manifest_payload = canonical_json_bytes(manifest_document)
    require(len(manifest_payload) <= MAXIMUM_JSON_REPORT_BYTES, "review manifest exceeds its JSON byte bound")
    return result_payload, manifest_payload, result_document, manifest_document


def check_permit() -> dict[str, Any]:
    authority = validate_authority()
    permit = authority["permit"]
    return {
        "documentType": "aetherlink.g2-pion-rung3-offline-review-run-result",
        "schemaVersion": "1.0",
        "status": "permit_validated_consumption_state_not_inspected",
        "permitConsumptionState": "not_inspected",
        "permitId": permit.get("permitId"),
        "permitRawSha256": authority["permitRawSha256"],
        "archiveOpenCount": 0,
        "archiveReadPassCount": 0,
        "fileWriteCount": 0,
        "reviewedSourceCompilerInvocationCount": 0,
        "verifiedAuxiliaryToolModulePythonCompileCount": 1,
        "reviewPerformed": False,
        "externalIdentityProofRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "userActionRequired": False,
    }


def execute_permit() -> dict[str, Any]:
    checker, authority = load_validated_authority()
    output_fd = open_secure_output_directory(create_missing=True)
    if output_fd is None:
        raise ReviewError("secure review output directory was not created")
    archive_fd = -1
    archive_parent_fd = -1
    result_temp_fd = -1
    manifest_temp_fd = -1
    published: list[str] = []
    try:
        _claim_payload, claim_sha256 = create_claim(output_fd, authority["permitRawSha256"])
        try:
            offline_zip = checker.load_validated_pure_module(ROOT)
        except Exception as error:
            raise ReviewError(
                f"validated pure review tool load failed after permit consumption: {error}"
            ) from error
        archive_path = read_pinned_receipt_archive_path(authority["permit"])
        archive_fd, archive_parent_fd, archive_name = open_relative_regular_file(
            archive_path,
            maximum_bytes=MAXIMUM_ARCHIVE_BYTES,
        )
        raw_archive, archive_metadata = read_one_stable_archive_fd(
            archive_fd,
            archive_parent_fd,
            archive_name,
        )
        try:
            inspection = offline_zip.inspect_module_zip(
                raw_archive,
                module_prefix=MODULE_PREFIX,
                limits={
                    "archiveBytes": MAXIMUM_ARCHIVE_BYTES,
                    "entryCount": MAXIMUM_ENTRIES,
                    "centralDirectoryBytes": MAXIMUM_CENTRAL_DIRECTORY_BYTES,
                    "pathBytes": MAXIMUM_PATH_BYTES,
                    "pathComponents": MAXIMUM_PATH_COMPONENTS,
                    "componentBytes": MAXIMUM_COMPONENT_BYTES,
                    "singleFileBytes": MAXIMUM_SINGLE_FILE_BYTES,
                    "totalUncompressedBytes": MAXIMUM_TOTAL_UNCOMPRESSED_BYTES,
                    "compressionRatio": MAXIMUM_COMPRESSION_RATIO,
                },
            )
        except Exception as error:
            raise ReviewError(f"offline ZIP validation failed: {error}") from error
        (
            result_payload,
            manifest_payload,
            _result_document,
            manifest_document,
        ) = build_review_documents(
            authority=authority,
            claim_sha256=claim_sha256,
            archive_metadata=archive_metadata,
            inspection=inspection,
        )
        result_temp_fd = create_temporary_report(output_fd, TEMP_RESULT_NAME, result_payload)
        manifest_temp_fd = create_temporary_report(output_fd, TEMP_MANIFEST_NAME, manifest_payload)
        os.close(result_temp_fd)
        result_temp_fd = -1
        os.close(manifest_temp_fd)
        manifest_temp_fd = -1
        publish_no_replace(output_fd, TEMP_RESULT_NAME, RESULT_NAME)
        published.append(RESULT_NAME)
        publish_no_replace(output_fd, TEMP_MANIFEST_NAME, MANIFEST_NAME)
        published.append(MANIFEST_NAME)
        require(len(published) == 2, "review reports were not both published")
        return {
            "documentType": "aetherlink.g2-pion-rung3-offline-review-run-result",
            "schemaVersion": "1.0",
            "status": manifest_document["status"],
            "result": manifest_document["result"],
            "nextAction": manifest_document["nextAction"],
            "permitConsumed": True,
            "claimRetained": True,
            "boundedCandidateLocationInventoryPerformed": True,
            "semanticSourceReviewPerformed": False,
            "rungThreeComplete": False,
            "archiveOpenCount": 1,
            "archiveReadPassCount": 1,
            "archiveEntryEnumerationCount": 1,
            "sourceMaterializationCount": 0,
            "reportPublicationCount": 2,
            "subprocessCount": 0,
            "networkOperationCount": 0,
            "socketCreateCount": 0,
            "reviewedSourceCompilerInvocationCount": 0,
            "verifiedAuxiliaryToolModulePythonCompileCount": 2,
            "gitOperationCount": 0,
            "deviceOperationCount": 0,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
        }
    except BaseException as error:
        cleanup_errors: list[str] = []
        for temporary_name in (TEMP_RESULT_NAME, TEMP_MANIFEST_NAME):
            try:
                os.unlink(temporary_name, dir_fd=output_fd)
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                cleanup_errors.append(f"{temporary_name}: {cleanup_error}")
        try:
            os.fsync(output_fd)
        except OSError as cleanup_error:
            cleanup_errors.append(f"directory fsync: {cleanup_error}")
        suffix = f"; cleanup errors: {'; '.join(cleanup_errors)}" if cleanup_errors else ""
        if isinstance(error, PublishedReportStateError):
            raise
        if published:
            raise PublishedReportStateError(
                "offline review partially published evidence and is fail-closed; "
                f"published={published}: {error}{suffix}"
            ) from error
        if isinstance(error, ReviewError):
            if suffix:
                raise ReviewError(f"{error}{suffix}") from error
            raise
        raise ReviewError(
            f"offline review was consumed and failed closed with {type(error).__name__}: {error}{suffix}"
        ) from error
    finally:
        for fd in (result_temp_fd, manifest_temp_fd, archive_fd, archive_parent_fd, output_fd):
            if fd is not None and fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass


def main(argv: Sequence[str] | None = None) -> int:
    require_isolated_interpreter()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-permit", action="store_true")
    mode.add_argument("--execute-permit", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = execute_permit() if args.execute_permit else check_permit()
    except ReviewError as error:
        failure = {
            "documentType": "aetherlink.g2-pion-rung3-offline-review-run-result",
            "schemaVersion": "1.0",
            "status": "failed_closed",
            "reason": str(error),
            "automaticRetryAllowed": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
        }
        if isinstance(error, PublishedReportStateError):
            failure["status"] = "failed_closed_report_publication_uncertain"
            failure["manualEvidenceInspectionRequiredBeforeAnyNewPermit"] = True
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
