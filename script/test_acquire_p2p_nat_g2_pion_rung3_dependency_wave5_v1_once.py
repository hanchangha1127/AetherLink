#!/usr/bin/env python3
"""Adversarial offline tests for the one-use Wave5 acquisition runner."""

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
    raise RuntimeError("Wave5 runner tests require `python3 -I -B -S`")

from contextlib import nullcontext
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import stat
import tempfile
import time
import unittest
from unittest import mock
import zipfile


RUNNER_PATH = Path(__file__).with_name(
    "acquire_p2p_nat_g2_pion_rung3_dependency_wave5_v1_once.py"
)
SPEC = importlib.util.spec_from_file_location(
    "wave5_source_acquirer_v1",
    RUNNER_PATH,
)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def make_zip(
    module: str,
    version: str,
    files: dict[str, bytes],
) -> bytes:
    output = io.BytesIO()
    prefix = f"{module}@{version}/"
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, raw in files.items():
            info = zipfile.ZipInfo(prefix + name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return output.getvalue()


def fixture() -> tuple[list[dict[str, object]], dict[int, bytes]]:
    rows: list[dict[str, object]] = []
    bodies: dict[int, bytes] = {}
    ordinal = 0
    for tuple_order in range(1, 16):
        module = f"example.test/dependency{tuple_order}"
        version = f"v1.0.{tuple_order}"
        digest = runner.sha256(f"{module}\n{version}\n".encode())
        tuple_id = f"wave5-{tuple_order:03d}-{digest[:12]}"
        selected = False
        mod = f"module {module}\n\ngo 1.22\n".encode()
        archive = make_zip(
            module,
            version,
            {
                "go.mod": mod,
                "source.go": (
                    f"package dependency{tuple_order}\n".encode()
                ),
            },
        )
        for kind, body, expected_h1, maximum in (
            (
                "mod",
                mod,
                runner.VALIDATION.go_mod_h1(mod),
                runner.CHECK.MAX_MOD_BYTES,
            ),
            (
                "zip",
                archive,
                runner.VALIDATION.module_zip_h1(
                    archive,
                    module,
                    version,
                ),
                runner.CHECK.MAX_ZIP_BYTES,
            ),
        ):
            ordinal += 1
            path = f"/{module}/@v/{version}.{kind}"
            rows.append(
                {
                    "requestOrdinal": ordinal,
                    "tupleOrder": tuple_order,
                    "tupleId": tuple_id,
                    "tupleDigestSha256": digest,
                    "selectedByGraphAlgorithm": selected,
                    "module": module,
                    "version": version,
                    "kind": kind,
                    "method": "GET",
                    "host": runner.CHECK.PROXY_HOST,
                    "port": 443,
                    "path": path,
                    "url": f"https://{runner.CHECK.PROXY_HOST}{path}",
                    "expectedH1": expected_h1,
                    "maximumResponseBodyBytes": maximum,
                    "acceptedFileName": (
                        f"{tuple_order:03d}-{digest[:20]}.{kind}"
                    ),
                }
            )
            bodies[ordinal] = body
    return rows, bodies


def values(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "decision": {
            "contentBinding": {"sha256": "d" * 64},
        },
        "permit": {
            "contentBinding": {"sha256": "p" * 64},
            "requestContract": {
                "requestCount": 30,
                "resources": rows,
                "resourcesCanonicalSha256": runner.sha256(
                    runner.canonical_bytes(rows)
                ),
            },
            "authority": {
                "externalAuthenticationRequired": False,
                "repositoryOwnerIdentityProofRequired": False,
                "passwordRequired": False,
                "privateKeyRequired": False,
                "signatureRequired": False,
                "tokenRequired": False,
                "userActionRequired": False,
            },
            "toolBindings": [
                {
                    "path": runner.CHECK.RUNNER_PATH,
                    "rawSha256": "r" * 64,
                }
            ],
        },
    }


def prepare_root(root: Path) -> None:
    (root / runner.CHECK.DEPENDENCY_ROOT).mkdir(
        parents=True,
        mode=0o700,
    )
    (root / runner.CHECK.BASE).mkdir(
        parents=True,
        mode=0o700,
    )


def terminal(root: Path, path: str) -> Path:
    return root / path


class Wave5RunnerTests(unittest.TestCase):
    def run_attempt(
        self,
        root: Path,
        fetch,
        rows: list[dict[str, object]],
        *,
        hook=None,
        ops=None,
        whole_timeout: float = 10,
        checkpoint=None,
    ):
        prepare_root(root)
        arguments = {"hook": hook}
        if ops is not None:
            arguments["ops"] = ops
        with runner.ExecutionNamespace(root, **arguments) as namespace:
            return runner._attempt(
                fetch,
                values(rows),
                namespace,
                whole_timeout=whole_timeout,
                checkpoint=checkpoint,
            )

    def test_success_claims_before_30_fetches_and_manifest_is_last(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls: list[int] = []
            events: list[str] = []

            def hook(event: str, _namespace) -> None:
                events.append(event)

            def fetch(resource, _deadline):
                self.assertTrue(
                    terminal(root, runner.CHECK.CLAIM_PATH).exists()
                )
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            receipt = self.run_attempt(
                root,
                fetch,
                rows,
                hook=hook,
            )
            self.assertEqual(calls, list(range(1, 31)))
            self.assertEqual(
                receipt["status"],
                "consumed_success_pending_independent_readback",
            )
            self.assertEqual(events[-3:], [
                "after_publish",
                "after_receipt_persisted",
                "after_manifest_persisted",
            ])
            accepted = terminal(root, runner.CHECK.FINAL_ACCEPTED)
            self.assertEqual(len(list(accepted.iterdir())), 30)
            self.assertTrue(
                terminal(root, runner.CHECK.CLAIM_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.RECEIPT_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.MANIFEST_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )
            self.assertTrue(
                all(
                    stat.S_IMODE(path.stat().st_mode) == 0o600
                    for path in accepted.iterdir()
                )
            )

    def test_h1_mismatch_consumes_once_and_retains_staging(self) -> None:
        rows, bodies = fixture()
        rows = copy.deepcopy(rows)
        rows[3]["expectedH1"] = "h1:" + "A" * 43 + "="
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls: list[int] = []

            def fetch(resource, _deadline):
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(root, fetch, rows)
            self.assertEqual(caught.exception.code, "E_H1_MISMATCH")
            self.assertEqual(
                runner.error_document(caught.exception)["status"],
                "consumed_failure_no_retry",
            )
            self.assertEqual(calls, [1, 2, 3, 4])
            self.assertTrue(
                terminal(root, runner.CHECK.CLAIM_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )
            dependency = terminal(root, runner.CHECK.DEPENDENCY_ROOT)
            self.assertEqual(
                len(
                    [
                        path
                        for path in dependency.iterdir()
                        if path.name.startswith(runner.CHECK.STAGING_PREFIX)
                    ]
                ),
                1,
            )
            failure = json.loads(
                terminal(root, runner.CHECK.FAILURE_PATH).read_text()
            )
            self.assertFalse(
                failure["externalAuthenticationRequired"]
            )
            self.assertFalse(failure["userActionRequired"])
            self.assertFalse(failure["retryResumeOrBackfillAllowed"])

    def test_canonical_preflight_context_composes_without_writes(self) -> None:
        self.assertFalse(
            terminal(runner.ROOT, runner.CHECK.CLAIM_PATH).exists()
        )
        package, _ = runner.CHECK.evaluate(True)
        permit = package["permit"]
        self.assertEqual(
            permit["oneUseContract"]["existingClaimState"],
            "already_consumed",
        )
        self.assertIs(
            permit["oneUseContract"]["claimAbsentAtPermitPublication"],
            True,
        )
        x_sys = [
            row for row in permit["requestContract"]["resources"]
            if row["module"] == "golang.org/x/sys"
            and row["version"] in {"v0.17.0", "v0.20.0"}
        ]
        self.assertEqual(
            {
                row["expectedH1"]
                for row in x_sys
                if row["kind"] == "mod"
            },
            {"h1:/VUhepiaJMQUp4+oa/7Zr1D23ma6VTLIYjOOTFZPUcA="},
        )
        self.assertEqual(
            len({row["acceptedFileName"] for row in x_sys}),
            4,
        )
        result = runner.validate_execution_context()
        self.assertTrue(result["validationPassed"])
        self.assertEqual(result["requestCount"], 30)
        self.assertFalse(result["networkUsed"])
        self.assertEqual(result["fileWriteCount"], 0)
        self.assertFalse(result["externalAuthenticationRequired"])
        self.assertFalse(result["userActionRequired"])
        self.assertFalse(
            terminal(runner.ROOT, runner.CHECK.CLAIM_PATH).exists()
        )

    def test_semantic_or_cardinality_mutation_fails_before_claim(self) -> None:
        original, _ = fixture()
        mutations = (
            lambda rows: rows.__setitem__(29, dict(rows[28])),
            lambda rows: rows[29].__setitem__(
                "requestOrdinal",
                31,
            ),
            lambda rows: rows[1].__setitem__(
                "tupleId",
                rows[3]["tupleId"],
            ),
            lambda rows: rows[0].__setitem__(
                "selectedByGraphAlgorithm",
                "false",
            ),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                rows = copy.deepcopy(original)
                mutation(rows)
                permit = values(rows)["permit"]
                with self.assertRaises(runner.AcquisitionError):
                    runner._validate_resource_contract(rows, permit)

    def test_expired_deadline_fetches_zero_after_durable_claim(self) -> None:
        rows, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls: list[int] = []
            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: calls.append(
                        resource["requestOrdinal"]
                    ),
                    rows,
                    whole_timeout=-1,
                )
            self.assertEqual(caught.exception.code, "E_DEADLINE")
            self.assertEqual(calls, [])
            self.assertTrue(
                terminal(root, runner.CHECK.CLAIM_PATH).exists()
            )
            self.assertTrue(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )

    def test_claim_fsync_uncertainty_never_fetches(self) -> None:
        rows, _ = fixture()
        for failing_call in (1, 2):
            with self.subTest(failing_call=failing_call):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    calls = 0
                    fsync_calls = 0

                    def controlled_fsync(fd: int) -> None:
                        nonlocal fsync_calls
                        fsync_calls += 1
                        if fsync_calls == failing_call:
                            raise OSError("synthetic fsync failure")
                        os.fsync(fd)

                    def fetch(_resource, _deadline):
                        nonlocal calls
                        calls += 1
                        return b"x"

                    with self.assertRaises(
                        runner.AcquisitionError
                    ) as caught:
                        self.run_attempt(
                            root,
                            fetch,
                            rows,
                            ops=runner.FileOps(
                                fsync=controlled_fsync
                            ),
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "E_CLAIM_STATE_UNCERTAIN",
                    )
                    self.assertEqual(calls, 0)
                    self.assertTrue(
                        terminal(root, runner.CHECK.CLAIM_PATH).exists()
                    )

    def test_claim_replacement_is_detected_before_network(self) -> None:
        rows, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fetches = 0

            def hook(event: str, namespace) -> None:
                if event != "after_claim_durable":
                    return
                name = Path(runner.CHECK.CLAIM_PATH).name
                os.unlink(name, dir_fd=namespace.dependency_fd)
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=namespace.dependency_fd,
                )
                os.write(fd, b"replacement")
                os.close(fd)

            def fetch(_resource, _deadline):
                nonlocal fetches
                fetches += 1
                return b"x"

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(root, fetch, rows, hook=hook)
            self.assertEqual(
                caught.exception.code,
                "E_FAILURE_PUBLICATION_UNCERTAIN",
            )
            self.assertEqual(fetches, 0)

    def test_preflight_classifies_exact_existing_claim_as_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            terminal(root, runner.CHECK.CLAIM_PATH).write_text(
                "existing",
            )
            with self.assertRaises(runner.AcquisitionError) as caught:
                runner._reject_consumed_claim(root)
            self.assertEqual(caught.exception.code, "E_CONSUMED")
            self.assertEqual(caught.exception.phase, "claim")
            self.assertEqual(
                runner.error_document(caught.exception)["status"],
                "already_consumed",
            )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            terminal(root, runner.CHECK.CLAIM_PATH).with_name(
                Path(runner.CHECK.CLAIM_PATH).name.upper()
            ).write_text("casefold collision")
            with self.assertRaises(runner.AcquisitionError) as caught:
                runner._reject_consumed_claim(root)
            self.assertEqual(caught.exception.code, "E_NAMESPACE")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_root(root)
            with mock.patch.object(
                runner.os,
                "listdir",
                return_value=["\u00e9", "e\u0301"],
            ):
                with self.assertRaises(runner.AcquisitionError) as caught:
                    runner._reject_consumed_claim(root)
            self.assertEqual(caught.exception.code, "E_NAMESPACE")

    def test_accepted_directory_rebind_blocks_next_write(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir(mode=0o700)
            calls: list[int] = []

            def hook(event: str, namespace) -> None:
                if event != "after_resource_persisted":
                    return
                if len(namespace.resources) != 1:
                    return
                os.rename(
                    "accepted",
                    "accepted-held",
                    src_dir_fd=namespace.staging.fd,
                    dst_dir_fd=namespace.staging.fd,
                )
                os.symlink(
                    outside,
                    "accepted",
                    dir_fd=namespace.staging.fd,
                )

            def fetch(resource, _deadline):
                calls.append(resource["requestOrdinal"])
                return bodies[resource["requestOrdinal"]]

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(root, fetch, rows, hook=hook)
            self.assertEqual(
                caught.exception.code,
                "E_FAILURE_PUBLICATION_UNCERTAIN",
            )
            self.assertEqual(calls, [1])
            self.assertEqual(list(outside.iterdir()), [])

    def test_final_rebind_after_publish_suppresses_receipt(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def hook(event: str, namespace) -> None:
                if event != "after_publish":
                    return
                final = Path(runner.CHECK.FINAL_ROOT).name
                os.rename(
                    final,
                    "moved-final",
                    src_dir_fd=namespace.dependency_fd,
                    dst_dir_fd=namespace.dependency_fd,
                )
                os.mkdir(
                    final,
                    0o700,
                    dir_fd=namespace.dependency_fd,
                )

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    rows,
                    hook=hook,
                )
            self.assertEqual(
                caught.exception.code,
                "E_POST_PUBLISH_UNCERTAIN",
            )
            self.assertFalse(
                terminal(root, runner.CHECK.RECEIPT_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.MANIFEST_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )

    def test_receipt_replacement_prevents_manifest(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def hook(event: str, namespace) -> None:
                if event != "after_receipt_persisted":
                    return
                name = Path(runner.CHECK.RECEIPT_PATH).name
                os.unlink(name, dir_fd=namespace.docs_fd)
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=namespace.docs_fd,
                )
                os.write(fd, b"replacement")
                os.close(fd)

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    rows,
                    hook=hook,
                )
            self.assertEqual(
                caught.exception.code,
                "E_POST_PUBLISH_UNCERTAIN",
            )
            self.assertFalse(
                terminal(root, runner.CHECK.MANIFEST_PATH).exists()
            )
            self.assertFalse(
                terminal(root, runner.CHECK.FAILURE_PATH).exists()
            )

    def test_atomic_no_replace_preserves_preexisting_final(self) -> None:
        rows, bodies = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def hook(event: str, namespace) -> None:
                if event == "before_publish":
                    os.mkdir(
                        Path(runner.CHECK.FINAL_ROOT).name,
                        0o700,
                        dir_fd=namespace.dependency_fd,
                    )

            with self.assertRaises(runner.AcquisitionError) as caught:
                self.run_attempt(
                    root,
                    lambda resource, _deadline: bodies[
                        resource["requestOrdinal"]
                    ],
                    rows,
                    hook=hook,
                )
            self.assertEqual(
                caught.exception.code,
                "E_POST_PUBLISH_UNCERTAIN",
            )
            final = terminal(root, runner.CHECK.FINAL_ROOT)
            self.assertTrue(final.is_dir())
            self.assertEqual(list(final.iterdir()), [])
            self.assertFalse(
                terminal(root, runner.CHECK.RECEIPT_PATH).exists()
            )

    def test_execute_restores_preexisting_real_timer(self) -> None:
        original_handler = signal.getsignal(signal.SIGALRM)
        original_timer = signal.getitimer(signal.ITIMER_REAL)

        def prior_handler(_signum, _frame):
            pass

        signal.signal(signal.SIGALRM, prior_handler)
        signal.setitimer(signal.ITIMER_REAL, 5.0, 0.25)
        started = time.monotonic()
        try:
            authority = mock.Mock()
            authority.__enter__ = mock.Mock(return_value=authority)
            authority.__exit__ = mock.Mock(return_value=None)
            namespace = mock.Mock()
            namespace.__enter__ = mock.Mock(return_value=namespace)
            namespace.__exit__ = mock.Mock(return_value=None)
            with mock.patch.object(
                runner,
                "preflight",
                return_value=({"permit": {}}, {}),
            ), mock.patch.object(
                runner.CHECK,
                "AuthorityFiles",
                return_value=authority,
            ), mock.patch.object(
                runner,
                "ExecutionNamespace",
                return_value=namespace,
            ), mock.patch.object(
                runner,
                "_attempt",
                return_value={"synthetic": True},
            ):
                self.assertEqual(
                    runner.execute(lambda _resource, _deadline: b""),
                    {"synthetic": True},
                )
            delay, interval = signal.getitimer(signal.ITIMER_REAL)
            elapsed = time.monotonic() - started
            self.assertGreater(
                delay,
                max(0.1, 5.0 - elapsed - 0.2),
            )
            self.assertLessEqual(delay, 5.0)
            self.assertAlmostEqual(interval, 0.25, places=2)
            self.assertIs(signal.getsignal(signal.SIGALRM), prior_handler)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, original_handler)
            if original_timer[0] > 0:
                signal.setitimer(
                    signal.ITIMER_REAL,
                    max(
                        0.000001,
                        original_timer[0]
                        - (time.monotonic() - started),
                    ),
                    original_timer[1],
                )

    def test_error_document_never_requests_authentication_or_retry(self) -> None:
        value = runner.error_document(
            runner.AcquisitionError("E_NETWORK", "request_01")
        )
        self.assertFalse(value["retryAllowed"])
        self.assertFalse(value["externalAuthenticationRequired"])
        self.assertFalse(value["userActionRequired"])

        resource = fixture()[0][0]
        connection_calls: list[tuple[str, int]] = []

        class RedirectResponse:
            status = 302

            @staticmethod
            def getheaders():
                return [("Location", "https://hostile.invalid/")]

            @staticmethod
            def getheader(_name):
                return None

        class DirectConnection:
            def __init__(self, host, port, **_kwargs):
                connection_calls.append((host, port))

            @staticmethod
            def request(*_args, **_kwargs):
                return None

            @staticmethod
            def getresponse():
                return RedirectResponse()

            @staticmethod
            def close():
                return None

        hostile_environment = {
            "HTTP_PROXY": "http://hostile.invalid:8080",
            "HTTPS_PROXY": "http://hostile.invalid:8443",
            "ALL_PROXY": "socks5://hostile.invalid:1080",
            "NO_PROXY": "",
        }
        with mock.patch.dict(
            os.environ,
            hostile_environment,
            clear=False,
        ):
            with self.assertRaises(
                runner.VALIDATION.AcquisitionError
            ) as caught:
                runner.VALIDATION.direct_fetch(
                    resource,
                    time.monotonic() + 5,
                    connection_factory=DirectConnection,
                )
        self.assertEqual(caught.exception.code, "E_RESPONSE")
        self.assertEqual(
            connection_calls,
            [(runner.CHECK.PROXY_HOST, 443)],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
