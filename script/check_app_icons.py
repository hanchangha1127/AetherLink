#!/usr/bin/env python3
"""Check AetherLink launcher and app icon assets."""

from __future__ import annotations

from pathlib import Path
import struct
import sys
import zlib


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
ICNS_PNG_CHUNK_SIZES = {
    "ic11": 32,
    "ic12": 64,
    "ic07": 128,
    "ic08": 256,
    "ic13": 256,
    "ic09": 512,
    "ic14": 512,
    "ic10": 1024,
}


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != PNG_SIGNATURE:
        raise ValueError("not a PNG")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def decode_png_rgba(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    return decode_png_rgba_data(path.read_bytes())


def decode_png_rgba_data(data: bytes) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    if len(data) < 33 or data[:8] != PNG_SIGNATURE:
        raise ValueError("not a PNG")

    cursor = 8
    width = height = bit_depth = color_type = interlace = None
    idat_chunks: list[bytes] = []
    while cursor + 12 <= len(data):
        chunk_length = int.from_bytes(data[cursor:cursor + 4], "big")
        chunk_type = data[cursor + 4:cursor + 8]
        chunk_start = cursor + 8
        chunk_end = chunk_start + chunk_length
        cursor = chunk_end + 4
        if cursor > len(data):
            raise ValueError("PNG chunk exceeds file length")
        chunk = data[chunk_start:chunk_end]
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB",
                chunk,
            )
            if compression != 0 or filter_method != 0:
                raise ValueError("unsupported PNG compression or filter method")
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or bit_depth is None or color_type is None or interlace is None:
        raise ValueError("PNG missing IHDR")
    if bit_depth != 8:
        raise ValueError(f"unsupported PNG bit depth {bit_depth}")
    if color_type not in (2, 6):
        raise ValueError(f"unsupported PNG color type {color_type}")
    if interlace != 0:
        raise ValueError("interlaced PNGs are not supported by this readability check")
    if not idat_chunks:
        raise ValueError("PNG missing image data")

    bytes_per_pixel = 4 if color_type == 6 else 3
    stride = width * bytes_per_pixel
    raw = zlib.decompress(b"".join(idat_chunks))
    expected_length = height * (stride + 1)
    if len(raw) != expected_length:
        raise ValueError(f"unexpected PNG data length: expected {expected_length}, found {len(raw)}")

    rows: list[bytearray] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        scanline = bytearray(raw[offset:offset + stride])
        offset += stride
        reconstructed = bytearray(stride)
        for index, value in enumerate(scanline):
            left = reconstructed[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            up = previous[index]
            upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            if filter_type == 0:
                restored = value
            elif filter_type == 1:
                restored = value + left
            elif filter_type == 2:
                restored = value + up
            elif filter_type == 3:
                restored = value + ((left + up) // 2)
            elif filter_type == 4:
                restored = value + paeth_predictor(left, up, upper_left)
            else:
                raise ValueError(f"unsupported PNG filter {filter_type}")
            reconstructed[index] = restored & 0xFF
        rows.append(reconstructed)
        previous = reconstructed

    pixels: list[tuple[int, int, int, int]] = []
    for row in rows:
        for index in range(0, len(row), bytes_per_pixel):
            if color_type == 6:
                pixels.append((row[index], row[index + 1], row[index + 2], row[index + 3]))
            else:
                pixels.append((row[index], row[index + 1], row[index + 2], 255))
    return width, height, pixels


def paeth_predictor(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def composited_luminance(pixel: tuple[int, int, int, int]) -> float:
    red, green, blue, alpha = pixel
    alpha_fraction = alpha / 255
    red = round(red * alpha_fraction + 255 * (1 - alpha_fraction))
    green = round(green * alpha_fraction + 255 * (1 - alpha_fraction))
    blue = round(blue * alpha_fraction + 255 * (1 - alpha_fraction))
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def require_icon_readability(
    path: Path,
    failures: list[str],
    *,
    min_visible_coverage: float = 0.45,
    min_foreground_coverage: float = 0.20,
    min_dark_coverage: float = 0.10,
    min_center_foreground_coverage: float = 0.25,
    min_luminance_range: float = 96,
    min_strong_edge_ratio: float = 0.02,
) -> None:
    relative = path.relative_to(ROOT)
    try:
        width, height, pixels = decode_png_rgba(path)
    except (ValueError, zlib.error) as error:
        failures.append(f"{relative}: cannot decode PNG for readability: {error}")
        return
    require_icon_pixel_readability(
        label=relative.as_posix(),
        width=width,
        height=height,
        pixels=pixels,
        failures=failures,
        min_visible_coverage=min_visible_coverage,
        min_foreground_coverage=min_foreground_coverage,
        min_dark_coverage=min_dark_coverage,
        min_center_foreground_coverage=min_center_foreground_coverage,
        min_luminance_range=min_luminance_range,
        min_strong_edge_ratio=min_strong_edge_ratio,
    )


def require_icon_data_readability(
    label: str,
    data: bytes,
    failures: list[str],
    *,
    expected_size: int,
    min_visible_coverage: float = 0.45,
    min_foreground_coverage: float = 0.20,
    min_dark_coverage: float = 0.10,
    min_center_foreground_coverage: float = 0.25,
    min_luminance_range: float = 96,
    min_strong_edge_ratio: float = 0.02,
) -> None:
    try:
        width, height, pixels = decode_png_rgba_data(data)
    except (ValueError, zlib.error) as error:
        failures.append(f"{label}: cannot decode PNG for readability: {error}")
        return
    if (width, height) != (expected_size, expected_size):
        failures.append(f"{label}: expected {expected_size}x{expected_size}, found {width}x{height}")
        return
    require_icon_pixel_readability(
        label=label,
        width=width,
        height=height,
        pixels=pixels,
        failures=failures,
        min_visible_coverage=min_visible_coverage,
        min_foreground_coverage=min_foreground_coverage,
        min_dark_coverage=min_dark_coverage,
        min_center_foreground_coverage=min_center_foreground_coverage,
        min_luminance_range=min_luminance_range,
        min_strong_edge_ratio=min_strong_edge_ratio,
    )


def require_icon_pixel_readability(
    *,
    label: str,
    width: int,
    height: int,
    pixels: list[tuple[int, int, int, int]],
    failures: list[str],
    min_visible_coverage: float,
    min_foreground_coverage: float,
    min_dark_coverage: float,
    min_center_foreground_coverage: float,
    min_luminance_range: float,
    min_strong_edge_ratio: float,
) -> None:
    total_pixels = width * height
    visible_pixels = [pixel for pixel in pixels if pixel[3] >= 32]
    foreground_pixels = [
        pixel
        for pixel in pixels
        if pixel[3] >= 128 and composited_luminance(pixel) < 245
    ]
    dark_pixels = [
        pixel
        for pixel in pixels
        if pixel[3] >= 128 and composited_luminance(pixel) < 210
    ]
    center_start_x = int(width * 0.30)
    center_end_x = max(center_start_x + 1, int(width * 0.70))
    center_start_y = int(height * 0.30)
    center_end_y = max(center_start_y + 1, int(height * 0.70))
    center_pixels = [
        pixels[(row * width) + column]
        for row in range(center_start_y, center_end_y)
        for column in range(center_start_x, center_end_x)
    ]
    center_foreground_pixels = [
        pixel
        for pixel in center_pixels
        if pixel[3] >= 128 and composited_luminance(pixel) < 245
    ]
    visible_luminance_values = [composited_luminance(pixel) for pixel in visible_pixels]
    luminance_range = (
        max(visible_luminance_values) - min(visible_luminance_values)
        if visible_luminance_values
        else 0
    )
    strong_edges = 0
    edge_count = 0
    for row in range(height):
        for column in range(width):
            current = composited_luminance(pixels[(row * width) + column])
            if column + 1 < width:
                edge_count += 1
                right = composited_luminance(pixels[(row * width) + column + 1])
                if abs(current - right) >= 24:
                    strong_edges += 1
            if row + 1 < height:
                edge_count += 1
                below = composited_luminance(pixels[((row + 1) * width) + column])
                if abs(current - below) >= 24:
                    strong_edges += 1

    visible_coverage = len(visible_pixels) / total_pixels
    foreground_coverage = len(foreground_pixels) / total_pixels
    dark_coverage = len(dark_pixels) / total_pixels
    center_foreground_coverage = len(center_foreground_pixels) / len(center_pixels)
    strong_edge_ratio = strong_edges / edge_count if edge_count else 0

    if visible_coverage < min_visible_coverage:
        failures.append(f"{label}: visible icon coverage too low ({visible_coverage:.2%})")
    if foreground_coverage < min_foreground_coverage:
        failures.append(f"{label}: non-white foreground coverage too low ({foreground_coverage:.2%})")
    if dark_coverage < min_dark_coverage:
        failures.append(f"{label}: dark foreground coverage too low ({dark_coverage:.2%})")
    if center_foreground_coverage < min_center_foreground_coverage:
        failures.append(f"{label}: center mark coverage too low ({center_foreground_coverage:.2%})")
    if luminance_range < min_luminance_range:
        failures.append(f"{label}: luminance contrast too low ({luminance_range:.1f})")
    if strong_edge_ratio < min_strong_edge_ratio:
        failures.append(f"{label}: strong edge ratio too low ({strong_edge_ratio:.2%})")


def icns_chunk_bodies(path: Path) -> dict[str, bytes]:
    data = path.read_bytes()
    if len(data) < 8 or data[:4] != b"icns":
        raise ValueError("not an ICNS file")
    declared_length = int.from_bytes(data[4:8], "big")
    if declared_length != len(data):
        raise ValueError(f"ICNS length mismatch: declared={declared_length}, actual={len(data)}")

    chunks: dict[str, bytes] = {}
    cursor = 8
    while cursor + 8 <= len(data):
        code = data[cursor:cursor + 4].decode("latin1")
        chunk_length = int.from_bytes(data[cursor + 4:cursor + 8], "big")
        if chunk_length < 8:
            raise ValueError(f"invalid ICNS chunk {code!r} length {chunk_length}")
        if cursor + chunk_length > len(data):
            raise ValueError(f"invalid ICNS chunk {code!r} exceeds file length")
        chunks[code] = data[cursor + 8:cursor + chunk_length]
        cursor += chunk_length
    if cursor != len(data):
        raise ValueError("ICNS has trailing partial chunk data")
    return chunks


def icns_chunks(path: Path) -> set[str]:
    return set(icns_chunk_bodies(path))


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
    require_icon_readability(BRAND_SOURCE, failures, min_strong_edge_ratio=0.005)
    require_png(BRAND_PREVIEW, 1024, failures)
    require_icon_readability(BRAND_PREVIEW, failures, min_strong_edge_ratio=0.005)
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
        launcher = ANDROID_RES / density_dir / "ic_launcher.png"
        round_launcher = ANDROID_RES / density_dir / "ic_launcher_round.png"
        require_png(launcher, size, failures)
        require_icon_readability(launcher, failures)
        require_png(round_launcher, size, failures)
        require_icon_readability(round_launcher, failures)

    android_foreground = ANDROID_RES / "drawable-nodpi/ic_launcher_foreground.png"
    require_png(android_foreground, 432, failures)
    require_icon_readability(android_foreground, failures)
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
            chunk_bodies = icns_chunk_bodies(MACOS_ICON)
        except ValueError as error:
            failures.append(f"{MACOS_ICON.relative_to(ROOT)}: {error}")
        else:
            chunks = set(chunk_bodies)
            missing_chunks = sorted(REQUIRED_ICNS_CHUNKS - chunks)
            if missing_chunks:
                failures.append(f"{MACOS_ICON.relative_to(ROOT)}: missing ICNS chunks {missing_chunks}")
            for chunk_code, expected_size in ICNS_PNG_CHUNK_SIZES.items():
                chunk = chunk_bodies.get(chunk_code)
                if chunk is None:
                    continue
                if not chunk.startswith(PNG_SIGNATURE):
                    failures.append(f"{MACOS_ICON.relative_to(ROOT)}:{chunk_code}: expected PNG chunk data")
                    continue
                require_icon_data_readability(
                    f"{MACOS_ICON.relative_to(ROOT)}:{chunk_code}",
                    chunk,
                    failures,
                    expected_size=expected_size,
                    min_strong_edge_ratio=0.005,
                )
            if MACOS_ICON.stat().st_size < 1_000_000:
                failures.append(f"{MACOS_ICON.relative_to(ROOT)}: ICNS is unexpectedly small")

    if failures:
        print("App icon check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("App icon assets OK for Android and macOS, including no-device small-size readability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
