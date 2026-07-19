import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "script" / "android_usb_install.sh"


class AndroidUsbInstallTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.calls = self.root / "calls.log"
        self.java_home = self.root / "java-home"
        (self.java_home / "bin").mkdir(parents=True)
        self._write_executable(self.java_home / "bin" / "java", "#!/bin/sh\nexit 0\n")
        self.adb = self.root / "adb"
        self.gradle = self.root / "gradlew"
        self._write_executable(
            self.adb,
            """#!/bin/sh
set -eu
if [ "$1" = "devices" ]; then
  printf 'List of devices attached\\n%s\\n' "$FAKE_ADB_DEVICES"
  exit 0
fi
printf 'adb %s\\n' "$*" >> "$FAKE_CALLS"
case "$*" in
  *'shell cmd package resolve-activity --brief'*)
    printf 'com.localagentbridge.android/.MainActivity\\n'
    ;;
esac
""",
        )
        self._write_executable(
            self.gradle,
            """#!/bin/sh
set -eu
printf 'gradle serial=%s args=%s\\n' "${ANDROID_SERIAL:-}" "$*" >> "$FAKE_CALLS"
""",
        )

    def test_multiple_authorized_devices_require_explicit_serial(self):
        result = self._run(devices="serial-a device\nserial-b device")

        self.assertEqual(result.returncode, 5, result)
        self.assertIn("Multiple authorized Android devices", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_cli_serial_binds_adb_and_gradle_to_the_same_device(self):
        result = self._run(
            devices="serial-a device\nserial-b device",
            arguments=["--serial", "serial-b"],
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls.read_text(encoding="utf-8")
        self.assertIn("adb -s serial-b reverse", calls)
        self.assertIn("adb -s serial-b shell cmd package resolve-activity", calls)
        self.assertIn("adb -s serial-b shell am start", calls)
        self.assertIn("gradle serial=serial-b", calls)
        self.assertNotIn("adb -s serial-a", calls)

    def test_android_serial_environment_selects_one_authorized_device(self):
        result = self._run(
            devices="serial-a device\nserial-b unauthorized",
            android_serial="serial-a",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls.read_text(encoding="utf-8")
        self.assertIn("gradle serial=serial-a", calls)
        self.assertNotIn("serial-b", calls)

    def test_requested_unauthorized_device_fails_before_gradle(self):
        result = self._run(
            devices="serial-a device\nserial-b unauthorized",
            arguments=["--serial", "serial-b"],
        )

        self.assertEqual(result.returncode, 4, result)
        self.assertIn("serial-b is unauthorized", result.stderr)
        self.assertFalse(self.calls.exists())

    def _run(self, *, devices, arguments=None, android_serial=None):
        environment = os.environ.copy()
        environment.update(
            {
                "ADB": str(self.adb),
                "GRADLE": str(self.gradle),
                "JAVA_HOME": str(self.java_home),
                "FAKE_ADB_DEVICES": devices,
                "FAKE_CALLS": str(self.calls),
            }
        )
        if android_serial is None:
            environment.pop("ANDROID_SERIAL", None)
        else:
            environment["ANDROID_SERIAL"] = android_serial
        return subprocess.run(
            ["bash", str(SCRIPT), *(arguments or [])],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

    @staticmethod
    def _write_executable(path, content):
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
