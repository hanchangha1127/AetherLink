#!/usr/bin/env python3
"""Regression tests for deterministic local release evidence archives."""

from __future__ import annotations

import os
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import script.check_release_artifact_archive as readback_module
import script.package_release_artifacts as builder_module
from script.check_release_artifact_archive import (
    ReleaseArchiveVerificationError,
    parse_aapt2_badging as parse_readback_aapt2_badging,
    parse_bundletool_manifest as parse_readback_bundletool_manifest,
    parse_gradle_lockfile as parse_readback_gradle_lockfile,
    canonicalize_r8_line_artifact as canonicalize_readback_r8_lines,
    canonicalize_r8_mapping_prt as canonicalize_readback_r8_prt,
    parse_canonical_json,
    require_exact_int,
    validate_member_path as validate_readback_member_path,
    verify_canonical_container,
)
from script.package_release_artifacts import (
    ArchiveMember,
    ReleaseArchiveError,
    canonical_json_bytes,
    canonicalize_r8_line_artifact as canonicalize_builder_r8_lines,
    canonicalize_r8_mapping_prt as canonicalize_builder_r8_prt,
    member_record,
    parse_aapt2_badging as parse_builder_aapt2_badging,
    parse_bundletool_manifest as parse_builder_bundletool_manifest,
    parse_gradle_lockfile as parse_builder_gradle_lockfile,
    publish_archive_directory,
    validate_member_path,
    write_canonical_zip,
)


