#!/usr/bin/env python3
"""Unit tests for the Release diagnostics usability producer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

from script import run_release_diagnostics_usability as module


SAMPLE_MAPPING = (
    "# compiler: R8\n"
    "# compiler_version: 9.2.14\n"
    "# min_api: 26\n"
    '# {"id":"com.android.tools.r8.mapping","version":"2.2"}\n'
    f"# pg_map_id: {'a' * 64}\n"
    f"# pg_map_hash: SHA-256 {'b' * 64}\n"
    "com.localagentbridge.android.DiagnosticsProbeKt -> a:\n"
    '# {"id":"sourceFile","fileName":"DiagnosticsProbe.kt"}\n'
    "    1:2:void recoverMe():42:42 -> b\n"
).encode("utf-8")


class ReleaseDiagnosticsProducerTests(unittest.TestCase):
    def test_canonical_json_is_sorted_ascii_and_lf_terminated(self) -> None:
        self.assertEqual(module.canonical_json_bytes({"z": "한", "a": 1}), b'{"a":1,"z":"\\ud55c"}\n')
        with self.assertRaises(module.DiagnosticsError):
            module.canonical_json_bytes({"bad": float("nan")})

    def test_mapping_metadata_and_probe_are_deterministic(self) -> None:
        self.assertEqual(
            module.android_mapping_metadata(SAMPLE_MAPPING),
            {
                "compiler": "R8",
                "compilerVersion": "9.2.14",
                "mapHash": "b" * 64,
                "mapId": "a" * 64,
            },
        )
        self.assertEqual(
            list(module.iter_android_probe_candidates(SAMPLE_MAPPING)),
            [
                {
                    "mappingLineSha256": module.sha256(
                        b"    1:2:void recoverMe():42:42 -> b\n"
                    ),
                    "obfuscatedClass": "a",
                    "obfuscatedLine": 1,
                    "obfuscatedMethod": "b",
                    "originalClass": (
                        "com.localagentbridge.android.DiagnosticsProbeKt"
                    ),
                    "originalMethod": "recoverMe",
                    "sourceFile": "DiagnosticsProbe.kt",
                    "sourceLine": 42,
                }
            ],
        )

    def test_mapping_metadata_rejects_version_and_line_endings(self) -> None:
        with self.assertRaises(module.DiagnosticsError):
            module.android_mapping_metadata(
                SAMPLE_MAPPING.replace(b"9.2.14", b"9.2.13")
            )
        with self.assertRaises(module.DiagnosticsError):
            module.android_mapping_metadata(SAMPLE_MAPPING.replace(b"\n", b"\r\n"))

    def test_probe_rejects_unobfuscated_or_removed_candidates(self) -> None:
        for replacement in (
            SAMPLE_MAPPING.replace(
                b"DiagnosticsProbeKt -> a:",
                b"DiagnosticsProbeKt -> com.localagentbridge.android.DiagnosticsProbeKt:",
            ),
            SAMPLE_MAPPING.replace(b" -> a:\n", b" -> R8$$REMOVED$$CLASS$$1:\n"),
            SAMPLE_MAPPING.replace(b" -> b\n", b" -> recoverMe\n"),
        ):
            with self.subTest(replacement=replacement[-120:]):
                self.assertEqual(
                    [], list(module.iter_android_probe_candidates(replacement))
                )

    def test_android_probe_resolution_skips_ambiguous_first_candidate(self) -> None:
        mapping = (
            "com.localagentbridge.android.FirstKt -> a:\n"
            '# {"id":"sourceFile","fileName":"First.kt"}\n'
            "    1:1:void first():10:10 -> b\n"
            "com.localagentbridge.android.SecondKt -> c:\n"
            '# {"id":"sourceFile","fileName":"Second.kt"}\n'
            "    2:2:void recover():20:20 -> d\n"
        ).encode("utf-8")
        first_source = {"path": "apps/android/First.kt"}
        second_source = {"path": "apps/android/Second.kt"}
        second_output = (
            f"{module.ANDROID_PROBE_EXCEPTION}\n"
            "\tat com.localagentbridge.android.SecondKt.recover(Second.kt:20)\n"
        ).encode("utf-8")
        with mock.patch.object(
            module,
            "source_record",
            side_effect=(first_source, second_source),
        ) as source_mock, mock.patch.object(
            module,
            "run_retrace",
            side_effect=(b"ambiguous inline output\n", second_output),
        ) as retrace_mock:
            probe, source, stack, output = module.resolve_android_probe(
                mapping,
                root=Path("."),
                mapping_path=Path("mapping.txt"),
                java=Path("java"),
                classpath="builder.jar",
            )
        self.assertEqual(probe["originalClass"], "com.localagentbridge.android.SecondKt")
        self.assertEqual(source, second_source)
        self.assertEqual(
            stack,
            (
                f"{module.ANDROID_PROBE_EXCEPTION}\n"
                "\tat c.d(Second.kt:2)\n"
            ).encode("utf-8"),
        )
        self.assertEqual(output, second_output)
        self.assertEqual(source_mock.call_count, 2)
        self.assertEqual(retrace_mock.call_count, 2)

    def test_android_probe_resolution_caches_duplicate_stack_and_bounds_time(
        self,
    ) -> None:
        mapping = (
            "com.localagentbridge.android.InlineKt -> a:\n"
            '# {"id":"sourceFile","fileName":"Inline.kt"}\n'
            "    1:1:void outer():10:10 -> b\n"
            "    1:1:void inner():20:20 -> b\n"
        ).encode("utf-8")
        recovered = (
            f"{module.ANDROID_PROBE_EXCEPTION}\n"
            "\tat com.localagentbridge.android.InlineKt.inner(Inline.kt:20)\n"
        ).encode("utf-8")
        sources = (
            {"line": 10, "path": "apps/android/Inline.kt"},
            {"line": 20, "path": "apps/android/Inline.kt"},
        )
        with mock.patch.object(
            module,
            "source_record",
            side_effect=sources,
        ), mock.patch.object(
            module,
            "run_retrace",
            return_value=recovered,
        ) as retrace_mock:
            probe, source, _stack, output = module.resolve_android_probe(
                mapping,
                root=Path("."),
                mapping_path=Path("mapping.txt"),
                java=Path("java"),
                classpath="builder.jar",
            )
        self.assertEqual(probe["originalMethod"], "inner")
        self.assertEqual(source, sources[1])
        self.assertEqual(output, recovered)
        retrace_mock.assert_called_once()

        clock = iter((0.0, module.ANDROID_PROBE_TOTAL_TIMEOUT_SECONDS)).__next__
        with self.assertRaisesRegex(module.DiagnosticsError, "total deadline"):
            module.resolve_android_probe(
                SAMPLE_MAPPING,
                root=Path("."),
                mapping_path=Path("mapping.txt"),
                java=Path("java"),
                classpath="builder.jar",
                monotonic=clock,
            )

    def test_android_probe_deadline_covers_no_candidate_mapping_scan(
        self,
    ) -> None:
        mapping = ("# no eligible frame\n" * 8).encode("utf-8")
        clock = iter(
            (0.0, 0.0, module.ANDROID_PROBE_TOTAL_TIMEOUT_SECONDS)
        ).__next__
        with self.assertRaisesRegex(module.DiagnosticsError, "total deadline"):
            module.resolve_android_probe(
                mapping,
                root=Path("."),
                mapping_path=Path("mapping.txt"),
                java=Path("java"),
                classpath="builder.jar",
                monotonic=clock,
            )

    def test_android_probe_deadline_covers_scan_before_first_candidate(
        self,
    ) -> None:
        mapping = (
            b"#" * module.ANDROID_MAPPING_SCAN_CHUNK_BYTES
            + b"\n"
            + SAMPLE_MAPPING
        )
        clock = iter(
            (0.0, 0.0, module.ANDROID_PROBE_TOTAL_TIMEOUT_SECONDS)
        ).__next__
        with mock.patch.object(module, "source_record") as source_mock, \
             mock.patch.object(module, "run_retrace") as retrace_mock:
            with self.assertRaisesRegex(
                module.DiagnosticsError,
                "total deadline",
            ):
                module.resolve_android_probe(
                    mapping,
                    root=Path("."),
                    mapping_path=Path("mapping.txt"),
                    java=Path("java"),
                    classpath="builder.jar",
                    monotonic=clock,
                )
        source_mock.assert_not_called()
        retrace_mock.assert_not_called()

    def test_mapping_line_limit_rejects_before_regex_materialization(
        self,
    ) -> None:
        mapping = b"#" * (module.ANDROID_MAPPING_LINE_MAX_BYTES + 1) + b"\n"
        with self.assertRaisesRegex(module.DiagnosticsError, "byte limit"):
            list(module.iter_android_probe_candidates(mapping))

    def test_source_record_binds_unique_line_and_rejects_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = Path("apps/android/app/src/main")
            source = root / source_root / "java/example/DiagnosticsProbe.kt"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"first\nsecond\n")
            self.assertEqual(
                module.source_record(
                    root=root,
                    roots=(source_root,),
                    source_file="DiagnosticsProbe.kt",
                    source_line=2,
                ),
                {
                    "line": 2,
                    "lineSha256": module.sha256(b"second\n"),
                    "path": source.relative_to(root).as_posix(),
                    "sha256": module.sha256(b"first\nsecond\n"),
                    "size": 13,
                },
            )
            duplicate = root / source_root / "kotlin/other/DiagnosticsProbe.kt"
            duplicate.parent.mkdir(parents=True)
            duplicate.write_bytes(b"first\nsecond\n")
            with self.assertRaises(module.DiagnosticsError):
                module.source_record(
                    root=root,
                    roots=(source_root,),
                    source_file="DiagnosticsProbe.kt",
                    source_line=2,
                )

    def test_regular_read_rejects_symlink_and_hardlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            physical = root / "physical"
            physical.write_bytes(b"bytes")
            symlink = root / "symlink"
            symlink.symlink_to(physical)
            hardlink = root / "hardlink"
            os.link(physical, hardlink)
            with self.assertRaises(module.DiagnosticsError):
                module.read_regular_bytes(symlink, maximum_bytes=32)
            with self.assertRaises(module.DiagnosticsError):
                module.read_regular_bytes(physical, maximum_bytes=32)
            self.assertEqual(
                module.read_regular_bytes(
                    physical,
                    maximum_bytes=32,
                    require_single_link=False,
                ),
                b"bytes",
            )

    def test_run_command_rejects_stderr_nonzero_and_oversize(self) -> None:
        stdout, stderr = module.run_command(
            [sys.executable, "-c", "print('ok')"], maximum_bytes=16
        )
        self.assertEqual((stdout, stderr), ("ok\n", ""))
        with self.assertRaises(module.DiagnosticsError):
            module.run_command(
                [sys.executable, "-c", "import sys; print('bad', file=sys.stderr)"]
            )
        with self.assertRaises(module.DiagnosticsError):
            module.run_command([sys.executable, "-c", "raise SystemExit(3)"])
        with self.assertRaises(module.DiagnosticsError):
            module.run_command(
                [sys.executable, "-c", "print('x' * 20)"], maximum_bytes=8
            )

    def test_write_result_is_atomic_canonical_and_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            module.write_result(path, {"result": "ok", "schemaVersion": 1})
            self.assertEqual(
                path.read_bytes(), b'{"result":"ok","schemaVersion":1}\n'
            )
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            previous = path.read_bytes()
            with self.assertRaises(module.DiagnosticsError):
                module.write_result(path, {"bad": float("nan")})
            self.assertEqual(path.read_bytes(), previous)

    def test_macos_uuid_requires_one_arm64_record(self) -> None:
        with mock.patch.object(
            module,
            "run_command",
            return_value=(
                "UUID: 6B06A6D0-9C89-3D36-A5B9-D2381598DDC8 (arm64) image\n",
                "",
            ),
        ):
            self.assertEqual(
                module.macos_uuid(Path("image"), root=Path(".")),
                "6B06A6D0-9C89-3D36-A5B9-D2381598DDC8",
            )
        with mock.patch.object(
            module,
            "run_command",
            return_value=("UUID: malformed (arm64) image\n", ""),
        ):
            with self.assertRaises(module.DiagnosticsError):
                module.macos_uuid(Path("image"), root=Path("."))

    def test_macos_probe_selects_first_repository_source_frame(self) -> None:
        nm = (
            "0000000100000000 T __mh_execute_header\n"
            "0000000100001000 T _first\n"
            "0000000100002000 T _second\n"
        )
        outputs = [
            (nm, ""),
            (
                "0x0000000100001000\n"
                "Probe.run() (in AetherLink) (Probe.swift:7)\n",
                "",
            ),
        ]
        source = {
            "line": 7,
            "lineSha256": "a" * 64,
            "path": "apps/macos/Probe.swift",
            "sha256": "b" * 64,
            "size": 10,
        }
        with mock.patch.object(module, "run_command", side_effect=outputs), mock.patch.object(
            module, "source_record", return_value=source
        ):
            self.assertEqual(
                module.macos_probe(
                    executable=Path("app"), dwarf=Path("dwarf"), root=Path(".")
                ),
                {
                    "address": "0x0000000100002000",
                    "nmSymbol": "_second",
                    "source": source,
                    "sourceFile": "Probe.swift",
                    "sourceLine": 7,
                    "symbol": "Probe.run()",
                    "symbolicatedFrame": (
                        "Probe.run() (in AetherLink) (Probe.swift:7)"
                    ),
                    "symbolicatedFrameSha256": module.sha256(
                        b"Probe.run() (in AetherLink) (Probe.swift:7)\n"
                    ),
                },
            )

    def test_prerequisite_digest_dispatches_and_wraps_failures(self) -> None:
        with mock.patch.object(
            module.archive,
            "verify_android_release_build_outputs",
            return_value={"ok": True},
        ):
            self.assertEqual(
                module.prerequisite_digest("android"),
                module.sha256(module.archive.canonical_json_bytes({"ok": True})),
            )
        with mock.patch.object(
            module.archive,
            "verify_macos_release_build_outputs",
            side_effect=module.archive.ReleaseArchiveVerificationError("bad"),
        ):
            with self.assertRaises(module.DiagnosticsError):
                module.prerequisite_digest("macos")


if __name__ == "__main__":
    unittest.main()
