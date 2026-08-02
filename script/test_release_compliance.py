#!/usr/bin/env python3
"""Regression tests for frozen Build 7 and deterministic Build 8 compliance."""

from __future__ import annotations

import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import script.check_release_compliance as readback
import script.generate_release_compliance as generator
from script.check_release_compliance import (
    CATALOG_MEMBER,
    CATALOG_SOURCE,
    ComplianceVerificationError,
    METADATA_MEMBER,
    METADATA_SOURCE,
    NOTICE_MEMBER,
    SPDX_MEMBER,
    expected_spdx_expression,
    parse_canonical_json as parse_readback_json,
    parse_current_locks,
    validate_catalog as validate_readback_catalog,
    verify_release_compliance,
)
from script.generate_release_compliance import (
    ComplianceError,
    build_release_compliance,
    canonical_json_bytes,
    load_catalog,
    load_release_metadata,
    parse_canonical_json,
    spdx_declared_expression,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SNAPSHOT_SHA256 = "1" * 64


class ReleaseComplianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog, cls.catalog_bytes, cls.packages = load_catalog()
        cls.metadata = load_release_metadata()
        cls.manifest_lock_files = cls.catalog["gradleLockFiles"]

    @staticmethod
    def _write_gradle_universe_fixture(root: Path) -> None:
        for relative in generator.GRADLE_BUILD_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"// fixture\n")
        (root / generator.GRADLE_SETTINGS_PATH).write_bytes(
            (ROOT / generator.GRADLE_SETTINGS_PATH).read_bytes()
        )
        for relative in generator.GRADLE_LOCK_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"empty=\n")

    def test_checked_in_catalog_exactly_covers_current_locks(self) -> None:
        current = parse_current_locks(ROOT)
        self.assertEqual(len(current), 350)
        self.assertEqual(len(self.packages), 350)
        self.assertEqual(
            {package["coordinate"] for package in self.packages},
            set(current),
        )
        self.assertEqual(len(self.catalog["pomRecords"]), 379)

    def test_dependency_input_universe_is_closed_in_both_implementations(
        self,
    ) -> None:
        self.assertEqual(
            generator.discovered_gradle_lock_paths(ROOT),
            generator.GRADLE_LOCK_PATHS,
        )
        self.assertEqual(
            readback.discovered_gradle_lock_paths(ROOT),
            readback.GRADLE_LOCK_PATHS,
        )
        self.assertEqual(generator.swift_external_dependency_count(ROOT), 0)
        self.assertEqual(readback.swift_external_dependency_count(ROOT), 0)

    def test_unexpected_or_missing_gradle_lock_is_rejected_independently(
        self,
    ) -> None:
        validators = (
            generator.validate_gradle_lock_path_universe,
            readback.validate_gradle_lock_path_universe,
        )
        error_types = (ComplianceError, ComplianceVerificationError)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_gradle_universe_fixture(root)
            for validator in validators:
                validator(root)

            def assert_rejected(mutation: str) -> None:
                for validator, error_type in zip(validators, error_types):
                    with self.subTest(
                        validator=validator.__module__,
                        mutation=mutation,
                    ):
                        with self.assertRaises(error_type):
                            validator(root)

            extra = root / "apps/android/extra/gradle.lockfile"
            extra.parent.mkdir(parents=True)
            extra.write_bytes(b"empty=\n")
            (extra.parent / "build.gradle.kts").write_bytes(b"// fixture\n")
            assert_rejected("extra module")

            extra.unlink()
            (extra.parent / "build.gradle.kts").unlink()
            missing = root / generator.GRADLE_LOCK_PATHS[0]
            missing_bytes = missing.read_bytes()
            missing.unlink()
            assert_rejected("missing module lock")
            missing.write_bytes(missing_bytes)

            settings = root / generator.GRADLE_SETTINGS_PATH
            settings_bytes = settings.read_bytes()
            settings.write_bytes(
                settings_bytes
                + b'includeBuild /* comment */ ("../external")\n'
            )
            assert_rejected("comment-obscured external included build")
            settings.write_bytes(settings_bytes)

            settings.write_bytes(
                settings_bytes.replace(
                    b'file("apps/android/app")',
                    b'file("../external-app")',
                    1,
                )
            )
            assert_rejected("external project directory")
            settings.write_bytes(settings_bytes)

            unexpected_build = root / "tools/fixture/build.gradle.kts"
            unexpected_build.parent.mkdir(parents=True)
            unexpected_build.write_bytes(b"// fixture\n")
            assert_rejected("unexpected repository Gradle project")
            unexpected_build.unlink()

            symlink_target = root / "symlink-target"
            symlink_target.mkdir()
            (root / "unexpected-symlink").symlink_to(
                symlink_target,
                target_is_directory=True,
            )
            assert_rejected("unexpected symlink directory")

        for implementation, error_type in (
            (generator, ComplianceError),
            (readback, ComplianceVerificationError),
        ):
            with self.subTest(
                implementation=implementation.__name__,
                mutation="walk error",
            ):
                with mock.patch.object(
                    implementation.os,
                    "walk",
                    side_effect=OSError("fixture walk failure"),
                ):
                    with self.assertRaises(error_type):
                        implementation.validate_gradle_project_universe(ROOT)

    def test_swift_external_dependency_is_rejected_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Package.swift").write_bytes(b"// swift-tools-version: 5.9\n")
            payloads = {
                "package dependency": {
                    "dependencies": [{"identity": "fixture-external-package"}],
                    "targets": [],
                },
                "URL binary target": {
                    "dependencies": [],
                    "targets": [
                        {
                            "name": "FixtureBinary",
                            "type": "binary",
                            "url": "https://example.invalid/fixture.zip",
                        }
                    ],
                },
            }
            for mutation, package in payloads.items():
                completed = subprocess.CompletedProcess(
                    args=["swift", "package", "dump-package"],
                    returncode=0,
                    stdout=json.dumps(
                        package,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                    stderr=b"",
                )

                def run(*_args: object, **_kwargs: object) -> object:
                    return completed

                with self.subTest(mutation=mutation, implementation="generator"):
                    with self.assertRaises(ComplianceError):
                        generator.swift_external_dependency_count(root, run=run)
                with self.subTest(mutation=mutation, implementation="readback"):
                    with self.assertRaises(ComplianceVerificationError):
                        readback.swift_external_dependency_count(root, run=run)

    def test_swift_resolution_file_is_rejected_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Package.swift").write_bytes(b"// swift-tools-version: 5.9\n")
            (root / "Package.resolved").write_bytes(b"{}\n")
            with self.assertRaises(ComplianceError):
                generator.swift_external_dependency_count(root)
            with self.assertRaises(ComplianceVerificationError):
                readback.swift_external_dependency_count(root)

    def test_catalog_is_canonical_and_has_stable_identity(self) -> None:
        self.assertEqual(
            parse_canonical_json(
                self.catalog_bytes,
                "catalog",
            ),
            self.catalog,
        )
        self.assertEqual(
            canonical_json_bytes(self.catalog),
            self.catalog_bytes,
        )
        self.assertEqual(
            hashlib.sha256(self.catalog_bytes).hexdigest(),
            "1f97b74e794e5e2b3092cc31ce8c67f634a299989658feca597bc301b67dcda5",
        )

    def test_offline_render_is_deterministic(self) -> None:
        with mock.patch.object(
            generator.urllib.request,
            "urlopen",
            side_effect=AssertionError("release render attempted network access"),
        ):
            first_members, first_summary = build_release_compliance(
                marketing_version="1.0.0",
                build_number=8,
                source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
            )
            second_members, second_summary = build_release_compliance(
                marketing_version="1.0.0",
                build_number=8,
                source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
            )
        self.assertEqual(first_members, second_members)
        self.assertEqual(first_summary, second_summary)
        self.assertEqual(
            {path for path, _ in first_members},
            {
                CATALOG_MEMBER,
                METADATA_MEMBER,
                NOTICE_MEMBER,
                SPDX_MEMBER,
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            rendered = root / "rendered"
            generator.write_release_compliance_members(
                rendered,
                first_members,
            )
            for member_path, expected in first_members:
                self.assertEqual(
                    rendered.joinpath(
                        *Path(member_path).parts
                    ).read_bytes(),
                    expected,
                )

            outside = root / "outside"
            outside.mkdir()
            linked_output = root / "linked-output"
            linked_output.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ComplianceError):
                generator.write_release_compliance_members(
                    linked_output,
                    first_members,
                )
            self.assertEqual(tuple(outside.iterdir()), ())

            leaf_target = root / "outside-leaf"
            leaf_target.write_bytes(b"preserve\n")
            leaf_output = root / "leaf-output"
            (leaf_output / "compliance").mkdir(parents=True)
            leaf = leaf_output / SPDX_MEMBER
            leaf.symlink_to(leaf_target)
            with self.assertRaises(ComplianceError):
                generator.write_release_compliance_members(
                    leaf_output,
                    first_members,
                )
            self.assertEqual(leaf_target.read_bytes(), b"preserve\n")

    def test_independent_readback_reconstructs_every_generated_byte(self) -> None:
        members, summary = build_release_compliance(
            marketing_version="1.0.0",
            build_number=8,
            source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
        )
        payload = dict(members)
        source_identities = {
            CATALOG_SOURCE: (
                len(payload[CATALOG_MEMBER]),
                hashlib.sha256(payload[CATALOG_MEMBER]).hexdigest(),
            ),
            METADATA_SOURCE: (
                len(payload[METADATA_MEMBER]),
                hashlib.sha256(payload[METADATA_MEMBER]).hexdigest(),
            ),
        }
        verify_release_compliance(
            compliance=summary,
            payload=payload,
            source_identities=source_identities,
            manifest_lock_files=self.manifest_lock_files,
            marketing_version="1.0.0",
            build_number=8,
            source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
            root=ROOT,
            compare_current_source=True,
        )

    def test_v2_spdx_has_all_configuration_derived_roles(self) -> None:
        members, summary = build_release_compliance(
            marketing_version="1.0.0",
            build_number=8,
            source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
        )
        spdx = parse_readback_json(dict(members)[SPDX_MEMBER], SPDX_MEMBER)
        packages = spdx["packages"]
        relationships = spdx["relationships"]
        self.assertEqual(len(packages), 351)
        self.assertEqual(len(relationships), 692)
        self.assertEqual(summary["spdx"]["packageCount"], 351)
        self.assertEqual(summary["spdx"]["relationshipCount"], 692)
        self.assertEqual(
            summary["profile"],
            "aetherlink-release-compliance-v2",
        )
        self.assertEqual(summary["schemaVersion"], 2)
        self.assertEqual(
            Counter(
                relationship["relationshipType"]
                for relationship in relationships
            ),
            {
                "RUNTIME_DEPENDENCY_OF": 202,
                "BUILD_DEPENDENCY_OF": 155,
                "BUILD_TOOL_OF": 335,
            },
        )
        self.assertEqual(
            len(
                {
                    (
                        relationship["spdxElementId"],
                        relationship["relationshipType"],
                        relationship["relatedSpdxElement"],
                    )
                    for relationship in relationships
                }
            ),
            692,
        )
        self.assertEqual(
            sum(
                package["SPDXID"] == "SPDXRef-Package-AetherLink"
                for package in packages
            ),
            1,
        )
        self.assertEqual(
            len({package["SPDXID"] for package in packages}),
            len(packages),
        )
        self.assertTrue(
            all(package["filesAnalyzed"] is False for package in packages)
        )

    def test_v1_historical_profileless_contract_is_frozen(self) -> None:
        metadata_bytes = (
            ROOT / "release/release-compliance-metadata-v1.json"
        ).read_bytes()
        spdx = readback.expected_spdx_v1(
            catalog_bytes=self.catalog_bytes,
            packages=self.packages,
            metadata=self.metadata,
            marketing_version="1.0.0",
            build_number=7,
        )
        spdx_bytes = canonical_json_bytes(spdx)
        notice_bytes = readback.expected_notice_v1(self.packages)
        relationships = spdx["relationships"]
        self.assertEqual(len(relationships), 350)
        self.assertEqual(
            Counter(
                relationship["relationshipType"]
                for relationship in relationships
            ),
            {
                "RUNTIME_DEPENDENCY_OF": 202,
                "BUILD_DEPENDENCY_OF": 141,
                "DEPENDENCY_OF": 7,
            },
        )
        self.assertEqual(
            spdx["documentNamespace"],
            "https://spdx.org/spdxdocs/"
            "aetherlink-1.0.0+7-local-v1-"
            "1f97b74e794e5e2b3092cc31ce8c67f634a299989658feca597bc301b67dcda5",
        )
        payload = {
            CATALOG_MEMBER: self.catalog_bytes,
            METADATA_MEMBER: metadata_bytes,
            NOTICE_MEMBER: notice_bytes,
            SPDX_MEMBER: spdx_bytes,
        }
        summary = {
            "artifactFilesAnalyzed": False,
            "catalog": readback.identity(CATALOG_MEMBER, self.catalog_bytes),
            "gradleLockedPackageCount": 350,
            "licenseCompatibilityConclusionIncluded": False,
            "licenseConcluded": "NOASSERTION",
            "metadata": readback.identity(METADATA_MEMBER, metadata_bytes),
            "networkRequiredForReleaseBuild": False,
            "notice": readback.identity(NOTICE_MEMBER, notice_bytes),
            "spdx": {
                **readback.identity(SPDX_MEMBER, spdx_bytes),
                "format": "SPDX-2.3",
                "packageCount": 351,
                "relationshipCount": 350,
            },
            "swiftExternalDependencyCount": 0,
        }
        self.assertNotIn("profile", summary)
        self.assertNotIn("schemaVersion", summary)
        verify_release_compliance(
            compliance=summary,
            payload=payload,
            source_identities={
                CATALOG_SOURCE: (
                    len(self.catalog_bytes),
                    hashlib.sha256(self.catalog_bytes).hexdigest(),
                ),
                METADATA_SOURCE: (
                    len(metadata_bytes),
                    hashlib.sha256(metadata_bytes).hexdigest(),
                ),
            },
            manifest_lock_files=self.manifest_lock_files,
            marketing_version="1.0.0",
            build_number=7,
            source_snapshot_sha256="0" * 64,
            root=ROOT,
            compare_current_source=True,
        )

    def test_v2_namespace_covers_every_generation_identity(self) -> None:
        base_arguments = {
            "catalog_bytes": self.catalog_bytes,
            "packages": self.packages,
            "metadata": self.metadata,
            "marketing_version": "1.0.0",
            "build_number": 8,
            "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
            "profile": generator.COMPLIANCE_PROFILE_V2,
        }
        baseline = generator.build_spdx_document(**base_arguments)
        repeated = generator.build_spdx_document(**base_arguments)
        self.assertEqual(baseline, repeated)

        changed_metadata = copy.deepcopy(self.metadata)
        changed_metadata["creator"] = "Organization: AetherLink fixture"
        metadata_namespace = generator.build_spdx_document(
            **{
                **base_arguments,
                "metadata": changed_metadata,
            }
        )["documentNamespace"]
        source_namespace = generator.build_spdx_document(
            **{
                **base_arguments,
                "source_snapshot_sha256": "2" * 64,
            }
        )["documentNamespace"]
        fixture_profile = generator.COMPLIANCE_PROFILE_V2 + "-fixture"
        with mock.patch.object(
            generator,
            "COMPLIANCE_PROFILE_V2",
            fixture_profile,
        ):
            profile_namespace = generator.build_spdx_document(
                **{
                    **base_arguments,
                    "profile": fixture_profile,
                }
            )["documentNamespace"]
        baseline_namespace = baseline["documentNamespace"]
        variant_namespaces = {
            metadata_namespace,
            profile_namespace,
            source_namespace,
        }
        self.assertEqual(len(variant_namespaces), 3)
        self.assertNotIn(baseline_namespace, variant_namespaces)

    def test_unknown_configuration_is_rejected_by_both_implementations(
        self,
    ) -> None:
        coordinate = self.packages[0]["coordinate"]
        mutated_catalog = copy.deepcopy(self.catalog)
        mutated_catalog["packages"][0]["configurations"] = [
            "unknownFixtureConfiguration"
        ]
        matching_locks = copy.deepcopy(generator.lock_inventory(ROOT))
        matching_locks[coordinate]["configurations"] = {
            "unknownFixtureConfiguration"
        }
        with mock.patch.object(
            generator,
            "lock_inventory",
            return_value=matching_locks,
        ):
            with self.assertRaises(ComplianceError):
                generator.validate_catalog(mutated_catalog, ROOT)

        readback_locks = copy.deepcopy(parse_current_locks(ROOT))
        readback_locks[coordinate]["configurations"] = {
            "unknownFixtureConfiguration"
        }
        with self.assertRaises(ComplianceVerificationError):
            validate_readback_catalog(
                mutated_catalog,
                manifest_lock_files=self.manifest_lock_files,
                current_locks=readback_locks,
            )

    def test_generator_rejects_claimed_repository_url_mismatch(self) -> None:
        mutated = copy.deepcopy(self.catalog)
        record = mutated["pomRecords"][0]
        record["repository"] = (
            "maven-central"
            if record["repository"] != "maven-central"
            else "google"
        )
        with self.assertRaisesRegex(
            ComplianceError,
            "POM record|pomRecords",
        ):
            generator.validate_catalog(mutated, ROOT)

    def test_unreviewed_license_names_remain_noassertion(self) -> None:
        self.assertEqual(
            spdx_declared_expression(
                [
                    {
                        "comments": "",
                        "distribution": "",
                        "name": "Unreviewed custom terms",
                        "url": "https://example.invalid/terms",
                    }
                ]
            ),
            "NOASSERTION",
        )
        self.assertEqual(
            expected_spdx_expression(
                [
                    {
                        "comments": "",
                        "distribution": "",
                        "name": "Unreviewed custom terms",
                        "url": "https://example.invalid/terms",
                    }
                ]
            ),
            "NOASSERTION",
        )

    def test_bool_package_count_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.catalog)
        mutated["gradleLockedPackageCount"] = True
        with self.assertRaises(ComplianceVerificationError):
            validate_readback_catalog(
                mutated,
                manifest_lock_files=self.manifest_lock_files,
                current_locks=parse_current_locks(ROOT),
            )

    def test_coordinate_purl_mutation_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.catalog)
        mutated["packages"][0]["purl"] += "-tampered"
        with self.assertRaisesRegex(
            ComplianceVerificationError,
            "package identity differs",
        ):
            validate_readback_catalog(
                mutated,
                manifest_lock_files=self.manifest_lock_files,
                current_locks=parse_current_locks(ROOT),
            )

    def test_license_mapping_mutation_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.catalog)
        mutated["packages"][0]["spdxLicenseDeclared"] = "MIT"
        with self.assertRaisesRegex(
            ComplianceVerificationError,
            "SPDX declaration differs",
        ):
            validate_readback_catalog(
                mutated,
                manifest_lock_files=self.manifest_lock_files,
                current_locks=parse_current_locks(ROOT),
            )

    def test_lock_identity_mutation_is_rejected(self) -> None:
        mutated_locks = copy.deepcopy(self.manifest_lock_files)
        mutated_locks[0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(
            ComplianceVerificationError,
            "lock identities differ",
        ):
            validate_readback_catalog(
                self.catalog,
                manifest_lock_files=mutated_locks,
                current_locks=None,
            )

    def test_generated_member_mutation_is_rejected(self) -> None:
        members, summary = build_release_compliance(
            marketing_version="1.0.0",
            build_number=8,
            source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
        )
        payload = dict(members)
        source_identities = {
            CATALOG_SOURCE: (
                len(payload[CATALOG_MEMBER]),
                hashlib.sha256(payload[CATALOG_MEMBER]).hexdigest(),
            ),
            METADATA_SOURCE: (
                len(payload[METADATA_MEMBER]),
                hashlib.sha256(payload[METADATA_MEMBER]).hexdigest(),
            ),
        }
        payload[SPDX_MEMBER] = payload[SPDX_MEMBER].replace(
            b'"SPDX-2.3"',
            b'"SPDX-2.2"',
            1,
        )
        with self.assertRaisesRegex(
            ComplianceVerificationError,
            "SPDX bytes differ",
        ):
            verify_release_compliance(
                compliance=summary,
                payload=payload,
                source_identities=source_identities,
                manifest_lock_files=self.manifest_lock_files,
                marketing_version="1.0.0",
                build_number=8,
                source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
                root=ROOT,
                compare_current_source=False,
            )

    def test_v2_summary_profile_and_schema_mutations_are_rejected(self) -> None:
        members, summary = build_release_compliance(
            marketing_version="1.0.0",
            build_number=8,
            source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
        )
        payload = dict(members)
        source_identities = {
            CATALOG_SOURCE: (
                len(payload[CATALOG_MEMBER]),
                hashlib.sha256(payload[CATALOG_MEMBER]).hexdigest(),
            ),
            METADATA_SOURCE: (
                len(payload[METADATA_MEMBER]),
                hashlib.sha256(payload[METADATA_MEMBER]).hexdigest(),
            ),
        }
        for key, value in (
            ("profile", "aetherlink-release-compliance-v1"),
            ("schemaVersion", 1),
            ("schemaVersion", True),
        ):
            with self.subTest(key=key, value=value):
                mutated = copy.deepcopy(summary)
                mutated[key] = value
                with self.assertRaisesRegex(
                    ComplianceVerificationError,
                    "summary|profile|schema",
                ):
                    verify_release_compliance(
                        compliance=mutated,
                        payload=payload,
                        source_identities=source_identities,
                        manifest_lock_files=self.manifest_lock_files,
                        marketing_version="1.0.0",
                        build_number=8,
                        source_snapshot_sha256=SOURCE_SNAPSHOT_SHA256,
                        root=ROOT,
                        compare_current_source=False,
                    )

    def test_noncanonical_or_duplicate_json_is_rejected(self) -> None:
        for data in (
            b'{"schemaVersion":1,"schemaVersion":1}\n',
            b'{ "schemaVersion":1}\n',
            b'{"schemaVersion":NaN}\n',
            b'{"schemaVersion":1}\r\n',
        ):
            with self.subTest(data=data):
                with self.assertRaises((ComplianceError, ValueError)):
                    parse_canonical_json(data, "fixture")
                with self.assertRaises(
                    (ComplianceVerificationError, ValueError)
                ):
                    parse_readback_json(data, "fixture")

    def test_catalog_statistics_capture_unresolved_boundary(self) -> None:
        counts: dict[str, int] = {}
        for package in self.packages:
            expression = str(package["spdxLicenseDeclared"])
            counts[expression] = counts.get(expression, 0) + 1
        self.assertEqual(sum(counts.values()), 350)
        self.assertGreater(counts.get("NOASSERTION", 0), 0)
        self.assertGreater(counts.get("Apache-2.0", 0), 0)
        self.assertTrue(
            all(
                package["spdxLicenseDeclared"] == "NOASSERTION"
                for package in self.packages
                if any(
                    declaration["name"] == "ML Kit Terms of Service"
                    for declaration in package["pomDeclaredLicenses"]
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
