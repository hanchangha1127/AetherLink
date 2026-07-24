#!/usr/bin/env python3
"""Fixture-copy and mutation tests for the semantic-review v1 readback."""

from __future__ import annotations

import ast
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    ROOT / "script/check_p2p_nat_g2_pion_rung3_semantic_review_result_v1.py"
)
CHECKER_SOURCE = CHECKER_PATH.read_bytes()
CHECKER = ModuleType("g2_pion_rung3_semantic_review_result_v1_checker_under_test")
CHECKER.__file__ = os.fspath(CHECKER_PATH)
CHECKER.__package__ = None
exec(
    compile(
        CHECKER_SOURCE,
        os.fspath(CHECKER_PATH),
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    ),
    CHECKER.__dict__,
    CHECKER.__dict__,
)


@contextmanager
def fixture_repository():
    with tempfile.TemporaryDirectory(prefix="aetherlink-semantic-postrun-") as temporary:
        fixture_root = Path(temporary).resolve()
        for relative in CHECKER.ALLOWED_PATHS:
            source = ROOT / relative
            destination = fixture_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination, follow_symlinks=False)
        yield fixture_root


def parse_documents(root: Path) -> dict[str, dict[str, object]]:
    return {
        path: CHECKER.strict_canonical_json((root / path).read_bytes(), path)
        for path in CHECKER.JSON_PATHS
    }


def rebound(document: dict[str, object], scope: str) -> dict[str, object]:
    result = copy.deepcopy(document)
    payload = copy.deepcopy(result)
    payload.pop("contentBinding", None)
    result["contentBinding"] = {
        "algorithm": "sha256",
        "canonicalization": "utf8_ascii_escaped_sorted_keys_compact_single_lf",
        "scope": scope,
        "sha256": CHECKER.sha256_bytes(CHECKER.canonical_json_bytes(payload)),
    }
    return result


