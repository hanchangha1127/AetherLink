#!/usr/bin/env python3
"""Check Android string resource locale parity and key order."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ANDROID_ROOT = ROOT / "apps" / "android"
LOCALE_DIRS = ("values-en", "values-ko", "values-ja", "values-zh-rCN", "values-fr")


def string_names(path: Path) -> list[str]:
    root = ET.parse(path).getroot()
    return [node.attrib["name"] for node in root.findall("string")]


def main() -> int:
    failures: list[str] = []
    default_files = sorted(
        ANDROID_ROOT.glob("**/src/main/res/values/strings.xml"),
        key=lambda path: str(path),
    )

    if not default_files:
        print("No Android default strings.xml files found.", file=sys.stderr)
        return 1

    for default_file in default_files:
        default_names = string_names(default_file)
        res_dir = default_file.parents[1]
        module = default_file.relative_to(ROOT)

        for locale_dir_name in LOCALE_DIRS:
            locale_file = res_dir / locale_dir_name / "strings.xml"
            if not locale_file.exists():
                failures.append(f"{module}: missing {locale_dir_name}/strings.xml")
                continue

            locale_names = string_names(locale_file)
            if locale_names != default_names:
                missing = [name for name in default_names if name not in locale_names]
                extra = [name for name in locale_names if name not in default_names]
                failures.append(
                    f"{locale_file.relative_to(ROOT)}: key order/parity mismatch "
                    f"(missing={missing}, extra={extra})"
                )

    if failures:
        print("Android string parity check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Android string parity OK for {len(default_files)} resource set(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
