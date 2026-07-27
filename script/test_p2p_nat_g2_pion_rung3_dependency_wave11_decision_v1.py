#!/usr/bin/env python3
"""Focused adversarial tests for the read-only Wave11 decision checker."""

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
    raise RuntimeError("Wave11 decision tests require `python3 -I -B -S`")

import ast
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    "script/check_p2p_nat_g2_pion_rung3_dependency_wave11_decision_v1.py"
)
DECISION_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave11-v1.json"
)
READER_PATH = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three/"
    "bounded-dependency-source-identity-and-acquisition-decision-wave11-v1.md"
)

EXPECTED_IDENTITY_ORACLE = (
    (
        "golang.org/x/crypto",
        "v0.0.0-20190308221718-c2843e01d9a2",
        False,
        "h1:djNgcEr1/C05ACkg1iLfiJU5Ep61QUkGW8qpdssI0+w=",
        "h1:VklqNMn3ovrHsnt90PveolxSbWFaJdECFbxSq0Mqo2M=",
        1,
        15,
        1,
    ),
    (
        "golang.org/x/mod",
        "v0.27.0",
        False,
        "h1:rWI627Fq0DEoudcK+MBkNkCe0EetEaDSwJJkCcjpazc=",
        "h1:kb+q2PyFnEADO2IEF935ehFUXlWiNjJWtRNgBLSfbxQ=",
        2,
        2,
        2,
    ),
    (
        "golang.org/x/net",
        "v0.43.0",
        False,
        "h1:vhO1fvI4dGsIjh73sWfUVjj3N7CA9WkKJNQm2svM6Jg=",
        "h1:lat02VYK2j4aLzMzecihNvTlJNQUq316m2Mr9rnM6YE=",
        2,
        2,
        2,
    ),
    (
        "golang.org/x/sync",
        "v0.16.0",
        False,
        "h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=",
        "h1:ycBJEhp9p4vXvUZNszeOq0kGTPghopOL8q0fq3vstxw=",
        1,
        1,
        1,
    ),
    (
        "golang.org/x/sys",
        "v0.0.0-20190215142949-d0b11bdaac8a",
        False,
        "h1:STP8DvDyc/dI5b8T5hshtkjS+E42TnysNCUPdjciGhY=",
        "h1:1BGLXjeY4akVXGgbC9HugT3Jv3hCI0z56oJR5vAMgBU=",
        1,
        15,
        2,
    ),
    (
        "golang.org/x/sys",
        "v0.0.0-20201119102817-f84b799fce68",
        False,
        "h1:h1NjWce9XRLGQEsW7wpKNCjG9DtNlClVuFLEZdDNbEs=",
        "h1:nxC68pudNYkKU6jWhgrqdreuFiOQWj1Fs7T3VrH4Pjw=",
        2,
        16,
        2,
    ),
    (
        "golang.org/x/sys",
        "v0.35.0",
        False,
        "h1:BJP2sWEmIv4KK5OTEluFJCKSidICx8ciO85XgH3Ak8k=",
        "h1:vz1N37gP5bs89s7He8XuIYXpyY0+QlsKmzipCbUtyxI=",
        1,
        1,
        1,
    ),
    (
        "golang.org/x/telemetry",
        "v0.0.0-20250807160809-1a19826ec488",
        False,
        "h1:fGb/2+tgXXjhjHsTNdVEEMZNWA0quBnfrO+AfoDSAKw=",
        "h1:3doPGa+Gg4snce233aCWnbZVFsyFMo/dR40KK/6skyE=",
        1,
        1,
        1,
    ),
    (
        "golang.org/x/text",
        "v0.3.0",
        False,
        "h1:NqM8EUOU14njkJ3fqMW+pc6Ldnwhi/IjpwHt7yyuwOQ=",
        "h1:g61tztE5qeGQ89tm6NTjjM9VPIm088od1l6aSorWRWg=",
        1,
        15,
        1,
    ),
)


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
        ).encode("utf-8")
        + b"\n"
    )


def independent_request_oracle() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for tuple_order, identity in enumerate(
        EXPECTED_IDENTITY_ORACLE,
        1,
    ):
        module, version, selected, mod_h1, zip_h1 = identity[:5]
        tuple_digest = hashlib.sha256(
            f"{module}\n{version}\n".encode("utf-8")
        ).hexdigest()
        for kind, expected_h1, maximum in (
            ("mod", mod_h1, 1_048_576),
            ("zip", zip_h1, 16_777_216),
        ):
            result.append(
                {
                    "requestOrdinal": len(result) + 1,
                    "tupleOrder": tuple_order,
                    "module": module,
                    "version": version,
                    "selectedByGraphAlgorithm": selected,
                    "resourceKind": kind,
                    "method": "GET",
                    "host": "proxy.golang.org",
                    "url": (
                        f"https://proxy.golang.org/{module}/"
                        f"@v/{version}.{kind}"
                    ),
                    "expectedH1": expected_h1,
                    "maximumResponseBytes": maximum,
                    "acceptedFileName": (
                        f"{tuple_order:03d}-"
                        f"{tuple_digest[:20]}.{kind}"
                    ),
                    "authenticationRequired": False,
                    "networkAuthorized": False,
                    "acquisitionAuthorized": False,
                }
            )
    return result


def load_checker(raw: bytes) -> types.ModuleType:
    path = ROOT / CHECKER_PATH
    module = types.ModuleType("wave11_decision_checker_test_subject")
    module.__dict__.update(
        {
            "__cached__": None,
            "__file__": str(path),
            "__loader__": None,
            "__name__": "wave11_decision_checker_test_subject",
            "__package__": None,
        }
    )
    exec(
        compile(
            raw,
            CHECKER_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        ),
        module.__dict__,
        module.__dict__,
    )
    return module


EXPECTED_CHECKER_IMPORT_SURFACE = (
    ("from", "__future__", 0, (("annotations", None),)),
    ("import", (("sys", None),)),
    ("import", (("argparse", None),)),
    ("import", (("base64", None),)),
    ("from", "contextlib", 0, (("ExitStack", None),)),
    ("import", (("errno", None),)),
    ("import", (("hashlib", None),)),
    ("import", (("io", None),)),
    ("import", (("json", None),)),
    ("import", (("os", None),)),
    ("from", "pathlib", 0, (("Path", None),)),
    ("import", (("shlex", None),)),
    ("import", (("stat", None),)),
    ("import", (("types", None),)),
    (
        "from",
        "typing",
        0,
        (("Any", None), ("Mapping", None), ("Sequence", None)),
    ),
    ("import", (("unicodedata", None),)),
    ("import", (("zipfile", None),)),
)
EXPECTED_CHECKER_CALL_COUNT = 731
EXPECTED_CHECKER_CALL_SURFACE_SHA256 = (
    "1821fa1f1b545468ef42d8deab55cfc537d90e1ba3c1a62dad045f5d839e295e"
)
EXPECTED_CHECKER_FULL_AST_SHA256 = (
    "daf9ed7b36710a442a86b5a12e7d98ca64446d106d483f1437f8a23d5215af8f"
)
NORMALIZED_CHECKER_ASSIGNMENTS = {
    "SELF_NORMALIZED_SHA256":
        "<normalized-self-normalized-sha256>",
    "TESTS_RAW_SHA256":
        "<normalized-tests-raw-sha256>",
}
SENSITIVE_MODULE_ROOTS = {
    "asyncio",
    "builtins",
    "ctypes",
    "getpass",
    "http",
    "importlib",
    "keyring",
    "multiprocessing",
    "requests",
    "socket",
    "ssl",
    "subprocess",
    "urllib",
}
IMPORTED_MODULE_NAMES = {
    "argparse",
    "base64",
    "errno",
    "hashlib",
    "io",
    "json",
    "os",
    "shlex",
    "stat",
    "sys",
    "types",
    "unicodedata",
    "zipfile",
}
FILESYSTEM_MUTATION_CALL_ATTRIBUTES = {
    "chmod",
    "chown",
    "extract",
    "extractall",
    "hardlink_to",
    "link",
    "makedirs",
    "mkdir",
    "open",
    "remove",
    "removedirs",
    "rename",
    "renames",
    "replace",
    "rmdir",
    "symlink",
    "symlink_to",
    "touch",
    "truncate",
    "unlink",
    "write",
    "write_bytes",
    "write_text",
    "writelines",
}
PROCESS_CALL_ATTRIBUTES = {
    "fork",
    "forkpty",
    "popen",
    "posix_spawn",
    "posix_spawnp",
    "system",
}
NETWORK_CALL_ATTRIBUTES = {
    "bind",
    "connect",
    "create_connection",
    "listen",
    "send",
    "sendall",
    "sendto",
    "urlopen",
}


