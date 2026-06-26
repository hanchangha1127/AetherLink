#!/usr/bin/env python3
"""Check the repository license declaration and handoff wording."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
LICENSE = ROOT / "LICENSE"
README = ROOT / "README.md"
DOCS = ROOT / "docs"
NESTED_READMES = {
    ROOT / "apps/android/README.md": "../../LICENSE",
    ROOT / "apps/macos/README.md": "../../LICENSE",
    ROOT / "packages/protocol-schema/README.md": "../../LICENSE",
    ROOT / "shared/protocol/README.md": "../../LICENSE",
    ROOT / "examples/README.md": "../LICENSE",
    ROOT / "assets/brand/README.md": "../../LICENSE",
}

APACHE_LICENSE_SNIPPETS = (
    "Apache License",
    "Version 2.0, January 2004",
    "http://www.apache.org/licenses/",
    "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
    "Copyright 2026 AetherLink contributors",
    'Licensed under the Apache License, Version 2.0 (the "License");',
    "http://www.apache.org/licenses/LICENSE-2.0",
)
README_SNIPPETS = (
    "## License",
    "AetherLink is licensed under the Apache License, Version 2.0.",
    "See [LICENSE](LICENSE).",
)
STALE_LICENSE_RE = re.compile(
    r"intended license direction|license direction|to be licensed|TBD license|"
    r"MIT License|GNU General Public License|\\bGPL\\b|BSD License|Proprietary",
    re.IGNORECASE,
)
ALLOWED_STALE_PATHS = {LICENSE.relative_to(ROOT).as_posix()}


def text_or_failure(path: Path, failures: list[str]) -> str:
    if not path.exists():
        failures.append(f"{path.relative_to(ROOT)}: missing file")
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    failures: list[str] = []

    license_text = text_or_failure(LICENSE, failures)
    if license_text:
        for snippet in APACHE_LICENSE_SNIPPETS:
            if snippet not in license_text:
                failures.append(f"{LICENSE.relative_to(ROOT)}: missing Apache 2.0 snippet {snippet!r}")

    readme_text = text_or_failure(README, failures)
    if readme_text:
        for snippet in README_SNIPPETS:
            if snippet not in readme_text:
                failures.append(f"{README.relative_to(ROOT)}: missing license snippet {snippet!r}")

    for path, license_href in NESTED_READMES.items():
        nested_text = text_or_failure(path, failures)
        if not nested_text:
            continue
        relative = path.relative_to(ROOT)
        for snippet in (
            "## License",
            "Licensed under the Apache License, Version 2.0.",
            f"See [LICENSE]({license_href}).",
        ):
            if snippet not in nested_text:
                failures.append(f"{relative}: missing license snippet {snippet!r}")

    checked_paths = [README, *NESTED_READMES.keys()]
    if DOCS.exists():
        checked_paths.extend(sorted(DOCS.glob("*.md")))

    for path in checked_paths:
        relative = path.relative_to(ROOT).as_posix()
        if relative in ALLOWED_STALE_PATHS:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if STALE_LICENSE_RE.search(line):
                failures.append(
                    f"{relative}:{line_number}: stale or conflicting license wording; "
                    "the project license is Apache License 2.0."
                )

    if failures:
        print("License check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("License declaration OK: Apache License 2.0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
