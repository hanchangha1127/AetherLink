#!/usr/bin/env python3
"""Regression tests for frozen Build 7 and deterministic Build 8 compliance."""

from __future__ import annotations

import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
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

    def test_checked_in_catalog_exactly_covers_current_locks(self) -> None:
        current = parse_current_locks(ROOT)
        self.assertEqual(len(current), 350)
        self.assertEqual(len(self.packages), 350)
        self.assertEqual(
            {package["coordinate"] for package in self.packages},
            set(current),
        )
        self.assertEqual(len(self.catalog["pomRecords"]), 379)

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
