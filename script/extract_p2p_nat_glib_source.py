#!/usr/bin/env python3
"""Safely extract the pinned GLib 2.64.2 source archive as data."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tarfile


ROOT = Path(__file__).resolve().parents[1]
INTAKE_ROOT = ROOT / "build/offline-source/glib-2.64.2"
ARCHIVE_PATH = INTAKE_ROOT / "original/glib-2.64.2.tar.xz"
SOURCE_ROOT = INTAKE_ROOT / "source"
TEMP_ROOT = INTAKE_ROOT / "source.extracting"
EXPECTED_ARCHIVE_SHA256 = "9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277"
ARCHIVE_PREFIX = "glib-2.64.2/"
MAX_MEMBERS = 50_000
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


class ExtractionError(ValueError):
    pass


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(raw: str) -> Path:
    if not raw or "\\" in raw or "\x00" in raw:
        raise ExtractionError(f"unsafe archive path {raw!r}")
    value = PurePosixPath(raw)
    if value.is_absolute() or any(part in ("", ".", "..") for part in value.parts):
        raise ExtractionError(f"unsafe archive path {raw!r}")
    if not value.as_posix().startswith(ARCHIVE_PREFIX):
        raise ExtractionError(f"unexpected archive root {raw!r}")
    relative = PurePosixPath(value.as_posix()[len(ARCHIVE_PREFIX):])
    if not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        raise ExtractionError(f"unsafe member path {raw!r}")
    return Path(*relative.parts)


def validated_members(archive: tarfile.TarFile) -> list[tuple[tarfile.TarInfo, Path]]:
    members = archive.getmembers()
    if not members or len(members) > MAX_MEMBERS:
        raise ExtractionError(f"unexpected archive member count {len(members)}")
    accepted: list[tuple[tarfile.TarInfo, Path]] = []
    seen: set[str] = set()
    total_bytes = 0
    for member in members:
        if member.name.rstrip("/") == ARCHIVE_PREFIX.rstrip("/") and member.isdir():
            continue
        relative = safe_relative_path(member.name)
        canonical = relative.as_posix()
        if canonical in seen:
            raise ExtractionError(f"duplicate archive member {member.name!r}")
        seen.add(canonical)
        if not member.isdir() and not member.isfile():
            raise ExtractionError(f"non-regular archive member {member.name!r}")
        if member.isfile():
            if member.size < 0 or member.size > MAX_FILE_BYTES:
                raise ExtractionError(f"oversized archive member {member.name!r}")
            total_bytes += member.size
            if total_bytes > MAX_TOTAL_BYTES:
                raise ExtractionError("archive exceeds the total extracted size limit")
        accepted.append((member, relative))
    return accepted


def extract() -> tuple[int, int]:
    if sha256_path(ARCHIVE_PATH) != EXPECTED_ARCHIVE_SHA256:
        raise ExtractionError("GLib archive SHA-256 does not match the intake lock")
    if SOURCE_ROOT.exists() or TEMP_ROOT.exists():
        raise ExtractionError("source destination already exists")
    TEMP_ROOT.mkdir(parents=True)
    file_count = 0
    total_bytes = 0
    try:
        with tarfile.open(ARCHIVE_PATH, mode="r:xz") as archive:
            for member, relative in validated_members(archive):
                destination = TEMP_ROOT / relative
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ExtractionError(f"unreadable archive member {member.name!r}")
                with source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if destination.stat().st_size != member.size:
                    raise ExtractionError(f"size mismatch for {member.name!r}")
                destination.chmod(0o644)
                file_count += 1
                total_bytes += member.size
        TEMP_ROOT.replace(SOURCE_ROOT)
    except Exception:
        shutil.rmtree(TEMP_ROOT, ignore_errors=True)
        raise
    return file_count, total_bytes


def main() -> int:
    file_count, total_bytes = extract()
    print(f"extracted pinned GLib source files={file_count} bytes={total_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
