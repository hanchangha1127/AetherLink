#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import math
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPT_DIR / "run_memory_semantic_calibration.py"
SPEC = importlib.util.spec_from_file_location("run_memory_semantic_calibration", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
calibration = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = calibration
SPEC.loader.exec_module(calibration)


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.body = body
        self.status = status
        self.headers = headers or {}

    def getheader(self, name: str) -> str | None:
        return self.headers.get(name)

    def read(self, amount: int) -> bytes:
        return self.body[:amount]

    def close(self) -> None:
        pass


class SlowUntilClosedResponse(FakeResponse):
    def __init__(self) -> None:
        super().__init__(b"{}")
        self.closed = threading.Event()

    def read(self, amount: int) -> bytes:
        del amount
        self.closed.wait(timeout=2.0)
        raise OSError("closed")

    def close(self) -> None:
        self.closed.set()


class FakeConnection:
    def __init__(self, factory: "FakeConnectionFactory", response: FakeResponse) -> None:
        self.factory = factory
        self.response = response

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.factory.requests.append((method, path, body, headers or {}))

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.factory.close_count += 1


class FakeConnectionFactory:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, int, float]] = []
        self.requests: list[tuple[str, str, bytes | None, dict[str, str]]] = []
        self.close_count = 0

    def __call__(self, host: str, port: int, *, timeout: float) -> FakeConnection:
        if not self.responses:
            raise AssertionError("unexpected connection")
        self.calls.append((host, port, timeout))
        return FakeConnection(self, self.responses.pop(0))


class MemorySemanticCalibrationTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_path = calibration.DEFAULT_CORPUS
        cls.fixture_raw = cls.fixture_path.read_bytes()
        cls.fixture_object = json.loads(cls.fixture_raw)
        cls.corpus = calibration.load_corpus(cls.fixture_path)

    def offline_report(self) -> dict[str, Any]:
        return calibration.evaluate(
            self.corpus,
            [entry.offline_embedding for entry in self.corpus.entries],
            "offline",
        )

    def write_fixture(self, value: Any) -> Path:
        temporary = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = Path(temporary.name)
        with temporary:
            temporary.write(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def assert_error(self, code: str, callback: Any) -> None:
        with self.assertRaises(calibration.CalibrationError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_canonical_offline_result_matches_swift_calibration(self) -> None:
        report = self.offline_report()

        self.assertEqual(report["mode"], "offline")
        self.assertEqual(report["corpus_sha256"], calibration.hashlib.sha256(self.fixture_raw).hexdigest())
        aggregate = report["aggregate_metrics"]
        self.assertEqual(aggregate["sweep_minimum_threshold_basis_points"], 8_000)
        self.assertEqual(aggregate["sweep_maximum_threshold_basis_points"], 10_000)
        self.assertEqual(aggregate["sweep_step_basis_points"], 1)
        self.assertEqual(aggregate["sweep_threshold_count"], 2_001)
        self.assertEqual(aggregate["best_f1"]["threshold_basis_points"], 9_511)
        self.assertEqual(
            aggregate["review_threshold"],
            {
                "threshold_basis_points": 9_000,
                "true_positive_count": 7,
                "false_positive_count": 0,
                "true_negative_count": 7,
                "false_negative_count": 0,
                "precision_basis_points": 10_000,
                "recall_basis_points": 10_000,
                "f1_basis_points": 10_000,
            },
        )
        self.assertTrue(report["review_clusters_exact_match"])
        self.assertEqual(
            report["predicted_review_clusters"],
            [
                {
                    "entry_ids": ["theme-en", "theme-zh"],
                    "minimum_similarity_basis_points": 9_900,
                },
                {
                    "entry_ids": ["source-en", "source-ja"],
                    "minimum_similarity_basis_points": 9_800,
                },
                {
                    "entry_ids": ["concise-en", "concise-fr", "concise-ko"],
                    "minimum_similarity_basis_points": 9_659,
                },
                {
                    "entry_ids": ["chain-a", "chain-b"],
                    "minimum_similarity_basis_points": 9_511,
                },
            ],
        )
        scores = {
            (pair["first_entry_id"], pair["second_entry_id"]): pair["similarity_basis_points"]
            for pair in report["pair_scores"]
        }
        self.assertEqual(scores[("chain-a", "chain-b")], 9_511)
        self.assertEqual(scores[("chain-a", "chain-c")], 8_090)
        self.assertEqual(scores[("chain-b", "chain-c")], 9_511)
        self.assertFalse(report["default_threshold_changed"])
        self.assertFalse(report["automatic_memory_mutation"])
        self.assertFalse(report["protocol_changed"])
        self.assertNotIn("model_id", report)
        self.assertNotIn("model_fingerprint", report)

    def test_cosine_rounding_is_nearest_away_from_zero(self) -> None:
        self.assertEqual(calibration.round_nearest_away_from_zero(9_510.5), 9_511)
        self.assertEqual(calibration.round_nearest_away_from_zero(-9_510.5), -9_511)
        self.assertEqual(calibration.round_nearest_away_from_zero(9_510.49), 9_510)

    def test_semantic_byte_exact_content_is_excluded(self) -> None:
        corpus = calibration.Corpus(
            corpus_id="byte-exact-test",
            review_threshold_basis_points=9_000,
            entries=(
                calibration.Entry("a", "same", (1.0, 0.0)),
                calibration.Entry("b", "same", (1.0, 0.0)),
                calibration.Entry("c", "different", (0.0, 1.0)),
            ),
            pair_labels=(
                calibration.PairLabel("a", "b", True),
                calibration.PairLabel("a", "c", False),
            ),
            expected_review_clusters=(),
            sha256="0" * 64,
        )
        report = calibration.evaluate(corpus, [(1, 0), (1, 0), (0, 1)], "offline")

        self.assertEqual(report["pair_scores"][0]["similarity_basis_points"], 10_000)
        self.assertFalse(report["pair_scores"][0]["is_semantic_candidate"])
        self.assertEqual(report["predicted_review_clusters"], [])
        self.assertIsNone(
            report["aggregate_metrics"]["review_threshold"]["precision_basis_points"]
        )

    def test_duplicate_json_keys_are_rejected(self) -> None:
        duplicate = self.fixture_raw.replace(
            b'"schema_version": 1,',
            b'"schema_version": 1, "schema_version": 1,',
            1,
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temporary:
            temporary.write(duplicate)
            path = Path(temporary.name)
        self.addCleanup(path.unlink, missing_ok=True)

        self.assert_error("duplicate_json_key", lambda: calibration.load_corpus(path))

    def test_malformed_and_exact_type_confusion_are_rejected(self) -> None:
        malformed = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        malformed_path = Path(malformed.name)
        with malformed:
            malformed.write(b"{")
        self.addCleanup(malformed_path.unlink, missing_ok=True)
        self.assert_error(
            "corpus_json_invalid", lambda: calibration.load_corpus(malformed_path)
        )

        mutations = [
            ("schema_version", True, "schema_version_invalid"),
            ("schema_version", 1.0, "schema_version_invalid"),
            ("review_threshold_basis_points", False, "review_threshold_invalid"),
            ("review_threshold_basis_points", 9_000.0, "review_threshold_invalid"),
        ]
        for key, value, expected_code in mutations:
            with self.subTest(key=key, value=value):
                fixture = copy.deepcopy(self.fixture_object)
                fixture[key] = value
                path = self.write_fixture(fixture)
                self.assert_error(expected_code, lambda path=path: calibration.load_corpus(path))

        fixture = copy.deepcopy(self.fixture_object)
        fixture["pair_labels"][0]["is_duplicate"] = 1
        path = self.write_fixture(fixture)
        self.assert_error("pair_label_type_invalid", lambda: calibration.load_corpus(path))

        fixture = copy.deepcopy(self.fixture_object)
        fixture["entries"][0]["offline_embedding"][0] = False
        path = self.write_fixture(fixture)
        self.assert_error("offline_embedding_invalid", lambda: calibration.load_corpus(path))

        fixture = copy.deepcopy(self.fixture_object)
        fixture["entries"][0]["offline_embedding"][0] = 10**400
        path = self.write_fixture(fixture)
        self.assert_error("offline_embedding_invalid", lambda: calibration.load_corpus(path))

        fixture = copy.deepcopy(self.fixture_object)
        fixture["entries"][0]["content"] = "   \n"
        path = self.write_fixture(fixture)
        self.assert_error("content_invalid", lambda: calibration.load_corpus(path))

        unpaired_surrogate = self.fixture_raw.replace(
            b'"chain-a"',
            b'"\\ud800"',
            1,
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temporary:
            temporary.write(unpaired_surrogate)
            path = Path(temporary.name)
        self.addCleanup(path.unlink, missing_ok=True)
        self.assert_error("entry_id_invalid", lambda: calibration.load_corpus(path))

    def test_nonliteral_loopback_hosts_are_rejected_without_connection(self) -> None:
        for host in ("localhost", "::1", "127.0.0.2", "127.0.0.1.", "example.invalid"):
            with self.subTest(host=host):
                factory = FakeConnectionFactory([])
                self.assert_error(
                    "host_not_loopback_literal",
                    lambda host=host: calibration.fetch_live_embeddings(
                        self.corpus,
                        host,
                        11_434,
                        "embed-model",
                        connection_factory=factory,
                    ),
                )
                self.assertEqual(factory.calls, [])

        factory = FakeConnectionFactory([])
        for model in (" embed-model", "embed model", "embed-model\n"):
            with self.subTest(model=model):
                self.assert_error(
                    "model_invalid",
                    lambda model=model: calibration.fetch_live_embeddings(
                        self.corpus,
                        "127.0.0.1",
                        11_434,
                        model,
                        connection_factory=factory,
                    ),
                )
        self.assertEqual(factory.calls, [])

    def test_mocked_live_ollama_uses_exact_model_and_one_embed_call(self) -> None:
        digest = "ab" * 32
        tags = {
            "models": [
                {
                    "name": "embed-model:latest",
                    "digest": digest,
                    "capabilities": ["embedding"],
                },
                {
                    "name": "embed-model",
                    "digest": "cd" * 32,
                    "capabilities": ["embedding"],
                },
            ]
        }
        embeddings = [list(entry.offline_embedding) for entry in self.corpus.entries]
        factory = FakeConnectionFactory(
            [
                FakeResponse(json.dumps(tags).encode("utf-8")),
                FakeResponse(json.dumps({"embeddings": embeddings}).encode("utf-8")),
                FakeResponse(json.dumps(tags).encode("utf-8")),
            ]
        )

        values, fingerprint = calibration.fetch_live_embeddings(
            self.corpus,
            "127.0.0.1",
            11_434,
            "embed-model:latest",
            timeout_seconds=3.5,
            connection_factory=factory,
        )

        self.assertEqual(values, embeddings)
        self.assertEqual(fingerprint, f"ollama-sha256:{digest}")
        self.assertEqual([request[:2] for request in factory.requests], [
            ("GET", "/api/tags"),
            ("POST", "/api/embed"),
            ("GET", "/api/tags"),
        ])
        embed_requests = [request for request in factory.requests if request[1] == "/api/embed"]
        self.assertEqual(len(embed_requests), 1)
        body = json.loads(embed_requests[0][2])
        self.assertEqual(body["model"], "embed-model:latest")
        self.assertEqual(body["input"], [entry.content for entry in self.corpus.entries])
        self.assertIs(body["truncate"], False)
        self.assertEqual(len(factory.calls), 3)
        self.assertTrue(all(call[0:2] == ("127.0.0.1", 11_434) for call in factory.calls))
        self.assertTrue(all(0 < call[2] <= 3.5 for call in factory.calls))
        self.assertEqual(factory.close_count, 3)

    def test_live_report_uses_provider_qualified_model_identity(self) -> None:
        embeddings = [list(entry.offline_embedding) for entry in self.corpus.entries]
        arguments = calibration.argparse.Namespace(
            corpus=self.fixture_path,
            mode="live-ollama",
            host="127.0.0.1",
            port=11_434,
            model="embed-model:latest",
            timeout_seconds=3.5,
        )
        with mock.patch.object(
            calibration,
            "fetch_live_embeddings",
            return_value=(embeddings, "ollama-sha256:" + "ab" * 32),
        ):
            report = calibration.run(arguments)

        self.assertEqual(report["mode"], "live-ollama")
        self.assertEqual(report["model_id"], "ollama:embed-model:latest")
        self.assertEqual(report["model_fingerprint"], "ollama-sha256:" + "ab" * 32)
        self.assertFalse(report["default_threshold_changed"])
        self.assertFalse(report["automatic_memory_mutation"])
        self.assertFalse(report["protocol_changed"])

    def test_live_capability_can_be_strictly_verified_by_show(self) -> None:
        digest = "01" * 32
        factory = FakeConnectionFactory(
            [
                FakeResponse(json.dumps({"models": [{"name": "m", "digest": digest}]}).encode()),
                FakeResponse(b'{"capabilities":["embedding"]}'),
                FakeResponse(
                    json.dumps(
                        {"embeddings": [list(entry.offline_embedding) for entry in self.corpus.entries]}
                    ).encode()
                ),
                FakeResponse(json.dumps({"models": [{"name": "m", "digest": digest}]}).encode()),
            ]
        )

        calibration.fetch_live_embeddings(
            self.corpus,
            "127.0.0.1",
            11_434,
            "m",
            connection_factory=factory,
        )

        self.assertEqual([request[:2] for request in factory.requests], [
            ("GET", "/api/tags"),
            ("POST", "/api/show"),
            ("POST", "/api/embed"),
            ("GET", "/api/tags"),
        ])
        show_body = json.loads(factory.requests[1][2])
        self.assertEqual(show_body, {"model": "m"})

    def test_live_model_digest_must_remain_stable_after_embedding(self) -> None:
        before_digest = "12" * 32
        after_digest = "34" * 32
        before_tags = {
            "models": [
                {"name": "m", "digest": before_digest, "capabilities": ["embedding"]}
            ]
        }
        after_tags = {
            "models": [
                {"name": "m", "digest": after_digest, "capabilities": ["embedding"]}
            ]
        }
        embeddings = [list(entry.offline_embedding) for entry in self.corpus.entries]
        factory = FakeConnectionFactory(
            [
                FakeResponse(json.dumps(before_tags).encode()),
                FakeResponse(json.dumps({"embeddings": embeddings}).encode()),
                FakeResponse(json.dumps(after_tags).encode()),
            ]
        )

        self.assert_error(
            "provider_model_changed_during_run",
            lambda: calibration.fetch_live_embeddings(
                self.corpus,
                "127.0.0.1",
                11_434,
                "m",
                connection_factory=factory,
            ),
        )

    def test_live_timeout_is_one_total_deadline_and_interrupts_slow_body(self) -> None:
        digest = "56" * 32
        tags = {
            "models": [
                {"name": "m", "digest": digest, "capabilities": ["embedding"]}
            ]
        }
        factory = FakeConnectionFactory(
            [
                FakeResponse(json.dumps(tags).encode()),
                SlowUntilClosedResponse(),
            ]
        )
        started = time.monotonic()

        self.assert_error(
            "provider_deadline_exceeded",
            lambda: calibration.fetch_live_embeddings(
                self.corpus,
                "127.0.0.1",
                11_434,
                "m",
                timeout_seconds=0.05,
                connection_factory=factory,
            ),
        )

        self.assertLess(time.monotonic() - started, 0.5)

    def test_live_deadline_is_rechecked_after_provider_json_parsing(self) -> None:
        factory = FakeConnectionFactory([FakeResponse(b'{"models":[]}')])
        connection = factory("127.0.0.1", 11_434, timeout=0.05)
        actual_loads = calibration.strict_json_loads

        def slow_loads(raw: bytes, error_code: str) -> Any:
            time.sleep(0.08)
            return actual_loads(raw, error_code)

        with mock.patch.object(calibration, "strict_json_loads", side_effect=slow_loads):
            self.assert_error(
                "provider_deadline_exceeded",
                lambda: calibration._request_json(
                    connection,
                    "GET",
                    "/api/tags",
                    calibration.MAXIMUM_TAGS_RESPONSE_BYTES,
                    time.monotonic() + 0.05,
                ),
            )

    def test_response_bounds_and_vector_invalidity_fail_closed(self) -> None:
        oversized = FakeResponse(
            b"{}",
            headers={"Content-Length": str(calibration.MAXIMUM_TAGS_RESPONSE_BYTES + 1)},
        )
        factory = FakeConnectionFactory([oversized])
        self.assert_error(
            "provider_response_too_large",
            lambda: calibration.fetch_live_embeddings(
                self.corpus,
                "127.0.0.1",
                11_434,
                "m",
                connection_factory=factory,
            ),
        )

        valid_tags = json.dumps(
            {
                "models": [
                    {"name": "m", "digest": "12" * 32, "capabilities": ["embedding"]}
                ]
            }
        ).encode()
        invalid_responses = [
            ({"embeddings": [[1.0, 0.0]]}, "embedding_count_invalid"),
            (
                {
                    "embeddings": [
                        [1.0, 0.0] if index == 0 else [1.0]
                        for index, _ in enumerate(self.corpus.entries)
                    ]
                },
                "embedding_dimension_invalid",
            ),
            (
                {
                    "embeddings": [
                        [0.0, 0.0] for _ in self.corpus.entries
                    ]
                },
                "embedding_value_invalid",
            ),
        ]
        for payload, code in invalid_responses:
            with self.subTest(code=code):
                factory = FakeConnectionFactory(
                    [FakeResponse(valid_tags), FakeResponse(json.dumps(payload).encode())]
                )
                self.assert_error(
                    code,
                    lambda factory=factory: calibration.fetch_live_embeddings(
                        self.corpus,
                        "127.0.0.1",
                        11_434,
                        "m",
                        connection_factory=factory,
                    ),
                )

        self.assert_error(
            "embedding_value_invalid",
            lambda: calibration.normalize_embeddings([[math.inf, 1.0]]),
        )
        self.assert_error(
            "embedding_dimension_invalid",
            lambda: calibration.normalize_embeddings([[1.0], [1.0, 2.0]]),
        )

    def test_provider_duplicate_keys_uppercase_digest_and_missing_capability_are_rejected(self) -> None:
        cases = [
            (
                b'{"models":[],"models":[]}',
                "duplicate_json_key",
            ),
            (
                json.dumps(
                    {
                        "models": [
                            {"name": "m", "digest": "AB" * 32, "capabilities": ["embedding"]}
                        ]
                    }
                ).encode(),
                "provider_model_digest_invalid",
            ),
            (
                json.dumps(
                    {
                        "models": [
                            {"name": "m", "digest": "ab" * 32, "capabilities": ["completion"]}
                        ]
                    }
                ).encode(),
                "provider_embedding_capability_missing",
            ),
        ]
        for tags, code in cases:
            with self.subTest(code=code):
                factory = FakeConnectionFactory([FakeResponse(tags)])
                self.assert_error(
                    code,
                    lambda factory=factory: calibration.fetch_live_embeddings(
                        self.corpus,
                        "127.0.0.1",
                        11_434,
                        "m",
                        connection_factory=factory,
                    ),
                )

    def test_report_has_no_content_vector_endpoint_or_provider_payload_leakage(self) -> None:
        report = self.offline_report()
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
        for entry in self.corpus.entries:
            self.assertNotIn(entry.content, serialized)
            self.assertNotIn(json.dumps(list(entry.offline_embedding)), serialized)
        forbidden_key_fragments = ("content", "embedding", "endpoint", "provider", "response")

        def inspect(value: Any) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    lowered = key.lower()
                    self.assertFalse(
                        any(fragment in lowered for fragment in forbidden_key_fragments),
                        key,
                    )
                    inspect(nested)
            elif isinstance(value, list):
                for nested in value:
                    inspect(nested)

        inspect(report)

    def test_cli_offline_emits_only_json_report(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = calibration.main(["--mode", "offline", "--corpus", str(self.fixture_path)])

        self.assertEqual(status, 0)
        self.assertEqual(stderr.getvalue(), "")
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["aggregate_metrics"]["best_f1"]["threshold_basis_points"], 9_511)
        self.assertEqual(report["mode"], "offline")

    def test_cli_failure_exposes_only_safe_error_code(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        secret = "payload-that-must-not-be-printed"
        malformed = tempfile.NamedTemporaryFile(suffix=secret + ".json", delete=False)
        malformed_path = Path(malformed.name)
        with malformed:
            malformed.write(b"{")
        self.addCleanup(malformed_path.unlink, missing_ok=True)

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = calibration.main(["--corpus", str(malformed_path)])

        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "calibration_error:corpus_json_invalid\n")
        self.assertNotIn(secret, stderr.getvalue())

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = calibration.main(["--port", secret])
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "calibration_error:arguments_invalid\n")
        self.assertNotIn(secret, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