class StaticContractTests(unittest.TestCase):
    def test_checker_has_no_enumeration_write_execution_or_external_io_api(self):
        tree = ast.parse(CHECKER_SOURCE)
        attribute_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        forbidden_calls = {
            "chmod",
            "chown",
            "fsync",
            "glob",
            "link",
            "listdir",
            "makedirs",
            "mkdir",
            "pwrite",
            "remove",
            "rename",
            "replace",
            "rglob",
            "scandir",
            "symlink",
            "truncate",
            "unlink",
            "walk",
            "write",
        }
        self.assertTrue(attribute_calls.isdisjoint(forbidden_calls))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertTrue(
            imported.isdisjoint(
                {"subprocess", "socket", "urllib", "requests", "http", "ssl"}
            )
        )
        names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"compile", "eval", "exec"}.isdisjoint(names))

    def test_allowlist_is_fixed_tracked_only_and_manifest_last(self):
        self.assertEqual(len(CHECKER.ALLOWED_PATHS), 8)
        self.assertEqual(CHECKER.ALLOWED_PATHS[-1], CHECKER.MANIFEST_PATH)
        self.assertTrue(all(not Path(path).is_absolute() for path in CHECKER.ALLOWED_PATHS))
        self.assertTrue(all("build" not in Path(path).parts for path in CHECKER.ALLOWED_PATHS))
        self.assertEqual(set(CHECKER.EXPECTED_RAW_SHA256), set(CHECKER.ALLOWED_PATHS))
        self.assertEqual(set(CHECKER.EXPECTED_CONTENT_SHA256), set(CHECKER.JSON_PATHS))

    def test_strict_json_rejects_duplicate_cr_missing_lf_nonfinite_and_spacing(self):
        invalid = (
            b'{"a":1,"a":2}\n',
            b'{"a":1}\r\n',
            b'{"a":1}',
            b'{"a":NaN}\n',
            b'{ "a":1}\n',
            b'\xff\n',
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(CHECKER.CheckError):
                CHECKER.strict_canonical_json(raw, "fixture")

    def test_recursive_exactness_rejects_bool_integer_aliases(self):
        self.assertFalse(CHECKER.same_typed_value(False, 0))
        self.assertFalse(CHECKER.same_typed_value({"closed": False}, {"closed": 0}))
        self.assertFalse(CHECKER.same_typed_value([True], [1]))


class FixedReadTests(unittest.TestCase):
    def test_valid_fixture_passes_with_exact_read_only_flags_and_boundaries(self):
        with fixture_repository() as fixture_root:
            real_open = CHECKER.os.open
            flags_seen: list[int] = []

            def probe(path, flags, *args, **kwargs):
                flags_seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(CHECKER.os, "open", side_effect=probe):
                result = CHECKER.check_repository(fixture_root)
        self.assertEqual(result["fixedPathCount"], 8)
        self.assertEqual(result["fixedPathReadCount"], 16)
        self.assertEqual(result["fixedPathReadCountPerPass"], 8)
        self.assertEqual(result["fullSetReadbackPassCount"], 2)
        self.assertEqual(result["heldFileDescriptorCount"], 8)
        self.assertGreater(result["heldDirectoryDescriptorCount"], 8)
        self.assertEqual(
            result["heldDescriptorCount"],
            result["heldFileDescriptorCount"]
            + result["heldDirectoryDescriptorCount"],
        )
        self.assertTrue(result["finalFullSetReadbackCompleted"])
        self.assertEqual(result["finalIdentityBarrierCount"], 2)
        self.assertTrue(result["repositoryPathAncestryHeldAndRevalidated"])
        self.assertEqual(result["fixedTrackedByteCount"], 255_402)
        self.assertEqual(result["fixedAbsenceCheckCount"], 10)
        self.assertEqual(result["fixedAbsenceCheckCountPerPass"], 5)
        self.assertTrue(result["manifestReadAndValidatedLast"])
        self.assertTrue(result["independentReadbackCompleted"])
        self.assertTrue(result["boundedSemanticPublicationCheckpointEvidenceEstablished"])
        self.assertTrue(result["candidateSemanticDigestsIndependentlyRecomputed"])
        self.assertTrue(result["findingAggregationIndependentlyRecomputed"])
        self.assertFalse(result["semanticJudgmentsIndependentlyReproducedByChecker"])
        self.assertFalse(result["sourceLocationBoundsIndependentlyRevalidatedByChecker"])
        self.assertFalse(result["semanticClosureComplete"])
        self.assertFalse(result["dependencyClosureComplete"])
        self.assertFalse(result["rungThreeComplete"])
        self.assertFalse(result["candidateSelected"])
        self.assertFalse(result["librarySelected"])
        write_mask = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        self.assertTrue(all(flags & write_mask == 0 for flags in flags_seen))
        self.assertTrue(all(flags & os.O_NOFOLLOW for flags in flags_seen))
        self.assertTrue(all(flags & os.O_NONBLOCK for flags in flags_seen))

    def test_missing_each_fixed_path_fails_closed(self):
        for relative in CHECKER.ALLOWED_PATHS:
            with self.subTest(path=relative), fixture_repository() as fixture_root:
                (fixture_root / relative).unlink()
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)

    def test_each_raw_byte_pin_rejects_mutation(self):
        for relative in CHECKER.ALLOWED_PATHS:
            with self.subTest(path=relative), fixture_repository() as fixture_root:
                path = fixture_root / relative
                raw = path.read_bytes()
                path.write_bytes(raw[:-1] + b" \n")
                if relative in CHECKER.PUBLISHED_PATHS:
                    os.chmod(path, 0o600)
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)

    def test_symlink_fifo_hardlink_and_published_mode_fail_closed(self):
        with fixture_repository() as fixture_root:
            path = fixture_root / CHECKER.MANIFEST_PATH
            target = path.with_name("manifest-target.json")
            shutil.copy2(path, target)
            path.unlink()
            path.symlink_to(target.name)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_repository(fixture_root)
        with fixture_repository() as fixture_root:
            path = fixture_root / CHECKER.RESULT_PATH
            path.unlink()
            os.mkfifo(path, 0o600)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_repository(fixture_root)
        with fixture_repository() as fixture_root:
            path = fixture_root / CHECKER.CLASSIFICATIONS_PATH
            os.link(path, path.with_name("classification-alias.json"))
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_repository(fixture_root)
        with fixture_repository() as fixture_root:
            path = fixture_root / CHECKER.MANIFEST_PATH
            os.chmod(path, 0o644)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_repository(fixture_root)

    def test_each_failure_or_staging_residue_fails_closed(self):
        for name in CHECKER.ABSENT_NAMES:
            with self.subTest(name=name), fixture_repository() as fixture_root:
                path = fixture_root / CHECKER.RUNG3 / name
                path.write_bytes(b"residue")
                os.chmod(path, 0o600)
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)

    def test_unsafe_paths_and_unlisted_reads_are_rejected(self):
        for path in (
            "/absolute.json",
            "../escape.json",
            "build/archive.zip",
            "README.md",
        ):
            with self.subTest(path=path), self.assertRaises(CHECKER.CheckError):
                CHECKER._allowed_parts(path)

    def test_symlinked_root_and_group_world_writable_descendant_fail(self):
        with fixture_repository() as fixture_root:
            linked_root = fixture_root.with_name(f"{fixture_root.name}-link")
            linked_root.symlink_to(fixture_root, target_is_directory=True)
            try:
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(linked_root)
            finally:
                linked_root.unlink()
        with fixture_repository() as fixture_root:
            rung_three = fixture_root / CHECKER.RUNG3
            os.chmod(rung_three, 0o777)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_repository(fixture_root)

    def test_stat_to_open_and_post_read_name_replacements_fail(self):
        with fixture_repository() as fixture_root:
            victim = fixture_root / CHECKER.CLASSIFICATIONS_PATH
            replacement = victim.with_name("replacement.json")
            shutil.copy2(victim, replacement)
            real_open = CHECKER.os.open
            replaced = False

            def replace_before_open(path, flags, *args, **kwargs):
                nonlocal replaced
                if (
                    not replaced
                    and path == victim.name
                    and kwargs.get("dir_fd") is not None
                    and not flags & os.O_DIRECTORY
                ):
                    os.replace(replacement, victim)
                    replaced = True
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(CHECKER.os, "open", side_effect=replace_before_open):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)
        with fixture_repository() as fixture_root:
            victim = fixture_root / CHECKER.CLASSIFICATIONS_PATH
            replacement = victim.with_name("replacement.json")
            shutil.copy2(victim, replacement)
            real_stat = CHECKER.os.stat
            named_stat_count = 0

            def replace_after_read(path, *args, **kwargs):
                nonlocal named_stat_count
                if path == victim.name and kwargs.get("dir_fd") is not None:
                    named_stat_count += 1
                    if named_stat_count == 2:
                        os.replace(replacement, victim)
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(CHECKER.os, "stat", side_effect=replace_after_read):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)

    def test_ancestor_directory_replacement_fails_final_identity_barrier(self):
        with fixture_repository() as fixture_root:
            rung_three = fixture_root / CHECKER.RUNG3
            displaced = rung_three.with_name(f"{rung_three.name}-displaced")
            original_reread = CHECKER.FixedTrackedReader.reread_held

            def replace_ancestor_after_reread(reader, handles):
                payload = original_reread(reader, handles)
                rung_three.rename(displaced)
                shutil.copytree(displaced, rung_three)
                return payload

            with mock.patch.object(
                CHECKER.FixedTrackedReader,
                "reread_held",
                new=replace_ancestor_after_reread,
            ):
                with self.assertRaisesRegex(
                    CHECKER.CheckError, "directory (?:metadata|ancestry) drift"
                ):
                    CHECKER.check_repository(fixture_root)

    def test_unsafe_directory_failure_closes_every_opened_descriptor(self):
        with fixture_repository() as fixture_root:
            os.chmod(fixture_root / CHECKER.RUNG3, 0o777)
            real_open = CHECKER.os.open
            real_close = CHECKER.os.close
            opened: list[int] = []
            closed: list[int] = []

            def tracked_open(*args, **kwargs):
                descriptor = real_open(*args, **kwargs)
                opened.append(descriptor)
                return descriptor

            def tracked_close(descriptor):
                closed.append(descriptor)
                return real_close(descriptor)

            with mock.patch.object(
                CHECKER.os, "open", side_effect=tracked_open
            ), mock.patch.object(CHECKER.os, "close", side_effect=tracked_close):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)
            self.assertEqual(sorted(opened), sorted(closed))

    def test_final_barrier_catches_interleaved_mutation_and_residue(self):
        with fixture_repository() as fixture_root:
            victim = fixture_root / CHECKER.CLASSIFICATIONS_PATH
            original_read = CHECKER.FixedTrackedReader._read_exact
            read_count = 0

            def mutate_after_final_classifications_read(descriptor, size):
                nonlocal read_count
                payload = original_read(descriptor, size)
                read_count += 1
                if read_count == 14:
                    changed = victim.read_bytes().replace(b"{", b"[", 1)
                    victim.write_bytes(changed)
                    os.chmod(victim, 0o600)
                return payload

            with mock.patch.object(
                CHECKER.FixedTrackedReader,
                "_read_exact",
                side_effect=mutate_after_final_classifications_read,
            ):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)
        with fixture_repository() as fixture_root:
            residue = fixture_root / CHECKER.RUNG3 / CHECKER.FAILURE_NAME
            original_barrier = CHECKER.FixedTrackedReader.final_identity_barrier

            def inject_after_identity_barrier(reader, handles):
                original_barrier(reader, handles)
                residue.write_bytes(b"late failure")
                os.chmod(residue, 0o600)

            with mock.patch.object(
                CHECKER.FixedTrackedReader,
                "final_identity_barrier",
                new=inject_after_identity_barrier,
            ):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)

    def test_short_final_read_fails_closed(self):
        with fixture_repository() as fixture_root:
            original_read = CHECKER.FixedTrackedReader._read_exact
            read_count = 0

            def truncate_one_final_read(descriptor, size):
                nonlocal read_count
                payload = original_read(descriptor, size)
                read_count += 1
                return payload[:-1] if read_count == 9 else payload

            with mock.patch.object(
                CHECKER.FixedTrackedReader,
                "_read_exact",
                side_effect=truncate_one_final_read,
            ):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)


