#!/usr/bin/env python3
"""Record the pinned libnice 0.1.23 source intake and dependency evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
INTAKE_ROOT = ROOT / "build/offline-source/libnice-0.1.23"
ARCHIVE_PATH = INTAKE_ROOT / "original/libnice-0.1.23.tar.gz"
SIGNATURE_PATH = INTAKE_ROOT / "original/libnice-0.1.23.tar.gz.asc"
SOURCE_ROOT = INTAKE_ROOT / "source"
DEFAULT_MANIFEST_PATH = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/"
    "phase-a/libnice-source-manifest-v1.json"
)
DEFAULT_PROVENANCE_PATH = INTAKE_ROOT / "source-provenance.json"

EXPECTED_ARCHIVE_SHA256 = "618fc4e8de393b719b1641c1d8eec01826d4d39d15ade92679d221c7f5e4e70d"
EXPECTED_SIGNATURE_SHA256 = "44292ddf373bc7a962eb3949d4754987d7bbd50cb2d3a2effccb71a2d332727b"
EXPECTED_FILE_COUNT = 184
ARCHIVE_PREFIX = "libnice-0.1.23/"

LIBRARY_SOURCES = [
    "agent/address.c", "agent/agent.c", "agent/candidate.c", "agent/component.c",
    "agent/conncheck.c", "agent/debug.c", "agent/discovery.c", "agent/inputstream.c",
    "agent/interfaces.c", "agent/iostream.c", "agent/outputstream.c",
    "agent/pseudotcp.c", "agent/stream.c", "random/random.c",
    "random/random-glib.c", "socket/socket.c", "socket/udp-bsd.c",
    "socket/tcp-bsd.c", "socket/tcp-active.c", "socket/tcp-passive.c",
    "socket/pseudossl.c", "socket/socks5.c", "socket/http.c",
    "socket/udp-turn.c", "socket/udp-turn-over-tcp.c", "stun/stunagent.c",
    "stun/stunmessage.c", "stun/stun5389.c", "stun/stuncrc32.c",
    "stun/rand.c", "stun/stunhmac.c", "stun/utils.c", "stun/debug.c",
    "stun/usages/ice.c", "stun/usages/bind.c", "stun/usages/turn.c",
    "stun/usages/timer.c",
]

PUBLIC_HEADERS = [
    "agent/address.h", "agent/agent.h", "agent/candidate.h", "agent/debug.h",
    "agent/interfaces.h", "agent/pseudotcp.h", "nice/nice.h", "stun/constants.h",
    "stun/debug.h", "stun/stunagent.h", "stun/stunmessage.h",
    "stun/usages/bind.h", "stun/usages/ice.h", "stun/usages/timer.h",
    "stun/usages/turn.h", "stun/win32_common.h",
]


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


def source_file_records() -> list[dict[str, Any]]:
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
        raise ManifestError(f"expected {EXPECTED_FILE_COUNT} source files, found {len(records)}")
    return records


def archive_file_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    with tarfile.open(ARCHIVE_PATH, mode="r:gz") as archive:
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
    archive_hash = sha256_path(ARCHIVE_PATH)
    signature_hash = sha256_path(SIGNATURE_PATH)
    if archive_hash != EXPECTED_ARCHIVE_SHA256:
        raise ManifestError(f"libnice archive digest drifted: {archive_hash}")
    if signature_hash != EXPECTED_SIGNATURE_SHA256:
        raise ManifestError(f"libnice signature digest drifted: {signature_hash}")
    source_records = source_file_records()
    archived_records = archive_file_records()
    if archived_records != source_records:
        raise ManifestError("archive and extracted source records differ")
    source_paths = {record["path"] for record in source_records}
    required_paths = set(LIBRARY_SOURCES + PUBLIC_HEADERS)
    required_paths.update({
        "COPYING", "COPYING.LGPL", "COPYING.MPL", "meson.build", "meson_options.txt",
        "nice/libnice.sym", "nice/libnice.ver", "nice/gen-def.py", "nice/gen-map.py",
        "subprojects/glib.wrap", "subprojects/zlib.wrap",
    })
    missing = sorted(required_paths - source_paths)
    if missing:
        raise ManifestError(f"required source inventory is missing {missing}")
    tree_hash = digest_records(source_records)
    return {
        "documentType": "aetherlink.p2p-nat-libnice-source-manifest",
        "schemaVersion": 1,
        "manifestId": "production_p2p_nat_v1_libnice_source_manifest_v1",
        "recordedDate": "2026-07-17",
        "status": "complete_dependency_closure_partial",
        "profileId": "production_p2p_nat_v1_recommended",
        "candidate": {
            "candidateId": "libnice-0.1.23-glib-c-abi",
            "officialReleaseIndexUrl": "https://libnice.freedesktop.org/",
            "archiveUrl": "https://libnice.freedesktop.org/releases/libnice-0.1.23.tar.gz",
            "signatureUrl": "https://libnice.freedesktop.org/releases/libnice-0.1.23.tar.gz.asc",
            "releaseVersion": "0.1.23",
            "mesonDeclaredVersionEvidence": "meson.build:1-4",
        },
        "acquisition": {
            "authorityDecision": "../decision-v4.json",
            "authorityHandoff": "../../implementation/handoff-v7.json",
            "transport": "https_only_exact_host_no_redirect_no_environment_proxy",
            "requestCount": 2,
            "archive": {"path": "build/offline-source/libnice-0.1.23/original/libnice-0.1.23.tar.gz", "sizeBytes": ARCHIVE_PATH.stat().st_size, "sha256": archive_hash},
            "detachedSignature": {
                "path": "build/offline-source/libnice-0.1.23/original/libnice-0.1.23.tar.gz.asc",
                "sizeBytes": SIGNATURE_PATH.stat().st_size,
                "sha256": signature_hash,
                "formatInspection": "openpgp_signature_old_packet_format",
                "cryptographicVerificationStatus": "not_verified_no_local_openpgp_verifier_or_trusted_signing_key",
                "coLocatedOfficialTransportIsNotSignatureTrust": True,
            },
        },
        "extraction": {
            "path": "build/offline-source/libnice-0.1.23/source",
            "archiveRoot": "libnice-0.1.23",
            "regularFileCount": len(source_records),
            "totalRegularFileBytes": sum(record["sizeBytes"] for record in source_records),
            "symlinkCount": 0,
            "hardlinkCount": 0,
            "specialFileCount": 0,
            "pathTraversalCount": 0,
            "archiveMatchesExtractedFiles": True,
        },
        "sourceTree": {
            "digestAlgorithm": "sha256(path_utf8_nul_size_ascii_nul_file_sha256_ascii_lf)_sorted_by_path_utf8",
            "sha256": tree_hash,
            "files": source_records,
        },
        "licenseReview": {
            "result": "complete_dual_license_notice_recorded",
            "projectLicense": "LGPL-2.1-or-later OR MPL-1.1",
            "evidence": [
                {"path": "COPYING", "sha256": sha256_path(SOURCE_ROOT / "COPYING")},
                {"path": "COPYING.LGPL", "sha256": sha256_path(SOURCE_ROOT / "COPYING.LGPL")},
                {"path": "COPYING.MPL", "sha256": sha256_path(SOURCE_ROOT / "COPYING.MPL")},
            ],
            "staticLinkingComplianceDisposition": "requires_product_legal_review_before_distribution",
        },
        "buildInputReview": {
            "authoritativeMesonEvidence": ["meson.build:1-355", "agent/meson.build:1-47", "stun/meson.build:1-36", "socket/meson.build:1-16", "random/meson.build:1-16", "nice/meson.build:1-80"],
            "librarySources": LIBRARY_SOURCES,
            "publicHeaders": PUBLIC_HEADERS,
            "requiredGeneratedBuildInputs": [
                "config.h",
                "agent/agent-enum-types.c",
                "agent/agent-enum-types.h",
                "nice/libnice.map_or_platform_equivalent",
                "nice/libnice.def_on_windows_only",
                "nice/nice-version.h",
            ],
            "sourceProvidedGenerators": ["nice/gen-def.py", "nice/gen-map.py"],
            "minimumOptions": [
                "default_library=static", "crypto-library=openssl", "gstreamer=disabled",
                "gupnp=disabled", "tests=disabled", "examples=disabled",
                "gtk_doc=disabled", "introspection=disabled",
            ],
            "mesonExecutionAllowed": False,
            "generatorExecutionAllowed": False,
            "compilerInvocationAllowed": False,
            "staticLibraryArchiverInvocationAllowed": False,
        },
        "dependencyReview": {
            "result": "partial_exact_direct_dependencies_known_transitive_closure_pending",
            "directRequired": [
                {"name": "GLib", "components": ["gio-2.0", "gthread-2.0", "glib-2.0", "gmodule-2.0", "gobject-2.0"], "minimumVersion": "2.56", "evidence": "meson.build:25,206-220"},
                {"name": "OpenSSL_or_GnuTLS", "selectedMinimum": "OpenSSL", "versionConstraint": "not_declared_by_libnice", "evidence": "meson.build:222-285"},
            ],
            "pinnedGlibFallback": {
                "version": "2.64.2",
                "urlInUpstreamWrap": "https://ftp.gnome.org/pub/gnome/sources/glib/2.64/glib-2.64.2.tar.xz",
                "canonicalNoRedirectUrlForNextLock": "https://download.gnome.org/sources/glib/2.64/glib-2.64.2.tar.xz",
                "sha256": "9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277",
                "evidence": "subprojects/glib.wrap:1-5",
                "acquisitionStatus": "not_acquired",
            },
            "optionalDisabled": [
                {"name": "GStreamer base", "minimumVersion": "1.14.0", "evidence": "meson.build:28,288-293"},
                {"name": "GUPnP IGD", "minimumVersion": "0.2.5", "evidence": "meson.build:27,295-297"},
                {"name": "GObject introspection", "evidence": "meson.build:314,322-342"},
                {"name": "gtk-doc", "evidence": "meson.build:326-334"},
            ],
            "transitiveItemsToResolveAfterGlibIntake": ["libffi", "PCRE_or_PCRE2", "zlib", "iconv_gettext_policy", "platform_threads_and_dynamic_loader"],
            "outsideCurrentEffectiveAcquisitionScope": ["OpenSSL"],
            "dependencyAcquisitionNetworkIOPerformed": False,
        },
        "authorityBoundary": {
            "sourceAcquisitionNetworkIOPerformed": True,
            "sourceInspectionPerformed": True,
            "sourceExecutionPerformed": False,
            "compilerInvocationPerformed": False,
            "staticLibraryArchiverInvocationPerformed": False,
            "buildSystemExecutionPerformed": False,
            "sourceLinkedOrLoaded": False,
            "socketCreationPerformed": False,
            "runtimeOrHarnessNetworkIOPerformed": False,
            "phaseBPerformed": False,
            "productionPermissionOpened": False,
        },
    }


def encode_manifest(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


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
        print(f"verified retained libnice intake sha256={hashlib.sha256(data).hexdigest()}")
        return 0
    write_atomic(arguments.output, data)
    write_atomic(arguments.provenance_output, data)
    print(f"recorded libnice source manifest sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
