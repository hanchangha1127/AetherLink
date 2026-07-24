#!/usr/bin/env python3
"""Synthetic tests for the exact G2 Pion non-Unix creator policy overlay."""

from __future__ import annotations

import ast
import io
from pathlib import Path
import threading
from types import ModuleType
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "script/p2p_nat_g2_pion_offline_zip.py"
POLICY_PATH = ROOT / "script/p2p_nat_g2_pion_offline_zip_creator_policy_v2.py"
MODULE_PREFIX = "github.com/pion/ice/v4@v4.3.0/"


def load_exact_source(path: Path, name: str, compile_name: str) -> ModuleType:
    raw = path.read_bytes()
    module = ModuleType(name)
    module.__file__ = compile_name
    code = compile(
        raw,
        compile_name,
        "exec",
        flags=0,
        dont_inherit=True,
        optimize=0,
    )
    exec(code, module.__dict__, module.__dict__)
    return module


BASE = load_exact_source(
    BASE_PATH,
    "g2_pion_offline_zip_base",
    "script/p2p_nat_g2_pion_offline_zip.py",
)
BASE_SOURCE = BASE_PATH.read_bytes()
POLICY = load_exact_source(
    POLICY_PATH,
    "g2_pion_offline_zip_creator_policy_v2",
    "script/p2p_nat_g2_pion_offline_zip_creator_policy_v2.py",
)


def entry(
    name: str,
    *,
    creator: int,
    external_attributes: int,
    content: bytes,
) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name)
    info.create_system = creator
    info.create_version = 20
    info.extract_version = 20
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = external_attributes
    return info, content


