from __future__ import annotations

import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from script import check_macos_build24_lifecycle_evidence as checker


def canonical_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def byte_identity(payload: bytes) -> checker.ByteIdentity:
    return checker.identity(len(payload), hashlib.sha256(payload).hexdigest())


def scalar_paths(
    value: object,
    scalar_type: type[object],
    prefix: tuple[object, ...] = (),
) -> list[tuple[object, ...]]:
    paths: list[tuple[object, ...]] = []
    if type(value) is dict:
        for key, child in value.items():
            paths.extend(
                scalar_paths(
                    child,
                    scalar_type,
                    prefix + (key,),
                )
            )
    elif type(value) is list:
        for ordinal, child in enumerate(value):
            paths.extend(
                scalar_paths(
                    child,
                    scalar_type,
                    prefix + (ordinal,),
                )
            )
    elif type(value) is scalar_type:
        paths.append(prefix)
    return paths


def replace_at_path(
    value: object,
    path: tuple[object, ...],
    replacement: object,
) -> None:
    target = value
    for component in path[:-1]:
        target = target[component]  # type: ignore[index]
    target[path[-1]] = replacement  # type: ignore[index]


def canonical_source_snapshot_directories() -> tuple[str, ...]:
    directories: set[str] = set()
    for semantic_path in checker.SOURCE_CONTRACTS:
        parent = Path(checker.source_storage_path(semantic_path)).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return tuple(
        sorted(
            directories,
            key=lambda value: (len(Path(value).parts), value),
        )
    )


def materialize_canonical_source_snapshot(root: Path) -> tuple[str, ...]:
    storage_paths = tuple(
        sorted(
            checker.source_storage_path(path)
            for path in checker.SOURCE_CONTRACTS
        )
    )
    for relative_path in storage_paths:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((checker.ROOT / relative_path).read_bytes())
    return storage_paths


