#!/usr/bin/env python3
"""Exercise the current source-bound unsealed macOS app under a clean HOME."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
import time
from typing import Callable, Sequence

if __package__:
    from script import check_release_artifact_archive as reader
    from script import run_macos_clean_home_installed_app_smoke as installed
    from script import run_macos_clean_home_installed_state_recovery_smoke as clean_recovery
    from script import run_macos_isolated_upgrade_smoke as publication
    from script import run_macos_packaged_app_lifecycle_smoke as lifecycle
    from script import run_macos_packaged_app_state_recovery_smoke as recovery
else:
    import check_release_artifact_archive as reader
    import run_macos_clean_home_installed_app_smoke as installed
    import run_macos_clean_home_installed_state_recovery_smoke as clean_recovery
    import run_macos_isolated_upgrade_smoke as publication
    import run_macos_packaged_app_lifecycle_smoke as lifecycle
    import run_macos_packaged_app_state_recovery_smoke as recovery


engine = installed.engine
ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_VERSION = 1
REPEATABILITY_SCHEMA_VERSION = 1
RESULT_SCOPE = (
    "same-host-per-user-current-source-unsealed-clean-home-install-"
    "abrupt-process-state-recovery-v1"
)
REPEATABILITY_SCOPE = RESULT_SCOPE + "-repeatability-v1"
COMMAND_POLICY = (
    "sandbox-exec-direct-owned-child-held-code-directory-graceful-"
    "sigkill-recovery-v4"
)
APPKIT_BUNDLE_IDENTIFIER_POLICY = (
    "validated-generation-bundle-id-and-direct-owned-executable-path-v1"
)
OUTPUT_RELATIVE_PATH = Path("dist/unsealed-package-only")
RESULT_RELATIVE_PATH = Path(
    "dist/lifecycle/macos-current-source-unsealed-build-24-clean-home-"
    "install-abrupt-process-state-recovery-v1-source-closure-five.json"
)
REPEATABILITY_RESULT_RELATIVE_PATH = Path(
    "dist/lifecycle/macos-current-source-unsealed-build-24-clean-home-"
    "install-abrupt-process-state-recovery-repeatability-v1-"
    "source-closure-five.json"
)
GENERATION_ENTRIES = {
    "AetherLink.app",
    "AetherLink.dSYM",
    reader.MACOS_UNSEALED_SOURCE_RECEIPT_NAME,
}
LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "post-persisted-sqlite-readback-observation-sigkill-only",
    "no-in-flight-write-checkpoint-or-open-transaction-observed",
    "not-write-durability-crash-consistency-power-loss-or-kernel-crash-evidence",
    "not-os-restart-ui-force-quit-arbitrary-history-or-soak-evidence",
    "not-a-clean-machine-or-separate-account-installation",
    "not-finder-quarantine-or-gatekeeper-evidence",
    "not-tcc-keychain-or-user-consent-evidence",
    "not-developer-id-signing-or-notarization-evidence",
    "not-network-provider-device-ui-or-accessibility-evidence",
    "not-upgrade-rollback-or-n-n-minus-one-evidence",
    "not-production-canonical-g6-g7-or-v1-qualification",
)
ABRUPT_LAUNCH_METHOD = "direct-installed-executable-owned-child"
ABRUPT_PROCESS_DISPOSITION = (
    "exact-owned-child-pid-sigkill-reaped-and-appkit-absent"
)
SIGNAL_TARGET_POLICY = "exact-popen-owned-child-pid-only-v1"
SIGKILL_NUMBER = int(signal.SIGKILL)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
CODESIGN = Path("/usr/bin/codesign")
CODESIGN_DISPLAY_TIMEOUT_SECONDS = 10.0
CODESIGN_DISPLAY_MAX_BYTES = 64 * 1024
CDHASH_PATTERN = re.compile(rb"(?m)^CDHash=([0-9a-f]{40})$")
MACHO_64_MAGIC = 0xFEEDFACF
MACHO_CPU_TYPE_ARM64 = 0x0100000C
MACHO_FILE_TYPE_EXECUTE = 2
MACHO_LOAD_COMMAND_CODE_SIGNATURE = 0x1D
MACHO_HEADER_64_SIZE = 32
MACHO_MAXIMUM_LOAD_COMMAND_COUNT = 4_096
MACHO_MAXIMUM_EXECUTABLE_BYTES = 128 * 1024 * 1024
CODE_SIGNATURE_SUPERBLOB_MAGIC = 0xFADE0CC0
CODE_SIGNATURE_CODE_DIRECTORY_MAGIC = 0xFADE0C02
CODE_SIGNATURE_PRIMARY_CODE_DIRECTORY_SLOT = 0
CODE_DIRECTORY_VERSION_EXEC_SEGMENT = 0x20400
CODE_DIRECTORY_FLAGS_LINKER_ADHOC = 0x20002
CODE_DIRECTORY_HEADER_SIZE = 88
CODE_DIRECTORY_IDENTIFIER = b"AetherLink\x00"
CODE_DIRECTORY_SHA256_HASH_SIZE = 32
CODE_DIRECTORY_SHA256_HASH_TYPE = 2
CODE_DIRECTORY_PAGE_SIZE_EXPONENT = 12
QUALIFICATION = {
    "canonicalG6ExitClaimed": False,
    "canonicalG7ExitClaimed": False,
    "cleanMachineClaimed": False,
    "productionQualificationClaimed": False,
    "signedOrNotarizedClaimed": False,
    "v1QualificationClaimed": False,
}

DIRECT_OWNED_TERMINATION_JXA = r"""
ObjC.import("AppKit");
function run(argv) {
    const pid = Number(argv[0]);
    const expectedExecutablePath = argv[1];
    const expectedBundleIdentifier = argv[2];
    const force = argv[3] === "force";
    if (!Number.isInteger(pid) || pid <= 0) {
        throw new Error("invalid pid");
    }
    const app = $.NSRunningApplication.runningApplicationWithProcessIdentifier(pid);
    if (app.isNil()) {
        return JSON.stringify({
            accepted: false,
            bundleIdentifierState: "absent",
            found: false,
            identityMatched: false
        });
    }
    const executablePath = ObjC.unwrap(app.executableURL.path);
    const bundleIdentifier = ObjC.unwrap(app.bundleIdentifier);
    const bundleUnavailable = (
        bundleIdentifier === undefined || bundleIdentifier === null
    );
    const bundleIdentifierState = bundleUnavailable
        ? "unavailable"
        : bundleIdentifier === expectedBundleIdentifier
            ? "expected"
            : "mismatch";
    const identityMatched = (
        executablePath === expectedExecutablePath
        && bundleIdentifierState !== "mismatch"
    );
    if (!identityMatched) {
        return JSON.stringify({
            accepted: false,
            bundleIdentifierState: bundleIdentifierState,
            found: true,
            identityMatched: false
        });
    }
    return JSON.stringify({
        accepted: force ? Boolean(app.forceTerminate) : Boolean(app.terminate),
        bundleIdentifierState: bundleIdentifierState,
        found: true,
        identityMatched: true
    });
}
"""

# Deliberate aliases: the installed-state recovery implementation owns these
# LaunchServices, log, environment, and SQLite contracts.
recovery_launch_environment = clean_recovery.recovery_launch_environment
validate_captured_log = clean_recovery.validate_captured_log
auxiliary_sqlite_evidence = clean_recovery.auxiliary_sqlite_evidence
prepare_captured_log = clean_recovery.prepare_captured_log
sandbox_profile = lifecycle.build_sandbox_profile
sandbox_preflight = lifecycle.preflight_sandbox


@dataclass(frozen=True)
class GenerationRead:
    app_files: dict[str, bytes]
    app_modes: dict[str, int]
    app_identity: dict[str, object]
    dsym_files: dict[str, bytes]
    dsym_modes: dict[str, int]
    dsym_identity: dict[str, object]
    receipt_bytes: bytes
    receipt_mode: int

    def public_identity(self) -> dict[str, object]:
        return {
            "app": dict(self.app_identity),
            "dSYM": dict(self.dsym_identity),
            "sourceReceipt": {
                "sha256": hashlib.sha256(self.receipt_bytes).hexdigest(),
                "size": len(self.receipt_bytes),
            },
        }


@dataclass(frozen=True)
class DirectOwnedApplicationStatus:
    activation_policy: int
    bundle_identifier_state: str
    executable_path: str
    finished_launching: bool


@dataclass(frozen=True)
class ExecutableDescriptorIdentity:
    device: int
    inode: int
    mode: int
    owner: int
    link_count: int
    size: int
    modified_ns: int
    changed_ns: int
    sha256: str


def _executable_status_identity(
    status: os.stat_result,
    *,
    sha256: str,
) -> ExecutableDescriptorIdentity:
    return ExecutableDescriptorIdentity(
        device=status.st_dev,
        inode=status.st_ino,
        mode=stat.S_IMODE(status.st_mode),
        owner=status.st_uid,
        link_count=status.st_nlink,
        size=status.st_size,
        modified_ns=status.st_mtime_ns,
        changed_ns=status.st_ctime_ns,
        sha256=sha256,
    )


def _read_descriptor_bytes(
    descriptor: int,
    *,
    maximum_bytes: int,
) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(1024 * 1024, maximum_bytes + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum_bytes:
            raise engine.LifecycleSmokeError(
                "installed executable exceeds the captured generation size"
            )
    return b"".join(chunks)


def open_held_installed_executable(
    executable: Path,
    *,
    expected_bytes: bytes,
) -> tuple[int, ExecutableDescriptorIdentity]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        descriptor = os.open(executable, flags)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot hold installed executable descriptor: {error}"
        ) from error
    try:
        status = os.fstat(descriptor)
        payload = _read_descriptor_bytes(
            descriptor,
            maximum_bytes=len(expected_bytes),
        )
        if (
            not stat.S_ISREG(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o755
            or status.st_uid != os.getuid()
            or status.st_nlink != 1
            or status.st_size != len(expected_bytes)
            or payload != expected_bytes
        ):
            raise engine.LifecycleSmokeError(
                "held installed executable differs from the private generation"
            )
        identity = _executable_status_identity(
            status,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        require_held_installed_executable(
            descriptor,
            executable,
            expected=identity,
            expected_bytes=expected_bytes,
        )
        return descriptor, identity
    except BaseException:
        os.close(descriptor)
        raise


def require_held_installed_executable(
    descriptor: int,
    executable: Path,
    *,
    expected: ExecutableDescriptorIdentity,
    expected_bytes: bytes,
) -> None:
    descriptor_status = os.fstat(descriptor)
    try:
        path_status = executable.lstat()
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"installed executable path cannot be re-read: {error}"
        ) from error
    payload = _read_descriptor_bytes(
        descriptor,
        maximum_bytes=len(expected_bytes),
    )
    descriptor_identity = _executable_status_identity(
        descriptor_status,
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    path_identity = _executable_status_identity(
        path_status,
        sha256=descriptor_identity.sha256,
    )
    if (
        not stat.S_ISREG(path_status.st_mode)
        or stat.S_ISLNK(path_status.st_mode)
        or descriptor_identity != expected
        or path_identity != expected
        or payload != expected_bytes
    ):
        raise engine.LifecycleSmokeError(
            "installed executable descriptor or path identity changed"
        )


def parse_codesign_cdhash(payload: bytes, *, label: str) -> str:
    if (
        type(payload) is not bytes
        or not payload
        or len(payload) > CODESIGN_DISPLAY_MAX_BYTES
        or b"\x00" in payload
    ):
        raise engine.LifecycleSmokeError(
            f"{label} codesign display output is not bounded exact bytes"
        )
    matches = CDHASH_PATTERN.findall(payload)
    if len(matches) != 1:
        raise engine.LifecycleSmokeError(
            f"{label} codesign display did not contain one exact CDHash"
        )
    return matches[0].decode("ascii")


def codesign_cdhash_for_target(
    target: str,
    *,
    label: str,
    command_runner: Callable[..., subprocess.CompletedProcess[bytes]] = (
        subprocess.run
    ),
) -> str:
    if type(target) is not str or not target or "\x00" in target:
        raise engine.LifecycleSmokeError(f"{label} codesign target is invalid")
    try:
        completed = command_runner(
            [str(CODESIGN), "-dvvv", target],
            check=False,
            env={"LANG": "C", "LC_ALL": "C"},
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            timeout=CODESIGN_DISPLAY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise engine.LifecycleSmokeError(
            f"{label} codesign display failed: {error}"
        ) from error
    if (
        type(completed.returncode) is not int
        or completed.returncode != 0
        or type(completed.stdout) is not bytes
        or completed.stdout != b""
        or type(completed.stderr) is not bytes
    ):
        raise engine.LifecycleSmokeError(
            f"{label} codesign display command result differs"
        )
    return parse_codesign_cdhash(completed.stderr, label=label)


def codesign_cdhash_for_executable_bytes(payload: bytes) -> str:
    if (
        type(payload) is not bytes
        or len(payload) < MACHO_HEADER_64_SIZE
        or len(payload) > MACHO_MAXIMUM_EXECUTABLE_BYTES
    ):
        raise engine.LifecycleSmokeError(
            "held executable code identity requires bounded exact Mach-O bytes"
        )

    def reject(detail: str) -> None:
        raise engine.LifecycleSmokeError(
            f"held executable Mach-O code identity {detail}"
        )

    (
        magic,
        cpu_type,
        cpu_subtype,
        file_type,
        load_command_count,
        load_command_bytes,
        _flags,
        reserved,
    ) = struct.unpack_from("<IiiIIIII", payload, 0)
    if (
        magic != MACHO_64_MAGIC
        or cpu_type != MACHO_CPU_TYPE_ARM64
        or cpu_subtype != 0
        or file_type != MACHO_FILE_TYPE_EXECUTE
        or reserved != 0
    ):
        reject("header differs from the thin arm64 executable contract")
    if not 1 <= load_command_count <= MACHO_MAXIMUM_LOAD_COMMAND_COUNT:
        reject("load-command count is outside the exact bound")
    commands_end = MACHO_HEADER_64_SIZE + load_command_bytes
    if load_command_bytes <= 0 or commands_end > len(payload):
        reject("load-command byte range is invalid")

    command_offset = MACHO_HEADER_64_SIZE
    code_signature_ranges: list[tuple[int, int]] = []
    for _ in range(load_command_count):
        if command_offset + 8 > commands_end:
            reject("load-command header is truncated")
        command, command_size = struct.unpack_from(
            "<II", payload, command_offset
        )
        next_command_offset = command_offset + command_size
        if (
            command_size < 8
            or command_size % 8 != 0
            or next_command_offset > commands_end
        ):
            reject("load-command size or alignment is invalid")
        if command == MACHO_LOAD_COMMAND_CODE_SIGNATURE:
            if command_size != 16:
                reject("LC_CODE_SIGNATURE size differs")
            _, _, signature_offset, signature_size = struct.unpack_from(
                "<IIII", payload, command_offset
            )
            code_signature_ranges.append((signature_offset, signature_size))
        command_offset = next_command_offset
    if command_offset != commands_end:
        reject("load-command inventory does not consume sizeofcmds")
    if len(code_signature_ranges) != 1:
        reject("requires exactly one LC_CODE_SIGNATURE")

    signature_offset, signature_size = code_signature_ranges[0]
    signature_end = signature_offset + signature_size
    if (
        signature_offset < commands_end
        or signature_offset % 16 != 0
        or signature_size < 20
        or signature_end != len(payload)
    ):
        reject("embedded-signature range is invalid")
    signature = payload[signature_offset:signature_end]
    superblob_magic, superblob_size, blob_count = struct.unpack_from(
        ">III", signature, 0
    )
    if (
        superblob_magic != CODE_SIGNATURE_SUPERBLOB_MAGIC
        or blob_count != 1
        or superblob_size < 20
        or superblob_size > signature_size
        or signature_size - superblob_size > 15
        or any(signature[superblob_size:])
    ):
        reject("embedded-signature SuperBlob differs")

    slot_type, code_directory_offset = struct.unpack_from(
        ">II", signature, 12
    )
    if (
        slot_type != CODE_SIGNATURE_PRIMARY_CODE_DIRECTORY_SLOT
        or code_directory_offset != 20
        or code_directory_offset + 8 > superblob_size
    ):
        reject("primary CodeDirectory index differs")
    code_directory_magic, code_directory_size = struct.unpack_from(
        ">II", signature, code_directory_offset
    )
    if (
        code_directory_magic != CODE_SIGNATURE_CODE_DIRECTORY_MAGIC
        or code_directory_size < CODE_DIRECTORY_HEADER_SIZE
        or code_directory_offset + code_directory_size != superblob_size
    ):
        reject("CodeDirectory byte range differs")
    code_directory = signature[
        code_directory_offset : code_directory_offset + code_directory_size
    ]

    (
        _code_directory_magic,
        _code_directory_size,
        version,
        directory_flags,
        hash_offset,
        identifier_offset,
        special_slot_count,
        code_slot_count,
        code_limit,
        hash_size,
        hash_type,
        platform,
        page_size_exponent,
        spare2,
    ) = struct.unpack_from(">9I4BI", code_directory, 0)
    (
        scatter_offset,
        team_offset,
        spare3,
        code_limit_64,
        executable_segment_base,
        executable_segment_limit,
        executable_segment_flags,
    ) = struct.unpack_from(">IIIQQQQ", code_directory, 44)
    if (
        version != CODE_DIRECTORY_VERSION_EXEC_SEGMENT
        or directory_flags != CODE_DIRECTORY_FLAGS_LINKER_ADHOC
        or hash_size != CODE_DIRECTORY_SHA256_HASH_SIZE
        or hash_type != CODE_DIRECTORY_SHA256_HASH_TYPE
        or platform != 0
        or page_size_exponent != CODE_DIRECTORY_PAGE_SIZE_EXPONENT
        or spare2 != 0
        or scatter_offset != 0
        or team_offset != 0
        or spare3 != 0
        or code_limit_64 != 0
        or executable_segment_base != 0
        or executable_segment_limit <= 0
        or executable_segment_limit > code_limit
        or executable_segment_flags != 1
    ):
        reject("CodeDirectory profile differs")
    if (
        special_slot_count != 0
        or code_limit != signature_offset
        or identifier_offset != CODE_DIRECTORY_HEADER_SIZE
        or hash_offset
        != identifier_offset + len(CODE_DIRECTORY_IDENTIFIER)
        or code_directory[identifier_offset:hash_offset]
        != CODE_DIRECTORY_IDENTIFIER
    ):
        reject("CodeDirectory layout or identifier differs")

    page_size = 1 << page_size_exponent
    expected_code_slot_count = (code_limit + page_size - 1) // page_size
    expected_code_directory_size = (
        hash_offset + code_slot_count * hash_size
    )
    if (
        code_slot_count <= 0
        or code_slot_count != expected_code_slot_count
        or expected_code_directory_size != code_directory_size
    ):
        reject("CodeDirectory slot inventory differs")
    for index in range(code_slot_count):
        page_offset = index * page_size
        page_end = min(page_offset + page_size, code_limit)
        expected_hash_offset = hash_offset + index * hash_size
        expected_hash = code_directory[
            expected_hash_offset : expected_hash_offset + hash_size
        ]
        actual_hash = hashlib.sha256(payload[page_offset:page_end]).digest()
        if actual_hash != expected_hash:
            reject("CodeDirectory page hash differs from held bytes")

    return hashlib.sha256(code_directory).digest()[:20].hex()


def codesign_cdhash_for_running_pid(pid: int) -> str:
    if type(pid) is not int or pid <= 0:
        raise engine.LifecycleSmokeError(
            "running executable code identity requires an exact positive PID"
        )
    return codesign_cdhash_for_target(
        f"+{pid}", label="running executable"
    )


def default_output_root() -> Path:
    return ROOT / OUTPUT_RELATIVE_PATH


def default_result_path() -> Path:
    return ROOT / RESULT_RELATIVE_PATH


def default_repeatability_result_path() -> Path:
    return ROOT / REPEATABILITY_RESULT_RELATIVE_PATH


def _read_unsealed_app_tree(
    app: Path,
) -> tuple[dict[str, bytes], dict[str, int], dict[str, object]]:
    return reader.read_exact_physical_tree(
        app,
        inventory=reader.MACOS_UNSEALED_APP_INVENTORY,
        expected_files=reader.MACOS_UNSEALED_APP_FILES,
        maximum_bytes=reader.MACOS_UNSEALED_APP_MAX_BYTES,
        executable_files={"Contents/MacOS/AetherLink"},
        maximum_total_bytes=603_979_776,
        digest_domain=b"aetherlink-macos-unsealed-app-tree-v1\0",
        label="current-source unsealed app",
    )


def _read_unsealed_dsym_tree(
    dsym: Path,
) -> tuple[dict[str, bytes], dict[str, int], dict[str, object]]:
    return reader.read_exact_physical_tree(
        dsym,
        inventory=reader.MACOS_UNSEALED_DSYM_INVENTORY,
        expected_files=reader.MACOS_UNSEALED_DSYM_FILES,
        maximum_bytes=reader.MACOS_UNSEALED_DSYM_MAX_BYTES,
        executable_files=set(),
        maximum_total_bytes=1_342_177_280,
        digest_domain=b"aetherlink-macos-unsealed-dsym-tree-v1\0",
        label="current-source unsealed dSYM",
    )


def read_generation(output_root: Path) -> GenerationRead:
    absolute_root = Path(os.path.abspath(output_root))
    try:
        root_status = absolute_root.lstat()
        resolved_root = absolute_root.resolve(strict=True)
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot inspect current-source unsealed generation root: {error}"
        ) from error
    if (
        stat.S_ISLNK(root_status.st_mode)
        or not stat.S_ISDIR(root_status.st_mode)
        or resolved_root != absolute_root
    ):
        raise engine.LifecycleSmokeError(
            "current-source unsealed generation root must be a physical directory"
        )
    output_root = absolute_root
    reader.require_directory_inventory(
        output_root,
        GENERATION_ENTRIES,
        "current-source unsealed output generation",
    )
    app_files, app_modes, app_identity = _read_unsealed_app_tree(
        output_root / "AetherLink.app"
    )
    dsym_files, dsym_modes, dsym_identity = _read_unsealed_dsym_tree(
        output_root / "AetherLink.dSYM"
    )
    receipt_path = output_root / reader.MACOS_UNSEALED_SOURCE_RECEIPT_NAME
    receipt_bytes = reader.read_stable_regular_file(
        receipt_path,
        "current-source unsealed receipt",
        maximum_bytes=reader.MACOS_UNSEALED_SOURCE_RECEIPT_MAX_BYTES,
    )
    try:
        receipt_status = receipt_path.lstat()
    except OSError as error:
        raise engine.LifecycleSmokeError(
            f"cannot inspect current-source unsealed receipt: {error}"
        ) from error
    receipt_mode = reader.normalized_mode(receipt_status.st_mode)
    if receipt_mode != 0o644:
        raise engine.LifecycleSmokeError(
            "current-source unsealed receipt mode differs from 0644"
        )
    reader.require_directory_inventory(
        output_root,
        GENERATION_ENTRIES,
        "current-source unsealed output generation after read",
    )
    return GenerationRead(
        app_files=app_files,
        app_modes=app_modes,
        app_identity=app_identity,
        dsym_files=dsym_files,
        dsym_modes=dsym_modes,
        dsym_identity=dsym_identity,
        receipt_bytes=receipt_bytes,
        receipt_mode=receipt_mode,
    )


def require_same_generation(
    expected: GenerationRead,
    observed: GenerationRead,
    *,
    label: str,
) -> None:
    if observed != expected:
        raise engine.LifecycleSmokeError(
            f"{label} differs in exact bytes, modes, or source receipt"
        )


def verify_readback_matches_generation(
    readback: dict[str, object],
    generation: GenerationRead,
) -> None:
    public = generation.public_identity()
    if (
        readback.get("app") != public["app"]
        or readback.get("dSYM") != public["dSYM"]
        or readback.get("sourceReceipt") != public["sourceReceipt"]
        or readback.get("outerBundleSeal") != "absent"
    ):
        raise engine.LifecycleSmokeError(
            "independent readback result differs from the private snapshot"
        )


def copy_generation_with_ditto(
    source: Path,
    destination: Path,
    *,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = (
        engine.run_checked
    ),
) -> None:
    if source.is_symlink() or not source.is_dir():
        raise engine.LifecycleSmokeError(
            "current-source unsealed generation must be a physical directory"
        )
    if destination.exists() or destination.is_symlink():
        raise engine.LifecycleSmokeError(
            "private output snapshot destination already exists"
        )
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise engine.LifecycleSmokeError(
            "private output snapshot parent must be a physical directory"
        )
    command_runner([str(installed.DITTO), str(source), str(destination)])
    if destination.is_symlink() or not destination.is_dir():
        raise engine.LifecycleSmokeError(
            "ditto did not create a physical private output snapshot"
        )


def require_output_paths_outside_generation(
    output_root: Path,
    result_path: Path,
    repeatability_result_path: Path,
) -> None:
    output = output_root.resolve(strict=False)
    targets = (
        result_path.resolve(strict=False),
        repeatability_result_path.resolve(strict=False),
    )
    if targets[0] == targets[1]:
        raise engine.LifecycleSmokeError(
            "canonical result and repeatability receipt paths must differ"
        )
    for target in targets:
        if target == output or output in target.parents:
            raise engine.LifecycleSmokeError(
                "result paths must be outside the unsealed output generation"
            )


def require_canonical_output_root(output_root: Path) -> Path:
    observed = Path(os.path.abspath(output_root))
    expected = Path(os.path.abspath(default_output_root()))
    if observed != expected:
        raise engine.LifecycleSmokeError(
            "current-unsealed lifecycle evidence requires the canonical "
            "dist/unsealed-package-only output root"
        )
    return expected


def remove_exact_installed_app(
    *,
    temporary_root: Path,
    isolated_home: Path,
    app_path: Path,
    expected: GenerationRead,
    lister: Callable[
        [], tuple[installed.RunningApplication, ...]
    ] = installed.list_bundle_applications,
    remover: Callable[[Path], None] = shutil.rmtree,
) -> None:
    expected_app = (
        temporary_root / "home/Applications" / installed.APP_RELATIVE_PATH
    )
    if isolated_home != temporary_root / "home" or app_path != expected_app:
        raise engine.LifecycleSmokeError(
            "removal target must be the exact temporary HOME app"
        )
    observed_files, observed_modes, observed_identity = (
        _read_unsealed_app_tree(app_path)
    )
    if (
        observed_files != expected.app_files
        or observed_modes != expected.app_modes
        or observed_identity != expected.app_identity
    ):
        raise engine.LifecycleSmokeError(
            "exact temporary app changed before final removal"
        )
    executable = app_path / installed.EXECUTABLE_RELATIVE_PATH
    if any(
        installed.application_matches_executable(application, executable)
        for application in lister()
    ):
        raise engine.LifecycleSmokeError(
            "exact temporary app is still running before final removal"
        )
    remover(app_path)
    if app_path.exists() or app_path.is_symlink():
        raise engine.LifecycleSmokeError(
            "exact temporary app remained after final removal"
        )


def query_direct_owned_application(pid: int) -> dict[str, object]:
    return lifecycle.run_jxa(lifecycle.STATUS_JXA, [str(pid)])


def direct_owned_application_status(
    pid: int,
    executable: Path,
    *,
    query_payload: Callable[[int], dict[str, object]] = (
        query_direct_owned_application
    ),
) -> DirectOwnedApplicationStatus | None:
    payload = query_payload(pid)
    if type(payload) is not dict:
        raise engine.LifecycleSmokeError(
            "direct-owned AppKit status must be an object"
        )
    found = payload.get("found")
    if type(found) is not bool:
        raise engine.LifecycleSmokeError(
            "direct-owned AppKit status has an invalid found flag"
        )
    if not found:
        if set(payload) != {"found"}:
            raise engine.LifecycleSmokeError(
                "absent direct-owned AppKit status keys differ"
            )
        return None

    keys = set(payload)
    required = {
        "activationPolicy",
        "executablePath",
        "finishedLaunching",
        "found",
    }
    if keys not in (required, required | {"bundleIdentifier"}):
        raise engine.LifecycleSmokeError(
            "present direct-owned AppKit status keys differ"
        )
    activation_policy = payload["activationPolicy"]
    bundle_identifier = payload.get("bundleIdentifier")
    executable_path = payload["executablePath"]
    finished_launching = payload["finishedLaunching"]
    if (
        type(activation_policy) is not int
        or (
            bundle_identifier is not None
            and type(bundle_identifier) is not str
        )
        or type(executable_path) is not str
        or type(finished_launching) is not bool
    ):
        raise engine.LifecycleSmokeError(
            "direct-owned AppKit status field types differ"
        )
    if bundle_identifier not in (None, installed.EXPECTED_BUNDLE_ID):
        raise engine.LifecycleSmokeError(
            "direct-owned AppKit bundle identifier differs"
        )
    if Path(executable_path).resolve() != executable.resolve():
        raise engine.LifecycleSmokeError(
            "direct-owned AppKit executable path differs"
        )
    return DirectOwnedApplicationStatus(
        activation_policy=activation_policy,
        bundle_identifier_state=(
            "unavailable" if bundle_identifier is None else "expected"
        ),
        executable_path=executable_path,
        finished_launching=finished_launching,
    )


def wait_for_direct_owned_readiness(
    process: subprocess.Popen[bytes],
    executable: Path,
    *,
    timeout_seconds: float,
    query_payload: Callable[[int], dict[str, object]] = (
        query_direct_owned_application
    ),
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> DirectOwnedApplicationStatus:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise engine.LifecycleSmokeError(
                "direct-owned app exited before readiness with code "
                f"{exit_code}"
            )
        status = direct_owned_application_status(
            process.pid,
            executable,
            query_payload=query_payload,
        )
        if status is not None and status.finished_launching:
            if status.activation_policy != 0:
                raise engine.LifecycleSmokeError(
                    "direct-owned app did not enter regular activation policy"
                )
            return status
        remaining = max(0.0, deadline - monotonic())
        sleeper(min(0.1, remaining))
    raise engine.LifecycleSmokeError("direct-owned app readiness timed out")


def terminate_direct_owned_application(
    pid: int,
    executable: Path,
    force: bool,
) -> dict[str, object]:
    return lifecycle.run_jxa(
        DIRECT_OWNED_TERMINATION_JXA,
        [
            str(pid),
            str(executable.resolve()),
            installed.EXPECTED_BUNDLE_ID,
            "force" if force else "graceful",
        ],
    )


def request_direct_owned_termination(
    pid: int,
    executable: Path,
    *,
    force: bool,
    probe: Callable[[int, Path, bool], dict[str, object]] = (
        terminate_direct_owned_application
    ),
) -> bool:
    payload = probe(pid, executable, force)
    if type(payload) is not dict or set(payload) != {
        "accepted",
        "bundleIdentifierState",
        "found",
        "identityMatched",
    }:
        raise engine.LifecycleSmokeError(
            "direct-owned termination result shape differs"
        )
    for key in ("accepted", "found", "identityMatched"):
        if type(payload[key]) is not bool:
            raise engine.LifecycleSmokeError(
                "direct-owned termination result types differ"
            )
    if payload["bundleIdentifierState"] not in {
        "absent",
        "expected",
        "mismatch",
        "unavailable",
    }:
        raise engine.LifecycleSmokeError(
            "direct-owned termination bundle state differs"
        )
    if (
        not payload["found"]
        or not payload["identityMatched"]
        or payload["bundleIdentifierState"]
        not in {"expected", "unavailable"}
    ):
        raise engine.LifecycleSmokeError(
            "direct-owned termination identity did not match"
        )
    return payload["accepted"]


def run_owned_recovery_cycle(
    *,
    ordinal: int,
    app_path: Path,
    profile: str,
    environment: dict[str, str],
    log_directory: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
    popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
) -> tuple[int, dict[str, object]]:
    stdout_path = log_directory / f"run-{ordinal}-stdout.log"
    stderr_path = log_directory / f"run-{ordinal}-stderr.log"
    prepare_captured_log(stdout_path)
    prepare_captured_log(stderr_path)
    captured_pids: list[int] = []

    def capture_popen(
        *args: object,
        **kwargs: object,
    ) -> subprocess.Popen[bytes]:
        process = popen_factory(*args, **kwargs)
        if type(process.pid) is not int or process.pid <= 0:
            raise engine.LifecycleSmokeError(
                "direct owned child returned an invalid process identifier"
            )
        captured_pids.append(process.pid)
        return process

    def wait_for_captured_process(
        process: subprocess.Popen[bytes],
        executable: Path,
        *,
        timeout_seconds: float,
    ) -> DirectOwnedApplicationStatus:
        if captured_pids != [process.pid]:
            raise engine.LifecycleSmokeError(
                "readiness process differs from the captured direct child"
            )
        return wait_for_direct_owned_readiness(
            process,
            executable,
            timeout_seconds=timeout_seconds,
        )

    def terminate_captured_process(
        pid: int,
        executable: Path,
        *,
        force: bool,
    ) -> bool:
        if captured_pids != [pid]:
            raise engine.LifecycleSmokeError(
                "termination PID differs from the captured direct child"
            )
        return request_direct_owned_termination(
            pid,
            executable,
            force=force,
        )

    run = lifecycle.run_one_lifecycle(
        ordinal=ordinal,
        executable=app_path / installed.EXECUTABLE_RELATIVE_PATH,
        profile=profile,
        environment=environment,
        working_directory=app_path.parent,
        log_directory=log_directory,
        readiness_timeout_seconds=readiness_timeout_seconds,
        observation_seconds=observation_seconds,
        termination_timeout_seconds=termination_timeout_seconds,
        popen_factory=capture_popen,
        readiness_waiter=wait_for_captured_process,
        request_termination=terminate_captured_process,
    )
    if len(captured_pids) != 1:
        raise engine.LifecycleSmokeError(
            "direct recovery launch did not capture exactly one owned child"
        )
    return captured_pids[0], {
        "activationPolicy": run.activation_policy,
        "appKitBundleIdentifierPolicy": APPKIT_BUNDLE_IDENTIFIER_POLICY,
        "appKitExecutablePathMatched": True,
        "exitCode": run.exit_code,
        "finishedLaunching": run.finished_launching,
        "minimumObservationSeconds": run.minimum_observation_seconds,
        "observationDeadlineReached": run.observation_deadline_reached,
        "ordinal": run.ordinal,
        "ownedChildProcessCaptured": True,
        "terminationAccepted": run.termination_accepted,
    }


def wait_for_direct_owned_absence(
    pid: int,
    executable: Path,
    *,
    timeout_seconds: float,
    query_payload: Callable[[int], dict[str, object]] = (
        query_direct_owned_application
    ),
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if direct_owned_application_status(
            pid,
            executable,
            query_payload=query_payload,
        ) is None:
            return True
        remaining = max(0.0, deadline - monotonic())
        sleeper(min(0.1, remaining))
    return (
        direct_owned_application_status(
            pid,
            executable,
            query_payload=query_payload,
        )
        is None
    )


def cleanup_owned_child(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
) -> None:
    failures: list[BaseException] = []
    interruption: KeyboardInterrupt | SystemExit | None = None

    def record_failure(error: BaseException) -> None:
        nonlocal interruption
        failures.append(error)
        if interruption is None and isinstance(
            error, (KeyboardInterrupt, SystemExit)
        ):
            interruption = error

    for _attempt in range(2):
        try:
            if process.poll() is not None:
                if interruption is not None:
                    raise interruption
                return
        except BaseException as error:
            record_failure(error)
        try:
            process.send_signal(signal.SIGKILL)
        except BaseException as error:
            record_failure(error)
        try:
            process.wait(timeout=timeout_seconds)
        except BaseException as error:
            record_failure(error)
        try:
            if process.poll() is not None:
                if interruption is not None:
                    raise interruption
                return
        except BaseException as error:
            record_failure(error)
    if interruption is not None:
        raise interruption
    raise engine.LifecycleSmokeError(
        "direct-owned abrupt child cleanup could not prove reap: "
        f"{[type(error).__name__ for error in failures]!r}"
    ) from (failures[-1] if failures else None)


def run_owned_abrupt_recovery_cycle(
    *,
    ordinal: int,
    app_path: Path,
    profile: str,
    environment: dict[str, str],
    log_directory: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
    persistence_probe: Callable[[], None],
    expected_executable_bytes: bytes,
    popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    readiness_waiter: Callable[..., DirectOwnedApplicationStatus] = (
        wait_for_direct_owned_readiness
    ),
    status_reader: Callable[
        [int, Path], DirectOwnedApplicationStatus | None
    ] = direct_owned_application_status,
    absence_waiter: Callable[..., bool] = wait_for_direct_owned_absence,
    held_code_identity_reader: Callable[[bytes], str] = (
        codesign_cdhash_for_executable_bytes
    ),
    running_code_identity_reader: Callable[[int], str] = (
        codesign_cdhash_for_running_pid
    ),
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[int, dict[str, object], dict[str, object], dict[str, object]]:
    if ordinal != 2:
        raise engine.LifecycleSmokeError(
            "current-unsealed abrupt cycle must use ordinal 2"
        )
    executable = app_path / installed.EXECUTABLE_RELATIVE_PATH
    stdout_path = log_directory / f"run-{ordinal}-stdout.log"
    stderr_path = log_directory / f"run-{ordinal}-stderr.log"
    prepare_captured_log(stdout_path)
    prepare_captured_log(stderr_path)
    process: subprocess.Popen[bytes] | None = None
    descriptor: int | None = None
    descriptor_identity: ExecutableDescriptorIdentity | None = None
    signal_was_evidence = False
    try:
        expected_code_identity = held_code_identity_reader(
            expected_executable_bytes
        )
        if not re.fullmatch(r"[0-9a-f]{40}", expected_code_identity):
            raise engine.LifecycleSmokeError(
                "held executable code identity is not an exact SHA-256 CDHash"
            )
        descriptor, descriptor_identity = open_held_installed_executable(
            executable,
            expected_bytes=expected_executable_bytes,
        )
        with (
            stdout_path.open("wb") as stdout_handle,
            stderr_path.open("wb") as stderr_handle,
        ):
            process = popen_factory(
                [
                    str(engine.SANDBOX_EXEC),
                    "-p",
                    profile,
                    str(executable),
                ],
                cwd=app_path.parent,
                env=environment,
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
            if type(process.pid) is not int or process.pid <= 0:
                raise engine.LifecycleSmokeError(
                    "direct-owned abrupt child returned an invalid PID"
                )
            status = readiness_waiter(
                process,
                executable,
                timeout_seconds=readiness_timeout_seconds,
            )
            if running_code_identity_reader(process.pid) != expected_code_identity:
                raise engine.LifecycleSmokeError(
                    "running executable code identity differs from held bytes"
                )
            deadline = monotonic() + observation_seconds
            while monotonic() < deadline:
                if process.poll() is not None:
                    raise engine.LifecycleSmokeError(
                        "direct-owned abrupt child exited before SIGKILL"
                    )
                remaining = max(0.0, deadline - monotonic())
                sleeper(min(0.1, remaining))

            observation = recovery.verify_observation_log(
                stdout_path,
                recovery.SQLITE_READBACK_MODE,
            )
            stderr_evidence = validate_captured_log(
                stderr_path,
                label="owned abrupt-process stderr",
            )
            if stderr_evidence != {"sha256": EMPTY_SHA256, "size": 0}:
                raise engine.LifecycleSmokeError(
                    "owned abrupt-process stderr must be exactly empty"
                )
            persistence_probe()
            if process.poll() is not None:
                raise engine.LifecycleSmokeError(
                    "direct-owned abrupt child exited before identity recheck"
                )
            require_held_installed_executable(
                descriptor,
                executable,
                expected=descriptor_identity,
                expected_bytes=expected_executable_bytes,
            )
            exact_status = status_reader(process.pid, executable)
            if (
                exact_status is None
                or not exact_status.finished_launching
                or exact_status.activation_policy != 0
                or exact_status.executable_path != status.executable_path
                or exact_status.bundle_identifier_state
                != status.bundle_identifier_state
            ):
                raise engine.LifecycleSmokeError(
                    "direct-owned abrupt child lost its exact ready identity"
                )
            if running_code_identity_reader(process.pid) != expected_code_identity:
                raise engine.LifecycleSmokeError(
                    "running executable code identity changed before SIGKILL"
                )
            process.send_signal(signal.SIGKILL)
            try:
                exit_code = process.wait(timeout=termination_timeout_seconds)
            except subprocess.TimeoutExpired as error:
                raise engine.LifecycleSmokeError(
                    "direct-owned abrupt child did not reap on time"
                ) from error
            if exit_code != -SIGKILL_NUMBER:
                raise engine.LifecycleSmokeError(
                    "direct-owned abrupt child exit did not prove SIGKILL"
                )
            if not absence_waiter(
                process.pid,
                executable,
                timeout_seconds=termination_timeout_seconds,
            ):
                raise engine.LifecycleSmokeError(
                    "direct-owned abrupt child remained registered in AppKit"
                )
            require_held_installed_executable(
                descriptor,
                executable,
                expected=descriptor_identity,
                expected_bytes=expected_executable_bytes,
            )
            stdout_handle.flush()
            stderr_handle.flush()
            post_reap_observation = recovery.verify_observation_log(
                stdout_path,
                recovery.SQLITE_READBACK_MODE,
            )
            post_reap_stderr_evidence = validate_captured_log(
                stderr_path,
                label="owned abrupt-process stderr after reap",
            )
            if (
                post_reap_observation != observation
                or post_reap_stderr_evidence != stderr_evidence
                or post_reap_stderr_evidence
                != {"sha256": EMPTY_SHA256, "size": 0}
            ):
                raise engine.LifecycleSmokeError(
                    "owned abrupt-process logs changed before reap completed"
                )
            signal_was_evidence = True
            return (
                process.pid,
                {
                    "activationPolicy": status.activation_policy,
                    "appKitBundleIdentifierPolicy": (
                        APPKIT_BUNDLE_IDENTIFIER_POLICY
                    ),
                    "appKitExecutablePathMatched": True,
                    "appKitProcessAbsentAfterReap": True,
                    "capturedLogsRevalidatedAfterReap": True,
                    (
                        "exactExecutableIdentityMatchedImmediatelyBeforeSignal"
                    ): True,
                    "exitCode": exit_code,
                    "finishedLaunching": status.finished_launching,
                    "installedExecutableDescriptorHeldAcrossSignal": True,
                    "launchMethod": ABRUPT_LAUNCH_METHOD,
                    "minimumObservationSeconds": observation_seconds,
                    "observationDeadlineReached": True,
                    "ordinal": ordinal,
                    "ownedChildProcessCaptured": True,
                    "pathIdentityStableAcrossSignal": True,
                    "persistenceProbePassedBeforeSignal": True,
                    "processReaped": True,
                    "runningExecutableCodeIdentityMatchedHeldBytes": True,
                    "signalName": "SIGKILL",
                    "signalNumber": SIGKILL_NUMBER,
                },
                post_reap_observation,
                post_reap_stderr_evidence,
            )
    finally:
        if process is not None and not signal_was_evidence:
            cleanup_owned_child(
                process,
                timeout_seconds=termination_timeout_seconds,
            )
        if descriptor is not None:
            os.close(descriptor)


def _require_exact_keys(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise engine.LifecycleSmokeError(f"{label} must be an object")
    if set(value) != keys:
        raise engine.LifecycleSmokeError(f"{label} keys differ")
    return value


def _require_bool(value: object, label: str, expected: bool | None = None) -> bool:
    if type(value) is not bool or (expected is not None and value is not expected):
        raise engine.LifecycleSmokeError(f"{label} must be an exact boolean")
    return value


def _require_int(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise engine.LifecycleSmokeError(f"{label} must be an exact integer")
    return value


def _require_signed_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise engine.LifecycleSmokeError(f"{label} must be an exact integer")
    return value


def _require_string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise engine.LifecycleSmokeError(f"{label} must be a non-empty string")
    return value


def _validate_sha(value: object, label: str) -> str:
    text = _require_string(value, label)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise engine.LifecycleSmokeError(f"{label} must be a SHA-256")
    return text


def _validate_tree_identity(value: object, label: str) -> None:
    identity = _require_exact_keys(value, {"fileCount", "sha256", "size"}, label)
    _require_int(identity["fileCount"], f"{label}.fileCount", minimum=1)
    _validate_sha(identity["sha256"], f"{label}.sha256")
    _require_int(identity["size"], f"{label}.size", minimum=1)


def _validate_receipt_identity(value: object, label: str) -> None:
    identity = _require_exact_keys(value, {"sha256", "size"}, label)
    _validate_sha(identity["sha256"], f"{label}.sha256")
    _require_int(identity["size"], f"{label}.size", minimum=1)


def validate_result_document(result: object) -> dict[str, object]:
    document = _require_exact_keys(
        result,
        {
            "abruptTermination",
            "app",
            "canary",
            "cleanup",
            "generation",
            "installation",
            "isolation",
            "lifecycle",
            "limitations",
            "qualification",
            "schemaVersion",
            "scope",
            "stateRecovery",
            "status",
        },
        "result",
    )
    if _require_int(document["schemaVersion"], "schemaVersion", minimum=1) != 1:
        raise engine.LifecycleSmokeError("result schemaVersion differs")
    if document["scope"] != RESULT_SCOPE or document["status"] != "passed":
        raise engine.LifecycleSmokeError("result scope or status differs")
    if document["limitations"] != list(LIMITATIONS):
        raise engine.LifecycleSmokeError("result limitations differ")
    qualification = _require_exact_keys(
        document["qualification"], set(QUALIFICATION), "qualification"
    )
    for key in QUALIFICATION:
        _require_bool(qualification[key], f"qualification.{key}", False)

    abrupt_termination = _require_exact_keys(
        document["abruptTermination"],
        {
            "appKitProcessAbsentAfterReap",
            "capturedLogsRevalidatedAfterReap",
            "exactExecutableRevalidatedBeforeSignal",
            "exitCode",
            "gracefulTerminationRequested",
            "inFlightWriteCheckpointObserved",
            "installedExecutableDescriptorHeldAcrossSignal",
            "launchMethod",
            "migrationCommittedBeforeAbruptLaunch",
            "observationCompletedBeforeSignal",
            "persistenceProbePassedBeforeSignal",
            "pathIdentityStableAcrossSignal",
            "processDisposition",
            "processReaped",
            "runningExecutableCodeIdentityMatchedHeldBytes",
            "signal",
            "signalNumber",
            "signalTargetPolicy",
        },
        "abruptTermination",
    )
    for key in (
        "appKitProcessAbsentAfterReap",
        "capturedLogsRevalidatedAfterReap",
        "exactExecutableRevalidatedBeforeSignal",
        "installedExecutableDescriptorHeldAcrossSignal",
        "migrationCommittedBeforeAbruptLaunch",
        "observationCompletedBeforeSignal",
        "persistenceProbePassedBeforeSignal",
        "pathIdentityStableAcrossSignal",
        "processReaped",
        "runningExecutableCodeIdentityMatchedHeldBytes",
    ):
        _require_bool(
            abrupt_termination[key], f"abruptTermination.{key}", True
        )
    for key in (
        "gracefulTerminationRequested",
        "inFlightWriteCheckpointObserved",
    ):
        _require_bool(
            abrupt_termination[key], f"abruptTermination.{key}", False
        )
    if (
        _require_signed_int(
            abrupt_termination["exitCode"], "abruptTermination.exitCode"
        )
        != -SIGKILL_NUMBER
        or abrupt_termination["launchMethod"] != ABRUPT_LAUNCH_METHOD
        or abrupt_termination["processDisposition"]
        != ABRUPT_PROCESS_DISPOSITION
        or abrupt_termination["signal"] != "SIGKILL"
        or abrupt_termination["signalTargetPolicy"] != SIGNAL_TARGET_POLICY
        or _require_int(
            abrupt_termination["signalNumber"],
            "abruptTermination.signalNumber",
            minimum=1,
        )
        != SIGKILL_NUMBER
    ):
        raise engine.LifecycleSmokeError(
            "abrupt termination contract differs"
        )

    app = _require_exact_keys(
        document["app"],
        {
            "architecture",
            "buildNumber",
            "bundleIdentifier",
            "marketingVersion",
            "minimumSystemVersion",
            "uuid",
        },
        "app",
    )
    _require_int(app["buildNumber"], "app.buildNumber", minimum=1)
    for key in (
        "architecture",
        "bundleIdentifier",
        "marketingVersion",
        "minimumSystemVersion",
        "uuid",
    ):
        _require_string(app[key], f"app.{key}")
    if (
        app["architecture"] != "arm64"
        or app["buildNumber"] != 24
        or app["bundleIdentifier"] != installed.EXPECTED_BUNDLE_ID
        or app["marketingVersion"] != "1.0.0"
        or app["minimumSystemVersion"] != "14.0"
        or re.fullmatch(
            r"[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}",
            app["uuid"],
        )
        is None
    ):
        raise engine.LifecycleSmokeError("app identity contract differs")

    generation = _require_exact_keys(
        document["generation"],
        {
            "app",
            "currentSourceBound",
            "dSYM",
            "independentReadbackStableAcrossExercise",
            "liveOutputMatchesPrivateSnapshotBeforeAndAfterExercise",
            "outerBundleSeal",
            "outputContract",
            "outputRelativePath",
            "source",
            "sourceReceipt",
        },
        "generation",
    )
    _validate_tree_identity(generation["app"], "generation.app")
    _validate_tree_identity(generation["dSYM"], "generation.dSYM")
    _validate_receipt_identity(
        generation["sourceReceipt"], "generation.sourceReceipt"
    )
    for key in (
        "currentSourceBound",
        "independentReadbackStableAcrossExercise",
        "liveOutputMatchesPrivateSnapshotBeforeAndAfterExercise",
    ):
        _require_bool(generation[key], f"generation.{key}", True)
    if (
        generation["outerBundleSeal"] != "absent"
        or generation["outputContract"] != reader.MACOS_UNSEALED_OUTPUT_CONTRACT
        or generation["outputRelativePath"] != OUTPUT_RELATIVE_PATH.as_posix()
    ):
        raise engine.LifecycleSmokeError("generation contract differs")
    source = _require_exact_keys(
        generation["source"], {"algorithm", "fileCount", "sha256"}, "source"
    )
    if (
        _require_string(source["algorithm"], "source.algorithm")
        != "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
    ):
        raise engine.LifecycleSmokeError("source algorithm differs")
    _require_int(source["fileCount"], "source.fileCount", minimum=1)
    _validate_sha(source["sha256"], "source.sha256")

    installation = _require_exact_keys(
        document["installation"],
        {
            "codesignVerified",
            "copyTool",
            "installedAppMatchesPrivateSnapshot",
            "installedRelativePath",
            "outerBundleSeal",
            "tree",
        },
        "installation",
    )
    _require_bool(installation["codesignVerified"], "codesignVerified", False)
    _require_bool(
        installation["installedAppMatchesPrivateSnapshot"],
        "installedAppMatchesPrivateSnapshot",
        True,
    )
    _validate_tree_identity(installation["tree"], "installation.tree")
    if (
        installation["copyTool"] != "ditto"
        or installation["installedRelativePath"] != "Applications/AetherLink.app"
        or installation["outerBundleSeal"] != "absent"
    ):
        raise engine.LifecycleSmokeError("installation contract differs")

    isolation = _require_exact_keys(
        document["isolation"],
        {
            "afInetBindDeniedByPreflight",
            "cleanHomeConfigured",
            "nonTemporaryWriteDeniedByPreflight",
            "preexistingAetherLinkApplicationsPreserved",
            "runtimeIdentityFileOverrideConfigured",
            "sandboxProfile",
            "sandboxed",
            "temporaryCFUserHomeConfigured",
        },
        "isolation",
    )
    for key in (
        "afInetBindDeniedByPreflight",
        "cleanHomeConfigured",
        "nonTemporaryWriteDeniedByPreflight",
        "preexistingAetherLinkApplicationsPreserved",
        "runtimeIdentityFileOverrideConfigured",
        "sandboxed",
        "temporaryCFUserHomeConfigured",
    ):
        _require_bool(isolation[key], f"isolation.{key}", True)
    if isolation["sandboxProfile"] != "allow-default-deny-network-and-non-temp-writes-v1":
        raise engine.LifecycleSmokeError("sandbox profile contract differs")

    launches = _require_exact_keys(
        document["lifecycle"],
        {"commandPolicy", "distinctProcessIdentifiers", "runs"},
        "lifecycle",
    )
    _require_bool(
        launches["distinctProcessIdentifiers"],
        "lifecycle.distinctProcessIdentifiers",
        True,
    )
    if launches["commandPolicy"] != COMMAND_POLICY:
        raise engine.LifecycleSmokeError("launch command policy differs")
    runs = launches["runs"]
    if type(runs) is not list or len(runs) != 3:
        raise engine.LifecycleSmokeError("lifecycle.runs must contain three runs")

    def validate_graceful_run(run: object, ordinal: int) -> None:
        row = _require_exact_keys(
            run,
            {
                "activationPolicy",
                "appKitBundleIdentifierPolicy",
                "appKitExecutablePathMatched",
                "exitCode",
                "finishedLaunching",
                "minimumObservationSeconds",
                "observationDeadlineReached",
                "ordinal",
                "ownedChildProcessCaptured",
                "terminationAccepted",
            },
            f"lifecycle.runs[{ordinal}]",
        )
        if _require_int(row["ordinal"], "run.ordinal", minimum=1) != ordinal:
            raise engine.LifecycleSmokeError("launch run ordinal differs")
        _require_int(row["activationPolicy"], "run.activationPolicy")
        if (
            row["appKitBundleIdentifierPolicy"]
            != APPKIT_BUNDLE_IDENTIFIER_POLICY
        ):
            raise engine.LifecycleSmokeError(
                "launch AppKit bundle identifier policy differs"
            )
        _require_bool(
            row["appKitExecutablePathMatched"],
            "run.appKitExecutablePathMatched",
            True,
        )
        if _require_int(row["exitCode"], "run.exitCode") != 0:
            raise engine.LifecycleSmokeError("launch run exitCode differs")
        if (
            type(row["minimumObservationSeconds"]) not in (int, float)
            or not math.isfinite(row["minimumObservationSeconds"])
            or row["minimumObservationSeconds"]
            < engine.MINIMUM_OBSERVATION_SECONDS
        ):
            raise engine.LifecycleSmokeError(
                "observation duration must be finite and bounded"
            )
        for key in (
            "finishedLaunching",
            "observationDeadlineReached",
            "ownedChildProcessCaptured",
            "terminationAccepted",
        ):
            _require_bool(row[key], f"run.{key}", True)

    validate_graceful_run(runs[0], 1)
    validate_graceful_run(runs[2], 3)
    abrupt_run = _require_exact_keys(
        runs[1],
        {
            "activationPolicy",
            "appKitBundleIdentifierPolicy",
            "appKitExecutablePathMatched",
            "appKitProcessAbsentAfterReap",
            "capturedLogsRevalidatedAfterReap",
            "exactExecutableIdentityMatchedImmediatelyBeforeSignal",
            "exitCode",
            "finishedLaunching",
            "installedExecutableDescriptorHeldAcrossSignal",
            "launchMethod",
            "minimumObservationSeconds",
            "observationDeadlineReached",
            "ordinal",
            "ownedChildProcessCaptured",
            "pathIdentityStableAcrossSignal",
            "persistenceProbePassedBeforeSignal",
            "processReaped",
            "runningExecutableCodeIdentityMatchedHeldBytes",
            "signalName",
            "signalNumber",
        },
        "lifecycle.runs[2]",
    )
    if (
        _require_int(abrupt_run["ordinal"], "abruptRun.ordinal", minimum=1)
        != 2
        or _require_int(
            abrupt_run["activationPolicy"], "abruptRun.activationPolicy"
        )
        != 0
        or abrupt_run["appKitBundleIdentifierPolicy"]
        != APPKIT_BUNDLE_IDENTIFIER_POLICY
        or _require_signed_int(
            abrupt_run["exitCode"], "abruptRun.exitCode"
        )
        != -SIGKILL_NUMBER
        or abrupt_run["launchMethod"] != ABRUPT_LAUNCH_METHOD
        or abrupt_run["signalName"] != "SIGKILL"
        or _require_int(
            abrupt_run["signalNumber"], "abruptRun.signalNumber", minimum=1
        )
        != SIGKILL_NUMBER
    ):
        raise engine.LifecycleSmokeError("abrupt launch record differs")
    if (
        type(abrupt_run["minimumObservationSeconds"]) not in (int, float)
        or not math.isfinite(abrupt_run["minimumObservationSeconds"])
        or abrupt_run["minimumObservationSeconds"]
        < engine.MINIMUM_OBSERVATION_SECONDS
    ):
        raise engine.LifecycleSmokeError(
            "abrupt observation duration must be finite and bounded"
        )
    for key in (
        "appKitExecutablePathMatched",
        "appKitProcessAbsentAfterReap",
        "capturedLogsRevalidatedAfterReap",
        "exactExecutableIdentityMatchedImmediatelyBeforeSignal",
        "finishedLaunching",
        "installedExecutableDescriptorHeldAcrossSignal",
        "observationDeadlineReached",
        "ownedChildProcessCaptured",
        "pathIdentityStableAcrossSignal",
        "persistenceProbePassedBeforeSignal",
        "processReaped",
        "runningExecutableCodeIdentityMatchedHeldBytes",
    ):
        _require_bool(abrupt_run[key], f"abruptRun.{key}", True)

    cleanup = _require_exact_keys(
        document["cleanup"],
        {
            "applicationSupportCleanupPerformed",
            "exactTemporaryAppPathOnly",
            "installedAppAbsentAfterFinalRemoval",
            "stateBytesAndModesUnchangedAfterAppRemoval",
            "temporaryRootRemoved",
        },
        "cleanup",
    )
    _require_bool(
        cleanup["applicationSupportCleanupPerformed"],
        "cleanup.applicationSupportCleanupPerformed",
        False,
    )
    for key in (
        "exactTemporaryAppPathOnly",
        "installedAppAbsentAfterFinalRemoval",
        "stateBytesAndModesUnchangedAfterAppRemoval",
        "temporaryRootRemoved",
    ):
        _require_bool(cleanup[key], f"cleanup.{key}", True)

    canary = _require_exact_keys(
        document["canary"],
        {
            "eventID",
            "eventJsonSha256",
            "eventJsonSize",
            "legacyJsonlSha256",
            "legacyJsonlSize",
            "model",
            "requestID",
            "sessionID",
        },
        "canary",
    )
    expected_canary = {
        "eventID": recovery.CANARY_EVENT_ID,
        "eventJsonSha256": recovery.CANARY_EVENT_JSON_SHA256,
        "eventJsonSize": len(recovery.CANARY_EVENT_JSON),
        "legacyJsonlSha256": recovery.CANARY_LEGACY_SHA256,
        "legacyJsonlSize": len(recovery.CANARY_LEGACY_BYTES),
        "model": recovery.CANARY_MODEL,
        "requestID": recovery.CANARY_REQUEST_ID,
        "sessionID": recovery.CANARY_SESSION_ID,
    }
    for key, expected in expected_canary.items():
        if type(canary[key]) is not type(expected) or canary[key] != expected:
            raise engine.LifecycleSmokeError(f"canary.{key} differs")
    state = _require_exact_keys(
        document["stateRecovery"],
        {
            "auxiliarySQLite",
            (
                "installedStateBytesAndModesUnchangedAcrossAbruptTermination"
                "AndRelaunch"
            ),
            "legacyAbsentBeforeAbruptAndRecoveryReadback",
            "legacyFixturePreservedUnchanged",
            "migrationObservation",
            "migrationSQLite",
            "ownedAbruptReadbackObservation",
            "ownedAbruptReadbackSQLite",
            "postAbruptSQLite",
            "recoveryReadbackObservation",
            "recoveryReadbackSQLite",
            "runtimeIdentityFilePresent",
            "sqliteCanaryUnchangedAcrossAbruptTerminationAndRelaunch",
            "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination",
            "stderr",
        },
        "stateRecovery",
    )
    for key in (
        "installedStateBytesAndModesUnchangedAcrossAbruptTerminationAndRelaunch",
        "legacyAbsentBeforeAbruptAndRecoveryReadback",
        "legacyFixturePreservedUnchanged",
        "sqliteCanaryUnchangedAcrossAbruptTerminationAndRelaunch",
        "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination",
    ):
        _require_bool(state[key], f"stateRecovery.{key}", True)
    _require_bool(
        state["runtimeIdentityFilePresent"],
        "stateRecovery.runtimeIdentityFilePresent",
        False,
    )
    auxiliary = state["auxiliarySQLite"]
    if type(auxiliary) is not list or len(auxiliary) != len(
        clean_recovery.AUXILIARY_SQLITE_FILES
    ):
        raise engine.LifecycleSmokeError("auxiliary SQLite evidence differs")
    for row_value, filename in zip(
        auxiliary, clean_recovery.AUXILIARY_SQLITE_FILES
    ):
        row = _require_exact_keys(
            row_value, {"filename", "integrityCheck"}, "auxiliary SQLite row"
        )
        if row != {"filename": filename, "integrityCheck": "ok"}:
            raise engine.LifecycleSmokeError("auxiliary SQLite row differs")

    def validate_observation(value: object, mode: str, label: str) -> None:
        row = _require_exact_keys(
            value, {"mode", "sha256", "size", "status"}, label
        )
        expected_bytes = recovery.expected_observation_line(mode)
        if (
            row["mode"] != mode
            or row["status"] != "passed"
            or row["sha256"] != hashlib.sha256(expected_bytes).hexdigest()
            or type(row["size"]) is not int
            or row["size"] != len(expected_bytes)
        ):
            raise engine.LifecycleSmokeError(f"{label} differs")

    validate_observation(
        state["migrationObservation"],
        recovery.MIGRATION_MODE,
        "migrationObservation",
    )
    validate_observation(
        state["ownedAbruptReadbackObservation"],
        recovery.SQLITE_READBACK_MODE,
        "ownedAbruptReadbackObservation",
    )
    validate_observation(
        state["recoveryReadbackObservation"],
        recovery.SQLITE_READBACK_MODE,
        "recoveryReadbackObservation",
    )

    def validate_canary_sqlite(value: object, label: str) -> None:
        row = _require_exact_keys(
            value,
            {"eventJsonSha256", "eventJsonSize", "integrityCheck", "totalEventCount"},
            label,
        )
        if (
            row["eventJsonSha256"] != recovery.CANARY_EVENT_JSON_SHA256
            or type(row["eventJsonSize"]) is not int
            or row["eventJsonSize"] != len(recovery.CANARY_EVENT_JSON)
            or row["integrityCheck"] != "ok"
            or type(row["totalEventCount"]) is not int
            or row["totalEventCount"] != 1
        ):
            raise engine.LifecycleSmokeError(f"{label} differs")

    for key in (
        "migrationSQLite",
        "ownedAbruptReadbackSQLite",
        "postAbruptSQLite",
        "recoveryReadbackSQLite",
    ):
        validate_canary_sqlite(state[key], key)
    stderr = _require_exact_keys(
        state["stderr"],
        {"abruptReadback", "migration", "recoveryReadback"},
        "stderr",
    )
    for key in ("abruptReadback", "migration", "recoveryReadback"):
        identity = _require_exact_keys(
            stderr[key], {"sha256", "size"}, f"stderr.{key}"
        )
        if (
            _validate_sha(identity["sha256"], f"stderr.{key}.sha256")
            != EMPTY_SHA256
            or _require_int(identity["size"], f"stderr.{key}.size") != 0
        ):
            raise engine.LifecycleSmokeError(
                f"stderr.{key} must be exactly empty"
            )

    def reject_sensitive(value: object) -> None:
        if type(value) is dict:
            for key, nested in value.items():
                if key in {"pid", "processId", "processIdentifier", "temporaryPath"}:
                    raise engine.LifecycleSmokeError(
                        "result must not retain a PID or temporary path"
                    )
                reject_sensitive(nested)
        elif type(value) is list:
            for nested in value:
                reject_sensitive(nested)
        elif type(value) is str and value.startswith("/"):
            raise engine.LifecycleSmokeError(
                "result must not retain an absolute temporary path"
            )

    reject_sensitive(document)
    return document


def validate_repeatability_receipt(receipt: object) -> dict[str, object]:
    document = _require_exact_keys(
        receipt,
        {
            "canonicalResult",
            "limitations",
            "qualification",
            "resultBytesEqual",
            "runCount",
            "runs",
            "schemaVersion",
            "scope",
            "status",
        },
        "repeatability receipt",
    )
    if (
        _require_int(document["schemaVersion"], "receipt.schemaVersion", minimum=1)
        != REPEATABILITY_SCHEMA_VERSION
        or document["scope"] != REPEATABILITY_SCOPE
        or document["status"] != "passed"
    ):
        raise engine.LifecycleSmokeError("repeatability receipt contract differs")
    _require_bool(document["resultBytesEqual"], "resultBytesEqual", True)
    if _require_int(document["runCount"], "runCount", minimum=1) != 2:
        raise engine.LifecycleSmokeError("repeatability runCount differs")
    if document["limitations"] != list(LIMITATIONS):
        raise engine.LifecycleSmokeError("repeatability limitations differ")
    qualification = _require_exact_keys(
        document["qualification"], set(QUALIFICATION), "receipt.qualification"
    )
    for key in QUALIFICATION:
        _require_bool(
            qualification[key], f"receipt.qualification.{key}", False
        )
    canonical = _require_exact_keys(
        document["canonicalResult"], {"fileName", "sha256", "size"}, "canonical"
    )
    _require_string(canonical["fileName"], "canonical.fileName")
    _validate_sha(canonical["sha256"], "canonical.sha256")
    _require_int(canonical["size"], "canonical.size", minimum=1)
    runs = document["runs"]
    if type(runs) is not list or len(runs) != 2:
        raise engine.LifecycleSmokeError("repeatability runs must contain two rows")
    for ordinal, row_value in enumerate(runs, start=1):
        row = _require_exact_keys(
            row_value, {"ordinal", "sha256", "size", "status"}, f"runs[{ordinal}]"
        )
        if (
            _require_int(row["ordinal"], "run.ordinal", minimum=1) != ordinal
            or row["status"] != "passed"
            or row["sha256"] != canonical["sha256"]
            or row["size"] != canonical["size"]
        ):
            raise engine.LifecycleSmokeError("repeatability run identity differs")
    return document


def execute_observation(
    *,
    output_root: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    readiness_timeout_seconds = engine.validated_duration(
        readiness_timeout_seconds, "readiness timeout", 0.1, 60.0
    )
    observation_seconds = engine.validated_duration(
        observation_seconds,
        "observation window",
        engine.MINIMUM_OBSERVATION_SECONDS,
        30.0,
    )
    termination_timeout_seconds = engine.validated_duration(
        termination_timeout_seconds, "termination timeout", 0.1, 30.0
    )
    output_root = Path(os.path.abspath(output_root))
    preexisting_applications = installed.list_bundle_applications()
    result: dict[str, object] | None = None
    temporary_root: Path | None = None

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-current-unsealed-recovery-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        live_before = read_generation(output_root)
        snapshot_root = temporary_root / "private-output-generation"
        copy_generation_with_ditto(output_root, snapshot_root)
        live_after_copy = read_generation(output_root)
        snapshot_before = read_generation(snapshot_root)
        require_same_generation(
            live_before, live_after_copy, label="live output after private snapshot"
        )
        require_same_generation(
            live_before, snapshot_before, label="private output snapshot"
        )
        readback_before = reader.verify_macos_release_build_outputs(
            root=ROOT,
            output_root=snapshot_root,
        )
        verify_readback_matches_generation(readback_before, snapshot_before)
        require_same_generation(
            snapshot_before,
            read_generation(snapshot_root),
            label="private snapshot after independent readback",
        )
        require_same_generation(
            live_before,
            read_generation(output_root),
            label="live output after independent readback",
        )

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        logs = temporary_root / "logs"
        for path in (isolated_home, isolated_temporary, isolated_state, logs):
            path.mkdir(mode=0o700)
        profile = sandbox_profile(temporary_root)
        sandbox_preflight(profile, temporary_root)
        installed_app = (
            isolated_home / "Applications" / installed.APP_RELATIVE_PATH
        )
        installed.install_app_with_ditto(
            snapshot_root / "AetherLink.app", installed_app
        )
        installed_files, installed_modes, installed_identity = (
            _read_unsealed_app_tree(installed_app)
        )
        if (
            installed_files != snapshot_before.app_files
            or installed_modes != snapshot_before.app_modes
            or installed_identity != snapshot_before.app_identity
        ):
            raise engine.LifecycleSmokeError(
                "installed app differs from the private output snapshot"
            )

        identity_file = isolated_state / "runtime-identity.json"
        application_support = (
            isolated_home / "Library/Application Support/AetherLink"
        )
        legacy_path = application_support / recovery.LEGACY_FILENAME
        database_path = application_support / recovery.DATABASE_FILENAME
        if (
            application_support.exists()
            or application_support.is_symlink()
            or identity_file.exists()
            or identity_file.is_symlink()
        ):
            raise engine.LifecycleSmokeError(
                "clean-HOME recovery state existed before fixture creation"
            )
        recovery.write_legacy_fixture(legacy_path)

        migration_environment = recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.MIGRATION_MODE,
        )
        first_stdout = logs / "run-1-stdout.log"
        first_stderr = logs / "run-1-stderr.log"
        first_pid, first_run = run_owned_recovery_cycle(
            ordinal=1,
            app_path=installed_app,
            profile=profile,
            environment=migration_environment,
            log_directory=logs,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        first_stderr_evidence = validate_captured_log(
            first_stderr, label="migration stderr"
        )
        first_observation = recovery.verify_observation_log(
            first_stdout, recovery.MIGRATION_MODE
        )
        first_sqlite = recovery.sqlite_canary_evidence(database_path)
        first_auxiliary = auxiliary_sqlite_evidence(application_support)
        first_app_read = _read_unsealed_app_tree(installed_app)

        preserved_legacy = recovery.remove_legacy_before_readback(
            legacy_path, temporary_root / "preserved-legacy"
        )
        first_state = installed.state_file_records(
            application_support, identity_file
        )
        readback_environment = recovery_launch_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
            mode=recovery.SQLITE_READBACK_MODE,
        )
        expected_app_read = (
            snapshot_before.app_files,
            snapshot_before.app_modes,
            snapshot_before.app_identity,
        )
        pre_signal_state: dict[str, installed.FileIdentity] | None = None
        pre_signal_sqlite: recovery.SQLiteCanaryEvidence | None = None

        def persistence_probe() -> None:
            nonlocal pre_signal_state, pre_signal_sqlite
            observed_sqlite = recovery.sqlite_canary_evidence(database_path)
            observed_auxiliary = auxiliary_sqlite_evidence(
                application_support
            )
            state_read_one = installed.state_file_records(
                application_support, identity_file
            )
            state_read_two = installed.state_file_records(
                application_support, identity_file
            )
            if (
                observed_sqlite != first_sqlite
                or observed_auxiliary != first_auxiliary
                or state_read_one != first_state
                or state_read_two != state_read_one
                or _read_unsealed_app_tree(installed_app) != expected_app_read
            ):
                raise engine.LifecycleSmokeError(
                    "persisted state was not quiescent before SIGKILL"
                )
            pre_signal_state = state_read_two
            pre_signal_sqlite = observed_sqlite

        (
            abrupt_pid,
            abrupt_run,
            abrupt_observation,
            abrupt_stderr_evidence,
        ) = run_owned_abrupt_recovery_cycle(
            ordinal=2,
            app_path=installed_app,
            profile=profile,
            environment=readback_environment,
            log_directory=logs,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
            persistence_probe=persistence_probe,
            expected_executable_bytes=snapshot_before.app_files[
                "Contents/MacOS/AetherLink"
            ],
        )
        if pre_signal_state is None or pre_signal_sqlite is None:
            raise engine.LifecycleSmokeError(
                "abrupt cycle did not capture the pre-signal persisted state"
            )
        if legacy_path.exists() or legacy_path.is_symlink():
            raise engine.LifecycleSmokeError(
                "legacy fixture reappeared during abrupt SQLite readback"
            )
        post_abrupt_sqlite = recovery.sqlite_canary_evidence(database_path)
        post_abrupt_auxiliary = auxiliary_sqlite_evidence(
            application_support
        )
        post_abrupt_state = installed.state_file_records(
            application_support, identity_file
        )
        if (
            post_abrupt_sqlite != pre_signal_sqlite
            or post_abrupt_auxiliary != first_auxiliary
            or post_abrupt_state != pre_signal_state
            or _read_unsealed_app_tree(installed_app) != expected_app_read
        ):
            raise engine.LifecycleSmokeError(
                "persisted state changed immediately after SIGKILL"
            )

        recovery_stdout = logs / "run-3-stdout.log"
        recovery_stderr = logs / "run-3-stderr.log"
        recovery_pid, recovery_run = run_owned_recovery_cycle(
            ordinal=3,
            app_path=installed_app,
            profile=profile,
            environment=readback_environment,
            log_directory=logs,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        if len({first_pid, abrupt_pid, recovery_pid}) != 3:
            raise engine.LifecycleSmokeError(
                "abrupt recovery did not use three distinct process identifiers"
            )
        recovery_stderr_evidence = validate_captured_log(
            recovery_stderr, label="recovery-readback stderr"
        )
        recovery_observation = recovery.verify_observation_log(
            recovery_stdout, recovery.SQLITE_READBACK_MODE
        )
        recovery_sqlite = recovery.sqlite_canary_evidence(database_path)
        recovery_auxiliary = auxiliary_sqlite_evidence(application_support)
        recovery_state = installed.state_file_records(
            application_support, identity_file
        )
        if (
            recovery_sqlite != first_sqlite
            or recovery_auxiliary != first_auxiliary
            or recovery_state != post_abrupt_state
            or _read_unsealed_app_tree(installed_app) != expected_app_read
        ):
            raise engine.LifecycleSmokeError(
                "persisted state changed during post-SIGKILL recovery readback"
            )
        if first_app_read != expected_app_read:
            raise engine.LifecycleSmokeError(
                "installed app differed from the private generation after migration"
            )
        if (
            preserved_legacy.read_bytes() != recovery.CANARY_LEGACY_BYTES
            or recovery.sha256_file(preserved_legacy)
            != recovery.CANARY_LEGACY_SHA256
        ):
            raise engine.LifecycleSmokeError(
                "preserved non-sensitive legacy fixture changed"
            )

        installed.assert_preexisting_applications_preserved(
            preexisting_applications
        )
        remove_exact_installed_app(
            temporary_root=temporary_root,
            isolated_home=isolated_home,
            app_path=installed_app,
            expected=snapshot_before,
        )
        state_after_removal = installed.state_file_records(
            application_support, identity_file
        )
        if state_after_removal != recovery_state:
            raise engine.LifecycleSmokeError(
                "runtime state bytes or modes changed after exact app removal"
            )
        installed.assert_preexisting_applications_preserved(
            preexisting_applications
        )

        snapshot_after = read_generation(snapshot_root)
        live_after = read_generation(output_root)
        require_same_generation(
            snapshot_before, snapshot_after, label="private snapshot after exercise"
        )
        require_same_generation(
            live_before, live_after, label="live output after exercise"
        )
        require_same_generation(
            live_after, snapshot_after, label="final live/private output cross-read"
        )
        readback_after = reader.verify_macos_release_build_outputs(
            root=ROOT,
            output_root=snapshot_root,
        )
        verify_readback_matches_generation(readback_after, snapshot_after)
        if readback_after != readback_before:
            raise engine.LifecycleSmokeError(
                "independent readback result changed across the exercise"
            )

        public_generation = snapshot_before.public_identity()
        result = {
            "abruptTermination": {
                "appKitProcessAbsentAfterReap": True,
                "capturedLogsRevalidatedAfterReap": True,
                "exactExecutableRevalidatedBeforeSignal": True,
                "exitCode": -SIGKILL_NUMBER,
                "gracefulTerminationRequested": False,
                "inFlightWriteCheckpointObserved": False,
                "installedExecutableDescriptorHeldAcrossSignal": True,
                "launchMethod": ABRUPT_LAUNCH_METHOD,
                "migrationCommittedBeforeAbruptLaunch": True,
                "observationCompletedBeforeSignal": True,
                "pathIdentityStableAcrossSignal": True,
                "persistenceProbePassedBeforeSignal": True,
                "processDisposition": ABRUPT_PROCESS_DISPOSITION,
                "processReaped": True,
                "runningExecutableCodeIdentityMatchedHeldBytes": True,
                "signal": "SIGKILL",
                "signalNumber": SIGKILL_NUMBER,
                "signalTargetPolicy": SIGNAL_TARGET_POLICY,
            },
            "app": {
                "architecture": readback_before["architecture"],
                "buildNumber": readback_before["buildNumber"],
                "bundleIdentifier": readback_before["bundleId"],
                "marketingVersion": readback_before["marketingVersion"],
                "minimumSystemVersion": readback_before["minimumSystemVersion"],
                "uuid": readback_before["uuid"],
            },
            "canary": {
                "eventID": recovery.CANARY_EVENT_ID,
                "eventJsonSha256": recovery.CANARY_EVENT_JSON_SHA256,
                "eventJsonSize": len(recovery.CANARY_EVENT_JSON),
                "legacyJsonlSha256": recovery.CANARY_LEGACY_SHA256,
                "legacyJsonlSize": len(recovery.CANARY_LEGACY_BYTES),
                "model": recovery.CANARY_MODEL,
                "requestID": recovery.CANARY_REQUEST_ID,
                "sessionID": recovery.CANARY_SESSION_ID,
            },
            "cleanup": {
                "applicationSupportCleanupPerformed": False,
                "exactTemporaryAppPathOnly": True,
                "installedAppAbsentAfterFinalRemoval": True,
                "stateBytesAndModesUnchangedAfterAppRemoval": True,
                "temporaryRootRemoved": False,
            },
            "generation": {
                "app": public_generation["app"],
                "currentSourceBound": True,
                "dSYM": public_generation["dSYM"],
                "independentReadbackStableAcrossExercise": True,
                "liveOutputMatchesPrivateSnapshotBeforeAndAfterExercise": True,
                "outerBundleSeal": "absent",
                "outputContract": reader.MACOS_UNSEALED_OUTPUT_CONTRACT,
                "outputRelativePath": OUTPUT_RELATIVE_PATH.as_posix(),
                "source": readback_before["source"],
                "sourceReceipt": public_generation["sourceReceipt"],
            },
            "installation": {
                "codesignVerified": False,
                "copyTool": "ditto",
                "installedAppMatchesPrivateSnapshot": True,
                "installedRelativePath": "Applications/AetherLink.app",
                "outerBundleSeal": "absent",
                "tree": public_generation["app"],
            },
            "isolation": {
                "afInetBindDeniedByPreflight": True,
                "cleanHomeConfigured": True,
                "nonTemporaryWriteDeniedByPreflight": True,
                "preexistingAetherLinkApplicationsPreserved": True,
                "runtimeIdentityFileOverrideConfigured": True,
                "sandboxProfile": (
                    "allow-default-deny-network-and-non-temp-writes-v1"
                ),
                "sandboxed": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "lifecycle": {
                "commandPolicy": COMMAND_POLICY,
                "distinctProcessIdentifiers": True,
                "runs": [first_run, abrupt_run, recovery_run],
            },
            "limitations": list(LIMITATIONS),
            "qualification": dict(QUALIFICATION),
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "scope": RESULT_SCOPE,
            "stateRecovery": {
                "auxiliarySQLite": list(first_auxiliary),
                (
                    "installedStateBytesAndModesUnchangedAcrossAbruptTermination"
                    "AndRelaunch"
                ): True,
                "legacyAbsentBeforeAbruptAndRecoveryReadback": True,
                "legacyFixturePreservedUnchanged": True,
                "migrationObservation": first_observation,
                "migrationSQLite": first_sqlite.record(),
                "ownedAbruptReadbackObservation": abrupt_observation,
                "ownedAbruptReadbackSQLite": pre_signal_sqlite.record(),
                "postAbruptSQLite": post_abrupt_sqlite.record(),
                "recoveryReadbackObservation": recovery_observation,
                "recoveryReadbackSQLite": recovery_sqlite.record(),
                "runtimeIdentityFilePresent": identity_file.is_file(),
                (
                    "sqliteCanaryUnchangedAcrossAbruptTerminationAndRelaunch"
                ): True,
                (
                    "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination"
                ): True,
                "stderr": {
                    "abruptReadback": abrupt_stderr_evidence,
                    "migration": first_stderr_evidence,
                    "recoveryReadback": recovery_stderr_evidence,
                },
            },
            "status": "passed",
        }

    if temporary_root is None or temporary_root.exists():
        raise engine.LifecycleSmokeError(
            "private temporary root remained after the observation"
        )
    if result is None:
        raise engine.LifecycleSmokeError("observation produced no result")
    cleanup = result["cleanup"]
    assert isinstance(cleanup, dict)
    cleanup["temporaryRootRemoved"] = True
    validate_result_document(result)
    return result


def execute_repeatability(
    *,
    output_root: Path,
    result_path: Path,
    repeatability_result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    output_root = require_canonical_output_root(output_root)
    require_output_paths_outside_generation(
        output_root, result_path, repeatability_result_path
    )
    results = [
        execute_observation(
            output_root=output_root,
            readiness_timeout_seconds=readiness_timeout_seconds,
            observation_seconds=observation_seconds,
            termination_timeout_seconds=termination_timeout_seconds,
        )
        for _ordinal in (1, 2)
    ]
    payloads = [engine.canonical_json_bytes(result) for result in results]
    if payloads[0] != payloads[1] or results[0] != results[1]:
        raise engine.LifecycleSmokeError(
            "two complete current-unsealed observations produced different results"
        )
    validate_result_document(results[0])
    canonical_identity = {
        "sha256": hashlib.sha256(payloads[0]).hexdigest(),
        "size": len(payloads[0]),
    }
    receipt = {
        "canonicalResult": {
            "fileName": result_path.name,
            **canonical_identity,
        },
        "limitations": list(LIMITATIONS),
        "qualification": dict(QUALIFICATION),
        "resultBytesEqual": True,
        "runCount": 2,
        "runs": [
            {
                "ordinal": ordinal,
                **canonical_identity,
                "status": "passed",
            }
            for ordinal in (1, 2)
        ],
        "schemaVersion": REPEATABILITY_SCHEMA_VERSION,
        "scope": REPEATABILITY_SCOPE,
        "status": "passed",
    }
    validate_repeatability_receipt(receipt)
    publication.publish_result_pair(
        result_path,
        payloads[0],
        repeatability_result_path,
        engine.canonical_json_bytes(receipt),
    )
    return receipt


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=default_result_path())
    parser.add_argument(
        "--repeatability-result",
        type=Path,
        default=default_repeatability_result_path(),
    )
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value, "readiness timeout", 0.1, 60
        ),
        default=20.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "observation window",
            engine.MINIMUM_OBSERVATION_SECONDS,
            30,
        ),
        default=engine.MINIMUM_OBSERVATION_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value, "termination timeout", 0.1, 30
        ),
        default=10.0,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        receipt = execute_repeatability(
            output_root=default_output_root(),
            result_path=arguments.result,
            repeatability_result_path=arguments.repeatability_result,
            readiness_timeout_seconds=arguments.readiness_timeout_seconds,
            observation_seconds=arguments.observation_seconds,
            termination_timeout_seconds=arguments.termination_timeout_seconds,
        )
    except KeyboardInterrupt:
        print(
            "macOS current-unsealed install recovery interrupted.",
            file=sys.stderr,
        )
        return 130
    except (
        engine.LifecycleSmokeError,
        reader.ReleaseArchiveVerificationError,
        OSError,
        sqlite3.Error,
    ) as error:
        print(
            f"macOS current-unsealed install recovery failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "macOS current-unsealed install recovery passed: "
        f"runs={receipt['runCount']}; byte-identical current-source "
        "install and SQLite recovery observations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