class SemanticMutationTests(unittest.TestCase):
    def _validated_inputs(self, root: Path):
        documents = parse_documents(root)
        records = CHECKER.validate_pass_records(documents)
        candidates, findings = CHECKER.validate_pass_input(
            documents[CHECKER.PASS_INPUT_PATH], records
        )
        return documents, records, candidates, findings

    def test_candidate_digest_and_candidate_schema_mutations_fail(self):
        with fixture_repository() as fixture_root:
            documents, records, _bindings, _findings = self._validated_inputs(fixture_root)
            mutated = copy.deepcopy(documents[CHECKER.PASS_INPUT_PATH])
            mutated["candidateFindings"][0]["rationale"] += " changed"
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_pass_input(mutated, records)
            mutated = copy.deepcopy(documents[CHECKER.PASS_INPUT_PATH])
            mutated["candidateFindings"][0]["unknown"] = False
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_pass_input(mutated, records)

    def test_nonattesting_and_authentication_overclaims_fail(self):
        with fixture_repository() as fixture_root:
            documents = parse_documents(fixture_root)
            documents[CHECKER.PRIMARY_RECORD_PATH]["recordIsSigned"] = True
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_pass_records(documents)
        with fixture_repository() as fixture_root:
            documents, records, bindings, findings = self._validated_inputs(fixture_root)
            result = copy.deepcopy(documents[CHECKER.RESULT_PATH])
            result["personalProjectBoundary"]["userActionRequired"] = True
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_result(
                    result,
                    record_bindings=records,
                    candidate_bindings=bindings,
                )

    def test_finding_aggregation_and_closure_overclaims_fail(self):
        with fixture_repository() as fixture_root:
            documents, records, bindings, findings = self._validated_inputs(fixture_root)
            classifications = copy.deepcopy(documents[CHECKER.CLASSIFICATIONS_PATH])
            classifications["candidateClassification"]["findings"][0][
                "finalDisposition"
            ] = "patch_required"
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_classifications(
                    classifications,
                    record_bindings=records,
                    candidate_bindings=bindings,
                    expected_findings=findings,
                )
            result = copy.deepcopy(documents[CHECKER.RESULT_PATH])
            result["closure"]["semanticClosureComplete"] = True
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_result(
                    result,
                    record_bindings=records,
                    candidate_bindings=bindings,
                )
            result["closure"]["semanticClosureComplete"] = 0
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_result(
                    result,
                    record_bindings=records,
                    candidate_bindings=bindings,
                )

    def test_manifest_commit_marker_and_artifact_mutations_fail(self):
        with fixture_repository() as fixture_root:
            documents, records, bindings, _findings = self._validated_inputs(fixture_root)
            manifest = copy.deepcopy(documents[CHECKER.MANIFEST_PATH])
            manifest["publicationContract"][
                "commitMarkerPresenceAloneIsFinalSuccessEvidence"
            ] = True
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_manifest(
                    manifest,
                    record_bindings=records,
                    candidate_bindings=bindings,
                )
            manifest = copy.deepcopy(documents[CHECKER.MANIFEST_PATH])
            manifest["artifacts"].reverse()
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.validate_manifest(
                    manifest,
                    record_bindings=records,
                    candidate_bindings=bindings,
                )

    def test_coherently_rebound_manifest_still_fails_raw_pin(self):
        with fixture_repository() as fixture_root:
            manifest_path = fixture_root / CHECKER.MANIFEST_PATH
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["publicationContract"][
                "commitMarkerPresenceAloneIsFinalSuccessEvidence"
            ] = True
            manifest = rebound(manifest, "manifest_without_contentBinding")
            manifest_path.write_bytes(CHECKER.canonical_json_bytes(manifest))
            os.chmod(manifest_path, 0o600)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.check_repository(fixture_root)

    def test_coherently_resealed_content_still_fails_content_pin(self):
        with fixture_repository() as fixture_root:
            result_path = fixture_root / CHECKER.RESULT_PATH
            result = json.loads(result_path.read_text(encoding="utf-8"))
            old_result = result["result"]
            result["result"] = "x" + old_result[1:]
            result = rebound(result, "result_without_contentBinding")
            raw = CHECKER.canonical_json_bytes(result)
            self.assertEqual(len(raw), CHECKER.EXPECTED_PUBLISHED_BYTES[CHECKER.RESULT_PATH])
            result_path.write_bytes(raw)
            os.chmod(result_path, 0o600)
            with mock.patch.dict(
                CHECKER.EXPECTED_RAW_SHA256,
                {CHECKER.RESULT_PATH: hashlib.sha256(raw).hexdigest()},
            ):
                with self.assertRaisesRegex(CHECKER.CheckError, "self hash"):
                    CHECKER.check_repository(fixture_root)

    def test_rebuild_finding_identity_disagreement_severity_and_order(self):
        with fixture_repository() as fixture_root:
            documents, _records, _bindings, expected = self._validated_inputs(
                fixture_root
            )
            candidates = documents[CHECKER.PASS_INPUT_PATH]["candidateFindings"]
            self.assertEqual(CHECKER.rebuild_findings(candidates), expected)

            disagreement = copy.deepcopy(candidates)
            for row in disagreement:
                if row["dedupGroupId"] == "G-RESOLUTION-GATHER":
                    row["reportedDisposition"] = "patch_required"
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.rebuild_findings(disagreement)

            changed_identity = copy.deepcopy(candidates)
            singleton_index = next(
                index
                for index, row in enumerate(changed_identity)
                if sum(
                    other["dedupGroupId"] == row["dedupGroupId"]
                    for other in changed_identity
                )
                == 1
            )
            changed_identity[singleton_index]["canonicalInvariantId"] += "_changed"
            rebuilt = CHECKER.rebuild_findings(changed_identity)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.require_exact(rebuilt, expected, "rebuilt findings")

            changed_severity = copy.deepcopy(candidates)
            target_group = changed_severity[0]["dedupGroupId"]
            for row in changed_severity:
                if row["dedupGroupId"] == target_group:
                    row["reportedSeverity"] = "P0"
            rebuilt = CHECKER.rebuild_findings(changed_severity)
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.require_exact(rebuilt, expected, "severity ranking")

            reordered = copy.deepcopy(expected)
            reordered[0]["patchUnits"] = list(reversed(reordered[0]["patchUnits"]))
            with self.assertRaises(CHECKER.CheckError):
                CHECKER.require_exact(reordered, expected, "finding unit order")

    def test_manifest_validation_is_called_after_classifications_and_result(self):
        with fixture_repository() as fixture_root:
            raw = {
                path: (fixture_root / path).read_bytes()
                for path in CHECKER.ALLOWED_PATHS
            }
            order: list[str] = []
            originals = {
                "classifications": CHECKER.validate_classifications,
                "result": CHECKER.validate_result,
                "manifest": CHECKER.validate_manifest,
            }

            def classifications(*args, **kwargs):
                order.append("classifications")
                return originals["classifications"](*args, **kwargs)

            def result(*args, **kwargs):
                order.append("result")
                return originals["result"](*args, **kwargs)

            def manifest(*args, **kwargs):
                order.append("manifest")
                return originals["manifest"](*args, **kwargs)

            with mock.patch.object(CHECKER, "validate_classifications", classifications), \
                    mock.patch.object(CHECKER, "validate_result", result), \
                    mock.patch.object(CHECKER, "validate_manifest", manifest):
                CHECKER.validate_documents(raw)
            self.assertEqual(order, ["classifications", "result", "manifest"])

    def test_content_binding_mutation_fails_even_when_raw_pin_is_temporarily_rebound(self):
        with fixture_repository() as fixture_root:
            result_path = fixture_root / CHECKER.RESULT_PATH
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["contentBinding"]["sha256"] = "0" * 64
            raw = CHECKER.canonical_json_bytes(result)
            result_path.write_bytes(raw)
            os.chmod(result_path, 0o600)
            with mock.patch.dict(
                CHECKER.EXPECTED_RAW_SHA256,
                {CHECKER.RESULT_PATH: hashlib.sha256(raw).hexdigest()},
            ):
                with self.assertRaises(CHECKER.CheckError):
                    CHECKER.check_repository(fixture_root)


if __name__ == "__main__":
    unittest.main()
