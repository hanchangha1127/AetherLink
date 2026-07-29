#!/usr/bin/env python3
"""Run the bounded exact-version Ollama compatibility matrix on macOS."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RUNNER_ID = "aetherlink-ollama-exact-version-runner-v1"
RECORDED_DATE = "2026-07-28"
EVIDENCE_BOUNDARY = (
    "official-darwin-archives-isolated-empty-catalog-no-model-download-"
    "or-model-backed-operation"
)
LIVE_TEST_FILTER = (
    "OllamaBackendTests.testLiveOllamaExactVersionEmptyCatalogCompatibility"
)
DEFAULT_OLLAMA_PORT = 11434
START_DEADLINE_SECONDS = 20.0
STOP_DEADLINE_SECONDS = 10.0
STOP_GRACEFUL_SECONDS = 8.0
STOP_FORCE_KILL_SECONDS = 2.0
COMMAND_DEADLINE_SECONDS = 300
SWIFT_TEST_LOG_BYTE_LIMIT = 4 * 1_024 * 1_024
NANOSECONDS_PER_SECOND = 1_000_000_000
START_DEADLINE_NS = int(START_DEADLINE_SECONDS * NANOSECONDS_PER_SECOND)
STOP_DEADLINE_NS = int(STOP_DEADLINE_SECONDS * NANOSECONDS_PER_SECOND)
STOP_GRACEFUL_NS = int(STOP_GRACEFUL_SECONDS * NANOSECONDS_PER_SECOND)
STOP_FORCE_KILL_NS = int(STOP_FORCE_KILL_SECONDS * NANOSECONDS_PER_SECOND)
DURATION_EVIDENCE_SCHEMA_VERSION = 1
DURATION_EVIDENCE_CLOCK = "time.monotonic_ns"
DURATION_EVIDENCE_ROUNDING = (
    "ceil-elapsed-nanoseconds-to-integer-milliseconds"
)
DURATION_EVIDENCE_PHASE_TOTAL_POLICY = "observed-only-no-v1-threshold"
DURATION_OBSERVATION_FIXTURE_ID = (
    "aetherlink-ollama-duration-observation-v1"
)
DURATION_OBSERVATION_RECORDED_DATE = "2026-07-29"
DURATION_OBSERVATION_EVIDENCE_BOUNDARY = (
    "one-local-macos-run-three-existing-model-profiles-two-exact-versions-"
    "cold-and-restart-observed-duration-not-sla-no-lm-studio-empty-catalog-"
    "semantic-quality-throughput-percentile-soak-or-cross-host-claim"
)
RECORDED_DURATION_OBSERVATION_SHA256 = (
    "aec82dc92f82f49681ed8854d0bea204f071004fd9aaa767678c0ed8290dfb13"
)
HTTP_RESPONSE_BYTE_LIMIT = 4 * 1_024 * 1_024
MAXIMUM_CATALOG_MODEL_COUNT = 256
SOURCE_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
MODEL_SNAPSHOT_DIRECTORY_NAME = "model-snapshot"
MODEL_BACKED_RUNNER_ID = "aetherlink-ollama-model-backed-runner-v1"
MODEL_BACKED_RECORDED_DATE = "2026-07-29"
MODEL_BACKED_EVIDENCE_BOUNDARY = (
    "official-darwin-archives-isolated-existing-chat-model-snapshot-"
    "no-model-download-no-retained-model-name-no-embedding-or-full-qualification"
)
MODEL_BACKED_LIVE_TEST_FILTER = (
    "OllamaBackendTests.testLiveOllamaExactVersionInstalledChatModelCompatibility"
)
MODEL_BACKED_RECORDED_SOURCE_VERSION = "0.32.4"
MODEL_BACKED_RECORDED_CATALOG_MODEL_COUNT = 4
MODEL_BACKED_RECORDED_BLOB_COUNT = 2_138
MODEL_BACKED_RECORDED_MANIFEST_BYTES = 460_486
MODEL_BACKED_RECORDED_MODEL_ARTIFACT_BYTES = 9_639_236_355
MODEL_BACKED_COPY_MODE = "clonefile-copy-on-write"
MODEL_BACKED_SELECTION_POLICY = (
    "smallest-unloaded-local-completion-capable-model"
)
MODEL_BACKED_TEMPORARY_PREFIX = "aetherlink-ollama-model-backed-"
LIVE_FAULT_INJECTION_FIXTURE_ID = (
    "aetherlink-ollama-chat-live-fault-injection-v1"
)
LIVE_FAULT_INJECTION_RECORDED_DATE = "2026-07-29"
LIVE_FAULT_INJECTION_EVIDENCE_BOUNDARY = (
    "one-local-macos-chat-process-lifecycle-three-faults-two-exact-versions-"
    "isolated-existing-model-snapshot-no-model-download-or-retained-payload-"
    "no-embedding-vision-power-loss-semantic-quality-concurrency-soak-sla-"
    "or-full-qualification-claim"
)
LIVE_FAULT_INJECTION_TEST_FILTER = (
    "OllamaBackendTests."
    "testLiveOllamaExactVersionProviderFaultInjection"
)
LIVE_FAULT_INJECTION_ENABLE_ENVIRONMENT_KEY = (
    "AETHERLINK_RUN_OLLAMA_LIVE_FAULT_INJECTION_TEST"
)
LIVE_FAULT_INJECTION_SCENARIO_ENVIRONMENT_KEY = (
    "AETHERLINK_OLLAMA_LIVE_FAULT_SCENARIO"
)
LIVE_FAULT_INJECTION_CONTROL_DIRECTORY_ENVIRONMENT_KEY = (
    "AETHERLINK_OLLAMA_LIVE_FAULT_CONTROL_DIRECTORY"
)
LIVE_FAULT_CONTROL_DIRECTORY_NAME = "fault-control"
LIVE_FAULT_FIRST_DELTA_MARKER_NAME = "first-provider-delta"
LIVE_FAULT_TEMPORARY_PREFIX = (
    "aetherlink-ollama-model-backed-fault-injection-"
)
LIVE_FAULT_IDS = (
    "provider-unavailable-before-request",
    "provider-exit-after-first-delta",
    "forced-stop-after-sigstop",
)
LIVE_FAULT_PRE_REQUEST_TERMINAL_SECONDS = 15
LIVE_FAULT_FIRST_DELTA_TRIGGER_SECONDS = 60
LIVE_FAULT_POST_TERMINAL_SECONDS = 15
LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS = 2
LIVE_FAULT_POLL_SECONDS = 0.01
RECORDED_LIVE_FAULT_INJECTION_SHA256 = (
    "226d7b367e2311ea4e664804bd614d93af59172d332e07afc5443f9c166c31cf"
)
RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256 = (
    "7fd12719dc9c3f229d6c1b5e00a26cef16f910185043e50a2aa19011d5d1e50d"
)
EMBEDDING_BACKED_RUNNER_ID = (
    "aetherlink-ollama-embedding-model-backed-runner-v1"
)
EMBEDDING_BACKED_RECORDED_DATE = "2026-07-29"
EMBEDDING_BACKED_EVIDENCE_BOUNDARY = (
    "official-darwin-archives-isolated-existing-embedding-model-snapshot-"
    "no-model-download-no-retained-model-name-or-vector-values-"
    "no-semantic-or-full-qualification"
)
EMBEDDING_BACKED_LIVE_TEST_FILTER = (
    "OllamaBackendTests."
    "testLiveOllamaExactVersionInstalledEmbeddingModelCompatibility"
)
EMBEDDING_BACKED_RECORDED_SOURCE_VERSION = "0.32.4"
EMBEDDING_BACKED_RECORDED_CATALOG_MODEL_COUNT = 4
EMBEDDING_BACKED_RECORDED_BLOB_COUNT = 4
EMBEDDING_BACKED_RECORDED_MANIFEST_BYTES = 741
EMBEDDING_BACKED_RECORDED_MODEL_ARTIFACT_BYTES = 621_875_917
EMBEDDING_BACKED_SELECTION_POLICY = (
    "smallest-unloaded-local-embedding-capable-model"
)
EMBEDDING_BACKED_TEMPORARY_PREFIX = (
    "aetherlink-ollama-embedding-model-backed-"
)
EMBEDDING_SEMANTIC_QUALITY_FIXTURE_ID = (
    "aetherlink-ollama-embedding-semantic-quality-v1"
)
EMBEDDING_SEMANTIC_QUALITY_RECORDED_DATE = "2026-07-29"
EMBEDDING_SEMANTIC_QUALITY_EVIDENCE_BOUNDARY = (
    "one-local-macos-existing-embedding-model-four-fixed-english-ranking-"
    "scenarios-two-permuted-batches-two-exact-ollama-versions-no-model-"
    "download-or-retained-model-name-input-vector-score-output-no-chat-"
    "vision-lm-studio-multilingual-retrieval-accuracy-soak-sla-or-full-"
    "qualification"
)
EMBEDDING_SEMANTIC_QUALITY_LIVE_TEST_FILTER = (
    "OllamaBackendTests."
    "testLiveOllamaExactVersionInstalledEmbeddingSemanticQuality"
)
EMBEDDING_SEMANTIC_QUALITY_RECOVERY_TEST_FILTER = (
    "OllamaBackendTests."
    "testLiveOllamaExactVersionInstalledEmbeddingSemanticRecovery"
)
EMBEDDING_SEMANTIC_QUALITY_ENABLE_ENVIRONMENT_KEY = (
    "AETHERLINK_RUN_OLLAMA_LIVE_EMBEDDING_SEMANTIC_QUALITY_TEST"
)
EMBEDDING_SEMANTIC_QUALITY_RECOVERY_ENVIRONMENT_KEY = (
    "AETHERLINK_RUN_OLLAMA_LIVE_EMBEDDING_SEMANTIC_RECOVERY_TEST"
)
EMBEDDING_SEMANTIC_QUALITY_TASK_SET_PATH_ENVIRONMENT_KEY = (
    "AETHERLINK_OLLAMA_EMBEDDING_SEMANTIC_TASK_SET_PATH"
)
EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA_ENVIRONMENT_KEY = (
    "AETHERLINK_OLLAMA_EMBEDDING_SEMANTIC_TASK_SET_SHA256"
)
EMBEDDING_SEMANTIC_QUALITY_TASK_SET_ID = (
    "aetherlink-ollama-embedding-semantic-task-set-v1"
)
EMBEDDING_SEMANTIC_QUALITY_TASK_SET_PATH = (
    ROOT
    / "shared"
    / "evaluation"
    / "ollama-embedding-semantic-quality-v1.json"
)
EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256 = (
    "e00f27d91a11f73f6f5f74eef9a4681b2dd2d70c45090456de17a5642b67023f"
)
EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_PATH = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaEmbeddingSemanticQualityTests.swift"
)
EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_SHA256 = (
    "4578680bf2e4548afcdbef4ba95022da81d15eecceb86acbfa088d068c6b0546"
)
EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_PATH = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaBackendTests.swift"
)
EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_SHA256 = (
    "e48dc934496c0473866d7c819cffa20bacd8411271628ed55e52be5ba34881c0"
)
EMBEDDING_SEMANTIC_QUALITY_TASK_SET_COPY_NAME = (
    "ollama-embedding-semantic-quality-v1.json"
)
EMBEDDING_SEMANTIC_QUALITY_TEMPORARY_PREFIX = (
    "aetherlink-ollama-embedding-semantic-quality-"
)
EMBEDDING_SEMANTIC_QUALITY_SCENARIO_COUNT = 4
EMBEDDING_SEMANTIC_QUALITY_TEXTS_PER_BATCH = 16
EMBEDDING_SEMANTIC_QUALITY_BATCH_CALLS_PER_VERSION = 2
EMBEDDING_SEMANTIC_QUALITY_EMBEDDING_COUNT_PER_VERSION = 32
EMBEDDING_SEMANTIC_QUALITY_MINIMUM_MARGIN_BASIS_POINTS = 200
EMBEDDING_SEMANTIC_QUALITY_MINIMUM_REPEAT_BASIS_POINTS = 9_990
EMBEDDING_SEMANTIC_QUALITY_ADAPTER_DEADLINE_SECONDS = 120
VISION_BACKED_RUNNER_ID = "aetherlink-ollama-vision-model-backed-runner-v1"
VISION_BACKED_RECORDED_DATE = "2026-07-29"
VISION_BACKED_EVIDENCE_BOUNDARY = (
    "official-darwin-archives-isolated-existing-vision-completion-model-snapshot-"
    "no-model-download-no-retained-model-name-input-image-or-output-"
    "no-semantic-or-full-qualification"
)
VISION_BACKED_LIVE_TEST_FILTER = (
    "OllamaBackendTests."
    "testLiveOllamaExactVersionInstalledVisionModelCompatibility"
)
VISION_BACKED_RECORDED_SOURCE_VERSION = "0.32.4"
VISION_BACKED_RECORDED_CATALOG_MODEL_COUNT = 4
VISION_BACKED_RECORDED_BLOB_COUNT = 997
VISION_BACKED_RECORDED_MANIFEST_BYTES = 207_279
VISION_BACKED_RECORDED_MODEL_ARTIFACT_BYTES = 21_909_210_142
VISION_BACKED_SELECTION_POLICY = (
    "smallest-unloaded-local-vision-and-completion-capable-model"
)
VISION_BACKED_TEMPORARY_PREFIX = "aetherlink-ollama-vision-model-backed-"

EXACT_CANDIDATES = (
    {
        "archiveSha256": (
            "5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"
        ),
        "archiveUrl": (
            "https://github.com/ollama/ollama/releases/download/"
            "v0.32.5/ollama-darwin.tgz"
        ),
        "version": "0.32.5",
    },
    {
        "archiveSha256": (
            "15383493225d5e7e7fda052dc103ab4d2835a22eabb41655f1d6302c6d1577bc"
        ),
        "archiveUrl": (
            "https://github.com/ollama/ollama/releases/download/"
            "v0.32.4/ollama-darwin.tgz"
        ),
        "version": "0.32.4",
    },
)


class MatrixFailure(RuntimeError):
    pass


class DuplicateJSONKeyError(ValueError):
    pass


@dataclass(frozen=True)
class SnapshotBlob:
    source_path: Path
    relative_path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SelectedLocalModel:
    provider_model_id: str
    manifest_digest: str
    reported_size_bytes: int
    manifest_source_path: Path
    manifest_relative_path: Path
    manifest_size_bytes: int
    blobs: tuple[SnapshotBlob, ...]
    capabilities: tuple[str, ...]

    @property
    def model_artifact_bytes(self) -> int:
        return sum(blob.size_bytes for blob in self.blobs)


@dataclass(frozen=True)
class ModelBackedProfile:
    runner_id: str
    recorded_date: str
    evidence_boundary: str
    live_test_filter: str
    enable_environment_key: str
    model_id_environment_key: str
    accepted_capabilities: frozenset[str]
    recorded_source_version: str
    recorded_catalog_model_count: int
    recorded_blob_count: int
    recorded_manifest_bytes: int
    recorded_model_artifact_bytes: int
    selection_policy: str
    temporary_prefix: str
    phase_success_keys: tuple[str, ...]
    required_capabilities: frozenset[str] = frozenset()


CHAT_MODEL_BACKED_PROFILE = ModelBackedProfile(
    runner_id=MODEL_BACKED_RUNNER_ID,
    recorded_date=MODEL_BACKED_RECORDED_DATE,
    evidence_boundary=MODEL_BACKED_EVIDENCE_BOUNDARY,
    live_test_filter=MODEL_BACKED_LIVE_TEST_FILTER,
    enable_environment_key="AETHERLINK_RUN_OLLAMA_LIVE_MODEL_BACKED_TEST",
    model_id_environment_key="AETHERLINK_OLLAMA_LIVE_CHAT_MODEL_ID",
    accepted_capabilities=frozenset({"chat", "completion"}),
    recorded_source_version=MODEL_BACKED_RECORDED_SOURCE_VERSION,
    recorded_catalog_model_count=MODEL_BACKED_RECORDED_CATALOG_MODEL_COUNT,
    recorded_blob_count=MODEL_BACKED_RECORDED_BLOB_COUNT,
    recorded_manifest_bytes=MODEL_BACKED_RECORDED_MANIFEST_BYTES,
    recorded_model_artifact_bytes=MODEL_BACKED_RECORDED_MODEL_ARTIFACT_BYTES,
    selection_policy=MODEL_BACKED_SELECTION_POLICY,
    temporary_prefix=MODEL_BACKED_TEMPORARY_PREFIX,
    phase_success_keys=(
        "adapterTestPassed",
        "catalogPopulated",
        "chatCancellationConfirmed",
        "chatCompleted",
        "installedStatePreserved",
        "modelUnloadConfirmed",
        "postCancellationRecoveryPassed",
    ),
)

EMBEDDING_MODEL_BACKED_PROFILE = ModelBackedProfile(
    runner_id=EMBEDDING_BACKED_RUNNER_ID,
    recorded_date=EMBEDDING_BACKED_RECORDED_DATE,
    evidence_boundary=EMBEDDING_BACKED_EVIDENCE_BOUNDARY,
    live_test_filter=EMBEDDING_BACKED_LIVE_TEST_FILTER,
    enable_environment_key=(
        "AETHERLINK_RUN_OLLAMA_LIVE_EMBEDDING_MODEL_BACKED_TEST"
    ),
    model_id_environment_key="AETHERLINK_OLLAMA_LIVE_EMBEDDING_MODEL_ID",
    accepted_capabilities=frozenset({"embed", "embedding"}),
    recorded_source_version=EMBEDDING_BACKED_RECORDED_SOURCE_VERSION,
    recorded_catalog_model_count=EMBEDDING_BACKED_RECORDED_CATALOG_MODEL_COUNT,
    recorded_blob_count=EMBEDDING_BACKED_RECORDED_BLOB_COUNT,
    recorded_manifest_bytes=EMBEDDING_BACKED_RECORDED_MANIFEST_BYTES,
    recorded_model_artifact_bytes=(
        EMBEDDING_BACKED_RECORDED_MODEL_ARTIFACT_BYTES
    ),
    selection_policy=EMBEDDING_BACKED_SELECTION_POLICY,
    temporary_prefix=EMBEDDING_BACKED_TEMPORARY_PREFIX,
    phase_success_keys=(
        "adapterTestPassed",
        "catalogPopulated",
        "embeddingBatchCompleted",
        "embeddingShapeValidated",
        "installedStatePreserved",
        "modelUnloadConfirmed",
    ),
)

VISION_MODEL_BACKED_PROFILE = ModelBackedProfile(
    runner_id=VISION_BACKED_RUNNER_ID,
    recorded_date=VISION_BACKED_RECORDED_DATE,
    evidence_boundary=VISION_BACKED_EVIDENCE_BOUNDARY,
    live_test_filter=VISION_BACKED_LIVE_TEST_FILTER,
    enable_environment_key=(
        "AETHERLINK_RUN_OLLAMA_LIVE_VISION_MODEL_BACKED_TEST"
    ),
    model_id_environment_key="AETHERLINK_OLLAMA_LIVE_VISION_MODEL_ID",
    accepted_capabilities=frozenset({"chat", "completion"}),
    required_capabilities=frozenset({"vision"}),
    recorded_source_version=VISION_BACKED_RECORDED_SOURCE_VERSION,
    recorded_catalog_model_count=VISION_BACKED_RECORDED_CATALOG_MODEL_COUNT,
    recorded_blob_count=VISION_BACKED_RECORDED_BLOB_COUNT,
    recorded_manifest_bytes=VISION_BACKED_RECORDED_MANIFEST_BYTES,
    recorded_model_artifact_bytes=(
        VISION_BACKED_RECORDED_MODEL_ARTIFACT_BYTES
    ),
    selection_policy=VISION_BACKED_SELECTION_POLICY,
    temporary_prefix=VISION_BACKED_TEMPORARY_PREFIX,
    phase_success_keys=(
        "adapterTestPassed",
        "catalogPopulated",
        "chatCancellationConfirmed",
        "imageAttachmentCompleted",
        "installedStatePreserved",
        "modelUnloadConfirmed",
        "postCancellationRecoveryPassed",
        "textChatCompleted",
    ),
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def strict_json_loads(data: bytes, *, label: str) -> object:
    try:
        return json.loads(
            data,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        DuplicateJSONKeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise MatrixFailure(f"{label} returned invalid JSON") from error


def validate_exact_json_value(
    value: object,
    expected: object,
    *,
    label: str,
) -> None:
    if type(value) is not type(expected):
        raise MatrixFailure(f"{label} had an unexpected JSON type")
    if isinstance(expected, dict):
        if set(value) != set(expected):
            raise MatrixFailure(f"{label} had an unexpected object shape")
        for key, expected_child in expected.items():
            validate_exact_json_value(
                value[key],
                expected_child,
                label=f"{label}.{key}",
            )
        return
    if isinstance(expected, list):
        if len(value) != len(expected):
            raise MatrixFailure(f"{label} had an unexpected array length")
        for index, expected_child in enumerate(expected):
            validate_exact_json_value(
                value[index],
                expected_child,
                label=f"{label}[{index}]",
            )
        return
    if value != expected:
        raise MatrixFailure(f"{label} differed from the recorded value")


def fetch_json(
    base_url: str,
    path: str,
    *,
    timeout: float,
    payload: dict[str, object] | None = None,
) -> object:
    request_data = None
    headers: dict[str, str] = {}
    method = "GET"
    if payload is not None:
        request_data = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(
        f"{base_url}/{path.lstrip('/')}",
        data=request_data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise MatrixFailure(f"{path} endpoint did not return HTTP 200")
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                parsed_content_length = int(content_length)
            except ValueError as error:
                raise MatrixFailure(
                    f"{path} endpoint returned an invalid Content-Length"
                ) from error
            if (
                parsed_content_length < 0
                or parsed_content_length > HTTP_RESPONSE_BYTE_LIMIT
            ):
                raise MatrixFailure(
                    f"{path} endpoint exceeded the response byte limit"
                )
        data = response.read(HTTP_RESPONSE_BYTE_LIMIT + 1)
    if len(data) > HTTP_RESPONSE_BYTE_LIMIT:
        raise MatrixFailure(f"{path} endpoint exceeded the response byte limit")
    return strict_json_loads(data, label=path)


def exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise MatrixFailure(f"{label} must be an exact integer")
    return value


def validate_embedding_semantic_quality_task_set(value: object) -> None:
    expected_root_keys = {
        "firstCall",
        "fixtureId",
        "minimumPositiveMarginBasisPoints",
        "minimumRepeatCosineBasisPoints",
        "scenarios",
        "schemaVersion",
        "secondCallOrder",
    }
    if not isinstance(value, dict) or set(value) != expected_root_keys:
        raise MatrixFailure(
            "embedding semantic-quality task set had an unexpected root shape"
        )
    if (
        value["fixtureId"] != EMBEDDING_SEMANTIC_QUALITY_TASK_SET_ID
        or exact_int(
            value["schemaVersion"],
            label="embedding semantic-quality task set schemaVersion",
        )
        != 1
        or exact_int(
            value["minimumPositiveMarginBasisPoints"],
            label="embedding semantic-quality minimum positive margin",
        )
        != EMBEDDING_SEMANTIC_QUALITY_MINIMUM_MARGIN_BASIS_POINTS
        or exact_int(
            value["minimumRepeatCosineBasisPoints"],
            label="embedding semantic-quality minimum repeat cosine",
        )
        != EMBEDDING_SEMANTIC_QUALITY_MINIMUM_REPEAT_BASIS_POINTS
    ):
        raise MatrixFailure(
            "embedding semantic-quality task set metadata was invalid"
        )

    first_call = value["firstCall"]
    if (
        not isinstance(first_call, list)
        or len(first_call) != EMBEDDING_SEMANTIC_QUALITY_TEXTS_PER_BATCH
    ):
        raise MatrixFailure(
            "embedding semantic-quality first batch shape was invalid"
        )
    input_ids: list[str] = []
    for row in first_call:
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "text"}
            or type(row["id"]) is not str
            or type(row["text"]) is not str
        ):
            raise MatrixFailure(
                "embedding semantic-quality input shape was invalid"
            )
        input_id = row["id"]
        text = row["text"]
        if (
            not 1 <= len(input_id.encode("utf-8")) <= 64
            or any(
                not (
                    "a" <= character <= "z"
                    or "0" <= character <= "9"
                    or character == "-"
                )
                for character in input_id
            )
            or not text.strip()
            or len(text.encode("utf-8")) > 512
            or any(ord(character) < 0x20 or ord(character) > 0x7E for character in text)
        ):
            raise MatrixFailure(
                "embedding semantic-quality input boundary was invalid"
            )
        input_ids.append(input_id)
    input_id_set = set(input_ids)
    if len(input_id_set) != EMBEDDING_SEMANTIC_QUALITY_TEXTS_PER_BATCH:
        raise MatrixFailure(
            "embedding semantic-quality input identifiers were not unique"
        )

    scenarios = value["scenarios"]
    if (
        not isinstance(scenarios, list)
        or len(scenarios) != EMBEDDING_SEMANTIC_QUALITY_SCENARIO_COUNT
    ):
        raise MatrixFailure(
            "embedding semantic-quality scenario shape was invalid"
        )
    expected_scenario_keys = {
        "hardNegativeId",
        "id",
        "positiveId",
        "queryId",
        "unrelatedNegativeId",
    }
    scenario_ids: list[str] = []
    referenced_ids: list[str] = []
    for scenario in scenarios:
        if (
            not isinstance(scenario, dict)
            or set(scenario) != expected_scenario_keys
            or any(type(scenario[key]) is not str for key in scenario)
        ):
            raise MatrixFailure(
                "embedding semantic-quality scenario row was invalid"
            )
        scenario_id = scenario["id"]
        if (
            not 1 <= len(scenario_id.encode("utf-8")) <= 64
            or any(
                not (
                    "a" <= character <= "z"
                    or "0" <= character <= "9"
                    or character == "-"
                )
                for character in scenario_id
            )
        ):
            raise MatrixFailure(
                "embedding semantic-quality scenario identifier was invalid"
            )
        role_ids = [
            scenario["queryId"],
            scenario["positiveId"],
            scenario["hardNegativeId"],
            scenario["unrelatedNegativeId"],
        ]
        if len(set(role_ids)) != 4:
            raise MatrixFailure(
                "embedding semantic-quality scenario roles were not unique"
            )
        scenario_ids.append(scenario_id)
        referenced_ids.extend(role_ids)
    if (
        len(set(scenario_ids)) != EMBEDDING_SEMANTIC_QUALITY_SCENARIO_COUNT
        or len(referenced_ids) != EMBEDDING_SEMANTIC_QUALITY_TEXTS_PER_BATCH
        or set(referenced_ids) != input_id_set
    ):
        raise MatrixFailure(
            "embedding semantic-quality scenario references were invalid"
        )

    second_call_order = value["secondCallOrder"]
    if (
        not isinstance(second_call_order, list)
        or len(second_call_order)
        != EMBEDDING_SEMANTIC_QUALITY_TEXTS_PER_BATCH
        or any(type(input_id) is not str for input_id in second_call_order)
        or len(set(second_call_order))
        != EMBEDDING_SEMANTIC_QUALITY_TEXTS_PER_BATCH
        or set(second_call_order) != input_id_set
        or second_call_order == input_ids
    ):
        raise MatrixFailure(
            "embedding semantic-quality second batch order was invalid"
        )


def recorded_embedding_semantic_quality_task_set_bytes() -> bytes:
    path = EMBEDDING_SEMANTIC_QUALITY_TASK_SET_PATH
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise MatrixFailure(
            "recorded embedding semantic-quality task set was unavailable"
        ) from error
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or resolved != path
        or metadata.st_size <= 0
        or metadata.st_size > 64 * 1_024
    ):
        raise MatrixFailure(
            "recorded embedding semantic-quality task set boundary was invalid"
        )
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != (
        EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256
    ):
        raise MatrixFailure(
            "recorded embedding semantic-quality task set bytes drifted"
        )
    value = strict_json_loads(
        data,
        label="recorded embedding semantic-quality task set",
    )
    validate_embedding_semantic_quality_task_set(value)
    return data


def assert_recorded_embedding_semantic_quality_swift_sources() -> None:
    for label, path, expected_sha256 in (
        (
            "semantic scorer",
            EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_PATH,
            EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_SHA256,
        ),
        (
            "live assertion",
            EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_PATH,
            EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_SHA256,
        ),
    ):
        try:
            metadata = path.lstat()
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise MatrixFailure(
                f"recorded embedding semantic-quality {label} source "
                "was unavailable"
            ) from error
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or resolved != path
            or metadata.st_size <= 0
            or metadata.st_size > 2 * 1_024 * 1_024
        ):
            raise MatrixFailure(
                f"recorded embedding semantic-quality {label} source "
                "boundary was invalid"
            )
        if file_sha256(path) != expected_sha256:
            raise MatrixFailure(
                f"recorded embedding semantic-quality {label} source "
                "bytes drifted"
            )


def create_embedding_semantic_quality_task_set_copy(
    candidate_root: Path,
) -> Path:
    data = recorded_embedding_semantic_quality_task_set_bytes()
    destination = (
        candidate_root / EMBEDDING_SEMANTIC_QUALITY_TASK_SET_COPY_NAME
    )
    if destination.exists() or destination.is_symlink():
        raise MatrixFailure(
            "embedding semantic-quality task set destination already existed"
        )
    destination.write_bytes(data)
    if (
        destination.is_symlink()
        or not destination.is_file()
        or destination.stat().st_size != len(data)
        or file_sha256(destination)
        != EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256
    ):
        raise MatrixFailure(
            "embedding semantic-quality task set copy was invalid"
        )
    return destination


def elapsed_milliseconds_ceil(start_ns: int, end_ns: int) -> int:
    if (
        type(start_ns) is not int
        or type(end_ns) is not int
        or start_ns < 0
        or end_ns < start_ns
    ):
        raise MatrixFailure("duration clock returned an invalid interval")
    return (end_ns - start_ns + 999_999) // 1_000_000


def duration_phase_result(
    *,
    phase_started_ns: int,
    ready_finished_ns: int,
    adapter_started_ns: int,
    adapter_finished_ns: int,
    stop_started_ns: int,
    stop_finished_ns: int,
    phase_finished_ns: int,
) -> dict[str, int]:
    result = {
        "adapterMs": elapsed_milliseconds_ceil(
            adapter_started_ns,
            adapter_finished_ns,
        ),
        "phaseTotalMs": elapsed_milliseconds_ceil(
            phase_started_ns,
            phase_finished_ns,
        ),
        "providerReadyMs": elapsed_milliseconds_ceil(
            phase_started_ns,
            ready_finished_ns,
        ),
        "stopMs": elapsed_milliseconds_ceil(
            stop_started_ns,
            stop_finished_ns,
        ),
    }
    validate_duration_phase(result, label="duration phase")
    return result


def validate_duration_phase(value: object, *, label: str) -> None:
    expected_keys = {
        "adapterMs",
        "phaseTotalMs",
        "providerReadyMs",
        "stopMs",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise MatrixFailure(f"{label} has an unexpected shape")
    durations = {
        key: exact_int(value[key], label=f"{label} {key}")
        for key in expected_keys
    }
    if durations["providerReadyMs"] > int(START_DEADLINE_SECONDS * 1_000):
        raise MatrixFailure(f"{label} provider ready duration exceeded the deadline")
    if durations["adapterMs"] > COMMAND_DEADLINE_SECONDS * 1_000:
        raise MatrixFailure(f"{label} adapter duration exceeded the deadline")
    if durations["stopMs"] > int(STOP_DEADLINE_SECONDS * 1_000):
        raise MatrixFailure(f"{label} stop duration exceeded the deadline")
    if durations["phaseTotalMs"] < max(
        durations["providerReadyMs"],
        durations["adapterMs"],
        durations["stopMs"],
    ):
        raise MatrixFailure(f"{label} total duration was internally inconsistent")
    component_sum = (
        durations["providerReadyMs"]
        + durations["adapterMs"]
        + durations["stopMs"]
    )
    if durations["phaseTotalMs"] + 2 < component_sum:
        raise MatrixFailure(
            f"{label} total duration was shorter than sequential components"
        )


def duration_evidence_result(
    versions: list[dict[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {
        "allBoundedOperationsWithinDeadline": True,
        "clock": DURATION_EVIDENCE_CLOCK,
        "deadlinesMs": {
            "adapter": COMMAND_DEADLINE_SECONDS * 1_000,
            "providerReady": int(START_DEADLINE_SECONDS * 1_000),
            "stop": int(STOP_DEADLINE_SECONDS * 1_000),
        },
        "phaseTotalPolicy": DURATION_EVIDENCE_PHASE_TOTAL_POLICY,
        "rounding": DURATION_EVIDENCE_ROUNDING,
        "sampleCountPerPhase": 1,
        "schemaVersion": DURATION_EVIDENCE_SCHEMA_VERSION,
        "versions": versions,
    }
    validate_duration_evidence(result)
    return result


def validate_duration_evidence(value: object) -> None:
    expected_root_keys = {
        "allBoundedOperationsWithinDeadline",
        "clock",
        "deadlinesMs",
        "phaseTotalPolicy",
        "rounding",
        "sampleCountPerPhase",
        "schemaVersion",
        "versions",
    }
    if not isinstance(value, dict) or set(value) != expected_root_keys:
        raise MatrixFailure("duration evidence has an unexpected root shape")
    if value["allBoundedOperationsWithinDeadline"] is not True:
        raise MatrixFailure("duration evidence deadline result must be true")
    if value["clock"] != DURATION_EVIDENCE_CLOCK:
        raise MatrixFailure("duration evidence clock was invalid")
    if value["rounding"] != DURATION_EVIDENCE_ROUNDING:
        raise MatrixFailure("duration evidence rounding was invalid")
    if value["phaseTotalPolicy"] != DURATION_EVIDENCE_PHASE_TOTAL_POLICY:
        raise MatrixFailure("duration evidence phase-total policy was invalid")
    if (
        exact_int(
            value["schemaVersion"],
            label="duration evidence schemaVersion",
        )
        != DURATION_EVIDENCE_SCHEMA_VERSION
        or exact_int(
            value["sampleCountPerPhase"],
            label="duration evidence sampleCountPerPhase",
            minimum=1,
        )
        != 1
    ):
        raise MatrixFailure("duration evidence schema metadata was invalid")

    deadlines = value["deadlinesMs"]
    expected_deadlines = {
        "adapter": COMMAND_DEADLINE_SECONDS * 1_000,
        "providerReady": int(START_DEADLINE_SECONDS * 1_000),
        "stop": int(STOP_DEADLINE_SECONDS * 1_000),
    }
    if not isinstance(deadlines, dict) or set(deadlines) != set(expected_deadlines):
        raise MatrixFailure("duration evidence deadlines had an unexpected shape")
    for key, expected in expected_deadlines.items():
        if exact_int(
            deadlines[key],
            label=f"duration evidence deadline {key}",
        ) != expected:
            raise MatrixFailure("duration evidence deadline value was invalid")

    versions = value["versions"]
    if type(versions) is not list or len(versions) != len(EXACT_CANDIDATES):
        raise MatrixFailure("duration evidence version count was invalid")
    for index, (version_row, candidate) in enumerate(
        zip(versions, EXACT_CANDIDATES)
    ):
        if (
            not isinstance(version_row, dict)
            or set(version_row) != {"coldStart", "restart", "version"}
            or version_row["version"] != candidate["version"]
        ):
            raise MatrixFailure(
                f"duration evidence version row {index} was invalid"
            )
        for phase in ("coldStart", "restart"):
            validate_duration_phase(
                version_row[phase],
                label=f"duration evidence version row {index} {phase}",
            )


def valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def canonical_model_name(value: str) -> str:
    return value[: -len(":latest")] if value.endswith(":latest") else value


def source_catalog_rows(base_url: str) -> tuple[dict[str, object], ...]:
    payload = fetch_json(base_url, "api/tags", timeout=3.0)
    if not isinstance(payload, dict) or set(payload) != {"models"}:
        raise MatrixFailure("source catalog returned an unexpected root shape")
    models = payload["models"]
    if (
        type(models) is not list
        or not 1 <= len(models) <= MAXIMUM_CATALOG_MODEL_COUNT
    ):
        raise MatrixFailure("source catalog model count is outside the supported range")

    rows: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for index, row in enumerate(models):
        if not isinstance(row, dict):
            raise MatrixFailure(f"source catalog row {index} must be an object")
        name = row.get("name") or row.get("model")
        digest = row.get("digest")
        size = exact_int(
            row.get("size"),
            label=f"source catalog row {index} size",
            minimum=1,
        )
        if (
            not isinstance(name, str)
            or not name
            or len(name.encode("utf-8")) > 1_024
            or any(ord(character) < 0x20 for character in name)
        ):
            raise MatrixFailure(f"source catalog row {index} has an invalid model name")
        if not valid_sha256(digest):
            raise MatrixFailure(f"source catalog row {index} has an invalid digest")
        canonical_name = canonical_model_name(name)
        if canonical_name in seen_names:
            raise MatrixFailure("source catalog contains duplicate model identities")
        seen_names.add(canonical_name)
        rows.append(
            {
                "digest": digest,
                "name": name,
                "size": size,
            }
        )
    return tuple(rows)


def source_running_model_names(base_url: str) -> frozenset[str]:
    payload = fetch_json(base_url, "api/ps", timeout=3.0)
    if not isinstance(payload, dict) or set(payload) != {"models"}:
        raise MatrixFailure("source running catalog returned an unexpected root shape")
    models = payload["models"]
    if type(models) is not list or len(models) > MAXIMUM_CATALOG_MODEL_COUNT:
        raise MatrixFailure("source running catalog exceeds the supported row limit")
    names: set[str] = set()
    for index, row in enumerate(models):
        if not isinstance(row, dict):
            raise MatrixFailure(
                f"source running catalog row {index} must be an object"
            )
        name = row.get("name") or row.get("model")
        if not isinstance(name, str) or not name:
            raise MatrixFailure(
                f"source running catalog row {index} has an invalid model name"
            )
        names.add(canonical_model_name(name))
    return frozenset(names)


def source_provider_version(base_url: str) -> str:
    payload = fetch_json(base_url, "api/version", timeout=3.0)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"version"}
        or not isinstance(payload["version"], str)
        or not payload["version"]
    ):
        raise MatrixFailure("source provider version payload was invalid")
    return payload["version"]


def model_capabilities(base_url: str, model_name: str) -> tuple[str, ...]:
    payload = fetch_json(
        base_url,
        "api/show",
        timeout=20.0,
        payload={"model": model_name},
    )
    if not isinstance(payload, dict):
        raise MatrixFailure("source model detail payload must be an object")
    raw_capabilities = payload.get("capabilities")
    if type(raw_capabilities) is not list or not raw_capabilities:
        raise MatrixFailure("source model detail payload has no capabilities")
    capabilities: list[str] = []
    for capability in raw_capabilities:
        if not isinstance(capability, str) or not capability.strip():
            raise MatrixFailure("source model capability must be a non-empty string")
        normalized = capability.strip().lower()
        if normalized not in capabilities:
            capabilities.append(normalized)
    return tuple(sorted(capabilities))


def find_manifest_by_digest(
    models_directory: Path,
    digest: str,
) -> tuple[Path, Path]:
    models_root = models_directory.resolve(strict=True)
    manifests_root = (models_root / "manifests").resolve(strict=True)
    try:
        manifests_root.relative_to(models_root)
    except ValueError as error:
        raise MatrixFailure("model manifests directory escaped the source store") from error

    matches: list[tuple[Path, Path]] = []
    for candidate in sorted(manifests_root.rglob("*")):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        if file_sha256(candidate) == digest:
            relative_path = candidate.resolve(strict=True).relative_to(models_root)
            matches.append((candidate, relative_path))
    if len(matches) != 1:
        raise MatrixFailure("selected model digest did not resolve to one manifest")
    return matches[0]


def manifest_blobs(
    models_directory: Path,
    manifest_path: Path,
) -> tuple[SnapshotBlob, ...]:
    payload = strict_json_loads(
        manifest_path.read_bytes(),
        label="selected model manifest",
    )
    if (
        not isinstance(payload, dict)
        or exact_int(
            payload.get("schemaVersion"),
            label="selected model manifest schemaVersion",
            minimum=2,
        )
        != 2
        or not isinstance(payload.get("config"), dict)
        or type(payload.get("layers")) is not list
    ):
        raise MatrixFailure("selected model manifest has an unsupported shape")
    descriptors = [payload["config"], *payload["layers"]]
    if not descriptors:
        raise MatrixFailure("selected model manifest has no descriptors")

    models_root = models_directory.resolve(strict=True)
    blobs_root = (models_root / "blobs").resolve(strict=True)
    try:
        blobs_root.relative_to(models_root)
    except ValueError as error:
        raise MatrixFailure("model blobs directory escaped the source store") from error

    blobs_by_digest: dict[str, SnapshotBlob] = {}
    for index, descriptor in enumerate(descriptors):
        if not isinstance(descriptor, dict):
            raise MatrixFailure(f"model descriptor {index} must be an object")
        digest_value = descriptor.get("digest")
        size = exact_int(
            descriptor.get("size"),
            label=f"model descriptor {index} size",
            minimum=1,
        )
        if (
            not isinstance(digest_value, str)
            or not digest_value.startswith("sha256:")
            or not valid_sha256(digest_value[len("sha256:") :])
        ):
            raise MatrixFailure(f"model descriptor {index} has an invalid digest")
        digest_sha256 = digest_value[len("sha256:") :]
        relative_path = Path("blobs") / digest_value.replace(":", "-", 1)
        source_path = models_root / relative_path
        if (
            source_path.is_symlink()
            or not source_path.is_file()
            or source_path.stat().st_size != size
        ):
            raise MatrixFailure(f"model descriptor {index} does not match a local blob")
        if file_sha256(source_path) != digest_sha256:
            raise MatrixFailure(
                f"model descriptor {index} blob content digest did not match"
            )
        existing = blobs_by_digest.get(digest_value)
        blob = SnapshotBlob(
            source_path=source_path,
            relative_path=relative_path,
            size_bytes=size,
            sha256=digest_sha256,
        )
        if existing is not None and existing != blob:
            raise MatrixFailure("duplicate model descriptor has conflicting metadata")
        blobs_by_digest[digest_value] = blob
    return tuple(
        blobs_by_digest[digest]
        for digest in sorted(blobs_by_digest)
    )


def select_source_model(
    models_directory: Path,
    *,
    profile: ModelBackedProfile,
    base_url: str = SOURCE_OLLAMA_BASE_URL,
) -> SelectedLocalModel:
    running_names = source_running_model_names(base_url)
    rows = sorted(
        source_catalog_rows(base_url),
        key=lambda row: (
            exact_int(row["size"], label="catalog size", minimum=1),
            str(row["digest"]),
        ),
    )
    for row in rows:
        name = str(row["name"])
        if canonical_model_name(name) in running_names:
            continue
        capabilities = model_capabilities(base_url, name)
        capability_set = frozenset(capabilities)
        if (
            not profile.accepted_capabilities.intersection(capability_set)
            or not profile.required_capabilities.issubset(capability_set)
        ):
            continue
        digest = str(row["digest"])
        try:
            manifest_path, manifest_relative_path = find_manifest_by_digest(
                models_directory,
                digest,
            )
            blobs = manifest_blobs(models_directory, manifest_path)
        except MatrixFailure:
            continue
        selected = SelectedLocalModel(
            provider_model_id=name,
            manifest_digest=digest,
            reported_size_bytes=exact_int(
                row["size"],
                label="selected model reported size",
                minimum=1,
            ),
            manifest_source_path=manifest_path,
            manifest_relative_path=manifest_relative_path,
            manifest_size_bytes=manifest_path.stat().st_size,
            blobs=blobs,
            capabilities=capabilities,
        )
        if selected.model_artifact_bytes != selected.reported_size_bytes:
            continue
        return selected
    raise MatrixFailure(
        "no unloaded local model matched the requested capability and source snapshot"
    )


def select_source_chat_model(
    models_directory: Path,
    *,
    base_url: str = SOURCE_OLLAMA_BASE_URL,
) -> SelectedLocalModel:
    return select_source_model(
        models_directory,
        profile=CHAT_MODEL_BACKED_PROFILE,
        base_url=base_url,
    )


def select_source_embedding_model(
    models_directory: Path,
    *,
    base_url: str = SOURCE_OLLAMA_BASE_URL,
) -> SelectedLocalModel:
    return select_source_model(
        models_directory,
        profile=EMBEDDING_MODEL_BACKED_PROFILE,
        base_url=base_url,
    )


def select_source_vision_model(
    models_directory: Path,
    *,
    base_url: str = SOURCE_OLLAMA_BASE_URL,
) -> SelectedLocalModel:
    return select_source_model(
        models_directory,
        profile=VISION_MODEL_BACKED_PROFILE,
        base_url=base_url,
    )


def clone_file_copy_on_write(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    libc = ctypes.CDLL(None, use_errno=True)
    clonefile = libc.clonefile
    clonefile.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]
    clonefile.restype = ctypes.c_int
    result = clonefile(
        os.fsencode(source),
        os.fsencode(destination),
        0,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise MatrixFailure(
            "copy-on-write model snapshot failed: "
            f"{os.strerror(error_number)}"
        )
    source_stat = source.stat()
    destination_stat = destination.stat()
    if (
        not stat.S_ISREG(destination_stat.st_mode)
        or destination_stat.st_size != source_stat.st_size
        or (
            destination_stat.st_dev == source_stat.st_dev
            and destination_stat.st_ino == source_stat.st_ino
        )
    ):
        raise MatrixFailure("copy-on-write model snapshot identity was invalid")


def create_model_snapshot(
    selected: SelectedLocalModel,
    destination: Path,
) -> tuple[tuple[str, int, str], ...]:
    destination.mkdir()
    files = (
        (
            selected.manifest_source_path,
            selected.manifest_relative_path,
            selected.manifest_size_bytes,
            selected.manifest_digest,
        ),
        *(
            (
                blob.source_path,
                blob.relative_path,
                blob.size_bytes,
                blob.sha256,
            )
            for blob in selected.blobs
        ),
    )
    for source, relative_path, expected_size, _expected_sha256 in files:
        target = destination / relative_path
        clone_file_copy_on_write(source, target)
        if target.stat().st_size != expected_size:
            raise MatrixFailure("model snapshot file size changed during cloning")
    return tuple(
        sorted(
            (
                relative_path.as_posix(),
                expected_size,
                expected_sha256,
            )
            for _, relative_path, expected_size, expected_sha256 in files
        )
    )


def model_snapshot_state(root: Path) -> tuple[tuple[str, int, str], ...]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise MatrixFailure("model snapshot contains a symbolic link")
        if not path.is_file():
            continue
        metadata = path.stat()
        rows.append(
            (
                path.relative_to(root).as_posix(),
                metadata.st_size,
                file_sha256(path),
            )
        )
    return tuple(rows)


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    label: str,
    redactions: tuple[str, ...] = (),
    timeout_seconds: float = COMMAND_DEADLINE_SECONDS,
) -> None:
    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or not 0 < timeout_seconds <= COMMAND_DEADLINE_SECONDS
    ):
        raise MatrixFailure("command timeout was outside the bounded range")
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        if any(redactions):
            bounded_output = "[selected-model subprocess output suppressed]"
        else:
            bounded_output = result.stdout[-2_000:].strip()
        detail = f": {bounded_output}" if bounded_output else ""
        raise MatrixFailure(
            f"{label} failed with exit code {result.returncode}{detail}"
        )


def download_archive(candidate: dict[str, str], destination: Path) -> None:
    curl = shutil.which("curl")
    if curl is None:
        raise MatrixFailure("curl is required")
    run_checked(
        [
            curl,
            "-fsSL",
            "--retry",
            "3",
            "--connect-timeout",
            "15",
            "--max-time",
            str(COMMAND_DEADLINE_SECONDS),
            "-o",
            str(destination),
            candidate["archiveUrl"],
        ],
        cwd=ROOT,
        environment=os.environ.copy(),
        label=f"Ollama {candidate['version']} archive download",
    )
    actual_sha256 = file_sha256(destination)
    if actual_sha256 != candidate["archiveSha256"]:
        raise MatrixFailure("downloaded archive SHA-256 did not match")


def reserve_unique_port() -> int:
    for _ in range(10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = int(listener.getsockname()[1])
        if port != DEFAULT_OLLAMA_PORT:
            return port
    raise MatrixFailure("could not reserve a non-default loopback port")


def fetch_version(base_url: str, timeout: float) -> str:
    request = urllib.request.Request(f"{base_url}/api/version", method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise MatrixFailure("version endpoint did not return HTTP 200")
        payload = json.loads(response.read())
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
        raise MatrixFailure("version endpoint returned an unexpected payload")
    return payload["version"]


def endpoint_is_available(
    base_url: str,
    *,
    timeout: float = 0.5,
) -> bool:
    try:
        fetch_version(base_url, timeout=timeout)
        return True
    except (
        MatrixFailure,
        OSError,
        TimeoutError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ):
        return False


def wait_until_ready(
    base_url: str,
    expected_version: str,
    *,
    deadline_ns: int | None = None,
) -> None:
    if deadline_ns is None:
        deadline_ns = time.monotonic_ns() + START_DEADLINE_NS
    while True:
        remaining_ns = deadline_ns - time.monotonic_ns()
        if remaining_ns <= 0:
            break
        try:
            observed_version = fetch_version(
                base_url,
                timeout=min(
                    0.5,
                    remaining_ns / NANOSECONDS_PER_SECOND,
                ),
            )
        except (
            MatrixFailure,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ):
            sleep_seconds = min(
                0.1,
                max(
                    0.0,
                    (deadline_ns - time.monotonic_ns())
                    / NANOSECONDS_PER_SECOND,
                ),
            )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            continue
        if time.monotonic_ns() > deadline_ns:
            raise MatrixFailure(
                "provider became ready after the absolute deadline"
            )
        if observed_version != expected_version:
            raise MatrixFailure("provider version did not match the exact candidate")
        return
    raise MatrixFailure("provider did not become ready before the deadline")


def signal_provider_process(
    process: subprocess.Popen[bytes],
    provider_signal: int,
    *,
    signal_process_group: bool,
) -> None:
    if signal_process_group:
        os.killpg(process.pid, provider_signal)
    elif provider_signal == signal.SIGTERM:
        process.terminate()
    elif provider_signal == signal.SIGKILL:
        process.kill()
    else:
        process.send_signal(provider_signal)


def stop_provider(
    process: subprocess.Popen[bytes],
    base_url: str,
    *,
    signal_process_group: bool = False,
) -> None:
    if STOP_GRACEFUL_NS + STOP_FORCE_KILL_NS != STOP_DEADLINE_NS:
        raise MatrixFailure("provider stop sub-budgets do not match the deadline")
    started_at_ns = time.monotonic_ns()
    graceful_deadline_ns = started_at_ns + STOP_GRACEFUL_NS
    deadline_ns = started_at_ns + STOP_DEADLINE_NS
    forced_termination = False
    if process.poll() is None:
        signal_provider_process(
            process,
            signal.SIGTERM,
            signal_process_group=signal_process_group,
        )
        graceful_remaining_ns = graceful_deadline_ns - time.monotonic_ns()
        if graceful_remaining_ns <= 0:
            forced_termination = True
            signal_provider_process(
                process,
                signal.SIGKILL,
                signal_process_group=signal_process_group,
            )
        else:
            try:
                process.wait(
                    timeout=(
                        graceful_remaining_ns
                        / NANOSECONDS_PER_SECOND
                    )
                )
            except subprocess.TimeoutExpired:
                forced_termination = True
                signal_provider_process(
                    process,
                    signal.SIGKILL,
                    signal_process_group=signal_process_group,
                )
        if forced_termination:
            force_remaining_ns = deadline_ns - time.monotonic_ns()
            if force_remaining_ns <= 0:
                raise MatrixFailure(
                    "provider stop exceeded the absolute deadline"
                )
            try:
                process.wait(
                    timeout=force_remaining_ns / NANOSECONDS_PER_SECOND
                )
            except subprocess.TimeoutExpired as error:
                raise MatrixFailure(
                    "provider stop exceeded the absolute deadline"
                ) from error
            if time.monotonic_ns() > deadline_ns:
                raise MatrixFailure(
                    "provider stop exceeded the absolute deadline"
                )
            raise MatrixFailure("provider required forced termination")
    remaining_ns = deadline_ns - time.monotonic_ns()
    if remaining_ns <= 0:
        raise MatrixFailure("provider stop exceeded the absolute deadline")
    if endpoint_is_available(
        base_url,
        timeout=min(
            0.5,
            remaining_ns / NANOSECONDS_PER_SECOND,
        ),
    ):
        raise MatrixFailure("provider endpoint remained available after stop")
    if time.monotonic_ns() > deadline_ns:
        raise MatrixFailure("provider stop exceeded the absolute deadline")


def run_adapter_test(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "AETHERLINK_OLLAMA_LIVE_ARCHIVE_SHA256": candidate[
                "archiveSha256"
            ],
            "AETHERLINK_OLLAMA_LIVE_BASE_URL": base_url,
            "AETHERLINK_OLLAMA_LIVE_EXPECTED_VERSION": candidate["version"],
            "AETHERLINK_OLLAMA_LIVE_MODELS_DIRECTORY": str(models_directory),
            "AETHERLINK_RUN_OLLAMA_LIVE_COMPATIBILITY_TEST": "1",
        }
    )
    run_checked(
        ["swift", "test", "--filter", LIVE_TEST_FILTER],
        cwd=ROOT,
        environment=environment,
        label=f"Ollama {candidate['version']} adapter test",
    )


def selected_model_backed_adapter_environment(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: SelectedLocalModel,
    profile: ModelBackedProfile,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "AETHERLINK_OLLAMA_LIVE_ARCHIVE_SHA256": candidate[
                "archiveSha256"
            ],
            "AETHERLINK_OLLAMA_LIVE_BASE_URL": base_url,
            profile.model_id_environment_key: selected.provider_model_id,
            "AETHERLINK_OLLAMA_LIVE_EXPECTED_CATALOG_COUNT": "1",
            "AETHERLINK_OLLAMA_LIVE_EXPECTED_VERSION": candidate["version"],
            "AETHERLINK_OLLAMA_LIVE_MODELS_DIRECTORY": str(models_directory),
            profile.enable_environment_key: "1",
        }
    )
    return environment


def embedding_semantic_quality_adapter_environment(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: SelectedLocalModel,
    task_set_path: Path,
) -> dict[str, str]:
    if (
        not task_set_path.is_file()
        or task_set_path.is_symlink()
        or task_set_path.name
        != EMBEDDING_SEMANTIC_QUALITY_TASK_SET_COPY_NAME
        or file_sha256(task_set_path)
        != EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256
    ):
        raise MatrixFailure(
            "embedding semantic-quality task set copy was invalid"
        )
    environment = selected_model_backed_adapter_environment(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        profile=EMBEDDING_MODEL_BACKED_PROFILE,
    )
    environment.pop(
        EMBEDDING_MODEL_BACKED_PROFILE.enable_environment_key,
        None,
    )
    environment.update(
        {
            EMBEDDING_SEMANTIC_QUALITY_ENABLE_ENVIRONMENT_KEY: "1",
            EMBEDDING_SEMANTIC_QUALITY_TASK_SET_PATH_ENVIRONMENT_KEY: str(
                task_set_path
            ),
            EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA_ENVIRONMENT_KEY: (
                EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256
            ),
        }
    )
    return environment


def run_selected_model_backed_adapter_test(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: SelectedLocalModel,
    profile: ModelBackedProfile,
) -> None:
    environment = selected_model_backed_adapter_environment(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        profile=profile,
    )
    run_checked(
        ["swift", "test", "--filter", profile.live_test_filter],
        cwd=ROOT,
        environment=environment,
        label=(
            f"Ollama {candidate['version']} "
            f"{profile.runner_id} adapter test"
        ),
        redactions=(selected.provider_model_id,),
    )


def run_model_backed_adapter_test(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: SelectedLocalModel,
) -> None:
    run_selected_model_backed_adapter_test(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        profile=CHAT_MODEL_BACKED_PROFILE,
    )


def process_group_is_available(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS can transiently report EPERM while a signalled group is still
        # being torn down. Treat it as present so the bounded readback remains
        # fail-closed until the kernel reports ESRCH.
        return True
    return True


def wait_for_process_group_exit(
    process_group_id: int,
    *,
    deadline_ns: int,
) -> None:
    while process_group_is_available(process_group_id):
        remaining_ns = deadline_ns - time.monotonic_ns()
        if remaining_ns <= 0:
            raise MatrixFailure(
                "runner-owned process group remained after the deadline"
            )
        time.sleep(
            min(
                LIVE_FAULT_POLL_SECONDS,
                remaining_ns / NANOSECONDS_PER_SECOND,
            )
        )


def kill_process_group_and_wait(
    process: subprocess.Popen[bytes],
    *,
    label: str,
) -> None:
    process_group_id = process.pid
    deadline_ns = (
        time.monotonic_ns()
        + LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS * NANOSECONDS_PER_SECOND
    )
    if process_group_is_available(process_group_id):
        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        remaining_ns = deadline_ns - time.monotonic_ns()
        if remaining_ns <= 0:
            raise MatrixFailure(f"{label} did not exit before the deadline")
        try:
            process.wait(
                timeout=remaining_ns / NANOSECONDS_PER_SECOND
            )
        except subprocess.TimeoutExpired as error:
            raise MatrixFailure(
                f"{label} did not exit before the deadline"
            ) from error
    wait_for_process_group_exit(
        process_group_id,
        deadline_ns=deadline_ns,
    )


def inject_process_group_sigkill(
    process: subprocess.Popen[bytes],
    *,
    label: str,
) -> None:
    process_group_id = process.pid
    if (
        process.poll() is not None
        or not process_group_is_available(process_group_id)
    ):
        raise MatrixFailure(f"{label} exited before the injected signal")
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError as error:
        raise MatrixFailure(
            f"{label} exited before the injected signal"
        ) from error
    deadline_ns = (
        time.monotonic_ns()
        + LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS * NANOSECONDS_PER_SECOND
    )
    remaining_ns = deadline_ns - time.monotonic_ns()
    if remaining_ns <= 0:
        raise MatrixFailure(f"{label} did not exit before the deadline")
    try:
        return_code = process.wait(
            timeout=remaining_ns / NANOSECONDS_PER_SECOND
        )
    except subprocess.TimeoutExpired as error:
        raise MatrixFailure(
            f"{label} did not exit before the deadline"
        ) from error
    if return_code != -signal.SIGKILL:
        raise MatrixFailure(
            f"{label} was not terminated by the injected signal"
        )
    wait_for_process_group_exit(
        process_group_id,
        deadline_ns=deadline_ns,
    )


def run_fault_swift_test(
    *,
    environment: dict[str, str],
    test_filter: str,
    log_path: Path,
    label: str,
    timeout_seconds: float,
) -> None:
    process: subprocess.Popen[bytes] | None = None
    try:
        with log_path.open("wb") as log_stream:
            process = subprocess.Popen(
                ["swift", "test", "--filter", test_filter],
                cwd=ROOT,
                env=environment,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            raise MatrixFailure(
                f"{label} did not finish before the deadline"
            ) from error
        if return_code != 0:
            raise MatrixFailure(f"{label} did not pass")
        wait_for_process_group_exit(
            process.pid,
            deadline_ns=(
                time.monotonic_ns()
                + LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS
                * NANOSECONDS_PER_SECOND
            ),
        )
        assert_exact_swift_test_execution(
            log_path=log_path,
            test_filter=test_filter,
            label=label,
        )
    except Exception as original_error:
        if process is not None and (
            process.poll() is None
            or process_group_is_available(process.pid)
        ):
            try:
                kill_process_group_and_wait(
                    process,
                    label=label,
                )
            except Exception as cleanup_error:
                raise cleanup_error
        raise original_error


def assert_exact_swift_test_execution(
    *,
    log_path: Path,
    test_filter: str,
    label: str,
) -> None:
    expected_suite, separator, expected_method = test_filter.rpartition(".")
    if (
        not separator
        or not expected_suite
        or not expected_method
        or any(character.isspace() for character in test_filter)
    ):
        raise MatrixFailure(f"{label} used an invalid exact test filter")
    try:
        metadata = log_path.lstat()
        if (
            log_path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > SWIFT_TEST_LOG_BYTE_LIMIT
        ):
            raise MatrixFailure(f"{label} produced an invalid test log")
        log_text = log_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise MatrixFailure(f"{label} test log could not be read") from error

    expected_identifier = (expected_suite.rsplit(".", 1)[-1], expected_method)
    started: list[tuple[str, str]] = []
    passed: list[tuple[str, str]] = []
    prefix = "Test Case '-["
    started_suffix = "]' started."
    passed_marker = "]' passed ("
    for line in log_text.splitlines():
        payload: str | None = None
        event: list[tuple[str, str]] | None = None
        if line.startswith(prefix) and line.endswith(started_suffix):
            payload = line[len(prefix) : -len(started_suffix)]
            event = started
        elif line.startswith(prefix) and passed_marker in line:
            payload = line[len(prefix) : line.index(passed_marker)]
            event = passed
        if payload is None or event is None:
            continue
        suite, event_separator, method = payload.rpartition(" ")
        if not event_separator:
            raise MatrixFailure(f"{label} produced an invalid test event")
        event.append((suite.rsplit(".", 1)[-1], method))

    if started != [expected_identifier] or passed != [expected_identifier]:
        raise MatrixFailure(
            f"{label} did not execute exactly one matching test case"
        )


def start_live_fault_provider(
    *,
    binary: Path,
    extracted: Path,
    models_directory: Path,
    candidate_root: Path,
    log_name: str,
    port: int,
    base_url: str,
    expected_version: str,
) -> subprocess.Popen[bytes]:
    server_environment = os.environ.copy()
    server_environment.update(
        {
            "OLLAMA_HOST": f"127.0.0.1:{port}",
            "OLLAMA_MODELS": str(models_directory),
        }
    )
    log_path = candidate_root / f"{log_name}.log"
    ready_deadline_ns = time.monotonic_ns() + START_DEADLINE_NS
    with log_path.open("wb") as log_stream:
        process = subprocess.Popen(
            [str(binary), "serve"],
            cwd=extracted,
            env=server_environment,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        wait_until_ready(
            base_url,
            expected_version,
            deadline_ns=ready_deadline_ns,
        )
    except Exception:
        kill_process_group_and_wait(
            process,
            label="fault-injection provider",
        )
        raise
    return process


def live_fault_adapter_environment(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: SelectedLocalModel,
    scenario: str,
    control_directory: Path | None = None,
) -> dict[str, str]:
    if scenario not in LIVE_FAULT_IDS[:2]:
        raise MatrixFailure("adapter fault scenario was not recognized")
    environment = selected_model_backed_adapter_environment(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        profile=CHAT_MODEL_BACKED_PROFILE,
    )
    environment.update(
        {
            LIVE_FAULT_INJECTION_ENABLE_ENVIRONMENT_KEY: "1",
            LIVE_FAULT_INJECTION_SCENARIO_ENVIRONMENT_KEY: scenario,
        }
    )
    if control_directory is not None:
        environment[
            LIVE_FAULT_INJECTION_CONTROL_DIRECTORY_ENVIRONMENT_KEY
        ] = str(control_directory)
    return environment


def run_provider_unavailable_adapter_fault(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    candidate_root: Path,
    selected: SelectedLocalModel,
) -> None:
    environment = live_fault_adapter_environment(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        scenario=LIVE_FAULT_IDS[0],
    )
    run_fault_swift_test(
        environment=environment,
        test_filter=LIVE_FAULT_INJECTION_TEST_FILTER,
        log_path=candidate_root / "provider-unavailable-adapter.log",
        label="Ollama unavailable-before-request adapter fault",
        timeout_seconds=LIVE_FAULT_PRE_REQUEST_TERMINAL_SECONDS,
    )


def wait_for_first_delta_marker(
    marker_path: Path,
    *,
    provider_process: subprocess.Popen[bytes],
    adapter_process: subprocess.Popen[bytes],
    deadline_ns: int,
) -> None:
    while True:
        if marker_path.exists():
            metadata = marker_path.lstat()
            if (
                marker_path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size != 0
            ):
                raise MatrixFailure(
                    "first-delta marker did not have the exact empty-file shape"
                )
            if (
                adapter_process.poll() is not None
                or not process_group_is_available(adapter_process.pid)
            ):
                raise MatrixFailure(
                    "adapter fault probe exited at the first-delta marker"
                )
            if (
                provider_process.poll() is not None
                or not process_group_is_available(provider_process.pid)
            ):
                raise MatrixFailure(
                    "provider exited before the runner injected the fault"
                )
            return
        if adapter_process.poll() is not None:
            raise MatrixFailure(
                "adapter fault probe exited before the first-delta marker"
            )
        if provider_process.poll() is not None:
            raise MatrixFailure(
                "provider exited before the runner injected the fault"
            )
        remaining_ns = deadline_ns - time.monotonic_ns()
        if remaining_ns <= 0:
            raise MatrixFailure(
                "first-delta marker was not observed before the deadline"
            )
        time.sleep(
            min(
                LIVE_FAULT_POLL_SECONDS,
                remaining_ns / NANOSECONDS_PER_SECOND,
            )
        )


def run_provider_exit_after_first_delta_fault(
    *,
    provider_process: subprocess.Popen[bytes],
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    candidate_root: Path,
    selected: SelectedLocalModel,
) -> None:
    control_directory = candidate_root / LIVE_FAULT_CONTROL_DIRECTORY_NAME
    control_directory.mkdir()
    marker_path = control_directory / LIVE_FAULT_FIRST_DELTA_MARKER_NAME
    environment = live_fault_adapter_environment(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        scenario=LIVE_FAULT_IDS[1],
        control_directory=control_directory,
    )
    adapter_log_path = candidate_root / "provider-exit-adapter.log"
    adapter_process: subprocess.Popen[bytes] | None = None
    try:
        with adapter_log_path.open("wb") as log_stream:
            adapter_process = subprocess.Popen(
                [
                    "swift",
                    "test",
                    "--filter",
                    LIVE_FAULT_INJECTION_TEST_FILTER,
                ],
                cwd=ROOT,
                env=environment,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        wait_for_first_delta_marker(
            marker_path,
            provider_process=provider_process,
            adapter_process=adapter_process,
            deadline_ns=(
                time.monotonic_ns()
                + LIVE_FAULT_FIRST_DELTA_TRIGGER_SECONDS
                * NANOSECONDS_PER_SECOND
            ),
        )
        inject_process_group_sigkill(
            provider_process,
            label="fault-injection provider",
        )
        try:
            return_code = adapter_process.wait(
                timeout=LIVE_FAULT_POST_TERMINAL_SECONDS
            )
        except subprocess.TimeoutExpired as error:
            raise MatrixFailure(
                "adapter did not report provider loss before the deadline"
            ) from error
        if return_code != 0:
            raise MatrixFailure(
                "adapter did not accept the injected in-flight provider loss"
            )
        wait_for_process_group_exit(
            adapter_process.pid,
            deadline_ns=(
                time.monotonic_ns()
                + LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS
                * NANOSECONDS_PER_SECOND
            ),
        )
        if endpoint_is_available(base_url):
            raise MatrixFailure(
                "provider endpoint remained available after injected exit"
            )
    finally:
        if adapter_process is not None and (
            adapter_process.poll() is None
            or process_group_is_available(adapter_process.pid)
        ):
            kill_process_group_and_wait(
                adapter_process,
                label="fault-injection adapter",
            )


def ensure_fault_provider_stopped(
    process: subprocess.Popen[bytes],
    base_url: str,
) -> None:
    wait_for_process_group_exit(
        process.pid,
        deadline_ns=(
            time.monotonic_ns()
            + LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS
            * NANOSECONDS_PER_SECOND
        ),
    )
    if endpoint_is_available(base_url):
        raise MatrixFailure(
            "provider endpoint remained available after the injected fault"
        )


def run_live_fault_scenario(
    *,
    fault_id: str,
    binary: Path,
    extracted: Path,
    models_directory: Path,
    candidate_root: Path,
    port: int,
    base_url: str,
    candidate: dict[str, str],
    selected: SelectedLocalModel,
    initial_snapshot_state: tuple[tuple[str, int, str], ...],
) -> None:
    if fault_id not in LIVE_FAULT_IDS:
        raise MatrixFailure("live fault identifier was not recognized")
    process = start_live_fault_provider(
        binary=binary,
        extracted=extracted,
        models_directory=models_directory,
        candidate_root=candidate_root,
        log_name=f"{fault_id}-fault",
        port=port,
        base_url=base_url,
        expected_version=candidate["version"],
    )
    scenario_error: Exception | None = None
    try:
        if fault_id == LIVE_FAULT_IDS[0]:
            stop_provider(
                process,
                base_url,
                signal_process_group=True,
            )
            ensure_fault_provider_stopped(process, base_url)
            run_provider_unavailable_adapter_fault(
                base_url=base_url,
                candidate=candidate,
                models_directory=models_directory,
                candidate_root=candidate_root,
                selected=selected,
            )
        elif fault_id == LIVE_FAULT_IDS[1]:
            run_provider_exit_after_first_delta_fault(
                provider_process=process,
                base_url=base_url,
                candidate=candidate,
                models_directory=models_directory,
                candidate_root=candidate_root,
                selected=selected,
            )
            ensure_fault_provider_stopped(process, base_url)
        else:
            signal_provider_process(
                process,
                signal.SIGSTOP,
                signal_process_group=True,
            )
            try:
                stop_provider(
                    process,
                    base_url,
                    signal_process_group=True,
                )
            except MatrixFailure as error:
                if str(error) != "provider required forced termination":
                    raise
            else:
                raise MatrixFailure(
                    "stopped provider did not require forced termination"
                )
            ensure_fault_provider_stopped(process, base_url)
    except Exception as error:
        scenario_error = error
    finally:
        if process.poll() is None or process_group_is_available(process.pid):
            try:
                kill_process_group_and_wait(
                    process,
                    label="fault-injection provider",
                )
            except Exception as error:
                scenario_error = error

    snapshot_unchanged = (
        model_snapshot_state(models_directory) == initial_snapshot_state
    )
    if not snapshot_unchanged:
        raise MatrixFailure(
            "isolated model snapshot bytes changed during fault injection"
        )
    if scenario_error is not None:
        raise scenario_error


def run_live_fault_recovery(
    *,
    fault_id: str,
    binary: Path,
    extracted: Path,
    models_directory: Path,
    candidate_root: Path,
    port: int,
    base_url: str,
    candidate: dict[str, str],
    selected: SelectedLocalModel,
    initial_snapshot_state: tuple[tuple[str, int, str], ...],
) -> None:
    process = start_live_fault_provider(
        binary=binary,
        extracted=extracted,
        models_directory=models_directory,
        candidate_root=candidate_root,
        log_name=f"{fault_id}-recovery",
        port=port,
        base_url=base_url,
        expected_version=candidate["version"],
    )
    recovery_error: Exception | None = None
    try:
        environment = selected_model_backed_adapter_environment(
            base_url=base_url,
            candidate=candidate,
            models_directory=models_directory,
            selected=selected,
            profile=CHAT_MODEL_BACKED_PROFILE,
        )
        run_fault_swift_test(
            environment=environment,
            test_filter=CHAT_MODEL_BACKED_PROFILE.live_test_filter,
            log_path=candidate_root / f"{fault_id}-recovery-adapter.log",
            label="Ollama fault recovery adapter test",
            timeout_seconds=COMMAND_DEADLINE_SECONDS,
        )
    except Exception as error:
        recovery_error = error
    finally:
        try:
            stop_provider(
                process,
                base_url,
                signal_process_group=True,
            )
            ensure_fault_provider_stopped(process, base_url)
        except Exception as error:
            recovery_error = error
            if process.poll() is None or process_group_is_available(process.pid):
                try:
                    kill_process_group_and_wait(
                        process,
                        label="fault-injection recovery provider",
                    )
                except Exception as cleanup_error:
                    recovery_error = cleanup_error

    snapshot_unchanged = (
        model_snapshot_state(models_directory) == initial_snapshot_state
    )
    if not snapshot_unchanged:
        raise MatrixFailure(
            "isolated model snapshot bytes changed during fault recovery"
        )
    if recovery_error is not None:
        raise recovery_error


def run_candidate(candidate: dict[str, str], temporary_root: Path) -> dict[str, object]:
    version = candidate["version"]
    candidate_root = temporary_root / version
    candidate_root.mkdir()
    archive = candidate_root / "ollama-darwin.tgz"
    download_archive(candidate, archive)

    extracted = candidate_root / "extracted"
    extracted.mkdir()
    tar = shutil.which("tar")
    if tar is None:
        raise MatrixFailure("tar is required")
    run_checked(
        [tar, "-xzf", str(archive), "-C", str(extracted)],
        cwd=ROOT,
        environment=os.environ.copy(),
        label=f"Ollama {version} archive extraction",
    )
    binary = extracted / "ollama"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise MatrixFailure("archive did not contain an executable ollama binary")

    models_directory = candidate_root / "empty-models"
    models_directory.mkdir()
    if any(models_directory.iterdir()):
        raise MatrixFailure("isolated model directory was not empty before start")

    port = reserve_unique_port()
    base_url = f"http://127.0.0.1:{port}"
    if endpoint_is_available(base_url):
        raise MatrixFailure("reserved loopback port was already serving Ollama")

    phases: dict[str, dict[str, bool]] = {}
    for phase in ("coldStart", "restart"):
        server_environment = os.environ.copy()
        server_environment.update(
            {
                "OLLAMA_HOST": f"127.0.0.1:{port}",
                "OLLAMA_MODELS": str(models_directory),
            }
        )
        log_path = candidate_root / f"{phase}.log"
        with log_path.open("wb") as log_stream:
            ready_deadline_ns = time.monotonic_ns() + START_DEADLINE_NS
            process = subprocess.Popen(
                [str(binary), "serve"],
                cwd=extracted,
                env=server_environment,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
            )
            phase_passed = False
            try:
                wait_until_ready(
                    base_url,
                    version,
                    deadline_ns=ready_deadline_ns,
                )
                run_adapter_test(
                    base_url=base_url,
                    candidate=candidate,
                    models_directory=models_directory,
                )
                phase_passed = True
            finally:
                stop_provider(process, base_url)
        phases[phase] = {
            "adapterTestPassed": phase_passed,
            "endpointUnavailableAfterStop": not endpoint_is_available(base_url),
        }

    return {
        "archiveSha256": candidate["archiveSha256"],
        "archiveUrl": candidate["archiveUrl"],
        "coldStart": phases["coldStart"],
        "restart": phases["restart"],
        "testRuns": 2,
        "version": version,
    }


def selected_source_state(
    models_directory: Path,
    selected: SelectedLocalModel,
) -> tuple[tuple[str, int, str], ...]:
    models_root = models_directory.resolve(strict=True)
    files = (selected.manifest_source_path, *(blob.source_path for blob in selected.blobs))
    rows: list[tuple[str, int, str]] = []
    for path in files:
        resolved = path.resolve(strict=True)
        try:
            relative = resolved.relative_to(models_root)
        except ValueError as error:
            raise MatrixFailure("selected source file escaped the model store") from error
        metadata = resolved.stat()
        rows.append((relative.as_posix(), metadata.st_size, file_sha256(resolved)))
    return tuple(sorted(rows))


def expected_selected_source_state(
    selected: SelectedLocalModel,
) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        sorted(
            (
                (
                    selected.manifest_relative_path.as_posix(),
                    selected.manifest_size_bytes,
                    selected.manifest_digest,
                ),
                *(
                    (
                        blob.relative_path.as_posix(),
                        blob.size_bytes,
                        blob.sha256,
                    )
                    for blob in selected.blobs
                ),
            )
        )
    )


def run_selected_model_backed_phase(
    *,
    binary: Path,
    extracted: Path,
    models_directory: Path,
    candidate_root: Path,
    phase: str,
    port: int,
    base_url: str,
    candidate: dict[str, str],
    selected: SelectedLocalModel,
    profile: ModelBackedProfile,
    initial_snapshot_state: tuple[tuple[str, int, str], ...],
    duration_sink: dict[str, dict[str, int]] | None = None,
) -> dict[str, bool]:
    server_environment = os.environ.copy()
    server_environment.update(
        {
            "OLLAMA_HOST": f"127.0.0.1:{port}",
            "OLLAMA_MODELS": str(models_directory),
        }
    )
    phase_error: Exception | None = None
    process: subprocess.Popen[bytes] | None = None
    phase_started_ns: int | None = None
    ready_finished_ns: int | None = None
    adapter_started_ns: int | None = None
    adapter_finished_ns: int | None = None
    stop_started_ns: int | None = None
    stop_finished_ns: int | None = None
    log_path = candidate_root / f"{phase}.log"
    with log_path.open("wb") as log_stream:
        try:
            phase_started_ns = time.monotonic_ns()
            ready_deadline_ns = phase_started_ns + START_DEADLINE_NS
            process = subprocess.Popen(
                [str(binary), "serve"],
                cwd=extracted,
                env=server_environment,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
            )
            wait_until_ready(
                base_url,
                candidate["version"],
                deadline_ns=ready_deadline_ns,
            )
            ready_finished_ns = time.monotonic_ns()
            adapter_started_ns = time.monotonic_ns()
            run_selected_model_backed_adapter_test(
                base_url=base_url,
                candidate=candidate,
                models_directory=models_directory,
                selected=selected,
                profile=profile,
            )
            adapter_finished_ns = time.monotonic_ns()
        except Exception as error:
            phase_error = error
        finally:
            if process is not None:
                stop_started_ns = time.monotonic_ns()
                try:
                    stop_provider(process, base_url)
                except Exception as error:
                    phase_error = error
                else:
                    stop_finished_ns = time.monotonic_ns()

    snapshot_unchanged = (
        model_snapshot_state(models_directory) == initial_snapshot_state
    )
    if not snapshot_unchanged:
        raise MatrixFailure(
            "isolated model snapshot bytes changed during the run"
        )
    if phase_error is not None:
        raise phase_error

    endpoint_unavailable = not endpoint_is_available(base_url)
    phase_finished_ns = time.monotonic_ns()
    if not endpoint_unavailable:
        raise MatrixFailure(
            "provider endpoint remained available after final stop readback"
        )
    if duration_sink is not None:
        timestamps = (
            phase_started_ns,
            ready_finished_ns,
            adapter_started_ns,
            adapter_finished_ns,
            stop_started_ns,
            stop_finished_ns,
        )
        if any(timestamp is None for timestamp in timestamps):
            raise MatrixFailure("successful phase was missing duration boundaries")
        duration_sink[phase] = duration_phase_result(
            phase_started_ns=phase_started_ns,
            ready_finished_ns=ready_finished_ns,
            adapter_started_ns=adapter_started_ns,
            adapter_finished_ns=adapter_finished_ns,
            stop_started_ns=stop_started_ns,
            stop_finished_ns=stop_finished_ns,
            phase_finished_ns=phase_finished_ns,
        )

    phase_result = {
        key: True
        for key in profile.phase_success_keys
    }
    phase_result["endpointUnavailableAfterStop"] = True
    phase_result["snapshotUnchanged"] = True
    return phase_result


def run_selected_model_backed_candidate(
    candidate: dict[str, str],
    temporary_root: Path,
    *,
    selected: SelectedLocalModel,
    profile: ModelBackedProfile,
    duration_versions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    version = candidate["version"]
    candidate_root = temporary_root / version
    candidate_root.mkdir()
    archive = candidate_root / "ollama-darwin.tgz"
    download_archive(candidate, archive)

    extracted = candidate_root / "extracted"
    extracted.mkdir()
    tar = shutil.which("tar")
    if tar is None:
        raise MatrixFailure("tar is required")
    run_checked(
        [tar, "-xzf", str(archive), "-C", str(extracted)],
        cwd=ROOT,
        environment=os.environ.copy(),
        label=f"Ollama {version} archive extraction",
    )
    binary = extracted / "ollama"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise MatrixFailure("archive did not contain an executable ollama binary")

    models_directory = candidate_root / MODEL_SNAPSHOT_DIRECTORY_NAME
    initial_snapshot_state = create_model_snapshot(selected, models_directory)
    if len(initial_snapshot_state) != len(selected.blobs) + 1:
        raise MatrixFailure("isolated model snapshot file count was invalid")

    port = reserve_unique_port()
    base_url = f"http://127.0.0.1:{port}"
    if endpoint_is_available(base_url):
        raise MatrixFailure("reserved loopback port was already serving Ollama")

    phases: dict[str, dict[str, bool]] = {}
    phase_durations: dict[str, dict[str, int]] | None = (
        {} if duration_versions is not None else None
    )
    for phase in ("coldStart", "restart"):
        phases[phase] = run_selected_model_backed_phase(
            binary=binary,
            extracted=extracted,
            models_directory=models_directory,
            candidate_root=candidate_root,
            phase=phase,
            port=port,
            base_url=base_url,
            candidate=candidate,
            selected=selected,
            profile=profile,
            initial_snapshot_state=initial_snapshot_state,
            duration_sink=phase_durations,
        )

    if duration_versions is not None:
        if phase_durations is None or set(phase_durations) != {
            "coldStart",
            "restart",
        }:
            raise MatrixFailure("candidate duration phases were incomplete")
        duration_versions.append(
            {
                "coldStart": phase_durations["coldStart"],
                "restart": phase_durations["restart"],
                "version": version,
            }
        )

    return {
        "archiveSha256": candidate["archiveSha256"],
        "archiveUrl": candidate["archiveUrl"],
        "coldStart": phases["coldStart"],
        "restart": phases["restart"],
        "testRuns": 2,
        "version": version,
    }


def run_embedding_semantic_quality_phase(
    *,
    binary: Path,
    extracted: Path,
    models_directory: Path,
    candidate_root: Path,
    phase: str,
    port: int,
    base_url: str,
    candidate: dict[str, str],
    selected: SelectedLocalModel,
    task_set_path: Path,
    initial_snapshot_state: tuple[tuple[str, int, str], ...],
) -> dict[str, bool]:
    if phase not in {"semantic", "recovery"}:
        raise MatrixFailure(
            "embedding semantic-quality phase was not recognized"
        )
    assert_recorded_embedding_semantic_quality_swift_sources()
    process = start_live_fault_provider(
        binary=binary,
        extracted=extracted,
        models_directory=models_directory,
        candidate_root=candidate_root,
        log_name=f"embedding-semantic-{phase}",
        port=port,
        base_url=base_url,
        expected_version=candidate["version"],
    )
    phase_error: Exception | None = None
    try:
        if phase == "semantic":
            environment = embedding_semantic_quality_adapter_environment(
                base_url=base_url,
                candidate=candidate,
                models_directory=models_directory,
                selected=selected,
                task_set_path=task_set_path,
            )
            test_filter = EMBEDDING_SEMANTIC_QUALITY_LIVE_TEST_FILTER
            timeout_seconds = (
                EMBEDDING_SEMANTIC_QUALITY_ADAPTER_DEADLINE_SECONDS
            )
        else:
            environment = selected_model_backed_adapter_environment(
                base_url=base_url,
                candidate=candidate,
                models_directory=models_directory,
                selected=selected,
                profile=EMBEDDING_MODEL_BACKED_PROFILE,
            )
            environment.pop(
                EMBEDDING_MODEL_BACKED_PROFILE.enable_environment_key,
                None,
            )
            environment[
                EMBEDDING_SEMANTIC_QUALITY_RECOVERY_ENVIRONMENT_KEY
            ] = "1"
            test_filter = (
                EMBEDDING_SEMANTIC_QUALITY_RECOVERY_TEST_FILTER
            )
            timeout_seconds = COMMAND_DEADLINE_SECONDS
        run_fault_swift_test(
            environment=environment,
            test_filter=test_filter,
            log_path=candidate_root / f"embedding-semantic-{phase}-adapter.log",
            label=f"Ollama embedding semantic-quality {phase} adapter test",
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        phase_error = error
    finally:
        try:
            stop_provider(
                process,
                base_url,
                signal_process_group=True,
            )
            ensure_fault_provider_stopped(process, base_url)
        except Exception as error:
            phase_error = error
            if (
                process.poll() is None
                or process_group_is_available(process.pid)
            ):
                try:
                    kill_process_group_and_wait(
                        process,
                        label=(
                            "embedding semantic-quality provider"
                        ),
                    )
                except Exception as cleanup_error:
                    phase_error = cleanup_error

    if (
        model_snapshot_state(models_directory)
        != initial_snapshot_state
    ):
        raise MatrixFailure(
            "isolated model snapshot bytes changed during embedding "
            "semantic-quality evaluation"
        )
    if (
        not task_set_path.is_file()
        or task_set_path.is_symlink()
        or file_sha256(task_set_path)
        != EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256
    ):
        raise MatrixFailure(
            "embedding semantic-quality task set bytes changed during the run"
        )
    assert_recorded_embedding_semantic_quality_swift_sources()
    if phase_error is not None:
        raise phase_error

    common = {
        "adapterTestPassed": True,
        "endpointUnavailableAfterStop": True,
        "exactTestCaseExecuted": True,
        "modelUnloadConfirmed": True,
        "processGroupReaped": True,
        "snapshotUnchanged": True,
        "swiftSourcesUnchanged": True,
        "taskSetUnchanged": True,
    }
    if phase == "semantic":
        return {
            **common,
            "allMarginsPassed": True,
            "allScenarioRankingsPassed": True,
            "embeddingBatchCompleted": True,
            "embeddingShapeValidated": True,
            "installedStatePreserved": True,
            "repeatabilityPassed": True,
        }
    return {
        **common,
        "catalogPopulated": True,
        "embeddingBatchCompleted": True,
        "embeddingShapeValidated": True,
        "installedStatePreserved": True,
    }


def run_embedding_semantic_quality_candidate(
    candidate: dict[str, str],
    temporary_root: Path,
    *,
    selected: SelectedLocalModel,
) -> dict[str, object]:
    version = candidate["version"]
    candidate_root = temporary_root / version
    candidate_root.mkdir()
    archive = candidate_root / "ollama-darwin.tgz"
    download_archive(candidate, archive)

    extracted = candidate_root / "extracted"
    extracted.mkdir()
    tar = shutil.which("tar")
    if tar is None:
        raise MatrixFailure("tar is required")
    run_checked(
        [tar, "-xzf", str(archive), "-C", str(extracted)],
        cwd=ROOT,
        environment=os.environ.copy(),
        label=f"Ollama {version} archive extraction",
    )
    binary = extracted / "ollama"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise MatrixFailure(
            "archive did not contain an executable ollama binary"
        )

    models_directory = candidate_root / MODEL_SNAPSHOT_DIRECTORY_NAME
    initial_snapshot_state = create_model_snapshot(
        selected,
        models_directory,
    )
    if len(initial_snapshot_state) != len(selected.blobs) + 1:
        raise MatrixFailure("isolated model snapshot file count was invalid")
    task_set_path = create_embedding_semantic_quality_task_set_copy(
        candidate_root
    )

    port = reserve_unique_port()
    base_url = f"http://127.0.0.1:{port}"
    if endpoint_is_available(base_url):
        raise MatrixFailure(
            "reserved loopback port was already serving Ollama"
        )

    semantic = run_embedding_semantic_quality_phase(
        binary=binary,
        extracted=extracted,
        models_directory=models_directory,
        candidate_root=candidate_root,
        phase="semantic",
        port=port,
        base_url=base_url,
        candidate=candidate,
        selected=selected,
        task_set_path=task_set_path,
        initial_snapshot_state=initial_snapshot_state,
    )
    recovery = run_embedding_semantic_quality_phase(
        binary=binary,
        extracted=extracted,
        models_directory=models_directory,
        candidate_root=candidate_root,
        phase="recovery",
        port=port,
        base_url=base_url,
        candidate=candidate,
        selected=selected,
        task_set_path=task_set_path,
        initial_snapshot_state=initial_snapshot_state,
    )
    return {
        "archiveSha256": candidate["archiveSha256"],
        "archiveUrl": candidate["archiveUrl"],
        "recovery": recovery,
        "recoveryRuns": 1,
        "semantic": semantic,
        "semanticRuns": 1,
        "testRuns": 2,
        "version": version,
    }


def run_model_backed_candidate(
    candidate: dict[str, str],
    temporary_root: Path,
    *,
    selected: SelectedLocalModel,
) -> dict[str, object]:
    return run_selected_model_backed_candidate(
        candidate,
        temporary_root,
        selected=selected,
        profile=CHAT_MODEL_BACKED_PROFILE,
    )


def run_live_fault_injection_candidate(
    candidate: dict[str, str],
    temporary_root: Path,
    *,
    selected: SelectedLocalModel,
) -> dict[str, object]:
    version = candidate["version"]
    candidate_root = temporary_root / version
    candidate_root.mkdir()
    archive = candidate_root / "ollama-darwin.tgz"
    download_archive(candidate, archive)

    extracted = candidate_root / "extracted"
    extracted.mkdir()
    tar = shutil.which("tar")
    if tar is None:
        raise MatrixFailure("tar is required")
    run_checked(
        [tar, "-xzf", str(archive), "-C", str(extracted)],
        cwd=ROOT,
        environment=os.environ.copy(),
        label=f"Ollama {version} archive extraction",
    )
    binary = extracted / "ollama"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise MatrixFailure("archive did not contain an executable ollama binary")

    models_directory = candidate_root / MODEL_SNAPSHOT_DIRECTORY_NAME
    initial_snapshot_state = create_model_snapshot(selected, models_directory)
    if len(initial_snapshot_state) != len(selected.blobs) + 1:
        raise MatrixFailure("isolated model snapshot file count was invalid")

    port = reserve_unique_port()
    base_url = f"http://127.0.0.1:{port}"
    if endpoint_is_available(base_url):
        raise MatrixFailure("reserved loopback port was already serving Ollama")

    fault_rows: list[dict[str, object]] = []
    for fault_id in LIVE_FAULT_IDS:
        run_live_fault_scenario(
            fault_id=fault_id,
            binary=binary,
            extracted=extracted,
            models_directory=models_directory,
            candidate_root=candidate_root,
            port=port,
            base_url=base_url,
            candidate=candidate,
            selected=selected,
            initial_snapshot_state=initial_snapshot_state,
        )
        run_live_fault_recovery(
            fault_id=fault_id,
            binary=binary,
            extracted=extracted,
            models_directory=models_directory,
            candidate_root=candidate_root,
            port=port,
            base_url=base_url,
            candidate=candidate,
            selected=selected,
            initial_snapshot_state=initial_snapshot_state,
        )
        fault_rows.append(
            {
                "endpointUnavailableAfterFault": True,
                "expectedFailureObserved": True,
                "faultId": fault_id,
                "faultTriggered": True,
                "processGroupReaped": True,
                "recoveryPassed": True,
                "snapshotUnchanged": True,
            }
        )

    return {
        "archiveSha256": candidate["archiveSha256"],
        "archiveUrl": candidate["archiveUrl"],
        "faults": fault_rows,
        "recoveryRuns": 3,
        "testRuns": 6,
        "version": version,
    }


def selected_model_backed_result(
    *,
    source_version: str,
    catalog_model_count: int,
    selected: SelectedLocalModel,
    versions: list[dict[str, object]],
    profile: ModelBackedProfile,
) -> dict[str, object]:
    return {
        "evidenceBoundary": profile.evidence_boundary,
        "fixtureId": profile.runner_id,
        "recordedDate": profile.recorded_date,
        "schemaVersion": 1,
        "snapshot": {
            "blobCount": len(selected.blobs),
            "copyMode": MODEL_BACKED_COPY_MODE,
            "manifestBytes": selected.manifest_size_bytes,
            "modelArtifactBytes": selected.model_artifact_bytes,
            "modelDownloadAttempted": False,
            "modelNameRetained": False,
        },
        "source": {
            "catalogModelCount": catalog_model_count,
            "catalogIdentityProjectionUnchanged": True,
            "modelNameRetained": False,
            "providerVersion": source_version,
            "runningIdentitySetUnchanged": True,
            "selectedFileBytesUnchanged": True,
            "selectionPolicy": profile.selection_policy,
        },
        "versions": versions,
    }


def model_backed_result(
    *,
    source_version: str,
    catalog_model_count: int,
    selected: SelectedLocalModel,
    versions: list[dict[str, object]],
) -> dict[str, object]:
    return selected_model_backed_result(
        source_version=source_version,
        catalog_model_count=catalog_model_count,
        selected=selected,
        versions=versions,
        profile=CHAT_MODEL_BACKED_PROFILE,
    )


def embedding_model_backed_result(
    *,
    source_version: str,
    catalog_model_count: int,
    selected: SelectedLocalModel,
    versions: list[dict[str, object]],
) -> dict[str, object]:
    return selected_model_backed_result(
        source_version=source_version,
        catalog_model_count=catalog_model_count,
        selected=selected,
        versions=versions,
        profile=EMBEDDING_MODEL_BACKED_PROFILE,
    )


def vision_model_backed_result(
    *,
    source_version: str,
    catalog_model_count: int,
    selected: SelectedLocalModel,
    versions: list[dict[str, object]],
) -> dict[str, object]:
    return selected_model_backed_result(
        source_version=source_version,
        catalog_model_count=catalog_model_count,
        selected=selected,
        versions=versions,
        profile=VISION_MODEL_BACKED_PROFILE,
    )


def recorded_selected_model_backed_fixture(
    profile: ModelBackedProfile,
) -> dict[str, object]:
    phase = {
        key: True
        for key in (
            *profile.phase_success_keys,
            "endpointUnavailableAfterStop",
            "snapshotUnchanged",
        )
    }
    versions = [
        {
            "archiveSha256": candidate["archiveSha256"],
            "archiveUrl": candidate["archiveUrl"],
            "coldStart": dict(phase),
            "restart": dict(phase),
            "testRuns": 2,
            "version": candidate["version"],
        }
        for candidate in EXACT_CANDIDATES
    ]
    return {
        "evidenceBoundary": profile.evidence_boundary,
        "fixtureId": profile.runner_id,
        "recordedDate": profile.recorded_date,
        "schemaVersion": 1,
        "snapshot": {
            "blobCount": profile.recorded_blob_count,
            "copyMode": MODEL_BACKED_COPY_MODE,
            "manifestBytes": profile.recorded_manifest_bytes,
            "modelArtifactBytes": profile.recorded_model_artifact_bytes,
            "modelDownloadAttempted": False,
            "modelNameRetained": False,
        },
        "source": {
            "catalogModelCount": profile.recorded_catalog_model_count,
            "catalogIdentityProjectionUnchanged": True,
            "modelNameRetained": False,
            "providerVersion": profile.recorded_source_version,
            "runningIdentitySetUnchanged": True,
            "selectedFileBytesUnchanged": True,
            "selectionPolicy": profile.selection_policy,
        },
        "versions": versions,
    }


def recorded_selected_model_backed_fixture_sha256(
    profile: ModelBackedProfile,
) -> str:
    fixture_bytes = json.dumps(
        recorded_selected_model_backed_fixture(profile),
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(fixture_bytes).hexdigest()


def recorded_model_backed_fixture() -> dict[str, object]:
    return recorded_selected_model_backed_fixture(
        CHAT_MODEL_BACKED_PROFILE
    )


def recorded_embedding_model_backed_fixture() -> dict[str, object]:
    return recorded_selected_model_backed_fixture(
        EMBEDDING_MODEL_BACKED_PROFILE
    )


def recorded_vision_model_backed_fixture() -> dict[str, object]:
    return recorded_selected_model_backed_fixture(
        VISION_MODEL_BACKED_PROFILE
    )


def recorded_embedding_semantic_quality_fixture() -> dict[str, object]:
    canonical_embedding = recorded_selected_model_backed_fixture(
        EMBEDDING_MODEL_BACKED_PROFILE
    )
    semantic = {
        "adapterTestPassed": True,
        "allMarginsPassed": True,
        "allScenarioRankingsPassed": True,
        "embeddingBatchCompleted": True,
        "embeddingShapeValidated": True,
        "endpointUnavailableAfterStop": True,
        "exactTestCaseExecuted": True,
        "installedStatePreserved": True,
        "modelUnloadConfirmed": True,
        "processGroupReaped": True,
        "repeatabilityPassed": True,
        "snapshotUnchanged": True,
        "swiftSourcesUnchanged": True,
        "taskSetUnchanged": True,
    }
    recovery = {
        "adapterTestPassed": True,
        "catalogPopulated": True,
        "embeddingBatchCompleted": True,
        "embeddingShapeValidated": True,
        "endpointUnavailableAfterStop": True,
        "exactTestCaseExecuted": True,
        "installedStatePreserved": True,
        "modelUnloadConfirmed": True,
        "processGroupReaped": True,
        "snapshotUnchanged": True,
        "swiftSourcesUnchanged": True,
        "taskSetUnchanged": True,
    }
    versions = [
        {
            "archiveSha256": candidate["archiveSha256"],
            "archiveUrl": candidate["archiveUrl"],
            "recovery": dict(recovery),
            "recoveryRuns": 1,
            "semantic": dict(semantic),
            "semanticRuns": 1,
            "testRuns": 2,
            "version": candidate["version"],
        }
        for candidate in EXACT_CANDIDATES
    ]
    return {
        "canonicalFixtureSha256": (
            recorded_selected_model_backed_fixture_sha256(
                EMBEDDING_MODEL_BACKED_PROFILE
            )
        ),
        "deadlinesMs": {
            "processGroupReap": (
                LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS * 1_000
            ),
            "providerReady": int(START_DEADLINE_SECONDS * 1_000),
            "recoveryAdapter": COMMAND_DEADLINE_SECONDS * 1_000,
            "semanticAdapter": (
                EMBEDDING_SEMANTIC_QUALITY_ADAPTER_DEADLINE_SECONDS
                * 1_000
            ),
            "stop": int(STOP_DEADLINE_SECONDS * 1_000),
        },
        "evidenceBoundary": (
            EMBEDDING_SEMANTIC_QUALITY_EVIDENCE_BOUNDARY
        ),
        "fixtureId": EMBEDDING_SEMANTIC_QUALITY_FIXTURE_ID,
        "profile": "embedding",
        "recordedDate": EMBEDDING_SEMANTIC_QUALITY_RECORDED_DATE,
        "recoveryObservationCount": 2,
        "runnerSourceSha256": (
            RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256
        ),
        "schemaVersion": 1,
        "semanticObservationCount": 2,
        "snapshot": canonical_embedding["snapshot"],
        "source": canonical_embedding["source"],
        "swiftSources": {
            "liveAssertionsSha256": (
                EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_SHA256
            ),
            "semanticScorerSha256": (
                EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_SHA256
            ),
        },
        "taskSet": {
            "fixtureId": EMBEDDING_SEMANTIC_QUALITY_TASK_SET_ID,
            "sha256": EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256,
        },
        "thresholds": {
            "batchCallsPerVersion": (
                EMBEDDING_SEMANTIC_QUALITY_BATCH_CALLS_PER_VERSION
            ),
            "embeddingCountPerVersion": (
                EMBEDDING_SEMANTIC_QUALITY_EMBEDDING_COUNT_PER_VERSION
            ),
            "minimumPositiveMarginBasisPoints": (
                EMBEDDING_SEMANTIC_QUALITY_MINIMUM_MARGIN_BASIS_POINTS
            ),
            "minimumRepeatCosineBasisPoints": (
                EMBEDDING_SEMANTIC_QUALITY_MINIMUM_REPEAT_BASIS_POINTS
            ),
            "scenarioCount": (
                EMBEDDING_SEMANTIC_QUALITY_SCENARIO_COUNT
            ),
            "textsPerBatch": (
                EMBEDDING_SEMANTIC_QUALITY_TEXTS_PER_BATCH
            ),
        },
        "versions": versions,
    }


def validate_recorded_embedding_semantic_quality_fixture(
    value: object,
) -> None:
    validate_exact_json_value(
        value,
        recorded_embedding_semantic_quality_fixture(),
        label="recorded embedding semantic-quality fixture",
    )


def embedding_semantic_quality_result(
    *,
    source_version: str,
    catalog_model_count: int,
    selected: SelectedLocalModel,
    versions: list[dict[str, object]],
) -> dict[str, object]:
    result = recorded_embedding_semantic_quality_fixture()
    result["snapshot"] = {
        "blobCount": len(selected.blobs),
        "copyMode": MODEL_BACKED_COPY_MODE,
        "manifestBytes": selected.manifest_size_bytes,
        "modelArtifactBytes": selected.model_artifact_bytes,
        "modelDownloadAttempted": False,
        "modelNameRetained": False,
    }
    result["source"] = {
        "catalogModelCount": catalog_model_count,
        "catalogIdentityProjectionUnchanged": True,
        "modelNameRetained": False,
        "providerVersion": source_version,
        "runningIdentitySetUnchanged": True,
        "selectedFileBytesUnchanged": True,
        "selectionPolicy": (
            EMBEDDING_MODEL_BACKED_PROFILE.selection_policy
        ),
    }
    result["versions"] = versions
    validate_recorded_embedding_semantic_quality_fixture(result)
    return result


def recorded_live_fault_injection_fixture() -> dict[str, object]:
    canonical_chat = recorded_selected_model_backed_fixture(
        CHAT_MODEL_BACKED_PROFILE
    )
    fault_rows = [
        {
            "endpointUnavailableAfterFault": True,
            "expectedFailureObserved": True,
            "faultId": fault_id,
            "faultTriggered": True,
            "processGroupReaped": True,
            "recoveryPassed": True,
            "snapshotUnchanged": True,
        }
        for fault_id in LIVE_FAULT_IDS
    ]
    versions = [
        {
            "archiveSha256": candidate["archiveSha256"],
            "archiveUrl": candidate["archiveUrl"],
            "faults": [dict(row) for row in fault_rows],
            "recoveryRuns": 3,
            "testRuns": 6,
            "version": candidate["version"],
        }
        for candidate in EXACT_CANDIDATES
    ]
    return {
        "canonicalFixtureSha256": (
            recorded_selected_model_backed_fixture_sha256(
                CHAT_MODEL_BACKED_PROFILE
            )
        ),
        "clock": "time.monotonic_ns",
        "deadlinesMs": {
            "firstDeltaTrigger": (
                LIVE_FAULT_FIRST_DELTA_TRIGGER_SECONDS * 1_000
            ),
            "postFaultTerminal": LIVE_FAULT_POST_TERMINAL_SECONDS * 1_000,
            "preRequestTerminal": (
                LIVE_FAULT_PRE_REQUEST_TERMINAL_SECONDS * 1_000
            ),
            "processGroupReap": (
                LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS * 1_000
            ),
            "providerReady": int(START_DEADLINE_SECONDS * 1_000),
            "recoveryAdapter": COMMAND_DEADLINE_SECONDS * 1_000,
            "stop": int(STOP_DEADLINE_SECONDS * 1_000),
        },
        "evidenceBoundary": LIVE_FAULT_INJECTION_EVIDENCE_BOUNDARY,
        "faultObservationCount": 6,
        "faultsPerVersion": 3,
        "fixtureId": LIVE_FAULT_INJECTION_FIXTURE_ID,
        "profile": "chat",
        "recordedDate": LIVE_FAULT_INJECTION_RECORDED_DATE,
        "recoveryRunsPerVersion": 3,
        "schemaVersion": 1,
        "snapshot": canonical_chat["snapshot"],
        "source": canonical_chat["source"],
        "versions": versions,
    }


def validate_recorded_live_fault_injection_fixture(value: object) -> None:
    validate_exact_json_value(
        value,
        recorded_live_fault_injection_fixture(),
        label="recorded live fault injection",
    )


def live_fault_injection_result(
    *,
    source_version: str,
    catalog_model_count: int,
    selected: SelectedLocalModel,
    versions: list[dict[str, object]],
) -> dict[str, object]:
    result = recorded_live_fault_injection_fixture()
    result["snapshot"] = {
        "blobCount": len(selected.blobs),
        "copyMode": MODEL_BACKED_COPY_MODE,
        "manifestBytes": selected.manifest_size_bytes,
        "modelArtifactBytes": selected.model_artifact_bytes,
        "modelDownloadAttempted": False,
        "modelNameRetained": False,
    }
    result["source"] = {
        "catalogModelCount": catalog_model_count,
        "catalogIdentityProjectionUnchanged": True,
        "modelNameRetained": False,
        "providerVersion": source_version,
        "runningIdentitySetUnchanged": True,
        "selectedFileBytesUnchanged": True,
        "selectionPolicy": CHAT_MODEL_BACKED_PROFILE.selection_policy,
    }
    result["versions"] = versions
    validate_recorded_live_fault_injection_fixture(result)
    return result


def validate_recorded_duration_observation_fixture(value: object) -> None:
    expected_root_keys = {
        "evidenceBoundary",
        "fixtureId",
        "phaseObservationCount",
        "profiles",
        "recordedDate",
        "schemaVersion",
    }
    if not isinstance(value, dict) or set(value) != expected_root_keys:
        raise MatrixFailure(
            "recorded duration observation has an unexpected root shape"
        )
    if (
        value["evidenceBoundary"] != DURATION_OBSERVATION_EVIDENCE_BOUNDARY
        or value["fixtureId"] != DURATION_OBSERVATION_FIXTURE_ID
        or value["recordedDate"] != DURATION_OBSERVATION_RECORDED_DATE
        or exact_int(
            value["schemaVersion"],
            label="recorded duration observation schemaVersion",
        )
        != 1
        or exact_int(
            value["phaseObservationCount"],
            label="recorded duration observation phaseObservationCount",
        )
        != 12
    ):
        raise MatrixFailure(
            "recorded duration observation metadata was invalid"
        )

    profiles = value["profiles"]
    expected_profiles = {
        "chat": CHAT_MODEL_BACKED_PROFILE,
        "embedding": EMBEDDING_MODEL_BACKED_PROFILE,
        "vision": VISION_MODEL_BACKED_PROFILE,
    }
    if not isinstance(profiles, dict) or set(profiles) != set(expected_profiles):
        raise MatrixFailure(
            "recorded duration observation profile set was invalid"
        )
    observed_phase_count = 0
    for key, profile in expected_profiles.items():
        profile_row = profiles[key]
        if (
            not isinstance(profile_row, dict)
            or set(profile_row)
            != {
                "canonicalFixtureSha256",
                "durationEvidence",
                "fixtureId",
            }
            or profile_row["canonicalFixtureSha256"]
            != recorded_selected_model_backed_fixture_sha256(profile)
            or profile_row["fixtureId"] != profile.runner_id
        ):
            raise MatrixFailure(
                f"recorded duration observation {key} profile was invalid"
            )
        validate_duration_evidence(profile_row["durationEvidence"])
        observed_phase_count += (
            len(profile_row["durationEvidence"]["versions"]) * 2
        )
    if observed_phase_count != value["phaseObservationCount"]:
        raise MatrixFailure(
            "recorded duration observation count was internally inconsistent"
        )


def recorded_duration_observation_result(
    profile_results: dict[str, dict[str, object]],
) -> dict[str, object]:
    expected_profiles = {
        "chat": CHAT_MODEL_BACKED_PROFILE,
        "embedding": EMBEDDING_MODEL_BACKED_PROFILE,
        "vision": VISION_MODEL_BACKED_PROFILE,
    }
    if set(profile_results) != set(expected_profiles):
        raise MatrixFailure(
            "duration observation requires chat, embedding, and vision results"
        )

    profiles: dict[str, dict[str, object]] = {}
    for key, profile in expected_profiles.items():
        result = profile_results[key]
        if (
            not isinstance(result, dict)
            or "durationEvidence" not in result
        ):
            raise MatrixFailure(
                f"duration observation {key} result had no duration evidence"
            )
        stable_projection = {
            result_key: result_value
            for result_key, result_value in result.items()
            if result_key != "durationEvidence"
        }
        if stable_projection != recorded_selected_model_backed_fixture(profile):
            raise MatrixFailure(
                f"duration observation {key} canonical projection drifted"
            )
        validate_duration_evidence(result["durationEvidence"])
        profiles[key] = {
            "canonicalFixtureSha256": (
                recorded_selected_model_backed_fixture_sha256(profile)
            ),
            "durationEvidence": result["durationEvidence"],
            "fixtureId": profile.runner_id,
        }

    fixture: dict[str, object] = {
        "evidenceBoundary": DURATION_OBSERVATION_EVIDENCE_BOUNDARY,
        "fixtureId": DURATION_OBSERVATION_FIXTURE_ID,
        "phaseObservationCount": 12,
        "profiles": profiles,
        "recordedDate": DURATION_OBSERVATION_RECORDED_DATE,
        "schemaVersion": 1,
    }
    validate_recorded_duration_observation_fixture(fixture)
    return fixture


def run_selected_model_backed_matrix(
    source_models_directory: Path,
    *,
    profile: ModelBackedProfile,
    include_duration_evidence: bool = False,
) -> dict[str, object]:
    if SOURCE_OLLAMA_BASE_URL != "http://127.0.0.1:11434":
        raise MatrixFailure("source provider must remain the default loopback Ollama")
    source_models_directory = source_models_directory.resolve(strict=True)
    if not source_models_directory.is_dir():
        raise MatrixFailure("source model store must be a directory")

    source_version_before = source_provider_version(SOURCE_OLLAMA_BASE_URL)
    candidate_versions = {candidate["version"] for candidate in EXACT_CANDIDATES}
    if (
        source_version_before != profile.recorded_source_version
        or source_version_before not in candidate_versions
    ):
        raise MatrixFailure("source provider version differs from the recorded baseline")
    catalog_before = source_catalog_rows(SOURCE_OLLAMA_BASE_URL)
    running_before = source_running_model_names(SOURCE_OLLAMA_BASE_URL)
    if len(catalog_before) != profile.recorded_catalog_model_count:
        raise MatrixFailure("source catalog count differs from the recorded baseline")

    selected = select_source_model(
        source_models_directory,
        profile=profile,
        base_url=SOURCE_OLLAMA_BASE_URL,
    )
    if (
        len(selected.blobs) != profile.recorded_blob_count
        or selected.manifest_size_bytes
        != profile.recorded_manifest_bytes
        or selected.model_artifact_bytes
        != profile.recorded_model_artifact_bytes
    ):
        raise MatrixFailure("selected model snapshot differs from the recorded baseline")
    source_files_before = expected_selected_source_state(selected)

    versions: list[dict[str, object]] | None = None
    duration_versions: list[dict[str, object]] | None = (
        [] if include_duration_evidence else None
    )
    candidate_error: Exception | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=profile.temporary_prefix
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            versions = [
                run_selected_model_backed_candidate(
                    candidate,
                    temporary_root,
                    selected=selected,
                    profile=profile,
                    duration_versions=duration_versions,
                )
                for candidate in EXACT_CANDIDATES
            ]
    except Exception as error:
        candidate_error = error

    try:
        source_version_after = source_provider_version(
            SOURCE_OLLAMA_BASE_URL
        )
        catalog_after = source_catalog_rows(SOURCE_OLLAMA_BASE_URL)
        running_after = source_running_model_names(SOURCE_OLLAMA_BASE_URL)
        source_files_after = selected_source_state(
            source_models_directory,
            selected,
        )
    except Exception:
        raise MatrixFailure(
            "post-run observed source readback failed inside the "
            "non-retained local-model boundary"
        ) from None
    if (
        source_version_after != source_version_before
        or catalog_after != catalog_before
        or running_after != running_before
        or source_files_after != source_files_before
    ):
        raise MatrixFailure(
            "observed source provider version, catalog identity projection, "
            "running identity set, or selected file bytes changed during the "
            "isolated run"
        )
    if candidate_error is not None:
        raise candidate_error
    if versions is None:
        raise MatrixFailure("model-backed matrix produced no candidate results")

    result = selected_model_backed_result(
        source_version=source_version_before,
        catalog_model_count=len(catalog_before),
        selected=selected,
        versions=versions,
        profile=profile,
    )
    if result != recorded_selected_model_backed_fixture(profile):
        raise MatrixFailure(
            "model-backed result differed from the recorded canonical fixture"
        )
    if include_duration_evidence:
        if duration_versions is None:
            raise MatrixFailure("duration evidence was not collected")
        result = {
            **result,
            "durationEvidence": duration_evidence_result(duration_versions),
        }
    serialized = json.dumps(
        result,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if selected.provider_model_id in serialized:
        raise MatrixFailure("model-backed result retained the selected model name")
    return result


def run_embedding_semantic_quality_matrix(
    source_models_directory: Path,
) -> dict[str, object]:
    if SOURCE_OLLAMA_BASE_URL != "http://127.0.0.1:11434":
        raise MatrixFailure(
            "source provider must remain the default loopback Ollama"
        )
    assert_recorded_embedding_semantic_quality_swift_sources()
    task_set_data = recorded_embedding_semantic_quality_task_set_bytes()
    task_set_value = strict_json_loads(
        task_set_data,
        label="recorded embedding semantic-quality task set",
    )
    validate_embedding_semantic_quality_task_set(task_set_value)
    task_texts = tuple(
        row["text"]
        for row in task_set_value["firstCall"]
    )

    source_models_directory = source_models_directory.resolve(strict=True)
    if not source_models_directory.is_dir():
        raise MatrixFailure("source model store must be a directory")
    profile = EMBEDDING_MODEL_BACKED_PROFILE
    source_version_before = source_provider_version(
        SOURCE_OLLAMA_BASE_URL
    )
    candidate_versions = {
        candidate["version"] for candidate in EXACT_CANDIDATES
    }
    if (
        source_version_before != profile.recorded_source_version
        or source_version_before not in candidate_versions
    ):
        raise MatrixFailure(
            "source provider version differs from the recorded baseline"
        )
    catalog_before = source_catalog_rows(SOURCE_OLLAMA_BASE_URL)
    running_before = source_running_model_names(SOURCE_OLLAMA_BASE_URL)
    if len(catalog_before) != profile.recorded_catalog_model_count:
        raise MatrixFailure(
            "source catalog count differs from the recorded baseline"
        )

    selected = select_source_model(
        source_models_directory,
        profile=profile,
        base_url=SOURCE_OLLAMA_BASE_URL,
    )
    if (
        len(selected.blobs) != profile.recorded_blob_count
        or selected.manifest_size_bytes
        != profile.recorded_manifest_bytes
        or selected.model_artifact_bytes
        != profile.recorded_model_artifact_bytes
    ):
        raise MatrixFailure(
            "selected model snapshot differs from the recorded baseline"
        )
    source_files_before = expected_selected_source_state(selected)

    versions: list[dict[str, object]] | None = None
    candidate_error: Exception | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=EMBEDDING_SEMANTIC_QUALITY_TEMPORARY_PREFIX
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            versions = [
                run_embedding_semantic_quality_candidate(
                    candidate,
                    temporary_root,
                    selected=selected,
                )
                for candidate in EXACT_CANDIDATES
            ]
    except Exception as error:
        candidate_error = error

    try:
        source_version_after = source_provider_version(
            SOURCE_OLLAMA_BASE_URL
        )
        catalog_after = source_catalog_rows(SOURCE_OLLAMA_BASE_URL)
        running_after = source_running_model_names(
            SOURCE_OLLAMA_BASE_URL
        )
        source_files_after = selected_source_state(
            source_models_directory,
            selected,
        )
    except Exception:
        raise MatrixFailure(
            "post-run observed source readback failed inside the "
            "non-retained embedding semantic-quality boundary"
        ) from None
    if (
        source_version_after != source_version_before
        or catalog_after != catalog_before
        or running_after != running_before
        or source_files_after != source_files_before
    ):
        raise MatrixFailure(
            "observed source provider version, catalog identity projection, "
            "running identity set, or selected file bytes changed during the "
            "isolated embedding semantic-quality run"
        )
    assert_recorded_embedding_semantic_quality_swift_sources()
    if candidate_error is not None:
        raise candidate_error
    if versions is None:
        raise MatrixFailure(
            "embedding semantic-quality matrix produced no results"
        )

    result = embedding_semantic_quality_result(
        source_version=source_version_before,
        catalog_model_count=len(catalog_before),
        selected=selected,
        versions=versions,
    )
    serialized = json.dumps(
        result,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    forbidden_values = (
        selected.provider_model_id,
        str(source_models_directory),
        *task_texts,
    )
    if any(value in serialized for value in forbidden_values):
        raise MatrixFailure(
            "embedding semantic-quality result retained non-evidence input"
        )
    return result


def run_live_fault_injection_matrix(
    source_models_directory: Path,
) -> dict[str, object]:
    profile = CHAT_MODEL_BACKED_PROFILE
    if SOURCE_OLLAMA_BASE_URL != "http://127.0.0.1:11434":
        raise MatrixFailure("source provider must remain the default loopback Ollama")
    source_models_directory = source_models_directory.resolve(strict=True)
    if not source_models_directory.is_dir():
        raise MatrixFailure("source model store must be a directory")

    source_version_before = source_provider_version(SOURCE_OLLAMA_BASE_URL)
    candidate_versions = {
        candidate["version"] for candidate in EXACT_CANDIDATES
    }
    if (
        source_version_before != profile.recorded_source_version
        or source_version_before not in candidate_versions
    ):
        raise MatrixFailure("source provider version differs from the recorded baseline")
    catalog_before = source_catalog_rows(SOURCE_OLLAMA_BASE_URL)
    running_before = source_running_model_names(SOURCE_OLLAMA_BASE_URL)
    if len(catalog_before) != profile.recorded_catalog_model_count:
        raise MatrixFailure("source catalog count differs from the recorded baseline")

    selected = select_source_model(
        source_models_directory,
        profile=profile,
        base_url=SOURCE_OLLAMA_BASE_URL,
    )
    if (
        len(selected.blobs) != profile.recorded_blob_count
        or selected.manifest_size_bytes
        != profile.recorded_manifest_bytes
        or selected.model_artifact_bytes
        != profile.recorded_model_artifact_bytes
    ):
        raise MatrixFailure("selected model snapshot differs from the recorded baseline")
    source_files_before = expected_selected_source_state(selected)

    versions: list[dict[str, object]] | None = None
    candidate_error: Exception | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=LIVE_FAULT_TEMPORARY_PREFIX
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            versions = [
                run_live_fault_injection_candidate(
                    candidate,
                    temporary_root,
                    selected=selected,
                )
                for candidate in EXACT_CANDIDATES
            ]
    except Exception as error:
        candidate_error = error

    try:
        source_version_after = source_provider_version(
            SOURCE_OLLAMA_BASE_URL
        )
        catalog_after = source_catalog_rows(SOURCE_OLLAMA_BASE_URL)
        running_after = source_running_model_names(SOURCE_OLLAMA_BASE_URL)
        source_files_after = selected_source_state(
            source_models_directory,
            selected,
        )
    except Exception:
        raise MatrixFailure(
            "post-run observed source readback failed inside the "
            "non-retained local-model boundary"
        ) from None
    if (
        source_version_after != source_version_before
        or catalog_after != catalog_before
        or running_after != running_before
        or source_files_after != source_files_before
    ):
        raise MatrixFailure(
            "observed source provider version, catalog identity projection, "
            "running identity set, or selected file bytes changed during the "
            "isolated fault-injection run"
        )
    if candidate_error is not None:
        raise candidate_error
    if versions is None:
        raise MatrixFailure("live fault-injection matrix produced no results")

    result = live_fault_injection_result(
        source_version=source_version_before,
        catalog_model_count=len(catalog_before),
        selected=selected,
        versions=versions,
    )
    serialized = json.dumps(
        result,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if selected.provider_model_id in serialized:
        raise MatrixFailure(
            "live fault-injection result retained the selected model name"
        )
    return result


def run_model_backed_matrix(
    source_models_directory: Path,
    *,
    include_duration_evidence: bool = False,
) -> dict[str, object]:
    return run_selected_model_backed_matrix(
        source_models_directory,
        profile=CHAT_MODEL_BACKED_PROFILE,
        include_duration_evidence=include_duration_evidence,
    )


def run_embedding_model_backed_matrix(
    source_models_directory: Path,
    *,
    include_duration_evidence: bool = False,
) -> dict[str, object]:
    return run_selected_model_backed_matrix(
        source_models_directory,
        profile=EMBEDDING_MODEL_BACKED_PROFILE,
        include_duration_evidence=include_duration_evidence,
    )


def run_vision_model_backed_matrix(
    source_models_directory: Path,
    *,
    include_duration_evidence: bool = False,
) -> dict[str, object]:
    return run_selected_model_backed_matrix(
        source_models_directory,
        profile=VISION_MODEL_BACKED_PROFILE,
        include_duration_evidence=include_duration_evidence,
    )


def run_cli_model_backed_matrix(
    source_models_directory: Path,
    *,
    profile: ModelBackedProfile,
    include_duration_evidence: bool = False,
) -> dict[str, object]:
    try:
        return run_selected_model_backed_matrix(
            source_models_directory,
            profile=profile,
            include_duration_evidence=include_duration_evidence,
        )
    except (MatrixFailure, OSError, subprocess.SubprocessError):
        raise MatrixFailure(
            f"{profile.runner_id} failed inside the non-retained local-model "
            "boundary"
        ) from None


def run_cli_embedding_semantic_quality_matrix(
    source_models_directory: Path,
) -> dict[str, object]:
    try:
        return run_embedding_semantic_quality_matrix(
            source_models_directory
        )
    except (MatrixFailure, OSError, subprocess.SubprocessError):
        raise MatrixFailure(
            f"{EMBEDDING_SEMANTIC_QUALITY_FIXTURE_ID} failed inside the "
            "non-retained local-model boundary"
        ) from None


def run_cli_live_fault_injection_matrix(
    source_models_directory: Path,
) -> dict[str, object]:
    try:
        return run_live_fault_injection_matrix(source_models_directory)
    except (MatrixFailure, OSError, subprocess.SubprocessError):
        raise MatrixFailure(
            f"{LIVE_FAULT_INJECTION_FIXTURE_ID} failed inside the "
            "non-retained local-model boundary"
        ) from None


def run_empty_catalog_matrix() -> dict[str, object]:
    if os.uname().sysname != "Darwin":
        raise MatrixFailure("the recorded Darwin compatibility matrix requires macOS")

    with tempfile.TemporaryDirectory(
        prefix="aetherlink-ollama-compatibility-"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        versions = [
            run_candidate(candidate, temporary_root)
            for candidate in EXACT_CANDIDATES
        ]

    return {
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "fixtureId": RUNNER_ID,
        "recordedDate": RECORDED_DATE,
        "schemaVersion": 1,
        "versions": versions,
    }


def parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded exact-version Ollama compatibility matrix."
    )
    model_mode = parser.add_mutually_exclusive_group()
    model_mode.add_argument(
        "--model-backed",
        action="store_true",
        help=(
            "use one automatically selected installed chat model through an "
            "isolated copy-on-write snapshot"
        ),
    )
    model_mode.add_argument(
        "--embedding-backed",
        action="store_true",
        help=(
            "use one automatically selected installed embedding model through "
            "an isolated copy-on-write snapshot"
        ),
    )
    model_mode.add_argument(
        "--vision-backed",
        action="store_true",
        help=(
            "use one automatically selected installed vision and completion "
            "model through an isolated copy-on-write snapshot"
        ),
    )
    parser.add_argument(
        "--duration-evidence",
        action="store_true",
        help=(
            "include one non-canonical monotonic duration observation for each "
            "model-backed version and phase"
        ),
    )
    parser.add_argument(
        "--live-fault-injection",
        action="store_true",
        help=(
            "run the separate bounded chat provider process-lifecycle fault "
            "matrix; requires --model-backed"
        ),
    )
    parser.add_argument(
        "--semantic-quality",
        action="store_true",
        help=(
            "run the separate fixed-task embedding semantic-quality matrix; "
            "requires --embedding-backed"
        ),
    )
    parser.add_argument(
        "--source-model-store",
        type=Path,
        help=(
            "source Ollama model store for any model-backed mode; defaults "
            "to OLLAMA_MODELS or the current user's standard Ollama store"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    if os.uname().sysname != "Darwin":
        raise MatrixFailure("the recorded Darwin compatibility matrix requires macOS")
    args = parse_arguments(arguments)
    if (
        args.source_model_store is not None
        and not args.model_backed
        and not args.embedding_backed
        and not args.vision_backed
    ):
        raise MatrixFailure(
            "--source-model-store requires a model-backed mode"
        )
    if (
        args.duration_evidence
        and not args.model_backed
        and not args.embedding_backed
        and not args.vision_backed
    ):
        raise MatrixFailure(
            "--duration-evidence requires a model-backed mode"
        )
    if args.semantic_quality and not args.embedding_backed:
        raise MatrixFailure(
            "--semantic-quality requires --embedding-backed"
        )
    if args.semantic_quality and args.duration_evidence:
        raise MatrixFailure(
            "--semantic-quality cannot be combined with "
            "--duration-evidence"
        )
    if args.semantic_quality and args.live_fault_injection:
        raise MatrixFailure(
            "--semantic-quality cannot be combined with "
            "--live-fault-injection"
        )
    if args.live_fault_injection and not args.model_backed:
        raise MatrixFailure(
            "--live-fault-injection requires --model-backed"
        )
    if args.live_fault_injection and args.duration_evidence:
        raise MatrixFailure(
            "--live-fault-injection cannot be combined with "
            "--duration-evidence"
        )

    if args.model_backed or args.embedding_backed or args.vision_backed:
        configured_store = os.environ.get("OLLAMA_MODELS")
        source_model_store = args.source_model_store or (
            Path(configured_store)
            if configured_store
            else Path.home() / ".ollama" / "models"
        )
        if args.vision_backed:
            profile = VISION_MODEL_BACKED_PROFILE
        elif args.embedding_backed:
            profile = EMBEDDING_MODEL_BACKED_PROFILE
        else:
            profile = CHAT_MODEL_BACKED_PROFILE
        if args.semantic_quality:
            result = run_cli_embedding_semantic_quality_matrix(
                source_model_store,
            )
        elif args.live_fault_injection:
            result = run_cli_live_fault_injection_matrix(
                source_model_store,
            )
        else:
            result = run_cli_model_backed_matrix(
                source_model_store,
                profile=profile,
                include_duration_evidence=args.duration_evidence,
            )
    else:
        result = run_empty_catalog_matrix()

    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MatrixFailure, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Ollama compatibility matrix failed: {error}") from error
