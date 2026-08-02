#!/usr/bin/env python3
"""Mutation tests for the Release diagnostics usability readback."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from script import check_release_diagnostics_usability as module
from script import run_release_diagnostics_usability as producer


class ReleaseDiagnosticsReadbackTests(unittest.TestCase):
    def test_load_result_requires_canonical_mode_0600_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            path.write_bytes(b'{"a":1}\n')
            path.chmod(0o600)
            self.assertEqual(module.load_result(path), {"a": 1})
            path.write_bytes(b'{ "a": 1 }\n')
            with self.assertRaises(module.EvidenceError):
                module.load_result(path)
            path.write_bytes(b'{"a":1,"a":2}\n')
            with self.assertRaises(module.EvidenceError):
                module.load_result(path)
            path.write_bytes(b'{"a":1}\n')
            path.chmod(0o644)
            with self.assertRaises(module.EvidenceError):
                module.load_result(path)

    def test_exact_integer_and_boolean_types_reject_bool_int_aliases(self) -> None:
        self.assertEqual(module.require_int(1, "count", minimum=1), 1)
        with self.assertRaises(module.EvidenceError):
            module.require_int(True, "count", minimum=1)
        module.require_bool(False, False, "flag")
        with self.assertRaises(module.EvidenceError):
            module.require_bool(0, False, "flag")

    def test_common_schema_version_requires_exact_integer_type(self) -> None:
        document: dict[str, object] = {
            "artifacts": {},
            "contract": producer.CONTRACT,
            "implementation": [],
            "platform": "macos",
            "prerequisiteReadbackSha256": "1" * 64,
            "probe": {},
            "qualification": dict(producer.QUALIFICATION),
            "result": "fixture",
            "schemaVersion": producer.SCHEMA_VERSION,
            "tool": {},
        }
        with mock.patch.object(
            producer,
            "prerequisite_digest",
            return_value="1" * 64,
        ), mock.patch.object(module, "validate_implementation"), mock.patch.object(
            module, "validate_qualification"
        ):
            module.validate_common(document, expected_platform="macos", root=Path("."))
            for invalid in (True, 1.0, "1"):
                with self.subTest(invalid=invalid):
                    mutated = dict(document)
                    mutated["schemaVersion"] = invalid
                    with self.assertRaises(module.EvidenceError):
                        module.validate_common(
                            mutated,
                            expected_platform="macos",
                            root=Path("."),
                        )

    def test_qualification_is_closed_and_all_false(self) -> None:
        module.validate_qualification(dict(producer.QUALIFICATION))
        for key in producer.QUALIFICATION:
            mutated = dict(producer.QUALIFICATION)
            mutated[key] = True
            with self.subTest(key=key), self.assertRaises(module.EvidenceError):
                module.validate_qualification(mutated)
        with self.assertRaises(module.EvidenceError):
            module.validate_qualification({**producer.QUALIFICATION, "extra": False})

    def test_source_readback_binds_allowed_path_bytes_and_exact_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative_root = Path("apps/android/app/src/main")
            relative = relative_root / "java/example/Probe.kt"
            source = root / relative
            source.parent.mkdir(parents=True)
            data = b"one\ntwo\n"
            source.write_bytes(data)
            record = {
                "line": 2,
                "lineSha256": producer.sha256(b"two\n"),
                "path": relative.as_posix(),
                "sha256": producer.sha256(data),
                "size": len(data),
            }
            module.source_readback(
                record,
                expected_roots=(relative_root,),
                source_file="Probe.kt",
                source_line=2,
                root=root,
            )
            mutated = dict(record)
            mutated["lineSha256"] = "0" * 64
            with self.assertRaises(module.EvidenceError):
                module.source_readback(
                    mutated,
                    expected_roots=(relative_root,),
                    source_file="Probe.kt",
                    source_line=2,
                    root=root,
                )
            mutated = dict(record)
            mutated["path"] = "outside/Probe.kt"
            with self.assertRaises(module.EvidenceError):
                module.source_readback(
                    mutated,
                    expected_roots=(relative_root,),
                    source_file="Probe.kt",
                    source_line=2,
                    root=root,
                )

    @staticmethod
    def android_fixture(builder: Path) -> tuple[dict[str, object], dict[str, object], bytes]:
        selected: dict[str, object] = {
            "mappingLineSha256": "1" * 64,
            "obfuscatedClass": "a",
            "obfuscatedLine": 1,
            "obfuscatedMethod": "b",
            "originalClass": "com.localagentbridge.android.ProbeKt",
            "originalMethod": "recover",
            "sourceFile": "Probe.kt",
            "sourceLine": 42,
        }
        obfuscated = "at a.b(Probe.kt:1)"
        original = "at com.localagentbridge.android.ProbeKt.recover(Probe.kt:42)"
        stack = f"{producer.ANDROID_PROBE_EXCEPTION}\n\t{obfuscated}\n".encode()
        output = f"{producer.ANDROID_PROBE_EXCEPTION}\n\t{original}\n".encode()
        builder_data = builder.read_bytes()
        document: dict[str, object] = {
            "artifacts": {"aab": {}, "apk": {}, "mapping": {}},
            "contract": producer.CONTRACT,
            "implementation": [],
            "mapping": {
                "compiler": "R8",
                "compilerVersion": producer.RETRACE_VERSION,
                "mapHash": "2" * 64,
                "mapId": "3" * 64,
            },
            "platform": "android",
            "prerequisiteReadbackSha256": "4" * 64,
            "probe": {
                **selected,
                "inputSha256": producer.sha256(stack),
                "obfuscatedFrame": obfuscated,
                "originalFrame": original,
                "outputSha256": producer.sha256(output),
                "source": {},
            },
            "qualification": dict(producer.QUALIFICATION),
            "result": "android-r8-retrace-resolved-one-project-frame",
            "schemaVersion": 1,
            "tool": {
                "agpVersion": producer.AGP_VERSION,
                "builderJar": {
                    "name": builder.name,
                    "sha256": producer.sha256(builder_data),
                    "size": len(builder_data),
                },
                "classpathEntryCount": 2,
                "mainClass": producer.RETRACE_MAIN_CLASS,
                "retraceVersion": "Retrace 9.2.14 (build fixture)",
            },
        }
        return document, selected, output

    def run_android_validation(
        self,
        document: dict[str, object],
        selected: dict[str, object],
        output: bytes,
        builder: Path,
    ) -> None:
        mapping_metadata = document["mapping"]
        assert isinstance(mapping_metadata, dict)
        with mock.patch.object(module, "validate_common"), mock.patch.object(
            module,
            "live_file_record",
            side_effect=lambda _record, expected_path, **_kwargs: (
                b"mapping" if expected_path == producer.ANDROID_MAPPING_PATH else b"artifact"
            ),
        ), mock.patch.object(module, "source_readback"), mock.patch.object(
            producer, "android_mapping_metadata", return_value=mapping_metadata
        ), mock.patch.object(producer, "android_tool",
            return_value=(
                Path("java"),
                f"one{os.pathsep}two",
                builder,
                "Retrace 9.2.14 (build fixture)",
            ),
        ), mock.patch.object(
            producer,
            "resolve_android_probe",
            return_value=(
                selected,
                document["probe"]["source"],
                (
                    f"{producer.ANDROID_PROBE_EXCEPTION}\n"
                    f"\t{document['probe']['obfuscatedFrame']}\n"
                ).encode(),
                output,
            ),
        ):
            module.validate_android(document, root=Path("."))

    def test_android_readback_accepts_recovered_frame_and_rejects_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            builder = Path(temporary) / f"builder-{producer.AGP_VERSION}.jar"
            builder.write_bytes(b"builder")
            document, selected, output = self.android_fixture(builder)
            self.run_android_validation(document, selected, output, builder)

            mutations: list[tuple[str, dict[str, object]]] = []
            wrong_frame = deepcopy(document)
            assert isinstance(wrong_frame["probe"], dict)
            wrong_frame["probe"]["originalFrame"] = "at wrong.Frame(Probe.kt:42)"
            mutations.append(("wrong original frame", wrong_frame))
            wrong_digest = deepcopy(document)
            assert isinstance(wrong_digest["probe"], dict)
            wrong_digest["probe"]["outputSha256"] = "0" * 64
            mutations.append(("wrong output digest", wrong_digest))
            wrong_jar = deepcopy(document)
            assert isinstance(wrong_jar["tool"], dict)
            assert isinstance(wrong_jar["tool"]["builderJar"], dict)
            wrong_jar["tool"]["builderJar"]["sha256"] = "0" * 64
            mutations.append(("wrong builder", wrong_jar))
            for label, mutated in mutations:
                with self.subTest(label=label), self.assertRaises(module.EvidenceError):
                    self.run_android_validation(mutated, selected, output, builder)

            stack = (
                f"{producer.ANDROID_PROBE_EXCEPTION}\n\tat a.b(Probe.kt:1)\n"
            ).encode()
            with self.assertRaises(module.EvidenceError):
                self.run_android_validation(document, selected, stack, builder)

    @staticmethod
    def macos_fixture() -> dict[str, object]:
        frame = "Probe.run() (in AetherLink) (Probe.swift:7)"
        return {
            "artifacts": {"dSYM": {}, "executable": {}, "sourceReceipt": {}},
            "contract": producer.CONTRACT,
            "implementation": [],
            "platform": "macos",
            "prerequisiteReadbackSha256": "4" * 64,
            "probe": {
                "address": "0x0000000100001000",
                "nmSymbol": "_probe",
                "source": {},
                "sourceFile": "Probe.swift",
                "sourceLine": 7,
                "symbol": "Probe.run()",
                "symbolicatedFrame": frame,
                "symbolicatedFrameSha256": producer.sha256((frame + "\n").encode()),
                "uuid": "6B06A6D0-9C89-3D36-A5B9-D2381598DDC8",
            },
            "qualification": dict(producer.QUALIFICATION),
            "result": "macos-dsym-symbolicated-one-project-frame",
            "schemaVersion": 1,
            "tool": {"atos": {}, "dwarfdump": {}, "nm": {}},
        }

    def run_macos_validation(
        self,
        document: dict[str, object],
        *,
        selected_probe: dict[str, object] | None = None,
        uuid: str = "6B06A6D0-9C89-3D36-A5B9-D2381598DDC8",
    ) -> None:
        recorded_probe = dict(document["probe"])
        recorded_probe.pop("uuid")
        with mock.patch.object(module, "validate_common"), mock.patch.object(
            module, "live_file_record", return_value=b"artifact"
        ), mock.patch.object(module, "live_external_tool_record"), mock.patch.object(
            module, "source_readback"
        ), mock.patch.object(
            producer, "macos_uuid", return_value=uuid
        ), mock.patch.object(
            producer,
            "macos_probe",
            return_value=recorded_probe if selected_probe is None else selected_probe,
        ):
            module.validate_macos(document, root=Path("."))

    def test_macos_readback_accepts_symbolicated_frame_and_rejects_mutations(self) -> None:
        document = self.macos_fixture()
        self.run_macos_validation(document)
        with self.assertRaises(module.EvidenceError):
            self.run_macos_validation(
                document,
                uuid="00000000-0000-0000-0000-000000000000",
            )
        alternate_probe = dict(document["probe"])
        alternate_probe.pop("uuid")
        alternate_probe["address"] = "0x0000000100002000"
        with self.assertRaises(module.EvidenceError):
            self.run_macos_validation(document, selected_probe=alternate_probe)
        mutated = deepcopy(document)
        assert isinstance(mutated["probe"], dict)
        mutated["probe"]["symbolicatedFrameSha256"] = "0" * 64
        with self.assertRaises(module.EvidenceError):
            self.run_macos_validation(mutated)


if __name__ == "__main__":
    unittest.main()
