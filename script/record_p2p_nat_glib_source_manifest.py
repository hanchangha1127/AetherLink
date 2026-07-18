#!/usr/bin/env python3
"""Record the pinned GLib 2.64.2 source and transitive dependency evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
INTAKE_ROOT = ROOT / "build/offline-source/glib-2.64.2"
ARCHIVE_PATH = INTAKE_ROOT / "original/glib-2.64.2.tar.xz"
CHECKSUM_PATH = INTAKE_ROOT / "original/glib-2.64.2.sha256sum"
SOURCE_ROOT = INTAKE_ROOT / "source"
DEFAULT_MANIFEST_PATH = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/"
    "phase-a/glib-source-manifest-v1.json"
)
DEFAULT_PROVENANCE_PATH = INTAKE_ROOT / "source-provenance.json"

EXPECTED_ARCHIVE_SHA256 = "9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277"
EXPECTED_CHECKSUM_SHA256 = "b7835b3cee483dc22f80cb4e82ad3675aee08a0fc8f81f23257a2a7d10d8a5f9"
EXPECTED_CHECKSUM_TEXT = (
    "70c9f34020dabb5c025c875c0a6fbf79ca74d6ca244e14d3d06b1d606b3f830b  glib-2.64.2.news\n"
    "9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277  glib-2.64.2.tar.xz\n"
)
EXPECTED_FILE_COUNT = 1961
ARCHIVE_PREFIX = "glib-2.64.2/"


class ManifestError(ValueError):
    pass


def sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_path(path: Path) -> str:
    with path.open("rb") as stream:
        return sha256_stream(stream)


def safe_relative_path(raw: str, label: str) -> str:
    if not raw or "\\" in raw or "\x00" in raw:
        raise ManifestError(f"{label}: unsafe path")
    value = PurePosixPath(raw)
    if value.is_absolute() or any(part in ("", ".", "..") for part in value.parts):
        raise ManifestError(f"{label}: unsafe path")
    return value.as_posix()


def file_records_from_source() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(SOURCE_ROOT.rglob("*")):
        relative = safe_relative_path(path.relative_to(SOURCE_ROOT).as_posix(), "source")
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ManifestError(f"source/{relative}: non-regular file")
        records.append({"path": relative, "sizeBytes": metadata.st_size, "sha256": sha256_path(path)})
    records.sort(key=lambda value: value["path"].encode("utf-8"))
    if len(records) != EXPECTED_FILE_COUNT:
        raise ManifestError(f"expected {EXPECTED_FILE_COUNT} files, found {len(records)}")
    return records


def file_records_from_archive() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    with tarfile.open(ARCHIVE_PATH, mode="r:xz") as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            if not member.isfile():
                raise ManifestError(f"archive member {member.name!r} is not regular")
            name = safe_relative_path(member.name, "archive")
            if not name.startswith(ARCHIVE_PREFIX):
                raise ManifestError(f"archive member {name!r} has unexpected root")
            relative = safe_relative_path(name[len(ARCHIVE_PREFIX):], "archive member")
            if relative in seen:
                raise ManifestError(f"duplicate archive member {relative!r}")
            seen.add(relative)
            stream = archive.extractfile(member)
            if stream is None:
                raise ManifestError(f"archive member {name!r} is unreadable")
            with stream:
                digest = sha256_stream(stream)
            records.append({"path": relative, "sizeBytes": member.size, "sha256": digest})
    records.sort(key=lambda value: value["path"].encode("utf-8"))
    return records


def digest_records(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["sizeBytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(record["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_manifest() -> dict[str, Any]:
    if sha256_path(ARCHIVE_PATH) != EXPECTED_ARCHIVE_SHA256:
        raise ManifestError("GLib archive digest drifted")
    if sha256_path(CHECKSUM_PATH) != EXPECTED_CHECKSUM_SHA256:
        raise ManifestError("GLib checksum-file digest drifted")
    if CHECKSUM_PATH.read_text(encoding="ascii") != EXPECTED_CHECKSUM_TEXT:
        raise ManifestError("official GLib checksum content drifted")
    source_records = file_records_from_source()
    if file_records_from_archive() != source_records:
        raise ManifestError("archive and extracted GLib source differ")
    source_paths = {record["path"] for record in source_records}
    required = {
        "COPYING", "meson.build", "meson_options.txt", "glib/meson.build",
        "glib/pcre/COPYING", "gobject/meson.build", "gmodule/meson.build",
        "gthread/meson.build", "gio/meson.build", "subprojects/libffi.wrap",
        "subprojects/proxy-libintl.wrap", "subprojects/zlib.wrap",
    }
    missing = sorted(required - source_paths)
    if missing:
        raise ManifestError(f"required GLib evidence missing: {missing}")
    tree_hash = digest_records(source_records)
    return {
        "documentType": "aetherlink.p2p-nat-glib-source-manifest",
        "schemaVersion": 1,
        "manifestId": "production_p2p_nat_v1_glib_source_manifest_v1",
        "profileId": "production_p2p_nat_v1_recommended",
        "recordedDate": "2026-07-17",
        "status": "complete_transitive_source_scope_expansion_required",
        "dependency": {
            "name": "GLib",
            "version": "2.64.2",
            "officialIndexUrl": "https://download.gnome.org/sources/glib/2.64/",
            "archiveUrl": "https://download.gnome.org/sources/glib/2.64/glib-2.64.2.tar.xz",
            "checksumUrl": "https://download.gnome.org/sources/glib/2.64/glib-2.64.2.sha256sum",
            "versionEvidence": "meson.build:1-9",
        },
        "acquisition": {
            "authorityDecision": "../decision-v5.json",
            "authorityHandoff": "../../implementation/handoff-v8.json",
            "transport": "https_only_exact_host_no_redirect_no_environment_proxy",
            "requestCount": 2,
            "officialChecksum": {"sizeBytes": CHECKSUM_PATH.stat().st_size, "sha256": EXPECTED_CHECKSUM_SHA256, "archiveEntryVerified": True},
            "archive": {"sizeBytes": ARCHIVE_PATH.stat().st_size, "sha256": EXPECTED_ARCHIVE_SHA256},
        },
        "extraction": {
            "regularFileCount": len(source_records),
            "totalRegularFileBytes": sum(record["sizeBytes"] for record in source_records),
            "treeSha256": tree_hash,
            "archiveMatchesExtractedFiles": True,
            "symlinkCount": 0,
            "hardlinkCount": 0,
            "specialFileCount": 0,
            "pathTraversalCount": 0,
        },
        "sourceTree": {
            "digestAlgorithm": "sha256(path_utf8_nul_size_ascii_nul_file_sha256_ascii_lf)_sorted_by_path_utf8",
            "sha256": tree_hash,
            "files": source_records,
        },
        "licenseReview": {
            "projectLicense": "LGPL-2.1-or-later",
            "projectLicensePath": "COPYING",
            "projectLicenseSha256": sha256_path(SOURCE_ROOT / "COPYING"),
            "bundledInternalPcreLicensePath": "glib/pcre/COPYING",
            "bundledInternalPcreLicenseSha256": sha256_path(SOURCE_ROOT / "glib/pcre/COPYING"),
            "staticLinkingComplianceDisposition": "requires_product_legal_review_before_distribution",
        },
        "targetPolicy": {
            "includedComponents": ["glib-2.0", "gobject-2.0", "gmodule-2.0", "gthread-2.0", "gio-2.0"],
            "minimumOptions": [
                "default_library=static", "internal_pcre=true", "libmount=disabled",
                "selinux=disabled", "xattr=false", "nls=disabled", "fam=false",
                "installed_tests=false", "gtk_doc=false", "man=false", "dtrace=false",
                "systemtap=false",
            ],
            "androidIconvPolicy": "external_required_because_NDK_iconv_is_API_28_and_target_is_minSdk26",
            "macosIconvPolicy": "system_libiconv_from_pinned_SDK",
            "zlibPolicy": "pinned_Android_NDK_or_macos_SDK_system_library_no_additional_source",
            "internalPcrePolicy": "bundled_source_selected_no_additional_acquisition",
        },
        "transitiveDependencyReview": {
            "requiredExternalSource": [
                {"name": "libffi", "constraint": ">= 3.0.0", "reason": "mandatory GObject dependency", "evidence": "meson.build:1883-1885", "upstreamWrapProblem": "unpinned_git_revision_meson"},
                {"name": "GNU libiconv or reviewed equivalent", "constraint": "Android API 26 compatible", "reason": "NDK iconv introduced at API 28", "evidence": "meson.build:1812-1838 plus NDK r28c iconv.h"},
                {"name": "proxy-libintl", "constraint": "upstream wrap revision 0.1", "reason": "Android libc lacks ngettext and GLib requires gettext symbols", "evidence": "meson.build:1903-1925 and subprojects/proxy-libintl.wrap"},
            ],
            "bundled": [
                {"name": "PCRE", "selection": "internal_pcre=true", "evidence": "meson_options.txt:37-40 and glib/pcre"}
            ],
            "pinnedPlatformInputs": [
                {"name": "zlib", "android": "NDK r28c libz", "macos": "MacOSX SDK libz", "evidence": "meson.build:1886-1901"},
                {"name": "threads_dynamic_loader_math_and_xattr", "source": "pinned platform SDKs"}
            ],
            "disabledOptional": ["libmount", "SELinux", "FAM", "gtk-doc", "DTrace", "SystemTap", "installed tests", "NLS catalogs"],
            "scopeExpansionRequiredFor": ["libffi", "libiconv", "proxy-libintl", "OpenSSL"],
        },
        "generatedAndConfigureInputs": {
            "pythonMinimum": "3.5",
            "pythonEvidence": "meson.build:2061-2069",
            "sourceGeneratorsPresent": True,
            "nativeConfigureCanExecuteProbePrograms": True,
            "nativeProbeEvidence": ["meson.build:15", "meson.build:1803-1808", "meson.build:2052-2057"],
            "compileOnlyPolicy": "both_android_and_macos_must_use_no_exe_wrapper_cross_configuration_with_reviewed_cross_properties",
            "generatorOrProbeExecutionAuthorized": False,
            "buildSystemExecutionAuthorized": False,
            "compilerInvocationAuthorized": False,
        },
        "authorityBoundary": {
            "sourceAcquisitionNetworkIOPerformed": True,
            "sourceInspectionPerformed": True,
            "sourceOrGeneratorExecutionPerformed": False,
            "compilerInvocationPerformed": False,
            "staticLibraryArchiverInvocationPerformed": False,
            "buildSystemExecutionPerformed": False,
            "socketCreationPerformed": False,
            "runtimeOrHarnessNetworkIOPerformed": False,
            "phaseBPerformed": False,
            "productionPermissionOpened": False,
        },
    }


def encode_manifest(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--provenance-output", type=Path, default=DEFAULT_PROVENANCE_PATH)
    parser.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    data = encode_manifest(build_manifest())
    if arguments.verify:
        for path, label in ((arguments.output, "committed manifest"), (arguments.provenance_output, "local provenance twin")):
            if path.read_bytes() != data:
                raise ManifestError(f"{label} differs from retained evidence: {path}")
        print(f"verified retained GLib intake sha256={hashlib.sha256(data).hexdigest()}")
        return 0
    write_atomic(arguments.output, data)
    write_atomic(arguments.provenance_output, data)
    print(f"recorded GLib source manifest sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
