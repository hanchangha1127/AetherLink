#!/usr/bin/env python3
"""Focused offline tests for the one-use Wave19 acquisition runner."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("Wave19 runner tests require `python3 -I -B -S`")

import ast
from contextlib import ExitStack
import copy
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import tempfile
import time
import types
import unittest
from unittest import mock
import warnings
import zipfile


def _deny_network(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("offline Wave19 tests must never create a connection")


http.client.HTTPSConnection = _deny_network
socket.create_connection = _deny_network

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT
    / "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave19_acquisition_v1.py"
)
RUNNER_RELATIVE_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py"
)
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave19_v1_once.py"
)
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
PERMIT_PATH = (
    ROOT
    / BASE
    / "bounded-dependency-source-acquisition-wave19-execution-permit-v1.json"
)
RESOURCE_CONTRACT_SHA256 = (
    "e5effbf132773b38711521ab3da4fec70732867556024fe997a4f735027ce484"
)
PROJECTION_SHA256 = (
    "2da2915bfcf76ddc2d3bf6d15c6ad7246116e17ab0d175554484b8662068e375"
)
RUNNER_CALL_COUNT = 755
RUNNER_CALL_SURFACE_SHA256 = (
    "602b3df860e8a58781f54869a7e9f95a993ab541ab9eb1087337dd20e3fbfbea"
)
TUPLES = (
    (
        "golang.org/x/crypto",
        "v0.38.0",
        "a26a2513c9f4c49c479c1378fd9e7d313032cb9ffc32a1a38dcebd0be1ae9b43",
        "h1:MvrbAqul58NNYPKnOra203SB9vpuZW0e+RRZV+Ggqjw=",
        "h1:jt+WWG8IZlBnVbomuhg2Mdq0+BBQaHbtqHEFEigjUV8=",
    ),
    (
        "golang.org/x/text",
        "v0.25.0",
        "c6022d5be99f60f2428ee0f587172a28d4eeeebb9f36694f4ab42177bcd585b8",
        "h1:WEdwpYrmk1qmdHvhkSTNPm3app7v4rsT8F2UD6+VHIA=",
        "h1:qVyWApTSYLk/drJRO5mDlNYskwQznZmkpV2c8q9zls4=",
    ),
)
MISSING_ROOT_GO_MOD = object()

EXPECTED_IMPORTS = (
    ("from", "__future__", 0, (("annotations", None),)),
    ("import", (("sys", None),)),
    ("import", (("argparse", None),)),
    ("import", (("ctypes", None),)),
    (
        "from",
        "dataclasses",
        0,
        (("dataclass", None), ("replace", None)),
    ),
    ("from", "enum", 0, (("Enum", None), ("auto", None))),
    ("import", (("errno", None),)),
    ("import", (("hashlib", None),)),
    ("import", (("json", None),)),
    ("import", (("os", None),)),
    ("from", "pathlib", 0, (("Path", None),)),
    ("import", (("re", None),)),
    ("import", (("secrets", None),)),
    ("import", (("signal", None),)),
    ("import", (("stat", None),)),
    ("import", (("threading", None),)),
    ("import", (("time", None),)),
    ("import", (("types", None),)),
    (
        "from",
        "typing",
        0,
        (
            ("Any", None),
            ("Callable", None),
            ("Mapping", None),
            ("Sequence", None),
        ),
    ),
    ("import", (("unicodedata", None),)),
)

RUNNER_RAW = RUNNER_PATH.read_bytes()
RUNNER_SOURCE = RUNNER_RAW.decode("utf-8")
RUNNER_TREE = ast.parse(RUNNER_SOURCE, filename=str(RUNNER_PATH))
PERMIT = json.loads(PERMIT_PATH.read_bytes())


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def import_surface(tree: ast.AST) -> tuple[object, ...]:
    result: list[object] = []
    nodes = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for node in nodes:
        if isinstance(node, ast.Import):
            result.append(
                (
                    "import",
                    tuple((alias.name, alias.asname) for alias in node.names),
                )
            )
        else:
            result.append(
                (
                    "from",
                    node.module,
                    node.level,
                    tuple((alias.name, alias.asname) for alias in node.names),
                )
            )
    return tuple(result)


class CallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = []
        self.calls: list[tuple[int, int, str, ast.Call]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(
            (
                node.lineno,
                node.col_offset,
                ".".join(self.scope) or "<module>",
                node,
            )
        )
        self.generic_visit(node)


def call_surface_sha256(
    rows: list[tuple[int, int, str, ast.Call]],
) -> str:
    projection = [
        {
            "call": ast.dump(
                call,
                annotate_fields=True,
                include_attributes=False,
            ),
            "scope": scope,
        }
        for _, _, scope, call in sorted(
            rows,
            key=lambda row: (
                row[0],
                row[1],
                row[2],
                ast.dump(
                    row[3],
                    annotate_fields=True,
                    include_attributes=False,
                ),
            ),
        )
    ]
    return sha256(canonical(projection))


def surface_signature(
    source: str,
) -> tuple[tuple[object, ...], int, str]:
    tree = ast.parse(source, filename=str(RUNNER_PATH))
    visitor = CallVisitor()
    visitor.visit(tree)
    return (
        import_surface(tree),
        len(visitor.calls),
        call_surface_sha256(visitor.calls),
    )


def normalized_runner(raw: bytes) -> bytes:
    marker = re.compile(br'EXPECTED_CHECKER_RAW = "[0-9a-f]{64}"')
    result, count = marker.subn(
        b'EXPECTED_CHECKER_RAW = "' + b"0" * 64 + b'"',
        raw,
    )
    if count != 1:
        raise AssertionError("runner normalization")
    return result


def preload_runner_gate(
    raw: bytes,
    source: str,
    tree: ast.AST,
    permit: object,
) -> dict[str, object]:
    if type(permit) is not dict:
        raise RuntimeError("Wave19 runner test permit schema")
    tool_bindings = permit.get("toolBindings")
    if type(tool_bindings) is not list:
        raise RuntimeError("Wave19 runner test tool bindings")
    runner_bindings = [
        row
        for row in tool_bindings
        if type(row) is dict
        and row.get("path") == RUNNER_RELATIVE_PATH
    ]
    if len(runner_bindings) != 1:
        raise RuntimeError(
            "Wave19 runner test runner binding cardinality"
        )
    binding = runner_bindings[0]
    if (
        set(binding)
        != {"normalizedSha256", "path", "rawSha256", "role"}
        or binding["role"] != "wave19_one_use_runner"
        or type(binding["rawSha256"]) is not str
        or type(binding["normalizedSha256"]) is not str
        or import_surface(tree) != EXPECTED_IMPORTS
        or surface_signature(source)
        != (
            EXPECTED_IMPORTS,
            RUNNER_CALL_COUNT,
            RUNNER_CALL_SURFACE_SHA256,
        )
        or sha256(raw) != binding["rawSha256"]
        or sha256(normalized_runner(raw))
        != binding["normalizedSha256"]
    ):
        raise RuntimeError("Wave19 runner test preload gate")
    return binding


PRELOAD_RUNNER_BINDING = preload_runner_gate(
    RUNNER_RAW,
    RUNNER_SOURCE,
    RUNNER_TREE,
    PERMIT,
)

SPEC = importlib.util.spec_from_file_location(
    "wave19_source_acquirer_v1_test_subject",
    RUNNER_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Wave19 runner test module spec")
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)
PRODUCTION_INVOCATION_VALIDATOR = runner.validate_production_invocation


def exact_resource_oracle() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for tuple_order, (
        module,
        version,
        digest,
        mod_h1,
        zip_h1,
    ) in enumerate(TUPLES, 1):
        for kind, expected_h1 in (("mod", mod_h1), ("zip", zip_h1)):
            path = f"/{module}/@v/{version}.{kind}"
            rows.append(
                {
                    "acceptedFileName":
                        f"{tuple_order:03d}-{digest[:20]}.{kind}",
                    "expectedH1": expected_h1,
                    "host": "proxy.golang.org",
                    "kind": kind,
                    "maximumResponseBodyBytes":
                        1_048_576 if kind == "mod" else 16_777_216,
                    "method": "GET",
                    "module": module,
                    "path": path,
                    "port": 443,
                    "requestOrdinal": len(rows) + 1,
                    "selectedByGraphAlgorithm": False,
                    "tupleDigestSha256": digest,
                    "tupleId":
                        f"wave19-{tuple_order:03d}-{digest[:12]}",
                    "tupleOrder": tuple_order,
                    "url": f"https://proxy.golang.org{path}",
                    "version": version,
                }
            )
    return rows


def make_zip(
    module: str,
    version: str,
    files: list[tuple[str, bytes, int | None]],
) -> bytes:
    output = io.BytesIO()
    prefix = f"{module}@{version}/"
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, raw, mode in files:
            info = zipfile.ZipInfo(prefix + name)
            info.create_system = 3
            info.external_attr = (
                (stat.S_IFREG | 0o644) if mode is None else mode
            ) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return output.getvalue()


def fixture() -> tuple[list[dict[str, object]], dict[int, bytes]]:
    rows = exact_resource_oracle()
    bodies: dict[int, bytes] = {}
    for tuple_order, (module, version, _, _, _) in enumerate(TUPLES, 1):
        mod = f"module {module}\n\ngo 1.22\n".encode()
        archive = make_zip(
            module,
            version,
            [
                ("go.mod", mod, None),
                ("source.go", b"package source\n", None),
            ],
        )
        bodies[tuple_order * 2 - 1] = mod
        bodies[tuple_order * 2] = archive
    return rows, bodies


def values(rows: list[dict[str, object]]) -> dict[str, object]:
    permit = copy.deepcopy(PERMIT)
    permit["requestContract"]["requestCount"] = 4
    permit["requestContract"]["resources"] = rows
    permit["requestContract"]["resourcesCanonicalSha256"] = runner.sha256(
        runner.canonical_bytes(rows)
    )
    return {
        "decision": {"contentBinding": {"sha256": "d" * 64}},
        "permit": permit,
    }


def synthetic_validation(
    mismatch_ordinal: int | None = None,
    *,
    root_go_mod_values: dict[int, object] | None = None,
    zip_entry_counts: dict[int, object] | None = None,
    zip_uncompressed_counts: dict[int, object] | None = None,
) -> ExitStack:
    expected = {
        module: (tuple_order, mod_h1, zip_h1)
        for tuple_order, (
            module,
            _,
            _,
            mod_h1,
            zip_h1,
        ) in enumerate(TUPLES, 1)
    }

    def validate_mod(raw: bytes, module: str) -> dict[str, object]:
        tuple_order, mod_h1, _ = expected[module]
        return {
            "goModH1":
                "synthetic-mismatch"
                if mismatch_ordinal == tuple_order * 2 - 1
                else mod_h1,
            "rawSha256": sha256(raw),
        }

    def validate_zip(
        raw: bytes,
        module: str,
        _version: str,
        _mod_raw: bytes,
    ) -> dict[str, object]:
        tuple_order, _, zip_h1 = expected[module]
        root_go_mod_present = (
            True
            if root_go_mod_values is None
            else root_go_mod_values[tuple_order]
        )
        result = {
            "entryCount": (
                2
                if zip_entry_counts is None
                else zip_entry_counts[tuple_order]
            ),
            "moduleZipH1":
                "synthetic-mismatch"
                if mismatch_ordinal == tuple_order * 2
                else zip_h1,
            "rawSha256": sha256(raw),
            "uncompressedBytes": (
                len(raw)
                if zip_uncompressed_counts is None
                else zip_uncompressed_counts[tuple_order]
            ),
        }
        if root_go_mod_present is not MISSING_ROOT_GO_MOD:
            result["rootGoModPresent"] = root_go_mod_present
        return result

    stack = ExitStack()
    stack.enter_context(
        mock.patch.object(
            runner.VALIDATION,
            "validate_mod",
            side_effect=validate_mod,
        )
    )
    stack.enter_context(
        mock.patch.object(
            runner.VALIDATION,
            "validate_zip",
            side_effect=validate_zip,
        )
    )
    return stack


class MemoryEntry:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def verify_bytes(self, _phase: str) -> bytes:
        return self.raw


class PureNamespace:
    """In-memory namespace seam; it performs no filesystem operations."""

    def __init__(
        self,
        *,
        fail_receipt: bool = False,
        fail_failure: bool = False,
    ) -> None:
        self.events: list[str] = []
        self.claim: object | None = None
        self.staging: object | None = None
        self.resources: dict[str, bytes] = {}
        self.evidence: MemoryEntry | None = None
        self.receipt: MemoryEntry | None = None
        self.manifest: MemoryEntry | None = None
        self.failure: MemoryEntry | None = None
        self.published = False
        self.fail_receipt = fail_receipt
        self.fail_failure = fail_failure

    def barrier(self, state: object) -> None:
        self.events.append(f"barrier:{state.name.lower()}")

    def create_claim(self, _payload: object) -> None:
        self.events.append("claim")
        self.claim = object()

    def create_staging(self, _attempt_id: str) -> None:
        self.events.append("staging")
        self.staging = object()

    def persist_resource(self, name: str, raw: bytes) -> MemoryEntry:
        self.events.append(f"resource:{name}")
        self.resources[name] = raw
        return MemoryEntry(raw)

    def persist_evidence(self, raw: bytes) -> MemoryEntry:
        self.events.append("evidence")
        self.evidence = MemoryEntry(raw)
        return self.evidence

    def verify_payloads(self, phase: str) -> None:
        self.events.append(f"verify:{phase}")

    def sync_staging(self) -> None:
        self.events.append("sync")

    def publish(self) -> None:
        self.events.append("publish")
        self.published = True

    def persist_receipt(self, raw: bytes) -> MemoryEntry:
        self.events.append("receipt")
        if self.fail_receipt:
            raise OSError("synthetic receipt failure")
        self.receipt = MemoryEntry(raw)
        return self.receipt

    def persist_manifest(self, raw: bytes) -> MemoryEntry:
        self.events.append("manifest")
        self.manifest = MemoryEntry(raw)
        return self.manifest

    def persist_failure(self, raw: bytes) -> MemoryEntry:
        self.events.append("failure")
        if self.fail_failure:
            raise OSError("synthetic failure publication failure")
        self.failure = MemoryEntry(raw)
        return self.failure


class FailingPersistenceNamespace(PureNamespace):
    def __init__(self, failed_ordinal: int, failure_kind: str) -> None:
        super().__init__()
        self.failed_ordinal = failed_ordinal
        self.failure_kind = failure_kind
        self.persistence_attempts = 0

    def persist_resource(self, name: str, raw: bytes) -> MemoryEntry:
        self.persistence_attempts += 1
        if self.persistence_attempts == self.failed_ordinal:
            if self.failure_kind == "read_after_write":
                self.events.append(f"resource:{name}")
                self.resources[name] = raw
                raise runner.AcquisitionError(
                    "E_PERSISTED_IDENTITY",
                    "resource",
                )
            if self.failure_kind == "write":
                raise runner.AcquisitionError("E_WRITE", "resource")
            raise AssertionError(self.failure_kind)
        return super().persist_resource(name, raw)


class FakeProcess:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.mask: set[signal.Signals] = set()
        self.original_handler = object()
        self.handler: object = self.original_handler
        self.timer = (5.0, 0.25)
        self.umask_value = 0o022
        self.clock = 100.0
        self.signal_calls = 0
        self.timer_calls = 0
        self.umask_calls = 0

    def pthread_sigmask(
        self,
        how: object,
        values: object,
    ) -> set[signal.Signals]:
        previous = set(self.mask)
        update = set(values)
        if how == signal.SIG_BLOCK:
            self.calls.append("block")
            self.mask.update(update)
        elif how == signal.SIG_SETMASK:
            self.calls.append("setmask")
            self.mask = update
        else:
            raise AssertionError(how)
        return previous

    def getsignal(self, _signum: int) -> object:
        self.calls.append("getsignal")
        return self.handler

    def getitimer(self, _which: int) -> tuple[float, float]:
        self.calls.append("getitimer")
        return self.timer

    def set_signal(self, _signum: int, handler: object) -> object:
        self.signal_calls += 1
        self.calls.append(
            "install_handler"
            if self.signal_calls == 1
            else "restore_handler"
        )
        previous = self.handler
        self.handler = handler
        return previous

    def setitimer(
        self,
        _which: int,
        delay: float,
        interval: float = 0,
    ) -> tuple[float, float]:
        self.timer_calls += 1
        if self.timer_calls == 1:
            label = "install_timer"
        elif delay == 0:
            label = "cancel_timer"
        else:
            label = "restore_timer"
        self.calls.append(label)
        previous = self.timer
        self.timer = (float(delay), float(interval))
        return previous

    def sigpending(self) -> set[signal.Signals]:
        self.calls.append("pending")
        return set()

    def sigwait(self, _values: object) -> int:
        raise AssertionError("no pending signal")

    def umask(self, value: int) -> int:
        self.umask_calls += 1
        self.calls.append(
            "install_umask" if self.umask_calls == 1 else "restore_umask"
        )
        previous = self.umask_value
        self.umask_value = value
        return previous

    def monotonic(self) -> float:
        self.clock += 0.01
        return self.clock

    def operations(self) -> object:
        return runner.ProcessOps(
            getsignal=self.getsignal,
            getitimer=self.getitimer,
            set_signal=self.set_signal,
            setitimer=self.setitimer,
            sigpending=self.sigpending,
            sigwait=self.sigwait,
            pthread_sigmask=self.pthread_sigmask,
            umask=self.umask,
            monotonic=self.monotonic,
        )


def prepare_root(root: Path) -> None:
    (root / runner.CHECK.DEPENDENCY_ROOT).mkdir(parents=True, mode=0o700)
    (root / runner.CHECK.BASE).mkdir(parents=True, mode=0o700)


class Wave19RunnerTests(unittest.TestCase):
    maxDiff = None

    def test_01_static_surface_bindings_and_exact_four_resources(self) -> None:
        self.assertEqual(import_surface(RUNNER_TREE), EXPECTED_IMPORTS)
        self.assertEqual(
            surface_signature(RUNNER_SOURCE),
            (
                EXPECTED_IMPORTS,
                RUNNER_CALL_COUNT,
                RUNNER_CALL_SURFACE_SHA256,
            ),
        )
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(RUNNER_TREE)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(RUNNER_TREE)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertTrue(
            imported_roots.isdisjoint(
                {"socket", "subprocess", "urllib", "requests", "http"}
            )
        )
        self.assertIn("expected_count == 4", RUNNER_SOURCE)
        self.assertIn("dont_inherit=True", RUNNER_SOURCE)
        self.assertIn("optimize=0", RUNNER_SOURCE)
        self.assertEqual(
            runner.EXPECTED_WAVE19_IDENTITY,
            tuple(
                (module, version, mod_h1, zip_h1)
                for module, version, _, mod_h1, zip_h1 in TUPLES
            ),
        )
        rows = exact_resource_oracle()
        self.assertEqual(
            runner._validate_resource_contract(rows, PERMIT),
            rows,
        )
        self.assertEqual(
            runner.sha256(runner.canonical_bytes(rows)),
            RESOURCE_CONTRACT_SHA256,
        )
        self.assertEqual(
            runner.EXPECTED_WAVE19_RESOURCE_CONTRACT_SHA256,
            RESOURCE_CONTRACT_SHA256,
        )
        self.assertEqual(
            PERMIT["zipLimits"]["maximumEntryNameBytes"],
            1_024,
        )
        self.assertEqual(
            runner.VALIDATION.CHECK.MAX_ZIP_NAME_BYTES,
            PERMIT["zipLimits"]["maximumEntryNameBytes"],
        )
        self.assertEqual(
            runner.WAVE4.CHECK.MAX_ZIP_NAME_BYTES,
            PERMIT["zipLimits"]["maximumEntryNameBytes"],
        )
        primitive_numeric_names = (
            "MAX_MOD_BYTES",
            "MAX_ZIP_BYTES",
            "MAX_ZIP_NAME_BYTES",
            "MAX_ZIP_FILES",
            "MAX_ZIP_UNCOMPRESSED_BYTES",
            "MAX_ZIP_FILE_BYTES",
            "MAX_AGGREGATE_BYTES",
            "MAX_HEADER_BYTES",
            "PER_REQUEST_DEADLINE_MS",
            "WHOLE_ATTEMPT_DEADLINE_MS",
        )
        for primitive_check in (
            runner.WAVE4.CHECK,
            runner.VALIDATION.CHECK,
        ):
            for key in primitive_numeric_names:
                expected = getattr(primitive_check, key)
                self.assertIs(type(expected), int)
                if key == "MAX_AGGREGATE_BYTES":
                    self.assertEqual(
                        expected,
                        runner.WAVE4.CHECK.MAX_AGGREGATE_BYTES,
                    )
                    self.assertGreaterEqual(
                        expected,
                        runner.CHECK.MAX_AGGREGATE_BYTES,
                    )
                else:
                    self.assertEqual(
                        expected,
                        getattr(runner.CHECK, key),
                    )
                for mutation_kind, mutation in (
                    ("changed_int", expected + 1),
                    ("float_alias", float(expected)),
                    ("bool_alias", True),
                ):
                    with (
                        self.subTest(
                            primitive=primitive_check.__name__,
                            numeric_binding=key,
                            mutation=mutation_kind,
                        ),
                        mock.patch.object(
                            primitive_check,
                            key,
                            mutation,
                        ),
                        self.assertRaises(
                            runner.AcquisitionError
                        ) as caught,
                    ):
                        runner._assert_primitive_contract()
                    self.assertEqual(
                        caught.exception.code,
                        "E_PRIMITIVE_BINDING",
                    )
        bindings = {
            row["path"]: row for row in PERMIT["toolBindings"]
        }
        self.assertEqual(
            set(bindings),
            {
                CHECKER_PATH,
                CHECKER_TEST_PATH,
                RUNNER_RELATIVE_PATH,
                RUNNER_TEST_PATH,
            },
        )
        self.assertEqual(
            PRELOAD_RUNNER_BINDING,
            bindings[RUNNER_RELATIVE_PATH],
        )
        test_source = Path(__file__).read_text(encoding="utf-8")
        self.assertLess(
            test_source.index(
                "PRELOAD_RUNNER_BINDING = preload_runner_gate("
            ),
            test_source.index("SPEC.loader.exec_module(runner)"),
        )
        for seal_key in ("rawSha256", "normalizedSha256"):
            mutated_permit = copy.deepcopy(PERMIT)
            mutated_permit["toolBindings"][
                next(
                    index
                    for index, row in enumerate(
                        mutated_permit["toolBindings"]
                    )
                    if row["path"] == RUNNER_RELATIVE_PATH
                )
            ][seal_key] = "0" * 64
            with (
                self.subTest(preload_seal=seal_key),
                self.assertRaises(RuntimeError),
            ):
                preload_runner_gate(
                    RUNNER_RAW,
                    RUNNER_SOURCE,
                    RUNNER_TREE,
                    mutated_permit,
                )
        for path, binding in bindings.items():
            with self.subTest(path=path):
                self.assertEqual(
                    sha256((ROOT / path).read_bytes()),
                    binding["rawSha256"],
                )
        self.assertEqual(
            runner.EXPECTED_CHECKER_RAW,
            bindings[CHECKER_PATH]["rawSha256"],
        )
        self.assertEqual(
            sha256(normalized_runner(RUNNER_RAW)),
            bindings[RUNNER_RELATIVE_PATH]["normalizedSha256"],
        )
        self.assertEqual(
            PERMIT["requestContract"][
                "decisionToPermitTypedProjectionCanonicalSha256"
            ],
            PROJECTION_SHA256,
        )
        self.assertEqual(
            (
                runner.CHECK.MAX_AGGREGATE_MOD_BYTES,
                runner.CHECK.MAX_AGGREGATE_ZIP_BYTES,
                runner.CHECK.MAX_AGGREGATE_BYTES,
                runner.CHECK.MAX_ALL_ZIP_FILES,
                runner.CHECK.MAX_ALL_ZIP_UNCOMPRESSED_BYTES,
            ),
            (
                2 * 1024 * 1024,
                32 * 1024 * 1024,
                34 * 1024 * 1024,
                40_000,
                256 * 1024 * 1024,
            ),
        )
        same_count_bypasses = (
            RUNNER_SOURCE.replace(
                "exec(code, module.__dict__, module.__dict__)",
                "eval(code, module.__dict__, module.__dict__)",
                1,
            ),
            RUNNER_SOURCE.replace(
                "namespace.create_claim(claim)",
                "namespace.cleanup(claim)",
                1,
            ),
            RUNNER_SOURCE.replace(
                "namespace.persist_manifest(manifest_raw)",
                "namespace.replace(manifest_raw)",
                1,
            ),
            RUNNER_SOURCE.replace(
                "raw = fetch(resource, request_deadline)",
                "raw = subprocess.run(resource, request_deadline)",
                1,
            ),
        )
        for index, changed in enumerate(same_count_bypasses):
            with self.subTest(same_count_bypass=index):
                self.assertNotEqual(changed, RUNNER_SOURCE)
                signature = surface_signature(changed)
                self.assertEqual(signature[0], EXPECTED_IMPORTS)
                self.assertEqual(signature[1], RUNNER_CALL_COUNT)
                self.assertNotEqual(
                    signature[2],
                    RUNNER_CALL_SURFACE_SHA256,
                )
                mutated_permit = copy.deepcopy(PERMIT)
                mutated_binding = next(
                    row
                    for row in mutated_permit["toolBindings"]
                    if row["path"] == RUNNER_RELATIVE_PATH
                )
                changed_raw = changed.encode()
                mutated_binding["rawSha256"] = sha256(changed_raw)
                mutated_binding["normalizedSha256"] = sha256(
                    normalized_runner(changed_raw)
                )
                with self.assertRaises(RuntimeError):
                    preload_runner_gate(
                        changed_raw,
                        changed,
                        ast.parse(changed, filename=str(RUNNER_PATH)),
                        mutated_permit,
                    )

        changed_import = RUNNER_SOURCE.replace(
            "import argparse\n",
            "import argparse\nimport socket\n",
            1,
        )
        self.assertNotEqual(changed_import, RUNNER_SOURCE)
        changed_import_raw = changed_import.encode()
        import_permit = copy.deepcopy(PERMIT)
        import_binding = next(
            row
            for row in import_permit["toolBindings"]
            if row["path"] == RUNNER_RELATIVE_PATH
        )
        import_binding["rawSha256"] = sha256(changed_import_raw)
        import_binding["normalizedSha256"] = sha256(
            normalized_runner(changed_import_raw)
        )
        with self.assertRaises(RuntimeError):
            preload_runner_gate(
                changed_import_raw,
                changed_import,
                ast.parse(changed_import, filename=str(RUNNER_PATH)),
                import_permit,
            )

    def test_02_cli_and_kernel_argv_are_exact_execute_only(self) -> None:
        runner.validate_argument_vector(["--execute"])
        for argv in (
            [],
            ["--preflight"],
            ["--exec"],
            ["--execute", "--execute"],
            ["--execute", "--extra"],
            [True],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(runner.AcquisitionError) as caught:
                    runner.validate_argument_vector(argv)
                self.assertEqual(caught.exception.code, "E_ARGUMENT")

        executable = runner.CHECK.KERNEL_EXECUTABLE_PATH
        argv = list(runner.CHECK.EXACT_KERNEL_ARGV)
        integer_bytes = runner.ctypes.sizeof(runner.ctypes.c_int)
        raw = (
            len(argv).to_bytes(
                integer_bytes,
                byteorder=runner.sys.byteorder,
                signed=True,
            )
            + executable.encode()
            + b"\0\0"
            + b"\0".join(value.encode() for value in argv)
            + b"\0ENV=value\0"
        )
        self.assertEqual(
            runner._parse_kernel_procargs2(raw),
            (executable, argv),
        )
        for malformed in (
            b"",
            (0).to_bytes(
                integer_bytes,
                byteorder=runner.sys.byteorder,
                signed=True,
            ) + b"/x\0\0",
            (2).to_bytes(
                integer_bytes,
                byteorder=runner.sys.byteorder,
                signed=True,
            ) + b"/x\0\0/x\0",
            (1).to_bytes(
                integer_bytes,
                byteorder=runner.sys.byteorder,
                signed=True,
            ) + b"\xff\0\0/x\0",
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(runner.AcquisitionError) as caught:
                    runner._parse_kernel_procargs2(malformed)
                self.assertEqual(caught.exception.code, "E_KERNEL_ARGV")

    def test_03_invocation_mismatch_precedes_preflight_and_execution(self) -> None:
        exact_python = [runner.CHECK.RUNNER_PATH, "--execute"]
        exact_kernel = (
            runner.CHECK.KERNEL_EXECUTABLE_PATH,
            list(runner.CHECK.EXACT_KERNEL_ARGV),
        )
        with (
            mock.patch.object(
                runner,
                "_read_kernel_invocation",
                return_value=exact_kernel,
            ),
            mock.patch.object(runner.sys, "argv", exact_python),
            mock.patch.object(
                runner.sys,
                "executable",
                runner.CHECK.INTERPRETER_PATH,
            ),
            mock.patch.object(runner.Path, "cwd", return_value=runner.ROOT),
            mock.patch.object(runner, "__name__", "__main__"),
            mock.patch.dict(runner.sys.modules, {"__main__": runner}),
        ):
            PRODUCTION_INVOCATION_VALIDATOR()

        cases = (
            ("imported", exact_python, exact_kernel, runner.ROOT, None),
            (
                "wrong_argv",
                [runner.CHECK.RUNNER_PATH, "--preflight"],
                exact_kernel,
                runner.ROOT,
                "__main__",
            ),
            (
                "wrong_kernel",
                exact_python,
                (exact_kernel[0], [*exact_kernel[1], "--extra"]),
                runner.ROOT,
                "__main__",
            ),
            (
                "wrong_cwd",
                exact_python,
                exact_kernel,
                runner.ROOT.parent,
                "__main__",
            ),
        )
        for label, argv, kernel, cwd, module_name in cases:
            with self.subTest(label=label), ExitStack() as stack:
                stack.enter_context(
                    mock.patch.object(
                        runner,
                        "validate_production_invocation",
                        PRODUCTION_INVOCATION_VALIDATOR,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        runner,
                        "_read_kernel_invocation",
                        return_value=kernel,
                    )
                )
                stack.enter_context(mock.patch.object(runner.sys, "argv", argv))
                stack.enter_context(
                    mock.patch.object(
                        runner.sys,
                        "executable",
                        runner.CHECK.INTERPRETER_PATH,
                    )
                )
                stack.enter_context(
                    mock.patch.object(runner.Path, "cwd", return_value=cwd)
                )
                if module_name is not None:
                    stack.enter_context(
                        mock.patch.object(runner, "__name__", module_name)
                    )
                    stack.enter_context(
                        mock.patch.dict(runner.sys.modules, {"__main__": runner})
                    )
                preflight = stack.enter_context(
                    mock.patch.object(runner, "preflight")
                )
                claim = stack.enter_context(
                    mock.patch.object(runner, "create_claim")
                )
                attempt = stack.enter_context(
                    mock.patch.object(runner, "_attempt")
                )
                fetch = mock.Mock()
                with self.assertRaises(runner.AcquisitionError):
                    runner.execute(fetch)
                preflight.assert_not_called()
                claim.assert_not_called()
                attempt.assert_not_called()
                fetch.assert_not_called()

    def test_04_live_execution_context_check_is_read_only(self) -> None:
        real_open = os.open
        opened: list[tuple[object, int]] = []
        write_flags = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_CREAT
            | os.O_TRUNC
            | os.O_APPEND
        )

        def observed_open(
            path: object,
            flags: int,
            *args: object,
            **kwargs: object,
        ) -> int:
            opened.append((path, flags))
            if flags & write_flags:
                raise AssertionError("dry context attempted a write")
            return real_open(path, flags, *args, **kwargs)

        with (
            mock.patch.object(runner.os, "open", side_effect=observed_open),
            mock.patch.object(
                runner,
                "direct_fetch",
                side_effect=AssertionError("dry context attempted fetch"),
            ),
            mock.patch.object(
                runner,
                "create_claim",
                side_effect=AssertionError("dry context attempted claim"),
            ),
            mock.patch.object(
                runner,
                "_exclusive_file",
                side_effect=AssertionError("dry context attempted write"),
            ),
        ):
            result = runner.validate_execution_context()
        self.assertEqual(result["requestCount"], 4)
        self.assertIs(result["validationPassed"], True)
        self.assertIs(result["networkUsed"], False)
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertIs(result["externalAuthenticationRequired"], False)
        self.assertIs(result["userActionRequired"], False)
        self.assertTrue(opened)
        self.assertTrue(all(flags & write_flags == 0 for _, flags in opened))

    def test_05_authority_unknown_keys_and_bool_int_aliases_fail_closed(
        self,
    ) -> None:
        permit = copy.deepcopy(PERMIT)
        self.assertTrue(runner._authority_contract_is_exact(permit))
        for section in ("authority", "filesystemAuthority"):
            extra = copy.deepcopy(permit)
            extra[section]["unknown"] = False
            self.assertFalse(runner._authority_contract_is_exact(extra))
            missing = copy.deepcopy(permit)
            missing[section].pop(next(iter(missing[section])))
            self.assertFalse(runner._authority_contract_is_exact(missing))
            for key, expected in permit[section].items():
                if type(expected) is not bool:
                    continue
                alias = copy.deepcopy(permit)
                alias[section][key] = int(expected)
                with self.subTest(section=section, key=key):
                    self.assertFalse(
                        runner._authority_contract_is_exact(alias)
                    )

    def test_06_resource_schema_and_bool_int_aliases_fail_closed(self) -> None:
        rows = exact_resource_oracle()
        permit = copy.deepcopy(PERMIT)
        self.assertEqual(
            runner._validate_resource_contract(rows, permit),
            rows,
        )

        def rejected(
            candidate: list[dict[str, object]],
            *,
            request_count: object = 4,
            stale_hash: bool = False,
        ) -> None:
            mutated = copy.deepcopy(permit)
            mutated["requestContract"]["requestCount"] = request_count
            if not stale_hash:
                mutated["requestContract"][
                    "resourcesCanonicalSha256"
                ] = runner.sha256(runner.canonical_bytes(candidate))
            with self.assertRaises(runner.AcquisitionError) as caught:
                runner._validate_resource_contract(candidate, mutated)
            self.assertEqual(caught.exception.code, "E_RESOURCES")

        for index, row in enumerate(rows):
            for key in row:
                candidate = copy.deepcopy(rows)
                candidate[index].pop(key)
                with self.subTest(index=index, missing=key):
                    rejected(candidate)
        candidate = copy.deepcopy(rows)
        candidate[0]["unknown"] = False
        rejected(candidate)
        rejected(list(reversed(copy.deepcopy(rows))))
        rejected(copy.deepcopy(rows), request_count=True)
        candidate = copy.deepcopy(rows)
        candidate[0]["expectedH1"] = candidate[1]["expectedH1"]
        rejected(candidate, stale_hash=True)
        candidate = copy.deepcopy(rows)
        candidate[2]["expectedH1"] = candidate[0]["expectedH1"]
        rejected(candidate)
        candidate = copy.deepcopy(rows)
        candidate[0], candidate[2] = candidate[2], candidate[0]
        rejected(candidate)
        for index, key in (
            (0, "requestOrdinal"),
            (0, "tupleOrder"),
            (0, "port"),
            (0, "maximumResponseBodyBytes"),
            (0, "selectedByGraphAlgorithm"),
        ):
            candidate = copy.deepcopy(rows)
            candidate[index][key] = (
                0 if key == "selectedByGraphAlgorithm" else True
            )
            with self.subTest(key=key):
                rejected(candidate)

    def test_07_immutable_ledger_exact_four_and_uncertainty_states(self) -> None:
        ledger = runner.ImmutablePhaseLedger()
        for ordinal in range(1, 5):
            raw = f"resource-{ordinal}".encode()
            ledger = ledger.begin_fetch(ordinal)
            ledger = ledger.commit_response(raw)
            ledger = ledger.begin_validation(ordinal)
            ledger = ledger.commit_validation()
            ledger = ledger.begin_persistence(ordinal)
            ledger = ledger.commit_persistence()
        success = ledger.success_fields(4)
        self.assertEqual(
            (
                success["dispatchBoundaryCount"],
                success["responseCommittedCount"],
                success["validationCommittedCount"],
                success["persistenceCommittedCount"],
            ),
            (4, 4, 4, 4),
        )
        self.assertEqual(
            success["operationCountSemantics"],
            "exact_terminal_success",
        )
        active = runner.ImmutablePhaseLedger().begin_fetch(1)
        self.assertEqual(
            active.failure_fields()["sourceAcquisitionState"],
            "unknown_after_dispatch",
        )
        self.assertEqual(active.current_resource_ordinal, 1)
        self.assertIs(active.additional_completion_uncertain, True)
        for operation in (
            lambda: runner.ImmutablePhaseLedger().begin_fetch(True),
            lambda: ledger.success_fields(True),
            lambda: runner.ImmutablePhaseLedger(
                dispatch_boundary_count=True
            ).begin_fetch(1),
        ):
            with self.assertRaises(runner.AcquisitionError):
                operation()

    def test_08_mod_zip_h1_and_archive_safety_are_in_memory_only(self) -> None:
        module = "example.test/dependency"
        version = "v1.2.3"
        mod = f"module {module}\n\ngo 1.22\n".encode()
        archive = make_zip(
            module,
            version,
            [
                ("go.mod", mod, None),
                ("source.go", b"package dependency\n", None),
            ],
        )
        self.assertEqual(
            runner.VALIDATION.validate_mod(mod, module)["goModH1"],
            runner.VALIDATION.go_mod_h1(mod),
        )
        with (
            mock.patch.object(
                zipfile.ZipFile,
                "extract",
                side_effect=AssertionError("extraction is forbidden"),
            ) as extract,
            mock.patch.object(
                zipfile.ZipFile,
                "extractall",
                side_effect=AssertionError("extraction is forbidden"),
            ) as extractall,
        ):
            verified = runner.VALIDATION.validate_zip(
                archive,
                module,
                version,
                mod,
            )
        extract.assert_not_called()
        extractall.assert_not_called()
        self.assertEqual(
            verified["moduleZipH1"],
            runner.VALIDATION.module_zip_h1(archive, module, version),
        )
        self.assertEqual(verified["entryCount"], 2)
        self.assertIs(verified["rootGoModPresent"], True)

        hostile: list[bytes] = []
        hostile.append(
            make_zip(
                module,
                version,
                [("../escape", b"x", None)],
            )
        )
        hostile.append(
            make_zip(
                "other.test/module",
                version,
                [("source.go", b"x", None)],
            )
        )
        hostile.append(
            make_zip(
                module,
                version,
                [("link", b"target", stat.S_IFLNK | 0o777)],
            )
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hostile.append(
                make_zip(
                    module,
                    version,
                    [("dup", b"a", None), ("dup", b"b", None)],
                )
            )
        hostile.append(
            make_zip(
                module,
                version,
                [("go.mod", b"module other.test/module\n", None)],
            )
        )

        encrypted = bytearray(archive)
        cursor = 0
        while True:
            cursor = encrypted.find(b"PK\x03\x04", cursor)
            if cursor < 0:
                break
            flags = int.from_bytes(encrypted[cursor + 6:cursor + 8], "little")
            encrypted[cursor + 6:cursor + 8] = (flags | 1).to_bytes(2, "little")
            cursor += 4
        cursor = 0
        while True:
            cursor = encrypted.find(b"PK\x01\x02", cursor)
            if cursor < 0:
                break
            flags = int.from_bytes(encrypted[cursor + 8:cursor + 10], "little")
            encrypted[cursor + 8:cursor + 10] = (flags | 1).to_bytes(2, "little")
            cursor += 4
        hostile.append(bytes(encrypted))

        crc_bad = bytearray(archive)
        local = crc_bad.find(b"PK\x03\x04")
        central = crc_bad.find(b"PK\x01\x02")
        self.assertGreaterEqual(local, 0)
        self.assertGreaterEqual(central, 0)
        crc = int.from_bytes(crc_bad[local + 14:local + 18], "little") ^ 1
        crc_bad[local + 14:local + 18] = crc.to_bytes(4, "little")
        crc_bad[central + 16:central + 20] = crc.to_bytes(4, "little")
        hostile.append(bytes(crc_bad))

        for index, raw in enumerate(hostile):
            parity = mod if index != 4 else mod
            with self.subTest(index=index):
                with self.assertRaises(
                    runner.VALIDATION.AcquisitionError
                ):
                    runner.VALIDATION.validate_zip(
                        raw,
                        module,
                        version,
                        parity,
                    )
        with self.assertRaises(runner.VALIDATION.AcquisitionError):
            runner.VALIDATION.validate_zip(
                archive,
                module,
                version,
                b"module other.test/module\n",
            )

        rows, bodies = fixture()
        for tuple_order in range(1, 3):
            failed_ordinal = tuple_order * 2
            for bad_root_go_mod in (
                MISSING_ROOT_GO_MOD,
                False,
                0,
                None,
            ):
                root_values: dict[int, object] = {
                    current: True for current in range(1, 3)
                }
                root_values[tuple_order] = bad_root_go_mod
                namespace = PureNamespace()
                with (
                    self.subTest(
                        tuple_order=tuple_order,
                        root_go_mod=bad_root_go_mod,
                    ),
                    synthetic_validation(
                        root_go_mod_values=root_values,
                    ),
                    self.assertRaises(
                        runner.AcquisitionError
                    ) as caught,
                ):
                    runner._attempt(
                        lambda resource, _deadline: bodies[
                            resource["requestOrdinal"]
                        ],
                        values(rows),
                        namespace,
                        whole_timeout=10,
                    )
                self.assertEqual(
                    caught.exception.code,
                    "E_ZIP_ROOT_GO_MOD",
                )
                self.assertIs(caught.exception.consumed, True)
                assert namespace.failure is not None
                failure = json.loads(namespace.failure.raw)
                self.assertEqual(
                    (
                        failure["dispatchBoundaryCount"],
                        failure["responseCommittedCount"],
                        failure["validationCommittedCount"],
                        failure["persistenceCommittedCount"],
                        failure["currentResourceOrdinal"],
                        failure["currentOperationPhase"],
                        failure["additionalCompletionUncertain"],
                    ),
                    (
                        failed_ordinal,
                        failed_ordinal,
                        failed_ordinal - 1,
                        failed_ordinal - 1,
                        failed_ordinal,
                        "validation_may_have_completed",
                        True,
                    ),
                )

        metadata_cases = (
            (
                "entryCount",
                "zip_entry_counts",
                {current: 2 for current in range(1, 3)},
                runner.CHECK.MAX_ZIP_FILES,
            ),
            (
                "uncompressedBytes",
                "zip_uncompressed_counts",
                {
                    current: len(bodies[current * 2])
                    for current in range(1, 3)
                },
                runner.CHECK.MAX_ZIP_UNCOMPRESSED_BYTES,
            ),
        )
        for (
            field_name,
            validation_keyword,
            valid_values,
            maximum,
        ) in metadata_cases:
            for tuple_order in range(1, 3):
                failed_ordinal = tuple_order * 2
                for mutation, bad_value in (
                    ("float_alias", float(valid_values[tuple_order])),
                    ("bool_alias", True),
                    ("negative", -1),
                    ("zero", 0),
                    ("over_limit", maximum + 1),
                ):
                    mutated_values = dict(valid_values)
                    mutated_values[tuple_order] = bad_value
                    namespace = PureNamespace()
                    with (
                        self.subTest(
                            zip_metadata=field_name,
                            tuple_order=tuple_order,
                            mutation=mutation,
                        ),
                        synthetic_validation(
                            **{
                                validation_keyword: mutated_values,
                            },
                        ),
                        self.assertRaises(
                            runner.AcquisitionError
                        ) as caught,
                    ):
                        runner._attempt(
                            lambda resource, _deadline: bodies[
                                resource["requestOrdinal"]
                            ],
                            values(rows),
                            namespace,
                            whole_timeout=10,
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "E_ZIP_SHAPE",
                    )
                    self.assertEqual(caught.exception.phase, "zip")
                    self.assertIs(caught.exception.consumed, True)
                    assert namespace.failure is not None
                    failure = json.loads(namespace.failure.raw)
                    self.assertEqual(
                        (
                            failure["failureCode"],
                            failure["failurePhase"],
                            failure["dispatchBoundaryCount"],
                            failure["responseCommittedCount"],
                            failure["validationCommittedCount"],
                            failure["persistenceCommittedCount"],
                            failure["currentResourceOrdinal"],
                            failure["currentOperationPhase"],
                            failure["additionalCompletionUncertain"],
                        ),
                        (
                            "E_ZIP_SHAPE",
                            "zip",
                            failed_ordinal,
                            failed_ordinal,
                            failed_ordinal - 1,
                            failed_ordinal - 1,
                            failed_ordinal,
                            "validation_may_have_completed",
                            True,
                        ),
                    )

    def test_09_hostile_proxy_statuses_and_auth_headers_are_rejected(
        self,
    ) -> None:
        resource = fixture()[0][0]
        connections: list[tuple[str, int]] = []
        requests: list[tuple[tuple[object, ...], dict[str, object]]] = []

        class Response:
            status = 302

            @staticmethod
            def getheaders() -> list[tuple[str, str]]:
                return [("Location", "https://hostile.invalid/")]

            @staticmethod
            def getheader(_name: str) -> None:
                return None

        class Connection:
            def __init__(self, host: str, port: int, **_kwargs: object) -> None:
                connections.append((host, port))

            @staticmethod
            def request(*args: object, **kwargs: object) -> None:
                requests.append((args, kwargs))

            @staticmethod
            def getresponse() -> Response:
                return Response()

            @staticmethod
            def close() -> None:
                return None

        with (
            mock.patch.object(
                runner.VALIDATION.signal,
                "getsignal",
                return_value=object(),
            ),
            mock.patch.object(
                runner.VALIDATION.signal,
                "getitimer",
                return_value=(0.0, 0.0),
            ),
            mock.patch.object(runner.VALIDATION.signal, "signal"),
            mock.patch.object(runner.VALIDATION.signal, "setitimer"),
            mock.patch.dict(
                os.environ,
                {
                    "HTTP_PROXY": "http://hostile.invalid:8080",
                    "HTTPS_PROXY": "http://hostile.invalid:8443",
                    "ALL_PROXY": "socks5://hostile.invalid:1080",
                },
                clear=False,
            ),
        ):
            for status in (302, 401, 407):
                Response.status = status
                with self.subTest(status=status):
                    with self.assertRaises(
                        runner.VALIDATION.AcquisitionError
                    ) as caught:
                        runner.VALIDATION.direct_fetch(
                            resource,
                            time.monotonic() + 5,
                            connection_factory=Connection,
                        )
                    self.assertEqual(caught.exception.code, "E_RESPONSE")
        self.assertEqual(
            connections,
            [(runner.CHECK.PROXY_HOST, 443)] * 3,
        )
        self.assertEqual(len(requests), 3)
        for args, kwargs in requests:
            serialized = repr((args, kwargs))
            self.assertNotIn("Authorization", serialized)
            self.assertNotIn("Proxy-Authorization", serialized)
            self.assertNotIn("Cookie", serialized)

    def test_10_direct_fetch_delegates_once_without_retry(self) -> None:
        resource = fixture()[0][0]
        deadline = time.monotonic() + 5
        with mock.patch.object(
            runner.WAVE4,
            "direct_fetch",
            return_value=b"response",
        ) as primitive:
            self.assertEqual(
                runner.direct_fetch(resource, deadline),
                b"response",
            )
            primitive.assert_called_once_with(resource, deadline)
        primitive_error = runner.WAVE4.AcquisitionError(
            "E_RESPONSE",
            "request_01",
        )
        with mock.patch.object(
            runner.WAVE4,
            "direct_fetch",
            side_effect=primitive_error,
        ) as primitive:
            with self.assertRaises(runner.AcquisitionError) as caught:
                runner.direct_fetch(resource, deadline)
            self.assertEqual(caught.exception.code, "E_RESPONSE")
            self.assertEqual(caught.exception.phase, "request_01")
            primitive.assert_called_once_with(resource, deadline)

    def test_11_mock_attempt_success_is_claim_first_manifest_last(self) -> None:
        rows, bodies = fixture()
        namespace = PureNamespace()
        fetches: list[int] = []

        def fetch(resource: dict[str, object], _deadline: float) -> bytes:
            self.assertIsNotNone(namespace.claim)
            self.assertIn("claim", namespace.events)
            fetches.append(resource["requestOrdinal"])
            namespace.events.append(f"fetch:{resource['requestOrdinal']}")
            return bodies[resource["requestOrdinal"]]

        with synthetic_validation():
            receipt = runner._attempt(
                fetch,
                values(rows),
                namespace,
                whole_timeout=10,
            )
        self.assertEqual(fetches, list(range(1, 5)))
        self.assertEqual(
            (
                receipt["dispatchBoundaryCount"],
                receipt["responseCommittedCount"],
                receipt["validationCommittedCount"],
                receipt["persistenceCommittedCount"],
            ),
            (4, 4, 4, 4),
        )
        self.assertEqual(receipt["modCount"], 2)
        self.assertEqual(receipt["zipCount"], 2)
        self.assertIs(receipt["sourceExtracted"], False)
        self.assertIs(receipt["sourceLoadedOrExecuted"], False)
        self.assertIs(receipt["compiled"], False)
        self.assertIs(receipt["externalAuthenticationRequired"], False)
        self.assertIs(receipt["userActionRequired"], False)
        self.assertLess(namespace.events.index("claim"), namespace.events.index("fetch:1"))
        self.assertLess(namespace.events.index("publish"), namespace.events.index("receipt"))
        self.assertLess(namespace.events.index("receipt"), namespace.events.index("manifest"))
        self.assertIsNone(namespace.failure)
        self.assertIs(
            PERMIT["oneUseContract"][
                "retryResumeBackfillOverwriteOrCleanupAllowed"
            ],
            False,
        )
        self.assertIs(
            PERMIT["filesystemAuthority"][
                "atomicNoReplacePublicationRequired"
            ],
            True,
        )

        response_limits = (
            (
                "MAX_AGGREGATE_ZIP_BYTES",
                sum(len(bodies[ordinal]) for ordinal in (2, 4)),
                "aggregateZipResponseBytes",
            ),
            (
                "MAX_AGGREGATE_BYTES",
                sum(len(raw) for raw in bodies.values()),
                "aggregateResponseBytes",
            ),
        )
        for limit_name, boundary, receipt_key in response_limits:
            boundary_namespace = PureNamespace()
            with (
                self.subTest(
                    aggregate=limit_name,
                    case="boundary",
                ),
                mock.patch.object(
                    runner.CHECK,
                    limit_name,
                    boundary,
                ),
                synthetic_validation(),
            ):
                boundary_receipt = runner._attempt(
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    values(rows),
                    boundary_namespace,
                    whole_timeout=10,
                )
            self.assertEqual(boundary_receipt[receipt_key], boundary)

            over_namespace = PureNamespace()
            with (
                self.subTest(
                    aggregate=limit_name,
                    case="over_by_one",
                ),
                mock.patch.object(
                    runner.CHECK,
                    limit_name,
                    boundary - 1,
                ),
                synthetic_validation(),
                self.assertRaises(
                    runner.AcquisitionError
                ) as caught,
            ):
                runner._attempt(
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    values(rows),
                    over_namespace,
                    whole_timeout=10,
                )
            self.assertEqual(caught.exception.code, "E_RESPONSE_SIZE")
            assert over_namespace.failure is not None
            failure = json.loads(over_namespace.failure.raw)
            self.assertEqual(
                (
                    failure["dispatchBoundaryCount"],
                    failure["responseCommittedCount"],
                    failure["validationCommittedCount"],
                    failure["persistenceCommittedCount"],
                    failure["currentResourceOrdinal"],
                    failure["currentOperationPhase"],
                    failure["additionalCompletionUncertain"],
                    failure["sourceAcquisitionState"],
                ),
                (
                    4,
                    4,
                    3,
                    3,
                    None,
                    None,
                    False,
                    "all_responses_committed",
                ),
            )

        aggregate_validation_cases = (
            (
                "entries",
                "MAX_ALL_ZIP_FILES",
                30,
                "zip_entry_counts",
                "aggregateZipEntryCount",
            ),
            (
                "uncompressed",
                "MAX_ALL_ZIP_UNCOMPRESSED_BYTES",
                300,
                "zip_uncompressed_counts",
                "aggregateZipUncompressedBytes",
            ),
        )
        for label, limit_name, boundary, keyword, receipt_key in (
            aggregate_validation_cases
        ):
            boundary_values = {
                1: boundary // 2,
                2: boundary - (boundary // 2),
            }
            boundary_namespace = PureNamespace()
            with (
                self.subTest(
                    aggregate=label,
                    case="boundary",
                ),
                mock.patch.object(
                    runner.CHECK,
                    limit_name,
                    boundary,
                ),
                synthetic_validation(
                    **{keyword: boundary_values},
                ),
            ):
                boundary_receipt = runner._attempt(
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    values(rows),
                    boundary_namespace,
                    whole_timeout=10,
                )
            self.assertEqual(boundary_receipt[receipt_key], boundary)

            over_values = dict(boundary_values)
            over_values[2] += 1
            over_namespace = PureNamespace()
            with (
                self.subTest(
                    aggregate=label,
                    case="over_by_one",
                ),
                mock.patch.object(
                    runner.CHECK,
                    limit_name,
                    boundary,
                ),
                synthetic_validation(
                    **{keyword: over_values},
                ),
                self.assertRaises(
                    runner.AcquisitionError
                ) as caught,
            ):
                runner._attempt(
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    values(rows),
                    over_namespace,
                    whole_timeout=10,
                )
            self.assertEqual(caught.exception.code, "E_ZIP_AGGREGATE")
            assert over_namespace.failure is not None
            failure = json.loads(over_namespace.failure.raw)
            self.assertEqual(
                (
                    failure["dispatchBoundaryCount"],
                    failure["responseCommittedCount"],
                    failure["validationCommittedCount"],
                    failure["persistenceCommittedCount"],
                    failure["currentResourceOrdinal"],
                    failure["currentOperationPhase"],
                    failure["additionalCompletionUncertain"],
                    failure["sourceAcquisitionState"],
                ),
                (
                    4,
                    4,
                    3,
                    3,
                    4,
                    "validation_may_have_completed",
                    True,
                    "partial_committed_with_additional_completion_uncertain",
                ),
            )

    def test_12_mock_attempt_failure_ledgers_and_uncertainty_are_exact(
        self,
    ) -> None:
        rows, bodies = fixture()
        for failed_ordinal in range(1, 5):
            namespace = PureNamespace()
            with (
                self.subTest(
                    failure_kind="h1",
                    request_ordinal=failed_ordinal,
                ),
                synthetic_validation(failed_ordinal),
                self.assertRaises(runner.AcquisitionError) as caught,
            ):
                runner._attempt(
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    values(rows),
                    namespace,
                    whole_timeout=10,
                )
            self.assertEqual(caught.exception.code, "E_H1_MISMATCH")
            self.assertIs(caught.exception.consumed, True)
            assert namespace.failure is not None
            failure = json.loads(namespace.failure.raw)
            self.assertEqual(
                (
                    failure["dispatchBoundaryCount"],
                    failure["responseCommittedCount"],
                    failure["validationCommittedCount"],
                    failure["persistenceCommittedCount"],
                ),
                (
                    failed_ordinal,
                    failed_ordinal,
                    failed_ordinal - 1,
                    failed_ordinal - 1,
                ),
            )
            self.assertEqual(
                failure["currentResourceOrdinal"],
                failed_ordinal,
            )
            self.assertEqual(
                failure["currentOperationPhase"],
                "validation_may_have_completed",
            )
            self.assertIs(
                failure["additionalCompletionUncertain"],
                True,
            )
            self.assertIs(
                failure["retryResumeOrBackfillAllowed"],
                False,
            )
            self.assertIs(failure["stagingRetained"], True)
            self.assertIsNone(namespace.receipt)
            self.assertIsNone(namespace.manifest)

        for failure_kind, expected_code, expected_phase in (
            ("write", "E_WRITE", "resource"),
            (
                "read_after_write",
                "E_PERSISTED_IDENTITY",
                "resource",
            ),
        ):
            for failed_ordinal in range(1, 5):
                namespace = FailingPersistenceNamespace(
                    failed_ordinal,
                    failure_kind,
                )
                with (
                    self.subTest(
                        failure_kind=failure_kind,
                        request_ordinal=failed_ordinal,
                    ),
                    synthetic_validation(),
                    self.assertRaises(
                        runner.AcquisitionError
                    ) as caught,
                ):
                    runner._attempt(
                        lambda resource, _deadline: bodies[
                            resource["requestOrdinal"]
                        ],
                        values(rows),
                        namespace,
                        whole_timeout=10,
                    )
                self.assertEqual(caught.exception.code, expected_code)
                self.assertEqual(caught.exception.phase, expected_phase)
                self.assertIs(caught.exception.consumed, True)
                self.assertEqual(
                    namespace.persistence_attempts,
                    failed_ordinal,
                )
                self.assertEqual(
                    len(namespace.resources),
                    (
                        failed_ordinal
                        if failure_kind == "read_after_write"
                        else failed_ordinal - 1
                    ),
                )
                assert namespace.failure is not None
                failure = json.loads(namespace.failure.raw)
                self.assertEqual(
                    failure["failureCode"],
                    expected_code,
                )
                self.assertEqual(
                    failure["failurePhase"],
                    expected_phase,
                )
                self.assertEqual(
                    (
                        failure["dispatchBoundaryCount"],
                        failure["responseCommittedCount"],
                        failure["validationCommittedCount"],
                        failure["persistenceCommittedCount"],
                        failure["currentResourceOrdinal"],
                        failure["currentOperationPhase"],
                        failure["additionalCompletionUncertain"],
                        failure["sourceAcquisitionState"],
                    ),
                    (
                        failed_ordinal,
                        failed_ordinal,
                        failed_ordinal,
                        failed_ordinal - 1,
                        failed_ordinal,
                        "persist_may_have_completed",
                        True,
                        (
                            "partial_committed_with_additional_"
                            "completion_uncertain"
                        ),
                    ),
                )
                self.assertIs(
                    failure["retryResumeOrBackfillAllowed"],
                    False,
                )
                self.assertIs(failure["claimRetained"], True)
                self.assertIs(failure["stagingRetained"], True)
                self.assertIsNone(namespace.receipt)
                self.assertIsNone(namespace.manifest)

        for failed_ordinal in range(1, 5):
            namespace = PureNamespace()

            def uncertain_fetch(
                resource: dict[str, object],
                _deadline: float,
            ) -> bytes:
                ordinal = resource["requestOrdinal"]
                if ordinal == failed_ordinal:
                    raise runner.AcquisitionError(
                        "E_NETWORK",
                        f"request_{failed_ordinal:02d}",
                    )
                return bodies[ordinal]

            with (
                self.subTest(
                    failure_kind="network",
                    request_ordinal=failed_ordinal,
                ),
                synthetic_validation(),
                self.assertRaises(runner.AcquisitionError) as caught,
            ):
                runner._attempt(
                    uncertain_fetch,
                    values(rows),
                    namespace,
                    whole_timeout=10,
                )
            self.assertEqual(caught.exception.code, "E_NETWORK")
            assert namespace.failure is not None
            failure = json.loads(namespace.failure.raw)
            self.assertEqual(
                (
                    failure["dispatchBoundaryCount"],
                    failure["responseCommittedCount"],
                    failure["validationCommittedCount"],
                    failure["persistenceCommittedCount"],
                ),
                (
                    failed_ordinal,
                    failed_ordinal - 1,
                    failed_ordinal - 1,
                    failed_ordinal - 1,
                ),
            )
            self.assertEqual(
                failure["sourceAcquisitionState"],
                (
                    "unknown_after_dispatch"
                    if failed_ordinal == 1
                    else
                    "partial_committed_with_additional_completion_uncertain"
                ),
            )
            self.assertEqual(
                failure["currentResourceOrdinal"],
                failed_ordinal,
            )
            self.assertEqual(
                failure["currentOperationPhase"],
                "fetch_may_have_completed",
            )
            self.assertIs(
                failure["additionalCompletionUncertain"],
                True,
            )

    def test_13_mock_terminal_publication_failures_are_uncertain(self) -> None:
        rows, bodies = fixture()
        post_publish = PureNamespace(fail_receipt=True)
        with (
            synthetic_validation(),
            self.assertRaises(runner.AcquisitionError) as caught,
        ):
            runner._attempt(
                lambda resource, _deadline: bodies[
                    resource["requestOrdinal"]
                ],
                values(rows),
                post_publish,
                whole_timeout=10,
            )
        self.assertEqual(caught.exception.code, "E_POST_PUBLISH_UNCERTAIN")
        self.assertIsNone(post_publish.failure)

        failure_publish = PureNamespace(fail_failure=True)
        with self.assertRaises(runner.AcquisitionError) as caught:
            runner._attempt(
                lambda _resource, _deadline: (_ for _ in ()).throw(
                    runner.AcquisitionError("E_NETWORK", "request_01")
                ),
                values(rows),
                failure_publish,
                whole_timeout=10,
            )
        self.assertEqual(
            caught.exception.code,
            "E_FAILURE_PUBLICATION_UNCERTAIN",
        )

    def test_14_process_state_guard_restores_fake_state(self) -> None:
        process = FakeProcess()
        guard = runner.ProcessStateGuard(process.operations(), set())
        handler = object()
        guard.install(handler)
        self.assertIs(process.handler, handler)
        self.assertEqual(process.umask_value, 0o077)
        errors = guard.restore()
        self.assertEqual(errors, ())
        self.assertIs(process.handler, process.original_handler)
        self.assertEqual(process.umask_value, 0o022)
        self.assertEqual(process.mask, set())
        self.assertAlmostEqual(process.timer[1], 0.25)
        for required in (
            "install_handler",
            "install_timer",
            "install_umask",
            "cancel_timer",
            "restore_handler",
            "restore_timer",
            "restore_umask",
        ):
            self.assertIn(required, process.calls)
        self.assertEqual(guard.restore(), ())

    def test_15_held_entry_rejects_hardlink_and_name_rebind(self) -> None:
        self.assertEqual(runner.RENAME_EXCL, 0x00000004)
        with tempfile.TemporaryDirectory() as temporary:
            os.mkdir(Path(temporary) / "source")
            os.mkdir(Path(temporary) / "destination")
            directory_fd = os.open(
                temporary,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
            )
            try:
                with self.assertRaises(runner.AcquisitionError) as caught:
                    runner.rename_exclusive(
                        directory_fd,
                        "source",
                        directory_fd,
                        "destination",
                        ops=runner.REAL_OPS,
                    )
                self.assertEqual(caught.exception.code, "E_FINAL_EXISTS")
                self.assertTrue((Path(temporary) / "source").is_dir())
                self.assertTrue((Path(temporary) / "destination").is_dir())
            finally:
                os.close(directory_fd)

        with tempfile.TemporaryDirectory() as temporary:
            directory_fd = os.open(
                temporary,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
            )
            try:
                real_open = os.open
                real_fsync = os.fsync
                open_calls: list[tuple[object, int, int]] = []
                fsync_calls: list[int] = []

                def observed_open(
                    path: object,
                    flags: int,
                    mode: int = 0o777,
                    **kwargs: object,
                ) -> int:
                    open_calls.append((path, flags, mode))
                    return real_open(path, flags, mode, **kwargs)

                def observed_fsync(fd: int) -> None:
                    fsync_calls.append(fd)
                    real_fsync(fd)

                with mock.patch.object(
                    runner.os,
                    "open",
                    side_effect=observed_open,
                ):
                    entry = runner._exclusive_file(
                        directory_fd,
                        "held",
                        b"original",
                        phase="test",
                        ops=runner.FileOps(fsync=observed_fsync),
                    )
                try:
                    self.assertEqual(len(open_calls), 1)
                    _, flags, mode = open_calls[0]
                    self.assertEqual(
                        flags & (os.O_CREAT | os.O_EXCL),
                        os.O_CREAT | os.O_EXCL,
                    )
                    self.assertEqual(
                        flags & getattr(os, "O_NOFOLLOW", 0),
                        getattr(os, "O_NOFOLLOW", 0),
                    )
                    self.assertEqual(mode, 0o600)
                    self.assertEqual(len(fsync_calls), 2)
                    self.assertEqual(fsync_calls[-1], directory_fd)
                    os.link(
                        "held",
                        "hardlink",
                        src_dir_fd=directory_fd,
                        dst_dir_fd=directory_fd,
                    )
                    with self.assertRaises(runner.AcquisitionError) as caught:
                        entry.identity_barrier("hardlink")
                    self.assertEqual(
                        caught.exception.code,
                        "E_PERSISTED_IDENTITY",
                    )
                finally:
                    entry.close()
            finally:
                os.close(directory_fd)

        with tempfile.TemporaryDirectory() as temporary:
            directory_fd = os.open(
                temporary,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
            )
            try:
                entry = runner._exclusive_file(
                    directory_fd,
                    "held",
                    b"original",
                    phase="test",
                    ops=runner.REAL_OPS,
                )
                try:
                    os.rename(
                        "held",
                        "displaced",
                        src_dir_fd=directory_fd,
                        dst_dir_fd=directory_fd,
                    )
                    replacement = os.open(
                        "held",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                        dir_fd=directory_fd,
                    )
                    os.write(replacement, b"replacement")
                    os.close(replacement)
                    with self.assertRaises(runner.AcquisitionError) as caught:
                        entry.identity_barrier("rebind")
                    self.assertEqual(
                        caught.exception.code,
                        "E_PERSISTED_IDENTITY",
                    )
                finally:
                    entry.close()
            finally:
                os.close(directory_fd)

        rows, bodies = fixture()
        attempt_id = "1" * 32
        claim_payload = {
            "attemptId": attempt_id,
            "status": "consumed_active",
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
        claim_raw = runner.canonical_bytes(claim_payload)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            with runner.ExecutionNamespace(root) as namespace:
                namespace.create_claim(claim_payload)
                namespace.barrier(runner.ExecutionState.CLAIMED)
                namespace.create_staging(attempt_id)
                for row in rows:
                    ordinal = row["requestOrdinal"]
                    entry = namespace.persist_resource(
                        row["acceptedFileName"],
                        bodies[ordinal],
                    )
                    self.assertEqual(
                        entry.verify_bytes(
                            f"resource_{ordinal:02d}_readback"
                        ),
                        bodies[ordinal],
                    )
                    namespace.barrier(runner.ExecutionState.STAGING)
                self.assertEqual(len(namespace.resources), 4)
                with self.assertRaises(
                    runner.AcquisitionError
                ) as replay:
                    runner.create_claim(
                        namespace.dependency_fd,
                        Path(runner.CHECK.CLAIM_PATH).name,
                        claim_payload,
                        ops=runner.REAL_OPS,
                    )
                self.assertEqual(replay.exception.code, "E_CONSUMED")
                assert namespace.claim is not None
                self.assertEqual(
                    namespace.claim.verify_bytes("claim_replay"),
                    claim_raw,
                )

            claim_path = root / runner.CHECK.CLAIM_PATH
            self.assertEqual(claim_path.read_bytes(), claim_raw)
            self.assertEqual(
                stat.S_IMODE(claim_path.stat().st_mode),
                0o600,
            )
            accepted = (
                root
                / runner.CHECK.DEPENDENCY_ROOT
                / f"{runner.CHECK.STAGING_PREFIX}{attempt_id}"
                / "accepted"
            )
            for row in rows:
                ordinal = row["requestOrdinal"]
                self.assertEqual(
                    (accepted / row["acceptedFileName"]).read_bytes(),
                    bodies[ordinal],
                )
            self.assertFalse(
                (root / runner.CHECK.FINAL_ROOT).exists()
            )

    def test_16_partial_open_failure_closes_all_owned_descriptors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            real_open = os.open
            real_close = os.close
            real_fstat = os.fstat
            opened: list[int] = []
            closed: list[int] = []
            fstat_calls = 0

            def tracked_open(*args: object, **kwargs: object) -> int:
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd

            def tracked_close(fd: int) -> None:
                closed.append(fd)
                real_close(fd)

            def failing_fstat(fd: int) -> os.stat_result:
                nonlocal fstat_calls
                fstat_calls += 1
                if fstat_calls == 2:
                    raise OSError("synthetic component fstat failure")
                return real_fstat(fd)

            with (
                mock.patch.object(runner.os, "open", side_effect=tracked_open),
                mock.patch.object(runner.os, "close", side_effect=tracked_close),
                mock.patch.object(
                    runner.os,
                    "fstat",
                    side_effect=failing_fstat,
                ),
            ):
                with self.assertRaises(runner.AcquisitionError) as caught:
                    with runner.ExecutionNamespace(root):
                        self.fail("partial directory open was accepted")
            self.assertEqual(caught.exception.code, "E_NAMESPACE")
            self.assertGreaterEqual(len(opened), 2)
            self.assertTrue(set(opened).issubset(set(closed)))
            for fd in opened:
                with self.assertRaises(OSError):
                    real_fstat(fd)

    def test_17_broken_symlink_readback_names_are_reserved(self) -> None:
        cases = (
            ("dependency", Path(runner.CHECK.READBACK_CLAIM_PATH).name),
            ("dependency", f"{runner.CHECK.READBACK_TEMP_PREFIX}broken"),
            ("docs", Path(runner.CHECK.READBACK_PATH).name),
            ("docs", Path(runner.CHECK.READBACK_MANIFEST_PATH).name),
        )
        for directory, name in cases:
            with self.subTest(directory=directory, name=name):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    prepare_root(root)
                    parent = (
                        root / runner.CHECK.DEPENDENCY_ROOT
                        if directory == "dependency"
                        else root / runner.CHECK.BASE
                    )
                    os.symlink(parent / "missing-target", parent / name)
                    with self.assertRaises(runner.AcquisitionError) as caught:
                        with runner.ExecutionNamespace(root):
                            self.fail("reserved symlink was accepted")
                    self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_18_error_documents_never_request_authentication_or_retry(
        self,
    ) -> None:
        cases = (
            ("E_CONSUMED", False, "already_consumed"),
            ("E_NETWORK", True, "consumed_failure_no_retry"),
            (
                "E_CONSUMED_TERMINAL_STATE_UNCERTAIN",
                True,
                "consumed_terminal_state_uncertain",
            ),
            (
                "E_PROCESS_STATE_RESTORE_UNCERTAIN",
                True,
                "consumed_terminal_state_uncertain",
            ),
            ("E_NETWORK", False, "failed_closed"),
        )
        for code, consumed, status in cases:
            with self.subTest(code=code, consumed=consumed):
                document = runner.error_document(
                    runner.AcquisitionError(
                        code,
                        "test",
                        consumed=consumed,
                    )
                )
                self.assertEqual(document["status"], status)
                self.assertIs(document["retryAllowed"], False)
                self.assertIs(
                    document["externalAuthenticationRequired"],
                    False,
                )
                self.assertIs(document["userActionRequired"], False)

        def string_values(value: object) -> list[str]:
            if type(value) is dict:
                result: list[str] = []
                for child in value.values():
                    result.extend(string_values(child))
                return result
            if type(value) is list:
                result = []
                for child in value:
                    result.extend(string_values(child))
                return result
            return [value] if type(value) is str else []

        predecessor_leaf = ".wave-" + "18-v1.claim"
        predecessor_path = (
            f"{runner.CHECK.DEPENDENCY_ROOT}/{predecessor_leaf}"
        )
        wave18_values = [
            value
            for value in string_values(PERMIT)
            if re.search(
                r"wave(?:-|_)?18",
                value,
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(wave18_values, [predecessor_path])
        self.assertEqual(
            PERMIT_PATH.read_bytes().count(predecessor_leaf.encode()),
            1,
        )
        self.assertIsNone(
            re.search(
                r"wave(?:-|_)?18",
                RUNNER_SOURCE,
                flags=re.IGNORECASE,
            )
        )

        package_paths = (
            PERMIT_PATH,
            ROOT / BASE
            / "bounded-dependency-source-acquisition-wave19-execution-permit-v1.md",
            ROOT / CHECKER_PATH,
            RUNNER_PATH,
            ROOT / CHECKER_TEST_PATH,
            ROOT / RUNNER_TEST_PATH,
        )
        stale_tokens = (
            ("wave" + "18PublicProxy6GetAcquisitionAuthorizedOnce").encode(),
            ("aetherlink.wave" + "18-source-acquisition").encode(),
            ("g2-pion-rung3-wave" + "18-6-resource").encode(),
            ("combinedFixedPoint" + "V16").encode(),
            ("wave17" + "NamespaceAnchor").encode(),
            ("exact_6_resource_one_use_wave" + "18").encode(),
            (
                "successRequiresNoActiveOperationAndExact"
                + "6CommittedCounts"
            ).encode(),
            (".wave-" + "18-v1-staging-").encode(),
            ("wave-" + "18-v1/accepted").encode(),
            ("wave-" + "18-v1/evidence.json").encode(),
            (".wave-" + "18-v1-readback.claim").encode(),
            (".wave-" + "18-readback-v1-").encode(),
            (
                "bounded-dependency-source-acquisition-wave" + "18-"
            ).encode(),
            ("golang.org/x/mod@" + "v0." + "24.0").encode(),
            ("golang.org/x/net@" + "v0." + "40.0").encode(),
            ("golang.org/x/sync@" + "v0." + "14.0").encode(),
            ("v0." + "24.0").encode(),
            ("v0." + "40.0").encode(),
            ("v0." + "14.0").encode(),
            ("001-" + "bb2025870bcef7a0c287").encode(),
            ("002-" + "3c84a9eecca520aed886").encode(),
            ("003-" + "4615480e24f0c4184e4c").encode(),
            ("wave" + "17PublicProxy2GetAcquisitionAuthorizedOnce").encode(),
            ("aetherlink.wave" + "17-source-acquisition").encode(),
            ("g2-pion-rung3-wave" + "17-2-resource").encode(),
            ("combinedFixedPoint" + "V15").encode(),
            ("wave16" + "NamespaceAnchor").encode(),
            ("golang.org/x/" + "tools").encode(),
            ("v0." + "33.0").encode(),
            ("8bd04e" + "a612ce").encode(),
            ("exact_2_resource_one_use_wave" + "18").encode(),
        )
        for path in package_paths:
            raw = path.read_bytes()
            for token in stale_tokens:
                with self.subTest(path=path, stale=token):
                    self.assertNotIn(token, raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