class Build24MacOSLifecycleEvidenceTests(unittest.TestCase):
    maxDiff = None

    def contract_named(self, suffix: str) -> checker.EvidenceContract:
        matches = [
            contract
            for contract in checker.EVIDENCE_CONTRACTS
            if contract.relative_path.endswith(suffix)
        ]
        self.assertEqual(1, len(matches))
        return matches[0]

    def document_for(
        self,
        contract: checker.EvidenceContract,
    ) -> dict[str, object]:
        payload = (checker.ROOT / contract.relative_path).read_bytes()
        return checker.parse_canonical_json(payload, contract.relative_path)

    def assert_semantic_mutation_rejected(
        self,
        contract: checker.EvidenceContract,
        mutate: object,
    ) -> None:
        document = copy.deepcopy(self.document_for(contract))
        self.assertTrue(callable(mutate))
        mutate(document)
        with self.assertRaises(checker.LifecycleEvidenceError):
            checker.validate_evidence_document(document, contract)

    def test_closed_production_inventory_is_exact(self) -> None:
        self.assertEqual({23, 24}, set(checker.RELEASES))
        self.assertEqual(9, len(checker.EVIDENCE_CONTRACTS))
        self.assertEqual(25, len(checker.SOURCE_CONTRACTS))
        self.assertEqual(
            checker.HISTORICAL_SOURCE_SNAPSHOT_COMMIT,
            "38027523f65f97a81044555c2f42b020eada3436",
        )
        self.assertEqual(
            checker.HISTORICAL_SOURCE_SNAPSHOT_ROOT,
            "docs/evidence/macos-build24-lifecycle-source-v1",
        )
        self.assertEqual(
            set(checker.HISTORICAL_SOURCE_STORAGE_PATHS),
            {
                "script/run_macos_local_dmg_install_smoke_v2.py",
                "script/test_run_macos_local_dmg_install_smoke_v2.py",
                "script/run_macos_local_dmg_uninstall_reinstall_smoke.py",
                "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py",
                (
                    "script/run_macos_local_dmg_uninstall_reinstall_"
                    "state_recovery_smoke.py"
                ),
                (
                    "script/test_run_macos_local_dmg_uninstall_reinstall_"
                    "state_recovery_smoke.py"
                ),
                (
                    "script/run_macos_local_dmg_uninstall_reinstall_"
                    "abrupt_process_state_recovery_smoke.py"
                ),
                (
                    "script/test_run_macos_local_dmg_uninstall_reinstall_"
                    "abrupt_process_state_recovery_smoke.py"
                ),
            },
        )
        checker.validate_historical_source_snapshot_contract()
        for semantic_path, storage_path in (
            checker.HISTORICAL_SOURCE_STORAGE_PATHS.items()
        ):
            expected = checker.SOURCE_CONTRACTS[semantic_path]
            fixture = checker.ROOT / storage_path
            with self.subTest(semantic_path=semantic_path):
                self.assertTrue(
                    storage_path.startswith(
                        checker.HISTORICAL_SOURCE_SNAPSHOT_ROOT + "/script/"
                    )
                )
                self.assertFalse(fixture.is_symlink())
                self.assertTrue(fixture.is_file())
                self.assertEqual(fixture.stat().st_mode & 0o111, 0)
                payload = fixture.read_bytes()
                self.assertEqual(byte_identity(payload), expected)
        live_v2 = (
            checker.ROOT / "script/run_macos_local_dmg_install_smoke_v2.py"
        ).read_bytes()
        self.assertNotEqual(
            byte_identity(live_v2),
            checker.SOURCE_CONTRACTS[
                "script/run_macos_local_dmg_install_smoke_v2.py"
            ],
        )
        self.assertEqual(12, len(checker.UNIT_TEST_MODULES))
        evidence_paths = [
            contract.relative_path for contract in checker.EVIDENCE_CONTRACTS
        ]
        self.assertEqual(len(evidence_paths), len(set(evidence_paths)))
        self.assertNotIn(
            (
                "dist/lifecycle/"
                "macos-packaged-app-build-23-to-24-isolated-upgrade-v1.json"
            ),
            evidence_paths,
        )
        self.assertNotIn(
            (
                "dist/lifecycle/"
                "macos-packaged-app-build-24-local-dmg-install-v1.json"
            ),
            evidence_paths,
        )
        self.assertEqual(
            {
                checker.UPGRADE_RESULT_PATH,
                checker.ABRUPT_RESULT_PATH,
            },
            {
                contract.canonical_result_path
                for contract in checker.EVIDENCE_CONTRACTS
                if contract.kind == "repeatability-receipt"
            },
        )

    def test_production_readback_passes_without_running_smokes(self) -> None:
        self.assertEqual([], checker.readback_failures(checker.ROOT))

    def test_every_production_evidence_document_passes_semantics(self) -> None:
        contracts_by_path = {
            contract.relative_path: contract
            for contract in checker.EVIDENCE_CONTRACTS
        }
        for contract in checker.EVIDENCE_CONTRACTS:
            with self.subTest(contract=contract.relative_path):
                checker.validate_evidence_document(
                    self.document_for(contract),
                    contract,
                    contracts_by_path,
                )

    def test_canonical_json_parser_rejects_noncanonical_or_ambiguous_input(
        self,
    ) -> None:
        invalid_payloads = (
            b'{"a":1, "b":2}\n',
            b'{"a":1,"a":2}\n',
            b'{"a":NaN}\n',
            b'{"a":1}',
            b'[1,2]\n',
            b"\xff\n",
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(checker.LifecycleEvidenceError):
                    checker.parse_canonical_json(payload, "mutation")
        self.assertEqual(
            {"a": 1, "b": [False, None]},
            checker.parse_canonical_json(
                b'{"a":1,"b":[false,null]}\n',
                "canonical",
            ),
        )

    def test_stable_regular_file_contract_rejects_wrong_types_and_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "payload"
            payload = b"bounded lifecycle bytes\n"
            path.write_bytes(payload)
            expected = byte_identity(payload)
            self.assertEqual(
                payload,
                checker.require_identity(
                    path,
                    expected,
                    maximum_bytes=1024,
                    retain_bytes=True,
                ),
            )
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.require_identity(
                    path,
                    checker.identity(
                        expected.size,
                        "0" * 64,
                    ),
                    maximum_bytes=1024,
                )
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.require_identity(
                    path,
                    expected,
                    maximum_bytes=len(payload) - 1,
                )
            directory = root / "directory"
            directory.mkdir()
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.read_stable_regular_file(
                    directory,
                    maximum_bytes=1024,
                    retain_bytes=False,
                )
            symlink = root / "symlink"
            symlink.symlink_to(path)
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.read_stable_regular_file(
                    symlink,
                    maximum_bytes=1024,
                    retain_bytes=False,
                )
            hardlink = root / "hardlink"
            os.link(path, hardlink)
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.read_stable_regular_file(
                    path,
                    maximum_bytes=1024,
                    retain_bytes=False,
                )

    def test_relative_paths_reject_escape_or_absolute_targets(self) -> None:
        for relative in ("", ".", "../outside", "/tmp/outside", "a/../b"):
            with self.subTest(relative=relative):
                with self.assertRaises(checker.LifecycleEvidenceError):
                    checker.resolve_relative(checker.ROOT, relative)
        self.assertEqual(
            checker.ROOT / "script/file.py",
            checker.resolve_relative(checker.ROOT, "script/file.py"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            physical = root / "physical"
            physical.mkdir()
            (root / "linked").symlink_to(physical, target_is_directory=True)
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.resolve_relative(root, "linked/file")

    def test_repository_reader_holds_and_rechecks_physical_parent_chain(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "one" / "two"
            parent.mkdir(parents=True)
            payload = b"repository-bound bytes\n"
            (parent / "payload").write_bytes(payload)
            self.assertEqual(
                (byte_identity(payload), payload),
                checker.read_stable_repository_file(
                    root,
                    "one/two/payload",
                    maximum_bytes=1024,
                    retain_bytes=True,
                ),
            )

            with mock.patch.object(
                checker,
                "verify_repository_parent_chain",
                side_effect=checker.LifecycleEvidenceError(
                    "parent identity drift"
                ),
            ):
                with self.assertRaises(checker.LifecycleEvidenceError):
                    checker.read_stable_repository_file(
                        root,
                        "one/two/payload",
                        maximum_bytes=1024,
                        retain_bytes=False,
                    )

    def test_collection_snapshot_reader_rejects_cross_file_directory_swap(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "collection"
            original.mkdir()
            first = b"first\n"
            second = b"second\n"
            (original / "first").write_bytes(first)
            (original / "second").write_bytes(second)
            with checker.RepositorySnapshotReader(
                root,
                ("collection",),
                ("collection/first", "collection/second"),
            ) as snapshot:
                self.assertEqual(
                    first,
                    snapshot.require_identity(
                        "collection/first",
                        byte_identity(first),
                        maximum_bytes=1024,
                        retain_bytes=True,
                    ),
                )
                retained = root / "retained-original"
                original.rename(retained)
                replacement = root / "collection"
                replacement.mkdir()
                (replacement / "first").write_bytes(b"replacement-first\n")
                (replacement / "second").write_bytes(b"replacement-second\n")

                self.assertEqual(
                    second,
                    snapshot.require_identity(
                        "collection/second",
                        byte_identity(second),
                        maximum_bytes=1024,
                        retain_bytes=True,
                    ),
                )
                with self.assertRaises(checker.LifecycleEvidenceError):
                    snapshot.verify_unchanged()

    def test_collection_snapshot_opens_all_files_before_any_hash_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            collection = root / "collection"
            collection.mkdir()
            expected_first = b"expected-first\n"
            expected_second = b"expected-second\n"
            wrong = b"wrong\n"
            (collection / "first").write_bytes(expected_first)
            (collection / "second").write_bytes(wrong)
            with checker.RepositorySnapshotReader(
                root,
                ("collection",),
                ("collection/first", "collection/second"),
            ) as snapshot:
                snapshot.require_identity(
                    "collection/first",
                    byte_identity(expected_first),
                    maximum_bytes=1024,
                )
                (collection / "first").unlink()
                (collection / "first").write_bytes(wrong)
                (collection / "second").unlink()
                (collection / "second").write_bytes(expected_second)
                with self.assertRaises(checker.LifecycleEvidenceError):
                    snapshot.require_identity(
                        "collection/second",
                        byte_identity(expected_second),
                        maximum_bytes=1024,
                    )
                with self.assertRaises(checker.LifecycleEvidenceError):
                    snapshot.verify_unchanged()

    def test_ledger_semantics_reject_terminal_and_shape_mutations(self) -> None:
        cases = (
            b"build_number\tmarketing_version\n23\t1.0.0\n24\t1.0.0\n",
            b"wrong\tmarketing_version\n23\t1.0.0\n24\t1.0.0\n",
            b"build_number\tmarketing_version\n24\t1.0.0\n23\t1.0.0\n",
            b"build_number\tmarketing_version\n23\t1.0.0\n25\t1.0.0\n",
            b"build_number\tmarketing_version\n23\t1.0.0\n24\t1.0.0",
        )
        expected_passes = (True, False, False, False, False)
        for payload, should_pass in zip(cases, expected_passes):
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    ledger = root / checker.LEDGER_RELATIVE_PATH
                    ledger.parent.mkdir(parents=True)
                    ledger.write_bytes(payload)
                    with mock.patch.object(
                        checker,
                        "LEDGER_IDENTITY",
                        byte_identity(payload),
                    ):
                        if should_pass:
                            checker.validate_ledger(root)
                        else:
                            with self.assertRaises(
                                checker.LifecycleEvidenceError
                            ):
                                checker.validate_ledger(root)

    def test_archive_manifests_bind_version_ledger_and_executable(self) -> None:
        for build_number in (23, 24):
            contract = checker.RELEASES[build_number]
            path = (
                checker.ROOT
                / "dist/releases"
                / contract.release_id
                / f"{contract.release_id}.manifest.json"
            )
            document = checker.parse_canonical_json(
                path.read_bytes(),
                path.name,
            )
            checker.validate_archive_manifest(document, contract)

            mutations = []
            schema = copy.deepcopy(document)
            schema["schemaVersion"] = True
            mutations.append(schema)
            release = copy.deepcopy(document)
            release["release"]["buildNumber"] = True
            mutations.append(release)
            ledger = copy.deepcopy(document)
            ledger["ledger"]["sha256"] = "0" * 64
            mutations.append(ledger)
            executable = copy.deepcopy(document)
            for member in executable["members"]:
                if (
                    member["path"]
                    == "macos/AetherLink.app/Contents/MacOS/AetherLink"
                ):
                    member["size"] = True
            mutations.append(executable)

            for mutation in mutations:
                with self.subTest(
                    build_number=build_number,
                    mutation=mutation,
                ):
                    with self.assertRaises(checker.LifecycleEvidenceError):
                        checker.validate_archive_manifest(mutation, contract)

    def test_every_boolean_leaf_rejects_integer_substitution(self) -> None:
        observed_names: set[str] = set()
        for contract in checker.EVIDENCE_CONTRACTS:
            document = self.document_for(contract)
            for path in scalar_paths(document, bool):
                observed_names.add(str(path[-1]))
                mutation = copy.deepcopy(document)
                original = document
                target: object = original
                for component in path:
                    target = target[component]  # type: ignore[index]
                replace_at_path(mutation, path, 1 if target else 0)
                with self.subTest(
                    contract=contract.relative_path,
                    path=path,
                ):
                    with self.assertRaises(checker.LifecycleEvidenceError):
                        checker.validate_evidence_document(
                            mutation,
                            contract,
                        )

        for release in checker.RELEASES.values():
            manifest_path = (
                checker.ROOT
                / "dist/releases"
                / release.release_id
                / f"{release.release_id}.manifest.json"
            )
            manifest = checker.parse_canonical_json(
                manifest_path.read_bytes(),
                manifest_path.name,
            )
            for path in scalar_paths(manifest, bool):
                observed_names.add(str(path[-1]))
                target: object = manifest
                for component in path:
                    target = target[component]  # type: ignore[index]
                mutation = copy.deepcopy(manifest)
                replace_at_path(mutation, path, 1 if target else 0)
                with self.subTest(
                    release=release.release_id,
                    path=path,
                ):
                    with self.assertRaises(checker.LifecycleEvidenceError):
                        checker.validate_archive_manifest(
                            mutation,
                            release,
                        )
        self.assertEqual(
            checker.EXACT_BOOLEAN_FIELD_NAMES,
            frozenset(observed_names),
        )

    def test_common_result_schema_scope_status_and_limitations_fail_closed(
        self,
    ) -> None:
        contract = self.contract_named(
            "macos-packaged-app-build-24-clean-home-install-v1.json"
        )
        mutations = (
            lambda document: document.__setitem__("extra", False),
            lambda document: document.__setitem__("schemaVersion", True),
            lambda document: document.__setitem__("scope", "widened"),
            lambda document: document.__setitem__("status", "failed"),
            lambda document: document["limitations"].pop(),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.assert_semantic_mutation_rejected(contract, mutate)

    def test_build_result_release_app_tree_and_archive_readback_fail_closed(
        self,
    ) -> None:
        clean_contract = self.contract_named(
            "macos-packaged-app-build-24-clean-home-install-v1.json"
        )
        self.assert_semantic_mutation_rejected(
            clean_contract,
            lambda document: document["release"].__setitem__(
                "archiveSha256",
                "0" * 64,
            ),
        )
        self.assert_semantic_mutation_rejected(
            clean_contract,
            lambda document: document["app"].__setitem__(
                "executableSha256",
                "0" * 64,
            ),
        )
        self.assert_semantic_mutation_rejected(
            clean_contract,
            lambda document: document["installation"]["tree"].__setitem__(
                "regularFileCount",
                True,
            ),
        )

        dmg_contract = self.contract_named(
            "macos-packaged-app-build-24-local-dmg-install-v2.json"
        )
        self.assert_semantic_mutation_rejected(
            dmg_contract,
            lambda document: document["archiveReadback"][
                "snapshotFiles"
            ][
                f"{checker.RELEASES[24].release_id}.zip"
            ].__setitem__(
                "size",
                True,
            ),
        )

        recovery_contract = self.contract_named(
            (
                "macos-packaged-app-build-24-local-dmg-"
                "uninstall-reinstall-state-recovery-v1.json"
            )
        )
        self.assert_semantic_mutation_rejected(
            recovery_contract,
            lambda document: document["stateRecovery"].__setitem__(
                "totalEventCount",
                True,
            ),
        )
        abrupt_contract = self.contract_named(
            (
                "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
                "abrupt-process-state-recovery-v1.json"
            )
        )
        self.assert_semantic_mutation_rejected(
            abrupt_contract,
            lambda document: document["launches"]["runs"][0].__setitem__(
                "minimumObservationSeconds",
                True,
            ),
        )

    def test_upgrade_direction_and_both_archive_snapshots_fail_closed(
        self,
    ) -> None:
        contract = self.contract_named(
            "macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json"
        )

        def reverse_releases(document: dict[str, object]) -> None:
            document["releases"]["from"], document["releases"]["to"] = (
                document["releases"]["to"],
                document["releases"]["from"],
            )

        self.assert_semantic_mutation_rejected(contract, reverse_releases)
        self.assert_semantic_mutation_rejected(
            contract,
            lambda document: document["archiveReadback"]["previous"][
                "snapshotFiles"
            ][
                f"{checker.RELEASES[23].release_id}.manifest.json"
            ].__setitem__(
                "sha256",
                "0" * 64,
            ),
        )

    def test_repeatability_receipts_bind_exact_result_and_exact_integer_runs(
        self,
    ) -> None:
        for suffix in (
            (
                "macos-packaged-app-build-23-to-24-"
                "isolated-upgrade-repeatability-v1.json"
            ),
            (
                "macos-packaged-app-build-24-local-dmg-uninstall-reinstall-"
                "abrupt-process-state-recovery-repeatability-v1.json"
            ),
        ):
            contract = self.contract_named(suffix)
            mutations = (
                lambda document: document["canonicalResult"].__setitem__(
                    "sha256",
                    "0" * 64,
                ),
                lambda document: document.__setitem__("runCount", True),
                lambda document: document.__setitem__(
                    "resultBytesEqual",
                    False,
                ),
                lambda document: document["runs"][0].__setitem__(
                    "ordinal",
                    True,
                ),
                lambda document: document["runs"][1].__setitem__(
                    "size",
                    True,
                ),
            )
            for mutate in mutations:
                with self.subTest(contract=contract.relative_path, mutate=mutate):
                    self.assert_semantic_mutation_rejected(contract, mutate)

    def test_evidence_byte_identity_rejects_semantically_rehashed_mutation(
        self,
    ) -> None:
        original = self.contract_named(
            "macos-packaged-app-build-24-clean-home-install-v1.json"
        )
        document = self.document_for(original)
        document["status"] = "failed"
        payload = canonical_bytes(document)
        mutated_contract = replace(original, identity=byte_identity(payload))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / mutated_contract.relative_path
            path.parent.mkdir(parents=True)
            path.write_bytes(payload)
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.validate_evidence_files(root, (mutated_contract,))

    def test_source_byte_inventory_detects_missing_or_mutated_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "script/source.py"
            source.parent.mkdir()
            source.write_bytes(b"pass\n")
            contracts = {"script/source.py": byte_identity(b"pass\n")}
            checker.validate_source_files(root, contracts)
            source.write_bytes(b"raise SystemExit\n")
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.validate_source_files(root, contracts)
            source.unlink()
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.validate_source_files(root, contracts)

    def test_historical_snapshot_contract_rejects_commit_and_path_drift(
        self,
    ) -> None:
        with mock.patch.object(
            checker,
            "HISTORICAL_SOURCE_SNAPSHOT_COMMIT",
            "0" * 40,
        ):
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.validate_historical_source_snapshot_contract()
        mutated_paths = dict(checker.HISTORICAL_SOURCE_STORAGE_PATHS)
        semantic_path = "script/run_macos_local_dmg_install_smoke_v2.py"
        mutated_paths[semantic_path] = semantic_path
        with mock.patch.object(
            checker,
            "HISTORICAL_SOURCE_STORAGE_PATHS",
            mutated_paths,
        ):
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.validate_historical_source_snapshot_contract()

    def test_canonical_source_readback_uses_exact_physical_fixture(self) -> None:
        def validate(root: Path, storage_paths: tuple[str, ...]) -> None:
            with checker.RepositorySnapshotReader(
                root,
                canonical_source_snapshot_directories(),
                storage_paths,
            ) as snapshot:
                checker.validate_source_files(root, snapshot=snapshot)
                checker.validate_source_files(
                    root,
                    checker.SOURCE_CONTRACTS,
                    snapshot=snapshot,
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            storage_paths = materialize_canonical_source_snapshot(root)
            live_v2 = root / "script/run_macos_local_dmg_install_smoke_v2.py"
            live_v2.write_bytes(
                b"current live runner is not Build 24 evidence\n"
            )
            validate(root, storage_paths)

            fixture = root / checker.HISTORICAL_SOURCE_STORAGE_PATHS[
                "script/run_macos_local_dmg_install_smoke_v2.py"
            ]
            fixture.write_bytes(fixture.read_bytes() + b"mutation")
            with self.assertRaises(checker.LifecycleEvidenceError):
                validate(root, storage_paths)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            storage_paths = materialize_canonical_source_snapshot(root)
            fixture = root / checker.HISTORICAL_SOURCE_STORAGE_PATHS[
                "script/run_macos_local_dmg_install_smoke_v2.py"
            ]
            fixture.unlink()
            fixture.symlink_to(
                root / "script/run_macos_local_dmg_install_smoke_v2.py"
            )
            with self.assertRaises((checker.LifecycleEvidenceError, OSError)):
                validate(root, storage_paths)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            storage_paths = materialize_canonical_source_snapshot(root)
            fixture_directory = (
                root
                / checker.HISTORICAL_SOURCE_SNAPSHOT_ROOT
                / "script"
            )
            (fixture_directory / "unexpected.py").write_bytes(b"pass\n")
            with self.assertRaises(checker.LifecycleEvidenceError):
                validate(root, storage_paths)

    def test_focused_unit_inventory_is_closed_bound_and_nonsecurity(self) -> None:
        checker.validate_unit_test_inventory()
        for module in checker.UNIT_TEST_MODULES:
            self.assertIn(
                checker.source_path_for_test_module(module),
                checker.SOURCE_CONTRACTS,
            )
            lowered = module.lower()
            self.assertFalse(
                any(
                    token in lowered
                    for token in checker.FORBIDDEN_UNIT_TEST_TOKENS
                )
            )

        mutated = checker.UNIT_TEST_MODULES[:-1] + (
            "script.test_security_mutation",
        )
        with mock.patch.object(checker, "UNIT_TEST_MODULES", mutated):
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.validate_unit_test_inventory(
                    mutated,
                    {
                        **checker.SOURCE_CONTRACTS,
                        "script/test_security_mutation.py": byte_identity(
                            b"pass\n"
                        ),
                    },
                )

        missing = checker.UNIT_TEST_MODULES[:-1] + (
            "script.test_unbound_lifecycle_mutation",
        )
        with mock.patch.object(checker, "UNIT_TEST_MODULES", missing):
            with self.assertRaises(checker.LifecycleEvidenceError):
                checker.validate_unit_test_inventory(
                    missing,
                    checker.SOURCE_CONTRACTS,
                )

    def test_checker_source_imports_no_lifecycle_runner_and_has_no_write_api(
        self,
    ) -> None:
        source_path = Path(checker.__file__)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules: list[str] = []
        called_attributes: list[str] = []
        called_names: list[str] = []
        forbidden_open_flags: list[str] = []
        non_os_open_calls: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(node.module or "")
            elif isinstance(node, ast.Call) and isinstance(
                node.func,
                ast.Attribute,
            ):
                called_attributes.append(node.func.attr)
                if node.func.attr == "open" and not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                ):
                    non_os_open_calls.append(node.lineno)
            elif isinstance(node, ast.Call) and isinstance(
                node.func,
                ast.Name,
            ):
                called_names.append(node.func.id)
            elif isinstance(node, ast.Attribute) and node.attr in {
                "O_APPEND",
                "O_CREAT",
                "O_RDWR",
                "O_TRUNC",
                "O_WRONLY",
            }:
                forbidden_open_flags.append(node.attr)
        self.assertFalse(
            any("run_macos_" in module for module in imported_modules)
        )
        for forbidden in (
            "write_bytes",
            "write_text",
            "unlink",
            "rename",
            "mkdir",
            "rmdir",
            "remove",
        ):
            self.assertNotIn(forbidden, called_attributes)
        self.assertNotIn("runpy", imported_modules)
        self.assertNotIn("importlib", imported_modules)
        self.assertNotIn("subprocess", imported_modules)
        self.assertNotIn("subprocess.run(", source)
        self.assertFalse(non_os_open_calls)
        self.assertFalse(forbidden_open_flags)
        for forbidden_name in (
            "__import__",
            "compile",
            "eval",
            "exec",
            "open",
        ):
            self.assertNotIn(forbidden_name, called_names)
        for forbidden_attribute in (
            "Popen",
            "execv",
            "execve",
            "fork",
            "popen",
            "spawnv",
            "system",
        ):
            self.assertNotIn(forbidden_attribute, called_attributes)
        self.assertFalse(
            {
                "http",
                "requests",
                "socket",
                "urllib",
            }
            & {module.split(".", 1)[0] for module in imported_modules}
        )
        self.assertNotIn("hdiutil", source)
        self.assertNotIn("osascript", source)
        self.assertNotIn("sandbox-exec", source)
        self.assertNotIn("os.replace(", source)
        self.assertGreaterEqual(source.count("dir_fd="), 3)
        self.assertIn("verify_repository_parent_chain(", source)

    def test_main_rejects_arguments_and_fails_closed_on_readback_failure(
        self,
    ) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(2, checker.main(["--weaken"]))
        self.assertIn("usage:", stderr.getvalue())

        with (
            mock.patch.object(
                checker,
                "readback_failures",
                return_value=["mutated input"],
            ),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(1, checker.main([]))

    def test_main_reports_success_only_after_one_static_readback(
        self,
    ) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(
                checker,
                "readback_failures",
                return_value=[],
            ) as readback,
            redirect_stdout(stdout),
        ):
            self.assertEqual(0, checker.main([]))
            readback.assert_called_once_with()
        self.assertIn(
            "2 archives, 9 result/receipt files, "
            "25 source files, 12 byte-bound focused unit modules "
            "(not executed)",
            stdout.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
