#!/usr/bin/env python3
"""Pure fake-toolchain regression tests for build_and_run.sh mode handling."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "script/build_and_run.sh"


class BuildAndRunModeTests(unittest.TestCase):
    def test_invalid_mode_invokes_no_fake_toolchain_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp_path = Path(temporary)
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()
            invocation_log = temp_path / "invocations.log"
            fake_command = (
                "#!/usr/bin/env bash\n"
                'printf "%s\\n" "${0##*/}" >>"$FAKE_TOOLCHAIN_LOG"\n'
                "exit 97\n"
            )
            for name in (
                "pkill",
                "swift",
                "rm",
                "mkdir",
                "cp",
                "chmod",
                "find",
                "cat",
                "lldb",
                "sleep",
                "pgrep",
            ):
                command = fake_bin / name
                command.write_text(fake_command, encoding="utf-8")
                command.chmod(0o755)

            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
            environment["FAKE_TOOLCHAIN_LOG"] = str(invocation_log)
            result = subprocess.run(
                ["/bin/bash", str(SCRIPT_PATH), "invalid-mode"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2, result)
            self.assertIn("usage:", result.stderr)
            self.assertFalse(
                invocation_log.exists(),
                invocation_log.read_text(encoding="utf-8") if invocation_log.exists() else "",
            )

    def test_mode_validation_precedes_every_named_side_effect(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        validation_index = source.index('\nvalidate_mode "$MODE"\n')
        for marker in (
            "pkill -x",
            "swift build",
            'rm -rf "$APP_BUNDLE"',
            "/usr/bin/codesign",
            "/usr/bin/open",
        ):
            with self.subTest(marker=marker):
                self.assertLess(validation_index, source.index(marker))


if __name__ == "__main__":
    unittest.main()
