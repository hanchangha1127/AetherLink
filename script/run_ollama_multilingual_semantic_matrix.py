#!/usr/bin/env python3
"""Run the bounded five-locale Ollama embedding semantic matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unicodedata

if __package__:
    from . import run_ollama_compatibility_matrix as base
else:
    try:
        import run_ollama_compatibility_matrix as base
    except ModuleNotFoundError:
        from script import run_ollama_compatibility_matrix as base


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ID = (
    "aetherlink-ollama-embedding-multilingual-semantic-quality-v2"
)
RECORDED_DATE = "2026-07-29"
EVIDENCE_BOUNDARY = (
    "one-local-macos-existing-embedding-model-five-supported-locales-"
    "twenty-fixed-within-locale-ranking-scenarios-two-permuted-batches-"
    "two-exact-ollama-versions-both-observed-korean-positive-margin-"
    "failure-plus-fresh-recovery-no-model-download-or-retained-model-name-"
    "input-id-vector-dimension-score-output-no-chat-vision-lm-studio-"
    "cross-locale-retrieval-accuracy-long-text-soak-sla-or-qualification"
)
SUPPORTED_LOCALES = ("en", "ko", "ja", "zh-CN", "fr")
LOCALE_SLUGS = {
    "en": "en",
    "ko": "ko",
    "ja": "ja",
    "zh-CN": "zh-cn",
    "fr": "fr",
}
LOCALE_COUNT = 5
SCENARIOS_PER_LOCALE = 4
TEXTS_PER_LOCALE = 16
SCENARIO_COUNT = 20
TEXTS_PER_BATCH = 80
BATCH_CALLS_PER_VERSION = 2
EMBEDDING_COUNT_PER_VERSION = 160
MINIMUM_MARGIN_BASIS_POINTS = 200
MINIMUM_REPEAT_BASIS_POINTS = 9_990
ADAPTER_DEADLINE_SECONDS = 180
SECOND_CALL_ORDER_POLICY = "reverse-first-call"
TASK_SET_ID = (
    "aetherlink-ollama-embedding-multilingual-semantic-task-set-v2"
)
TASK_SET_PATH = (
    ROOT
    / "shared"
    / "evaluation"
    / "ollama-embedding-multilingual-semantic-quality-v2.json"
)
TASK_SET_COPY_NAME = (
    "ollama-embedding-multilingual-semantic-quality-v2.json"
)
TASK_SET_SHA256 = (
    "a4dde8d94f661fe9682103875ed53db703761722c19ec32b35ceba72ecae2e31"
)
SWIFT_SOURCE_PATH = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaEmbeddingMultilingualSemanticQualityTests.swift"
)
SWIFT_SOURCE_SHA256 = (
    "62ff0de9a1bffa9f42d65d89bd5b4622286ed4cf31ff4b1d0e00306bc5ace768"
)
RECOVERY_SOURCE_PATH = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaBackendTests.swift"
)
RECOVERY_SOURCE_SHA256 = (
    "e48dc934496c0473866d7c819cffa20bacd8411271628ed55e52be5ba34881c0"
)
BASE_RUNNER_SOURCE_PATH = (
    ROOT / "script" / "run_ollama_compatibility_matrix.py"
)
BASE_RUNNER_SOURCE_SHA256 = (
    "7a7ff27b84387f56d712e7ed6fc3bd926796a159c76bfbd2e3b57878e2b23014"
)
RECORDED_RUNNER_SOURCE_SHA256 = (
    "5362015be1e3f7f565e50389a0fa5b094b6c32a67e797b1ddf0686916118707b"
)
LIVE_TEST_FILTER = (
    "OllamaEmbeddingMultilingualSemanticQualityTests."
    "testLiveOllamaExactVersionInstalledEmbeddingMultilingualSemanticQuality"
)
ENABLE_ENVIRONMENT_KEY = (
    "AETHERLINK_RUN_OLLAMA_LIVE_EMBEDDING_MULTILINGUAL_"
    "SEMANTIC_QUALITY_TEST"
)
TASK_SET_PATH_ENVIRONMENT_KEY = (
    "AETHERLINK_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_TASK_SET_PATH"
)
TASK_SET_SHA_ENVIRONMENT_KEY = (
    "AETHERLINK_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_TASK_SET_SHA256"
)
TEMPORARY_PREFIX = (
    "aetherlink-ollama-embedding-semantic-quality-v2-"
)
RUNNER_SOURCE_DIGEST_PATTERN = re.compile(
    r"(?m)^(RECORDED_RUNNER_SOURCE_SHA256 = \(\n"
    r'    ")[0-9a-f]{64}("\n\))$'
)


MatrixFailure = base.MatrixFailure


def exact_regular_file_bytes(
    path: Path,
    *,
    label: str,
    maximum_size: int,
) -> bytes:
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise MatrixFailure(f"{label} was unavailable") from error
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or resolved != path
        or metadata.st_size <= 0
        or metadata.st_size > maximum_size
    ):
        raise MatrixFailure(f"{label} boundary was invalid")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise MatrixFailure(f"{label} was unreadable") from error
    if len(data) != metadata.st_size:
        raise MatrixFailure(f"{label} changed while being read")
    return data


def normalized_runner_source_sha256(source: str) -> str:
    normalized, replacement_count = RUNNER_SOURCE_DIGEST_PATTERN.subn(
        lambda match: match.group(1) + ("0" * 64) + match.group(2),
        source,
    )
    if replacement_count != 1:
        raise MatrixFailure(
            "multilingual semantic runner must contain one source digest"
        )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def assert_bound_sources() -> None:
    runner_data = exact_regular_file_bytes(
        Path(__file__).resolve(),
        label="multilingual semantic runner source",
        maximum_size=1 * 1_024 * 1_024,
    )
    try:
        runner_source = runner_data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MatrixFailure(
            "multilingual semantic runner source was not UTF-8"
        ) from error
    if (
        normalized_runner_source_sha256(runner_source)
        != RECORDED_RUNNER_SOURCE_SHA256
    ):
        raise MatrixFailure(
            "multilingual semantic runner source bytes drifted"
        )
    for label, path, expected_sha256 in (
        (
            "base compatibility runner",
            BASE_RUNNER_SOURCE_PATH,
            BASE_RUNNER_SOURCE_SHA256,
        ),
        (
            "multilingual scorer and live assertion",
            SWIFT_SOURCE_PATH,
            SWIFT_SOURCE_SHA256,
        ),
        (
            "embedding recovery assertion",
            RECOVERY_SOURCE_PATH,
            RECOVERY_SOURCE_SHA256,
        ),
    ):
        data = exact_regular_file_bytes(
            path,
            label=label,
            maximum_size=8 * 1_024 * 1_024,
        )
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise MatrixFailure(f"{label} source bytes drifted")
    base.assert_recorded_embedding_semantic_quality_swift_sources()


def is_bounded_identifier(value: object) -> bool:
    if type(value) is not str:
        return False
    encoded = value.encode("utf-8")
    return (
        1 <= len(encoded) <= 64
        and all(
            "a" <= character <= "z"
            or "0" <= character <= "9"
            or character == "-"
            for character in value
        )
    )


def is_valid_task_text(value: object) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if (
        len(encoded) > 512
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        return False
    for character in value:
        category = unicodedata.category(character)
        if category in {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}:
            return False
        if character.isspace() and character != " ":
            return False
    return True


def validate_task_set(value: object) -> None:
    expected_root_keys = {
        "firstCall",
        "fixtureId",
        "locales",
        "minimumPositiveMarginBasisPoints",
        "minimumRepeatCosineBasisPoints",
        "scenarios",
        "schemaVersion",
        "secondCallOrderPolicy",
    }
    if not isinstance(value, dict) or set(value) != expected_root_keys:
        raise MatrixFailure(
            "multilingual semantic task set had an unexpected root shape"
        )
    if (
        value["fixtureId"] != TASK_SET_ID
        or base.exact_int(
            value["schemaVersion"],
            label="multilingual semantic task set schemaVersion",
        )
        != 2
        or value["locales"] != list(SUPPORTED_LOCALES)
        or base.exact_int(
            value["minimumPositiveMarginBasisPoints"],
            label="multilingual semantic minimum positive margin",
        )
        != MINIMUM_MARGIN_BASIS_POINTS
        or base.exact_int(
            value["minimumRepeatCosineBasisPoints"],
            label="multilingual semantic minimum repeat cosine",
        )
        != MINIMUM_REPEAT_BASIS_POINTS
        or value["secondCallOrderPolicy"] != SECOND_CALL_ORDER_POLICY
    ):
        raise MatrixFailure(
            "multilingual semantic task set metadata was invalid"
        )

    first_call = value["firstCall"]
    if not isinstance(first_call, list) or len(first_call) != TEXTS_PER_BATCH:
        raise MatrixFailure(
            "multilingual semantic first batch shape was invalid"
        )
    inputs_by_id: dict[str, dict[str, str]] = {}
    locale_text_counts = {locale: 0 for locale in SUPPORTED_LOCALES}
    for row in first_call:
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "locale", "text"}
            or type(row["id"]) is not str
            or type(row["locale"]) is not str
            or type(row["text"]) is not str
        ):
            raise MatrixFailure(
                "multilingual semantic input shape was invalid"
            )
        input_id = row["id"]
        locale = row["locale"]
        slug = LOCALE_SLUGS.get(locale)
        if (
            not is_bounded_identifier(input_id)
            or slug is None
            or not input_id.startswith(f"{slug}-")
            or not is_valid_task_text(row["text"])
            or input_id in inputs_by_id
        ):
            raise MatrixFailure(
                "multilingual semantic input boundary was invalid"
            )
        inputs_by_id[input_id] = row
        locale_text_counts[locale] += 1
    if any(
        count != TEXTS_PER_LOCALE
        for count in locale_text_counts.values()
    ):
        raise MatrixFailure(
            "multilingual semantic locale text counts were invalid"
        )

    scenarios = value["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != SCENARIO_COUNT:
        raise MatrixFailure(
            "multilingual semantic scenario shape was invalid"
        )
    scenario_keys = {
        "hardNegativeId",
        "id",
        "locale",
        "positiveId",
        "queryId",
        "unrelatedNegativeId",
    }
    scenario_ids: set[str] = set()
    referenced_ids: list[str] = []
    locale_scenario_counts = {
        locale: 0 for locale in SUPPORTED_LOCALES
    }
    for scenario in scenarios:
        if (
            not isinstance(scenario, dict)
            or set(scenario) != scenario_keys
            or any(type(scenario[key]) is not str for key in scenario)
        ):
            raise MatrixFailure(
                "multilingual semantic scenario row was invalid"
            )
        scenario_id = scenario["id"]
        locale = scenario["locale"]
        slug = LOCALE_SLUGS.get(locale)
        role_ids = [
            scenario["queryId"],
            scenario["positiveId"],
            scenario["hardNegativeId"],
            scenario["unrelatedNegativeId"],
        ]
        if (
            not is_bounded_identifier(scenario_id)
            or slug is None
            or not scenario_id.startswith(f"{slug}-")
            or scenario_id in scenario_ids
            or len(set(role_ids)) != 4
            or any(
                inputs_by_id.get(role_id, {}).get("locale") != locale
                for role_id in role_ids
            )
        ):
            raise MatrixFailure(
                "multilingual semantic scenario boundary was invalid"
            )
        scenario_ids.add(scenario_id)
        referenced_ids.extend(role_ids)
        locale_scenario_counts[locale] += 1
    if (
        len(referenced_ids) != TEXTS_PER_BATCH
        or len(set(referenced_ids)) != TEXTS_PER_BATCH
        or set(referenced_ids) != set(inputs_by_id)
        or any(
            count != SCENARIOS_PER_LOCALE
            for count in locale_scenario_counts.values()
        )
    ):
        raise MatrixFailure(
            "multilingual semantic scenario references were invalid"
        )


def recorded_task_set_bytes() -> bytes:
    data = exact_regular_file_bytes(
        TASK_SET_PATH,
        label="recorded multilingual semantic task set",
        maximum_size=64 * 1_024,
    )
    if hashlib.sha256(data).hexdigest() != TASK_SET_SHA256:
        raise MatrixFailure(
            "recorded multilingual semantic task set bytes drifted"
        )
    value = base.strict_json_loads(
        data,
        label="recorded multilingual semantic task set",
    )
    validate_task_set(value)
    return data


def create_task_set_copy(candidate_root: Path) -> Path:
    data = recorded_task_set_bytes()
    destination = candidate_root / TASK_SET_COPY_NAME
    if destination.exists() or destination.is_symlink():
        raise MatrixFailure(
            "multilingual semantic task set destination already existed"
        )
    destination.write_bytes(data)
    destination.chmod(0o600)
    if (
        destination.is_symlink()
        or not destination.is_file()
        or base.file_sha256(destination) != TASK_SET_SHA256
    ):
        raise MatrixFailure(
            "multilingual semantic task set copy was invalid"
        )
    return destination


def semantic_adapter_environment(
    *,
    base_url: str,
    candidate: dict[str, str],
    models_directory: Path,
    selected: base.SelectedLocalModel,
    task_set_path: Path,
) -> dict[str, str]:
    if (
        not task_set_path.is_file()
        or task_set_path.is_symlink()
        or task_set_path.name != TASK_SET_COPY_NAME
        or base.file_sha256(task_set_path) != TASK_SET_SHA256
    ):
        raise MatrixFailure(
            "multilingual semantic task set copy was invalid"
        )
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
    environment.update(
        {
            ENABLE_ENVIRONMENT_KEY: "1",
            TASK_SET_PATH_ENVIRONMENT_KEY: str(task_set_path),
            TASK_SET_SHA_ENVIRONMENT_KEY: TASK_SET_SHA256,
        }
    )
    return environment


def locale_results() -> list[dict[str, object]]:
    return [
        {
            "allMarginsPassed": True,
            "allScenarioRankingsPassed": True,
            "locale": locale,
            "repeatabilityPassed": True,
            "scenarioCount": SCENARIOS_PER_LOCALE,
            "textCount": TEXTS_PER_LOCALE,
        }
        for locale in SUPPORTED_LOCALES
    ]


def failed_locale_results(
    *,
    failed_locale: str,
    failed_scenario_ordinal: int,
) -> list[dict[str, object]]:
    try:
        failed_locale_index = SUPPORTED_LOCALES.index(failed_locale)
    except ValueError as error:
        raise MatrixFailure(
            "multilingual semantic failure locale was invalid"
        ) from error
    if not 1 <= failed_scenario_ordinal <= SCENARIOS_PER_LOCALE:
        raise MatrixFailure(
            "multilingual semantic failure scenario ordinal was invalid"
        )
    results: list[dict[str, object]] = []
    for locale_index, locale in enumerate(SUPPORTED_LOCALES):
        if locale_index < failed_locale_index:
            ranking_status = "passed"
            ranking_scenarios_passed = SCENARIOS_PER_LOCALE
        elif locale_index == failed_locale_index:
            ranking_status = "failed-positive-margin"
            ranking_scenarios_passed = failed_scenario_ordinal - 1
        else:
            ranking_status = "not-evaluated-after-failure"
            ranking_scenarios_passed = 0
        results.append(
            {
                "locale": locale,
                "rankingScenariosPassed": ranking_scenarios_passed,
                "rankingStatus": ranking_status,
                "repeatabilityEvaluated": False,
            }
        )
    return results


def classify_expected_semantic_failure(
    log_path: Path,
) -> dict[str, object] | None:
    try:
        metadata = log_path.lstat()
        if (
            log_path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > base.SWIFT_TEST_LOG_BYTE_LIMIT
        ):
            return None
        log_data = log_path.read_bytes()
        if len(log_data) != metadata.st_size:
            return None
        log_text = log_data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    expected_suite, separator, expected_method = (
        LIVE_TEST_FILTER.rpartition(".")
    )
    if not separator or not expected_suite or not expected_method:
        return None
    expected_identifier = (
        expected_suite.rsplit(".", 1)[-1],
        expected_method,
    )
    events: dict[str, list[tuple[str, str]]] = {
        "started": [],
        "passed": [],
        "failed": [],
        "skipped": [],
    }
    prefix = "Test Case '-["
    event_markers = {
        "started": "]' started.",
        "passed": "]' passed (",
        "failed": "]' failed (",
        "skipped": "]' skipped (",
    }
    for line in log_text.splitlines():
        if not line.startswith(prefix):
            continue
        status: str | None = None
        payload: str | None = None
        for candidate_status, marker in event_markers.items():
            if (
                candidate_status == "started"
                and line.endswith(marker)
            ):
                status = candidate_status
                payload = line[len(prefix) : -len(marker)]
                break
            if candidate_status != "started" and marker in line:
                status = candidate_status
                payload = line[len(prefix) : line.index(marker)]
                break
        if status is None or payload is None:
            return None
        suite, event_separator, method = payload.rpartition(" ")
        if not event_separator:
            return None
        events[status].append((suite.rsplit(".", 1)[-1], method))
    if (
        events["started"] != [expected_identifier]
        or events["failed"] != [expected_identifier]
        or events["passed"]
        or events["skipped"]
    ):
        return None

    if (
        log_text.count("positiveMarginFailed") != 1
        or any(
            marker in log_text
            for marker in (
                "repeatabilityFailed",
                "invalidTaskSet",
                "invalidEmbeddingShape",
                "invalidEmbeddingValue",
                "scenarioID",
                "inputID",
            )
        )
    ):
        return None
    error_lines = [
        line for line in log_text.splitlines() if ": error:" in line
    ]
    if (
        len(error_lines) != 1
        or error_lines[0].count("positiveMarginFailed") != 1
    ):
        return None
    coordinate_pattern = re.compile(
        r"positiveMarginFailed\(locale: "
        r'(?:"([^"\\]+)"|\\"([^"\\]+)\\"), '
        r"scenarioOrdinalWithinLocale: ([0-9]+)\)"
    )
    coordinates = coordinate_pattern.findall(log_text)
    if len(coordinates) != 1:
        return None
    raw_locale, escaped_locale, ordinal_text = coordinates[0]
    locale = raw_locale or escaped_locale
    try:
        ordinal = int(ordinal_text)
    except ValueError:
        return None
    if (
        locale not in SUPPORTED_LOCALES
        or not 1 <= ordinal <= SCENARIOS_PER_LOCALE
    ):
        return None

    task_set = base.strict_json_loads(
        recorded_task_set_bytes(),
        label="recorded multilingual semantic failure task set",
    )
    try:
        validate_task_set(task_set)
    except MatrixFailure:
        return None
    retained_tokens: list[str] = []
    for row in task_set["firstCall"]:
        retained_tokens.extend(
            (
                row["id"],
                row["text"],
                json.dumps(row["text"], ensure_ascii=True)[1:-1],
            )
        )
    retained_tokens.extend(
        scenario["id"] for scenario in task_set["scenarios"]
    )
    if any(token and token in log_text for token in retained_tokens):
        return None

    return {
        "adapterTestPassed": False,
        "allLocalesPassed": False,
        "allMarginsPassed": False,
        "allScenarioRankingsPassed": False,
        "embeddingBatchCompleted": True,
        "embeddingShapeValidated": True,
        "endpointUnavailableAfterStop": True,
        "exactTestCaseExecuted": True,
        "failureCheck": "positive-margin",
        "failureLocale": locale,
        "failureScenarioOrdinalWithinLocale": ordinal,
        "installedStatePreserved": True,
        "localeResults": failed_locale_results(
            failed_locale=locale,
            failed_scenario_ordinal=ordinal,
        ),
        "modelUnloadConfirmed": False,
        "processGroupReaped": True,
        "qualityGatePassed": False,
        "repeatabilityEvaluated": False,
        "snapshotUnchanged": True,
        "sourceBindingsUnchanged": True,
        "taskSetUnchanged": True,
    }


def run_phase(
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
) -> dict[str, object]:
    if phase not in {"semantic", "recovery"}:
        raise MatrixFailure(
            "multilingual semantic phase was not recognized"
        )
    assert_bound_sources()
    process = base.start_live_fault_provider(
        binary=binary,
        extracted=extracted,
        models_directory=models_directory,
        candidate_root=candidate_root,
        log_name=f"multilingual-semantic-{phase}",
        port=port,
        base_url=base_url,
        expected_version=candidate["version"],
    )
    adapter_error: Exception | None = None
    cleanup_error: Exception | None = None
    expected_semantic_failure: dict[str, object] | None = None
    adapter_log_path = (
        candidate_root / f"multilingual-semantic-{phase}-adapter.log"
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
            test_filter = (
                base.EMBEDDING_SEMANTIC_QUALITY_RECOVERY_TEST_FILTER
            )
            timeout_seconds = base.COMMAND_DEADLINE_SECONDS
        base.run_fault_swift_test(
            environment=environment,
            test_filter=test_filter,
            log_path=adapter_log_path,
            label=f"Ollama multilingual semantic {phase} adapter test",
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
                        label="multilingual semantic provider",
                    )
                except Exception as fallback_error:
                    cleanup_error = fallback_error

    if (
        base.model_snapshot_state(models_directory)
        != initial_snapshot_state
    ):
        raise MatrixFailure(
            "isolated model snapshot bytes changed during the multilingual "
            "semantic evaluation"
        )
    if (
        not task_set_path.is_file()
        or task_set_path.is_symlink()
        or base.file_sha256(task_set_path) != TASK_SET_SHA256
    ):
        raise MatrixFailure(
            "multilingual semantic task set bytes changed during the run"
        )
    assert_bound_sources()
    if cleanup_error is not None:
        raise cleanup_error
    if phase == "semantic" and adapter_error is not None:
        expected_semantic_failure = classify_expected_semantic_failure(
            adapter_log_path
        )
        if expected_semantic_failure is not None:
            adapter_error = None
    if adapter_error is not None:
        raise adapter_error
    if expected_semantic_failure is not None:
        return expected_semantic_failure

    common: dict[str, object] = {
        "adapterTestPassed": True,
        "endpointUnavailableAfterStop": True,
        "exactTestCaseExecuted": True,
        "modelUnloadConfirmed": True,
        "processGroupReaped": True,
        "snapshotUnchanged": True,
        "sourceBindingsUnchanged": True,
        "taskSetUnchanged": True,
    }
    if phase == "semantic":
        return {
            **common,
            "allLocalesPassed": True,
            "allMarginsPassed": True,
            "allScenarioRankingsPassed": True,
            "embeddingBatchCompleted": True,
            "embeddingShapeValidated": True,
            "installedStatePreserved": True,
            "localeResults": locale_results(),
            "repeatabilityPassed": True,
        }
    return {
        **common,
        "catalogPopulated": True,
        "embeddingBatchCompleted": True,
        "embeddingShapeValidated": True,
        "installedStatePreserved": True,
    }


def run_candidate(
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
        raise MatrixFailure(
            "isolated model snapshot file count was invalid"
        )
    task_set_path = create_task_set_copy(candidate_root)

    port = base.reserve_unique_port()
    base_url = f"http://127.0.0.1:{port}"
    if base.endpoint_is_available(base_url):
        raise MatrixFailure(
            "reserved loopback port was already serving Ollama"
        )

    semantic = run_phase(
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
    recovery = run_phase(
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


def recorded_fixture() -> dict[str, object]:
    canonical_embedding = base.recorded_selected_model_backed_fixture(
        base.EMBEDDING_MODEL_BACKED_PROFILE
    )
    semantic = {
        "adapterTestPassed": False,
        "allLocalesPassed": False,
        "allMarginsPassed": False,
        "allScenarioRankingsPassed": False,
        "embeddingBatchCompleted": True,
        "embeddingShapeValidated": True,
        "endpointUnavailableAfterStop": True,
        "exactTestCaseExecuted": True,
        "failureCheck": "positive-margin",
        "failureLocale": "ko",
        "failureScenarioOrdinalWithinLocale": 2,
        "installedStatePreserved": True,
        "localeResults": failed_locale_results(
            failed_locale="ko",
            failed_scenario_ordinal=2,
        ),
        "modelUnloadConfirmed": False,
        "processGroupReaped": True,
        "qualityGatePassed": False,
        "repeatabilityEvaluated": False,
        "snapshotUnchanged": True,
        "sourceBindingsUnchanged": True,
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
        "sourceBindingsUnchanged": True,
        "taskSetUnchanged": True,
    }
    versions = [
        {
            "archiveSha256": candidate["archiveSha256"],
            "archiveUrl": candidate["archiveUrl"],
            "recovery": json.loads(json.dumps(recovery)),
            "recoveryRuns": 1,
            "semantic": json.loads(json.dumps(semantic)),
            "semanticRuns": 1,
            "testRuns": 2,
            "version": candidate["version"],
        }
        for candidate in base.EXACT_CANDIDATES
    ]
    return {
        "canonicalFixtureSha256": (
            base.recorded_selected_model_backed_fixture_sha256(
                base.EMBEDDING_MODEL_BACKED_PROFILE
            )
        ),
        "deadlinesMs": {
            "processGroupReap": (
                base.LIVE_FAULT_PROCESS_GROUP_REAP_SECONDS * 1_000
            ),
            "providerReady": int(base.START_DEADLINE_SECONDS * 1_000),
            "recoveryAdapter": (
                base.COMMAND_DEADLINE_SECONDS * 1_000
            ),
            "semanticAdapter": ADAPTER_DEADLINE_SECONDS * 1_000,
            "stop": int(base.STOP_DEADLINE_SECONDS * 1_000),
        },
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "fixtureId": FIXTURE_ID,
        "profile": "embedding",
        "qualityGatePassed": False,
        "recordedDate": RECORDED_DATE,
        "recoveryObservationCount": 2,
        "resultStatus": "observed-quality-failure",
        "runnerSourceSha256": RECORDED_RUNNER_SOURCE_SHA256,
        "schemaVersion": 2,
        "semanticFailureObservationCount": 2,
        "semanticObservationCount": 2,
        "snapshot": canonical_embedding["snapshot"],
        "source": canonical_embedding["source"],
        "sourceBindings": {
            "baseRunnerSha256": BASE_RUNNER_SOURCE_SHA256,
            "recoveryAssertionSha256": RECOVERY_SOURCE_SHA256,
            "scorerAndLiveAssertionSha256": SWIFT_SOURCE_SHA256,
        },
        "taskSet": {
            "fixtureId": TASK_SET_ID,
            "locales": list(SUPPORTED_LOCALES),
            "sha256": TASK_SET_SHA256,
        },
        "thresholds": {
            "batchCallsPerVersion": BATCH_CALLS_PER_VERSION,
            "embeddingCountPerVersion": (
                EMBEDDING_COUNT_PER_VERSION
            ),
            "localeCount": LOCALE_COUNT,
            "minimumPositiveMarginBasisPoints": (
                MINIMUM_MARGIN_BASIS_POINTS
            ),
            "minimumRepeatCosineBasisPoints": (
                MINIMUM_REPEAT_BASIS_POINTS
            ),
            "scenarioCount": SCENARIO_COUNT,
            "scenariosPerLocale": SCENARIOS_PER_LOCALE,
            "textsPerBatch": TEXTS_PER_BATCH,
            "textsPerLocale": TEXTS_PER_LOCALE,
        },
        "versions": versions,
    }


def validate_recorded_fixture(value: object) -> None:
    base.validate_exact_json_value(
        value,
        recorded_fixture(),
        label="recorded multilingual semantic fixture",
    )


def result_for_observation(
    *,
    source_version: str,
    catalog_model_count: int,
    selected: base.SelectedLocalModel,
    versions: list[dict[str, object]],
) -> dict[str, object]:
    result = recorded_fixture()
    result["snapshot"] = {
        "blobCount": len(selected.blobs),
        "copyMode": base.MODEL_BACKED_COPY_MODE,
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
            base.EMBEDDING_MODEL_BACKED_PROFILE.selection_policy
        ),
    }
    result["versions"] = versions
    validate_recorded_fixture(result)
    return result


def string_leaves(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        leaves: set[str] = set()
        for row in value:
            leaves.update(string_leaves(row))
        return leaves
    if isinstance(value, dict):
        leaves = set()
        for key, row in value.items():
            leaves.add(str(key))
            leaves.update(string_leaves(row))
        return leaves
    return set()


def assert_result_does_not_retain_inputs(
    result: dict[str, object],
    *,
    selected_model_id: str,
    source_models_directory: Path,
    task_set: dict[str, object],
) -> None:
    inputs = task_set["firstCall"]
    scenarios = task_set["scenarios"]
    if not isinstance(inputs, list) or not isinstance(scenarios, list):
        raise MatrixFailure(
            "multilingual semantic task set could not be checked for leaks"
        )
    forbidden = {
        selected_model_id,
        str(source_models_directory),
        *(
            str(row[field])
            for row in inputs
            if isinstance(row, dict)
            for field in ("id", "text")
        ),
        *(
            str(row["id"])
            for row in scenarios
            if isinstance(row, dict)
        ),
    }
    leaves = string_leaves(result)
    escaped_forbidden = {
        value: json.dumps(value, ensure_ascii=True)[1:-1]
        for value in forbidden
    }
    for leaf in leaves:
        for value, escaped in escaped_forbidden.items():
            if value in leaf or escaped in leaf:
                raise MatrixFailure(
                    "multilingual semantic result retained raw or escaped "
                    "input"
                )
    serialized = json.dumps(result, ensure_ascii=True, sort_keys=True)
    for value in forbidden:
        if value in serialized:
            raise MatrixFailure(
                "multilingual semantic result retained raw or escaped input"
            )


def run_matrix(source_models_directory: Path) -> dict[str, object]:
    if base.SOURCE_OLLAMA_BASE_URL != "http://127.0.0.1:11434":
        raise MatrixFailure(
            "source provider must remain the default loopback Ollama"
        )
    assert_bound_sources()
    task_set_data = recorded_task_set_bytes()
    task_set = base.strict_json_loads(
        task_set_data,
        label="recorded multilingual semantic task set",
    )
    validate_task_set(task_set)

    source_models_directory = source_models_directory.resolve(strict=True)
    if not source_models_directory.is_dir():
        raise MatrixFailure("source model store must be a directory")
    profile = base.EMBEDDING_MODEL_BACKED_PROFILE
    source_version_before = base.source_provider_version(
        base.SOURCE_OLLAMA_BASE_URL
    )
    candidate_versions = {
        candidate["version"] for candidate in base.EXACT_CANDIDATES
    }
    if (
        source_version_before != profile.recorded_source_version
        or source_version_before not in candidate_versions
    ):
        raise MatrixFailure(
            "source provider version differs from the recorded baseline"
        )
    catalog_before = base.source_catalog_rows(
        base.SOURCE_OLLAMA_BASE_URL
    )
    running_before = base.source_running_model_names(
        base.SOURCE_OLLAMA_BASE_URL
    )
    if len(catalog_before) != profile.recorded_catalog_model_count:
        raise MatrixFailure(
            "source catalog count differs from the recorded baseline"
        )
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
        raise MatrixFailure(
            "selected model snapshot differs from the recorded baseline"
        )
    source_files_before = base.expected_selected_source_state(selected)

    versions: list[dict[str, object]] | None = None
    candidate_error: Exception | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=TEMPORARY_PREFIX
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            versions = [
                run_candidate(
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
        raise MatrixFailure(
            "post-run observed source readback failed inside the "
            "non-retained multilingual semantic boundary"
        ) from None
    if (
        source_version_after != source_version_before
        or catalog_after != catalog_before
        or running_after != running_before
        or source_files_after != source_files_before
    ):
        raise MatrixFailure(
            "observed source provider version, catalog identity projection, "
            "running identity set, or selected file bytes changed during "
            "the isolated multilingual semantic run"
        )
    assert_bound_sources()
    if candidate_error is not None:
        raise candidate_error
    if versions is None:
        raise MatrixFailure(
            "multilingual semantic matrix produced no results"
        )

    result = result_for_observation(
        source_version=source_version_before,
        catalog_model_count=len(catalog_before),
        selected=selected,
        versions=versions,
    )
    assert_result_does_not_retain_inputs(
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
            f"{FIXTURE_ID} failed inside the non-retained local-model "
            "boundary"
        ) from None


def parse_arguments(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded five-locale exact-version Ollama embedding "
            "semantic matrix."
        )
    )
    parser.add_argument(
        "--source-model-store",
        type=Path,
        help=(
            "source Ollama model store; defaults to OLLAMA_MODELS or the "
            "current user's standard Ollama store"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    if os.uname().sysname != "Darwin":
        raise MatrixFailure(
            "the recorded Darwin multilingual matrix requires macOS"
        )
    args = parse_arguments(arguments)
    configured_store = os.environ.get("OLLAMA_MODELS")
    source_model_store = args.source_model_store or (
        Path(configured_store)
        if configured_store
        else Path.home() / ".ollama" / "models"
    )
    result = run_cli_matrix(source_model_store)
    print(
        json.dumps(
            result,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MatrixFailure, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(
            f"Ollama multilingual semantic matrix failed: {error}"
        ) from error
