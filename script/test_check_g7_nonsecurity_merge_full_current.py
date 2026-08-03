from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest import mock

from script import check_g7_nonsecurity_merge_full_current as checker
from script import run_g7_nonsecurity_merge_full_current as producer


def write_bytes(path: Path, data: bytes, *, mode: int, mtime_ns: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)
    os.utime(path, ns=(mtime_ns, mtime_ns))


def write_json(
    path: Path,
    value: object,
    *,
    mode: int,
    mtime_ns: int,
) -> None:
    write_bytes(
        path,
        checker.canonical_json_bytes(value),
        mode=mode,
        mtime_ns=mtime_ns,
    )


class CheckerPrimitiveTests(unittest.TestCase):
    def test_exact_integer_rejects_boolean(self) -> None:
        with self.assertRaises(checker.EvidenceError):
            checker.require_exact_int(True, "count")
        self.assertEqual(checker.require_exact_int(1, "count"), 1)

    def test_duplicate_json_key_is_rejected(self) -> None:
        with self.assertRaises(checker.DuplicateKeyError):
            json.loads(
                '{"value":1,"value":2}',
                object_pairs_hook=checker.reject_duplicate_keys,
            )

    def test_canonical_json_is_ascii_sorted_and_lf_terminated(self) -> None:
        self.assertEqual(
            checker.canonical_json_bytes({"z": "한", "a": 1}),
            b'{"a":1,"z":"\\ud55c"}\n',
        )

    def test_console_requires_one_started_passed_pair_per_identity(self) -> None:
        identities = ("FixtureTests.Case/testOne", "FixtureTests.Case/testTwo")
        console = (
            "Test Case '-[FixtureTests.Case testOne]' started.\n"
            "Test Case '-[FixtureTests.Case testOne]' passed (0.001 seconds).\n"
            "Test Case '-[FixtureTests.Case testTwo]' started.\n"
            "Test Case '-[FixtureTests.Case testTwo]' passed (0.001 seconds).\n"
            "Executed 2 tests, with 0 failures (0 unexpected) in 0.002 "
            "(0.002) seconds\n"
        ).encode()
        snapshot = checker.console_snapshot(console, identities)
        self.assertEqual(snapshot["tests"], 2)
        self.assertEqual(snapshot["skipped"], 0)
        with self.assertRaises(checker.EvidenceError):
            checker.console_snapshot(console.replace(b"passed", b"skipped", 1), identities)
        with self.assertRaises(checker.EvidenceError):
            checker.console_snapshot(console.replace(b"Executed 2", b"Executed 1"), identities)
        poisoned_summary = console.replace(
            b"Executed 2 tests, with 0 failures",
            b"Executed 1 test, with 1 failure (1 unexpected) in 0.001 "
            b"(0.001) seconds\nExecuted 2 tests, with 0 failures",
            1,
        )
        with self.assertRaises(checker.EvidenceError):
            checker.console_snapshot(poisoned_summary, identities)

    def test_stable_reader_rejects_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("fixture")
            symlink = root / "symlink.txt"
            symlink.symlink_to(source)
            with self.assertRaises(checker.EvidenceError):
                checker.stable_regular_bytes(
                    symlink,
                    maximum_bytes=100,
                    label="symlink fixture",
                )
            hardlink = root / "hardlink.txt"
            os.link(source, hardlink)
            with self.assertRaises(checker.EvidenceError):
                checker.stable_regular_bytes(
                    source,
                    maximum_bytes=100,
                    label="hardlink fixture",
                )

    def test_stable_reader_rejects_max_plus_one_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.bin"
            path.write_bytes(b"x" * 11)
            with self.assertRaises(checker.EvidenceError):
                checker.stable_regular_bytes(
                    path,
                    maximum_bytes=10,
                    label="oversized fixture",
                )


