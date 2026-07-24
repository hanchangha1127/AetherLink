#!/usr/bin/env python3
"""Read back the completed G2 Pion rung-three review-v2 publication.

This checker is intentionally outside the pre-execution authority graph.  It
does not import or read the runner, permit checker, permit, retained archive, or
any tracked evidence document.  It opens only the exact review-v2 directory
components and five fixed publication names, follows no symlinks, enumerates no
directory, and writes nothing.
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
        raise RuntimeError("post-run v2 readback requires unoptimized `python3 -I -B -S`")


require_isolated_interpreter()

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY_PARTS = (
    "build",
    "offline-source",
    "pion-ice-v4.3.0",
    "review-v2",
)
OUTPUT_DIRECTORY = "/".join(OUTPUT_DIRECTORY_PARTS)
CLAIM_NAME = ".g2-pion-ice-v4.3.0-rung3-offline-review-v2.claim"
RESULT_NAME = "offline-source-review-result-v2.json"
MANIFEST_NAME = "offline-source-review-manifest-v2.json"
TEMP_RESULT_NAME = f".{RESULT_NAME}.tmp"
TEMP_MANIFEST_NAME = f".{MANIFEST_NAME}.tmp"
FIXED_READ_NAMES = (
    CLAIM_NAME,
    TEMP_RESULT_NAME,
    RESULT_NAME,
    TEMP_MANIFEST_NAME,
    MANIFEST_NAME,
)

BASE = "docs/security-hardening/production-p2p-nat-v1/g2-pion-restricted-fork-v1"
RUNG2 = f"{BASE}/rung-two"
RUNG3 = f"{BASE}/rung-three"
PERMIT_PATH = f"{RUNG3}/offline-source-review-execution-permit-v2.json"
RECEIPT_PATH = f"{RUNG2}/source-acquisition-receipt-v1.json"

EXPECTED_PERMIT_ID = (
    "g2-pion-ice-v4.3.0-offline-source-review-execution-permit-v2"
)
EXPECTED_PERMIT_RAW_SHA256 = (
    "7f125ecc7d6e6d0a597cb4cddecebf37eaad5e0a8f614d1019603b4e952f9a06"
)
EXPECTED_PERMIT_SEMANTIC_SHA256 = (
    "3164cbf4b25f75c9689ad47db50776ba4fbbe7c4b315dfa5bcfbbba01e5c0321"
)
EXPECTED_ARCHIVE_SHA256 = (
    "f95ef3ce2e0063c13925f478bf8d188833725b2f0a7ecb1e695dee8ab61ef63c"
)
EXPECTED_ARCHIVE_BYTES = 293_023
EXPECTED_ENTRY_COUNT = 129
EXPECTED_FILE_COUNT = 129
EXPECTED_TOTAL_UNCOMPRESSED_BYTES = 1_131_286
MODULE_PREFIX = "github.com/pion/ice/v4@v4.3.0/"
MAXIMUM_JSON_REPORT_BYTES = 2_097_152
MAXIMUM_TEXT_VALUE_BYTES = 16_384

EXPECTED_CREATOR_POLICY_SEMANTICS = (
    "creator_zero_regular_file_metadata_with_path_provenance_only_safe_for_"
    "fresh_private_in_memory_tool_instance_never_extraction"
)
PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)
RULE_IDS: Mapping[str, frozenset[str]] = {
    PATCH_UNITS[0]: frozenset({"egress-dial", "egress-listen", "candidate-io"}),
    PATCH_UNITS[1]: frozenset({"diagnostic-call", "credential-token"}),
    PATCH_UNITS[2]: frozenset({"callback", "channel", "event"}),
    PATCH_UNITS[3]: frozenset({"deadline", "shutdown", "time-bound"}),
    PATCH_UNITS[4]: frozenset({"transport-path", "network-type"}),
    PATCH_UNITS[5]: frozenset({"resolver", "turn-tls", "network-injection"}),
    PATCH_UNITS[6]: frozenset({"pre-auth", "promotion-state", "one-use"}),
}
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

HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX_EXTERNAL_ATTRIBUTES = re.compile(r"^[0-9a-f]{8}$")
OCTAL_MODE = re.compile(r"^[0-7]{6}$")
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
SAFE_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9._+@%=-]+$")
GO_MODULE_PATH = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?"
    r"(?:/[A-Za-z0-9](?:[A-Za-z0-9._~+-]*[A-Za-z0-9])?)+$"
)
GO_MODULE_VERSION = re.compile(
    r"^v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?(?:/go\.mod)?$"
)
GO_LANGUAGE_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,2}$")
GO_TOOLCHAIN = re.compile(r"^go[0-9]+(?:\.[0-9]+){1,2}(?:[-A-Za-z0-9.]+)?$")
GO_SUM_H1 = re.compile(r"^h1:[A-Za-z0-9+/]{43}=$")
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?<![A-Za-z0-9])bearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?<![A-Za-z0-9])gh[opsur]_[A-Za-z0-9]{20,}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])(?:sk|rk)-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{20,}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}(?![A-Za-z0-9])"),
    re.compile(
        r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\."
        r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])"
    ),
)


class CheckError(ValueError):
    """The fixed post-run publication failed closed validation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def exact_object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    require(type(value) is dict, f"{label} must be object")
    require(set(value) == keys, f"{label} exact keys mismatch")
    return value


