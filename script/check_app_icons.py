#!/usr/bin/env python3
"""Check AetherLink launcher and app icon assets."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

ANDROID_MANIFEST = ROOT / "apps/android/app/src/main/AndroidManifest.xml"
ANDROID_RES = ROOT / "apps/android/app/src/main/res"
MACOS_ICON = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/Resources/AppIcon.icns"
BRAND_SOURCE = ROOT / "assets/brand/aetherlink_icon_source.png"
BRAND_PREVIEW = ROOT / "assets/brand/aetherlink_icon_1024.png"
BRAND_GENERATOR = ROOT / "assets/brand/generate_aetherlink_icons.swift"

ANDROID_DENSITY_ICONS = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
REQUIRED_ICNS_CHUNKS = {
    "ic04",
    "ic05",
    "ic07",
    "ic08",
    "ic09",
    "ic10",
    "ic11",
    "ic12",
    "ic13",
    "ic14",
}


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != PNG_SIGNATURE:
        raise ValueError("not a PNG")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def icns_chunks(path: Path) -> set[str]:
    data = path.read_bytes()
    if len(data) < 8 or data[:4] != b"icns":
        raise ValueError("not an ICNS file")
    declared_length = int.from_bytes(data[4:8], "big")
    if declared_length != len(data):
        raise ValueError(f"ICNS length mismatch: declared={declared_length}, actual={len(data)}")

    chunks: set[str] = set()
    cursor = 8
    while cursor + 8 <= len(data):
        code = data[cursor:cursor + 4].decode("latin1")
        chunk_length = int.from_bytes(data[cursor + 4:cursor + 8], "big")
        if chunk_length < 8:
            raise ValueError(f"invalid ICNS chunk {code!r} length {chunk_length}")
        chunks.add(code)
        cursor += chunk_length
    if cursor != len(data):
        raise ValueError("ICNS has trailing partial chunk data")
    return chunks


def require_png(path: Path, expected_size: int, failures: list[str]) -> None:
    relative = path.relative_to(ROOT)
    if not path.exists():
        failures.append(f"{relative}: missing PNG")
        return
    try:
        width, height = png_size(path)
    except ValueError as error:
        failures.append(f"{relative}: {error}")
        return
    if (width, height) != (expected_size, expected_size):
        failures.append(f"{relative}: expected {expected_size}x{expected_size}, found {width}x{height}")
    if path.stat().st_size < max(1024, expected_size * expected_size // 8):
        failures.append(f"{relative}: PNG is unexpectedly small; icon may be blank or truncated")


def require_text(path: Path, snippets: tuple[str, ...], failures: list[str]) -> None:
    relative = path.relative_to(ROOT)
    if not path.exists():
        failures.append(f"{relative}: missing file")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    for snippet in snippets:
        if snippet not in text:
            failures.append(f"{relative}: missing snippet {snippet!r}")


def main() -> int:
    failures: list[str] = []

    require_png(BRAND_SOURCE, 1254, failures)
    require_png(BRAND_PREVIEW, 1024, failures)
    require_text(
        BRAND_GENERATOR,
        (
            "aetherlink_icon_source.png",
            "ic_launcher_foreground.png",
            "AppIcon.icns",
            "/usr/bin/iconutil",
        ),
        failures,
    )
    require_text(
        ANDROID_MANIFEST,
        (
            'android:icon="@mipmap/ic_launcher"',
            'android:roundIcon="@mipmap/ic_launcher_round"',
        ),
        failures,
    )

    for density_dir, size in ANDROID_DENSITY_ICONS.items():
        require_png(ANDROID_RES / density_dir / "ic_launcher.png", size, failures)
        require_png(ANDROID_RES / density_dir / "ic_launcher_round.png", size, failures)

    require_png(ANDROID_RES / "drawable-nodpi/ic_launcher_foreground.png", 432, failures)
    require_text(
        ANDROID_RES / "mipmap-anydpi-v26/ic_launcher.xml",
        (
            '<background android:drawable="@drawable/ic_launcher_background" />',
            '<foreground android:drawable="@drawable/ic_launcher_foreground" />',
        ),
        failures,
    )
    require_text(
        ANDROID_RES / "mipmap-anydpi-v26/ic_launcher_round.xml",
        (
            '<background android:drawable="@drawable/ic_launcher_background" />',
            '<foreground android:drawable="@drawable/ic_launcher_foreground" />',
        ),
        failures,
    )
    require_text(
        ANDROID_RES / "drawable/ic_launcher_background.xml",
        ('<solid android:color="#FFFFFF" />',),
        failures,
    )

    if not MACOS_ICON.exists():
        failures.append(f"{MACOS_ICON.relative_to(ROOT)}: missing ICNS")
    else:
        try:
            chunks = icns_chunks(MACOS_ICON)
        except ValueError as error:
            failures.append(f"{MACOS_ICON.relative_to(ROOT)}: {error}")
        else:
            missing_chunks = sorted(REQUIRED_ICNS_CHUNKS - chunks)
            if missing_chunks:
                failures.append(f"{MACOS_ICON.relative_to(ROOT)}: missing ICNS chunks {missing_chunks}")
            if MACOS_ICON.stat().st_size < 1_000_000:
                failures.append(f"{MACOS_ICON.relative_to(ROOT)}: ICNS is unexpectedly small")

    if failures:
        print("App icon check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("App icon assets OK for Android and macOS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
