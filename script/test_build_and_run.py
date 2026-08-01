#!/usr/bin/env python3
"""Pure fake-toolchain regression tests for build_and_run.sh mode handling."""

from __future__ import annotations

import os
from pathlib import Path
import json
import plistlib
import shutil
import subprocess
import tempfile
import unittest

from script.check_release_version_ledger import (
    LedgerError,
    parse_release_version_ledger,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "script/build_and_run.sh"


class BuildAndRunModeTests(unittest.TestCase):
    @staticmethod
    def set_fixed_repro_scratch_path(script: Path, scratch: Path | str) -> None:
        declaration = (
            'REPRO_SWIFT_SCRATCH_PATH='
            '"/private/tmp/aetherlink-g6-swift-scratch-v1"'
        )
        source = script.read_text(encoding="utf-8")
        if source.count(declaration) != 1:
            raise AssertionError("fixed reproducibility scratch declaration drifted")
        script.write_text(
            source.replace(
                declaration,
                f'REPRO_SWIFT_SCRATCH_PATH="{scratch}"',
            ),
            encoding="utf-8",
        )

    def make_fake_package_workspace(
        self,
        temporary: str,
        *,
        resource_bundle_count: int,
        ledger_text: str | None = None,
        ledger_bytes: bytes | None = None,
    ) -> tuple[Path, dict[str, str], Path]:
        temp_path = Path(temporary)
        workspace = temp_path / "workspace"
        script_dir = workspace / "script"
        release_dir = workspace / "release"
        resources_dir = workspace / "apps/macos/LocalAgentBridgeApp/Sources/Resources"
        fake_bin = temp_path / "bin"
        swift_bin_path = temp_path / "swift-bin"
        script_dir.mkdir(parents=True)
        release_dir.mkdir()
        fake_bin.mkdir()
        swift_bin_path.mkdir()
        shutil.copy2(SCRIPT_PATH, script_dir / SCRIPT_PATH.name)
        if ledger_text is not None and ledger_bytes is not None:
            raise ValueError("provide at most one ledger fixture")
        if ledger_bytes is not None:
            (release_dir / "version-ledger.tsv").write_bytes(ledger_bytes)
        elif ledger_text is None:
            shutil.copy2(
                ROOT / "release/version-ledger.tsv",
                release_dir / "version-ledger.tsv",
            )
        else:
            (release_dir / "version-ledger.tsv").write_text(
                ledger_text,
                encoding="ascii",
            )
        shutil.copytree(
            ROOT / "apps/macos/LocalAgentBridgeApp/Sources/Resources",
            resources_dir,
        )
        fake_executable = swift_bin_path / "AetherLink"
        shutil.copyfile("/usr/bin/true", fake_executable)
        fake_executable.chmod(0o755)
        fake_dsym = swift_bin_path / "AetherLink.dSYM"
        fake_dsym_dwarf = fake_dsym / "Contents/Resources/DWARF/AetherLink"
        fake_dsym_relocation = (
            fake_dsym
            / "Contents/Resources/Relocations/aarch64/AetherLink.yml"
        )
        fake_dsym_dwarf.parent.mkdir(parents=True)
        fake_dsym_relocation.parent.mkdir(parents=True)
        with (fake_dsym / "Contents/Info.plist").open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleIdentifier": "com.apple.xcode.dsym.AetherLink",
                    "CFBundlePackageType": "dSYM",
                },
                handle,
            )
        fake_dsym_dwarf.write_bytes(b"fixture-aetherlink-dwarf\n")
        fake_dsym_relocation.write_bytes(b"fixture-relocations\n")

        for index in range(resource_bundle_count):
            prefix = "AetherLink" if resource_bundle_count == 1 else f"Candidate{index + 1}"
            resource_bundle = swift_bin_path / f"{prefix}_LocalAgentBridge.bundle"
            resource_bundle.mkdir()
            with (resource_bundle / "Info.plist").open("wb") as handle:
                plistlib.dump(
                    {
                        "CFBundleDevelopmentRegion": "en",
                        "CFBundleIdentifier": f"test.{prefix.lower()}",
                    },
                    handle,
                )
            for locale in ("en", "ko", "ja", "zh-Hans", "fr"):
                localized = resource_bundle / f"{locale}.lproj"
                localized.mkdir()
                (localized / "Localizable.strings").write_text(
                    '"AetherLink" = "AetherLink";\n',
                    encoding="utf-8",
                )

        invocation_log = temp_path / "invocations.log"
        fake_swift = fake_bin / "swift"
        fake_swift.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf "swift %s\\n" "$*" >>"$FAKE_TOOLCHAIN_LOG"\n'
            'expected_options="${FAKE_SWIFT_BUILD_OPTIONS:--c release}"\n'
            'if [[ "$*" == "package clean" ]]; then\n'
            "  exit 0\n"
            "fi\n"
            'if [[ "$*" == "build $expected_options --product AetherLink" ]]; then\n'
            "  exit 0\n"
            "fi\n"
            'if [[ "$*" == "build $expected_options --show-bin-path" ]]; then\n'
            '  printf "%s\\n" "$FAKE_SWIFT_BIN_PATH"\n'
            "  exit 0\n"
            "fi\n"
            "exit 97\n",
            encoding="utf-8",
        )
        fake_swift.chmod(0o755)
        fake_pkill = fake_bin / "pkill"
        fake_pkill.write_text(
            "#!/usr/bin/env bash\n"
            'printf "pkill %s\\n" "$*" >>"$FAKE_TOOLCHAIN_LOG"\n'
            "exit 97\n",
            encoding="utf-8",
        )
        fake_pkill.chmod(0o755)
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'command_name="${3:-}"\n'
            'if [[ "$command_name" == "unsealed-macos-source-receipt" ]]; then\n'
            '  printf "%s\\n" "$FAKE_UNSEALED_SOURCE_RECEIPT"\n'
            "  exit 0\n"
            "fi\n"
            'if [[ "$command_name" == "publish-unsealed-macos-output" ]]; then\n'
            '  if [[ "${4:-}" != "--staging-root" || -z "${5:-}" ]]; then\n'
            "    exit 96\n"
            "  fi\n"
            '  staging_root="$5"\n'
            '  destination="${staging_root%/*}/unsealed-package-only"\n'
            '  if [[ "${FAKE_UNSEALED_PUBLISH_ROLLBACK_FAILURE:-0}" == "1" '
            '&& ( -e "$destination" || -L "$destination" ) ]]; then\n'
            '    replaced="${staging_root%/*}/.unsealed-package-only.replaced"\n'
            '    /bin/mv "$destination" "$replaced"\n'
            '    /bin/mv "$staging_root" "$destination"\n'
            '    /bin/mv "$replaced" "$staging_root"\n'
            '    printf "injected post-readback and rollback failure\\n" >&2\n'
            "    exit 91\n"
            "  fi\n"
            '  if [[ "${FAKE_UNSEALED_PUBLISH_CLEANUP_WARNING:-0}" == "1" '
            '&& ( -e "$destination" || -L "$destination" ) ]]; then\n'
            '    replaced="${staging_root%/*}/.unsealed-package-only.replaced"\n'
            '    /bin/mv "$destination" "$replaced"\n'
            '    /bin/mv "$staging_root" "$destination"\n'
            '    /bin/mv "$replaced" "$staging_root"\n'
            '    printf "injected committed cleanup warning\\n" >&2\n'
            "    exit 0\n"
            "  fi\n"
            '  if [[ -e "$destination" || -L "$destination" ]]; then\n'
            '    replaced="${staging_root%/*}/.unsealed-package-only.replaced"\n'
            '    /bin/mv "$destination" "$replaced"\n'
            '    /bin/mv "$staging_root" "$destination"\n'
            '    /bin/rm -rf "$replaced"\n'
            "  else\n"
            '    /bin/mv "$staging_root" "$destination"\n'
            "  fi\n"
            '  printf "Unsealed macOS output published: %s\\n" "$destination"\n'
            "  exit 0\n"
            "fi\n"
            'exec /usr/bin/python3 "$@"\n',
            encoding="utf-8",
        )
        fake_python.chmod(0o755)

        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        environment["FAKE_TOOLCHAIN_LOG"] = str(invocation_log)
        environment["FAKE_SWIFT_BIN_PATH"] = str(swift_bin_path)
        try:
            current_release = parse_release_version_ledger(
                (release_dir / "version-ledger.tsv").read_bytes()
            )[-1]
            receipt_build_number = current_release.build_number
            receipt_marketing_version = current_release.marketing_version
        except (IndexError, LedgerError):
            receipt_build_number = 1
            receipt_marketing_version = "0.0.0"
        environment["FAKE_UNSEALED_SOURCE_RECEIPT"] = json.dumps(
            {
                "build": {
                    "buildNumber": receipt_build_number,
                    "configuration": "release",
                    "marketingVersion": receipt_marketing_version,
                    "mode": "unsealed-package-only",
                },
                "outputContract": "macos-unsealed-app-dsym-source-bound-v1",
                "schemaVersion": 1,
                "source": {
                    "algorithm": (
                        "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
                    ),
                    "fileCount": 1,
                    "sha256": "a" * 64,
                },
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        return workspace, environment, invocation_log

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
            "/usr/bin/nohup",
        ):
            with self.subTest(marker=marker):
                self.assertLess(validation_index, source.index(marker))

    def test_debug_launch_uses_file_backed_runtime_identity(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'DEBUG_RUNTIME_IDENTITY_FILE="${AETHERLINK_RUNTIME_IDENTITY_FILE:-',
            source,
        )
        self.assertIn(
            "/usr/bin/nohup /usr/bin/env",
            source,
        )
        self.assertIn(
            'AETHERLINK_RUNTIME_IDENTITY_FILE="$DEBUG_RUNTIME_IDENTITY_FILE"',
            source,
        )
        self.assertIn("APP_LAUNCH_SETTLE_SECONDS=5", source)
        self.assertIn('sleep "$APP_LAUNCH_SETTLE_SECONDS"', source)
        self.assertIn('kill -0 "$launch_pid"', source)
        self.assertNotIn("/usr/bin/open", source)

    def test_package_only_builds_self_contained_release_without_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, invocation_log = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            script = workspace / "script/build_and_run.sh"
            result = subprocess.run(
                ["/bin/bash", str(script), "--package-only"],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result)
            app_bundle = workspace / "dist/package-only/AetherLink.app"
            self.assertTrue(
                (
                    app_bundle
                    / "Contents/Resources/AetherLink_LocalAgentBridge.bundle"
                ).is_dir()
            )
            self.assertFalse(
                (
                    app_bundle
                    / "Contents/Resources/AetherLink_LocalAgentBridge.bundle/AppIcon.icns"
                ).exists()
            )
            for locale in ("en", "ko", "ja", "zh-Hans", "fr"):
                self.assertFalse(
                    (app_bundle / f"Contents/Resources/{locale}.lproj").exists()
                )
            self.assertTrue((app_bundle / "Contents/MacOS/AetherLink").is_file())
            self.assertFalse(
                (workspace / "dist/package-only/AetherLink.dSYM").exists()
            )
            with (app_bundle / "Contents/Info.plist").open("rb") as handle:
                info = plistlib.load(handle)
            current_release = parse_release_version_ledger(
                (workspace / "release/version-ledger.tsv").read_bytes()
            )[-1]
            self.assertEqual(
                info["CFBundleShortVersionString"],
                current_release.marketing_version,
            )
            self.assertEqual(
                info["CFBundleVersion"],
                str(current_release.build_number),
            )
            invocations = invocation_log.read_text(encoding="utf-8")
            self.assertEqual(
                invocations.splitlines(),
                [
                    "swift package clean",
                    "swift build -c release --product AetherLink",
                    "swift build -c release --show-bin-path",
                ],
            )
            self.assertNotIn("pkill", invocations)
            verification = subprocess.run(
                [
                    "/usr/bin/codesign",
                    "--verify",
                    "--deep",
                    "--strict",
                    str(app_bundle),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verification.returncode, 0, verification)

    def test_unsealed_package_only_builds_release_and_copies_dsym_without_launch_or_seal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, invocation_log = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            development_app = workspace / "dist/AetherLink.app"
            development_app.mkdir(parents=True)
            development_sentinel = development_app / "running-build.txt"
            development_sentinel.write_bytes(b"preserve-running-build")
            legacy_output = workspace / "dist/package-only"
            legacy_output.mkdir()
            legacy_sentinel = legacy_output / "preserve.txt"
            legacy_sentinel.write_bytes(b"preserve-package-only")
            environment["AETHERLINK_PACKAGE_OUTPUT_ROOT"] = str(
                workspace / "dist/release-package"
            )

            result = subprocess.run(
                [
                    "/bin/bash",
                    str(workspace / "script/build_and_run.sh"),
                    "--unsealed-package-only",
                ],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result)
            self.assertEqual(
                development_sentinel.read_bytes(),
                b"preserve-running-build",
            )
            self.assertEqual(
                legacy_sentinel.read_bytes(),
                b"preserve-package-only",
            )
            output = workspace / "dist/unsealed-package-only"
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "AetherLink.app",
                    "AetherLink.dSYM",
                    "source-receipt.json",
                },
            )
            self.assertEqual(
                json.loads(
                    (output / "source-receipt.json").read_text(
                        encoding="ascii"
                    )
                ),
                json.loads(environment["FAKE_UNSEALED_SOURCE_RECEIPT"]),
            )
            app_bundle = output / "AetherLink.app"
            output_dsym = output / "AetherLink.dSYM"
            self.assertFalse((app_bundle / "Contents/_CodeSignature").exists())
            self.assertFalse(
                any(
                    path.name == "CodeResources"
                    for path in app_bundle.rglob("*")
                )
            )
            with (app_bundle / "Contents/Info.plist").open("rb") as handle:
                info = plistlib.load(handle)
            current_release = parse_release_version_ledger(
                (workspace / "release/version-ledger.tsv").read_bytes()
            )[-1]
            self.assertEqual(
                info["CFBundleShortVersionString"],
                current_release.marketing_version,
            )
            self.assertEqual(
                info["CFBundleVersion"],
                str(current_release.build_number),
            )
            source_dsym = Path(environment["FAKE_SWIFT_BIN_PATH"]) / "AetherLink.dSYM"
            for relative in (
                "Contents/Info.plist",
                "Contents/Resources/DWARF/AetherLink",
                "Contents/Resources/Relocations/aarch64/AetherLink.yml",
            ):
                self.assertEqual(
                    (output_dsym / relative).read_bytes(),
                    (source_dsym / relative).read_bytes(),
                )
            self.assertEqual(
                invocation_log.read_text(encoding="utf-8").splitlines(),
                [
                    "swift package clean",
                    "swift build -c release --product AetherLink",
                    "swift build -c release --show-bin-path",
                ],
            )
            self.assertNotIn("pkill", invocation_log.read_text(encoding="utf-8"))
            self.assertIn(str(output), result.stdout)

    def test_unsealed_package_only_requires_physical_dsym_before_replacing_outputs(
        self,
    ) -> None:
        for mutation in ("missing", "symlink", "special"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                workspace, environment, _ = self.make_fake_package_workspace(
                    temporary,
                    resource_bundle_count=1,
                )
                source_dsym = (
                    Path(environment["FAKE_SWIFT_BIN_PATH"])
                    / "AetherLink.dSYM"
                )
                if mutation == "missing":
                    shutil.rmtree(source_dsym)
                elif mutation == "symlink":
                    physical = source_dsym.with_name("physical.dSYM")
                    source_dsym.rename(physical)
                    source_dsym.symlink_to(physical, target_is_directory=True)
                else:
                    dwarf = (
                        source_dsym
                        / "Contents/Resources/DWARF/AetherLink"
                    )
                    dwarf.unlink()
                    os.mkfifo(dwarf)

                output = workspace / "dist/unsealed-package-only"
                old_app = output / "AetherLink.app"
                old_dsym = output / "AetherLink.dSYM"
                old_app.mkdir(parents=True)
                old_dsym.mkdir()
                app_sentinel = old_app / "preserve.txt"
                dsym_sentinel = old_dsym / "preserve.txt"
                app_sentinel.write_bytes(b"old-app")
                dsym_sentinel.write_bytes(b"old-dsym")

                result = subprocess.run(
                    [
                        "/bin/bash",
                        str(workspace / "script/build_and_run.sh"),
                        "--unsealed-package-only",
                    ],
                    cwd=workspace,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 1, result)
                self.assertIn("unsealed Release dSYM source", result.stderr)
                self.assertEqual(app_sentinel.read_bytes(), b"old-app")
                self.assertEqual(dsym_sentinel.read_bytes(), b"old-dsym")

    def test_unsealed_package_only_staged_copy_failure_preserves_previous_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, _ = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            fake_cp = Path(temporary) / "bin/cp"
            fake_cp.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'last_argument="${!#}"\n'
                'if [[ "$last_argument" == */AetherLink.dSYM ]]; then\n'
                "  exit 95\n"
                "fi\n"
                'exec /bin/cp "$@"\n',
                encoding="utf-8",
            )
            fake_cp.chmod(0o755)
            output = workspace / "dist/unsealed-package-only"
            old_app = output / "AetherLink.app"
            old_dsym = output / "AetherLink.dSYM"
            old_app.mkdir(parents=True)
            old_dsym.mkdir()
            (old_app / "preserve.txt").write_bytes(b"old-app")
            (old_dsym / "preserve.txt").write_bytes(b"old-dsym")
            (output / "source-receipt.json").write_bytes(b"old-receipt\n")

            result = subprocess.run(
                [
                    "/bin/bash",
                    str(workspace / "script/build_and_run.sh"),
                    "--unsealed-package-only",
                ],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 95, result)
            self.assertEqual(
                (old_app / "preserve.txt").read_bytes(),
                b"old-app",
            )
            self.assertEqual(
                (old_dsym / "preserve.txt").read_bytes(),
                b"old-dsym",
            )
            self.assertEqual(
                (output / "source-receipt.json").read_bytes(),
                b"old-receipt\n",
            )
            self.assertEqual(
                list((workspace / "dist").glob(".unsealed-package-only.stage-*")),
                [],
            )

    def test_unsealed_package_only_double_publish_failure_preserves_recovery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, _ = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            output = workspace / "dist/unsealed-package-only"
            old_app = output / "AetherLink.app"
            old_dsym = output / "AetherLink.dSYM"
            old_app.mkdir(parents=True)
            old_dsym.mkdir()
            (old_app / "preserve.txt").write_bytes(b"old-app")
            (old_dsym / "preserve.txt").write_bytes(b"old-dsym")
            (output / "source-receipt.json").write_bytes(b"old-receipt\n")
            environment["FAKE_UNSEALED_PUBLISH_ROLLBACK_FAILURE"] = "1"

            result = subprocess.run(
                [
                    "/bin/bash",
                    str(workspace / "script/build_and_run.sh"),
                    "--unsealed-package-only",
                ],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 91, result)
            self.assertIn(
                "preserving unsealed recovery generation",
                result.stderr,
            )
            recoveries = [
                path
                for path in (workspace / "dist").glob(
                    ".unsealed-package-only.stage-*"
                )
                if path.is_dir()
            ]
            self.assertEqual(len(recoveries), 1)
            recovery = recoveries[0]
            self.assertEqual(
                (recovery / "AetherLink.app/preserve.txt").read_bytes(),
                b"old-app",
            )
            self.assertEqual(
                (recovery / "AetherLink.dSYM/preserve.txt").read_bytes(),
                b"old-dsym",
            )
            self.assertEqual(
                (recovery / "source-receipt.json").read_bytes(),
                b"old-receipt\n",
            )
            self.assertTrue((output / "AetherLink.app").is_dir())
            self.assertTrue((output / "AetherLink.dSYM").is_dir())
            self.assertFalse((output / "AetherLink.app/preserve.txt").exists())

        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, _ = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            fake_rm = Path(environment["PATH"].split(":", 1)[0]) / "rm"
            fake_rm.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'last_argument="${!#}"\n'
                'last_basename="${last_argument##*/}"\n'
                'if [[ "$last_basename" == .unsealed-package-only.stage-* ]]; then\n'
                "  exit 93\n"
                "fi\n"
                'exec /bin/rm "$@"\n',
                encoding="utf-8",
            )
            fake_rm.chmod(0o755)
            output = workspace / "dist/unsealed-package-only"
            old_app = output / "AetherLink.app"
            old_dsym = output / "AetherLink.dSYM"
            old_app.mkdir(parents=True)
            old_dsym.mkdir()
            (old_app / "preserve.txt").write_bytes(b"old-app")
            (old_dsym / "preserve.txt").write_bytes(b"old-dsym")
            (output / "source-receipt.json").write_bytes(b"old-receipt\n")
            environment["FAKE_UNSEALED_PUBLISH_CLEANUP_WARNING"] = "1"

            result = subprocess.run(
                [
                    "/bin/bash",
                    str(workspace / "script/build_and_run.sh"),
                    "--unsealed-package-only",
                ],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result)
            self.assertIn("injected committed cleanup warning", result.stderr)
            self.assertIn(
                "could not clean unsealed staging generation",
                result.stderr,
            )
            self.assertTrue((output / "AetherLink.app").is_dir())
            self.assertFalse((output / "AetherLink.app/preserve.txt").exists())
            retained = [
                path
                for path in (workspace / "dist").glob(
                    ".unsealed-package-only.stage-*"
                )
                if path.is_dir()
            ]
            self.assertEqual(len(retained), 1)
            self.assertEqual(
                (retained[0] / "AetherLink.app/preserve.txt").read_bytes(),
                b"old-app",
            )

    def test_unsealed_package_only_reproducibility_seam_uses_exact_fixed_flags(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, invocation_log = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            script = workspace / "script/build_and_run.sh"
            scratch = Path(temporary).resolve() / "repro-swift-scratch"
            self.set_fixed_repro_scratch_path(script, scratch)
            expected_options = (
                f"-c release --jobs 1 --scratch-path {scratch} "
                "-Xswiftc -num-threads -Xswiftc 1 "
                "-Xswiftc -file-prefix-map "
                f"-Xswiftc {workspace.resolve()}=/aetherlink/source "
                "-Xswiftc -file-compilation-dir "
                "-Xswiftc /aetherlink/source "
                "-Xswiftc -prefix-serialized-debugging-options "
                "-Xcc -working-directory "
                f"-Xcc {scratch} "
                "-Xcc -Xclang "
                "-Xcc -fdebug-compilation-dir=/aetherlink/source "
                "-Xcc -Xclang -Xcc -fdisable-module-hash "
                "-Xcc -Xclang -Xcc -fbuild-session-timestamp=0 "
                "-Xcc -Xclang -Xcc -fno-pch-timestamp "
                "-Xlinker -reproducible"
            )
            environment["AETHERLINK_REPRO_SWIFT_SCRATCH_PATH"] = str(scratch)
            environment["FAKE_SWIFT_BUILD_OPTIONS"] = expected_options

            result = subprocess.run(
                ["/bin/bash", str(script), "--unsealed-package-only"],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result)
            self.assertEqual(
                invocation_log.read_text(encoding="utf-8").splitlines(),
                [
                    f"swift build {expected_options} --product AetherLink",
                    f"swift build {expected_options} --show-bin-path",
                ],
            )

    def test_unsealed_package_only_codesign_and_launch_branches_are_disjoint(
        self,
    ) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count("/usr/bin/codesign"), 2)
        self.assertIn(
            'if is_package_only; then\n'
            '  /usr/bin/codesign --force --deep --sign - "$APP_BUNDLE"\n'
            '  /usr/bin/codesign --verify --deep --strict "$APP_BUNDLE"\n'
            "fi\n",
            source,
        )
        unsealed_case = source.split(
            "  --unsealed-package-only|unsealed-package-only)\n",
            1,
        )[1].split("    ;;", 1)[0]
        self.assertNotIn("open_app", unsealed_case)
        self.assertNotIn("codesign", unsealed_case)

    def test_package_only_reproducibility_seam_uses_exact_fixed_flags(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, invocation_log = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            script = workspace / "script/build_and_run.sh"
            scratch = Path(temporary).resolve() / "repro-swift-scratch"
            self.set_fixed_repro_scratch_path(script, scratch)
            expected_options = (
                f"-c release --jobs 1 --scratch-path {scratch} "
                "-Xswiftc -num-threads -Xswiftc 1 "
                "-Xswiftc -file-prefix-map "
                f"-Xswiftc {workspace.resolve()}=/aetherlink/source "
                "-Xswiftc -file-compilation-dir "
                "-Xswiftc /aetherlink/source "
                "-Xswiftc -prefix-serialized-debugging-options "
                "-Xcc -working-directory "
                f"-Xcc {scratch} "
                "-Xcc -Xclang "
                "-Xcc -fdebug-compilation-dir=/aetherlink/source "
                "-Xcc -Xclang -Xcc -fdisable-module-hash "
                "-Xcc -Xclang -Xcc -fbuild-session-timestamp=0 "
                "-Xcc -Xclang -Xcc -fno-pch-timestamp "
                "-Xlinker -reproducible"
            )
            environment["AETHERLINK_REPRO_SWIFT_SCRATCH_PATH"] = str(scratch)
            environment["FAKE_SWIFT_BUILD_OPTIONS"] = expected_options

            result = subprocess.run(
                ["/bin/bash", str(script), "--package-only"],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result)
            self.assertEqual(
                invocation_log.read_text(encoding="utf-8").splitlines(),
                [
                    f"swift build {expected_options} --product AetherLink",
                    f"swift build {expected_options} --show-bin-path",
                ],
            )
            self.assertEqual(expected_options.count("-working-directory"), 1)
            self.assertEqual(
                expected_options.count(
                    "-fdebug-compilation-dir=/aetherlink/source"
                ),
                1,
            )
            self.assertEqual(expected_options.count("-fno-pch-timestamp"), 1)

    def test_package_only_reproducibility_seam_rejects_unsafe_scratch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            existing = base / "existing"
            existing.mkdir()
            real_parent = base / "real-parent"
            real_parent.mkdir()
            linked_parent = base / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            cases = {
                "relative": "relative-scratch",
                "root": "/",
                "source_nested": "SOURCE_NESTED",
                "existing": existing,
                "symlink_parent": linked_parent / "scratch",
            }
            for label, configured in cases.items():
                with self.subTest(label=label):
                    workspace, environment, invocation_log = (
                        self.make_fake_package_workspace(
                            temporary=f"{temporary}/{label}",
                            resource_bundle_count=1,
                        )
                    )
                    if configured == "SOURCE_NESTED":
                        scratch: Path | str = workspace / ".repro-scratch"
                    else:
                        scratch = configured
                    script = workspace / "script/build_and_run.sh"
                    self.set_fixed_repro_scratch_path(script, scratch)
                    environment[
                        "AETHERLINK_REPRO_SWIFT_SCRATCH_PATH"
                    ] = str(scratch)

                    result = subprocess.run(
                        ["/bin/bash", str(script), "--package-only"],
                        cwd=workspace,
                        env=environment,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(result.returncode, 2, result)
                    self.assertIn(
                        "reproducible Swift scratch",
                        result.stderr,
                    )
                    self.assertFalse(invocation_log.exists())

    def test_package_only_uses_latest_shared_release_ledger_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, _ = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
                ledger_text=(
                    "build_number\tmarketing_version\n"
                    "1\t1.0.0\n"
                    "42\t1.2.3\n"
                ),
            )
            script = workspace / "script/build_and_run.sh"

            result = subprocess.run(
                ["/bin/bash", str(script), "--package-only"],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result)
            with (
                workspace
                / "dist/package-only/AetherLink.app/Contents/Info.plist"
            ).open("rb") as handle:
                info = plistlib.load(handle)
            self.assertEqual(info["CFBundleShortVersionString"], "1.2.3")
            self.assertEqual(info["CFBundleVersion"], "42")

    def test_package_only_preserves_development_bundle_and_supports_isolated_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace, environment, _ = self.make_fake_package_workspace(
                temporary,
                resource_bundle_count=1,
            )
            development_app = workspace / "dist/AetherLink.app"
            development_app.mkdir(parents=True)
            sentinel = development_app / "running-build.txt"
            sentinel.write_bytes(b"preserve-running-build")
            before = sentinel.read_bytes()
            custom_output = workspace / "dist/release-package"
            environment["AETHERLINK_PACKAGE_OUTPUT_ROOT"] = str(
                custom_output
            )

            result = subprocess.run(
                [
                    "/bin/bash",
                    str(workspace / "script/build_and_run.sh"),
                    "--package-only",
                ],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result)
            self.assertEqual(sentinel.read_bytes(), before)
            self.assertTrue(
                (custom_output / "AetherLink.app/Contents/Info.plist").is_file()
            )
            self.assertFalse(
                (workspace / "dist/package-only/AetherLink.app").exists()
            )

    def test_package_only_rejects_unsafe_output_roots_before_toolchain(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            cases = {
                "relative": Path("dist/package-only"),
                "legacy_bundle_parent": None,
                "development_bundle_root": None,
                "other_bundle_root": None,
                "uppercase_bundle_root": None,
                "tab_control": None,
                "vertical_tab_control": None,
                "form_feed_control": None,
                "delete_control": None,
                "outside_source": base / "outside",
                "nested": None,
            }
            for label, configured in cases.items():
                with self.subTest(label=label):
                    workspace, environment, invocation_log = (
                        self.make_fake_package_workspace(
                            f"{temporary}/{label}",
                            resource_bundle_count=1,
                        )
                    )
                    if label == "legacy_bundle_parent":
                        configured = workspace / "dist"
                    elif label == "development_bundle_root":
                        configured = workspace / "dist/AetherLink.app"
                    elif label == "other_bundle_root":
                        configured = workspace / "dist/LocalAgentBridge.app"
                    elif label == "uppercase_bundle_root":
                        configured = workspace / "dist/Other.APP"
                    elif label == "tab_control":
                        configured = workspace / "dist/bad\troot"
                    elif label == "vertical_tab_control":
                        configured = workspace / "dist/bad\vroot"
                    elif label == "form_feed_control":
                        configured = workspace / "dist/bad\froot"
                    elif label == "delete_control":
                        configured = workspace / "dist/bad\x7froot"
                    elif label == "nested":
                        configured = workspace / "dist/nested/output"
                    environment["AETHERLINK_PACKAGE_OUTPUT_ROOT"] = str(
                        configured
                    )

                    result = subprocess.run(
                        [
                            "/bin/bash",
                            str(workspace / "script/build_and_run.sh"),
                            "--package-only",
                        ],
                        cwd=workspace,
                        env=environment,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(result.returncode, 2, result)
                    self.assertIn("package output root", result.stderr)
                    self.assertFalse(invocation_log.exists())

    def test_invalid_release_ledger_fails_before_toolchain_side_effects(self) -> None:
        invalid_ledgers = {
            "missing_entry": b"build_number\tmarketing_version\n",
            "duplicate_build": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\n"
                b"1\t1.0.1\n"
            ),
            "version_regression": (
                b"build_number\tmarketing_version\n"
                b"1\t1.1.0\n"
                b"2\t1.0.0\n"
            ),
            "extra_field": (
                b"build_number\tmarketing_version\n1\t1.0.0\textra\n"
            ),
            "nul": b"build_number\tmarketing_version\n1\t1.0.0\x00\n",
            "vertical_tab_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x0b2\t1.0.1\n"
            ),
            "form_feed_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x0c2\t1.0.1\n"
            ),
            "file_separator_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x1c2\t1.0.1\n"
            ),
            "group_separator_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x1d2\t1.0.1\n"
            ),
            "record_separator_as_separator": (
                b"build_number\tmarketing_version\n"
                b"1\t1.0.0\x1e2\t1.0.1\n"
            ),
            "delete_control": (
                b"build_number\tmarketing_version\n1\t1.0.0\x7f\n"
            ),
            "non_ascii": (
                b"build_number\tmarketing_version\n1\t1.0.0\xc2\xa0\n"
            ),
        }

        for label, ledger_bytes in invalid_ledgers.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                workspace, environment, invocation_log = (
                    self.make_fake_package_workspace(
                        temporary,
                        resource_bundle_count=1,
                        ledger_bytes=ledger_bytes,
                    )
                )
                script = workspace / "script/build_and_run.sh"

                result = subprocess.run(
                    ["/bin/bash", str(script), "--package-only"],
                    cwd=workspace,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 2, result)
                self.assertIn("release version ledger", result.stderr)
                self.assertFalse(invocation_log.exists())
                self.assertFalse((workspace / "dist").exists())

    def test_package_only_rejects_missing_or_ambiguous_resource_bundle(self) -> None:
        for resource_bundle_count in (0, 2):
            with self.subTest(resource_bundle_count=resource_bundle_count):
                with tempfile.TemporaryDirectory() as temporary:
                    workspace, environment, _ = self.make_fake_package_workspace(
                        temporary,
                        resource_bundle_count=resource_bundle_count,
                    )
                    script = workspace / "script/build_and_run.sh"
                    result = subprocess.run(
                        ["/bin/bash", str(script), "--package-only"],
                        cwd=workspace,
                        env=environment,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(result.returncode, 1, result)
                    self.assertIn(
                        "expected exactly one SwiftPM resource bundle",
                        result.stderr,
                    )
                    self.assertIn(
                        f"found {resource_bundle_count}",
                        result.stderr,
                    )


if __name__ == "__main__":
    unittest.main()
