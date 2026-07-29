#!/usr/bin/env python3
"""Run the exact Ollama matrix for one additional installed chat shape."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

if __package__:
    from . import run_ollama_compatibility_matrix as base
else:
    try:
        import run_ollama_compatibility_matrix as base
    except ModuleNotFoundError:
        from script import run_ollama_compatibility_matrix as base


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ID = "aetherlink-ollama-additional-chat-shape-v1"
RECORDED_DATE = "2026-07-29"
EVIDENCE_BOUNDARY = (
    "one-local-macos-second-smallest-installed-completion-capable-model-"
    "two-exact-ollama-versions-cold-and-restart-chat-cancel-recovery-unload-"
    "no-model-download-or-retained-model-name-prompt-output-path-pid-base-url-"
    "no-embedding-vision-audio-semantic-quality-concurrency-soak-sla-minimum-"
    "version-or-full-qualification"
)
SELECTION_POLICY = (
    "second-smallest-installed-completion-capable-model-must-be-unloaded"
)
SELECTION_ORDINAL = 2
RECORDED_COMPLETION_CANDIDATE_COUNT = 3
RECORDED_SOURCE_VERSION = "0.32.4"
RECORDED_CATALOG_MODEL_COUNT = 4
RECORDED_BLOB_COUNT = 991
RECORDED_MANIFEST_BYTES = 213_712
RECORDED_MODEL_ARTIFACT_BYTES = 16_679_502_421
RECORDED_TARGET_MANIFEST_DIGEST = (
    "21c59a2eae301d2b4ee734f0930728ddc284b4cbf9856b8ad7c3f1c11e056832"
)
RECORDED_TARGET_CAPABILITIES = ("completion", "thinking", "tools")
RECORDED_TARGET_CAPABILITY_COUNT = 3
RECORDED_TARGET_VISION_CAPABLE = False
TEMPORARY_PREFIX = (
    "aetherlink-ollama-model-backed-additional-chat-shape-"
)
BASE_RUNNER_SOURCE_PATH = (
    ROOT / "script" / "run_ollama_compatibility_matrix.py"
)
BASE_RUNNER_SOURCE_SHA256 = (
    "7a7ff27b84387f56d712e7ed6fc3bd926796a159c76bfbd2e3b57878e2b23014"
)
SWIFT_SOURCE_PATH = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaBackendTests.swift"
)
SWIFT_SOURCE_SHA256 = (
    "e48dc934496c0473866d7c819cffa20bacd8411271628ed55e52be5ba34881c0"
)
RECORDED_RUNNER_SOURCE_SHA256 = (
    "318a08ed99fae1ea797ed736fc24f7ad4e199f2f8b85518ba67b9c71fb7bb5a5"
)
RUNNER_SOURCE_DIGEST_PATTERN = re.compile(
    r"(?m)^(RECORDED_RUNNER_SOURCE_SHA256 = \(\n"
    r'    ")[0-9a-f]{64}("\n\))$'
)

PROFILE = base.ModelBackedProfile(
    runner_id=FIXTURE_ID,
    recorded_date=RECORDED_DATE,
    evidence_boundary=EVIDENCE_BOUNDARY,
    live_test_filter=base.MODEL_BACKED_LIVE_TEST_FILTER,
    enable_environment_key=(
        base.CHAT_MODEL_BACKED_PROFILE.enable_environment_key
    ),
    model_id_environment_key=(
        base.CHAT_MODEL_BACKED_PROFILE.model_id_environment_key
    ),
    accepted_capabilities=base.CHAT_MODEL_BACKED_PROFILE.accepted_capabilities,
    recorded_source_version=RECORDED_SOURCE_VERSION,
    recorded_catalog_model_count=RECORDED_CATALOG_MODEL_COUNT,
    recorded_blob_count=RECORDED_BLOB_COUNT,
    recorded_manifest_bytes=RECORDED_MANIFEST_BYTES,
    recorded_model_artifact_bytes=RECORDED_MODEL_ARTIFACT_BYTES,
    selection_policy=SELECTION_POLICY,
    temporary_prefix=TEMPORARY_PREFIX,
    phase_success_keys=base.CHAT_MODEL_BACKED_PROFILE.phase_success_keys,
    required_capabilities=frozenset({"completion"}),
)

MatrixFailure = base.MatrixFailure


@dataclass(frozen=True)
class CatalogCandidate:
    capabilities: tuple[str, ...]
    digest: str
    name: str
    reported_size_bytes: int


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
            "additional chat-shape runner must contain one source digest"
        )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def assert_bound_sources() -> None:
    runner_data = exact_regular_file_bytes(
        Path(__file__).resolve(),
        label="additional chat-shape runner source",
        maximum_size=1 * 1_024 * 1_024,
    )
    try:
        runner_source = runner_data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MatrixFailure(
            "additional chat-shape runner source was not UTF-8"
        ) from error
    if (
        normalized_runner_source_sha256(runner_source)
        != RECORDED_RUNNER_SOURCE_SHA256
    ):
        raise MatrixFailure(
            "additional chat-shape runner source bytes drifted"
        )
    for label, path, expected_sha256 in (
        (
            "base compatibility runner",
            BASE_RUNNER_SOURCE_PATH,
            BASE_RUNNER_SOURCE_SHA256,
        ),
        (
            "chat model live assertion",
            SWIFT_SOURCE_PATH,
            SWIFT_SOURCE_SHA256,
        ),
    ):
        data = exact_regular_file_bytes(
            path,
            label=label,
            maximum_size=8 * 1_024 * 1_024,
        )
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise MatrixFailure(f"{label} source bytes drifted")


def catalog_candidates(
    catalog_rows: tuple[dict[str, object], ...],
    *,
    base_url: str,
) -> tuple[CatalogCandidate, ...]:
    candidates: list[CatalogCandidate] = []
    for row in catalog_rows:
        name = str(row["name"])
        capabilities = base.model_capabilities(base_url, name)
        candidates.append(
            CatalogCandidate(
                capabilities=capabilities,
                digest=str(row["digest"]),
                name=name,
                reported_size_bytes=base.exact_int(
                    row["size"],
                    label="additional chat-shape catalog size",
                    minimum=1,
                ),
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.reported_size_bytes,
                candidate.digest,
            ),
        )
    )


def capability_projection(
    candidates: tuple[CatalogCandidate, ...],
) -> tuple[tuple[str, int, tuple[str, ...]], ...]:
    return tuple(
        (
            candidate.digest,
            candidate.reported_size_bytes,
            candidate.capabilities,
        )
        for candidate in candidates
    )


def completion_candidates(
    candidates: tuple[CatalogCandidate, ...],
) -> tuple[CatalogCandidate, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if (
            PROFILE.accepted_capabilities.intersection(
                frozenset(candidate.capabilities)
            )
            and PROFILE.required_capabilities.issubset(
                frozenset(candidate.capabilities)
            )
        )
    )


def select_recorded_model(
    models_directory: Path,
    *,
    candidates: tuple[CatalogCandidate, ...],
    running_names: frozenset[str],
) -> base.SelectedLocalModel:
    eligible = completion_candidates(candidates)
    if len(eligible) != RECORDED_COMPLETION_CANDIDATE_COUNT:
        raise MatrixFailure(
            "completion-capable catalog count differs from the recorded "
            "additional-shape baseline"
        )
    target = eligible[SELECTION_ORDINAL - 1]
    if base.canonical_model_name(target.name) in running_names:
        raise MatrixFailure(
            "recorded additional chat-shape target was already running"
        )
    if (
        target.digest != RECORDED_TARGET_MANIFEST_DIGEST
        or target.capabilities != RECORDED_TARGET_CAPABILITIES
        or target.reported_size_bytes != RECORDED_MODEL_ARTIFACT_BYTES
        or len(target.capabilities) != RECORDED_TARGET_CAPABILITY_COUNT
        or ("vision" in target.capabilities)
        is not RECORDED_TARGET_VISION_CAPABLE
    ):
        raise MatrixFailure(
            "recorded additional chat-shape target identity drifted"
        )
    manifest_path, manifest_relative_path = base.find_manifest_by_digest(
        models_directory,
        target.digest,
    )
    blobs = base.manifest_blobs(models_directory, manifest_path)
    selected = base.SelectedLocalModel(
        provider_model_id=target.name,
        manifest_digest=target.digest,
        reported_size_bytes=target.reported_size_bytes,
        manifest_source_path=manifest_path,
        manifest_relative_path=manifest_relative_path,
        manifest_size_bytes=manifest_path.stat().st_size,
        blobs=blobs,
        capabilities=target.capabilities,
    )
    if (
        len(selected.blobs) != RECORDED_BLOB_COUNT
        or selected.manifest_size_bytes != RECORDED_MANIFEST_BYTES
        or selected.model_artifact_bytes
        != RECORDED_MODEL_ARTIFACT_BYTES
        or selected.model_artifact_bytes
        != selected.reported_size_bytes
    ):
        raise MatrixFailure(
            "selected additional chat-shape snapshot differs from the "
            "recorded baseline"
        )
    return selected


def recorded_fixture() -> dict[str, object]:
    result = base.recorded_selected_model_backed_fixture(PROFILE)
    return {
        **result,
        "observationCount": 4,
        "profile": "chat",
        "selection": {
            "completionCandidateCount": (
                RECORDED_COMPLETION_CANDIDATE_COUNT
            ),
            "selectionOrdinal": SELECTION_ORDINAL,
            "targetCapabilityCount": RECORDED_TARGET_CAPABILITY_COUNT,
            "targetInitiallyUnloaded": True,
            "targetVisionCapable": RECORDED_TARGET_VISION_CAPABLE,
        },
        "sourceBindings": {
            "baseRunnerSha256": BASE_RUNNER_SOURCE_SHA256,
            "liveAssertionSha256": SWIFT_SOURCE_SHA256,
            "runnerSourceSha256": RECORDED_RUNNER_SOURCE_SHA256,
        },
    }


def validate_recorded_fixture(value: object) -> None:
    base.validate_exact_json_value(
        value,
        recorded_fixture(),
        label="recorded additional chat-shape fixture",
    )


def assert_result_nonretention(
    result: object,
    *,
    selected: base.SelectedLocalModel,
    source_models_directory: Path,
) -> None:
    serialized = json.dumps(
        result,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    forbidden_values = (
        selected.provider_model_id,
        str(source_models_directory),
        str(selected.manifest_source_path),
        selected.manifest_relative_path.as_posix(),
    )
    if any(value and value in serialized for value in forbidden_values):
        raise MatrixFailure(
            "additional chat-shape result retained non-evidence input"
        )


def run_matrix(
    source_models_directory: Path,
) -> dict[str, object]:
    assert_bound_sources()
    if base.SOURCE_OLLAMA_BASE_URL != "http://127.0.0.1:11434":
        raise MatrixFailure(
            "source provider must remain the default loopback Ollama"
        )
    source_models_directory = source_models_directory.resolve(strict=True)
    if not source_models_directory.is_dir():
        raise MatrixFailure("source model store must be a directory")

    source_version_before = base.source_provider_version(
        base.SOURCE_OLLAMA_BASE_URL
    )
    candidate_versions = {
        candidate["version"] for candidate in base.EXACT_CANDIDATES
    }
    if (
        source_version_before != RECORDED_SOURCE_VERSION
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
    if len(catalog_before) != RECORDED_CATALOG_MODEL_COUNT:
        raise MatrixFailure(
            "source catalog count differs from the recorded baseline"
        )
    candidates_before = catalog_candidates(
        catalog_before,
        base_url=base.SOURCE_OLLAMA_BASE_URL,
    )
    selected = select_recorded_model(
        source_models_directory,
        candidates=candidates_before,
        running_names=running_before,
    )
    source_files_before = base.expected_selected_source_state(selected)

    versions: list[dict[str, object]] | None = None
    candidate_error: Exception | None = None
    temporary_root: Path | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix=TEMPORARY_PREFIX
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            versions = [
                base.run_selected_model_backed_candidate(
                    candidate,
                    temporary_root,
                    selected=selected,
                    profile=PROFILE,
                )
                for candidate in base.EXACT_CANDIDATES
            ]
    except Exception as error:
        candidate_error = error
    if (
        temporary_root is not None
        and os.path.lexists(temporary_root)
    ):
        raise MatrixFailure(
            "additional chat-shape temporary cleanup failed"
        ) from None

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
        candidates_after = catalog_candidates(
            catalog_after,
            base_url=base.SOURCE_OLLAMA_BASE_URL,
        )
        source_files_after = base.selected_source_state(
            source_models_directory,
            selected,
        )
    except Exception:
        raise MatrixFailure(
            "post-run observed source readback failed inside the "
            "additional-shape non-retained boundary"
        ) from None
    if (
        source_version_after != source_version_before
        or catalog_after != catalog_before
        or running_after != running_before
        or capability_projection(candidates_after)
        != capability_projection(candidates_before)
        or source_files_after != source_files_before
    ):
        raise MatrixFailure(
            "observed source provider, catalog, capability projection, "
            "running set, or selected bytes changed during the isolated "
            "additional-shape run"
        )
    assert_bound_sources()
    if candidate_error is not None:
        raise candidate_error
    if versions is None:
        raise MatrixFailure(
            "additional chat-shape matrix produced no candidate results"
        )

    result = recorded_fixture()
    result["versions"] = versions
    validate_recorded_fixture(result)
    assert_result_nonretention(
        result,
        selected=selected,
        source_models_directory=source_models_directory,
    )
    return result


def run_cli_matrix(
    source_models_directory: Path,
) -> dict[str, object]:
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
            "Run one additional installed chat-model shape against the two "
            "exact Ollama candidates."
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
            "the recorded additional chat-shape matrix requires macOS"
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
            f"Ollama additional chat-shape matrix failed: {error}"
        ) from error
