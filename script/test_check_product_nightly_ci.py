#!/usr/bin/env python3
"""Regression tests for the bounded G7 Android product-nightly contract."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

from script import check_android_headless_emulator_product_lifecycle as lifecycle_v1
from script import check_android_headless_emulator_product_lifecycle_v2 as lifecycle_v2
from script import check_product_nightly_ci as checker


class ProductNightlyCIContractTests(unittest.TestCase):
    def workflow(self) -> str:
        return checker.WORKFLOW_PATH.read_text(encoding="utf-8")

    def github_environment(self) -> dict[str, str]:
        return {
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": "example/aetherlink",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_REF": (
                "example/aetherlink/.github/workflows/"
                "product-nightly.yml@refs/heads/main"
            ),
        }

    class FakeSnapshot:
        def __init__(self, result_directory: Path) -> None:
            self.result_directory = result_directory

        def verify_unchanged(self) -> None:
            return None

        def close(self) -> None:
            return None

    def result_payload(
        self,
        lane: str,
        run_id: str,
        evidence: dict[str, object] | None = None,
    ) -> dict[str, object]:
        lifecycle = lifecycle_v1 if lane == "v1" else lifecycle_v2
        evidence = evidence or {
            relative: lifecycle_v2.CapturedEvidenceFile(
                data=(relative + "\n").encode("utf-8"),
                identity=(),
                mode="0644",
            )
            for relative in lifecycle.EVIDENCE_PATHS
        }
        return {
            "contract": lifecycle.CONTRACT,
            "evidence": [
                evidence[relative].record(relative)  # type: ignore[attr-defined]
                for relative in lifecycle.EVIDENCE_PATHS
            ],
            "run": {
                "finishedAt": (
                    "2026-08-02T18:39:00.000Z"
                    if lane == "v1"
                    else "2026-08-02T18:42:00.000Z"
                ),
                "id": run_id,
                "startedAt": (
                    "2026-08-02T18:37:00.000Z"
                    if lane == "v1"
                    else "2026-08-02T18:39:00.000Z"
                ),
            },
            "cleanup": {"ownedProcessExited": True},
            "scenarios": [
                {"name": name, "status": "passed"}
                for name, _checks in lifecycle.SCENARIO_CHECKS
            ],
            "schemaVersion": lifecycle.SCHEMA_VERSION,
            "source": {
                "fileCount": 135 if lane == "v1" else 145,
                "sha256": ("a" if lane == "v1" else "b") * 64,
            },
            "status": "passed",
        }

    def captured_fixture(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        run_ids = {
            "v1": "android-headless-api36-1-20260802T183700Z-1234abcd",
            "v2": "android-headless-api36-1-v2-20260802T183900Z-1234abcd",
        }
        captures = {}
        paths = {}
        for lane in checker.LANE_ORDER:
            lifecycle = lifecycle_v1 if lane == "v1" else lifecycle_v2
            directory = root / run_ids[lane]
            directory.mkdir(mode=0o700)
            evidence: dict[str, object] = {
                relative: lifecycle_v2.CapturedEvidenceFile(
                    data=(lane + ":" + relative + "\n").encode("utf-8"),
                    identity=(),
                    mode="0644",
                )
                for relative in lifecycle.EVIDENCE_PATHS
            }
            result = self.result_payload(lane, run_ids[lane], evidence)
            result_capture = lifecycle_v2.CapturedEvidenceFile(
                data=checker.canonical_json_bytes(result),
                identity=(),
                mode="0644",
            )
            evidence["result.json"] = result_capture
            paths[lane] = directory / "result.json"
            captures[lane] = (
                lifecycle,
                self.FakeSnapshot(directory),
                evidence,
                result_capture,
                result,
            )

        def opened(lane: str, *_args: object, **_kwargs: object):
            return captures[lane]

        return paths, captures, opened

    def test_current_workflow_and_self_test_pass(self) -> None:
        workflow = self.workflow()
        self.assertEqual([], checker.workflow_failures(workflow))
        self.assertEqual([], checker.self_test(workflow))

    def test_workflow_rejects_trigger_permission_and_bypass_mutations(self) -> None:
        workflow = self.workflow()
        mutations = (
            workflow.replace(
                '  schedule:\n    - cron: "37 18 * * *"\n',
                "  pull_request:\n",
                1,
            ),
            workflow.replace(
                "permissions:\n  contents: read\n",
                "permissions:\n  contents: write\n",
                1,
            ),
            workflow.replace("          java -version\n", "          java -version || true\n", 1),
            workflow.replace("          retention-days: 14\n", "          retention-days: 90\n", 1),
        )
        for mutated in mutations:
            with self.subTest():
                self.assertNotEqual(workflow, mutated)
                self.assertTrue(
                    checker.workflow_failures(mutated, check_canonical_bytes=False)
                )

    def test_workflow_rejects_producer_checker_and_upload_order_drift(self) -> None:
        workflow = self.workflow()
        swapped_runners = workflow.replace(
            "script/run_android_headless_emulator_product_lifecycle.py",
            "script/__nightly_v1_runner_placeholder__.py",
            1,
        ).replace(
            "script/run_android_headless_emulator_product_lifecycle_v2.py",
            "script/run_android_headless_emulator_product_lifecycle.py",
            1,
        ).replace(
            "script/__nightly_v1_runner_placeholder__.py",
            "script/run_android_headless_emulator_product_lifecycle_v2.py",
            1,
        )
        mutations = (
            workflow.replace(
                "          python3 -B script/run_android_headless_emulator_product_lifecycle.py \\\n",
                "",
                1,
            ),
            workflow.replace(
                "          python3 -B script/run_android_headless_emulator_product_lifecycle_v2.py \\\n",
                "",
                1,
            ),
            workflow.replace(
                "script/run_android_headless_emulator_product_lifecycle_v2.py",
                "script/run_android_headless_emulator_product_lifecycle.py",
                1,
            ),
            swapped_runners,
            workflow.replace(
                '--v1-result "$LIFECYCLE_V1_RESULT"',
                '--v1-result "$LIFECYCLE_V2_RESULT"',
                1,
            ),
            workflow.replace(
                "      - name: Upload one sealed nightly candidate\n",
                "      - name: Upload one sealed nightly candidate\n"
                "        if: ${{ always() }}\n",
                1,
            ),
            workflow.replace(
                "      - name: Prepare exact Android build dependencies\n",
                "      - name: Prepare removed Android build dependencies\n",
                1,
            ),
            workflow.replace(
                "      - name: Seal and read back exact dual-lifecycle nightly artifact\n",
                "      - name: Seal and read back exact dual-lifecycle nightly artifact after upload\n",
                1,
            ),
        )
        for mutated in mutations:
            with self.subTest():
                self.assertNotEqual(workflow, mutated)
                self.assertTrue(
                    checker.workflow_failures(mutated, check_canonical_bytes=False)
                )

    def test_duplicate_yaml_mapping_is_rejected(self) -> None:
        workflow = self.workflow().replace(
            "permissions:\n  contents: read\n",
            "permissions:\n  contents: read\npermissions:\n  contents: read\n",
            1,
        )
        failures = checker.workflow_failures(workflow, check_canonical_bytes=False)
        self.assertTrue(any("duplicate mapping key" in failure for failure in failures))

    def test_contract_test_manifest_is_exact(self) -> None:
        _, identities = checker.discover_contract_tests()
        self.assertEqual(checker.CONTRACT_TEST_COUNT, len(identities))
        self.assertEqual([], checker.contract_test_selection_failures(identities))
        for mutation in (
            identities[:-1],
            identities + (identities[-1],),
            tuple(reversed(identities)),
            identities[:-1] + ("script.Replaced.test_replaced",),
        ):
            with self.subTest():
                self.assertTrue(checker.contract_test_selection_failures(mutation))

    def test_lifecycle_source_snapshot_binds_nightly_lane_inputs(self) -> None:
        required = {
            ".github/workflows/product-nightly.yml",
            "script/check_product_nightly_ci.py",
            "script/test_check_product_nightly_ci.py",
            "script/check_no_device_quality.sh",
            "script/test_run_android_headless_emulator_product_lifecycle.py",
            "script/test_check_android_headless_emulator_product_lifecycle.py",
            "script/test_run_android_headless_emulator_product_lifecycle_v2.py",
            "script/test_check_android_headless_emulator_product_lifecycle_v2.py",
        }
        configured = {
            path.as_posix()
            for path in lifecycle_v2.SOURCE_SUCCESSOR_FILES
        }
        self.assertTrue(required.issubset(configured))
        snapshot = lifecycle_v2.source_snapshot()
        retained = {
            record["path"]
            for record in snapshot["files"]
        }
        self.assertTrue(required.issubset(retained))
        self.assertEqual(145, snapshot["fileCount"])

    def test_contract_result_rejects_counts_order_and_result_categories(self) -> None:
        _, identities = checker.discover_contract_tests()
        baseline = unittest.TestResult()
        baseline.testsRun = len(identities)
        baseline.started_test_ids = list(identities)
        self.assertEqual(
            [],
            checker.contract_test_result_failures(
                baseline,
                expected_ids=identities,
            ),
        )
        for count in (len(identities) - 1, len(identities) + 1, True):
            result = unittest.TestResult()
            result.testsRun = count
            result.started_test_ids = list(identities)
            self.assertTrue(
                checker.contract_test_result_failures(
                    result,
                    expected_ids=identities,
                )
            )
        reordered = unittest.TestResult()
        reordered.testsRun = len(identities)
        reordered.started_test_ids = list(reversed(identities))
        self.assertTrue(
            checker.contract_test_result_failures(
                reordered,
                expected_ids=identities,
            )
        )
        for attribute, record in (
            ("skipped", (None, "skip")),
            ("failures", (None, "failure")),
            ("errors", (None, "error")),
            ("expectedFailures", (None, "expected")),
            ("unexpectedSuccesses", None),
        ):
            result = unittest.TestResult()
            result.testsRun = len(identities)
            result.started_test_ids = list(identities)
            getattr(result, attribute).append(record)
            self.assertTrue(
                checker.contract_test_result_failures(
                    result,
                    expected_ids=identities,
                )
            )

    def test_github_context_is_exact_and_rejects_wrong_types_or_scope(self) -> None:
        environment = self.github_environment()
        context = checker.github_context(environment)
        self.assertEqual(123456789, context["runId"])
        self.assertEqual(2, context["runAttempt"])
        for key, value in (
            ("GITHUB_EVENT_NAME", "push"),
            ("GITHUB_REF", "refs/heads/release"),
            ("GITHUB_RUN_ID", "0"),
            ("GITHUB_RUN_ATTEMPT", "true"),
            ("GITHUB_SHA", "A" * 40),
            ("GITHUB_WORKFLOW_REF", "example/aetherlink/other.yml@refs/heads/main"),
        ):
            mutated = dict(environment)
            mutated[key] = value
            with self.subTest(key=key):
                with self.assertRaises(checker.NightlyContractError):
                    checker.github_context(mutated)

    def test_source_records_bind_exact_git_commit_blobs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            subprocess.run(["git", "init", "-q", os.fspath(root)], check=True)
            subprocess.run(
                ["git", "-C", os.fspath(root), "config", "user.name", "Nightly Test"],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    os.fspath(root),
                    "config",
                    "user.email",
                    "nightly-test@example.invalid",
                ],
                check=True,
            )
            (root / "alpha.txt").write_bytes(b"alpha\n")
            executable = root / "runner.sh"
            executable.write_bytes(b"#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
            subprocess.run(
                ["git", "-C", os.fspath(root), "add", "alpha.txt", "runner.sh"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", os.fspath(root), "commit", "-q", "-m", "fixture"],
                check=True,
            )
            commit = subprocess.run(
                ["git", "-C", os.fspath(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            records = []
            for path, mode in (("alpha.txt", "0644"), ("runner.sh", "0755")):
                raw = (root / path).read_bytes()
                records.append(
                    {
                        "mode": mode,
                        "path": path,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size": len(raw),
                    }
                )
            digest = hashlib.sha256()
            for record in records:
                digest.update(
                    (
                        f"{record['path']}\0{record['mode']}\0{record['size']}\0"
                        f"{record['sha256']}\n"
                    ).encode("ascii")
                )
            source = {
                "algorithm": "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1",
                "fileCount": len(records),
                "files": records,
                "sha256": digest.hexdigest(),
            }
            self.assertEqual(
                [],
                checker.source_git_binding_failures(
                    source,
                    git_checkout=root,
                    commit=commit,
                ),
            )
            mutated = json.loads(json.dumps(source))
            mutated["files"][0]["sha256"] = "0" * 64
            self.assertTrue(
                checker.source_git_binding_failures(
                    mutated,
                    git_checkout=root,
                    commit=commit,
                )
            )

    def test_canonical_json_rejects_duplicate_and_noncanonical_bytes(self) -> None:
        self.assertEqual(
            {"a": 1},
            checker.parse_canonical_json(b'{"a":1}\n', label="fixture"),
        )
        for raw in (b'{"a":1,"a":1}\n', b'{"a": 1}\n', b'{"a":1}'):
            with self.subTest(raw=raw):
                with self.assertRaises(checker.NightlyContractError):
                    checker.parse_canonical_json(raw, label="fixture")

    def test_regular_file_reader_rejects_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "target.json"
            target.write_bytes(b"{}\n")
            self.assertEqual(
                b"{}\n",
                checker.read_regular_file(target, max_bytes=16),
            )
            hardlink = root / "hardlink.json"
            os.link(target, hardlink)
            with self.assertRaises(checker.NightlyContractError):
                checker.read_regular_file(target, max_bytes=16)
            hardlink.unlink()
            symlink = root / "symlink.json"
            symlink.symlink_to(target)
            with self.assertRaises(checker.NightlyContractError):
                checker.read_regular_file(symlink, max_bytes=16)

            physical = root / "physical"
            physical.mkdir()
            nested = physical / "nested.json"
            nested.write_bytes(b"{}\n")
            alias = root / "alias"
            alias.symlink_to(physical, target_is_directory=True)
            with self.assertRaises(checker.NightlyContractError):
                checker.read_regular_file(alias / "nested.json", max_bytes=16)

            held_parent = root / "held-parent"
            held_parent.mkdir()
            held_target = held_parent / "target.json"
            held_target.write_bytes(b"{}\n")
            held = checker._PhysicalParent(held_target)
            try:
                displaced = root / "held-parent-displaced"
                held_parent.rename(displaced)
                held_parent.mkdir()
                with self.assertRaises(checker.NightlyContractError):
                    held.verify()
            finally:
                held.close()

    def test_exclusive_writer_round_trips_and_rejects_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            output = root / "receipt.json"
            checker.write_exclusive_regular(output, b'{"status":"passed"}\n')
            self.assertEqual(b'{"status":"passed"}\n', output.read_bytes())
            with self.assertRaises(checker.NightlyContractError):
                checker.write_exclusive_regular(output, b"{}\n")

            replacement = root / "replacement.json"
            displaced = root / "created-displaced.json"

            def replace_then_fail(_descriptor: int, _view: object) -> int:
                replacement.rename(displaced)
                replacement.write_bytes(b"replacement\n")
                raise OSError("injected write failure after path replacement")

            with mock.patch.object(checker.os, "write", side_effect=replace_then_fail):
                with self.assertRaises(OSError):
                    checker.write_exclusive_regular(replacement, b"original\n")
            self.assertEqual(b"replacement\n", replacement.read_bytes())
            self.assertTrue(displaced.exists())

    def test_dual_provenance_and_archive_round_trip_bind_both_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            paths, captures, opened = self.captured_fixture(root)
            bundle_id = f"{paths['v1'].parent.name}--{paths['v2'].parent.name}"
            provenance_root = root / "provenance"
            provenance_root.mkdir(mode=0o700)
            provenance = provenance_root / f"{bundle_id}.json"
            environment = self.github_environment()
            with (
                mock.patch.object(
                    checker, "_open_validated_lifecycle_snapshot", side_effect=opened
                ),
                mock.patch.object(
                    checker, "source_git_binding_failures", return_value=[]
                ) as git_binding,
            ):
                checker.write_provenance(
                    provenance,
                    paths["v1"],
                    paths["v2"],
                    sdk_root=root,
                    java_home=root,
                    environment=environment,
                )
                self.assertEqual(
                    [],
                    checker.provenance_failures(
                        provenance,
                        paths["v1"],
                        paths["v2"],
                        sdk_root=root,
                        java_home=root,
                        environment=environment,
                    ),
                )
                self.assertTrue(
                    all(call.kwargs["commit"] == "a" * 40 for call in git_binding.call_args_list)
                )
            payload = json.loads(provenance.read_bytes())
            self.assertEqual(checker.PROVENANCE_CONTRACT, payload["contract"])
            self.assertEqual(["v1", "v2"], [item["lane"] for item in payload["lifecycles"]])
            self.assertEqual([13, 5], [item["scenarioCount"] for item in payload["lifecycles"]])
            self.assertEqual([46, 72], [item["evidenceFileCount"] for item in payload["lifecycles"]])
            self.assertEqual(
                ["a" * 40, "a" * 40],
                [item["sourceGitCommit"] for item in payload["lifecycles"]],
            )

            lane_evidence = {lane: captures[lane][2] for lane in checker.LANE_ORDER}
            provenance_raw = provenance.read_bytes()
            archive_raw = checker._archive_bytes(lane_evidence, provenance_raw)
            self.assertEqual(
                archive_raw, checker._archive_bytes(lane_evidence, provenance_raw)
            )
            archive = root / f"candidate-{bundle_id}.tar"
            checker.write_exclusive_regular(
                archive, archive_raw, max_bytes=checker.MAX_ARCHIVE_BYTES
            )
            expected_sha256 = hashlib.sha256(archive_raw).hexdigest()
            with mock.patch.object(
                checker, "source_git_binding_failures", return_value=[]
            ):
                self.assertEqual(
                    [],
                    checker.archive_failures(
                        archive,
                        expected_sha256=expected_sha256,
                        environment=environment,
                        git_checkout=root,
                    ),
                )
            lifecycles, archived, archived_provenance = checker._archive_contents(archive_raw)
            self.assertEqual(set(checker.LANE_ORDER), set(lifecycles))
            self.assertEqual(
                {"lifecycle-v1/", "lifecycle-v2/"},
                {
                    next(
                        prefix
                        for prefix in checker.ARCHIVE_LANE_PREFIXES.values()
                        if member.name.startswith(prefix)
                    )
                    for member in tarfile.open(fileobj=io.BytesIO(archive_raw), mode="r:").getmembers()
                    if member.name != checker.ARCHIVE_PROVENANCE_PATH
                },
            )
            self.assertEqual(set(lifecycle_v1.EVIDENCE_PATHS) | {"result.json"}, set(archived["v1"]))
            self.assertEqual(set(lifecycle_v2.EVIDENCE_PATHS) | {"result.json"}, set(archived["v2"]))
            self.assertEqual(provenance_raw, archived_provenance)

            captured_source = root / "captured-v1" / paths["v1"].parent.name
            captured_source.mkdir(parents=True)
            original_result = captured_source / "result.json"
            original_evidence = captured_source / "evidence.txt"
            original_result.write_bytes(b'{"captured":true}\n')
            original_evidence.write_bytes(b"captured evidence\n")
            observed: dict[str, object] = {}

            class FakeV1Lifecycle:
                EVIDENCE_PATHS = ("evidence.txt",)

                @staticmethod
                def result_failures(result_path, **_kwargs):
                    observed["path"] = result_path
                    observed["result"] = result_path.read_bytes()
                    observed["evidence"] = (result_path.parent / "evidence.txt").read_bytes()
                    original_result.write_bytes(b'{"captured":false}\n')
                    return []

            with mock.patch.object(
                checker, "_lifecycle_module", return_value=FakeV1Lifecycle
            ):
                with self.assertRaisesRegex(
                    checker.NightlyContractError, "changed during binding"
                ):
                    checker._open_validated_lifecycle_snapshot(
                        "v1",
                        original_result,
                        sdk_root=root,
                        java_home=root,
                    )
            self.assertNotEqual(original_result, observed["path"])
            self.assertEqual(b'{"captured":true}\n', observed["result"])
            self.assertEqual(b"captured evidence\n", observed["evidence"])

    def test_archive_rejects_lane_omission_order_metadata_and_cross_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            paths, captures, _opened = self.captured_fixture(root)
            context = checker.github_context(self.github_environment())
            with mock.patch.object(checker, "source_git_binding_failures", return_value=[]):
                provenance_payload = checker._expected_provenance_from_captures(
                    captures,
                    environment=self.github_environment(),
                    git_checkout=root,
                )
            provenance_raw = checker.canonical_json_bytes(provenance_payload)
            lane_evidence = {lane: captures[lane][2] for lane in checker.LANE_ORDER}
            archive_raw = checker._archive_bytes(lane_evidence, provenance_raw)

            with self.assertRaises(checker.NightlyContractError):
                checker._archive_bytes({"v2": lane_evidence["v2"], "v1": lane_evidence["v1"]}, provenance_raw)
            with self.assertRaises(checker.NightlyContractError):
                checker._archive_bytes({"v1": lane_evidence["v1"]}, provenance_raw)
            with self.assertRaises(checker.NightlyContractError):
                checker._lane_provenance_from_capture(
                    "v1",
                    lifecycle=lifecycle_v1,
                    result_directory=paths["v2"].parent,
                    result_capture=captures["v2"][3],
                    result=captures["v2"][4],
                    evidence_capture=captures["v2"][2],
                    context=context,
                    git_checkout=root,
                )

            def repack(transform):
                entries = []
                with tarfile.open(fileobj=io.BytesIO(archive_raw), mode="r:") as source:
                    for member in source.getmembers():
                        stream = source.extractfile(member)
                        self.assertIsNotNone(stream)
                        entries.append((member, stream.read()))
                transform(entries)
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w:", format=tarfile.USTAR_FORMAT) as target:
                    for member, data in entries:
                        target.addfile(member, io.BytesIO(data) if member.isfile() else None)
                return buffer.getvalue()

            transformations = {
                "omission": lambda entries: entries.pop(0),
                "order": lambda entries: entries.__setitem__(slice(0, 2), [entries[1], entries[0]]),
                "duplicate": lambda entries: entries.insert(1, entries[0]),
                "metadata": lambda entries: setattr(entries[0][0], "mtime", 1),
            }
            for label, transform in transformations.items():
                with self.subTest(label=label):
                    with self.assertRaises(checker.NightlyContractError):
                        checker._archive_contents(repack(transform))

            noncanonical = json.loads(captures["v1"][3].data)
            noncanonical_raw = json.dumps(noncanonical, indent=2).encode() + b"\n"
            mutated = dict(lane_evidence)
            mutated_v1 = dict(lane_evidence["v1"])
            mutated_v1["result.json"] = lifecycle_v2.CapturedEvidenceFile(
                data=noncanonical_raw, identity=(), mode="0644"
            )
            mutated["v1"] = mutated_v1
            raw = checker._archive_bytes(mutated, provenance_raw)
            archive = root / f"candidate-{provenance_payload['bundleId']}.tar"
            archive.write_bytes(raw)
            with mock.patch.object(checker, "source_git_binding_failures", return_value=[]):
                failures = checker.archive_failures(
                    archive,
                    expected_sha256=hashlib.sha256(raw).hexdigest(),
                    environment=self.github_environment(),
                    git_checkout=root,
                )
            self.assertTrue(any("canonical" in failure for failure in failures))

    def test_provenance_rejects_mutation_wrong_filename_counts_order_and_source_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            paths, captures, opened = self.captured_fixture(root)
            bundle_id = f"{paths['v1'].parent.name}--{paths['v2'].parent.name}"
            provenance_root = root / "provenance"
            provenance_root.mkdir(mode=0o700)
            provenance = provenance_root / f"{bundle_id}.json"
            environment = self.github_environment()
            with (
                mock.patch.object(checker, "_open_validated_lifecycle_snapshot", side_effect=opened),
                mock.patch.object(checker, "source_git_binding_failures", return_value=[]),
            ):
                checker.write_provenance(
                    provenance,
                    paths["v1"],
                    paths["v2"],
                    sdk_root=root,
                    java_home=root,
                    environment=environment,
                )
                payload = json.loads(provenance.read_bytes())
                payload["lifecycles"].reverse()
                provenance.write_bytes(checker.canonical_json_bytes(payload))
                self.assertTrue(
                    checker.provenance_failures(
                        provenance,
                        paths["v1"],
                        paths["v2"],
                        sdk_root=root,
                        java_home=root,
                        environment=environment,
                    )
                )
                wrong = provenance_root / "wrong.json"
                provenance.replace(wrong)
                self.assertTrue(
                    checker.provenance_failures(
                        wrong,
                        paths["v1"],
                        paths["v2"],
                        sdk_root=root,
                        java_home=root,
                        environment=environment,
                    )
                )

            captures["v1"][4]["source"]["fileCount"] = True
            captures["v1"][2]["result.json"] = lifecycle_v2.CapturedEvidenceFile(
                data=checker.canonical_json_bytes(captures["v1"][4]),
                identity=(),
                mode="0644",
            )
            mutated = (
                captures["v1"][0],
                captures["v1"][1],
                captures["v1"][2],
                captures["v1"][2]["result.json"],
                captures["v1"][4],
            )
            captures["v1"] = mutated
            with mock.patch.object(checker, "source_git_binding_failures", return_value=[]):
                with self.assertRaises(checker.NightlyContractError):
                    checker._expected_provenance_from_captures(
                        captures, environment=environment, git_checkout=root
                    )

            paths, captures, _opened = self.captured_fixture(root / "fresh")
            def reject_v2_source(_source, *, git_checkout, commit):
                del git_checkout, commit
                return ["source bytes differ from GITHUB_SHA"] if _source is captures["v2"][4]["source"] else []
            with mock.patch.object(
                checker, "source_git_binding_failures", side_effect=reject_v2_source
            ):
                with self.assertRaisesRegex(checker.NightlyContractError, "v2 source"):
                    checker._expected_provenance_from_captures(
                        captures, environment=environment, git_checkout=root
                    )


if __name__ == "__main__":
    unittest.main()
