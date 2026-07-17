#!/usr/bin/env python3
"""Record the approved, read-only libjuice and toolchain intake evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
INTAKE_ROOT = ROOT / "build/offline-source/libjuice-1.7.2"
ARCHIVE_PATH = INTAKE_ROOT / "original/libjuice-1.7.2.tar.gz"
SOURCE_ROOT = INTAKE_ROOT / "source"
NDK_ARCHIVE_PATH = ROOT / "build/toolchain-intake/android-ndk-r28c-darwin.zip"
NDK_ROOT = Path.home() / "Library/Android/sdk/ndk/28.2.13676358"
DEFAULT_MANIFEST_PATH = ROOT / (
    "docs/security-hardening/production-p2p-nat-v1/controlled-network-spike/"
    "phase-a/libjuice-source-manifest-v1.json"
)
DEFAULT_PROVENANCE_PATH = INTAKE_ROOT / "source-provenance.json"

EXPECTED_ARCHIVE_SHA256 = (
    "75159867c4a5a689a6559e11aa0d30c9eba12ce73a4ae3d898b521467e1f635d"
)
EXPECTED_NDK_ARCHIVE_SHA256 = (
    "0d4599e8bbf1a1668a0d51a541729b2246360f350018a2081d0b302dbb594f2a"
)
TAG_OBJECT_SHA1 = "0f823d8210ea9dfe62a1c248da2b3219f6d8568d"
COMMIT_SHA1 = "3c40a3545b6b1b62c7adee7f8f2bd58aa290afd6"

LIBRARY_SOURCES = [
    "src/addr.c",
    "src/agent.c",
    "src/crc32.c",
    "src/const_time.c",
    "src/conn.c",
    "src/conn_poll.c",
    "src/conn_thread.c",
    "src/conn_mux.c",
    "src/base64.c",
    "src/hash.c",
    "src/hmac.c",
    "src/ice.c",
    "src/juice.c",
    "src/log.c",
    "src/random.c",
    "src/server.c",
    "src/stun.c",
    "src/timestamp.c",
    "src/tcp.c",
    "src/turn.c",
    "src/udp.c",
]

PRIVATE_HEADERS = [
    "src/addr.h",
    "src/agent.h",
    "src/base64.h",
    "src/conn.h",
    "src/conn_mux.h",
    "src/conn_poll.h",
    "src/conn_thread.h",
    "src/const_time.h",
    "src/crc32.h",
    "src/hash.h",
    "src/hmac.h",
    "src/ice.h",
    "src/log.h",
    "src/picohash.h",
    "src/random.h",
    "src/server.h",
    "src/socket.h",
    "src/stun.h",
    "src/tcp.h",
    "src/thread.h",
    "src/timestamp.h",
    "src/turn.h",
    "src/udp.h",
]

EXCLUDED_C_SOURCES = [
    "fuzzer/fuzzer.c",
    "test/base64.c",
    "test/bind.c",
    "test/conflict.c",
    "test/connectivity.c",
    "test/crc32.c",
    "test/gathering.c",
    "test/main.c",
    "test/mux.c",
    "test/notrickle.c",
    "test/server.c",
    "test/stun-unhandled-multiple.c",
    "test/stun-unhandled-no-host.c",
    "test/stun-unhandled-unhandle.c",
    "test/stun-unhandled.c",
    "test/stun.c",
    "test/tcp.c",
    "test/thread.c",
    "test/turn.c",
    "test/ufrag.c",
]

NDK_TOOL_HASHES = {
    "source.properties": "c00aa236fdb205e9be9edd9e2169763e48aca52735efff4e16f34205d49783b5",
    "toolchains/llvm/prebuilt/darwin-x86_64/bin/clang": (
        "df85444b66234bf4cae267e22bde45ea8fef596d30ca2991b2091a27e6ea7718"
    ),
    "toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android26-clang": (
        "c9ec0ccdc82aede75e6724738b833603707c0990061e05a1484860249f7520d5"
    ),
    "toolchains/llvm/prebuilt/darwin-x86_64/bin/x86_64-linux-android26-clang": (
        "176e679fe06dd5660a95fd35ee5a95084263b7d2d47bd6a0f58aa254e65d165e"
    ),
    "toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-ar": (
        "3705c4237aab47a369b999f5b0af572a6ea56488df7174aaab29e5fc4b082ea3"
    ),
    "toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-nm": (
        "709c3ec8bf09b68ac535275b1bb5bb511b7809413817036e3605f187809e7b81"
    ),
}

APPLE_TOOL_HASHES = {
    "/Applications/Xcode.app/Contents/Developer/Toolchains/"
    "XcodeDefault.xctoolchain/usr/bin/clang": (
        "7def90dd8829726686213a747fc5bff1583df933dae5edc55d755479e0bfe00a"
    ),
    "/Applications/Xcode.app/Contents/Developer/Toolchains/"
    "XcodeDefault.xctoolchain/usr/bin/ar": (
        "e49ffad64ad1cee722540fc5ecb00a230fd8071680682c60d9c851029d20e814"
    ),
    "/Applications/Xcode.app/Contents/Developer/Toolchains/"
    "XcodeDefault.xctoolchain/usr/bin/nm": (
        "d910f3acb104791e5475254000ede2aa129aa1a42eafcc7f5bdb27afffc642dc"
    ),
    "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/"
    "Developer/SDKs/MacOSX.sdk/SDKSettings.json": (
        "f8d005f09381389167f9e0aeaa169bc9e7dff162ef22ca2fd8e98df7ff1acafe"
    ),
}


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
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
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
        records.append(
            {
                "path": relative,
                "sizeBytes": metadata.st_size,
                "sha256": sha256_path(path),
            }
        )
    if len(records) != 81:
        raise ManifestError(f"expected 81 source files, found {len(records)}")
    return records


def archive_file_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with tarfile.open(ARCHIVE_PATH, mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            if not member.isfile():
                raise ManifestError(f"archive member {member.name!r} is not regular")
            name = safe_relative_path(member.name, "archive")
            prefix = "libjuice-1.7.2/"
            if not name.startswith(prefix):
                raise ManifestError(f"archive member {name!r} has unexpected root")
            relative = safe_relative_path(name[len(prefix):], "archive member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ManifestError(f"archive member {name!r} is unreadable")
            with stream:
                digest = sha256_stream(stream)
            records.append(
                {"path": relative, "sizeBytes": member.size, "sha256": digest}
            )
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


def checked_hashes(root: Path, expected: dict[str, str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative, expected_hash in expected.items():
        path = root / relative
        actual_hash = sha256_path(path)
        if actual_hash != expected_hash:
            raise ManifestError(f"{path}: expected {expected_hash}, got {actual_hash}")
        records.append(
            {
                "path": relative,
                "sizeBytes": path.stat().st_size,
                "sha256": actual_hash,
            }
        )
    return records


def build_manifest() -> dict[str, Any]:
    archive_hash = sha256_path(ARCHIVE_PATH)
    if archive_hash != EXPECTED_ARCHIVE_SHA256:
        raise ManifestError(f"libjuice archive digest drifted: {archive_hash}")
    ndk_archive_hash = sha256_path(NDK_ARCHIVE_PATH)
    if ndk_archive_hash != EXPECTED_NDK_ARCHIVE_SHA256:
        raise ManifestError(f"Android NDK archive digest drifted: {ndk_archive_hash}")

    source_records = source_file_records()
    archived_records = archive_file_records()
    if archived_records != source_records:
        raise ManifestError("archive and extracted source records differ")

    source_paths = {record["path"] for record in source_records}
    required_paths = set(LIBRARY_SOURCES + PRIVATE_HEADERS + EXCLUDED_C_SOURCES)
    required_paths.update({"CMakeLists.txt", "LICENSE", "include/juice/juice.h"})
    missing = sorted(required_paths - source_paths)
    if missing:
        raise ManifestError(f"required source inventory is missing {missing}")

    ndk_tools = checked_hashes(NDK_ROOT, NDK_TOOL_HASHES)
    apple_tools: list[dict[str, Any]] = []
    for raw_path, expected_hash in APPLE_TOOL_HASHES.items():
        path = Path(raw_path)
        actual_hash = sha256_path(path)
        if actual_hash != expected_hash:
            raise ManifestError(f"{path}: expected {expected_hash}, got {actual_hash}")
        apple_tools.append(
            {
                "path": raw_path,
                "sizeBytes": path.stat().st_size,
                "sha256": actual_hash,
            }
        )

    tree_digest = digest_records(source_records)
    return {
        "documentType": "aetherlink.p2p-nat-libjuice-source-manifest",
        "schemaVersion": 1,
        "manifestId": "production_p2p_nat_v1_libjuice_source_manifest_v1",
        "recordedDate": "2026-07-17",
        "status": "complete_audit_input_rejected_for_compile",
        "profileId": "production_p2p_nat_v1_recommended",
        "candidate": {
            "candidateId": "libjuice-1.7.2-static-c-abi",
            "repository": "https://github.com/paullouisageneau/libjuice",
            "repositoryMetadataUrl": "https://github.com/paullouisageneau/libjuice.git",
            "archiveUrl": (
                "https://codeload.github.com/paullouisageneau/libjuice/"
                "tar.gz/refs/tags/v1.7.2"
            ),
            "releaseTag": "v1.7.2",
            "annotatedTagObjectSha1": TAG_OBJECT_SHA1,
            "commitSha1": COMMIT_SHA1,
        },
        "acquisition": {
            "authorityDecision": "../decision-v2.json",
            "authorityHandoff": "../../implementation/handoff-v5.json",
            "transport": "https_only_no_redirect_no_environment_proxy",
            "archive": {
                "path": "build/offline-source/libjuice-1.7.2/original/libjuice-1.7.2.tar.gz",
                "sizeBytes": ARCHIVE_PATH.stat().st_size,
                "sha256": archive_hash,
            },
        },
        "extraction": {
            "path": "build/offline-source/libjuice-1.7.2/source",
            "archiveRoot": "libjuice-1.7.2",
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
            "sha256": tree_digest,
            "fileDigestSetSha256": tree_digest,
            "files": source_records,
        },
        "licenseReview": {
            "result": "complete_mixed_notices_recorded",
            "projectLicense": {
                "path": "LICENSE",
                "spdx": "MPL-2.0",
                "sha256": sha256_path(SOURCE_ROOT / "LICENSE"),
            },
            "embeddedNotices": [
                {
                    "path": "src/picohash.h",
                    "classification": "public_domain_with_upstream_attributions",
                    "sha256": sha256_path(SOURCE_ROOT / "src/picohash.h"),
                    "archiveRole": "compiled_when_USE_NETTLE_is_0",
                },
                {
                    "path": "cmake/Modules/FindNettle.cmake",
                    "classification": "bsd_3_clause_style_notice",
                    "sha256": sha256_path(SOURCE_ROOT / "cmake/Modules/FindNettle.cmake"),
                    "archiveRole": "not_compiled",
                },
                {
                    "path": "fuzzer/fuzzer.c",
                    "classification": "LGPL-2.1-or-later_notice_no_bundled_license_copy",
                    "sha256": sha256_path(SOURCE_ROOT / "fuzzer/fuzzer.c"),
                    "archiveRole": "excluded",
                },
            ],
        },
        "generatedFileReview": {
            "result": "complete",
            "generatedCOrHeaderFiles": [],
            "cmakeGeneratedPackageFilesCompiled": False,
            "makeGeneratedObjectsArchivesSharedLibrariesOrTestsAccepted": False,
        },
        "buildInputReview": {
            "authoritativeCMakeSourceLines": "CMakeLists.txt:38-60",
            "librarySources": LIBRARY_SOURCES,
            "publicHeaders": ["include/juice/juice.h"],
            "privateHeaders": PRIVATE_HEADERS,
            "excludedCSources": EXCLUDED_C_SOURCES,
            "minimalClientOnlySourcesIfCandidateHadPassed": [
                path for path in LIBRARY_SOURCES if path != "src/server.c"
            ],
            "requiredDefinesIfCandidateHadPassed": [
                "USE_NETTLE=0",
                "NO_SERVER=1",
                "JUICE_STATIC=1",
                "RELEASE=1",
            ],
            "requiredCommonFlagsIfCandidateHadPassed": [
                "-std=c11",
                "-fPIC",
                "-fvisibility=hidden",
                "-pthread",
                "-Wall",
                "-Wextra",
                "-Wno-address-of-packed-member",
                "-c",
            ],
            "cmakeExecutionAllowed": False,
            "makeExecutionAllowed": False,
            "configureExecutionAllowed": False,
            "compilerInvocationAllowedByThisManifest": False,
            "archiveInvocationAllowedByThisManifest": False,
        },
        "dependencyReview": {
            "result": "complete_for_unmodified_source_tree",
            "bundled": [
                {
                    "name": "picohash",
                    "path": "src/picohash.h",
                    "selectedWhen": "USE_NETTLE=0",
                }
            ],
            "optionalExternal": [
                {
                    "name": "nettle",
                    "selectedWhen": "USE_NETTLE=1",
                    "allowedForBoundedCandidate": False,
                }
            ],
            "system": [
                "c_runtime",
                "posix_sockets_and_dns",
                "pthreads",
                "polling",
                "monotonic_and_realtime_clocks",
                "platform_interface_and_route_apis",
            ],
            "ambientIncludeOrPkgConfigAllowed": False,
        },
        "toolchainReceipt": {
            "android": {
                "selectionBasis": "agp_9_2_1_embedded_default",
                "agpJarSha256": (
                    "582e85078b60eb80669223b34b58200ba034654b2edb1cf9621e62fde7dfc0a3"
                ),
                "packageId": "ndk;28.2.13676358",
                "releaseName": "r28c",
                "archive": {
                    "path": "build/toolchain-intake/android-ndk-r28c-darwin.zip",
                    "sizeBytes": NDK_ARCHIVE_PATH.stat().st_size,
                    "sha256": ndk_archive_hash,
                },
                "installPath": "$ANDROID_SDK_ROOT/ndk/28.2.13676358",
                "clangVersion": "Android 13624864 clang 19.0.1",
                "tools": ndk_tools,
                "sysrootTreeDigest": None,
                "sysrootDigestDisposition": "not_computed_candidate_rejected_before_compile_contract",
            },
            "macos": {
                "xcodeVersion": "26.6",
                "xcodeBuild": "17F113",
                "clangVersion": "Apple clang 21.0.0",
                "sdkVersion": "26.5",
                "sdkBuild": "25F70",
                "tools": apple_tools,
                "sdkTreeDigest": None,
                "sdkDigestDisposition": "not_computed_candidate_rejected_before_compile_contract",
            },
        },
        "authorityBoundary": {
            "sourceInspectionPerformed": True,
            "sourceExecutionPerformed": False,
            "compilerInvocationPerformed": False,
            "archiveInvocationPerformed": False,
            "sourceLinkedOrLoaded": False,
            "socketCreationPerformed": False,
            "runtimeNetworkIOPerformed": False,
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
    parser.add_argument(
        "--verify",
        action="store_true",
        help="read and hash retained evidence without writing either manifest",
    )
    arguments = parser.parse_args()

    data = encode_manifest(build_manifest())
    if arguments.verify:
        for path, label in (
            (arguments.output, "committed manifest"),
            (arguments.provenance_output, "local provenance twin"),
        ):
            if path.read_bytes() != data:
                raise ManifestError(f"{label} differs from retained evidence: {path}")
        print(
            "verified retained libjuice archive, 81-file source tree, NDK archive, "
            "installed NDK tools, Apple tools, and both manifest copies "
            f"sha256={hashlib.sha256(data).hexdigest()}"
        )
        return 0
    write_atomic(arguments.output, data)
    write_atomic(arguments.provenance_output, data)
    print(f"recorded libjuice source manifest sha256={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
