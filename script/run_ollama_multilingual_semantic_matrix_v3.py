#!/usr/bin/env python3
"""Run the compact full-matrix multilingual Ollama observation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

if __package__:
    from . import run_ollama_compatibility_matrix as base
    from . import run_ollama_multilingual_semantic_matrix as v2
else:
    try:
        import run_ollama_compatibility_matrix as base
        import run_ollama_multilingual_semantic_matrix as v2
    except ModuleNotFoundError:
        from script import run_ollama_compatibility_matrix as base
        from script import run_ollama_multilingual_semantic_matrix as v2


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ID = "aetherlink-ollama-embedding-multilingual-full-matrix-v3"
SCHEMA_VERSION = 5
PROJECTION_SCHEMA_VERSION = 1
SOURCE_PROVIDER_VERSION = "0.32.5"
SUPPORTED_LOCALES = v2.SUPPORTED_LOCALES
SCENARIOS_PER_LOCALE = v2.SCENARIOS_PER_LOCALE
TEXTS_PER_LOCALE = v2.TEXTS_PER_LOCALE
SCENARIO_COUNT = v2.SCENARIO_COUNT
TEXTS_PER_BATCH = v2.TEXTS_PER_BATCH
BATCH_CALLS_PER_VERSION = v2.BATCH_CALLS_PER_VERSION
RANKING_COMPARISON_COUNT = SCENARIO_COUNT * BATCH_CALLS_PER_VERSION * 2
REPEATABILITY_COMPARISON_COUNT = TEXTS_PER_BATCH
ADAPTER_DEADLINE_SECONDS = 180
EVIDENCE_BOUNDARY = (
    "new-versioned-no-device-full-matrix-observation-five-locales-"
    "twenty-scenarios-two-batches-eighty-ranking-and-eighty-repeatability-"
    "comparisons-two-exact-ollama-candidates-fresh-recovery-bounded-"
    "coordinate-only-output-no-v2-rewrite-no-model-download-or-quality-"
    "preclaim"
)
LIVE_TEST_FILTER = (
    "OllamaEmbeddingMultilingualFullMatrixV3Tests."
    "testLiveOllamaExactVersionInstalledEmbeddingMultilingualFullMatrix"
    "ObservationV3"
)
ENABLE_ENVIRONMENT_KEY = (
    "AETHERLINK_RUN_OLLAMA_LIVE_EMBEDDING_MULTILINGUAL_"
    "FULL_MATRIX_V3_TEST"
)
DIAGNOSTIC_PREFIX = "AETHERLINK_OLLAMA_MULTILINGUAL_FULL_MATRIX_V3="
TEMPORARY_PREFIX = (
    base.EMBEDDING_SEMANTIC_QUALITY_TEMPORARY_PREFIX
    + "full-matrix-v3-"
)
V3_SWIFT_SOURCE_PATH = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaEmbeddingMultilingualFullMatrixV3Tests.swift"
)
RECORDED_RESULT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "ollama-embedding-multilingual-full-matrix-v3.json"
)
V3_SWIFT_SOURCE_SHA256 = (
    "009360901ffd17390a90d5b480e50e9f8e659ae457aa732037b6c4e4d1bd2a9d"
)
V2_RUNNER_SOURCE_PATH = (
    ROOT / "script" / "run_ollama_multilingual_semantic_matrix.py"
)
V2_RUNNER_SOURCE_SHA256 = (
    "0c9f88794f53721c84be495363b626ce3f46786d703a3ebb2867c46239867be0"
)
RUNNER_SOURCE_SHA256 = (
    "58b65494fd0817133649465d7784688724108a1b3842468f963cdeb1a25e670e"
)
RUNNER_SOURCE_DIGEST_PATTERN = re.compile(
    r"(?m)^(RUNNER_SOURCE_SHA256 = \(\n"
    r'    ")[0-9a-f]{64}("\n\))$'
)


MatrixFailure = base.MatrixFailure


def normalized_runner_source_sha256(source: str) -> str:
    normalized, count = RUNNER_SOURCE_DIGEST_PATTERN.subn(
        lambda match: match.group(1) + ("0" * 64) + match.group(2),
        source,
    )
    if count != 1:
        raise MatrixFailure(
            "full-matrix V3 runner must contain one source digest"
        )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def assert_bound_sources() -> None:
    runner_data = v2.exact_regular_file_bytes(
        Path(__file__).resolve(),
        label="full-matrix V3 runner",
        maximum_size=1 * 1_024 * 1_024,
    )
    try:
        runner_source = runner_data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MatrixFailure("full-matrix V3 runner was not UTF-8") from error
    if normalized_runner_source_sha256(runner_source) != RUNNER_SOURCE_SHA256:
        raise MatrixFailure("full-matrix V3 runner source bytes drifted")

    bindings = (
        (
            "embedding request contract",
            v2.EMBEDDING_CONTRACT_SOURCE_PATH,
            v2.EMBEDDING_CONTRACT_SOURCE_SHA256,
        ),
        (
            "Ollama embedding adapter",
            v2.OLLAMA_ADAPTER_SOURCE_PATH,
            v2.OLLAMA_ADAPTER_SOURCE_SHA256,
        ),
        ("V3 scorer", V3_SWIFT_SOURCE_PATH, V3_SWIFT_SOURCE_SHA256),
        ("frozen V2 scorer", v2.SWIFT_SOURCE_PATH, v2.SWIFT_SOURCE_SHA256),
        (
            "recovery assertion",
            v2.RECOVERY_SOURCE_PATH,
            v2.RECOVERY_SOURCE_SHA256,
        ),
        (
            "base compatibility runner",
            v2.BASE_RUNNER_SOURCE_PATH,
            v2.BASE_RUNNER_SOURCE_SHA256,
        ),
        (
            "frozen V2 runner",
            V2_RUNNER_SOURCE_PATH,
            V2_RUNNER_SOURCE_SHA256,
        ),
    )
    for label, path, expected_sha256 in bindings:
        data = v2.exact_regular_file_bytes(
            path,
            label=label,
            maximum_size=8 * 1_024 * 1_024,
        )
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise MatrixFailure(f"{label} source bytes drifted")
    if (
        hashlib.sha256(v2.recorded_task_set_bytes()).hexdigest()
        != v2.TASK_SET_SHA256
    ):
        raise MatrixFailure("frozen V2 task bytes drifted")


def _bounded_int(
    value: object,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    observed = base.exact_int(value, label=label, minimum=minimum)
    if observed > maximum:
        raise MatrixFailure(f"{label} exceeded its maximum")
    return observed


def validate_full_matrix_projection(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "rankingFailures",
        "repeatabilityFailures",
        "schemaVersion",
    }:
        raise MatrixFailure("full-matrix projection shape was invalid")
    if (
        base.exact_int(
            value["schemaVersion"],
            label="full-matrix projection schemaVersion",
        )
        != PROJECTION_SCHEMA_VERSION
    ):
        raise MatrixFailure("full-matrix projection schema was invalid")

    ranking_failures = value["rankingFailures"]
    if (
        type(ranking_failures) is not list
        or len(ranking_failures) > SCENARIO_COUNT
    ):
        raise MatrixFailure("full-matrix ranking failures were invalid")
    ranking_coordinates: list[tuple[int, int]] = []
    for row_index, row in enumerate(ranking_failures):
        if not isinstance(row, dict) or set(row) != {
            "failedBatches",
            "locale",
            "scenarioOrdinalWithinLocale",
        }:
            raise MatrixFailure("full-matrix ranking failure shape was invalid")
        locale = row["locale"]
        if type(locale) is not str or locale not in SUPPORTED_LOCALES:
            raise MatrixFailure("full-matrix ranking locale was invalid")
        ordinal = _bounded_int(
            row["scenarioOrdinalWithinLocale"],
            label=f"rankingFailures[{row_index}] scenario ordinal",
            minimum=1,
            maximum=SCENARIOS_PER_LOCALE,
        )
        batches = row["failedBatches"]
        if (
            type(batches) is not list
            or not 1 <= len(batches) <= BATCH_CALLS_PER_VERSION
        ):
            raise MatrixFailure("full-matrix failed batches were invalid")
        batch_ordinals: list[int] = []
        for batch_index, batch in enumerate(batches):
            if not isinstance(batch, dict) or set(batch) != {
                "batchOrdinal",
                "comparisonFailureCount",
            }:
                raise MatrixFailure(
                    "full-matrix failed batch shape was invalid"
                )
            batch_ordinals.append(
                _bounded_int(
                    batch["batchOrdinal"],
                    label=(
                        f"rankingFailures[{row_index}]."
                        f"failedBatches[{batch_index}] batch ordinal"
                    ),
                    minimum=1,
                    maximum=BATCH_CALLS_PER_VERSION,
                )
            )
            _bounded_int(
                batch["comparisonFailureCount"],
                label=(
                    f"rankingFailures[{row_index}]."
                    f"failedBatches[{batch_index}] comparison count"
                ),
                minimum=1,
                maximum=2,
            )
        if batch_ordinals != sorted(set(batch_ordinals)):
            raise MatrixFailure(
                "full-matrix failed batches were not canonical"
            )
        ranking_coordinates.append(
            (SUPPORTED_LOCALES.index(locale), ordinal)
        )
    if ranking_coordinates != sorted(set(ranking_coordinates)):
        raise MatrixFailure(
            "full-matrix ranking failures were not canonical"
        )

    repeatability_failures = value["repeatabilityFailures"]
    if (
        type(repeatability_failures) is not list
        or len(repeatability_failures) > TEXTS_PER_BATCH
    ):
        raise MatrixFailure(
            "full-matrix repeatability failures were invalid"
        )
    repeatability_coordinates: list[tuple[int, int]] = []
    for index, row in enumerate(repeatability_failures):
        if not isinstance(row, dict) or set(row) != {
            "inputOrdinalWithinLocale",
            "locale",
        }:
            raise MatrixFailure(
                "full-matrix repeatability failure shape was invalid"
            )
        locale = row["locale"]
        if type(locale) is not str or locale not in SUPPORTED_LOCALES:
            raise MatrixFailure(
                "full-matrix repeatability locale was invalid"
            )
        ordinal = _bounded_int(
            row["inputOrdinalWithinLocale"],
            label=f"repeatabilityFailures[{index}] input ordinal",
            minimum=1,
            maximum=TEXTS_PER_LOCALE,
        )
        repeatability_coordinates.append(
            (SUPPORTED_LOCALES.index(locale), ordinal)
        )
    if repeatability_coordinates != sorted(
        set(repeatability_coordinates)
    ):
        raise MatrixFailure(
            "full-matrix repeatability failures were not canonical"
        )


def projection_summary(value: object) -> dict[str, object]:
    validate_full_matrix_projection(value)
    assert isinstance(value, dict)
    ranking_failure_count = sum(
        batch["comparisonFailureCount"]
        for row in value["rankingFailures"]
        for batch in row["failedBatches"]
    )
    repeatability_failure_count = len(value["repeatabilityFailures"])
    if ranking_failure_count > RANKING_COMPARISON_COUNT:
        raise MatrixFailure("full-matrix ranking failure count overflowed")
    return {
        "qualityGatePassed": (
            ranking_failure_count == 0
            and repeatability_failure_count == 0
        ),
        "rankingComparisonsPassed": (
            RANKING_COMPARISON_COUNT - ranking_failure_count
        ),
        "repeatabilityComparisonsPassed": (
            REPEATABILITY_COMPARISON_COUNT
            - repeatability_failure_count
        ),
    }


def parse_full_matrix_observation(
    log_path: Path,
    *,
    forbidden_tokens: set[str],
) -> dict[str, object]:
    data = v2.exact_regular_file_bytes(
        log_path,
        label="full-matrix V3 adapter log",
        maximum_size=base.SWIFT_TEST_LOG_BYTE_LIMIT,
    )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MatrixFailure("full-matrix V3 log was not UTF-8") from error
    base.assert_exact_swift_test_execution(
        log_path=log_path,
        test_filter=LIVE_TEST_FILTER,
        label="full-matrix V3 observation",
    )
    marker_lines = [
        line for line in text.splitlines() if line.startswith(DIAGNOSTIC_PREFIX)
    ]
    if (
        len(marker_lines) != 1
        or text.count(DIAGNOSTIC_PREFIX) != 1
        or any(": error:" in line for line in text.splitlines())
    ):
        raise MatrixFailure("full-matrix V3 observation marker was invalid")
    projection = base.strict_json_loads(
        marker_lines[0][len(DIAGNOSTIC_PREFIX) :].encode("utf-8"),
        label="full-matrix V3 observation",
    )
    validate_full_matrix_projection(projection)
    for token in forbidden_tokens:
        escaped = json.dumps(token, ensure_ascii=True)[1:-1]
        if token and (token in text or escaped in text):
            raise MatrixFailure("full-matrix V3 log retained forbidden input")
    return projection


def semantic_adapter_environment(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: base.SelectedLocalModel,
    task_set_path: Path,
) -> dict[str, str]:
    environment = v2.semantic_adapter_environment(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        task_set_path=task_set_path,
    )
    environment.pop(v2.ENABLE_ENVIRONMENT_KEY, None)
    environment[ENABLE_ENVIRONMENT_KEY] = "1"
    return environment


def _forbidden_log_tokens(
    *,
    selected: base.SelectedLocalModel,
    models_directory: Path,
) -> set[str]:
    task_set = base.strict_json_loads(
        v2.recorded_task_set_bytes(),
        label="frozen V2 multilingual task set",
    )
    v2.validate_task_set(task_set)
    tokens = {selected.provider_model_id, str(models_directory)}
    for row in task_set["firstCall"]:
        tokens.update((row["id"], row["text"]))
    tokens.update(row["id"] for row in task_set["scenarios"])
    return tokens


def _recovery_environment(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: base.SelectedLocalModel,
) -> dict[str, str]:
    environment = base.selected_model_backed_adapter_environment(
        base_url=base_url,
        candidate=candidate,
        models_directory=models_directory,
        selected=selected,
        profile=base.EMBEDDING_MODEL_BACKED_PROFILE,
    )
    environment.pop(
        base.EMBEDDING_MODEL_BACKED_PROFILE.enable_environment_key,
        None,
    )
    environment[
        base.EMBEDDING_SEMANTIC_QUALITY_RECOVERY_ENVIRONMENT_KEY
    ] = "1"
    return environment


def run_phase_v3(
    *,
    binary: Path,
    extracted: Path,
    models_directory: Path,
    candidate_root: Path,
    phase: str,
    port: int,
    base_url: str,
    candidate: dict[str, str],
    selected: base.SelectedLocalModel,
    task_set_path: Path,
    initial_snapshot_state: tuple[tuple[str, int, str], ...],
) -> dict[str, object] | None:
    if phase not in {"semantic", "recovery"}:
        raise MatrixFailure("full-matrix V3 phase was not recognized")
    assert_bound_sources()
    process = base.start_live_fault_provider(
        binary=binary,
        extracted=extracted,
        models_directory=models_directory,
        candidate_root=candidate_root,
        log_name=f"multilingual-full-matrix-v3-{phase}",
        port=port,
        base_url=base_url,
        expected_version=candidate["version"],
    )
    adapter_error: Exception | None = None
    cleanup_error: Exception | None = None
    log_path = (
        candidate_root / f"multilingual-full-matrix-v3-{phase}-adapter.log"
    )
    try:
        if phase == "semantic":
            environment = semantic_adapter_environment(
                base_url=base_url,
                candidate=candidate,
                models_directory=models_directory,
                selected=selected,
                task_set_path=task_set_path,
            )
            test_filter = LIVE_TEST_FILTER
            timeout_seconds = ADAPTER_DEADLINE_SECONDS
        else:
            environment = _recovery_environment(
                base_url=base_url,
                candidate=candidate,
                models_directory=models_directory,
                selected=selected,
            )
            test_filter = (
                base.EMBEDDING_SEMANTIC_QUALITY_RECOVERY_TEST_FILTER
            )
            timeout_seconds = base.COMMAND_DEADLINE_SECONDS
        base.run_fault_swift_test(
            environment=environment,
            test_filter=test_filter,
            log_path=log_path,
            label=f"full-matrix V3 {phase} test",
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        adapter_error = error
    finally:
        try:
            base.stop_provider(
                process,
                base_url,
                signal_process_group=True,
            )
            base.ensure_fault_provider_stopped(process, base_url)
        except Exception as error:
            cleanup_error = error
            if (
                process.poll() is None
                or base.process_group_is_available(process.pid)
            ):
                try:
                    base.kill_process_group_and_wait(
                        process,
                        label="full-matrix V3 provider",
                    )
                except Exception as fallback_error:
                    cleanup_error = fallback_error

    boundary_error: Exception | None = None
    try:
        if (
            base.model_snapshot_state(models_directory)
            != initial_snapshot_state
        ):
            raise MatrixFailure(
                "full-matrix V3 isolated snapshot changed"
            )
        if (
            not task_set_path.is_file()
            or task_set_path.is_symlink()
            or base.file_sha256(task_set_path) != v2.TASK_SET_SHA256
        ):
            raise MatrixFailure("full-matrix V3 task bytes changed")
        assert_bound_sources()
    except Exception as error:
        boundary_error = error
    if cleanup_error is not None:
        raise cleanup_error
    if boundary_error is not None:
        raise boundary_error
    if adapter_error is not None:
        raise adapter_error
    if phase == "semantic":
        return parse_full_matrix_observation(
            log_path,
            forbidden_tokens=_forbidden_log_tokens(
                selected=selected,
                models_directory=models_directory,
            ),
        )
    return None


def run_candidate_v3(
    candidate: dict[str, str],
    temporary_root: Path,
    *,
    selected: base.SelectedLocalModel,
) -> dict[str, object]:
    version = candidate["version"]
    candidate_root = temporary_root / version
    candidate_root.mkdir()
    archive = candidate_root / "ollama-darwin.tgz"
    base.download_archive(candidate, archive)

    extracted = candidate_root / "extracted"
    extracted.mkdir()
    tar = base.shutil.which("tar")
    if tar is None:
        raise MatrixFailure("tar is required")
    base.run_checked(
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

    models_directory = (
        candidate_root / base.MODEL_SNAPSHOT_DIRECTORY_NAME
    )
    initial_snapshot_state = base.create_model_snapshot(
        selected,
        models_directory,
    )
    if len(initial_snapshot_state) != len(selected.blobs) + 1:
        raise MatrixFailure("isolated model snapshot count was invalid")
    task_set_path = v2.create_task_set_copy(candidate_root)
    port = base.reserve_unique_port()
    base_url = f"http://127.0.0.1:{port}"
    if base.endpoint_is_available(base_url):
        raise MatrixFailure("reserved loopback port was already in use")

    phase_arguments = {
        "binary": binary,
        "extracted": extracted,
        "models_directory": models_directory,
        "candidate_root": candidate_root,
        "port": port,
        "base_url": base_url,
        "candidate": candidate,
        "selected": selected,
        "task_set_path": task_set_path,
        "initial_snapshot_state": initial_snapshot_state,
    }
    observation = run_phase_v3(phase="semantic", **phase_arguments)
    run_phase_v3(phase="recovery", **phase_arguments)
    if not isinstance(observation, dict):
        raise MatrixFailure("full-matrix V3 observation was absent")
    return {
        "archiveSha256": candidate["archiveSha256"],
        "observation": observation,
        "recoveryPassed": True,
        "version": version,
    }


def _source_bindings() -> dict[str, str]:
    return {
        "baseRunnerSha256": v2.BASE_RUNNER_SOURCE_SHA256,
        "embeddingRequestContractSha256": (
            v2.EMBEDDING_CONTRACT_SOURCE_SHA256
        ),
        "ollamaEmbeddingAdapterSha256": (
            v2.OLLAMA_ADAPTER_SOURCE_SHA256
        ),
        "recoveryAssertionSha256": v2.RECOVERY_SOURCE_SHA256,
        "v2RunnerSha256": V2_RUNNER_SOURCE_SHA256,
        "v2ScorerAndTaskLoaderSha256": v2.SWIFT_SOURCE_SHA256,
        "v3ScorerAndLiveAssertionSha256": V3_SWIFT_SOURCE_SHA256,
    }


def validate_result_v3(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "evidenceBoundary",
        "fixtureId",
        "qualityGatePassed",
        "runnerSourceSha256",
        "schemaVersion",
        "sourceBindings",
        "sourceProviderVersion",
        "sourceStatePreserved",
        "taskSet",
        "versions",
    }:
        raise MatrixFailure("full-matrix V3 result shape was invalid")
    if (
        value["evidenceBoundary"] != EVIDENCE_BOUNDARY
        or value["fixtureId"] != FIXTURE_ID
        or value["runnerSourceSha256"] != RUNNER_SOURCE_SHA256
        or value["sourceProviderVersion"] != SOURCE_PROVIDER_VERSION
        or base.exact_int(
            value["schemaVersion"],
            label="full-matrix V3 schemaVersion",
        )
        != SCHEMA_VERSION
        or type(value["sourceStatePreserved"]) is not bool
        or not value["sourceStatePreserved"]
    ):
        raise MatrixFailure("full-matrix V3 fixed result fields were invalid")
    base.validate_exact_json_value(
        value["sourceBindings"],
        _source_bindings(),
        label="full-matrix V3 source bindings",
    )
    base.validate_exact_json_value(
        value["taskSet"],
        {"fixtureId": v2.TASK_SET_ID, "sha256": v2.TASK_SET_SHA256},
        label="full-matrix V3 task set",
    )

    versions = value["versions"]
    if type(versions) is not list or len(versions) != len(
        base.EXACT_CANDIDATES
    ):
        raise MatrixFailure("full-matrix V3 versions were invalid")
    quality_results: list[bool] = []
    for candidate, version in zip(base.EXACT_CANDIDATES, versions):
        if not isinstance(version, dict) or set(version) != {
            "archiveSha256",
            "observation",
            "recoveryPassed",
            "version",
        }:
            raise MatrixFailure("full-matrix V3 version shape was invalid")
        if (
            version["version"] != candidate["version"]
            or version["archiveSha256"] != candidate["archiveSha256"]
            or type(version["recoveryPassed"]) is not bool
            or not version["recoveryPassed"]
        ):
            raise MatrixFailure("full-matrix V3 version identity was invalid")
        summary = projection_summary(version["observation"])
        quality_results.append(bool(summary["qualityGatePassed"]))
    quality_gate_passed = all(quality_results)
    if (
        type(value["qualityGatePassed"]) is not bool
        or value["qualityGatePassed"] != quality_gate_passed
    ):
        raise MatrixFailure("full-matrix V3 quality result was invalid")


def recorded_result() -> dict[str, object]:
    data = v2.exact_regular_file_bytes(
        RECORDED_RESULT_PATH,
        label="recorded full-matrix V3 result",
        maximum_size=64 * 1_024,
    )
    value = base.strict_json_loads(
        data,
        label="recorded full-matrix V3 result",
    )
    validate_result_v3(value)
    canonical = (
        json.dumps(
            value,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if data != canonical:
        raise MatrixFailure(
            "recorded full-matrix V3 result was not canonical"
        )
    return value


def result_for_observation(
    *,
    source_version: str,
    versions: list[dict[str, object]],
) -> dict[str, object]:
    result = {
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "fixtureId": FIXTURE_ID,
        "qualityGatePassed": all(
            bool(projection_summary(row["observation"])["qualityGatePassed"])
            for row in versions
        ),
        "runnerSourceSha256": RUNNER_SOURCE_SHA256,
        "schemaVersion": SCHEMA_VERSION,
        "sourceBindings": _source_bindings(),
        "sourceProviderVersion": source_version,
        "sourceStatePreserved": True,
        "taskSet": {
            "fixtureId": v2.TASK_SET_ID,
            "sha256": v2.TASK_SET_SHA256,
        },
        "versions": versions,
    }
    validate_result_v3(result)
    return result


def run_matrix(source_models_directory: Path) -> dict[str, object]:
    if base.SOURCE_OLLAMA_BASE_URL != "http://127.0.0.1:11434":
        raise MatrixFailure("source provider must use the default loopback")
    assert_bound_sources()
    task_set = base.strict_json_loads(
        v2.recorded_task_set_bytes(),
        label="frozen V2 multilingual task set",
    )
    v2.validate_task_set(task_set)

    source_models_directory = source_models_directory.resolve(strict=True)
    if not source_models_directory.is_dir():
        raise MatrixFailure("source model store must be a directory")
    profile = base.EMBEDDING_MODEL_BACKED_PROFILE
    source_version_before = base.source_provider_version(
        base.SOURCE_OLLAMA_BASE_URL
    )
    if (
        source_version_before != SOURCE_PROVIDER_VERSION
        or source_version_before
        not in {row["version"] for row in base.EXACT_CANDIDATES}
    ):
        raise MatrixFailure("source provider version differed from baseline")
    catalog_before = base.source_catalog_rows(base.SOURCE_OLLAMA_BASE_URL)
    running_before = base.source_running_model_names(
        base.SOURCE_OLLAMA_BASE_URL
    )
    if len(catalog_before) != profile.recorded_catalog_model_count:
        raise MatrixFailure("source catalog differed from baseline")
    selected = base.select_source_model(
        source_models_directory,
        profile=profile,
        base_url=base.SOURCE_OLLAMA_BASE_URL,
    )
    if (
        len(selected.blobs) != profile.recorded_blob_count
        or selected.manifest_size_bytes != profile.recorded_manifest_bytes
        or selected.model_artifact_bytes
        != profile.recorded_model_artifact_bytes
    ):
        raise MatrixFailure("selected model differed from baseline")
    source_files_before = base.expected_selected_source_state(selected)

    versions: list[dict[str, object]] | None = None
    candidate_error: Exception | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=TEMPORARY_PREFIX
        ) as temporary_directory:
            temporary_root = Path(temporary_directory).resolve(strict=True)
            versions = [
                run_candidate_v3(
                    candidate,
                    temporary_root,
                    selected=selected,
                )
                for candidate in base.EXACT_CANDIDATES
            ]
    except Exception as error:
        candidate_error = error

    try:
        source_version_after = base.source_provider_version(
            base.SOURCE_OLLAMA_BASE_URL
        )
        catalog_after = base.source_catalog_rows(
            base.SOURCE_OLLAMA_BASE_URL
        )
        running_after = base.source_running_model_names(
            base.SOURCE_OLLAMA_BASE_URL
        )
        source_files_after = base.selected_source_state(
            source_models_directory,
            selected,
        )
    except Exception:
        raise MatrixFailure("full-matrix V3 source readback failed") from None
    if (
        source_version_after != source_version_before
        or catalog_after != catalog_before
        or running_after != running_before
        or source_files_after != source_files_before
    ):
        raise MatrixFailure("full-matrix V3 source state changed")
    assert_bound_sources()
    if candidate_error is not None:
        raise candidate_error
    if versions is None:
        raise MatrixFailure("full-matrix V3 produced no results")

    result = result_for_observation(
        source_version=source_version_before,
        versions=versions,
    )
    v2.assert_result_does_not_retain_inputs(
        result,
        selected_model_id=selected.provider_model_id,
        source_models_directory=source_models_directory,
        task_set=task_set,
    )
    return result


def run_cli_matrix(source_models_directory: Path) -> dict[str, object]:
    try:
        return run_matrix(source_models_directory)
    except (MatrixFailure, OSError, subprocess.SubprocessError):
        raise MatrixFailure(
            f"{FIXTURE_ID} failed inside the non-retained local boundary"
        ) from None


def parse_arguments(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the five-locale exact-version Ollama full-matrix "
            "observation."
        )
    )
    parser.add_argument(
        "--source-model-store",
        type=Path,
        help=(
            "source Ollama model store; defaults to OLLAMA_MODELS or the "
            "standard local store"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    if os.uname().sysname != "Darwin":
        raise MatrixFailure("the Darwin full-matrix runner requires macOS")
    args = parse_arguments(arguments)
    configured_store = os.environ.get("OLLAMA_MODELS")
    source_model_store = args.source_model_store or (
        Path(configured_store)
        if configured_store
        else Path.home() / ".ollama" / "models"
    )
    result = run_cli_matrix(source_model_store)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MatrixFailure, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(
            f"Ollama multilingual full-matrix V3 failed: {error}"
        ) from error
