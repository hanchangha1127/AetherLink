#!/usr/bin/env python3
"""Exact non-Unix ZIP creator policy for the G2 Pion in-memory review.

This bytes-only overlay is intentionally small.  It delegates all ZIP parsing,
path, collision, CRC, size, and decompression checks to the separately pinned
v1 validator and replaces only its central-entry creator/mode decision for the
duration of one synchronous call.
"""

from __future__ import annotations

import builtins
import hashlib
from types import ModuleType


class CreatorMetadataPolicyError(RuntimeError):
    """The exact creator metadata policy rejected an entry or integration."""


MS_DOS_CREATOR = 0
UNIX_CREATOR = 3
DOS_READ_ONLY = 0x01
DOS_ARCHIVE = 0x20
ALLOWED_MS_DOS_FILE_ATTRIBUTES = DOS_READ_ONLY | DOS_ARCHIVE
SYNTHETIC_READ_ONLY_REGULAR_MODE = 0o100444
POLICY_SEMANTICS = (
    "creator_zero_regular_file_metadata_with_path_provenance_only_safe_for_"
    "fresh_private_in_memory_tool_instance_never_extraction"
)
EXPECTED_BASE_VALIDATOR_RAW_SHA256 = (
    "9daef717b30337191ee9902110bdf4455babacb261acab9124d37de72fa8988b"
)
BASE_IMPORT_ALLOWLIST = frozenset(
    {
        "__future__",
        "collections",
        "collections.abc",
        "hashlib",
        "struct",
        "typing",
        "unicodedata",
        "zlib",
    }
)
BASE_BUILTIN_ALLOWLIST = frozenset(
    {
        "RuntimeError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "__build_class__",
        "any",
        "bool",
        "bytearray",
        "bytes",
        "dict",
        "enumerate",
        "int",
        "isinstance",
        "len",
        "list",
        "ord",
        "range",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
    }
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CreatorMetadataPolicyError(message)


def _load_private_base_validator(base_validator_source: bytes) -> ModuleType:
    """Compile exact pinned tool bytes into a call-local, unshared module."""

    _require(
        isinstance(base_validator_source, bytes),
        "base validator source must be immutable bytes",
    )
    _require(
        hashlib.sha256(base_validator_source).hexdigest()
        == EXPECTED_BASE_VALIDATOR_RAW_SHA256,
        "base validator source digest drifted",
    )
    _require(b"\x00" not in base_validator_source, "base validator source contains NUL")
    try:
        base_validator_source.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CreatorMetadataPolicyError(
            "base validator source is not strict UTF-8"
        ) from error

    original_import = builtins.__import__

    def guarded_import(name, globals_value=None, locals_value=None, fromlist=(), level=0):
        _require(level == 0, f"base validator relative import forbidden: {name}")
        _require(
            name in BASE_IMPORT_ALLOWLIST,
            f"base validator import outside allowlist: {name}",
        )
        return original_import(name, globals_value, locals_value, fromlist, level)

    safe_builtins = {
        name: getattr(builtins, name)
        for name in BASE_BUILTIN_ALLOWLIST
    }
    safe_builtins["__import__"] = guarded_import
    module = ModuleType("g2_pion_offline_zip_private_v2")
    module.__dict__.update(
        {
            "__builtins__": safe_builtins,
            "__cached__": None,
            "__file__": "script/p2p_nat_g2_pion_offline_zip.py",
            "__loader__": None,
            "__package__": None,
        }
    )
    try:
        code = compile(
            base_validator_source,
            "script/p2p_nat_g2_pion_offline_zip.py",
            "exec",
            flags=0,
            dont_inherit=True,
            optimize=0,
        )
        exec(code, module.__dict__, module.__dict__)
    except CreatorMetadataPolicyError:
        raise
    except BaseException as error:
        raise CreatorMetadataPolicyError(
            f"unable to load exact private base validator: {type(error).__name__}: {error}"
        ) from error
    _require(
        callable(getattr(module, "_validate_entry_mode", None))
        and callable(getattr(module, "inspect_module_zip", None)),
        "base validator interface drifted",
    )
    _require(
        getattr(module, "UNIX_CREATOR", None) == UNIX_CREATOR,
        "base validator Unix creator identity drifted",
    )
    return module


def inspect_module_zip(
    base_validator_source: bytes,
    raw_archive: bytes,
    *,
    module_prefix: str,
    limits=None,
):
    """Inspect through one fresh private validator that is never returned."""

    base_validator = _load_private_base_validator(base_validator_source)
    namespace = base_validator.__dict__
    original = base_validator._validate_entry_mode
    base_inspect = base_validator.inspect_module_zip
    counts = {"msDos": 0, "unix": 0}
    observed_dos_attributes = set()
    entry_metadata = []

    def record_entry(
        *,
        path: str,
        creator: int,
        external_attributes: int,
        mode_source: str,
        effective_mode: int,
    ) -> None:
        entry_metadata.append(
            {
                "path": path,
                "creatorSystem": creator,
                "externalAttributes": f"{external_attributes:08x}",
                "modeSource": mode_source,
                "effectiveUnixMode": f"{effective_mode:06o}",
            }
        )

    def validate_entry_mode(
        *,
        path: str,
        version_made_by: int,
        external_attributes: int,
        is_directory: bool,
    ) -> int:
        creator = (version_made_by >> 8) & 0xFF
        if creator == UNIX_CREATOR:
            mode = original(
                path=path,
                version_made_by=version_made_by,
                external_attributes=external_attributes,
                is_directory=is_directory,
            )
            counts["unix"] += 1
            record_entry(
                path=path,
                creator=creator,
                external_attributes=external_attributes,
                mode_source="archive_unix_mode",
                effective_mode=mode,
            )
            return mode
        _require(
            creator == MS_DOS_CREATOR,
            f"unsupported ZIP creator system for in-memory review: {path!r}",
        )
        _require(
            not is_directory,
            f"MS-DOS creator policy permits regular files only: {path!r}",
        )
        _require(
            external_attributes >> 8 == 0,
            f"MS-DOS creator entry carries non-DOS or hidden high attributes: {path!r}",
        )
        dos_attributes = external_attributes & 0xFF
        _require(
            dos_attributes & ~ALLOWED_MS_DOS_FILE_ATTRIBUTES == 0,
            f"MS-DOS creator entry carries forbidden attributes: {path!r}",
        )
        counts["msDos"] += 1
        observed_dos_attributes.add(dos_attributes)
        record_entry(
            path=path,
            creator=creator,
            external_attributes=external_attributes,
            mode_source="synthetic_read_only_regular_mode",
            effective_mode=SYNTHETIC_READ_ONLY_REGULAR_MODE,
        )
        return SYNTHETIC_READ_ONLY_REGULAR_MODE

    namespace["_validate_entry_mode"] = validate_entry_mode
    result = base_inspect(
        raw_archive,
        module_prefix=module_prefix,
        limits=limits,
    )
    _require(isinstance(result, dict), "base validator returned a non-object result")
    _require(
        counts["msDos"] + counts["unix"] == result.get("entryCount"),
        "creator-policy entry count differs from validated ZIP entry count",
    )
    entries = result.get("entries")
    _require(
        isinstance(entries, tuple),
        "base validator returned a non-deterministic entry collection",
    )
    result_paths = [entry.get("path") for entry in entries if isinstance(entry, dict)]
    metadata_paths = [row["path"] for row in entry_metadata]
    _require(
        len(result_paths) == len(entries)
        and len(set(metadata_paths)) == len(metadata_paths)
        and sorted(result_paths, key=lambda value: value.encode("utf-8"))
        == sorted(metadata_paths, key=lambda value: value.encode("utf-8")),
        "creator metadata does not map one-to-one to validated ZIP entries",
    )
    output = dict(result)
    output["creatorMetadataPolicy"] = {
        "policyVersion": "2.0",
        "semantics": POLICY_SEMANTICS,
        "msDosCreatorSystem": MS_DOS_CREATOR,
        "unixCreatorSystem": UNIX_CREATOR,
        "msDosRegularFileCount": counts["msDos"],
        "unixEntryCount": counts["unix"],
        "acceptedDosExternalAttributes": [
            f"{value:02x}" for value in sorted(observed_dos_attributes)
        ],
        "allowedDosAttributeMask": f"{ALLOWED_MS_DOS_FILE_ATTRIBUTES:02x}",
        "syntheticReadOnlyRegularMode": f"{SYNTHETIC_READ_ONLY_REGULAR_MODE:06o}",
        "entryMetadata": sorted(
            entry_metadata,
            key=lambda row: row["path"].encode("utf-8"),
        ),
        "filesystemExtractionAllowed": False,
        "sourceExecutionAllowed": False,
    }
    return output