class StaticSurfaceFailure(AssertionError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def static_dotted_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


class StaticCallSurfaceVisitor(ast.NodeVisitor):
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

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

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


def static_import_surface(tree: ast.AST) -> tuple[object, ...]:
    rows: list[object] = []
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    for node in sorted(
        imports,
        key=lambda value: (value.lineno, value.col_offset),
    ):
        if isinstance(node, ast.Import):
            rows.append(
                (
                    "import",
                    tuple(
                        (alias.name, alias.asname)
                        for alias in node.names
                    ),
                )
            )
        else:
            rows.append(
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
    return tuple(rows)


def static_call_surface_sha256(
    call_rows: list[tuple[int, int, str, ast.Call]],
) -> str:
    projection = [
        {
            "scope": scope,
            "call": ast.dump(
                call,
                annotate_fields=True,
                include_attributes=False,
            ),
        }
        for _, _, scope, call in sorted(
            call_rows,
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
    return sha256(
        json.dumps(
            projection,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def static_full_ast_sha256(tree: ast.AST) -> str:
    normalized = copy.deepcopy(tree)
    counts = {
        name: 0
        for name in NORMALIZED_CHECKER_ASSIGNMENTS
    }
    for node in normalized.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        name = node.targets[0].id
        if name not in NORMALIZED_CHECKER_ASSIGNMENTS:
            continue
        if not (
            isinstance(node.value, ast.Constant)
            and type(node.value.value) is str
            and len(node.value.value) == 64
            and all(
                character in "0123456789abcdef"
                for character in node.value.value
            )
        ):
            raise StaticSurfaceFailure("E_FULL_AST_ALLOWLIST")
        counts[name] += 1
        node.value = ast.Constant(
            value=NORMALIZED_CHECKER_ASSIGNMENTS[name]
        )
    if any(count != 1 for count in counts.values()):
        raise StaticSurfaceFailure("E_FULL_AST_ALLOWLIST")
    return sha256(
        ast.dump(
            normalized,
            annotate_fields=True,
            include_attributes=False,
        ).encode("utf-8")
        + b"\n"
    )


def is_read_only_flag_expression(node: ast.AST) -> bool:
    allowed = {
        "O_CLOEXEC",
        "O_DIRECTORY",
        "O_NOFOLLOW",
        "O_NONBLOCK",
        "O_RDONLY",
    }
    found: list[str] = []

    def visit(value: ast.AST) -> bool:
        if isinstance(value, ast.BinOp) and isinstance(
            value.op,
            ast.BitOr,
        ):
            return visit(value.left) and visit(value.right)
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "os"
            and value.attr in allowed
        ):
            found.append(value.attr)
            return True
        return False

    return visit(node) and "O_RDONLY" in found


def assignment_values(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            names = tuple(
                target.id
                for root in targets
                for target in ast.walk(root)
                if isinstance(target, ast.Name)
                and isinstance(target.ctx, ast.Store)
            )
            yield names, node.value


def validate_checker_static_surface(source: str) -> ast.AST:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise StaticSurfaceFailure("E_STATIC_PARSE") from error
    if static_import_surface(tree) != EXPECTED_CHECKER_IMPORT_SURFACE:
        raise StaticSurfaceFailure("E_IMPORT_ALLOWLIST")

    visitor = StaticCallSurfaceVisitor()
    visitor.visit(tree)
    calls = visitor.calls
    allowed_getattr = {
        (
            "load_v9_checker",
            ast.dump(
                ast.parse(
                    "getattr(module, name, None)",
                    mode="eval",
                ).body,
                include_attributes=False,
            ),
        ),
        (
            "identity_barrier",
            ast.dump(
                ast.parse(
                    "getattr(item, 'root_fd', -1)",
                    mode="eval",
                ).body,
                include_attributes=False,
            ),
        ),
    }

    for _, _, scope, call in calls:
        dotted = static_dotted_name(call.func)
        dumped = ast.dump(call, include_attributes=False)
        if isinstance(call.func, ast.Name) and call.func.id == "getattr":
            if (scope, dumped) not in allowed_getattr:
                raise StaticSurfaceFailure("E_GETATTR_ALLOWLIST")
        if dotted in {"builtins.__import__", "__import__"}:
            raise StaticSurfaceFailure("E_DYNAMIC_IMPORT")
        if isinstance(call.func, ast.Name) and call.func.id in {
            "eval",
            "__import__",
            "input",
            "open",
        }:
            raise StaticSurfaceFailure("E_BUILTIN_CALL")
        if isinstance(call.func, ast.Name) and call.func.id in {
            "compile",
            "exec",
        }:
            if scope != "load_v9_checker":
                raise StaticSurfaceFailure("E_PINNED_CODE_CALL")
            if call.func.id == "compile":
                keywords = {
                    keyword.arg: keyword.value
                    for keyword in call.keywords
                }
                valid = (
                    len(call.args) == 3
                    and isinstance(call.args[0], ast.Attribute)
                    and isinstance(call.args[0].value, ast.Name)
                    and call.args[0].value.id == "held"
                    and call.args[0].attr == "raw"
                    and isinstance(call.args[1], ast.Name)
                    and call.args[1].id == "V9_CHECKER_PATH"
                    and isinstance(call.args[2], ast.Constant)
                    and call.args[2].value == "exec"
                    and set(keywords) == {"dont_inherit", "optimize"}
                    and ast.literal_eval(keywords["dont_inherit"]) is True
                    and ast.literal_eval(keywords["optimize"]) == 0
                )
            else:
                valid = (
                    len(call.args) == 3
                    and not call.keywords
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == "code"
                    and all(
                        isinstance(argument, ast.Attribute)
                        and isinstance(argument.value, ast.Name)
                        and argument.value.id == "module"
                        and argument.attr == "__dict__"
                        for argument in call.args[1:]
                    )
                )
            if not valid:
                raise StaticSurfaceFailure("E_PINNED_CODE_CALL")
        if dotted and dotted.split(".", 1)[0] in SENSITIVE_MODULE_ROOTS:
            raise StaticSurfaceFailure("E_FORBIDDEN_MODULE_CALL")
        if dotted and dotted.startswith("os."):
            attribute = dotted.split(".", 1)[1]
            if attribute not in {
                "close",
                "dup",
                "fstat",
                "geteuid",
                "listdir",
                "lseek",
                "open",
                "read",
                "stat",
            }:
                raise StaticSurfaceFailure("E_OS_CALL")
            if attribute == "open" and (
                len(call.args) < 2
                or not is_read_only_flag_expression(call.args[1])
            ):
                raise StaticSurfaceFailure("E_OS_OPEN_FLAGS")
        if dotted and dotted.startswith("sys."):
            if not (
                scope == "main"
                and dotted == "sys.stdout.buffer.write"
            ):
                raise StaticSurfaceFailure("E_OUTPUT_CALL")
        if isinstance(call.func, ast.Attribute):
            attribute = call.func.attr
            if attribute in PROCESS_CALL_ATTRIBUTES:
                raise StaticSurfaceFailure("E_PROCESS_CALL")
            if attribute in NETWORK_CALL_ATTRIBUTES:
                raise StaticSurfaceFailure("E_NETWORK_CALL")
            if attribute in FILESYSTEM_MUTATION_CALL_ATTRIBUTES:
                if dotted in {
                    "os.open",
                    "sys.stdout.buffer.write",
                }:
                    continue
                raise StaticSurfaceFailure("E_FILESYSTEM_CALL")

    for target_names, value in assignment_values(tree):
        dotted = static_dotted_name(value)
        if isinstance(value, ast.Name) and value.id in (
            IMPORTED_MODULE_NAMES | {"eval", "exec", "__import__"}
        ):
            raise StaticSurfaceFailure("E_SENSITIVE_ALIAS")
        if isinstance(value, ast.Attribute):
            if (target_names, dotted) == (("flags",), "sys.flags"):
                continue
            root = dotted.split(".", 1)[0] if dotted else None
            if (
                root in IMPORTED_MODULE_NAMES
                or root in SENSITIVE_MODULE_ROOTS
                or value.attr in (
                    FILESYSTEM_MUTATION_CALL_ATTRIBUTES
                    | PROCESS_CALL_ATTRIBUTES
                    | NETWORK_CALL_ATTRIBUTES
                    | {"__import__", "eval", "exec", "import_module"}
                )
            ):
                raise StaticSurfaceFailure("E_SENSITIVE_ALIAS")
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "getattr"
            and not (
                target_names == ("root_fd",)
                and ast.dump(value, include_attributes=False)
                == dict(allowed_getattr)["identity_barrier"]
            )
        ):
            raise StaticSurfaceFailure("E_GETATTR_ALLOWLIST")

    compile_count = sum(
        isinstance(call.func, ast.Name)
        and call.func.id == "compile"
        for _, _, _, call in calls
    )
    exec_count = sum(
        isinstance(call.func, ast.Name)
        and call.func.id == "exec"
        for _, _, _, call in calls
    )
    if (compile_count, exec_count) != (1, 1):
        raise StaticSurfaceFailure("E_PINNED_CODE_COUNT")
    if len(calls) != EXPECTED_CHECKER_CALL_COUNT:
        raise StaticSurfaceFailure("E_CALL_ALLOWLIST")
    if (
        static_call_surface_sha256(calls)
        != EXPECTED_CHECKER_CALL_SURFACE_SHA256
    ):
        raise StaticSurfaceFailure("E_CALL_ALLOWLIST")
    if static_full_ast_sha256(tree) != EXPECTED_CHECKER_FULL_AST_SHA256:
        raise StaticSurfaceFailure("E_FULL_AST_ALLOWLIST")
    return tree


CHECKER_SOURCE_RAW = (ROOT / CHECKER_PATH).read_bytes()
try:
    CHECKER_SOURCE = CHECKER_SOURCE_RAW.decode("utf-8")
except UnicodeDecodeError as error:
    raise StaticSurfaceFailure("E_STATIC_PARSE") from error
validate_checker_static_surface(CHECKER_SOURCE)
CHECKER = load_checker(CHECKER_SOURCE_RAW)
VALID_H1_A = "h1:" + base64.b64encode(bytes(32)).decode("ascii")
VALID_H1_B = (
    "h1:" + base64.b64encode(bytes([1]) * 32).decode("ascii")
)


class FakeRunner:
    @staticmethod
    def parse_go_mod(
        raw: bytes,
        expected_module: str,
    ) -> dict[str, object]:
        if f"module {expected_module}" not in raw.decode("utf-8"):
            raise ValueError("module mismatch")
        return {}


def minimal_witness(h1: str) -> dict[str, object]:
    return {
        "archivePath": "held.zip",
        "archiveRawSha256": "0" * 64,
        "entryPath": "module@v1.0.0/go.sum",
        "entryRawSha256": "1" * 64,
        "holderModule": "example.test/parent",
        "holderVersion": "v4.0.0",
        "holderWave": "synthetic",
        "line": 1,
        "text": f"example.test/target v1.0.0 {h1}",
        "h1": h1,
    }


class UnitBoundaryTests(unittest.TestCase):
    def test_01_static_surface_has_no_network_or_write_capability(
        self,
    ) -> None:
        raw = (ROOT / CHECKER_PATH).read_bytes()
        validate_checker_static_surface(raw.decode("utf-8"))
        source = raw.decode("utf-8")
        self.assertIn(
            "trusted_pinned_normal_reconstruction_path",
            source,
        )
        self.assertIn('"osSyscallSandboxProvided": False', source)

    def test_02_h1_validation_is_exact(self) -> None:
        self.assertTrue(CHECKER.valid_h1(VALID_H1_A))
        self.assertFalse(CHECKER.valid_h1("h1:not-base64"))
        self.assertFalse(
            CHECKER.valid_h1(
                "h1:"
                + base64.b64encode(bytes(31)).decode("ascii")
            )
        )
        self.assertFalse(CHECKER.valid_h1("sha256:" + "0" * 64))

    def test_03_declaration_capture_preserves_parent_and_line(
        self,
    ) -> None:
        raw = (
            b"module example.test/parent\n\n"
            b"require (\n"
            b"\texample.test/target v1.0.0 // indirect\n"
            b")\n"
        )
        target = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        result = CHECKER.capture_declarations(
            raw=raw,
            runner=FakeRunner,
            targets=target,
            holder_module="example.test/parent",
            holder_version="v4.0.0",
            holder_wave="synthetic",
            container_kind="external_mod",
            path="parent.mod",
            container_raw_sha256=sha256(raw),
            entry_raw_sha256=None,
        )
        rows = result[("example.test/target", "v1.0.0")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["line"], 4)
        self.assertEqual(
            rows[0]["text"],
            "\texample.test/target v1.0.0 // indirect",
        )
        self.assertEqual(
            rows[0]["holderModule"],
            "example.test/parent",
        )

    def test_04_missing_and_conflicting_h1_fail_identity(
        self,
    ) -> None:
        wave = [
            {
                "tupleOrder": 1,
                "module": "example.test/target",
                "version": "v1.0.0",
            }
        ] * CHECKER.EXPECTED_FRONTIER_COUNT
        wave = [
            {
                **row,
                "tupleOrder": order,
                "module": f"example.test/target-{order}",
                "selectedByGraphAlgorithm": order % 2 == 0,
            }
            for order, row in enumerate(wave, 1)
        ]
        targets = {
            (row["module"], row["version"]): row
            for row in wave
        }
        declarations = {
            pair: [{"path": "parent.mod", "line": 1, "text": "x"}]
            for pair in targets
        }
        zip_h1 = {
            pair: [minimal_witness(VALID_H1_A)]
            for pair in targets
        }
        mod_h1 = {
            pair: [minimal_witness(VALID_H1_A)]
            for pair in targets
        }
        first = next(iter(targets))
        zip_h1[first] = []
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertEqual(
            [row["tupleOrder"] for row in rows],
            list(range(1, CHECKER.EXPECTED_FRONTIER_COUNT + 1)),
        )
        self.assertEqual(
            [row["selectedByGraphAlgorithm"] for row in rows],
            [
                order % 2 == 0
                for order in range(
                    1,
                    CHECKER.EXPECTED_FRONTIER_COUNT + 1,
                )
            ],
        )
        self.assertFalse(rows[0]["identityPairComplete"])
        zip_h1[first] = [
            minimal_witness(VALID_H1_A),
            minimal_witness(VALID_H1_B),
        ]
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertTrue(rows[0]["moduleZipH1Conflict"])
        self.assertFalse(rows[0]["identityPairComplete"])
        zip_h1[first] = [minimal_witness(VALID_H1_A)]
        mod_h1[first] = [
            minimal_witness(VALID_H1_A),
            minimal_witness(VALID_H1_B),
        ]
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertTrue(rows[0]["goModH1Conflict"])
        declarations[first] = []
        rows = CHECKER.build_identity_rows(
            wave_rows=wave,
            declarations=declarations,
            module_zip_h1=zip_h1,
            go_mod_h1=mod_h1,
        )
        self.assertFalse(rows[0]["declarationComplete"])

    def test_05_go_sum_and_zip_shapes_fail_closed(self) -> None:
        targets = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        common = {
            "targets": targets,
            "holder_module": "example.test/parent",
            "holder_version": "v4.0.0",
            "holder_wave": "synthetic",
            "archive_path": "held.zip",
            "archive_raw_sha256": "0" * 64,
            "entry_path": "parent@v4.0.0/go.sum",
        }
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.parse_go_sum_entry(
                raw=b"example.test/target v1.0.0 bad\n",
                **common,
            )
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.parse_go_sum_entry(raw=b"\xff\n", **common)
        duplicate = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("module@v1.0.0/go.sum", b"")
                archive.writestr("module@v1.0.0/go.sum", b"")
        duplicate.seek(0)
        with zipfile.ZipFile(duplicate, "r") as archive:
            with self.assertRaises(CHECKER.DecisionFailure):
                CHECKER.validate_archive_names(archive.infolist())
        with self.assertRaises(CHECKER.DecisionFailure):
            CHECKER.validate_archive_names(
                [zipfile.ZipInfo("../go.sum")]
            )

    def test_06_self_normalization_rejects_ambiguous_marker(
        self,
    ) -> None:
        raw = (ROOT / CHECKER_PATH).read_bytes()
        normalized = CHECKER.normalized_self_bytes(raw)
        self.assertEqual(
            sha256(normalized),
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        marker = b'SELF_NORMALIZED_SHA256 = (\n    "'
        with self.assertRaises(CHECKER.DecisionFailure) as caught:
            CHECKER.normalized_self_bytes(raw + marker + b"0" * 64 + b'"\n)')
        self.assertEqual(caught.exception.code, "E_SELF_IDENTITY")

    def test_07_frontier_and_request_order_are_exact(self) -> None:
        frontier = CHECKER.expected_frontier()
        self.assertEqual(
            len(frontier),
            CHECKER.EXPECTED_FRONTIER_COUNT,
        )
        self.assertEqual(
            sha256(canonical(frontier)),
            CHECKER.V9_FRONTIER_SHA256,
        )
        self.assertNotEqual(
            CHECKER.V9_INPUT_SET_SHA256,
            CHECKER.V9_SOURCE_BINDINGS_SHA256,
        )
        self.assertEqual(
            len(CHECKER.EXPECTED_IDENTITY),
            CHECKER.EXPECTED_FRONTIER_COUNT,
        )
        self.assertEqual(
            tuple(CHECKER.EXPECTED_IDENTITY),
            EXPECTED_IDENTITY_ORACLE,
        )
        rows = [
            {
                "tupleOrder": order,
                "module": value[0],
                "version": value[1],
                "selectedByGraphAlgorithm": value[2],
                "goModH1Values": [value[3]],
                "moduleZipH1Values": [value[4]],
            }
            for order, value in enumerate(
                CHECKER.EXPECTED_IDENTITY,
                1,
            )
        ]
        requests = CHECKER.request_set(rows)
        self.assertEqual(requests, independent_request_oracle())
        self.assertEqual(
            sha256(CHECKER.digest_json_bytes(requests)),
            "bbde21b5f7a523bb6cddf78fbbbfdce46f8bcf61d60ebcec72a80d52dda50ba8",
        )

    def test_07b_request_set_preserves_all_false_graph_facts(self) -> None:
        rows = [
            {
                "tupleOrder": order,
                "module": value[0],
                "version": value[1],
                "selectedByGraphAlgorithm": value[2],
                "goModH1Values": [value[3]],
                "moduleZipH1Values": [value[4]],
            }
            for order, value in enumerate(EXPECTED_IDENTITY_ORACLE, 1)
        ]
        requests = CHECKER.request_set(rows)
        self.assertEqual(len(requests), 18)
        self.assertTrue(
            all(
                row["selectedByGraphAlgorithm"] is False
                for row in requests
            )
        )
        self.assertTrue(
            all(
                row["authenticationRequired"] is False
                and row["networkAuthorized"] is False
                and row["acquisitionAuthorized"] is False
                for row in requests
            )
        )

    def test_08_wave9_duplicate_mod_boundary_fails_closed(self) -> None:
        rows = [
            {
                "kind": "mod",
                "tupleOrder": 131,
                "wave": "wave9",
                "module": "example.test/shared",
                "version": "v1.0.0",
                "rawSha256": "a" * 64,
                "path": "first.mod",
                "tupleId": "first",
            },
            {
                "kind": "mod",
                "tupleOrder": 132,
                "wave": "wave9",
                "module": "example.test/shared",
                "version": "v1.1.0",
                "rawSha256": "a" * 64,
                "path": "second.mod",
                "tupleId": "second",
            },
        ]
        CHECKER.validate_wave9_duplicate_mod_boundary(rows)
        mutations = (
            lambda value: value[1].__setitem__("rawSha256", "b" * 64),
            lambda value: value[1].__setitem__("path", "first.mod"),
            lambda value: value[1].__setitem__("tupleId", "first"),
            lambda value: value[1].__setitem__("version", "v1.0.0"),
            lambda value: value[1].__setitem__(
                "module",
                "example.test/other",
            ),
            lambda value: value[1].__setitem__("wave", "wave8"),
            lambda value: value[1].__setitem__("tupleOrder", 133),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(rows)
                mutate(changed)
                with self.assertRaises(
                    CHECKER.DecisionFailure,
                ) as caught:
                    CHECKER.validate_wave9_duplicate_mod_boundary(changed)
                self.assertEqual(
                    caught.exception.code,
                    "E_WAVE9_DUPLICATE_MOD",
                )


class HardeningBoundaryTests(unittest.TestCase):
    def test_static_bypasses_fail_strict_allowlist(self) -> None:
        source = (ROOT / CHECKER_PATH).read_text()
        validate_checker_static_surface(source)
        mutations = (
            (
                "from_os_system",
                "from os import system\nsystem('x')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "from_os_remove_alias",
                "from os import remove as cleanup\ncleanup('x')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "import_os_alias",
                "import os as operating_system\n"
                "operating_system.system('x')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "import_subprocess_alias",
                "import subprocess as process\nprocess.run(['x'])\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "from_builtins_eval",
                "from builtins import eval as evaluator\n"
                "evaluator('1 + 1')\n",
                "E_IMPORT_ALLOWLIST",
            ),
            (
                "literal_getattr",
                "getattr(os, 'system')('x')\n",
                "E_GETATTR_ALLOWLIST",
            ),
            (
                "dynamic_getattr",
                "dynamic_name = 'system'\n"
                "getattr(os, dynamic_name)('x')\n",
                "E_GETATTR_ALLOWLIST",
            ),
            (
                "non_allowlisted_getattr",
                "getattr(module, name)()\n",
                "E_GETATTR_ALLOWLIST",
            ),
            (
                "builtins_import",
                "builtins.__import__('socket')\n",
                "E_DYNAMIC_IMPORT",
            ),
            (
                "import_alias",
                "loader = __import__\nloader('socket')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "eval_alias",
                "evaluator = eval\nevaluator('1 + 1')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "exec_alias",
                "executor = exec\nexecutor('pass')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "importlib_alias",
                "loader = importlib.import_module\nloader('socket')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "ctypes_alias",
                "loader = ctypes.CDLL\nloader('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "subprocess_alias",
                "process = subprocess.run\nprocess(['x'])\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "socket_alias",
                "connector = socket.socket\nconnector()\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "network_alias",
                "request = requests.get\n"
                "request('https://invalid')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "process_alias",
                "process = os.system\nprocess('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "filesystem_alias",
                "cleanup = os.remove\ncleanup('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "path_write_alias",
                "writer = Path('/tmp/x').write_text\nwriter('x')\n",
                "E_SENSITIVE_ALIAS",
            ),
            (
                "direct_process",
                "os.system('x')\n",
                "E_OS_CALL",
            ),
            (
                "direct_filesystem",
                "os.remove('x')\n",
                "E_OS_CALL",
            ),
            (
                "path_unlink",
                "Path('/tmp/x').unlink()\n",
                "E_FILESYSTEM_CALL",
            ),
            (
                "output_write",
                "sys.stdout.buffer.write(b'x')\n",
                "E_OUTPUT_CALL",
            ),
            (
                "write_open_flag",
                "os.open('x', os.O_WRONLY)\n",
                "E_OS_OPEN_FLAGS",
            ),
            (
                "numeric_write_open_flag",
                "os.open('x', 1)\n",
                "E_OS_OPEN_FLAGS",
            ),
            (
                "builtin_open",
                "open('x', 'w')\n",
                "E_BUILTIN_CALL",
            ),
            (
                "unscoped_exec",
                "exec('pass')\n",
                "E_PINNED_CODE_CALL",
            ),
            (
                "unscoped_compile",
                "compile(b'pass', 'x', 'exec')\n",
                "E_PINNED_CODE_CALL",
            ),
            (
                "otherwise_safe_extra_call",
                "len([])\n",
                "E_CALL_ALLOWLIST",
            ),
            (
                "environment_read",
                "os.getenv('TOKEN')\n",
                "E_OS_CALL",
            ),
            (
                "getpass_read",
                "getpass.getpass()\n",
                "E_FORBIDDEN_MODULE_CALL",
            ),
            (
                "keyring_read",
                "keyring.get_password('x', 'y')\n",
                "E_FORBIDDEN_MODULE_CALL",
            ),
        )
        for name, suffix, expected_code in mutations:
            with (
                self.subTest(mutation=name),
                self.assertRaises(StaticSurfaceFailure) as caught,
            ):
                validate_checker_static_surface(f"{source}\n{suffix}")
            self.assertEqual(caught.exception.code, expected_code)

        def mutate_held_raw(value: str) -> str:
            changed = value.replace(
                "    try:\n"
                "        code = compile(\n",
                "    try:\n"
                "        original_raw = held.raw\n"
                "        held.raw = b\"pass\\n\"\n"
                "        code = compile(\n",
                1,
            )
            return changed.replace(
                "        exec(code, module.__dict__, module.__dict__)\n",
                "        held.raw = original_raw\n"
                "        exec(code, module.__dict__, module.__dict__)\n",
                1,
            )

        def mutate_summary_environment_read(value: str) -> str:
            return value.replace(
                "        sys.stdout.buffer.write(\n"
                "            canonical_json_bytes(\n"
                "                expected if args.print_expected else summary\n",
                "        summary[\"leak\"] = os.environ[\"TOKEN\"]\n"
                "        sys.stdout.buffer.write(\n"
                "            canonical_json_bytes(\n"
                "                expected if args.print_expected else summary\n",
                1,
            )

        baseline_tree = ast.parse(source)
        baseline_calls = StaticCallSurfaceVisitor()
        baseline_calls.visit(baseline_tree)
        for name, mutate in (
            ("held_raw_save_modify_restore", mutate_held_raw),
            (
                "summary_environment_subscript",
                mutate_summary_environment_read,
            ),
        ):
            changed = mutate(source)
            self.assertTrue(changed != source, name)
            changed_tree = ast.parse(changed)
            changed_calls = StaticCallSurfaceVisitor()
            changed_calls.visit(changed_tree)
            self.assertEqual(
                len(changed_calls.calls),
                len(baseline_calls.calls),
            )
            self.assertEqual(
                static_call_surface_sha256(changed_calls.calls),
                static_call_surface_sha256(baseline_calls.calls),
            )
            with (
                self.subTest(mutation=name),
                self.assertRaises(StaticSurfaceFailure) as caught,
            ):
                validate_checker_static_surface(changed)
            self.assertEqual(
                caught.exception.code,
                "E_FULL_AST_ALLOWLIST",
            )

    def test_main_failure_documents_are_canonical(self) -> None:
        for raised, code in (
            (CHECKER.DecisionFailure("E_SYNTHETIC"), "E_SYNTHETIC"),
            (RuntimeError("sensitive details"), "E_INTERNAL"),
        ):
            stdout = types.SimpleNamespace(buffer=io.BytesIO())
            with (
                mock.patch.object(
                    CHECKER,
                    "evaluate",
                    side_effect=raised,
                ),
                mock.patch.object(CHECKER.sys, "stdout", stdout),
            ):
                returncode = CHECKER.main([])
            self.assertEqual(returncode, 1)
            self.assertEqual(
                stdout.buffer.getvalue(),
                canonical(CHECKER.error_document(code)),
            )

    def test_bootstrap_alias_and_close_retry_fail_closed(self) -> None:
        alias = types.SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600,
            st_nlink=2,
            st_uid=CHECKER.os.geteuid(),
            st_size=1,
        )
        with self.assertRaises(CHECKER.DecisionFailure) as caught:
            CHECKER.BootstrapPinnedCodeFile._validate_file(alias)
        self.assertEqual(caught.exception.code, "E_TOOL_IDENTITY")

        pinned = object.__new__(CHECKER.BootstrapPinnedCodeFile)
        pinned.owned_fds = [10, 11]
        pinned.directories = []
        pinned.fd = 11
        pinned.parent_fd = 10
        pinned.root_fd = 10
        failed = False

        def close_once(fd: int) -> None:
            nonlocal failed
            if fd == 10 and not failed:
                failed = True
                raise OSError(5, "synthetic")

        with (
            mock.patch.object(
                CHECKER.os,
                "close",
                side_effect=close_once,
            ),
            mock.patch.object(
                CHECKER.os,
                "fstat",
                return_value=alias,
            ),
        ):
            with self.assertRaises(OSError):
                pinned.close()
        self.assertEqual(pinned.owned_fds, [10])
        with mock.patch.object(CHECKER.os, "close", return_value=None):
            pinned.close()
        self.assertEqual(pinned.owned_fds, [])

    def test_wave11_namespace_rejects_stale_and_portable_aliases(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency = root / "dependencies"
            docs = root / "docs"
            scripts = root / "script"
            dependency.mkdir()
            docs.mkdir()
            scripts.mkdir()
            (docs / Path(CHECKER.DECISION_PATH).name).touch()
            (docs / Path(CHECKER.READER_PATH).name).touch()
            (scripts / Path(CHECKER.SELF_PATH).name).touch()
            (scripts / Path(CHECKER.TESTS_PATH).name).touch()
            fds = [
                os.open(path, os.O_RDONLY | os.O_DIRECTORY)
                for path in (dependency, docs, scripts)
            ]
            try:
                CHECKER.validate_wave11_namespace_absent(*fds)
                cases = (
                    (dependency, ".WAVE-11-v1.claim"),
                    (
                        docs,
                        "bounded-dependency-source-acquisition-"
                        "wave11-execution-permit-v1.json",
                    ),
                    (
                        scripts,
                        "check_p2p_nat_g2_pion_rung3_dependency_"
                        "wave11_acquisition_v1.py",
                    ),
                )
                for parent, name in cases:
                    path = parent / name
                    path.touch()
                    try:
                        with self.assertRaises(
                            CHECKER.DecisionFailure,
                        ) as caught:
                            CHECKER.validate_wave11_namespace_absent(*fds)
                        self.assertEqual(
                            caught.exception.code,
                            "E_WAVE11_NAMESPACE",
                        )
                    finally:
                        path.unlink()
            finally:
                for fd in reversed(fds):
                    os.close(fd)
        with mock.patch.object(
            CHECKER.os,
            "listdir",
            side_effect=[
                [],
                [Path(CHECKER.DECISION_PATH).name.upper()],
                [
                    Path(CHECKER.SELF_PATH).name,
                    Path(CHECKER.TESTS_PATH).name,
                ],
            ],
        ):
            with self.assertRaises(
                CHECKER.DecisionFailure,
            ) as caught:
                CHECKER.validate_wave11_namespace_absent(1, 2, 3)
        self.assertEqual(caught.exception.code, "E_WAVE11_NAMESPACE")


class LiveRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package_raw = {
            CHECKER.SELF_PATH:
                (ROOT / CHECKER.SELF_PATH).read_bytes(),
            CHECKER.TESTS_PATH:
                (ROOT / CHECKER.TESTS_PATH).read_bytes(),
            CHECKER.READER_PATH:
                (ROOT / CHECKER.READER_PATH).read_bytes(),
            CHECKER.V9_CHECKER_PATH:
                (ROOT / CHECKER.V9_CHECKER_PATH).read_bytes(),
            CHECKER.V9_TESTS_PATH:
                (ROOT / CHECKER.V9_TESTS_PATH).read_bytes(),
        }
        cls.expected, _ = CHECKER.evaluate(
            ROOT,
            verify_disk=False,
        )
        cls.generated_raw = canonical(cls.expected)

    def mutated_failure(self, mutate, code: str) -> None:
        value = copy.deepcopy(self.expected)
        mutate(value)
        value.pop("contentBinding", None)
        value = CHECKER.content_bound(value)
        with self.assertRaises(
            CHECKER.DecisionFailure,
        ) as caught:
            CHECKER.validate_semantic_decision(
                value,
                self.package_raw,
            )
        self.assertEqual(caught.exception.code, code)

    def test_08_self_reader_tests_and_v9_pins(self) -> None:
        self.assertEqual(
            sha256(
                CHECKER.normalized_self_bytes(
                    self.package_raw[CHECKER.SELF_PATH]
                )
            ),
            CHECKER.SELF_NORMALIZED_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.TESTS_PATH]),
            CHECKER.TESTS_RAW_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.READER_PATH]),
            CHECKER.READER_RAW_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.V9_CHECKER_PATH]),
            CHECKER.V9_CHECKER_RAW_SHA256,
        )
        self.assertEqual(
            sha256(self.package_raw[CHECKER.V9_TESTS_PATH]),
            CHECKER.V9_TESTS_RAW_SHA256,
        )

    def test_09_materialized_decision_is_exact_canonical_output(
        self,
    ) -> None:
        decision_raw = (ROOT / DECISION_PATH).read_bytes()
        self.assertEqual(decision_raw, self.generated_raw)
        self.assertEqual(decision_raw, canonical(self.expected))
        with mock.patch.object(
            CHECKER,
            "identity_barrier",
            wraps=CHECKER.identity_barrier,
        ) as identity_barrier:
            validated = CHECKER.validate_materialized_decision_path(
                ROOT,
                self.expected,
                self.package_raw,
            )
        self.assertEqual(validated, self.expected)
        self.assertEqual(identity_barrier.call_count, 2)
        identity = self.expected["identityResolution"]
        self.assertEqual(
            (
                identity["tupleCount"],
                identity["graphSelectedTupleCount"],
                identity["versionSpecificNonSelectedTupleCount"],
                identity["parentDeclarationCount"],
                identity["goModH1WitnessCount"],
                identity["moduleZipH1WitnessCount"],
                identity["completeIdentityPairCount"],
                identity["blockedTupleCount"],
                identity["conflictingIdentityCount"],
            ),
            (
                CHECKER.EXPECTED_FRONTIER_COUNT,
                CHECKER.EXPECTED_GRAPH_SELECTED_TUPLE_COUNT,
                (
                    CHECKER.EXPECTED_FRONTIER_COUNT
                    - CHECKER.EXPECTED_GRAPH_SELECTED_TUPLE_COUNT
                ),
                CHECKER.EXPECTED_PARENT_DECLARATION_COUNT,
                CHECKER.EXPECTED_GO_MOD_H1_WITNESS_COUNT,
                CHECKER.EXPECTED_MODULE_ZIP_H1_WITNESS_COUNT,
                CHECKER.EXPECTED_FRONTIER_COUNT,
                0,
                0,
            ),
        )
        self.assertEqual(
            identity["compactIdentitySha256"],
            CHECKER.COMPACT_IDENTITY_SHA256,
        )
        self.assertEqual(
            identity["fullWitnessSha256"],
            CHECKER.FULL_WITNESS_SHA256,
        )
        self.assertEqual(
            sum(
                row["selectedByGraphAlgorithm"]
                for row in identity["tuples"]
            ),
            CHECKER.EXPECTED_GRAPH_SELECTED_TUPLE_COUNT,
        )
        self.assertEqual(
            self.expected["sourceAcquisitionPreparation"][
                "requestSet"
            ],
            independent_request_oracle(),
        )

    def test_10_authority_scope_and_counters_are_closed(self) -> None:
        authority = self.expected["authority"]
        self.assertEqual(
            set(authority),
            set(CHECKER.EXPECTED_DECISION_AUTHORITY),
        )
        self.assertTrue(
            authority and all(value is False for value in authority.values())
        )
        lineage = self.expected["predecessorBindings"][
            "combinedFixedPointV9"
        ]
        self.assertEqual(
            lineage,
            {
                "checkerPath": CHECKER.V9_CHECKER_PATH,
                "checkerRawSha256": CHECKER.V9_CHECKER_RAW_SHA256,
                "checkerNormalizedSha256":
                    CHECKER.V9_CHECKER_NORMALIZED_SHA256,
                "testsPath": CHECKER.V9_TESTS_PATH,
                "testsRawSha256": CHECKER.V9_TESTS_RAW_SHA256,
                "contentSha256":
                    CHECKER.V9_CANDIDATE_CONTENT_SHA256,
                "combinedInputSetSha256": CHECKER.V9_INPUT_SET_SHA256,
                "sourceBindingsSha256":
                    CHECKER.V9_SOURCE_BINDINGS_SHA256,
                "graphSha256": CHECKER.V9_GRAPH_SHA256,
                "frontierSha256": CHECKER.V9_FRONTIER_SHA256,
                "fixedPointReached": False,
                "frontierTupleCount": CHECKER.EXPECTED_FRONTIER_COUNT,
                "totalFullSourceReconstructionCount": 16,
                "totalGraphArchiveOpenCount": 1666,
                "providerFacadeVerificationScope":
                    "trusted_pinned_normal_reconstruction_path",
                "trustedPinnedNormalPathFileWriteCount": 0,
                "osSyscallSandboxProvided": False,
                "v8TestsBindingScope":
                    "historical_metadata_only_not_live_held",
                "v8TestsLiveHeld": False,
                "wave9LegacyBuildCompatibilityPolicy": {
                    "configuredProfileInclusionEquivalent": True,
                    "directReconstructionApplicationCount": 4,
                    "expectedExpression":
                        "((go1.8 && !go1.9)) && ((!windows))",
                    "fallbackErrorCode": "E_BUILD_CONSTRAINT",
                    "fallbackErrorPhase": "source_inventory",
                    "go111TrailingWordOrSemanticsChecked": True,
                    "normalizedSourceSha256":
                        "a46760412870548bd5bf6cfb011129769545623276e3b0385f85deb3206045f2",
                    "originalLineOccurrenceCount": 1,
                    "originalProviderParserTriedFirst": True,
                    "rawSourceSha256":
                        "042948d42899becd3c158c680d9c491ca9a57629cc893edea31ef2aae2666443",
                    "sourceBytesModified": False,
                },
                "wave9PinnedLegacyBuildCompatibilityCount": 4,
                "retainedSnapshotBoundary": {
                    "historicalExact40FrozenSnapshotDescriptorSetBound":
                        True,
                    "liveTerminalControlMetadataVerifiedAtCombinedV9Barrier":
                        True,
                    "liveFinalAndAcceptedInventoriesVerifiedAtCombinedV9Barrier":
                        True,
                    "finalNamespaceReverifiedAfterCombinedV9Reconstruction":
                        True,
                    "retainedFdPreManifestBarrierCount": 3,
                    "completionAppliesToRetainedSnapshot": True,
                    "currentPathIdentityGuaranteedThroughManifestPublication":
                        False,
                    "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented":
                        False,
                },
            },
        )
        self.assertEqual(
            lineage["providerFacadeVerificationScope"],
            "trusted_pinned_normal_reconstruction_path",
        )
        self.assertFalse(lineage["osSyscallSandboxProvided"])
        self.assertEqual(
            (
                lineage["checkerRawSha256"],
                lineage["checkerNormalizedSha256"],
                lineage["testsRawSha256"],
                lineage["contentSha256"],
                lineage["combinedInputSetSha256"],
                lineage["sourceBindingsSha256"],
                lineage["graphSha256"],
                lineage["frontierSha256"],
                lineage["frontierTupleCount"],
            ),
            (
                CHECKER.V9_CHECKER_RAW_SHA256,
                CHECKER.V9_CHECKER_NORMALIZED_SHA256,
                CHECKER.V9_TESTS_RAW_SHA256,
                CHECKER.V9_CANDIDATE_CONTENT_SHA256,
                CHECKER.V9_INPUT_SET_SHA256,
                CHECKER.V9_SOURCE_BINDINGS_SHA256,
                CHECKER.V9_GRAPH_SHA256,
                CHECKER.V9_FRONTIER_SHA256,
                CHECKER.EXPECTED_FRONTIER_COUNT,
            ),
        )
        self.assertEqual(
            (
                lineage["totalFullSourceReconstructionCount"],
                lineage["totalGraphArchiveOpenCount"],
                lineage["trustedPinnedNormalPathFileWriteCount"],
            ),
            (16, 1666, 0),
        )
        counters = self.expected["operationCounters"]
        self.assertEqual(
            (
                counters["identityWitnessScanCount"],
                counters["identityWitnessArchiveOpenCount"],
                counters["overallDecisionExecutionArchiveOpenCount"],
                counters["descriptorIdentityBarrierCount"],
                counters["namespaceSnapshotCount"],
                counters["dependencySourceLoadCount"],
                counters["dependencySourceCompileCount"],
                counters["fileWriteCount"],
            ),
            (2, 300, 1966, 7, 2, 0, 0, 0),
        )

    def test_11_unknown_keys_and_boolean_as_integer_fail(self) -> None:
        cases = (
            (
                lambda value:
                    value.__setitem__("unknown", False),
                "E_DECISION_SCHEMA",
            ),
            (
                lambda value:
                    value["authority"].__setitem__("unknown", False),
                "E_DECISION_AUTHORITY",
            ),
            (
                lambda value:
                    value["identityResolution"].__setitem__(
                        "unknown",
                        False,
                    ),
                "E_DECISION_IDENTITY",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("unknown", False),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"].__setitem__(
                        "requestCount",
                        True,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["operationCounters"].__setitem__(
                        "identityWitnessScanCount",
                        True,
                    ),
                "E_DECISION_COUNTERS",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ].__setitem__("fixedPointReached", 0),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "retainedFdPreManifestBarrierCount",
                        True,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ].__setitem__("osSyscallSandboxProvided", 0),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "completionAppliesToRetainedSnapshot",
                        1,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "currentPathIdentityGuaranteedThroughManifestPublication",
                        0,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ]["retainedSnapshotBoundary"].__setitem__(
                        "sameUidConcurrentRenameOrReplacementAfterLastBarrierPrevented",
                        0,
                    ),
                "E_DECISION_LINEAGE",
            ),
        )
        for mutate, code in cases:
            with self.subTest(code=code):
                self.mutated_failure(mutate, code)

    def test_12_lineage_h1_request_and_scope_mutations_fail(
        self,
    ) -> None:
        cases = (
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ].__setitem__("frontierSha256", "0" * 64),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ].__setitem__("osSyscallSandboxProvided", True),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ].__setitem__("v8TestsLiveHeld", True),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ].__setitem__(
                        "wave9PinnedLegacyBuildCompatibilityCount",
                        3,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["predecessorBindings"][
                        "combinedFixedPointV9"
                    ]["wave9LegacyBuildCompatibilityPolicy"].__setitem__(
                        "directReconstructionApplicationCount",
                        3,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["heldSourceInputSet"].__setitem__(
                        "sourceBindingsSha256",
                        "0" * 64,
                    ),
                "E_DECISION_LINEAGE",
            ),
            (
                lambda value:
                    value["identityResolution"]["tuples"][0].__setitem__(
                        "goModH1",
                        VALID_H1_A,
                    ),
                "E_DECISION_IDENTITY",
            ),
            (
                lambda value:
                    value["identityResolution"]["tuples"][8].__setitem__(
                        "selectedByGraphAlgorithm",
                        True,
                    ),
                "E_DECISION_IDENTITY",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("resourceKind", "zip"),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][16].__setitem__(
                        "selectedByGraphAlgorithm",
                        True,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"].__setitem__(
                        "namespaceCleanAtDecisionCheck",
                        False,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"].__setitem__(
                        "namespaceCheckIsPointInTimeOnly",
                        False,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"].__setitem__(
                        "namespaceReservationClaimed",
                        True,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("requestOrdinal", 2),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__("expectedH1", VALID_H1_A),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__(
                        "url",
                        "https://proxy.golang.org/invalid",
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__(
                        "acceptedFileName",
                        "invalid.mod",
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["sourceAcquisitionPreparation"][
                        "requestSet"
                    ][0].__setitem__(
                        "maximumResponseBytes",
                        1_048_577,
                    ),
                "E_DECISION_REQUEST",
            ),
            (
                lambda value:
                    value["toolBindings"][0].__setitem__(
                        "normalizedSha256",
                        "0" * 64,
                    ),
                "E_DECISION_BINDINGS",
            ),
        )
        for mutate, code in cases:
            with self.subTest(code=code):
                self.mutated_failure(mutate, code)

    def test_13_main_normal_output_contract_is_fast(self) -> None:
        summary = {
            "documentType":
                "aetherlink.wave11-identity-acquisition-decision-check",
            "validationPassed": True,
            "tupleCount": CHECKER.EXPECTED_FRONTIER_COUNT,
            "acquisitionAuthorized": False,
            "externalAuthenticationRequired": False,
            "osSyscallSandboxProvided": False,
        }
        stdout = types.SimpleNamespace(buffer=io.BytesIO())
        with (
            mock.patch.object(
                CHECKER,
                "evaluate",
                return_value=(self.expected, summary),
            ) as evaluate_mock,
            mock.patch.object(CHECKER.sys, "stdout", stdout),
        ):
            returncode = CHECKER.main([])
        self.assertEqual(returncode, 0)
        evaluate_mock.assert_called_once_with(
            CHECKER.ROOT,
            verify_disk=True,
        )
        self.assertEqual(stdout.buffer.getvalue(), canonical(summary))

    def test_14_request_contract_rejects_duplicates_and_encoding(
        self,
    ) -> None:
        rows = [
            {
                "tupleOrder": order,
                "module": value[0],
                "version": value[1],
                "selectedByGraphAlgorithm": value[2],
                "goModH1Values": [value[3]],
                "moduleZipH1Values": [value[4]],
            }
            for order, value in enumerate(
                CHECKER.EXPECTED_IDENTITY,
                1,
            )
        ]
        duplicate = copy.deepcopy(rows)
        duplicate[1]["module"] = duplicate[0]["module"]
        duplicate[1]["version"] = duplicate[0]["version"]
        uppercase = copy.deepcopy(rows)
        uppercase[0]["module"] = "github.com/Example/module"
        reordered = copy.deepcopy(rows)
        reordered[0]["tupleOrder"] = 2
        for value in (duplicate, uppercase, reordered):
            with self.subTest(value=value[0]):
                with self.assertRaises(
                    CHECKER.DecisionFailure,
                ) as caught:
                    CHECKER.request_set(value)
                self.assertEqual(caught.exception.code, "E_REQUEST_SET")

    def test_15_go_sum_strips_only_exact_trailing_mod_suffix(
        self,
    ) -> None:
        targets = {
            ("example.test/target", "v1.0.0"): {
                "tupleOrder": 1,
            }
        }
        zip_rows, mod_rows = CHECKER.parse_go_sum_entry(
            raw=(
                f"example.test/target v1.0.0 {VALID_H1_A}\n"
                f"example.test/target v1.0.0/go.mod {VALID_H1_B}\n"
                f"example.test/target v1.0.0/go.mod/go.mod {VALID_H1_A}\n"
            ).encode(),
            targets=targets,
            holder_module="example.test/parent",
            holder_version="v1.0.0",
            holder_wave="synthetic",
            archive_path="held.zip",
            archive_raw_sha256="0" * 64,
            entry_path="parent@v1.0.0/go.sum",
        )
        pair = ("example.test/target", "v1.0.0")
        self.assertEqual(
            [row["h1"] for row in zip_rows[pair]],
            [VALID_H1_A],
        )
        self.assertEqual(
            [row["h1"] for row in mod_rows[pair]],
            [VALID_H1_B],
        )

    def test_16_every_closure_value_mutation_fails_closed(
        self,
    ) -> None:
        closure = self.expected["closure"]
        for key, expected in closure.items():
            with self.subTest(key=key):
                self.mutated_failure(
                    lambda value, key=key, expected=expected:
                        value["closure"].__setitem__(key, not expected),
                    "E_DECISION_CLOSURE",
                )

    def test_17_exact_identity_and_request_lists_reject_every_mutation(
        self,
    ) -> None:
        def changed(value):
            if type(value) is bool:
                return not value
            if type(value) is int:
                return value + 1000
            if type(value) is str:
                return value + "-mutated"
            self.fail(f"unhandled exact-row field type: {type(value)!r}")

        identity_rows = self.expected["identityResolution"]["tuples"]
        for row_index, row in enumerate(identity_rows):
            for key, original in row.items():
                with self.subTest(
                    list_name="identity",
                    row=row_index,
                    key=key,
                ):
                    self.mutated_failure(
                        lambda value,
                        row_index=row_index,
                        key=key,
                        original=original:
                            value["identityResolution"]["tuples"][
                                row_index
                            ].__setitem__(key, changed(original)),
                        "E_DECISION_IDENTITY",
                    )

        identity_list_mutations = (
            lambda rows: rows.pop(0),
            lambda rows: rows.append(copy.deepcopy(rows[0])),
            lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0])),
            lambda rows: rows.__setitem__(
                slice(0, 2),
                [rows[1], rows[0]],
            ),
            lambda rows: rows[0].__setitem__(
                "module",
                "example.invalid/same-cardinality-substitute",
            ),
        )
        for index, mutate in enumerate(identity_list_mutations):
            with self.subTest(list_name="identity", mutation=index):
                self.mutated_failure(
                    lambda value, mutate=mutate:
                        mutate(value["identityResolution"]["tuples"]),
                    "E_DECISION_IDENTITY",
                )

        requests = self.expected["sourceAcquisitionPreparation"][
            "requestSet"
        ]
        for row_index, row in enumerate(requests):
            for key, original in row.items():
                with self.subTest(
                    list_name="request",
                    row=row_index,
                    key=key,
                ):
                    self.mutated_failure(
                        lambda value,
                        row_index=row_index,
                        key=key,
                        original=original:
                            value["sourceAcquisitionPreparation"][
                                "requestSet"
                            ][row_index].__setitem__(
                                key,
                                changed(original),
                            ),
                        "E_DECISION_REQUEST",
                    )

        request_list_mutations = (
            lambda rows: rows.pop(0),
            lambda rows: rows.append(copy.deepcopy(rows[0])),
            lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0])),
            lambda rows: rows.__setitem__(
                slice(0, 2),
                [rows[1], rows[0]],
            ),
            lambda rows: rows[0].__setitem__(
                "module",
                "example.invalid/same-cardinality-substitute",
            ),
        )
        for index, mutate in enumerate(request_list_mutations):
            with self.subTest(list_name="request", mutation=index):
                self.mutated_failure(
                    lambda value, mutate=mutate:
                        mutate(
                            value["sourceAcquisitionPreparation"][
                                "requestSet"
                            ]
                        ),
                    "E_DECISION_REQUEST",
                )

    def test_18_authority_closure_and_counter_types_fail_closed(
        self,
    ) -> None:
        for key in self.expected["authority"]:
            for replacement in (True, 0):
                with self.subTest(
                    section="authority",
                    key=key,
                    replacement=replacement,
                ):
                    self.mutated_failure(
                        lambda value,
                        key=key,
                        replacement=replacement:
                            value["authority"].__setitem__(
                                key,
                                replacement,
                            ),
                        "E_DECISION_AUTHORITY",
                    )
        self.mutated_failure(
            lambda value:
                value["authority"].__setitem__("unknown", False),
            "E_DECISION_AUTHORITY",
        )

        for key, original in self.expected["closure"].items():
            for replacement in (not original, int(original)):
                with self.subTest(
                    section="closure",
                    key=key,
                    replacement=replacement,
                ):
                    self.mutated_failure(
                        lambda value,
                        key=key,
                        replacement=replacement:
                            value["closure"].__setitem__(
                                key,
                                replacement,
                            ),
                        "E_DECISION_CLOSURE",
                    )
        self.mutated_failure(
            lambda value:
                value["closure"].__setitem__("unknown", False),
            "E_DECISION_CLOSURE",
        )

        equivalent_counter_bool_cases = 0
        for key, original in self.expected["operationCounters"].items():
            replacement = bool(original)
            if original in (0, 1):
                equivalent_counter_bool_cases += 1
                self.assertEqual(replacement, original)
                self.assertIsNot(type(replacement), type(original))
            with self.subTest(
                section="counter",
                key=key,
                replacement=replacement,
            ):
                self.mutated_failure(
                    lambda value,
                    key=key,
                    replacement=replacement:
                        value["operationCounters"].__setitem__(
                            key,
                            replacement,
                        ),
                    "E_DECISION_COUNTERS",
                )
        self.assertGreaterEqual(equivalent_counter_bool_cases, 2)
        self.mutated_failure(
            lambda value:
                value["operationCounters"].__setitem__("unknown", 0),
            "E_DECISION_COUNTERS",
        )

    def test_19_noncanonical_json_bytes_fail_closed(self) -> None:
        raw = canonical(self.expected)
        reordered = (
            json.dumps(
                dict(reversed(tuple(self.expected.items()))),
                ensure_ascii=True,
                sort_keys=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        variants = (
            b" " + raw,
            raw.replace(b",", b", ", 1),
            reordered,
            raw[:-1] + b"\r\n",
            raw[:-1],
            raw + b"\n",
        )
        for index, variant in enumerate(variants):
            with (
                self.subTest(variant=index),
                self.assertRaises(
                    CHECKER.DecisionFailure,
                ) as caught,
            ):
                CHECKER.validate_materialized_decision(
                    variant,
                    self.expected,
                    self.package_raw,
                )
            self.assertEqual(caught.exception.code, "E_DECISION_JSON")

if __name__ == "__main__":
    unittest.main(verbosity=2)
