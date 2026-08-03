#!/usr/bin/env python3
"""Focused regressions for independent Android repeatability readback."""

from __future__ import annotations

import copy
import ast
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from script import check_android_release_repeatability_current as checker


class AndroidReleaseRepeatabilityCheckerTests(unittest.TestCase):
    @staticmethod
    def projection() -> dict[str, object]:
        kind_by_path = {
            path: kind
            for path, kind in (
                ((checker.archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/0/app-release-unsigned.dm").as_posix(), checker.DM_COMPARISON_KIND),
                ((checker.archive.ANDROID_RELEASE_APK_RELATIVE_PATH.parent / "baselineProfiles/1/app-release-unsigned.dm").as_posix(), checker.DM_COMPARISON_KIND),
                ((checker.archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "mapping.prt").as_posix(), checker.MAPPING_PRT_COMPARISON_KIND),
                ((checker.archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "resources.txt").as_posix(), checker.RESOURCES_COMPARISON_KIND),
                ((checker.archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "seeds.txt").as_posix(), checker.SEEDS_COMPARISON_KIND),
            )
        }
        records = []
        for path in sorted({"out.bin", *checker.NORMALIZED_COMPARISON_PATHS}):
            raw_hash = hashlib.sha256(path.encode()).hexdigest()
            records.append({
                "comparison": {"kind": kind_by_path.get(path, checker.RAW_COMPARISON_KIND), "sha256": raw_hash},
                "mode": 0o644,
                "path": path,
                "sha256": raw_hash,
                "size": len(path),
            })
        return {
            "comparisonGraphSha256": checker.comparison_graph_digest(records),
            "dex": {"logicalSha256": "1" * 64, "memberCount": 1},
            "fileCount": len(records),
            "files": records,
            "jni": {
                "intermediateAbis": ["arm64-v8a", "armeabi-v7a", "x86", "x86_64"],
                "logicalSha256": "2" * 64,
                "memberCount": 5,
                "mergedLogicalSha256": "3" * 64,
                "packagedAbis": ["arm64-v8a"],
                "strippedLogicalSha256": "4" * 64,
            },
            "profiles": {"logicalSha256": "5" * 64, "memberCount": 2},
            "rawGraphSha256": checker.raw_graph_digest(records),
        }

    @staticmethod
    def process() -> dict[str, object]:
        return {
            "exitCode": 0,
            "stderr": {"sha256": "0" * 64, "size": 0},
            "stdout": {"sha256": "0" * 64, "size": 0},
        }

    @classmethod
    def document(cls) -> dict[str, object]:
        source = {"algorithm": checker.SOURCE_ALGORITHM, "fileCount": 6, "sha256": "a" * 64, "size": 42}
        projection = cls.projection()
        process = cls.process()
        return {
            "comparison": {
                "comparisonGraphIdentical": True,
                "fileCount": 6,
                "normalizedFileCount": 5,
                "rawByteIdentical": True,
                "rawDifferentFileCount": 0,
                "rawDifferentPaths": [],
                "rawIdenticalFileCount": 6,
                "semanticIdentical": True,
            },
            "contract": checker.CONTRACT,
            "execution": {
                "deadlineSeconds": checker.BUILD_TIMEOUT_SECONDS,
                "prepareArgv": list(checker.PREPARE_COMMAND),
                "runs": {
                    "a": {"prepare": copy.deepcopy(process), "workflow": copy.deepcopy(process)},
                    "b": {"prepare": copy.deepcopy(process), "workflow": copy.deepcopy(process)},
                },
                "workflowArgv": list(checker.BUILD_COMMAND),
            },
            "limitations": list(checker.LIMITATIONS),
            "readback": {"apk": {"sha256": "6" * 64, "size": 1}, "versionCode": 1},
            "runs": {"a": copy.deepcopy(projection), "b": copy.deepcopy(projection)},
            "schemaVersion": checker.SCHEMA_VERSION,
            "source": {"after": copy.deepcopy(source), "before": copy.deepcopy(source), "between": copy.deepcopy(source), "stable": True},
            "status": "passed",
            "toolchain": {"fixture": "current"},
        }

    @staticmethod
    def write_result(path: Path, document: dict[str, object], *, mode: int = 0o600) -> None:
        path.write_bytes(checker.canonical_json_bytes(document))
        path.chmod(mode)

    def test_checker_source_does_not_import_producer(self) -> None:
        source = Path(checker.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported.extend(alias.name for alias in node.names)
        self.assertFalse(
            any(name.endswith("run_android_release_repeatability_current") for name in imported)
        )

    def test_projection_rejects_bool_for_every_integer_gate(self) -> None:
        mutations = (
            ("fileCount",),
            ("files", 0, "mode"),
            ("files", 0, "size"),
            ("dex", "memberCount"),
            ("jni", "memberCount"),
            ("profiles", "memberCount"),
        )
        for path in mutations:
            with self.subTest(path=path):
                value = self.projection()
                target: object = value
                for part in path[:-1]:
                    target = target[part]  # type: ignore[index]
                target[path[-1]] = True  # type: ignore[index]
                with self.assertRaises(checker.RepeatabilityCheckError):
                    checker.validate_projection(value, "projection")

    def test_exact_bool_rejects_integer_one(self) -> None:
        with self.assertRaises(checker.RepeatabilityCheckError):
            checker.exact_bool(1, True, "flag")

    def test_ab_comparison_accepts_only_normalized_raw_differences(self) -> None:
        run_a = self.projection()
        run_b = copy.deepcopy(run_a)
        for record in run_b["files"]:
            if record["path"] in checker.NORMALIZED_COMPARISON_PATHS:
                record["sha256"] = hashlib.sha256((record["path"] + "-b").encode()).hexdigest()
                record["size"] += 1
        run_b["rawGraphSha256"] = checker.raw_graph_digest(run_b["files"])
        paths = sorted(checker.NORMALIZED_COMPARISON_PATHS)
        summary = {
            "comparisonGraphIdentical": True,
            "fileCount": 6,
            "normalizedFileCount": 5,
            "rawByteIdentical": False,
            "rawDifferentFileCount": 5,
            "rawDifferentPaths": paths,
            "rawIdenticalFileCount": 1,
            "semanticIdentical": True,
        }
        self.assertEqual(checker.validate_ab_comparison(run_a, run_b, summary), summary)
        unauthorized = copy.deepcopy(run_b)
        raw = next(record for record in unauthorized["files"] if record["path"] == "out.bin")
        raw["sha256"] = "f" * 64
        with self.assertRaises(checker.RepeatabilityCheckError):
            checker.validate_ab_comparison(run_a, unauthorized, summary)
        comparison_drift = copy.deepcopy(run_b)
        comparison_drift["files"][0]["comparison"]["sha256"] = "e" * 64
        with self.assertRaises(checker.RepeatabilityCheckError):
            checker.validate_ab_comparison(run_a, comparison_drift, summary)
        bad_summary = copy.deepcopy(summary)
        bad_summary["rawDifferentFileCount"] = True
        with self.assertRaises(checker.RepeatabilityCheckError):
            checker.validate_ab_comparison(run_a, run_b, bad_summary)

    def test_result_reader_requires_canonical_mode_0600_single_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "result.json"
            self.write_result(path, self.document(), mode=0o644)
            with self.assertRaises(checker.RepeatabilityCheckError):
                checker.load_result(path)
            path.chmod(0o600)
            self.assertEqual(checker.load_result(path), self.document())
            hard = root / "hard.json"
            os.link(path, hard)
            with self.assertRaises(checker.RepeatabilityCheckError):
                checker.load_result(path)

    def test_result_reader_rejects_symlink_oversize_and_noncanonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            self.write_result(target, self.document())
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaises(checker.RepeatabilityCheckError):
                checker.load_result(link)
            target.write_bytes(b" " + checker.canonical_json_bytes(self.document()))
            target.chmod(0o600)
            with self.assertRaisesRegex(checker.RepeatabilityCheckError, "canonical"):
                checker.load_result(target)
            with mock.patch.object(checker, "MAX_RESULT_BYTES", 4):
                with self.assertRaises(checker.RepeatabilityCheckError):
                    checker.load_result(target)

    def test_directory_inventory_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "target").write_bytes(b"x")
            (root / "link").symlink_to(root / "target")
            with self.assertRaises(checker.RepeatabilityCheckError):
                checker.directory_names(root, "fixture", entries_are_directories=False)

    def test_independent_check_reconstructs_current_source_readback_and_graph(self) -> None:
        document = self.document()
        source = document["source"]["before"]  # type: ignore[index]
        projection = document["runs"]["a"]  # type: ignore[index]
        readback = document["readback"]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            self.write_result(path, document)
            with mock.patch.object(checker, "current_toolchain", return_value=document["toolchain"]), \
                mock.patch.object(checker, "source_snapshot", side_effect=[source, source]), \
                mock.patch.object(checker.archive, "verify_android_release_build_outputs", return_value=readback), \
                mock.patch.object(checker, "capture_output_graph", return_value=projection):
                self.assertEqual(checker.check(path, root=Path(temporary)), document)

    def test_check_rejects_schema_and_readback_bool_integer_confusion(self) -> None:
        for mutation in ("schema", "readback", "readback_float"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                document = self.document()
                if mutation == "schema":
                    document["schemaVersion"] = True
                elif mutation == "readback":
                    document["readback"]["versionCode"] = True  # type: ignore[index]
                else:
                    document["readback"]["versionCode"] = 1.0  # type: ignore[index]
                path = Path(temporary) / "result.json"
                self.write_result(path, document)
                if mutation == "readback_float":
                    source = document["source"]["before"]  # type: ignore[index]
                    projection = document["runs"]["a"]  # type: ignore[index]
                    with mock.patch.object(checker, "current_toolchain", return_value=document["toolchain"]), \
                        mock.patch.object(checker, "source_snapshot", side_effect=[source, source]), \
                        mock.patch.object(checker.archive, "verify_android_release_build_outputs", return_value={"apk": {"sha256": "6" * 64, "size": 1}, "versionCode": 1}), \
                        mock.patch.object(checker, "capture_output_graph", return_value=projection):
                        with self.assertRaises(checker.RepeatabilityCheckError):
                            checker.check(path, root=Path(temporary))
                else:
                    with self.assertRaises(checker.RepeatabilityCheckError):
                        checker.check(path, root=Path(temporary))


if __name__ == "__main__":
    unittest.main()
