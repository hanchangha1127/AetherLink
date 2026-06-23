#!/usr/bin/env python3
"""Check macOS Localizable.strings locale parity, order, and duplicates."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = (
    ROOT
    / "apps"
    / "macos"
    / "LocalAgentBridgeApp"
    / "Sources"
    / "Resources"
)
LOCALES = ("en", "ko", "ja", "zh-Hans", "fr")
BASE_LOCALE = "en"

ENTRY_RE = re.compile(
    r"""
    ^\s*
    "((?:\\.|[^"\\])*)"
    \s*=\s*
    "((?:\\.|[^"\\])*)"
    \s*;
    \s*$
    """,
    re.VERBOSE,
)


def strings_path(locale: str) -> Path:
    return RESOURCE_ROOT / f"{locale}.lproj" / "Localizable.strings"


def lint_with_plutil(path: Path) -> str | None:
    plutil = shutil.which("plutil")
    if plutil is None:
        return None

    result = subprocess.run(
        [plutil, "-lint", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return None

    detail = (result.stderr or result.stdout).strip()
    return detail or "plutil reported invalid property-list strings syntax"


def unescape_key(value: str) -> str:
    return (
        value.replace(r"\"", '"')
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )


def parse_keys(path: Path) -> tuple[list[str], list[str]]:
    keys: list[str] = []
    failures: list[str] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        match = ENTRY_RE.match(line)
        if match is None:
            failures.append(f"line {line_number}: could not parse strings entry")
            continue

        keys.append(unescape_key(match.group(1)))

    return keys, failures


def duplicate_keys(keys: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []

    for key in keys:
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)

    return duplicates


def main() -> int:
    failures: list[str] = []
    locale_keys: dict[str, list[str]] = {}

    for locale in LOCALES:
        path = strings_path(locale)
        relative_path = path.relative_to(ROOT)

        if not path.exists():
            failures.append(f"{relative_path}: missing")
            continue

        lint_failure = lint_with_plutil(path)
        if lint_failure is not None:
            failures.append(f"{relative_path}: {lint_failure}")

        keys, parse_failures = parse_keys(path)
        for parse_failure in parse_failures:
            failures.append(f"{relative_path}: {parse_failure}")

        duplicates = duplicate_keys(keys)
        if duplicates:
            failures.append(f"{relative_path}: duplicate keys {duplicates}")

        locale_keys[locale] = keys

    base_keys = locale_keys.get(BASE_LOCALE)
    if base_keys is None:
        failures.append(f"{BASE_LOCALE}.lproj/Localizable.strings: base locale unavailable")
    else:
        for locale in LOCALES:
            if locale == BASE_LOCALE or locale not in locale_keys:
                continue

            keys = locale_keys[locale]
            if keys != base_keys:
                missing = [key for key in base_keys if key not in keys]
                extra = [key for key in keys if key not in base_keys]
                failures.append(
                    f"{strings_path(locale).relative_to(ROOT)}: key order/parity mismatch "
                    f"(missing={missing}, extra={extra})"
                )

    if failures:
        print("macOS localization check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"macOS localization parity OK for {len(LOCALES)} locale(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
