#!/usr/bin/env python3
"""Focused offline tests for the one-use Wave17 acquisition runner."""

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
    raise RuntimeError("Wave17 runner tests require `python3 -I -B -S`")

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
    raise AssertionError("offline Wave17 tests must never create a connection")


http.client.HTTPSConnection = _deny_network
socket.create_connection = _deny_network

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT
    / "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py"
)
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py"
)
CHECKER_TEST_PATH = (
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave17_acquisition_v1.py"
)
RUNNER_RELATIVE_PATH = (
    "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py"
)
RUNNER_TEST_PATH = (
    "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave17_v1_once.py"
)
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
PERMIT_PATH = (
    ROOT
    / BASE
    / "bounded-dependency-source-acquisition-wave17-execution-permit-v1.json"
)
RESOURCE_CONTRACT_SHA256 = (
    "4920d020b6a4df4adc890a8eb2a0290e1343938483e396cc7e21447728f14686"
)
TUPLE_DIGEST = (
    "8bd04ea612cec978713135c7452cb52e20350f82cd8b2a17691e3c431b43973c"
)
MOD_H1 = "h1:CIJMaWEY88juyUfo7UbgPqbC8rU2OqfAV1h2Qp0oMYI="
ZIP_H1 = "h1:4qz2S3zmRxbGIhDIAgjxvFutSvH5EfnsYrRBj0UI0bc="

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

SPEC = importlib.util.spec_from_file_location(
    "wave17_source_acquirer_v1_test_subject",
    RUNNER_PATH,
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)
PRODUCTION_INVOCATION_VALIDATOR = runner.validate_production_invocation


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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


def normalized_runner(raw: bytes) -> bytes:
    marker = re.compile(br'EXPECTED_CHECKER_RAW = "[0-9a-f]{64}"')
    result, count = marker.subn(
        b'EXPECTED_CHECKER_RAW = "' + b"0" * 64 + b'"',
        raw,
    )
    if count != 1:
        raise AssertionError("runner normalization")
    return result


def exact_resource_oracle() -> list[dict[str, object]]:
    common = {
        "host": "proxy.golang.org",
        "method": "GET",
        "module": "golang.org/x/tools",
        "port": 443,
        "selectedByGraphAlgorithm": False,
        "tupleDigestSha256": TUPLE_DIGEST,
        "tupleId": "wave17-001-8bd04ea612ce",
        "tupleOrder": 1,
        "version": "v0.33.0",
    }
    return [
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.mod",
            "expectedH1": MOD_H1,
            "kind": "mod",
            "maximumResponseBodyBytes": 1_048_576,
            "path": "/golang.org/x/tools/@v/v0.33.0.mod",
            "requestOrdinal": 1,
            "url":
                "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.mod",
        },
        {
            **common,
            "acceptedFileName": "001-8bd04ea612cec9787131.zip",
            "expectedH1": ZIP_H1,
            "kind": "zip",
            "maximumResponseBodyBytes": 16_777_216,
            "path": "/golang.org/x/tools/@v/v0.33.0.zip",
            "requestOrdinal": 2,
            "url":
                "https://proxy.golang.org/golang.org/x/tools/@v/v0.33.0.zip",
        },
    ]


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
    module = "example.test/dependency"
    version = "v1.0.1"
    digest = runner.sha256(f"{module}\n{version}\n".encode())
    tuple_id = f"wave17-001-{digest[:12]}"
    mod = f"module {module}\n\ngo 1.22\n".encode()
    archive = make_zip(
        module,
        version,
        [
            ("go.mod", mod, None),
            ("source.go", b"package dependency\n", None),
        ],
    )
    bodies = {1: mod, 2: archive}
    rows: list[dict[str, object]] = []
    for ordinal, kind, body, maximum in (
        (1, "mod", mod, runner.CHECK.MAX_MOD_BYTES),
        (2, "zip", archive, runner.CHECK.MAX_ZIP_BYTES),
    ):
        path = f"/{module}/@v/{version}.{kind}"
        expected_h1 = (
            runner.VALIDATION.go_mod_h1(body)
            if kind == "mod"
            else runner.VALIDATION.module_zip_h1(body, module, version)
        )
        rows.append(
            {
                "acceptedFileName": f"001-{digest[:20]}.{kind}",
                "expectedH1": expected_h1,
                "host": runner.CHECK.PROXY_HOST,
                "kind": kind,
                "maximumResponseBodyBytes": maximum,
                "method": "GET",
                "module": module,
                "path": path,
                "port": 443,
                "requestOrdinal": ordinal,
                "selectedByGraphAlgorithm": False,
                "tupleDigestSha256": digest,
                "tupleId": tuple_id,
                "tupleOrder": 1,
                "url": f"https://{runner.CHECK.PROXY_HOST}{path}",
                "version": version,
            }
        )
    return rows, bodies


def values(rows: list[dict[str, object]]) -> dict[str, object]:
    permit = copy.deepcopy(PERMIT)
    permit["requestContract"]["requestCount"] = 2
    permit["requestContract"]["resources"] = rows
    permit["requestContract"]["resourcesCanonicalSha256"] = runner.sha256(
        runner.canonical_bytes(rows)
    )
    return {
        "decision": {"contentBinding": {"sha256": "d" * 64}},
        "permit": permit,
    }


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