def make_zip(entries: list[tuple[zipfile.ZipInfo, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for info, content in entries:
                archive.writestr(info, content)
    return output.getvalue()


def dos_zip(attributes: int = POLICY.DOS_ARCHIVE, creator: int = 0) -> bytes:
    return make_zip(
        [
            entry(
                MODULE_PREFIX + "go.mod",
                creator=creator,
                external_attributes=attributes,
                content=b"module github.com/pion/ice/v4\n",
            ),
            entry(
                MODULE_PREFIX + "ice.go",
                creator=creator,
                external_attributes=attributes,
                content=b"package ice\n",
            ),
        ]
    )


def with_zero_external_attributes(raw: bytes) -> bytes:
    output = bytearray(raw)
    eocd_offset = len(output) - BASE.EOCD.size
    fields = BASE.EOCD.unpack_from(output, eocd_offset)
    entry_count = fields[4]
    cursor = fields[6]
    for _ in range(entry_count):
        if bytes(output[cursor : cursor + 4]) != BASE.CENTRAL_SIGNATURE:
            raise AssertionError("synthetic central-directory signature drifted")
        name_length = int.from_bytes(output[cursor + 28 : cursor + 30], "little")
        extra_length = int.from_bytes(output[cursor + 30 : cursor + 32], "little")
        comment_length = int.from_bytes(output[cursor + 32 : cursor + 34], "little")
        output[cursor + 38 : cursor + 42] = b"\x00\x00\x00\x00"
        cursor += 46 + name_length + extra_length + comment_length
    return bytes(output)


def unix_zip() -> bytes:
    regular_mode = 0o100644 << 16
    return make_zip(
        [
            entry(
                MODULE_PREFIX + "go.mod",
                creator=3,
                external_attributes=regular_mode,
                content=b"module github.com/pion/ice/v4\n",
            ),
            entry(
                MODULE_PREFIX + "ice.go",
                creator=3,
                external_attributes=regular_mode,
                content=b"package ice\n",
            ),
        ]
    )


def mixed_creator_zip() -> bytes:
    return make_zip(
        [
            entry(
                MODULE_PREFIX + "go.mod",
                creator=0,
                external_attributes=0x20,
                content=b"module github.com/pion/ice/v4\n",
            ),
            entry(
                MODULE_PREFIX + "ice.go",
                creator=3,
                external_attributes=0o100644 << 16,
                content=b"package ice\n",
            ),
        ]
    )


def fresh_base() -> ModuleType:
    return load_exact_source(
        BASE_PATH,
        "g2_pion_offline_zip_private",
        "script/p2p_nat_g2_pion_offline_zip.py",
    )


def corrupt_first_entry_crc(raw: bytes) -> bytes:
    output = bytearray(raw)
    eocd = len(output) - BASE.EOCD.size
    central = BASE.EOCD.unpack_from(output, eocd)[6]
    local = int.from_bytes(output[central + 42 : central + 46], "little")
    crc = int.from_bytes(output[central + 16 : central + 20], "little") ^ 1
    encoded = crc.to_bytes(4, "little")
    output[central + 16 : central + 20] = encoded
    output[local + 14 : local + 18] = encoded
    return bytes(output)


def corrupt_first_entry_payload(raw: bytes) -> bytes:
    output = bytearray(raw)
    eocd = len(output) - BASE.EOCD.size
    central = BASE.EOCD.unpack_from(output, eocd)[6]
    local = int.from_bytes(output[central + 42 : central + 46], "little")
    name_length = int.from_bytes(output[local + 26 : local + 28], "little")
    extra_length = int.from_bytes(output[local + 28 : local + 30], "little")
    data = local + 30 + name_length + extra_length
    output[data] ^= 0xFF
    return bytes(output)


class CreatorPolicyV2Tests(unittest.TestCase):
    def inspect(self, raw: bytes):
        return POLICY.inspect_module_zip(
            BASE_SOURCE,
            raw,
            module_prefix=MODULE_PREFIX,
        )

    def test_01_accepts_exact_dos_archive_regular_files(self) -> None:
        result = self.inspect(dos_zip())
        metadata = result["creatorMetadataPolicy"]
        self.assertEqual(metadata["msDosRegularFileCount"], 2)
        self.assertEqual(metadata["unixEntryCount"], 0)
        self.assertEqual(metadata["acceptedDosExternalAttributes"], ["20"])
        self.assertEqual(metadata["syntheticReadOnlyRegularMode"], "100444")
        self.assertFalse(metadata["filesystemExtractionAllowed"])
        self.assertTrue(all(row["unixMode"] == "100444" for row in result["entries"]))

    def test_02_accepts_only_read_only_and_archive_dos_bits(self) -> None:
        for attributes in (0x01, 0x20, 0x21):
            with self.subTest(attributes=attributes):
                result = self.inspect(dos_zip(attributes))
                self.assertEqual(
                    result["creatorMetadataPolicy"]["acceptedDosExternalAttributes"],
                    [f"{attributes:02x}"],
                )
        zero_result = self.inspect(with_zero_external_attributes(dos_zip()))
        self.assertEqual(
            zero_result["creatorMetadataPolicy"]["acceptedDosExternalAttributes"],
            ["00"],
        )

    def test_03_unix_creator_delegates_without_semantic_change(self) -> None:
        raw = unix_zip()
        expected = fresh_base().inspect_module_zip(raw, module_prefix=MODULE_PREFIX)
        actual = self.inspect(raw)
        metadata = actual.pop("creatorMetadataPolicy")
        self.assertEqual(actual, expected)
        self.assertEqual(metadata["unixEntryCount"], 2)
        self.assertEqual(metadata["msDosRegularFileCount"], 0)

    def test_04_rejects_non_dos_creator_systems(self) -> None:
        with self.assertRaisesRegex(POLICY.CreatorMetadataPolicyError, "unsupported ZIP creator"):
            self.inspect(dos_zip(0x20, creator=1))

    def test_05_rejects_dos_hidden_system_volume_directory_and_unknown_bits(self) -> None:
        for attributes in (0x02, 0x04, 0x08, 0x10, 0x40, 0x80):
            with self.subTest(attributes=attributes):
                with self.assertRaisesRegex(
                    POLICY.CreatorMetadataPolicyError,
                    "forbidden attributes",
                ):
                    self.inspect(dos_zip(attributes))

    def test_06_rejects_creator_zero_high_or_middle_attributes(self) -> None:
        for attributes in (0x0100, 0o100644 << 16, (0o100644 << 16) | 0x20):
            with self.subTest(attributes=attributes):
                with self.assertRaisesRegex(
                    POLICY.CreatorMetadataPolicyError,
                    "hidden high attributes",
                ):
                    self.inspect(dos_zip(attributes))

    def test_07_each_call_uses_fresh_private_state(self) -> None:
        first = self.inspect(dos_zip())
        with self.assertRaises(POLICY.CreatorMetadataPolicyError):
            self.inspect(dos_zip(0x02))
        second = self.inspect(dos_zip())
        self.assertEqual(first, second)

    def test_08_rejects_nonbytes_or_drifted_base_source(self) -> None:
        drifted = bytearray(BASE_SOURCE)
        drifted[-1] ^= 1
        for invalid in (bytearray(BASE_SOURCE), bytes(drifted), b""):
            with self.subTest(kind=type(invalid).__name__, length=len(invalid)):
                with self.assertRaises(POLICY.CreatorMetadataPolicyError):
                    POLICY.inspect_module_zip(
                        invalid,
                        dos_zip(),
                        module_prefix=MODULE_PREFIX,
                    )

    def test_09_policy_source_only_compiles_the_pinned_auxiliary_tool(self) -> None:
        tree = ast.parse(POLICY_PATH.read_text(encoding="utf-8"))
        imports = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        self.assertEqual(imports, {"__future__", "builtins", "hashlib", "types"})
        self.assertIn("compile", calls)
        self.assertIn("exec", calls)
        self.assertTrue(
            calls.isdisjoint(
                {
                    "open",
                    "eval",
                    "system",
                    "popen",
                    "urlopen",
                    "socket",
                }
            )
        )

    def test_10_records_exact_path_provenance_for_mixed_creators(self) -> None:
        result = self.inspect(mixed_creator_zip())
        metadata = result["creatorMetadataPolicy"]
        self.assertEqual(metadata["msDosRegularFileCount"], 1)
        self.assertEqual(metadata["unixEntryCount"], 1)
        by_path = {row["path"]: row for row in metadata["entryMetadata"]}
        self.assertEqual(
            by_path[MODULE_PREFIX + "go.mod"],
            {
                "path": MODULE_PREFIX + "go.mod",
                "creatorSystem": 0,
                "externalAttributes": "00000020",
                "modeSource": "synthetic_read_only_regular_mode",
                "effectiveUnixMode": "100444",
            },
        )
        self.assertEqual(
            by_path[MODULE_PREFIX + "ice.go"]["modeSource"],
            "archive_unix_mode",
        )
        self.assertEqual(
            by_path[MODULE_PREFIX + "ice.go"]["effectiveUnixMode"],
            "100644",
        )

    def test_11_rejects_explicit_ms_dos_directory_entries(self) -> None:
        raw = make_zip(
            [
                entry(
                    MODULE_PREFIX + "dir/",
                    creator=0,
                    external_attributes=0x10,
                    content=b"",
                ),
                entry(
                    MODULE_PREFIX + "go.mod",
                    creator=0,
                    external_attributes=0x20,
                    content=b"module github.com/pion/ice/v4\n",
                ),
            ]
        )
        with self.assertRaisesRegex(
            POLICY.CreatorMetadataPolicyError,
            "regular files only",
        ):
            self.inspect(raw)

    def test_12_preserves_path_collision_and_resource_checks_for_dos(self) -> None:
        invalid_path = make_zip(
            [
                entry(
                    MODULE_PREFIX + "../go.mod",
                    creator=0,
                    external_attributes=0x20,
                    content=b"module github.com/pion/ice/v4\n",
                )
            ]
        )
        with self.assertRaises(RuntimeError):
            self.inspect(invalid_path)

        duplicate = make_zip(
            [
                entry(
                    MODULE_PREFIX + "go.mod",
                    creator=0,
                    external_attributes=0x20,
                    content=b"module github.com/pion/ice/v4\n",
                ),
                entry(
                    MODULE_PREFIX + "go.mod",
                    creator=0,
                    external_attributes=0x20,
                    content=b"module github.com/pion/ice/v4\n",
                ),
            ]
        )
        with self.assertRaises(RuntimeError):
            self.inspect(duplicate)

        with self.assertRaises(RuntimeError):
            POLICY.inspect_module_zip(
                BASE_SOURCE,
                dos_zip(),
                module_prefix=MODULE_PREFIX,
                limits={"singleFileBytes": 8},
            )

        for corrupted in (
            corrupt_first_entry_crc(dos_zip()),
            corrupt_first_entry_payload(dos_zip()),
        ):
            with self.assertRaises(RuntimeError):
                self.inspect(corrupted)

        high_ratio = make_zip(
            [
                entry(
                    MODULE_PREFIX + "go.mod",
                    creator=0,
                    external_attributes=0x20,
                    content=b"module github.com/pion/ice/v4\n" + b"A" * 4096,
                ),
                entry(
                    MODULE_PREFIX + "ice.go",
                    creator=0,
                    external_attributes=0x20,
                    content=b"package ice\n",
                ),
            ]
        )
        with self.assertRaises(RuntimeError):
            POLICY.inspect_module_zip(
                BASE_SOURCE,
                high_ratio,
                module_prefix=MODULE_PREFIX,
                limits={"compressionRatio": 1},
            )

    def test_13_concurrent_calls_have_disjoint_private_modules(self) -> None:
        failures = []
        results = []

        def inspect_once() -> None:
            try:
                results.append(self.inspect(mixed_creator_zip()))
            except BaseException as error:
                failures.append(error)

        workers = [threading.Thread(target=inspect_once) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=2)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(failures, [])
        self.assertEqual(len(results), 8)
        self.assertTrue(all(result == results[0] for result in results))


if __name__ == "__main__":
    unittest.main()