class ReleaseArtifactArchiveTests(unittest.TestCase):
    AAPT2_BADGING = (
        "package: name='com.localagentbridge.android' versionCode='1' "
        "versionName='1.0.0' platformBuildVersionName='16'\n"
        "minSdkVersion:'26'\n"
        "targetSdkVersion:'36'\n"
        "native-code: 'arm64-v8a'\n"
    )
    BUNDLETOOL_MANIFEST = (
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
        'android:versionCode="1" android:versionName="1.0.0" '
        'package="com.localagentbridge.android">'
        '<uses-sdk android:minSdkVersion="26" '
        'android:targetSdkVersion="36"/>'
        "</manifest>"
    )
    GRADLE_LOCKFILE = (
        "# This is a Gradle generated file for dependency locking.\n"
        "# Manual edits can break the build and are not advised.\n"
        "# This file is expected to be part of source control.\n"
        "com.example:alpha:1.0=releaseCompileClasspath,"
        "releaseRuntimeClasspath\n"
        "com.example:beta:2.0=releaseRuntimeClasspath\n"
        "empty=releaseAnnotationProcessorClasspath\n"
    ).encode("ascii")
    EMPTY_ONLY_GRADLE_LOCKFILE = (
        "# This is a Gradle generated file for dependency locking.\n"
        "# Manual edits can break the build and are not advised.\n"
        "# This file is expected to be part of source control.\n"
        "empty=incomingCatalogForLibs0\n"
    ).encode("ascii")

    def fixture(
        self,
    ) -> tuple[list[ArchiveMember], bytes]:
        members = [
            ArchiveMember("payload/a.txt", b"alpha\n", 0o644),
            ArchiveMember("payload/run", b"#!/bin/sh\nexit 0\n", 0o755),
        ]
        manifest = {
            "members": [member_record(member) for member in members],
            "schemaVersion": 1,
        }
        return members, canonical_json_bytes(manifest)

    def test_canonical_zip_is_reproducible_and_reads_back(self) -> None:
        members, manifest = self.fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.zip"
            second = root / "second.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)

            write_canonical_zip(first, manifest, members)
            write_canonical_zip(second, manifest, members)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            parsed, payload, modes = verify_canonical_container(first, external)
            self.assertEqual(parsed["schemaVersion"], 1)
            self.assertEqual(payload["payload/a.txt"], b"alpha\n")
            self.assertEqual(modes["payload/run"], 0o755)

    def test_r8_unordered_line_artifacts_are_canonicalized(self) -> None:
        source = b"zeta\nalpha\nbeta\n"
        expected = b"alpha\nbeta\nzeta\n"
        self.assertEqual(
            canonicalize_builder_r8_lines(source, "fixture"),
            expected,
        )
        self.assertEqual(
            canonicalize_readback_r8_lines(source, "fixture"),
            expected,
        )
        for invalid in (
            b"",
            b"alpha",
            b"alpha\r\n",
            b"alpha\nalpha\n",
            b"alpha\n\n",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ReleaseArchiveError):
                    canonicalize_builder_r8_lines(invalid, "fixture")
                with self.assertRaises(
                    ReleaseArchiveVerificationError
                ):
                    canonicalize_readback_r8_lines(
                        invalid,
                        "fixture",
                    )

    def test_r8_mapping_partition_zip_is_canonicalized(self) -> None:
        def make_zip(
            entries: list[tuple[str, bytes]],
            timestamp: tuple[int, int, int, int, int, int],
        ) -> bytes:
            output = io.BytesIO()
            with zipfile.ZipFile(
                output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                for name, data in entries:
                    info = zipfile.ZipInfo(name, timestamp)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data)
            return output.getvalue()

        first = make_zip(
            [("zeta", b"z"), ("alpha", b"a")],
            (2025, 1, 2, 3, 4, 6),
        )
        second = make_zip(
            [("alpha", b"a"), ("zeta", b"z")],
            (2026, 7, 8, 9, 10, 12),
        )
        builder_first = canonicalize_builder_r8_prt(
            first,
            "fixture",
        )
        builder_second = canonicalize_builder_r8_prt(
            second,
            "fixture",
        )
        self.assertEqual(builder_first, builder_second)
        self.assertEqual(
            canonicalize_readback_r8_prt(first, "fixture"),
            builder_first,
        )
        self.assertEqual(
            canonicalize_readback_r8_prt(builder_first, "fixture"),
            builder_first,
        )

    def test_readback_rejects_payload_tampering(self) -> None:
        members, manifest = self.fixture()
        tampered = [
            ArchiveMember("payload/a.txt", b"tampered\n", 0o644),
            members[1],
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)
            write_canonical_zip(archive, manifest, tampered)

            with self.assertRaisesRegex(
                ReleaseArchiveVerificationError,
                "byte identity differs",
            ):
                verify_canonical_container(archive, external)

    def test_readback_rejects_noncanonical_zip_metadata(self) -> None:
        members, manifest = self.fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)
            with zipfile.ZipFile(
                archive,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as output:
                output.writestr("manifest.json", manifest)
                for member in members:
                    output.writestr(member.path, member.data)

            with self.assertRaises(ReleaseArchiveVerificationError):
                verify_canonical_container(archive, external)

    def test_readback_reports_unicode_zip_member_as_a_controlled_error(self) -> None:
        manifest = canonical_json_bytes({"members": [], "schemaVersion": 1})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive.zip"
            external = root / "manifest.json"
            external.write_bytes(manifest)
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("manifest.json", manifest)
                output.writestr("payload/한글", b"not canonical")

            with self.assertRaises(ReleaseArchiveVerificationError):
                verify_canonical_container(archive, external)

    def test_readback_rejects_unsorted_or_extended_member_records(self) -> None:
        members, _ = self.fixture()
        invalid_manifests = (
            {
                "members": [
                    member_record(members[1]),
                    member_record(members[0]),
                ],
                "schemaVersion": 1,
            },
            {
                "members": [
                    {
                        **member_record(members[0]),
                        "unexpected": "field",
                    },
                    member_record(members[1]),
                ],
                "schemaVersion": 1,
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, manifest_value in enumerate(invalid_manifests):
                manifest = canonical_json_bytes(manifest_value)
                archive = root / f"archive-{index}.zip"
                external = root / f"manifest-{index}.json"
                external.write_bytes(manifest)
                write_canonical_zip(archive, manifest, members)
                with self.assertRaises(ReleaseArchiveVerificationError):
                    verify_canonical_container(archive, external)

    def test_member_paths_reject_escape_absolute_unicode_and_backslash(self) -> None:
        invalid = (
            "../escape",
            "/absolute",
            "payload/../escape",
            "payload\\file",
            "payload/한글",
            "",
        )
        for path in invalid:
            with self.subTest(path=path):
                with self.assertRaises((ReleaseArchiveError, ValueError)):
                    validate_member_path(path)
                with self.assertRaises(
                    (ReleaseArchiveVerificationError, ValueError)
                ):
                    validate_readback_member_path(path)

    def test_publish_is_idempotent_and_never_overwrites_different_bytes(
        self,
    ) -> None:
        manifest = canonical_json_bytes({"members": [], "schemaVersion": 1})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            source = root / "archive.zip"
            source.write_bytes(b"first archive")

            directory, existed = publish_archive_directory(
                output,
                "aetherlink-1.0.0+1-local-v1",
                source,
                manifest,
            )
            self.assertFalse(existed)
            first_archive = (
                directory / "aetherlink-1.0.0+1-local-v1.zip"
            ).read_bytes()

            same_directory, existed = publish_archive_directory(
                output,
                "aetherlink-1.0.0+1-local-v1",
                source,
                manifest,
            )
            self.assertTrue(existed)
            self.assertEqual(same_directory, directory)

            source.write_bytes(b"different archive")
            with self.assertRaisesRegex(
                ReleaseArchiveError,
                "increment the shared build number",
            ):
                publish_archive_directory(
                    output,
                    "aetherlink-1.0.0+1-local-v1",
                    source,
                    manifest,
                )
            self.assertEqual(
                (
                    directory / "aetherlink-1.0.0+1-local-v1.zip"
                ).read_bytes(),
                first_archive,
            )

    def test_json_rejects_duplicate_keys_and_noncanonical_encoding(self) -> None:
        invalid_documents = (
            b'{"schemaVersion":1,"schemaVersion":1}\n',
            b'{ "schemaVersion":1}\n',
            b'{"schemaVersion":NaN}\n',
            b"\xef\xbb\xbf{}\n",
            b"{}\r\n",
        )
        for document in invalid_documents:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_canonical_json(document, "fixture")

    def test_integer_fields_reject_boolean_and_float_confusion(self) -> None:
        for value in (True, False, 1.0, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ReleaseArchiveVerificationError):
                    require_exact_int(value, "fixture.count")
        self.assertEqual(require_exact_int(1, "fixture.count"), 1)

    def test_builder_and_readback_parse_exact_apk_badging(self) -> None:
        expected = {
            "applicationId": "com.localagentbridge.android",
            "minSdk": 26,
            "nativeAbis": ["arm64-v8a"],
            "targetSdk": 36,
            "versionCode": 1,
            "versionName": "1.0.0",
        }
        self.assertEqual(
            parse_builder_aapt2_badging(self.AAPT2_BADGING),
            expected,
        )
        self.assertEqual(
            parse_readback_aapt2_badging(self.AAPT2_BADGING),
            expected,
        )

    def test_apk_badging_parsers_reject_missing_duplicate_and_nondecimal_fields(
        self,
    ) -> None:
        invalid = (
            self.AAPT2_BADGING.replace("minSdkVersion:'26'\n", ""),
            self.AAPT2_BADGING + "targetSdkVersion:'36'\n",
            self.AAPT2_BADGING.replace("versionCode='1'", "versionCode='01'"),
            self.AAPT2_BADGING.replace(
                "native-code: 'arm64-v8a'",
                "native-code:",
            ),
        )
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveError):
                    parse_builder_aapt2_badging(document)
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_readback_aapt2_badging(document)

    def test_builder_and_readback_parse_exact_bundletool_manifest(self) -> None:
        expected = {
            "applicationId": "com.localagentbridge.android",
            "minSdk": 26,
            "targetSdk": 36,
            "versionCode": 1,
            "versionName": "1.0.0",
        }
        self.assertEqual(
            parse_builder_bundletool_manifest(self.BUNDLETOOL_MANIFEST),
            expected,
        )
        self.assertEqual(
            parse_readback_bundletool_manifest(self.BUNDLETOOL_MANIFEST),
            expected,
        )

    def test_bundletool_manifest_parsers_reject_noncanonical_identity(
        self,
    ) -> None:
        invalid = (
            self.BUNDLETOOL_MANIFEST.replace(
                '<uses-sdk android:minSdkVersion="26" '
                'android:targetSdkVersion="36"/>',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                "</manifest>",
                '<uses-sdk android:minSdkVersion="26" '
                'android:targetSdkVersion="36"/></manifest>',
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                'android:versionCode="1"',
                'android:versionCode="01"',
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' android:versionName="1.0.0"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' package="com.localagentbridge.android"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                'android:minSdkVersion="26"',
                'android:minSdkVersion="026"',
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                ' android:targetSdkVersion="36"',
                "",
            ),
            self.BUNDLETOOL_MANIFEST.replace(
                "<manifest ",
                "<application ",
            ).replace("</manifest>", "</application>"),
            self.BUNDLETOOL_MANIFEST.removesuffix("</manifest>"),
        )
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveError):
                    parse_builder_bundletool_manifest(document)
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_readback_bundletool_manifest(document)

    def test_bundletool_runtime_classpath_is_closed_and_version_pinned(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundletool = root / "bundletool-1.18.3.jar"
            dependency = root / "dependency.jar"
            wrong_bundletool = root / "bundletool-1.18.2.jar"
            non_jar = root / "dependency.txt"
            for path in (
                bundletool,
                dependency,
                wrong_bundletool,
                non_jar,
            ):
                path.write_bytes(b"fixture")
            valid = os.pathsep.join((str(bundletool), str(dependency)))
            invalid = (
                "",
                f"noise\nAETHERLINK_BUNDLETOOL_CLASSPATH={valid}",
                os.pathsep.join((str(bundletool), str(bundletool))),
                os.pathsep.join((str(wrong_bundletool), str(dependency))),
                os.pathsep.join((str(bundletool), str(non_jar))),
            )
            for module, error_type in modules:
                module.bundletool_runtime_classpath.cache_clear()
                with mock.patch.object(
                    module,
                    "run_text",
                    return_value=(
                        "AETHERLINK_BUNDLETOOL_CLASSPATH=" + valid
                    ),
                ) as run_text:
                    self.assertEqual(
                        module.bundletool_runtime_classpath(root),
                        valid,
                    )
                    command = run_text.call_args.args[0]
                    self.assertEqual(command[1:5], [
                        "--offline",
                        "--no-daemon",
                        "--console=plain",
                        "--quiet",
                    ])
                    self.assertEqual(
                        command[-1],
                        "printBundletoolRuntimeClasspath",
                    )
                for output in invalid:
                    module.bundletool_runtime_classpath.cache_clear()
                    with self.subTest(
                        module=module.__name__,
                        output=output,
                    ), mock.patch.object(
                        module,
                        "run_text",
                        return_value=output,
                    ):
                        with self.assertRaises(error_type):
                            module.bundletool_runtime_classpath(root)
                module.bundletool_runtime_classpath.cache_clear()

    def test_bundletool_version_is_exact_and_aab_temp_file_is_removed(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        for module, error_type in modules:
            with mock.patch.object(
                module,
                "run_bundletool",
                return_value="1.18.3",
            ):
                self.assertEqual(module.bundletool_version(), "1.18.3")
            for version in ("1.18.2", "1.18.3\nunexpected", ""):
                with self.subTest(
                    module=module.__name__,
                    version=version,
                ), mock.patch.object(
                    module,
                    "run_bundletool",
                    return_value=version,
                ):
                    with self.assertRaises(error_type):
                        module.bundletool_version()

            temporary_paths: list[Path] = []

            def fake_run(
                arguments: list[str],
                *,
                root: Path,
            ) -> str:
                self.assertEqual(arguments[:2], ["dump", "manifest"])
                self.assertEqual(arguments[-1], "--module=base")
                bundle_path = Path(
                    arguments[2].removeprefix("--bundle=")
                )
                self.assertEqual(bundle_path.read_bytes(), b"fixture-aab")
                temporary_paths.append(bundle_path)
                return self.BUNDLETOOL_MANIFEST

            with mock.patch.object(
                module,
                "run_bundletool",
                side_effect=fake_run,
            ):
                self.assertEqual(
                    module.inspect_aab_manifest(b"fixture-aab"),
                    {
                        "applicationId": "com.localagentbridge.android",
                        "minSdk": 26,
                        "targetSdk": 36,
                        "versionCode": 1,
                        "versionName": "1.0.0",
                    },
                )
            self.assertTrue(temporary_paths)
            self.assertTrue(
                all(not path.exists() for path in temporary_paths)
            )

            failed_paths: list[Path] = []

            def fail_run(
                arguments: list[str],
                *,
                root: Path,
            ) -> str:
                failed_paths.append(
                    Path(arguments[2].removeprefix("--bundle="))
                )
                raise error_type("fixture bundletool failure")

            with mock.patch.object(
                module,
                "run_bundletool",
                side_effect=fail_run,
            ):
                with self.assertRaises(error_type):
                    module.inspect_aab_manifest(b"fixture-aab")
            self.assertTrue(failed_paths)
            self.assertTrue(all(not path.exists() for path in failed_paths))

    def test_builder_and_readback_parse_exact_gradle_lockfile(self) -> None:
        expected = {
            "configurationCount": 3,
            "emptyConfigurationCount": 1,
            "moduleCount": 2,
        }
        self.assertEqual(
            parse_builder_gradle_lockfile(
                self.GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )
        self.assertEqual(
            parse_readback_gradle_lockfile(
                self.GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )

    def test_gradle_lockfile_parsers_reject_noncanonical_shapes(
        self,
    ) -> None:
        invalid = (
            self.GRADLE_LOCKFILE.rstrip(b"\n"),
            self.GRADLE_LOCKFILE.replace(b"\n", b"\r\n"),
            self.GRADLE_LOCKFILE.replace(
                b"com.example:alpha:1.0=releaseCompileClasspath,"
                b"releaseRuntimeClasspath\n"
                b"com.example:beta:2.0=releaseRuntimeClasspath\n",
                b"com.example:beta:2.0=releaseRuntimeClasspath\n"
                b"com.example:alpha:1.0=releaseCompileClasspath,"
                b"releaseRuntimeClasspath\n",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"com.example:beta:2.0=releaseRuntimeClasspath",
                b"com.example:alpha:1.0=releaseRuntimeClasspath",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"releaseCompileClasspath,releaseRuntimeClasspath",
                b"releaseRuntimeClasspath,releaseCompileClasspath",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"empty=releaseAnnotationProcessorClasspath\n",
                b"empty=releaseAnnotationProcessorClasspath\n"
                b"com.example:zeta:3.0=releaseRuntimeClasspath\n",
            ),
            self.GRADLE_LOCKFILE.replace(
                b"com.example:beta:2.0=releaseRuntimeClasspath",
                b"com.example:beta:2.0=",
            ),
            b"\xef\xbb\xbf" + self.GRADLE_LOCKFILE,
            self.EMPTY_ONLY_GRADLE_LOCKFILE.replace(
                b"empty=incomingCatalogForLibs0\n",
                b"empty=\n",
            ),
        )
        for document in invalid:
            with self.subTest(document=document):
                with self.assertRaises(ReleaseArchiveError):
                    parse_builder_gradle_lockfile(document, "fixture")
                with self.assertRaises(ReleaseArchiveVerificationError):
                    parse_readback_gradle_lockfile(document, "fixture")

    def test_gradle_lockfile_parsers_accept_empty_only_configuration(
        self,
    ) -> None:
        expected = {
            "configurationCount": 1,
            "emptyConfigurationCount": 1,
            "moduleCount": 0,
        }
        self.assertEqual(
            parse_builder_gradle_lockfile(
                self.EMPTY_ONLY_GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )
        self.assertEqual(
            parse_readback_gradle_lockfile(
                self.EMPTY_ONLY_GRADLE_LOCKFILE,
                "fixture",
            ),
            expected,
        )

    def test_dependency_lock_inventory_tracks_gradle_and_swiftpm_state(
        self,
    ) -> None:
        modules = (
            (builder_module, ReleaseArchiveError),
            (readback_module, ReleaseArchiveVerificationError),
        )
        for module, error_type in modules:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for relative in module.GRADLE_LOCK_PATHS:
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(self.GRADLE_LOCKFILE)
                with mock.patch.object(
                    module,
                    "swift_package_dump",
                    return_value={
                        "dependencies": [],
                        "name": "AetherLink",
                    },
                ):
                    metadata = module.dependency_locking_metadata(root)
                    self.assertEqual(
                        len(metadata["gradle"]["lockFiles"]),
                        len(module.GRADLE_LOCK_PATHS),
                    )
                    self.assertEqual(
                        metadata["gradle"]["ignoredDependencies"],
                        [
                            "org.jetbrains.kotlin:"
                            "kotlin-stdlib-common"
                        ],
                    )
                    self.assertEqual(
                        metadata["swiftPackageManager"],
                        {
                            "externalDependencyCount": 0,
                            "packageResolved": None,
                            "status": (
                                "not-applicable-no-external-dependencies"
                            ),
                        },
                    )

                    (root / "Package.resolved").write_bytes(b"stale\n")
                    with self.assertRaises(error_type):
                        module.dependency_locking_metadata(root)

                (root / "Package.resolved").unlink()
                with mock.patch.object(
                    module,
                    "swift_package_dump",
                    return_value={
                        "dependencies": [{"sourceControl": []}],
                        "name": "AetherLink",
                    },
                ):
                    with self.assertRaises(error_type):
                        module.dependency_locking_metadata(root)
                    resolved = root / "Package.resolved"
                    resolved.write_bytes(b'{"version":3}\n')
                    metadata = module.dependency_locking_metadata(root)
                    self.assertEqual(
                        metadata["swiftPackageManager"][
                            "externalDependencyCount"
                        ],
                        1,
                    )
                    self.assertEqual(
                        metadata["swiftPackageManager"]["packageResolved"][
                            "path"
                        ],
                        "Package.resolved",
                    )

    def test_release_script_requires_strict_read_only_dependency_locks(
        self,
    ) -> None:
        release_script = (
            Path(__file__).resolve().parents[1]
            / "script/build_release_artifacts.sh"
        ).read_text(encoding="utf-8")
        root_build = (
            Path(__file__).resolve().parents[1]
            / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "-PaetherlinkStrictReleaseDependencyLocks=true",
            release_script,
        )
        self.assertNotIn("--write-locks", release_script)
        for clean_task in (
            ":app:clean",
            ":core:pairing:clean",
            ":core:protocol:clean",
            ":core:transport:clean",
        ):
            self.assertIn(clean_task, release_script)
        self.assertIn("lockAllConfigurations()", root_build)
        self.assertIn("lockMode.set(LockMode.STRICT)", root_build)
        self.assertIn(
            "resolutionStrategy.activateDependencyLocking()",
            root_build,
        )
        self.assertIn(
            '"org.jetbrains.kotlin:kotlin-stdlib-common"',
            root_build,
        )
        self.assertIn('"buildscript-gradle.lockfile"', root_build)
        self.assertIn('"settings-gradle.lockfile"', root_build)


if __name__ == "__main__":
    unittest.main()
