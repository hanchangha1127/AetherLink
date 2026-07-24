#!/usr/bin/env python3
"""Tests for the externally pinned, read-only Wave4 candidate checker."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True


def require_isolated_interpreter() -> None:
    flags = sys.flags
    if not (
        flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.ignore_environment == 1
        and flags.no_user_site == 1
        and flags.no_site == 1
        and flags.optimize == 0
    ):
        raise RuntimeError(
            "Wave4 candidate tests require unoptimized "
            "`python3 -I -B -S`"
        )


require_isolated_interpreter()

import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    ROOT
    / "script"
    / "check_p2p_nat_g2_pion_rung3_dependency_wave4_candidate_v1.py"
)
EXPECTED_CHECKER_RAW_SHA256 = (
    "9401a9c87f2f2e0ee563b46366c97b2fa2dcb35980a469d242be60d749f4391e"
)


def preflight_checker_source(raw: bytes) -> str:
    """Reject unsafe checker syntax before any checker byte is executed."""

    def ensure(condition, detail):
        if not condition:
            raise AssertionError(detail)

    ensure(type(raw) is bytes and bool(raw), "checker source bytes")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AssertionError("checker source utf-8") from error
    ensure(source.encode("utf-8") == raw, "checker source round trip")
    tree = ast.parse(source, filename=str(CHECKER_PATH), mode="exec")
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    def dotted_name(node):
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def enclosing_function(node):
        current = node
        while current in parents:
            current = parents[current]
            if isinstance(
                current,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                return current.name
        return None

    def string_mode(call):
        ensure(
            all(keyword.arg is not None for keyword in call.keywords),
            "open keyword expansion",
        )
        mode_nodes = [
            keyword.value
            for keyword in call.keywords
            if keyword.arg == "mode"
        ]
        if len(call.args) >= 2:
            mode_nodes.append(call.args[1])
        ensure(len(mode_nodes) <= 1, "open duplicate mode")
        if not mode_nodes:
            return "r"
        mode_node = mode_nodes[0]
        ensure(
            isinstance(mode_node, ast.Constant)
            and type(mode_node.value) is str,
            "open literal mode",
        )
        return mode_node.value

    expected_import_roots = {
        "__future__",
        "argparse",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "stat",
        "sys",
        "types",
        "typing",
    }
    expected_import_declarations = [
        (
            "from",
            "__future__",
            0,
            (("annotations", None),),
        ),
        ("import", (("sys", None),)),
        ("import", (("argparse", None),)),
        ("import", (("hashlib", None),)),
        ("import", (("json", None),)),
        ("import", (("os", None),)),
        (
            "from",
            "pathlib",
            0,
            (("Path", None),),
        ),
        ("import", (("stat", None),)),
        ("import", (("types", None),)),
        (
            "from",
            "typing",
            0,
            (
                ("Any", None),
                ("Mapping", None),
                ("Sequence", None),
            ),
        ),
    ]
    expected_os_calls = {
        "os.close",
        "os.dup",
        "os.fstat",
        "os.geteuid",
        "os.lseek",
        "os.open",
        "os.read",
        "os.stat",
    }
    expected_os_attributes = {
        "O_CLOEXEC",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_NONBLOCK",
        "O_RDONLY",
        "SEEK_SET",
        "close",
        "dup",
        "fstat",
        "geteuid",
        "lseek",
        "open",
        "read",
        "stat",
        "stat_result",
    }
    allowed_os_open_flags = {
        "O_CLOEXEC",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_NONBLOCK",
        "O_RDONLY",
    }

    def os_open_flag_names(node):
        if isinstance(node, ast.Attribute):
            ensure(
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in allowed_os_open_flags,
                "os.open flag leaf",
            )
            return {node.attr}
        ensure(
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.BitOr),
            "os.open flag grammar",
        )
        return (
            os_open_flag_names(node.left)
            | os_open_flag_names(node.right)
        )

    forbidden_imports = {
        "aiohttp",
        "asyncio",
        "cffi",
        "ctypes",
        "ftplib",
        "getpass",
        "http",
        "httpx",
        "importlib",
        "multiprocessing",
        "requests",
        "runpy",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
    }
    forbidden_mutating_attributes = {
        "chmod",
        "chown",
        "copy",
        "copy2",
        "copyfile",
        "fdopen",
        "link",
        "makedirs",
        "mkdir",
        "move",
        "remove",
        "removedirs",
        "rename",
        "renames",
        "replace",
        "rmdir",
        "rmtree",
        "symlink",
        "touch",
        "truncate",
        "unlink",
        "write_bytes",
        "write_text",
    }
    forbidden_process_attributes = {
        "fork",
        "forkpty",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "startfile",
        "system",
    }
    forbidden_network_attributes = {
        "accept",
        "bind",
        "connect",
        "connect_ex",
        "create_connection",
        "listen",
        "request",
        "send",
        "sendall",
        "sendto",
        "socket",
        "urlopen",
    }
    forbidden_named_calls = {
        "__import__",
        "breakpoint",
        "eval",
        "execfile",
        "fork",
        "forkpty",
        "input",
        "openpty",
        "popen",
        "print",
        "spawn",
        "system",
    }
    import_roots = set()
    import_declarations = []
    os_call_names = set()
    os_attributes = set()
    builtin_open_calls = []
    other_open_calls = []
    os_open_calls = []
    stdout_write_calls = []
    compile_calls = []
    exec_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_declarations.append(
                (
                    "import",
                    tuple(
                        (alias.name, alias.asname)
                        for alias in node.names
                    ),
                )
            )
            roots = {
                alias.name.split(".")[0]
                for alias in node.names
            }
            import_roots.update(roots)
            ensure(roots.isdisjoint(forbidden_imports), "forbidden import")
        if isinstance(node, ast.ImportFrom):
            import_declarations.append(
                (
                    "from",
                    node.module,
                    node.level,
                    tuple(
                        (alias.name, alias.asname)
                        for alias in node.names
                    ),
                )
            )
            root = (node.module or "").split(".")[0]
            import_roots.add(root)
            ensure(root not in forbidden_imports, "forbidden import")
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        ):
            os_attributes.add(node.attr)
        if not isinstance(node, ast.Call):
            continue
        call_name = dotted_name(node.func)
        if call_name is not None and call_name.startswith("os."):
            os_call_names.add(call_name)
        if isinstance(node.func, ast.Name):
            ensure(
                node.func.id not in forbidden_named_calls,
                "forbidden named call",
            )
            if node.func.id == "open":
                builtin_open_calls.append(node)
                ensure(
                    string_mode(node) in {"r", "rb", "br", "rt", "tr"},
                    "built-in open mode",
                )
            elif node.func.id == "compile":
                compile_calls.append(node)
            elif node.func.id == "exec":
                exec_calls.append(node)
        if isinstance(node.func, ast.Attribute):
            attribute = node.func.attr
            ensure(
                attribute not in forbidden_mutating_attributes,
                "mutating attribute",
            )
            ensure(
                attribute not in forbidden_process_attributes,
                "process attribute",
            )
            ensure(
                attribute not in forbidden_network_attributes,
                "network attribute",
            )
            ensure(
                not attribute.startswith(("spawn", "exec")),
                "process attribute prefix",
            )
            if attribute == "open":
                if call_name == "os.open":
                    os_open_calls.append(node)
                    ensure(len(node.args) == 2, "os.open positional args")
                    ensure(
                        all(
                            keyword.arg == "dir_fd"
                            for keyword in node.keywords
                        ),
                        "os.open keywords",
                    )
                    flag_names = os_open_flag_names(node.args[1])
                    ensure(
                        "O_RDONLY" in flag_names,
                        "os.open requires O_RDONLY",
                    )
                else:
                    other_open_calls.append(node)
                    ensure(
                        string_mode(node)
                        in {"r", "rb", "br", "rt", "tr"},
                        "attribute open mode",
                    )
            if attribute == "write":
                ensure(
                    call_name == "sys.stdout.buffer.write",
                    "write surface",
                )
                ensure(
                    enclosing_function(node) == "main",
                    "stdout write scope",
                )
                stdout_write_calls.append(node)

    ensure(import_roots == expected_import_roots, "import roots")
    ensure(
        import_declarations == expected_import_declarations,
        "import declarations",
    )
    ensure(os_call_names == expected_os_calls, "os call surface")
    ensure(os_attributes == expected_os_attributes, "os attribute surface")
    ensure(not builtin_open_calls, "built-in open surface")
    ensure(not other_open_calls, "attribute open surface")
    ensure(len(os_open_calls) == 3, "os.open count")
    ensure(len(stdout_write_calls) == 3, "stdout write count")
    ensure(len(compile_calls) == 1, "compile count")
    compile_call = compile_calls[0]
    ensure(
        enclosing_function(compile_call) == "load_v2_checker",
        "compile scope",
    )
    ensure(len(compile_call.args) == 3, "compile args")
    ensure(
        dotted_name(compile_call.args[0]) == "held.raw",
        "compile source",
    )
    ensure(
        isinstance(compile_call.args[1], ast.Name)
        and compile_call.args[1].id == "V2_CHECKER_PATH",
        "compile filename",
    )
    ensure(
        isinstance(compile_call.args[2], ast.Constant)
        and compile_call.args[2].value == "exec",
        "compile mode",
    )
    compile_keywords = {
        keyword.arg: keyword.value
        for keyword in compile_call.keywords
    }
    ensure(
        set(compile_keywords) == {"dont_inherit", "optimize"},
        "compile keywords",
    )
    ensure(
        isinstance(compile_keywords["dont_inherit"], ast.Constant)
        and compile_keywords["dont_inherit"].value is True,
        "compile dont_inherit",
    )
    ensure(
        isinstance(compile_keywords["optimize"], ast.Constant)
        and compile_keywords["optimize"].value == 0,
        "compile optimize",
    )
    ensure(len(exec_calls) == 1, "exec count")
    exec_call = exec_calls[0]
    ensure(
        enclosing_function(exec_call) == "load_v2_checker",
        "exec scope",
    )
    ensure(len(exec_call.args) == 3, "exec args")
    ensure(
        isinstance(exec_call.args[0], ast.Name)
        and exec_call.args[0].id == "code",
        "exec code",
    )
    ensure(
        dotted_name(exec_call.args[1]) == "module.__dict__"
        and dotted_name(exec_call.args[2]) == "module.__dict__",
        "exec namespace",
    )
    ensure(not exec_call.keywords, "exec keywords")
    ensure("--execute" not in source, "execute option")
    ensure("--record" not in source, "record option")
    ensure("input(" not in source, "interactive input")
    return source


def load_checker(preflighted_raw: bytes):
    code = compile(
        preflighted_raw,
        str(CHECKER_PATH),
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    module = types.ModuleType("wave4_candidate_tests_target")
    module.__file__ = str(CHECKER_PATH)
    exec(code, module.__dict__, module.__dict__)
    return module


CHECKER_RAW = CHECKER_PATH.read_bytes()
if hashlib.sha256(CHECKER_RAW).hexdigest() != EXPECTED_CHECKER_RAW_SHA256:
    raise AssertionError("checker raw sha256")
CHECKER_SOURCE = preflight_checker_source(CHECKER_RAW)
CHECKER = load_checker(CHECKER_RAW)

EXPECTED_AUTHORITY_KEYS = frozenset(
    {
        "acquisitionAuthorityGranted",
        "decisionAuthorityGranted",
        "dependencySourceExecutionAuthorized",
        "executionAuthorityGranted",
        "externalAuthenticationRequired",
        "fileWriteAuthorized",
        "filesystemExtractionAuthorized",
        "gitWriteAuthorized",
        "identityResolutionAuthorityGranted",
        "networkAuthorized",
        "passwordRequired",
        "privateKeyRequired",
        "publicationAuthorityGranted",
        "repositoryOwnerIdentityProofRequired",
        "signatureRequired",
        "subprocessAuthorized",
        "tokenRequired",
        "userActionRequired",
    }
)


class Wave4CandidateTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        command = [
            sys.executable,
            "-I",
            "-B",
            "-S",
            str(CHECKER_PATH),
        ]
        cls.live_runs = [
            subprocess.run(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=240,
            )
            for _ in range(2)
        ]

    def test_01_exact_external_package_pins(self):
        self.assertEqual(
            hashlib.sha256((ROOT / CHECKER.V2_CHECKER_PATH).read_bytes())
            .hexdigest(),
            CHECKER.V2_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            hashlib.sha256((ROOT / CHECKER.V2_TESTS_PATH).read_bytes())
            .hexdigest(),
            CHECKER.V2_TESTS_RAW_SHA256,
        )

    def test_02_expected_frontier_digest_and_shape(self):
        frontier = CHECKER.expected_frontier_rows()
        self.assertEqual(len(frontier), 16)
        self.assertEqual(
            sum(row["selectedByGraphAlgorithm"] for row in frontier),
            3,
        )
        self.assertEqual(
            CHECKER.sha256_bytes(CHECKER.canonical_json_bytes(frontier)),
            CHECKER.V2_FRONTIER_SHA256,
        )
        self.assertTrue(
            all(row["acquisitionAuthorized"] is False for row in frontier)
        )

    def test_03_tuple_projection_is_deterministic(self):
        first = CHECKER.wave4_rows(CHECKER.expected_frontier_rows())
        second = CHECKER.wave4_rows(CHECKER.expected_frontier_rows())
        self.assertEqual(first, second)
        self.assertEqual(
            [row["tupleOrder"] for row in first],
            list(range(1, 17)),
        )
        self.assertEqual(len({row["tupleId"] for row in first}), 16)
        self.assertEqual(
            first[0]["tupleId"],
            (
                "wave4-001-"
                + hashlib.sha256(
                    b"github.com/google/go-cmp\nv0.6.0\n"
                ).hexdigest()[:12]
            ),
        )
        self.assertTrue(
            all(
                row["acquisitionAuthorized"] is False
                and row["identityResolutionAuthorized"] is False
                and row["requiresSeparateIdentityDecision"] is True
                for row in first
            )
        )

    def test_04_semantic_mutations_fail_even_when_content_is_rebound(self):
        base_candidate = {
            "documentType": (
                "aetherlink.g2-pion-combined-wave1-wave2-wave3-"
                "fixed-point-candidate"
            ),
            "schemaVersion": "2.0",
            "status": "combined_graph_discovery_complete_next_wave_required",
            "route": "next_wave_required",
            "verificationOnly": True,
            "recordModeExposed": False,
            "inputSet": {
                "heldSourceInputCount": 101,
                "resourceCount": 100,
                "modCount": 50,
                "zipCount": 50,
                "uniqueModuleVersionTupleCount": 50,
                "aggregateRawByteSize": 73_022_054,
                "combinedInputSetSha256": CHECKER.V2_INPUT_SET_SHA256,
            },
            "graphDiscovery": {
                "newTupleCount": 16,
                "fixedPointReached": False,
                "graphNodeCount": 132,
                "graphEdgeCount": 1_047,
                "moduleNodeCount": 67,
                "moduleEdgeCount": 181,
                "nodeSetSha256": CHECKER.V2_NODE_SET_SHA256,
                "edgeSetSha256": CHECKER.V2_EDGE_SET_SHA256,
                "moduleNodeSetSha256":
                    CHECKER.V2_MODULE_NODE_SET_SHA256,
                "moduleEdgeSetSha256":
                    CHECKER.V2_MODULE_EDGE_SET_SHA256,
                "moduleGraphAndFrontierSha256":
                    CHECKER.V2_MODULE_GRAPH_AND_FRONTIER_SHA256,
                "reconstructionProjectionSha256":
                    CHECKER.V2_RECONSTRUCTION_PROJECTION_SHA256,
                "graphSha256": CHECKER.V2_GRAPH_SHA256,
                "exactFrontier": CHECKER.expected_frontier_rows(),
            },
            "coverage": {
                "archiveCount": 51,
                "aggregateEntryCount": 14_836,
                "aggregateUncompressedByteCount": 269_029_720,
                "goSourceFileCount": 11_820,
                "semanticParsedGoSourceCount": 10_953,
                "testdataSemanticExclusionCount": 867,
            },
            "authority": {
                key: False
                for key in EXPECTED_AUTHORITY_KEYS
            },
        }

        def bind(value):
            value = copy.deepcopy(value)
            body = dict(value)
            body.pop("contentBinding", None)
            value["contentBinding"] = {
                "algorithm": "sha256",
                "canonicalization":
                    "utf8_ascii_escaped_sorted_keys_compact_single_lf",
                "scope": "candidate_without_contentBinding",
                "sha256": CHECKER.sha256_bytes(
                    CHECKER.canonical_json_bytes(body)
                ),
            }
            return value

        self.assertEqual(
            frozenset(base_candidate["authority"]),
            EXPECTED_AUTHORITY_KEYS,
        )
        self.assertTrue(
            all(
                value is False
                for value in base_candidate["authority"].values()
            )
        )
        rebound_base = bind(base_candidate)
        original = CHECKER.V2_CANDIDATE_CONTENT_SHA256
        CHECKER.V2_CANDIDATE_CONTENT_SHA256 = (
            rebound_base["contentBinding"]["sha256"]
        )
        try:
            self.assertEqual(
                CHECKER.validate_v2_candidate(rebound_base),
                CHECKER.expected_frontier_rows(),
            )
        finally:
            CHECKER.V2_CANDIDATE_CONTENT_SHA256 = original

        mutations = [
            (
                "inputSet",
                "combinedInputSetSha256",
                "0" * 64,
                "E_V2_INPUT",
            ),
            (
                "graphDiscovery",
                "graphSha256",
                "0" * 64,
                "E_V2_GRAPH",
            ),
            (
                "graphDiscovery",
                "newTupleCount",
                15,
                "E_V2_GRAPH",
            ),
        ]
        for section, key, value, expected_code in mutations:
            with self.subTest(section=section, key=key):
                mutated = copy.deepcopy(base_candidate)
                mutated[section][key] = value
                mutated = bind(mutated)
                original = CHECKER.V2_CANDIDATE_CONTENT_SHA256
                CHECKER.V2_CANDIDATE_CONTENT_SHA256 = (
                    mutated["contentBinding"]["sha256"]
                )
                try:
                    with self.assertRaisesRegex(
                        CHECKER.Wave4CandidateFailure,
                        f"^{expected_code}$",
                    ):
                        CHECKER.validate_v2_candidate(mutated)
                finally:
                    CHECKER.V2_CANDIDATE_CONTENT_SHA256 = original
        mutated = copy.deepcopy(base_candidate)
        mutated["graphDiscovery"]["exactFrontier"][0]["version"] = "v0.0.0"
        mutated = bind(mutated)
        original = CHECKER.V2_CANDIDATE_CONTENT_SHA256
        CHECKER.V2_CANDIDATE_CONTENT_SHA256 = (
            mutated["contentBinding"]["sha256"]
        )
        try:
            with self.assertRaisesRegex(
                CHECKER.Wave4CandidateFailure,
                "^E_V2_FRONTIER$",
            ):
                CHECKER.validate_v2_candidate(mutated)
        finally:
            CHECKER.V2_CANDIDATE_CONTENT_SHA256 = original

    def test_05_bootstrap_pin_rejects_hash_hardlink_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "script"
            script.mkdir(mode=0o700)
            target = script / "tool.py"
            raw = b"VALUE = 1\n"
            target.write_bytes(raw)
            target.chmod(0o644)
            with self.assertRaises(CHECKER.Wave4CandidateFailure):
                CHECKER.BootstrapPinnedCodeFile(
                    root,
                    "script/tool.py",
                    "0" * 64,
                )
            linked = script / "linked.py"
            os.link(target, linked)
            with self.assertRaises(CHECKER.Wave4CandidateFailure):
                CHECKER.BootstrapPinnedCodeFile(
                    root,
                    "script/tool.py",
                    hashlib.sha256(raw).hexdigest(),
                )
            linked.unlink()
            target.rename(linked)
            target.symlink_to("linked.py")
            with self.assertRaises(OSError):
                CHECKER.BootstrapPinnedCodeFile(
                    root,
                    "script/tool.py",
                    hashlib.sha256(raw).hexdigest(),
                )

    def test_06_workspace_root_rebind_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "workspace"
            displaced = parent / "workspace-displaced"
            script = root / "script"
            script.mkdir(parents=True, mode=0o700)
            tool = script / "tool.py"
            raw = b"VALUE = 1\n"
            tool.write_bytes(raw)
            tool.chmod(0o644)
            with CHECKER.BootstrapPinnedCodeFile(
                root,
                "script/tool.py",
                hashlib.sha256(raw).hexdigest(),
            ) as held:
                root.rename(displaced)
                root.mkdir(mode=0o700)
                with self.assertRaises(CHECKER.Wave4CandidateFailure):
                    held.final_barrier()
                root.rmdir()
                displaced.rename(root)

    def test_07_live_candidate_is_exact_canonical_and_non_authorizing(self):
        completed = self.live_runs[0]
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(completed.stderr, b"")
        candidate = json.loads(completed.stdout)
        self.assertEqual(
            candidate["status"],
            (
                "exact_16_wave4_frontier_identity_candidates_"
                "prepared_without_authority"
            ),
        )
        self.assertEqual(
            candidate["sourceCandidateBinding"]["contentSha256"],
            CHECKER.V2_CANDIDATE_CONTENT_SHA256,
        )
        self.assertEqual(
            candidate["sourceCandidateBinding"][
                "exactFrontierCanonicalSha256"
            ],
            CHECKER.V2_FRONTIER_SHA256,
        )
        wave = candidate["wave"]
        self.assertEqual(wave["tupleCount"], 16)
        self.assertEqual(wave["graphSelectedTupleCount"], 3)
        self.assertEqual(
            wave["versionSpecificNonSelectedTupleCount"],
            13,
        )
        self.assertEqual(
            wave["tuples"],
            CHECKER.wave4_rows(CHECKER.expected_frontier_rows()),
        )
        authority = candidate["authority"]
        self.assertEqual(frozenset(authority), EXPECTED_AUTHORITY_KEYS)
        self.assertTrue(authority)
        self.assertTrue(all(value is False for value in authority.values()))
        counters = candidate["operationCounters"]
        self.assertEqual(counters["networkOperationCount"], 0)
        self.assertEqual(counters["fileWriteCount"], 0)
        self.assertEqual(counters["subprocessCount"], 0)
        self.assertEqual(
            completed.stdout,
            CHECKER.canonical_json_bytes(candidate),
        )
        body = dict(candidate)
        binding = body.pop("contentBinding")
        self.assertEqual(
            binding["sha256"],
            CHECKER.sha256_bytes(CHECKER.canonical_json_bytes(body)),
        )

    def test_08_live_runs_are_byte_identical(self):
        first, second = self.live_runs
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stderr, b"")
        self.assertEqual(second.stderr, b"")
        self.assertEqual(first.stdout, second.stdout)

    def test_09_static_surface_is_stdout_only_offline_and_auth_free(self):
        self.assertEqual(
            preflight_checker_source(CHECKER_RAW),
            CHECKER_SOURCE,
        )

    def test_10_cli_error_is_canonical_and_stderr_free(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(CHECKER_PATH),
                "--not-a-real-option",
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(completed.stdout, CHECKER.error_document_bytes())


if __name__ == "__main__":
    unittest.main()
