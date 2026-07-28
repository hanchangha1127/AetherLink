#!/usr/bin/env python3
"""Run the bounded exact-version Ollama compatibility matrix on macOS."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
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
COMMAND_DEADLINE_SECONDS = 300

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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    label: str,
) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=COMMAND_DEADLINE_SECONDS,
        check=False,
    )
    if result.returncode != 0:
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


def endpoint_is_available(base_url: str) -> bool:
    try:
        fetch_version(base_url, timeout=0.5)
        return True
    except (
        MatrixFailure,
        OSError,
        TimeoutError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ):
        return False


def wait_until_ready(base_url: str, expected_version: str) -> None:
    deadline = time.monotonic() + START_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        try:
            observed_version = fetch_version(base_url, timeout=0.5)
        except (
            MatrixFailure,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ):
            time.sleep(0.1)
            continue
        if observed_version != expected_version:
            raise MatrixFailure("provider version did not match the exact candidate")
        return
    raise MatrixFailure("provider did not become ready before the deadline")


def stop_provider(process: subprocess.Popen[bytes], base_url: str) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=STOP_DEADLINE_SECONDS)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait(timeout=STOP_DEADLINE_SECONDS)
            raise MatrixFailure("provider required forced termination") from error
    if endpoint_is_available(base_url):
        raise MatrixFailure("provider endpoint remained available after stop")


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
            process = subprocess.Popen(
                [str(binary), "serve"],
                cwd=extracted,
                env=server_environment,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
            )
            phase_passed = False
            try:
                wait_until_ready(base_url, version)
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


def main() -> int:
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

    result = {
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "fixtureId": RUNNER_ID,
        "recordedDate": RECORDED_DATE,
        "schemaVersion": 1,
        "versions": versions,
    }
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MatrixFailure, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Ollama compatibility matrix failed: {error}") from error