class CurrentRunReadbackTests(unittest.TestCase):
    @contextmanager
    def evidence_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exact_relative = Path("fixture/exact-source.txt")
            source_root_relative = Path("fixture/Sources")
            source_relative = source_root_relative / "Source.swift"
            base_time = time.time_ns() - 30_000_000_000

            write_bytes(
                root / exact_relative,
                b"exact source\n",
                mode=0o644,
                mtime_ns=base_time,
            )
            write_bytes(
                root / checker.V5_IDENTITY_RELATIVE_PATH,
                (checker.ROOT / checker.V5_IDENTITY_RELATIVE_PATH).read_bytes(),
                mode=0o644,
                mtime_ns=base_time,
            )
            write_bytes(
                root / checker.V6_IDENTITY_RELATIVE_PATH,
                (checker.ROOT / checker.V6_IDENTITY_RELATIVE_PATH).read_bytes(),
                mode=0o644,
                mtime_ns=base_time,
            )
            write_bytes(
                root / source_relative,
                b"struct Fixture {}\n",
                mode=0o644,
                mtime_ns=base_time,
            )
            test_list_data = (
                checker.ROOT / checker.TEST_LIST_RELATIVE_PATH
            ).read_bytes()
            write_bytes(
                root / checker.TEST_LIST_RELATIVE_PATH,
                test_list_data,
                mode=0o600,
                mtime_ns=base_time + 1_000_000_000,
            )
            output_root = root / checker.OUTPUT_ROOT_RELATIVE_PATH
            output_root.mkdir(parents=True, mode=0o700)
            output_root.chmod(0o700)

            with (
                mock.patch.object(
                    checker,
                    "TRACKED_EXACT_SOURCE_RELATIVE_PATHS",
                    (
                        exact_relative,
                        checker.V5_IDENTITY_RELATIVE_PATH,
                        checker.V6_IDENTITY_RELATIVE_PATH,
                    ),
                ),
                mock.patch.object(
                    checker,
                    "SOURCE_ROOT_RELATIVE_PATHS",
                    (source_root_relative,),
                ),
                mock.patch.object(
                    checker,
                    "FOCUSED_EXACT_SOURCE_RELATIVE_PATHS",
                    (exact_relative,),
                ),
            ):
                partition, failures = producer.reconstruct_partition()
                self.assertEqual(failures, [])
                self.assertIsNotNone(partition)
                command, command_failures = producer.command_and_filter_failures(
                    partition  # type: ignore[arg-type]
                )
                self.assertEqual(command_failures, [])
                self.assertIsNotNone(command)
                environment = {"LANG": "C", "LC_ALL": "C"}
                execution = producer.execution_contract_payload(
                    partition,  # type: ignore[arg-type]
                    command or (),
                    environment,
                )
                write_json(
                    root / checker.EXECUTION_CONTRACT_RELATIVE_PATH,
                    execution,
                    mode=0o600,
                    mtime_ns=base_time + 2_000_000_000,
                )

                discovered, copied_test_list = checker.read_test_list(root=root)
                selected, _remaining, _filter, _env, _footprint = (
                    checker.validate_execution_contract(
                        execution,
                        discovered,
                        root=root,
                    )
                )
                source_inputs = checker.source_snapshot(root=root)
                list_snapshot = checker.test_list_snapshot(
                    selected,
                    copied_test_list,
                )
                marker = {
                    "contract": checker.RUN_MARKER_CONTRACT,
                    "sourceInputs": source_inputs,
                    "testList": list_snapshot,
                }
                write_json(
                    root / checker.RUN_MARKER_RELATIVE_PATH,
                    marker,
                    mode=0o600,
                    mtime_ns=base_time + 3_000_000_000,
                )
                marker_data = checker.canonical_json_bytes(marker)

                console_lines: list[str] = []
                for identity in selected:
                    suite, test = identity.split("/", 1)
                    console_lines.append(f"Test Case '-[{suite} {test}]' started.")
                    console_lines.append(
                        f"Test Case '-[{suite} {test}]' passed (0.001 seconds)."
                    )
                console_lines.append(
                    f"Executed {len(selected)} tests, with 0 failures "
                    "(0 unexpected) in 1.000 (1.000) seconds"
                )
                console_data = ("\n".join(console_lines) + "\n").encode()
                write_bytes(
                    root / checker.CONSOLE_RELATIVE_PATH,
                    console_data,
                    mode=0o600,
                    mtime_ns=base_time + 4_000_000_000,
                )
                binding = {
                    "contract": checker.BINDING_CONTRACT,
                    "result": checker.console_snapshot(console_data, selected),
                    "runMarker": {
                        "bytes": len(marker_data),
                        "sha256": hashlib.sha256(marker_data).hexdigest(),
                    },
                    "sourceInputs": source_inputs,
                    "testList": list_snapshot,
                }
                write_json(
                    root / checker.BINDING_RELATIVE_PATH,
                    binding,
                    mode=0o600,
                    mtime_ns=base_time + 5_000_000_000,
                )
                artifact_contracts = {
                    "binding": (checker.BINDING_RELATIVE_PATH, checker.RESULT_MAX_BYTES),
                    "console": (checker.CONSOLE_RELATIVE_PATH, checker.CONSOLE_MAX_BYTES),
                    "executionContract": (
                        checker.EXECUTION_CONTRACT_RELATIVE_PATH,
                        checker.EXECUTION_CONTRACT_MAX_BYTES,
                    ),
                    "runMarker": (
                        checker.RUN_MARKER_RELATIVE_PATH,
                        checker.RESULT_MAX_BYTES,
                    ),
                    "testList": (
                        checker.TEST_LIST_RELATIVE_PATH,
                        checker.TEST_LIST_MAX_BYTES,
                    ),
                }
                artifacts = {
                    key: checker.current_file_record(
                        relative,
                        root=root,
                        maximum_bytes=maximum,
                    )
                    for key, (relative, maximum) in artifact_contracts.items()
                }
                result = producer.compose_result_payload(
                    partition,  # type: ignore[arg-type]
                    artifacts=artifacts,
                    source_inputs=source_inputs,
                    execution_document=execution,
                )
                self.assertEqual(
                    result,
                    checker.expected_result_payload(root=root),
                )
                result_path = root / checker.RESULT_RELATIVE_PATH
                write_json(
                    result_path,
                    result,
                    mode=0o600,
                    mtime_ns=base_time + 6_000_000_000,
                )

                parent_partition = checker.parent_partition_from_execution(
                    execution,
                    discovered,
                    root=root,
                )
                focused_tests = parent_partition["focusedCarrier"]
                focused_source = checker.focused_source_snapshot(root=root)
                focused_list_snapshot = checker.test_list_snapshot(
                    focused_tests,
                    copied_test_list,
                )
                focused_marker = {
                    "contract": checker.RUN_MARKER_CONTRACT,
                    "sourceInputs": focused_source,
                    "testList": focused_list_snapshot,
                }
                write_json(
                    root / checker.FOCUSED_RUN_MARKER_RELATIVE_PATH,
                    focused_marker,
                    mode=0o600,
                    mtime_ns=base_time + 2_200_000_000,
                )
                focused_marker_data = checker.canonical_json_bytes(
                    focused_marker
                )
                focused_console_lines: list[str] = []
                for identity in focused_tests:
                    suite, test = identity.split("/", 1)
                    focused_console_lines.append(
                        f"Test Case '-[{suite} {test}]' started."
                    )
                    focused_console_lines.append(
                        f"Test Case '-[{suite} {test}]' passed (0.001 seconds)."
                    )
                focused_console_lines.append(
                    f"Executed {len(focused_tests)} tests, with 0 failures "
                    "(0 unexpected) in 1.000 (1.000) seconds"
                )
                focused_console_data = (
                    "\n".join(focused_console_lines) + "\n"
                ).encode()
                write_bytes(
                    root / checker.FOCUSED_CONSOLE_RELATIVE_PATH,
                    focused_console_data,
                    mode=0o600,
                    mtime_ns=base_time + 2_400_000_000,
                )
                focused_binding = {
                    "contract": checker.BINDING_CONTRACT,
                    "result": checker.console_snapshot(
                        focused_console_data,
                        focused_tests,
                    ),
                    "runMarker": {
                        "bytes": len(focused_marker_data),
                        "sha256": hashlib.sha256(
                            focused_marker_data
                        ).hexdigest(),
                    },
                    "sourceInputs": focused_source,
                    "testList": focused_list_snapshot,
                }
                write_json(
                    root / checker.FOCUSED_BINDING_RELATIVE_PATH,
                    focused_binding,
                    mode=0o600,
                    mtime_ns=base_time + 2_600_000_000,
                )
                parent_result = checker.expected_parent_payload(root=root)
                parent_result_path = root / checker.PARENT_RESULT_RELATIVE_PATH
                write_json(
                    parent_result_path,
                    parent_result,
                    mode=0o600,
                    mtime_ns=base_time + 7_000_000_000,
                )
                yield {
                    "root": root,
                    "result": result_path,
                    "parent": parent_result_path,
                    "source": root / source_relative,
                    "execution": root / checker.EXECUTION_CONTRACT_RELATIVE_PATH,
                    "console": root / checker.CONSOLE_RELATIVE_PATH,
                    "focused_console": (
                        root / checker.FOCUSED_CONSOLE_RELATIVE_PATH
                    ),
                    "v5_manifest": root / checker.V5_IDENTITY_RELATIVE_PATH,
                    "v6_manifest": root / checker.V6_IDENTITY_RELATIVE_PATH,
                }

    def test_complete_fixture_passes_independent_readback(self) -> None:
        with self.evidence_fixture() as fixture:
            document = checker.validate_result(
                fixture["result"],
                root=fixture["root"],
            )
            self.assertEqual(document["result"], "passed")
            coverage = document["coverage"]
            self.assertEqual(
                coverage["v6New"],
                {
                    "manifestSha256": (
                        "6b4991164cab03a5575a8c0d4a0526874571994e65e5bde612d8716333482a5d"
                    ),
                    "tests": 7,
                },
            )
            self.assertEqual(
                coverage["selected"],
                {
                    "manifestSha256": (
                        "fbab18434f821237178e87aab1e84ce58bf7e82802978439ae43fc1f95e76fde"
                    ),
                    "tests": 1_204,
                },
            )
            self.assertEqual(
                coverage["notExecuted"],
                {
                    "manifestSha256": (
                        "018058edbc3b344da6a7fae3a8b077d9aad6fc3c7fd2929a1130c2cee4152974"
                    ),
                    "tests": 971,
                },
            )

    def test_complete_parent_fixture_passes_independent_readback(self) -> None:
        with self.evidence_fixture() as fixture:
            document = checker.validate_parent_result(
                fixture["parent"],
                root=fixture["root"],
            )
            self.assertEqual(document["result"], "passed")
            coverage = document["coverage"]
            self.assertEqual(
                coverage["reviewedExecuted"]["tests"],
                1_208,
            )
            self.assertEqual(
                coverage["noSocketExecuted"]["tests"],
                1_204,
            )
            self.assertEqual(
                coverage["remaining"]["tests"],
                967,
            )
            self.assertEqual(
                coverage["localSocketExecuted"]["tests"],
                4,
            )
            self.assertEqual(
                coverage["reviewedExecuted"]["manifestSha256"],
                "ea63ec325a6125f4ae92c49c0ca9d3054e054369335bec6ebeb99c7256468846",
            )
            self.assertEqual(
                coverage["remaining"]["manifestSha256"],
                "fe4c11470e53a92ff64fe31c143b7d587eacdfcdd68ac8af7c5ba7233d58e9e6",
            )

    def test_parent_boolean_invocation_count_is_rejected(self) -> None:
        with self.evidence_fixture() as fixture:
            document = json.loads(fixture["parent"].read_bytes())
            document["execution"]["childSwiftInvocations"] = True
            write_json(
                fixture["parent"],
                document,
                mode=0o600,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_parent_result(
                    fixture["parent"],
                    root=fixture["root"],
                )

    def test_parent_rejects_missing_local_socket_pass_event(self) -> None:
        with self.evidence_fixture() as fixture:
            identity = checker.LOCAL_SOCKET_EXCLUSION_IDENTITIES[0]
            suite, test = identity.split("/", 1)
            event = f"Test Case '-[{suite} {test}]' passed (0.001 seconds).\n"
            data = fixture["focused_console"].read_text(encoding="utf-8")
            self.assertIn(event, data)
            write_bytes(
                fixture["focused_console"],
                data.replace(event, "", 1).encode(),
                mode=0o600,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_parent_result(
                    fixture["parent"],
                    root=fixture["root"],
                )

    def test_parent_must_postdate_both_children(self) -> None:
        with self.evidence_fixture() as fixture:
            current_mtime = fixture["result"].stat().st_mtime_ns
            os.utime(
                fixture["parent"],
                ns=(current_mtime - 1_000_000_000,) * 2,
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_parent_result(
                    fixture["parent"],
                    root=fixture["root"],
                )

    def test_boolean_count_mutation_is_rejected(self) -> None:
        for partition_name in ("selected", "v6New"):
            with self.subTest(partition=partition_name), self.evidence_fixture() as fixture:
                document = json.loads(fixture["result"].read_bytes())
                document["coverage"][partition_name]["tests"] = True
                write_json(
                    fixture["result"],
                    document,
                    mode=0o600,
                    mtime_ns=time.time_ns(),
                )
                with self.assertRaises(checker.EvidenceError):
                    checker.validate_result(
                        fixture["result"],
                        root=fixture["root"],
                    )

    def test_canonical_result_must_postdate_binding(self) -> None:
        with self.evidence_fixture() as fixture:
            binding_mtime = (
                fixture["root"] / checker.BINDING_RELATIVE_PATH
            ).stat().st_mtime_ns
            os.utime(
                fixture["result"],
                ns=(binding_mtime - 1_000_000_000,) * 2,
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_broad_execution_filter_mutation_is_rejected(self) -> None:
        with self.evidence_fixture() as fixture:
            document = json.loads(fixture["execution"].read_bytes())
            document["command"][-1] = ".*"
            document["commandAndEnvironmentBytes"] = (
                checker.command_environment_footprint(
                    document["command"],
                    document["environment"],
                )
            )
            write_json(
                fixture["execution"],
                document,
                mode=0o600,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_v5_filter_must_equal_the_exact_manifest(self) -> None:
        with self.evidence_fixture() as fixture:
            document = json.loads(fixture["execution"].read_bytes())
            component = next(
                value
                for value in document["filterComponents"]
                if value["name"] == "v5Exact"
            )
            component["pattern"] = (
                r"^LocalAgentBridgeTests\.(?:AetherLinkLocalizationTests|"
                r"PairingRouteNoticeTests)/.*$"
            )
            document["command"][-1] = "(?:" + "|".join(
                value["pattern"] for value in document["filterComponents"]
            ) + ")"
            document["commandAndEnvironmentBytes"] = (
                checker.command_environment_footprint(
                    document["command"],
                    document["environment"],
                )
            )
            write_json(
                fixture["execution"],
                document,
                mode=0o600,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_v5_manifest_byte_mutation_is_rejected(self) -> None:
        with self.evidence_fixture() as fixture:
            path = fixture["v5_manifest"]
            write_bytes(
                path,
                path.read_bytes() + b"\n",
                mode=0o644,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_v6_filter_must_equal_the_exact_manifest(self) -> None:
        with self.evidence_fixture() as fixture:
            document = json.loads(fixture["execution"].read_bytes())
            component = next(
                value
                for value in document["filterComponents"]
                if value["name"] == "v6Exact"
            )
            already_selected = checker.CURRENT_V2_DELTA_IDENTITIES[0]
            component["pattern"] = (
                "(?:"
                + component["pattern"]
                + "|^"
                + re.escape(already_selected)
                + "$)"
            )
            document["command"][-1] = "(?:" + "|".join(
                value["pattern"] for value in document["filterComponents"]
            ) + ")"
            document["commandAndEnvironmentBytes"] = (
                checker.command_environment_footprint(
                    document["command"],
                    document["environment"],
                )
            )
            write_json(
                fixture["execution"],
                document,
                mode=0o600,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaisesRegex(
                checker.EvidenceError,
                "execution V6 filter differs",
            ):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_v6_manifest_byte_mutation_is_rejected(self) -> None:
        with self.evidence_fixture() as fixture:
            path = fixture["v6_manifest"]
            original = path.read_bytes()
            mutated = original.replace(
                b"EncodingFailure",
                b"EncodingFailurf",
                1,
            )
            self.assertNotEqual(mutated, original)
            self.assertEqual(len(mutated), len(original))
            write_bytes(
                path,
                mutated,
                mode=0o644,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaisesRegex(
                checker.EvidenceError,
                "V6 identity manifest bytes differ",
            ):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_local_socket_reinclusion_mutation_is_rejected(self) -> None:
        with self.evidence_fixture() as fixture:
            document = json.loads(fixture["execution"].read_bytes())
            document["filterComponents"][0]["pattern"] = (
                producer.product_ci.SWIFT_FILTER
            )
            document["command"][-1] = "(?:" + "|".join(
                component["pattern"]
                for component in document["filterComponents"]
            ) + ")"
            document["commandAndEnvironmentBytes"] = (
                checker.command_environment_footprint(
                    document["command"],
                    document["environment"],
                )
            )
            write_json(
                fixture["execution"],
                document,
                mode=0o600,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_failed_console_event_is_rejected(self) -> None:
        with self.evidence_fixture() as fixture:
            data = fixture["console"].read_bytes().replace(
                b"passed (0.001 seconds).",
                b"failed (0.001 seconds).",
                1,
            )
            write_bytes(
                fixture["console"],
                data,
                mode=0o600,
                mtime_ns=time.time_ns(),
            )
            with self.assertRaises(checker.EvidenceError):
                checker.validate_result(fixture["result"], root=fixture["root"])

    def test_source_mutation_after_marker_is_rejected(self) -> None:
        with self.evidence_fixture() as fixture:
            fixture["source"].write_bytes(b"struct Fixture { let changed = true }\n")
            with self.assertRaises(checker.EvidenceError):
                checker.validate_result(fixture["result"], root=fixture["root"])


if __name__ == "__main__":
    unittest.main()