class Wave17RunnerTests(unittest.TestCase):
    maxDiff = None

    def test_01_static_surface_bindings_and_exact_two_resources(self) -> None:
        self.assertEqual(import_surface(RUNNER_TREE), EXPECTED_IMPORTS)
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
        self.assertNotIn(
            "wave16PublicProxy6GetAcquisitionAuthorizedOnce",
            RUNNER_SOURCE,
        )
        self.assertNotIn("expected_count == 6", RUNNER_SOURCE)
        self.assertEqual(
            runner.EXPECTED_WAVE17_IDENTITY,
            ((
                "golang.org/x/tools",
                "v0.33.0",
                MOD_H1,
                ZIP_H1,
            ),),
        )
        rows = exact_resource_oracle()
        self.assertEqual(runner.CHECK.resource_contract(), rows)
        self.assertEqual(
            runner.sha256(runner.canonical_bytes(rows)),
            RESOURCE_CONTRACT_SHA256,
        )
        self.assertEqual(
            runner.EXPECTED_WAVE17_RESOURCE_CONTRACT_SHA256,
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
        self.assertEqual(result["requestCount"], 2)
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
            request_count: object = 2,
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

    def test_07_immutable_ledger_exact_two_and_uncertainty_states(self) -> None:
        ledger = runner.ImmutablePhaseLedger()
        for ordinal, raw in ((1, b"m"), (2, b"zip")):
            ledger = ledger.begin_fetch(ordinal)
            ledger = ledger.commit_response(raw)
            ledger = ledger.begin_validation(ordinal)
            ledger = ledger.commit_validation()
            ledger = ledger.begin_persistence(ordinal)
            ledger = ledger.commit_persistence()
        success = ledger.success_fields(2)
        self.assertEqual(
            (
                success["dispatchBoundaryCount"],
                success["responseCommittedCount"],
                success["validationCommittedCount"],
                success["persistenceCommittedCount"],
            ),
            (2, 2, 2, 2),
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

        receipt = runner._attempt(
            fetch,
            values(rows),
            namespace,
            whole_timeout=10,
        )
        self.assertEqual(fetches, [1, 2])
        self.assertEqual(
            (
                receipt["dispatchBoundaryCount"],
                receipt["responseCommittedCount"],
                receipt["validationCommittedCount"],
                receipt["persistenceCommittedCount"],
            ),
            (2, 2, 2, 2),
        )
        self.assertEqual(receipt["modCount"], 1)
        self.assertEqual(receipt["zipCount"], 1)
        self.assertIs(receipt["sourceExtracted"], False)
        self.assertIs(receipt["sourceLoadedOrExecuted"], False)
        self.assertIs(receipt["compiled"], False)
        self.assertIs(receipt["externalAuthenticationRequired"], False)
        self.assertIs(receipt["userActionRequired"], False)
        self.assertLess(namespace.events.index("claim"), namespace.events.index("fetch:1"))
        self.assertLess(namespace.events.index("publish"), namespace.events.index("receipt"))
        self.assertLess(namespace.events.index("receipt"), namespace.events.index("manifest"))
        self.assertIsNone(namespace.failure)

    def test_12_mock_attempt_failure_ledgers_and_uncertainty_are_exact(
        self,
    ) -> None:
        rows, bodies = fixture()
        mismatch = copy.deepcopy(rows)
        mismatch[1]["expectedH1"] = mismatch[0]["expectedH1"]
        namespace = PureNamespace()
        with self.assertRaises(runner.AcquisitionError) as caught:
            runner._attempt(
                lambda resource, _deadline: bodies[
                    resource["requestOrdinal"]
                ],
                values(mismatch),
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
            (2, 2, 1, 1),
        )
        self.assertIs(failure["retryResumeOrBackfillAllowed"], False)
        self.assertIs(failure["stagingRetained"], True)
        self.assertIsNone(namespace.receipt)
        self.assertIsNone(namespace.manifest)

        active = PureNamespace()

        def uncertain_fetch(
            _resource: object,
            _deadline: float,
        ) -> bytes:
            raise runner.AcquisitionError("E_NETWORK", "request_01")

        with self.assertRaises(runner.AcquisitionError) as caught:
            runner._attempt(
                uncertain_fetch,
                values(rows),
                active,
                whole_timeout=10,
            )
        self.assertEqual(caught.exception.code, "E_NETWORK")
        assert active.failure is not None
        failure = json.loads(active.failure.raw)
        self.assertEqual(failure["sourceAcquisitionState"], "unknown_after_dispatch")
        self.assertEqual(failure["currentResourceOrdinal"], 1)
        self.assertEqual(
            failure["currentOperationPhase"],
            "fetch_may_have_completed",
        )
        self.assertIs(failure["additionalCompletionUncertain"], True)

    def test_13_mock_terminal_publication_failures_are_uncertain(self) -> None:
        rows, bodies = fixture()
        post_publish = PureNamespace(fail_receipt=True)
        with self.assertRaises(runner.AcquisitionError) as caught:
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