def require_exact(value: Any, expected: Any, label: str) -> None:
    require(type(value) is type(expected), f"{label} type mismatch")
    require(value == expected, f"{label} mismatch")


def require_digest(value: Any, label: str) -> str:
    require(type(value) is str and HEX_SHA256.fullmatch(value) is not None,
            f"{label} must be lowercase SHA-256")
    return value


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


def strict_canonical_json(data: bytes, label: str) -> Any:
    require(data.endswith(b"\n") and not data.endswith(b"\n\n"),
            f"{label}: exactly one terminal LF required")
    require(b"\r" not in data, f"{label}: CR forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    try:
        parsed = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CheckError(f"{label}: non-finite value {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError(f"{label}: invalid strict JSON: {error}") from error
    reject_nonfinite(parsed, label)
    require(canonical_json_bytes(parsed) == data, f"{label}: non-canonical JSON bytes")
    return parsed


def reject_nonfinite(value: Any, label: str) -> None:
    if type(value) is float:
        require(math.isfinite(value), f"{label}: non-finite float")
    elif type(value) is list:
        for index, item in enumerate(value):
            reject_nonfinite(item, f"{label}[{index}]")
    elif type(value) is dict:
        for key, item in value.items():
            require(type(key) is str, f"{label}: non-string key")
            reject_nonfinite(item, f"{label}.{key}")


def validate_content_binding(document: Mapping[str, Any], scope: str, label: str) -> None:
    binding = exact_object(
        document.get("contentBinding"),
        {"algorithm", "canonicalization", "scope", "sha256"},
        f"{label}.contentBinding",
    )
    require_exact(binding["algorithm"], "sha256", f"{label}.contentBinding.algorithm")
    require_exact(
        binding["canonicalization"],
        "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        f"{label}.contentBinding.canonicalization",
    )
    require_exact(binding["scope"], scope, f"{label}.contentBinding.scope")
    payload = dict(document)
    payload.pop("contentBinding")
    require_exact(
        require_digest(binding["sha256"], f"{label}.contentBinding.sha256"),
        sha256_bytes(canonical_json_bytes(payload)),
        f"{label}.contentBinding.sha256",
    )


def require_safe_text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    require(type(value) is str, f"{label} must be string")
    require(allow_empty or bool(value), f"{label} must not be empty")
    require(len(value.encode("utf-8")) <= MAXIMUM_TEXT_VALUE_BYTES, f"{label} is too long")
    require("\x00" not in value and "\r" not in value and "\n" not in value,
            f"{label} contains control separators")
    require(
        not value.startswith(("/", "\\", "file://"))
        and WINDOWS_ABSOLUTE.match(value) is None,
        f"{label} records an absolute path",
    )
    require(
        not any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS),
        f"{label} resembles secret material",
    )
    return value


def safe_relative_path(value: Any, label: str) -> str:
    text = require_safe_text(value, label)
    require("\\" not in text, f"{label} uses backslash")
    path = PurePosixPath(text)
    require(
        not path.is_absolute()
        and path.parts
        and len(path.parts) <= 32
        and all(part not in ("", ".", "..") for part in path.parts)
        and all(
            len(part.encode("utf-8")) <= 255
            and SAFE_PATH_COMPONENT.fullmatch(part) is not None
            for part in path.parts
        )
        and len(text.encode("utf-8")) <= 1_024
        and path.as_posix() == text,
        f"{label} is not a normalized relative path",
    )
    return text


def classify_inventory_path(path: str) -> str:
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


def stable_metadata(identity: os.stat_result) -> tuple[int, ...]:
    return (
        identity.st_dev,
        identity.st_ino,
        identity.st_mode,
        identity.st_uid,
        identity.st_nlink,
        identity.st_size,
        identity.st_mtime_ns,
        identity.st_ctime_ns,
    )


def named_identity(identity: os.stat_result) -> tuple[int, ...]:
    return (
        identity.st_dev,
        identity.st_ino,
        identity.st_mode,
        identity.st_uid,
        identity.st_nlink,
        identity.st_size,
    )


class FixedOutputReader:
    """Component-wise no-follow reader for exactly five fixed output names."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _open_directory(self) -> int:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        require(nofollow != 0 and directory != 0, "nofollow directory opens required")
        flags = os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)
        try:
            current = os.open(os.fspath(self.root), flags)
        except OSError as error:
            raise CheckError(f"repository root safe open failed: {error}") from error
        try:
            root_metadata = os.fstat(current)
            require(stat.S_ISDIR(root_metadata.st_mode), "repository root is not directory")
            require(root_metadata.st_uid == os.geteuid(), "repository root owner mismatch")
            require(stat.S_IMODE(root_metadata.st_mode) & 0o022 == 0,
                    "repository root is group- or world-writable")
            for index, component in enumerate(OUTPUT_DIRECTORY_PARTS):
                try:
                    next_fd = os.open(component, flags, dir_fd=current)
                except OSError as error:
                    raise CheckError(
                        f"output component {component!r} safe open failed: {error}"
                    ) from error
                metadata = os.fstat(next_fd)
                require(stat.S_ISDIR(metadata.st_mode), f"{component!r} is not directory")
                require(metadata.st_uid == os.geteuid(), f"{component!r} owner mismatch")
                require(stat.S_IMODE(metadata.st_mode) & 0o022 == 0,
                        f"{component!r} is group- or world-writable")
                if index == len(OUTPUT_DIRECTORY_PARTS) - 1:
                    require(stat.S_IMODE(metadata.st_mode) == 0o700,
                            "review-v2 directory mode must be 0700")
                os.close(current)
                current = next_fd
            result = current
            current = -1
            return result
        finally:
            if current >= 0:
                os.close(current)

    @staticmethod
    def _read_file(directory_fd: int, name: str, expected_links: int) -> tuple[bytes, os.stat_result]:
        require(name in FIXED_READ_NAMES and PurePosixPath(name).name == name,
                f"unlisted output read forbidden: {name}")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = -1
        try:
            named_before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            descriptor = os.open(name, flags, dir_fd=directory_fd)
            before = os.fstat(descriptor)
            require(
                stat.S_ISREG(before.st_mode)
                and before.st_uid == os.geteuid()
                and stat.S_IMODE(before.st_mode) == 0o600
                and before.st_nlink == expected_links
                and 0 < before.st_size <= MAXIMUM_JSON_REPORT_BYTES,
                f"{name}: file metadata mismatch",
            )
            require(named_identity(named_before) == named_identity(before),
                    f"{name}: name/descriptor identity mismatch")
            remaining = before.st_size + 1
            chunks: list[bytes] = []
            while remaining:
                chunk = os.read(descriptor, min(65_536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
            named_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            require(
                len(raw) == before.st_size
                and stable_metadata(before) == stable_metadata(after)
                and named_identity(after) == named_identity(named_after),
                f"{name}: changed during stable descriptor read",
            )
            return raw, after
        except OSError as error:
            raise CheckError(f"{name}: safe read failed: {error}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def read_complete_publication(
        self,
    ) -> tuple[dict[str, bytes], dict[str, os.stat_result]]:
        directory_fd = self._open_directory()
        try:
            raw: dict[str, bytes] = {}
            metadata: dict[str, os.stat_result] = {}
            for name, links in (
                (CLAIM_NAME, 1),
                (TEMP_RESULT_NAME, 2),
                (RESULT_NAME, 2),
                (TEMP_MANIFEST_NAME, 2),
                (MANIFEST_NAME, 2),
            ):
                raw[name], metadata[name] = self._read_file(directory_fd, name, links)
        finally:
            os.close(directory_fd)
        for temporary, final in (
            (TEMP_RESULT_NAME, RESULT_NAME),
            (TEMP_MANIFEST_NAME, MANIFEST_NAME),
        ):
            require(
                metadata[temporary].st_dev == metadata[final].st_dev
                and metadata[temporary].st_ino == metadata[final].st_ino
                and raw[temporary] == raw[final],
                f"{temporary} and {final} are not the exact retained hard-link pair",
            )
        return raw, metadata


EXPECTED_CLAIM = {
    "automaticRetryAllowed": False,
    "claimType": "aetherlink.g2-pion-rung3-offline-review-v2-one-use-claim",
    "externalIdentityProofRequired": False,
    "permitRawSha256": EXPECTED_PERMIT_RAW_SHA256,
    "repositoryOwnerAuthenticationRequired": False,
    "rule": (
        "claim_persists_after_successful_exclusive_creation_even_if_"
        "module_load_archive_read_inspection_or_publication_fails"
    ),
    "schemaVersion": "2.0",
    "userActionRequired": False,
}


def validate_claim(raw: bytes) -> tuple[Mapping[str, Any], str]:
    claim = strict_canonical_json(raw, "claim")
    require_exact(claim, EXPECTED_CLAIM, "claim")
    return claim, sha256_bytes(raw)


def validate_creator_policy(
    value: Any, source_entries: Sequence[Mapping[str, Any]]
) -> None:
    policy = exact_object(
        value,
        {
            "policyVersion",
            "semantics",
            "msDosCreatorSystem",
            "unixCreatorSystem",
            "msDosRegularFileCount",
            "unixEntryCount",
            "acceptedDosExternalAttributes",
            "allowedDosAttributeMask",
            "syntheticReadOnlyRegularMode",
            "filesystemExtractionAllowed",
            "sourceExecutionAllowed",
            "perPathProvenanceRecordedInSourceInventory",
        },
        "result.creatorMetadataPolicy",
    )
    expected_fixed = {
        "policyVersion": "2.0",
        "semantics": EXPECTED_CREATOR_POLICY_SEMANTICS,
        "msDosCreatorSystem": 0,
        "unixCreatorSystem": 3,
        "allowedDosAttributeMask": "21",
        "syntheticReadOnlyRegularMode": "100444",
        "filesystemExtractionAllowed": False,
        "sourceExecutionAllowed": False,
        "perPathProvenanceRecordedInSourceInventory": True,
    }
    for key, expected in expected_fixed.items():
        require_exact(policy[key], expected, f"result.creatorMetadataPolicy.{key}")
    ms_dos_count = 0
    unix_count = 0
    observed_dos: set[int] = set()
    for index, entry in enumerate(source_entries):
        creator = entry["creatorSystem"]
        external = entry["externalAttributes"]
        mode_source = entry["modeSource"]
        effective = entry["effectiveUnixMode"]
        require(
            type(creator) is int
            and type(external) is str
            and HEX_EXTERNAL_ATTRIBUTES.fullmatch(external) is not None
            and type(mode_source) is str
            and type(effective) is str
            and OCTAL_MODE.fullmatch(effective) is not None,
            f"result.sourceInventory.entries[{index}] creator metadata shape mismatch",
        )
        external_value = int(external, 16)
        effective_value = int(effective, 8)
        dos_attributes = external_value & 0xFF
        if creator == 0:
            require(
                external_value >> 8 == 0
                and dos_attributes & ~0x21 == 0
                and mode_source == "synthetic_read_only_regular_mode"
                and effective_value == 0o100444,
                f"result.sourceInventory.entries[{index}] MS-DOS metadata unsafe",
            )
            ms_dos_count += 1
            observed_dos.add(dos_attributes)
        elif creator == 3:
            unix_mode = (external_value >> 16) & 0xFFFF
            require(
                mode_source == "archive_unix_mode"
                and effective_value == unix_mode
                and unix_mode & 0o170000 in {0, 0o100000}
                and unix_mode & 0o7000 == 0
                and unix_mode & 0o111 == 0
                and dos_attributes & (0x02 | 0x04 | 0x08 | 0x10) == 0,
                f"result.sourceInventory.entries[{index}] Unix metadata unsafe",
            )
            unix_count += 1
        else:
            raise CheckError(
                f"result.sourceInventory.entries[{index}] unsupported creator system"
            )
    require_exact(policy["msDosRegularFileCount"], ms_dos_count,
                  "result.creatorMetadataPolicy.msDosRegularFileCount")
    require_exact(policy["unixEntryCount"], unix_count,
                  "result.creatorMetadataPolicy.unixEntryCount")
    require_exact(
        policy["acceptedDosExternalAttributes"],
        [f"{value:02x}" for value in sorted(observed_dos)],
        "result.creatorMetadataPolicy.acceptedDosExternalAttributes",
    )


def validate_dependency_metadata(value: Any) -> None:
    metadata = exact_object(
        value, {"goMod", "goSum", "inventoryOnlyNoDependencyAcquisition"},
        "result.dependencyMetadata",
    )
    require_exact(metadata["inventoryOnlyNoDependencyAcquisition"], True,
                  "result.dependencyMetadata.inventoryOnlyNoDependencyAcquisition")
    go_mod = exact_object(
        metadata["goMod"], {"modulePath", "goVersion", "toolchain", "requires"},
        "result.dependencyMetadata.goMod",
    )
    require_exact(go_mod["modulePath"], "github.com/pion/ice/v4",
                  "result.dependencyMetadata.goMod.modulePath")
    for key in ("goVersion", "toolchain"):
        require(go_mod[key] is None or type(go_mod[key]) is str,
                f"result.dependencyMetadata.goMod.{key} invalid")
        if type(go_mod[key]) is str:
            require_safe_text(go_mod[key], f"result.dependencyMetadata.goMod.{key}")
    if type(go_mod["goVersion"]) is str:
        require(
            GO_LANGUAGE_VERSION.fullmatch(go_mod["goVersion"]) is not None,
            "result.dependencyMetadata.goMod.goVersion grammar mismatch",
        )
    if type(go_mod["toolchain"]) is str:
        require(
            GO_TOOLCHAIN.fullmatch(go_mod["toolchain"]) is not None,
            "result.dependencyMetadata.goMod.toolchain grammar mismatch",
        )
    requires = go_mod["requires"]
    require(type(requires) is list, "result.dependencyMetadata.goMod.requires must be list")
    seen_requires: set[tuple[str, str, bool]] = set()
    for index, row_value in enumerate(requires):
        row = exact_object(
            row_value, {"module", "version", "indirect"},
            f"result.dependencyMetadata.goMod.requires[{index}]",
        )
        module = require_safe_text(row["module"], f"goMod.requires[{index}].module")
        version = require_safe_text(row["version"], f"goMod.requires[{index}].version")
        require(GO_MODULE_PATH.fullmatch(module) is not None,
                f"goMod.requires[{index}].module grammar mismatch")
        require(
            GO_MODULE_VERSION.fullmatch(version) is not None
            and not version.endswith("/go.mod"),
            f"goMod.requires[{index}].version grammar mismatch",
        )
        require(type(row["indirect"]) is bool, f"goMod.requires[{index}].indirect invalid")
        item = (module, version, row["indirect"])
        require(item not in seen_requires, "goMod.requires contains duplicate")
        seen_requires.add(item)
    require(
        [(row["module"], row["version"], row["indirect"]) for row in requires]
        == sorted(seen_requires),
        "goMod.requires is not sorted",
    )
    go_sum = metadata["goSum"]
    if go_sum is None:
        return
    go_sum_object = exact_object(
        go_sum, {"recordCount", "records"}, "result.dependencyMetadata.goSum"
    )
    records = go_sum_object["records"]
    require(
        type(records) is list
        and type(go_sum_object["recordCount"]) is int
        and go_sum_object["recordCount"] == len(records),
            "goSum record count mismatch")
    seen_records: set[tuple[str, str, str]] = set()
    for index, row_value in enumerate(records):
        row = exact_object(
            row_value, {"module", "version", "h1"},
            f"result.dependencyMetadata.goSum.records[{index}]",
        )
        item = (
            require_safe_text(row["module"], f"goSum.records[{index}].module"),
            require_safe_text(row["version"], f"goSum.records[{index}].version"),
            require_safe_text(row["h1"], f"goSum.records[{index}].h1"),
        )
        require(GO_MODULE_PATH.fullmatch(item[0]) is not None,
                f"goSum.records[{index}].module grammar mismatch")
        require(GO_MODULE_VERSION.fullmatch(item[1]) is not None,
                f"goSum.records[{index}].version grammar mismatch")
        require(GO_SUM_H1.fullmatch(item[2]) is not None,
                f"goSum.records[{index}].h1 invalid")
        require(item not in seen_records, "goSum.records contains duplicate")
        seen_records.add(item)
    require(
        [(row["module"], row["version"], row["h1"]) for row in records]
        == sorted(seen_records),
        "goSum.records is not sorted",
    )


def validate_result(raw: bytes, claim_sha256: str) -> Mapping[str, Any]:
    result = exact_object(
        strict_canonical_json(raw, "result"),
        {
            "documentType", "schemaVersion", "reviewId", "recordedDate", "status",
            "result", "nextAction", "contentBinding", "permitBinding", "claimBinding",
            "archiveEvidence", "creatorMetadataPolicy", "sourceInventory",
            "dependencyMetadata", "licenseAndNoticeInventory",
            "patchUnitCandidateInventory", "profileVerificationUnits",
            "publicationCompletion", "operationCounters", "executionBoundary",
            "evidenceBoundary", "personalProjectBoundary",
        },
        "result",
    )
    fixed = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-result",
        "schemaVersion": "2.0",
        "reviewId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-v2",
        "recordedDate": "2026-07-23",
        "status": "rung3_v2_candidate_inventory_recorded_awaiting_completion_manifest",
        "result": "bounded_candidate_location_inventory_recorded_semantic_review_not_performed",
        "nextAction": "publish_bound_v2_completion_manifest",
    }
    for key, expected in fixed.items():
        require_exact(result[key], expected, f"result.{key}")
    validate_content_binding(result, "result_without_contentBinding", "result")

    permit = exact_object(
        result["permitBinding"],
        {"path", "permitId", "rawSha256", "semanticSha256", "consumed"},
        "result.permitBinding",
    )
    require_exact(permit["path"], PERMIT_PATH, "result.permitBinding.path")
    require_exact(permit["permitId"], EXPECTED_PERMIT_ID, "result.permitBinding.permitId")
    require_exact(permit["rawSha256"], EXPECTED_PERMIT_RAW_SHA256,
                  "result.permitBinding.rawSha256")
    require_exact(permit["semanticSha256"], EXPECTED_PERMIT_SEMANTIC_SHA256,
                  "result.permitBinding.semanticSha256")
    require_exact(permit["consumed"], True, "result.permitBinding.consumed")

    claim = exact_object(
        result["claimBinding"],
        {"path", "sha256", "retained", "automaticRetryAllowed"},
        "result.claimBinding",
    )
    require_exact(claim["path"], f"{OUTPUT_DIRECTORY}/{CLAIM_NAME}",
                  "result.claimBinding.path")
    require_exact(claim["sha256"], claim_sha256, "result.claimBinding.sha256")
    require_exact(claim["retained"], True, "result.claimBinding.retained")
    require_exact(claim["automaticRetryAllowed"], False,
                  "result.claimBinding.automaticRetryAllowed")

    archive = exact_object(
        result["archiveEvidence"],
        {
            "receiptPath", "absolutePathRecorded", "archiveEvidenceId", "bytes",
            "rawSha256", "mode", "linkCount", "entryCount", "fileCount",
            "totalUncompressedBytes", "modulePrefix",
            "readThroughOneStableNoFollowFileDescriptor", "filesystemExtracted",
        },
        "result.archiveEvidence",
    )
    archive_expected = {
        "receiptPath": RECEIPT_PATH,
        "absolutePathRecorded": False,
        "archiveEvidenceId": "G2R2E009",
        "bytes": EXPECTED_ARCHIVE_BYTES,
        "rawSha256": EXPECTED_ARCHIVE_SHA256,
        "mode": "0600",
        "linkCount": 1,
        "entryCount": EXPECTED_ENTRY_COUNT,
        "fileCount": EXPECTED_FILE_COUNT,
        "totalUncompressedBytes": EXPECTED_TOTAL_UNCOMPRESSED_BYTES,
        "modulePrefix": MODULE_PREFIX,
        "readThroughOneStableNoFollowFileDescriptor": True,
        "filesystemExtracted": False,
    }
    for key, expected in archive_expected.items():
        require_exact(archive[key], expected, f"result.archiveEvidence.{key}")

    inventory = exact_object(
        result["sourceInventory"],
        {"treeSha256", "entryCount", "sourceFilesObserved", "entries"},
        "result.sourceInventory",
    )
    require_digest(inventory["treeSha256"], "result.sourceInventory.treeSha256")
    require_exact(inventory["entryCount"], EXPECTED_ENTRY_COUNT,
                  "result.sourceInventory.entryCount")
    entries = inventory["entries"]
    require(type(entries) is list and len(entries) == EXPECTED_ENTRY_COUNT,
            "result.sourceInventory.entries count mismatch")
    paths: list[str] = []
    tree_rows: list[bytes] = []
    entry_by_path: dict[str, Mapping[str, Any]] = {}
    go_count = 0
    for index, row_value in enumerate(entries):
        row = exact_object(
            row_value,
            {
                "path", "bytes", "sha256", "category", "creatorSystem",
                "externalAttributes", "modeSource", "effectiveUnixMode",
            },
            f"result.sourceInventory.entries[{index}]",
        )
        path = safe_relative_path(row["path"], f"result.sourceInventory.entries[{index}].path")
        require(type(row["bytes"]) is int and row["bytes"] >= 0,
                f"result.sourceInventory.entries[{index}].bytes invalid")
        require_digest(row["sha256"], f"result.sourceInventory.entries[{index}].sha256")
        require(
            row["category"] in {
                "go_source", "go_module_metadata", "license_or_notice",
                "other_text", "other",
            },
            f"result.sourceInventory.entries[{index}].category invalid",
        )
        require_exact(
            row["category"],
            classify_inventory_path(path),
            f"result.sourceInventory.entries[{index}].category",
        )
        go_count += int(row["category"] == "go_source")
        paths.append(path)
        tree_rows.append(
            f"{path}\0{row['bytes']}\0{row['sha256']}\n".encode("utf-8")
        )
        entry_by_path[path] = row
    require(
        paths == sorted(paths, key=lambda path: path.encode("utf-8"))
        and len(set(paths)) == len(paths),
        "result.sourceInventory paths are not unique byte-sorted paths",
    )
    require_exact(inventory["sourceFilesObserved"], go_count,
                  "result.sourceInventory.sourceFilesObserved")
    require(go_count > 0, "result.sourceInventory has no Go source metadata")
    require_exact(
        sum(row["bytes"] for row in entries),
        EXPECTED_TOTAL_UNCOMPRESSED_BYTES,
        "result.sourceInventory total entry bytes",
    )
    require_exact(
        inventory["treeSha256"],
        sha256_bytes(b"".join(sorted(tree_rows))),
        "result.sourceInventory.treeSha256",
    )
    validate_creator_policy(result["creatorMetadataPolicy"], entries)
    source_paths = set(paths)

    validate_dependency_metadata(result["dependencyMetadata"])
    licenses = exact_object(
        result["licenseAndNoticeInventory"],
        {"meaning", "fileCount", "files"},
        "result.licenseAndNoticeInventory",
    )
    require_exact(licenses["meaning"], "inventory_only_not_legal_conclusion",
                  "result.licenseAndNoticeInventory.meaning")
    require(type(licenses["files"]) is list
            and type(licenses["fileCount"]) is int
            and licenses["fileCount"] == len(licenses["files"]),
            "result.licenseAndNoticeInventory count mismatch")
    license_paths: list[str] = []
    for index, row_value in enumerate(licenses["files"]):
        row = exact_object(
            row_value, {"path", "bytes", "sha256"},
            f"result.licenseAndNoticeInventory.files[{index}]",
        )
        path = safe_relative_path(row["path"], f"license files[{index}].path")
        require(path in source_paths, f"license files[{index}] absent from source inventory")
        require(
            entry_by_path[path]["category"] == "license_or_notice",
            f"license files[{index}] is not classified as license or notice",
        )
        require(type(row["bytes"]) is int and row["bytes"] >= 0,
                f"license files[{index}].bytes invalid")
        require_digest(row["sha256"], f"license files[{index}].sha256")
        require_exact(row["bytes"], entry_by_path[path]["bytes"],
                      f"license files[{index}].bytes")
        require_exact(row["sha256"], entry_by_path[path]["sha256"],
                      f"license files[{index}].sha256")
        license_paths.append(path)
    require(
        license_paths == sorted(license_paths, key=lambda path: path.encode("utf-8"))
        and len(set(license_paths)) == len(license_paths),
        "license paths are not unique byte-sorted paths",
    )
    require(
        set(license_paths)
        == {
            path
            for path, entry in entry_by_path.items()
            if entry["category"] == "license_or_notice"
        },
        "license inventory is not complete for all classified license or notice files",
    )

    candidate_rows = result["patchUnitCandidateInventory"]
    require(type(candidate_rows) is list and len(candidate_rows) == len(PATCH_UNITS),
            "result.patchUnitCandidateInventory count mismatch")
    for index, (row_value, patch_unit) in enumerate(zip(candidate_rows, PATCH_UNITS)):
        row = exact_object(
            row_value, {"patchUnit", "meaning", "hitCount", "hits"},
            f"result.patchUnitCandidateInventory[{index}]",
        )
        require_exact(row["patchUnit"], patch_unit, f"candidate[{index}].patchUnit")
        require_exact(
            row["meaning"],
            "lexical_candidate_locations_only_not_type_control_or_data_flow_proof",
            f"candidate[{index}].meaning",
        )
        require(type(row["hits"]) is list and len(row["hits"]) > 0
                and type(row["hitCount"]) is int
                and row["hitCount"] == len(row["hits"]),
                f"candidate[{index}] hit count mismatch")
        observed_hits: list[tuple[str, int, str]] = []
        for hit_index, hit_value in enumerate(row["hits"]):
            hit = exact_object(
                hit_value, {"path", "line", "ruleId"},
                f"candidate[{index}].hits[{hit_index}]",
            )
            path = safe_relative_path(hit["path"], f"candidate[{index}].hits[{hit_index}].path")
            require(path in source_paths, f"candidate[{index}] hit path absent from inventory")
            require(entry_by_path[path]["category"] == "go_source",
                    f"candidate[{index}] hit path is not Go source")
            require(type(hit["line"]) is int and hit["line"] > 0,
                    f"candidate[{index}] line invalid")
            require(hit["ruleId"] in RULE_IDS[patch_unit],
                    f"candidate[{index}] rule id invalid")
            observed_hits.append((path, hit["line"], hit["ruleId"]))
        require(observed_hits == sorted(set(observed_hits), key=lambda item: (
            item[0].encode("utf-8"), item[1], item[2])),
            f"candidate[{index}] hits are not unique and sorted")

    verification_rows = result["profileVerificationUnits"]
    require(type(verification_rows) is list
            and len(verification_rows) == len(VERIFICATION_IDS),
            "result.profileVerificationUnits count mismatch")
    for index, (row_value, verification_id) in enumerate(
        zip(verification_rows, VERIFICATION_IDS)
    ):
        row = exact_object(
            row_value, {"id", "relatedPatchUnits", "status", "meaning"},
            f"result.profileVerificationUnits[{index}]",
        )
        require_exact(row["id"], verification_id, f"verification[{index}].id")
        require_exact(row["relatedPatchUnits"], list(VERIFICATION_CROSSWALK[verification_id]),
                      f"verification[{index}].relatedPatchUnits")
        require_exact(
            row["status"],
            "candidate_location_crosswalk_recorded_required_check_not_executed",
            f"verification[{index}].status",
        )
        require_exact(
            row["meaning"],
            "candidate_location_crosswalk_only_not_semantic_review_or_required_check_evidence",
            f"verification[{index}].meaning",
        )

    completion = exact_object(
        result["publicationCompletion"],
        {"complete", "completionManifestRequired", "completionManifestPath", "meaning"},
        "result.publicationCompletion",
    )
    completion_expected = {
        "complete": False,
        "completionManifestRequired": True,
        "completionManifestPath": f"{OUTPUT_DIRECTORY}/{MANIFEST_NAME}",
        "meaning": "this_result_is_explicitly_incomplete_without_the_bound_v2_completion_manifest",
    }
    for key, expected in completion_expected.items():
        require_exact(completion[key], expected, f"result.publicationCompletion.{key}")

    counters = exact_object(
        result["operationCounters"],
        {
            "claimCreateCount", "archiveOpenCount", "archiveReadPassCount",
            "archiveEntryEnumerationCount", "reviewAdapterInvocationCount",
            "materializationCount", "sourceObservationCount", "sourceWriteCount",
            "sourceExecuteCount", "subprocessCount", "shellCount", "dnsCount",
            "networkOperationCount", "socketCreateCount", "gitOperationCount",
            "packageManagerInvocationCount", "reviewedSourceCompilerInvocationCount",
            "verifiedAuxiliaryToolModulePythonCompileCount", "deviceOperationCount",
        },
        "result.operationCounters",
    )
    expected_counters = {
        "claimCreateCount": 1,
        "archiveOpenCount": 1,
        "archiveReadPassCount": 1,
        "archiveEntryEnumerationCount": 1,
        "reviewAdapterInvocationCount": 1,
        "materializationCount": 0,
        "sourceObservationCount": go_count,
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
        "verifiedAuxiliaryToolModulePythonCompileCount": 3,
        "deviceOperationCount": 0,
    }
    for key, expected in expected_counters.items():
        require_exact(counters[key], expected, f"result.operationCounters.{key}")

    expected_execution_boundary = {
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
    }
    require_exact(result["executionBoundary"], expected_execution_boundary,
                  "result.executionBoundary")
    expected_evidence_boundary = {
        "evidenceClass": "bounded_offline_static_inventory_not_os_sandbox_attestation",
        "sourceBodiesRecorded": False,
        "absoluteArchivePathRecorded": False,
        "secretsOrCredentialsRecorded": False,
        "controlOrDataFlowProven": False,
        "typeCorrectnessProven": False,
        "coverageProven": False,
        "licenseConclusionMade": False,
        "reviewedSourceCompileOrRuntimeEvidencePresent": False,
    }
    require_exact(result["evidenceBoundary"], expected_evidence_boundary,
                  "result.evidenceBoundary")
    expected_personal_boundary = {
        "technicalSafetyGatesRemainRequired": True,
        "repositoryOwnerAuthenticationIsNotATechnicalGate": True,
        "noAuthenticationOrUserActionRequested": True,
    }
    require_exact(result["personalProjectBoundary"], expected_personal_boundary,
                  "result.personalProjectBoundary")
    assert_no_absolute_or_secret_values(result, "result")
    return result


def assert_no_absolute_or_secret_values(value: Any, label: str) -> None:
    if type(value) is str:
        require_safe_text(value, label, allow_empty=True)
    elif type(value) is list:
        for index, item in enumerate(value):
            assert_no_absolute_or_secret_values(item, f"{label}[{index}]")
    elif type(value) is dict:
        for key, item in value.items():
            assert_no_absolute_or_secret_values(item, f"{label}.{key}")


def validate_manifest(
    raw: bytes, result_raw: bytes, claim_sha256: str, result: Mapping[str, Any]
) -> Mapping[str, Any]:
    manifest = exact_object(
        strict_canonical_json(raw, "manifest"),
        {
            "documentType", "schemaVersion", "manifestId", "recordedDate", "status",
            "result", "nextAction", "contentBinding", "permitRawSha256",
            "claimSha256", "archiveRawSha256", "resultBinding", "artifacts",
            "publication", "executionBoundary",
        },
        "manifest",
    )
    fixed = {
        "documentType": "aetherlink.g2-pion-rung3-offline-source-review-runtime-manifest",
        "schemaVersion": "2.0",
        "manifestId": "g2-pion-ice-v4.3.0-rung3-offline-source-review-runtime-manifest-v2",
        "recordedDate": "2026-07-23",
        "status": "rung3_v2_candidate_location_inventory_committed_semantic_review_not_performed",
        "result": "bounded_v2_candidate_location_inventory_publication_committed_semantic_review_not_performed",
        "nextAction": "prepare_separate_versioned_rung3_semantic_source_review_decision",
        "permitRawSha256": EXPECTED_PERMIT_RAW_SHA256,
        "claimSha256": claim_sha256,
        "archiveRawSha256": EXPECTED_ARCHIVE_SHA256,
    }
    for key, expected in fixed.items():
        require_exact(manifest[key], expected, f"manifest.{key}")
    validate_content_binding(manifest, "manifest_without_contentBinding", "manifest")
    result_digest = sha256_bytes(result_raw)
    binding = exact_object(
        manifest["resultBinding"], {"path", "bytes", "rawSha256", "requiredStatus"},
        "manifest.resultBinding",
    )
    expected_binding = {
        "path": f"{OUTPUT_DIRECTORY}/{RESULT_NAME}",
        "bytes": len(result_raw),
        "rawSha256": result_digest,
        "requiredStatus": result["status"],
    }
    for key, expected in expected_binding.items():
        require_exact(binding[key], expected, f"manifest.resultBinding.{key}")
    require_exact(
        manifest["artifacts"],
        [{
            "path": f"{OUTPUT_DIRECTORY}/{RESULT_NAME}",
            "role": "bounded_offline_static_review_v2_result",
            "bytes": len(result_raw),
            "rawSha256": result_digest,
        }],
        "manifest.artifacts",
    )
    expected_publication = {
        "soleCompletionMarker": True,
        "boundResultPublicationComplete": True,
        "boundedCandidateLocationInventoryPerformed": True,
        "semanticSourceReviewPerformed": False,
        "rungThreeComplete": False,
        "ownerOnlyDirectoryMode": "0700",
        "fileMode": "0600",
        "atomicNoReplace": True,
        "directoryFsyncRequired": True,
        "temporaryBackingFilesRetained": True,
        "temporaryNameDeletionAllowed": False,
        "publishedFileLinkCount": 2,
        "runtimePublicationRequiresPostRunReadbackForCanonicalEvidence": True,
        "sameUidHostileConcurrentFilesystemMutationOutOfScope": True,
        "sourceMaterializationCount": 0,
    }
    require_exact(manifest["publication"], expected_publication, "manifest.publication")
    require_exact(
        manifest["executionBoundary"],
        {
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
            "productEndpointAuthenticationRequired": True,
        },
        "manifest.executionBoundary",
    )
    assert_no_absolute_or_secret_values(manifest, "manifest")
    return manifest


def check_post_run(root: Path = ROOT) -> dict[str, Any]:
    reader = FixedOutputReader(root)
    raw, _metadata = reader.read_complete_publication()
    _claim, claim_sha256 = validate_claim(raw[CLAIM_NAME])
    result = validate_result(raw[RESULT_NAME], claim_sha256)
    manifest = validate_manifest(
        raw[MANIFEST_NAME], raw[RESULT_NAME], claim_sha256, result
    )
    return {
        "documentType": "aetherlink.g2-pion-rung3-offline-review-v2-post-run-readback",
        "schemaVersion": "1.0",
        "status": "rung3_v2_publication_read_back_complete",
        "result": manifest["result"],
        "nextAction": manifest["nextAction"],
        "permitRawSha256": EXPECTED_PERMIT_RAW_SHA256,
        "claimRawSha256": claim_sha256,
        "resultRawSha256": sha256_bytes(raw[RESULT_NAME]),
        "manifestRawSha256": sha256_bytes(raw[MANIFEST_NAME]),
        "fixedNameReadCount": len(FIXED_READ_NAMES),
        "directoryEnumerationCount": 0,
        "archiveOpenCount": 0,
        "archiveReadPassCount": 0,
        "fileWriteCount": 0,
        "manifestWasValidatedLastAsSoleCompletionMarker": True,
        "externalIdentityProofRequired": False,
        "repositoryOwnerAuthenticationRequired": False,
        "userActionRequired": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    require_isolated_interpreter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = check_post_run(args.root.resolve())
    except CheckError as error:
        print(json.dumps({
            "documentType": "aetherlink.g2-pion-rung3-offline-review-v2-post-run-readback",
            "schemaVersion": "1.0",
            "status": "failed_closed",
            "reason": str(error),
            "automaticRetryAllowed": False,
            "externalIdentityProofRequired": False,
            "repositoryOwnerAuthenticationRequired": False,
            "userActionRequired": False,
        }, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
