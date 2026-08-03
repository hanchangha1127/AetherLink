#!/usr/bin/env python3
"""Validate and read back the bounded G7 Android product-nightly lane."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Iterable, Mapping, Optional, Sequence
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/product-nightly.yml"
CHECKER_PATH = Path(__file__).resolve()
WORKFLOW_RELATIVE = ".github/workflows/product-nightly.yml"
CHECKER_RELATIVE = "script/check_product_nightly_ci.py"
CANONICAL_WORKFLOW_SHA256 = (
    "77ce2a1cc0ce112dbe3f47b9061b4ceba30c56ed26d070daef88af44766dfe78"
)
CANONICAL_PARSED_WORKFLOW_SHA256 = (
    "c2e9606a28408c08bffeffb5afe8147e422aecf630a9c33e61cbc69701766a19"
)
EXPECTED_CRON = "37 18 * * *"
PROVENANCE_CONTRACT = "aetherlink-g7-android-headless-nightly-provenance-v2"
PROVENANCE_SCHEMA_VERSION = 2
MAX_WORKFLOW_BYTES = 64 * 1024
MAX_CHECKER_BYTES = 256 * 1024
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_PROVENANCE_BYTES = 128 * 1024
MAX_ARCHIVE_BYTES = 640 * 1024 * 1024
ARCHIVE_PROVENANCE_PATH = "nightly-provenance.json"
LANE_ORDER = ("v1", "v2")
ARCHIVE_LANE_PREFIXES = {
    "v1": "lifecycle-v1/",
    "v2": "lifecycle-v2/",
}
LANE_EVIDENCE_FILE_COUNTS = {"v1": 46, "v2": 72}
LANE_SCENARIO_COUNTS = {"v1": 13, "v2": 5}
LANE_RUN_ID_PATTERNS = {
    "v1": re.compile(r"android-headless-api36-1-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z"),
    "v2": re.compile(r"android-headless-api36-1-v2-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z"),
}
ARCHIVE_FILENAME_PREFIX = "candidate-"
ARCHIVE_PROVENANCE_STATE = "sealed-local-readback-candidate"
ARTIFACT_ACCEPTANCE_POLICY = "same-workflow-run-success-only"

LIFECYCLE_TEST_MODULES = (
    "script.test_run_android_headless_emulator_product_lifecycle",
    "script.test_check_android_headless_emulator_product_lifecycle",
    "script.test_run_android_headless_emulator_product_lifecycle_v2",
    "script.test_check_android_headless_emulator_product_lifecycle_v2",
)
SUCCESSOR_TEST_MODULES = LIFECYCLE_TEST_MODULES[-2:]
CONTRACT_TEST_MODULES = (
    "script.test_check_product_nightly_ci",
) + LIFECYCLE_TEST_MODULES
CONTRACT_TEST_COUNT = 101
CONTRACT_TEST_MANIFEST_SHA256 = (
    "28baa8d8bd8a60028a0d0de117659091092b9d8709f88616402f676eef74f7c8"
)
LIFECYCLE_TEST_COUNT = 86
LIFECYCLE_TEST_MANIFEST_SHA256 = (
    "eb6ae488967921a3e19dae57f8e3026dfc29a0b4491d9d349e82a4386233f412"
)
SUCCESSOR_TEST_COUNT = 41
SUCCESSOR_TEST_MANIFEST_SHA256 = (
    "83544e09194fa5e1498d9eec84ce77d2c17de814994331a5fd8735618f3c4830"
)
LIFECYCLE_EVIDENCE_FILE_COUNT = 72

REQUIRED_WORKFLOW_PREFIX = """name: Product nightly (non-security Android lifecycle subset)

"on":
  schedule:
    - cron: "37 18 * * *"

permissions:
  contents: read

# Uploaded archives remain candidates. A consumer may accept their bytes only
# after this same workflow run reaches a successful final conclusion.
env:
  AETHERLINK_NIGHTLY_ARTIFACT_ACCEPTANCE: same-workflow-run-success-only

concurrency:
  group: product-nightly-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false

defaults:
  run:
    shell: bash

jobs:
"""

PRODUCER_JOB_ID = "android-headless-lifecycle-v1-v2"
READBACK_JOB_ID = "downloaded-artifact-readback"
JOB_IDS = (PRODUCER_JOB_ID, READBACK_JOB_ID)
PRODUCER_STEP_NAMES = (
    "Check out source",
    "Materialize scheduled commit source",
    "Set up JDK 21",
    "Set up Gradle",
    "Validate exact nightly contract",
    "Install exact Android emulator toolchain",
    "Prepare exact Android build dependencies",
    "Run Android API 36.1 lifecycle V1",
    "Independently read back lifecycle V1",
    "Run Android API 36.1 lifecycle V2",
    "Independently read back lifecycle V2",
    "Seal and read back exact dual-lifecycle nightly artifact",
    "Upload one sealed nightly candidate",
    "Bind uploaded candidate digest",
)
READBACK_STEP_NAMES = (
    "Check out source",
    "Download sealed artifact by immutable ID",
    "Read back independently downloaded candidate bytes",
)

FORBIDDEN_PATTERNS = {
    "pull-request trigger": r"(?m)^\s*pull_request(?:_target)?\s*:",
    "push trigger": r"(?m)^\s*push\s*:",
    "manual trigger": r"(?m)^\s*workflow_dispatch\s*:",
    "secret reference": r"\bsecrets\.",
    "identity-token permission": r"(?m)^\s*id-token\s*:",
    "write permission": r"(?m)^\s*[a-z-]+\s*:\s*write\s*$",
    "ignored failure": r"(?m)^\s*continue-on-error\s*:|\|\|\s*true\b",
    "always upload": r"\bif:\s*\$\{\{\s*always\(\)",
    "deployment environment": r"(?m)^\s*environment\s*:",
    "service container": r"(?m)^\s*services\s*:",
    "repository mutation": r"\bgit\s+(?:push|commit|tag)\b",
    "release publication": r"\bgh\s+release\b",
    "signing or notarization": r"\b(?:codesign|notarytool|jarsigner|apksigner)\b",
    "live provider": r"\b(?:Ollama|LM[ _-]?Studio|RUN_LIVE|LIVE_PROVIDER)\b",
    "mixed aggregate gate": r"\bcheck_no_device_quality(?:\.sh)?\b",
}


class NightlyContractError(RuntimeError):
    pass


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def duplicate_rejecting_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise NightlyContractError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def parse_canonical_json(raw: bytes, *, label: str) -> object:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=duplicate_rejecting_object,
            parse_constant=lambda token: (_ for _ in ()).throw(
                NightlyContractError(f"{label} contains {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NightlyContractError(f"{label} is not canonical JSON: {error}") from error
    if canonical_json_bytes(value) != raw:
        raise NightlyContractError(f"{label} bytes are not canonical")
    return value


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def _directory_identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_uid,
        status.st_gid,
    )


def _file_identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_nlink,
        status.st_uid,
        status.st_gid,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


@dataclass(frozen=True)
class CapturedRegularFile:
    data: bytes
    identity: tuple[int, ...]
    mode: str

    def record(self, relative: str) -> dict[str, object]:
        return {
            "mode": self.mode,
            "path": relative,
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "size": len(self.data),
        }


class _PhysicalParent:
    """Hold one absolute parent chain without following a directory link."""

    def __init__(self, leaf_path: Path) -> None:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise NightlyContractError(
                "physical file access requires O_NOFOLLOW and O_DIRECTORY"
            )
        self.absolute = _absolute_path(leaf_path)
        if self.absolute == Path(os.sep) or not self.absolute.name:
            raise NightlyContractError("a leaf file path is required")
        self.leaf_name = self.absolute.name
        self.descriptors: list[int] = []
        self.names: list[str] = []
        self.identities: list[tuple[int, ...]] = []
        try:
            self._open()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _directory_flags() -> int:
        return (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )

    def _open(self) -> None:
        flags = self._directory_flags()
        root_descriptor = os.open(os.sep, flags)
        self.descriptors.append(root_descriptor)
        self.names.append(os.sep)
        self.identities.append(_directory_identity(os.fstat(root_descriptor)))
        parent_descriptor = root_descriptor
        for part in self.absolute.parent.parts[1:]:
            try:
                descriptor = os.open(part, flags, dir_fd=parent_descriptor)
            except OSError as error:
                raise NightlyContractError(
                    f"cannot open physical parent {part!r} for {self.absolute}: {error}"
                ) from error
            status = os.fstat(descriptor)
            if not stat.S_ISDIR(status.st_mode):
                os.close(descriptor)
                raise NightlyContractError(
                    f"physical directory parent is required: {part!r}"
                )
            self.descriptors.append(descriptor)
            self.names.append(part)
            self.identities.append(_directory_identity(status))
            parent_descriptor = descriptor
        self.verify()

    @property
    def descriptor(self) -> int:
        if not self.descriptors:
            raise NightlyContractError("physical parent descriptor is closed")
        return self.descriptors[-1]

    def verify(self) -> None:
        for index, expected in enumerate(self.identities):
            try:
                held = os.fstat(self.descriptors[index])
            except OSError as error:
                raise NightlyContractError(
                    f"cannot inspect held parent for {self.absolute}: {error}"
                ) from error
            if (
                not stat.S_ISDIR(held.st_mode)
                or _directory_identity(held) != expected
            ):
                raise NightlyContractError(
                    f"physical parent identity changed for {self.absolute}"
                )
            if index:
                try:
                    current = os.stat(
                        self.names[index],
                        dir_fd=self.descriptors[index - 1],
                        follow_symlinks=False,
                    )
                except OSError as error:
                    raise NightlyContractError(
                        f"physical parent path changed for {self.absolute}: {error}"
                    ) from error
                if (
                    not stat.S_ISDIR(current.st_mode)
                    or _directory_identity(current) != expected
                ):
                    raise NightlyContractError(
                        f"physical parent path changed for {self.absolute}"
                    )

    def close(self) -> None:
        for descriptor in reversed(self.descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
        self.descriptors.clear()

    def __enter__(self) -> _PhysicalParent:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _capture_descriptor(
    descriptor: int,
    *,
    absolute: Path,
    max_bytes: int,
) -> CapturedRegularFile:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise NightlyContractError(f"single-link regular file is required: {absolute}")
    if before.st_size < 0 or before.st_size > max_bytes:
        raise NightlyContractError(f"file exceeds its byte bound: {absolute}")
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = before.st_size
    while remaining:
        chunk = os.read(descriptor, min(1024 * 1024, remaining))
        if not chunk:
            raise NightlyContractError(f"short read from {absolute}")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(descriptor, 1):
        raise NightlyContractError(f"file grew while being read: {absolute}")
    after = os.fstat(descriptor)
    if _file_identity(before) != _file_identity(after):
        raise NightlyContractError(f"file identity changed while being read: {absolute}")
    raw = b"".join(chunks)
    if len(raw) != after.st_size:
        raise NightlyContractError(f"file size changed while being read: {absolute}")
    return CapturedRegularFile(
        data=raw,
        identity=_file_identity(after),
        mode=f"{stat.S_IMODE(after.st_mode):04o}",
    )


def capture_regular_file(path: Path, *, max_bytes: int) -> CapturedRegularFile:
    absolute = _absolute_path(path)
    with _PhysicalParent(absolute) as parent:
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(parent.leaf_name, flags, dir_fd=parent.descriptor)
        except OSError as error:
            raise NightlyContractError(f"cannot open {absolute}: {error}") from error
        try:
            captured = _capture_descriptor(
                descriptor,
                absolute=absolute,
                max_bytes=max_bytes,
            )
            current = os.stat(
                parent.leaf_name,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
            parent.verify()
            if _file_identity(current) != captured.identity:
                raise NightlyContractError(
                    f"file path changed while being read: {absolute}"
                )
            return captured
        except OSError as error:
            raise NightlyContractError(f"cannot read {absolute}: {error}") from error
        finally:
            os.close(descriptor)


def read_regular_file(path: Path, *, max_bytes: int) -> bytes:
    return capture_regular_file(path, max_bytes=max_bytes).data


def write_exclusive_regular(
    path: Path,
    raw: bytes,
    *,
    max_bytes: int = MAX_PROVENANCE_BYTES,
) -> CapturedRegularFile:
    absolute = _absolute_path(path)
    if len(raw) > max_bytes:
        raise NightlyContractError(f"output exceeds its byte bound: {absolute}")
    with _PhysicalParent(absolute) as parent:
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            descriptor = os.open(
                parent.leaf_name,
                flags,
                0o600,
                dir_fd=parent.descriptor,
            )
        except OSError as error:
            raise NightlyContractError(f"cannot create {absolute}: {error}") from error
        created_identity: Optional[tuple[int, ...]] = None
        try:
            os.fchmod(descriptor, 0o600)
            created = os.fstat(descriptor)
            created_identity = _file_identity(created)
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise NightlyContractError(f"short write to {absolute}")
                view = view[written:]
            os.fsync(descriptor)
            captured = _capture_descriptor(
                descriptor,
                absolute=absolute,
                max_bytes=max_bytes,
            )
            current = os.stat(
                parent.leaf_name,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
            parent.verify()
            if captured.data != raw or _file_identity(current) != captured.identity:
                raise NightlyContractError(f"written output readback differs: {absolute}")
            os.fsync(parent.descriptor)
            return captured
        except BaseException:
            if created_identity is not None:
                try:
                    current = os.stat(
                        parent.leaf_name,
                        dir_fd=parent.descriptor,
                        follow_symlinks=False,
                    )
                except OSError:
                    current = None
                if current is not None and (
                    current.st_dev,
                    current.st_ino,
                ) == (
                    created_identity[0],
                    created_identity[1],
                ):
                    try:
                        os.unlink(parent.leaf_name, dir_fd=parent.descriptor)
                        os.fsync(parent.descriptor)
                    except OSError:
                        pass
            raise
        finally:
            os.close(descriptor)


def file_record(path: Path, *, relative: str, max_bytes: int) -> dict[str, object]:
    return capture_regular_file(path, max_bytes=max_bytes).record(relative)


def _job_body(workflow: str, job_id: str) -> Optional[str]:
    match = re.search(
        rf"(?ms)^  {re.escape(job_id)}:\n"
        rf"(?P<body>.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        workflow,
    )
    return match.group("body") if match else None


def _named_step_body(job: str, name: str) -> Optional[str]:
    match = re.search(
        rf"(?ms)^      - name: {re.escape(name)}\n"
        rf"(?P<body>.*?)(?=^      - name:|\Z)",
        job,
    )
    return match.group("body") if match else None


def _parsed_yaml_failures(workflow: str) -> list[str]:
    ruby = r'''require "yaml"
require "json"
source = STDIN.read

def reject_duplicate_mapping_keys(node, path = "$")
  case node
  when Psych::Nodes::Mapping
    seen = {}
    node.children.each_slice(2) do |key, value|
      raise "non-scalar mapping key at #{path}" unless key.is_a?(Psych::Nodes::Scalar)
      raise "explicit mapping tag at #{path}" unless key.tag.nil?
      raise "duplicate mapping key #{key.value.inspect} at #{path}" if seen.key?(key.value)
      seen[key.value] = true
      reject_duplicate_mapping_keys(value, "#{path}.#{key.value}")
    end
  when Psych::Nodes::Sequence
    node.children.each_with_index { |child, index| reject_duplicate_mapping_keys(child, "#{path}[#{index}]") }
  when Psych::Nodes::Stream, Psych::Nodes::Document
    node.children.each { |child| reject_duplicate_mapping_keys(child, path) }
  end
end

begin
  syntax_tree = Psych.parse_stream(source)
  raise "workflow must contain one document" unless syntax_tree.children.length == 1
  reject_duplicate_mapping_keys(syntax_tree)
  value = YAML.safe_load(source, permitted_classes: [], permitted_symbols: [], aliases: false)
  STDOUT.write(JSON.generate(value))
rescue StandardError => error
  warn error.message
  exit 2
end
'''
    try:
        completed = subprocess.run(
            ["ruby", "-ryaml", "-rjson", "-e", ruby],
            input=workflow,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [f"workflow YAML parser failed: {error}"]
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        return [f"workflow YAML is invalid{suffix}"]
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        return [f"workflow YAML parser returned invalid JSON: {error}"]
    if not isinstance(parsed, dict):
        return ["parsed workflow must be a mapping"]

    failures: list[str] = []
    normalized = json.dumps(
        parsed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    actual_sha256 = hashlib.sha256(normalized).hexdigest()
    if actual_sha256 != CANONICAL_PARSED_WORKFLOW_SHA256:
        failures.append(
            "parsed workflow semantics differ from the reviewed contract: "
            f"expected {CANONICAL_PARSED_WORKFLOW_SHA256}, got {actual_sha256}"
        )
    if tuple(parsed) != (
        "name",
        "on",
        "permissions",
        "env",
        "concurrency",
        "defaults",
        "jobs",
    ):
        failures.append("parsed workflow top-level keys must match exactly")
    trigger = parsed.get("on")
    if trigger != {"schedule": [{"cron": EXPECTED_CRON}]}:
        failures.append("parsed workflow must have one exact daily schedule")
    if parsed.get("permissions") != {"contents": "read"}:
        failures.append("parsed workflow permissions must be contents-read only")
    if parsed.get("env") != {
        "AETHERLINK_NIGHTLY_ARTIFACT_ACCEPTANCE": ARTIFACT_ACCEPTANCE_POLICY,
    }:
        failures.append(
            "parsed nightly artifact acceptance policy must require whole-run success"
        )
    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict) or tuple(jobs) != JOB_IDS:
        failures.append("parsed workflow must contain the exact producer/readback jobs")
        return failures
    producer = jobs.get(PRODUCER_JOB_ID)
    readback = jobs.get(READBACK_JOB_ID)
    if not isinstance(producer, dict) or not isinstance(readback, dict):
        failures.append("parsed nightly jobs must be mappings")
        return failures
    if tuple(producer) != (
        "name",
        "if",
        "runs-on",
        "timeout-minutes",
        "outputs",
        "steps",
    ):
        failures.append("parsed nightly producer keys must match exactly")
    if tuple(readback) != (
        "name",
        "needs",
        "if",
        "runs-on",
        "timeout-minutes",
        "steps",
    ):
        failures.append("parsed nightly readback keys must match exactly")
    expected_condition = (
        "${{ github.event_name == 'schedule' && github.ref == 'refs/heads/main' }}"
    )
    if (
        producer.get("name") != "Android API 36.1 headless lifecycle V1 then V2"
        or producer.get("if") != expected_condition
        or producer.get("runs-on") != "macos-26"
        or producer.get("timeout-minutes") != 60
    ):
        failures.append("parsed nightly producer execution contract differs")
    if producer.get("outputs") != {
        "artifact_id": "${{ steps.upload.outputs.artifact-id }}",
        "archive_name": "${{ steps.seal.outputs.archive_name }}",
        "archive_sha256": "${{ steps.seal.outputs.archive_sha256 }}",
        "remote_digest": "${{ steps.upload.outputs.artifact-digest }}",
    }:
        failures.append("parsed nightly producer outputs must match exactly")
    if (
        readback.get("name") != "Downloaded nightly artifact byte readback"
        or readback.get("needs") != PRODUCER_JOB_ID
        or readback.get("if") != expected_condition
        or readback.get("runs-on") != "ubuntu-24.04"
        or readback.get("timeout-minutes") != 10
    ):
        failures.append("parsed downloaded-artifact readback contract differs")
    for label, job, expected_names in (
        ("producer", producer, PRODUCER_STEP_NAMES),
        ("readback", readback, READBACK_STEP_NAMES),
    ):
        steps = job.get("steps")
        if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
            failures.append(f"parsed nightly {label} steps must be mappings")
        elif tuple(step.get("name") for step in steps) != expected_names:
            failures.append(f"parsed nightly {label} step names and order must match")
    return failures


def workflow_failures(
    workflow: str,
    *,
    check_canonical_bytes: bool = True,
) -> list[str]:
    failures: list[str] = []
    if check_canonical_bytes:
        actual_sha256 = hashlib.sha256(workflow.encode("utf-8")).hexdigest()
        if actual_sha256 != CANONICAL_WORKFLOW_SHA256:
            failures.append(
                "nightly workflow bytes differ from the reviewed contract: "
                f"expected {CANONICAL_WORKFLOW_SHA256}, got {actual_sha256}"
            )
    if "\r" in workflow or not workflow.endswith("\n"):
        failures.append("nightly workflow must use LF and end with LF")
    failures.extend(_parsed_yaml_failures(workflow))
    if not workflow.startswith(REQUIRED_WORKFLOW_PREFIX):
        failures.append("nightly workflow header must match the exact bounded schedule")
    for label, pattern in FORBIDDEN_PATTERNS.items():
        if re.search(pattern, workflow, flags=re.IGNORECASE):
            failures.append(f"nightly workflow contains out-of-scope {label}")
    try:
        jobs_section = workflow.split("jobs:\n", 1)[1]
    except IndexError:
        failures.append("nightly workflow is missing jobs")
        return failures
    found_jobs = tuple(re.findall(r"(?m)^  ([a-z][a-z0-9-]*):\n", jobs_section))
    if found_jobs != JOB_IDS:
        failures.append("nightly workflow must contain exact producer/readback jobs")
    for job_id, expected_names in (
        (PRODUCER_JOB_ID, PRODUCER_STEP_NAMES),
        (READBACK_JOB_ID, READBACK_STEP_NAMES),
    ):
        job = _job_body(workflow, job_id)
        if job is None:
            failures.append(f"nightly workflow is missing job {job_id!r}")
            continue
        found_steps = tuple(re.findall(r"(?m)^      - name: ([^\n]+)$", job))
        if found_steps != expected_names:
            failures.append(f"nightly job {job_id!r} steps must match exact order")
    actions = tuple(re.findall(r"(?m)^\s*uses:\s*([^\s#]+)\s*$", workflow))
    if actions != (
        "actions/checkout@v7",
        "actions/setup-java@v5",
        "gradle/actions/setup-gradle@v6",
        "actions/upload-artifact@v7",
        "actions/checkout@v7",
        "actions/download-artifact@v8",
    ):
        failures.append("nightly actions must match the exact approved sequence")
    if workflow.count("--run-contract-tests") != 1:
        failures.append("nightly workflow must run one exact contract-test manifest")
    if workflow.count("run_android_headless_emulator_product_lifecycle.py") != 1:
        failures.append("nightly workflow must run one lifecycle V1 producer")
    if workflow.count("check_android_headless_emulator_product_lifecycle.py") != 1:
        failures.append("nightly workflow must run one independent lifecycle V1 checker")
    if workflow.count("run_android_headless_emulator_product_lifecycle_v2.py") != 1:
        failures.append("nightly workflow must run one lifecycle V2 producer")
    if workflow.count("check_android_headless_emulator_product_lifecycle_v2.py") != 1:
        failures.append("nightly workflow must run one independent lifecycle V2 checker")
    producer_job = _job_body(workflow, PRODUCER_JOB_ID) or ""
    ordered_commands = tuple(
        producer_job.find(command)
        for command in (
            "run_android_headless_emulator_product_lifecycle.py",
            "check_android_headless_emulator_product_lifecycle.py",
            "run_android_headless_emulator_product_lifecycle_v2.py",
            "check_android_headless_emulator_product_lifecycle_v2.py",
        )
    )
    if any(position < 0 for position in ordered_commands) or ordered_commands != tuple(
        sorted(ordered_commands)
    ):
        failures.append("nightly workflow must run and check V1 before V2")
    if workflow.count("--seal-artifact") != 1:
        failures.append("nightly workflow must seal one exact lifecycle artifact")
    if workflow.count("--readback-artifact") != 2:
        failures.append("nightly workflow must read back local and downloaded archives")
    if workflow.count("--deep-result-readback") != 1:
        failures.append("nightly workflow must perform one deep pre-upload readback")
    if workflow.count("git archive --format=tar") != 1:
        failures.append("nightly workflow must materialize one exact Git commit archive")
    if workflow.count(":app:assembleDebug") != 1:
        failures.append("nightly workflow must perform one online dependency preparation")
    if workflow.count("--v1-result") != 1 or workflow.count("--v2-result") != 1:
        failures.append("nightly seal must receive one exact V1 and V2 result")
    if workflow.count("archive: false") != 1:
        failures.append("nightly workflow must upload one unwrapped sealed tar")
    if workflow.count(ARTIFACT_ACCEPTANCE_POLICY) != 2:
        failures.append(
            "nightly workflow must bind candidate acceptance to whole-run success"
        )
    return failures


def _flatten_suite(suite: unittest.TestSuite) -> list[unittest.TestCase]:
    flattened: list[unittest.TestCase] = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            flattened.extend(_flatten_suite(item))
        elif isinstance(item, unittest.TestCase):
            flattened.append(item)
        else:
            raise TypeError(f"unexpected unittest item: {type(item).__name__}")
    return flattened


def discover_contract_tests() -> tuple[list[unittest.TestCase], tuple[str, ...]]:
    root_text = str(ROOT)
    added = root_text not in sys.path
    if added:
        sys.path.insert(0, root_text)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames(CONTRACT_TEST_MODULES)
        tests = _flatten_suite(suite)
        return tests, tuple(test.id() for test in tests)
    finally:
        if added:
            sys.path.remove(root_text)


def _manifest_sha256(identities: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(identities) + "\n").encode("utf-8")).hexdigest()


def contract_test_selection_failures(
    identities: Optional[tuple[str, ...]] = None,
) -> list[str]:
    if identities is None:
        try:
            _, identities = discover_contract_tests()
        except Exception as error:
            return [f"cannot discover nightly contract tests: {error}"]
    failures: list[str] = []
    if type(CONTRACT_TEST_COUNT) is not int or CONTRACT_TEST_COUNT <= 0:
        failures.append("nightly contract test count must be a positive exact integer")
    if len(identities) != CONTRACT_TEST_COUNT:
        failures.append(
            f"nightly contract test manifest has {len(identities)}/{CONTRACT_TEST_COUNT} tests"
        )
    if len(set(identities)) != len(identities):
        failures.append("nightly contract test manifest contains duplicate identities")
    actual_contract_sha = _manifest_sha256(identities)
    if actual_contract_sha != CONTRACT_TEST_MANIFEST_SHA256:
        failures.append(
            "nightly contract test manifest identity changed: expected "
            f"{CONTRACT_TEST_MANIFEST_SHA256}, got {actual_contract_sha}"
        )
    lifecycle_ids = tuple(
        identity
        for identity in identities
        if identity.startswith(tuple(module + "." for module in LIFECYCLE_TEST_MODULES))
    )
    if (
        len(lifecycle_ids) != LIFECYCLE_TEST_COUNT
        or _manifest_sha256(lifecycle_ids) != LIFECYCLE_TEST_MANIFEST_SHA256
    ):
        failures.append("combined lifecycle tests must match the exact 86-test manifest")
    successor_ids = tuple(
        identity
        for identity in identities
        if identity.startswith(tuple(module + "." for module in SUCCESSOR_TEST_MODULES))
    )
    if (
        len(successor_ids) != SUCCESSOR_TEST_COUNT
        or _manifest_sha256(successor_ids) != SUCCESSOR_TEST_MANIFEST_SHA256
    ):
        failures.append("lifecycle V2 tests must match the exact 41-test manifest")
    return failures


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.started_test_ids: list[str] = []

    def startTest(self, test: unittest.TestCase) -> None:
        self.started_test_ids.append(test.id())
        super().startTest(test)


def contract_test_result_failures(
    result: unittest.TestResult,
    *,
    expected_ids: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    if type(result.testsRun) is not int or result.testsRun != len(expected_ids):
        failures.append(
            f"nightly contract runner executed {result.testsRun}/{len(expected_ids)} tests"
        )
    if tuple(getattr(result, "started_test_ids", ())) != expected_ids:
        failures.append("nightly contract runner start identities changed or reordered")
    for label, records in (
        ("skips", result.skipped),
        ("failures", result.failures),
        ("errors", result.errors),
        ("expected failures", result.expectedFailures),
        ("unexpected successes", result.unexpectedSuccesses),
    ):
        if records:
            failures.append(f"nightly contract runner recorded {len(records)} {label}")
    if not result.wasSuccessful() and not failures:
        failures.append("nightly contract runner was not successful")
    return failures


def run_contract_tests() -> list[str]:
    try:
        tests, identities = discover_contract_tests()
    except Exception as error:
        return [f"cannot discover nightly contract tests: {error}"]
    failures = contract_test_selection_failures(identities)
    if failures:
        return failures
    output = io.StringIO()
    result = unittest.TextTestRunner(
        stream=output,
        verbosity=2,
        failfast=False,
        buffer=False,
        resultclass=RecordingResult,
    ).run(unittest.TestSuite(tests))
    print(output.getvalue(), end="")
    return contract_test_result_failures(result, expected_ids=identities)


def _positive_int_text(value: Optional[str], *, label: str) -> int:
    if value is None or re.fullmatch(r"[1-9][0-9]{0,18}", value) is None:
        raise NightlyContractError(f"{label} must be one positive decimal integer")
    parsed = int(value)
    if parsed > 9_223_372_036_854_775_807:
        raise NightlyContractError(f"{label} exceeds int64")
    return parsed


def github_context(environment: Mapping[str, str]) -> dict[str, object]:
    event = environment.get("GITHUB_EVENT_NAME")
    sha = environment.get("GITHUB_SHA")
    ref = environment.get("GITHUB_REF")
    repository = environment.get("GITHUB_REPOSITORY")
    workflow_ref = environment.get("GITHUB_WORKFLOW_REF")
    if event != "schedule":
        raise NightlyContractError("GITHUB_EVENT_NAME must be schedule")
    if sha is None or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise NightlyContractError("GITHUB_SHA must be one lowercase SHA-1 identity")
    if ref != "refs/heads/main":
        raise NightlyContractError("GITHUB_REF must be refs/heads/main")
    if repository is None or re.fullmatch(r"[^/@\n]+/[^/@\n]+", repository) is None:
        raise NightlyContractError("GITHUB_REPOSITORY must be owner/name")
    expected_workflow_ref = f"{repository}/{WORKFLOW_RELATIVE}@{ref}"
    if workflow_ref != expected_workflow_ref:
        raise NightlyContractError("GITHUB_WORKFLOW_REF must bind the exact workflow and ref")
    return {
        "eventName": event,
        "ref": ref,
        "repository": repository,
        "runAttempt": _positive_int_text(
            environment.get("GITHUB_RUN_ATTEMPT"),
            label="GITHUB_RUN_ATTEMPT",
        ),
        "runId": _positive_int_text(
            environment.get("GITHUB_RUN_ID"),
            label="GITHUB_RUN_ID",
        ),
        "sha": sha,
        "workflowRef": workflow_ref,
    }


def _require_exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise NightlyContractError(f"{label} must be an exact integer >= {minimum}")
    return value


def _require_sha256(value: object, *, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise NightlyContractError(f"{label} must be one lowercase SHA-256")
    return value


def _source_record_failures(source: object) -> list[str]:
    failures: list[str] = []
    if type(source) is not dict or tuple(source) != (
        "algorithm",
        "fileCount",
        "files",
        "sha256",
    ):
        return ["lifecycle source snapshot keys must match exactly"]
    if source.get("algorithm") != "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1":
        failures.append("lifecycle source algorithm must match the exact v1 contract")
    files = source.get("files")
    count = source.get("fileCount")
    if type(files) is not list or type(count) is not int or count != len(files) or count < 1:
        failures.append("lifecycle source fileCount must exactly bind a nonempty file list")
        return failures
    paths: list[str] = []
    digest = hashlib.sha256()
    for index, record in enumerate(files):
        label = f"lifecycle source files[{index}]"
        if type(record) is not dict or tuple(record) != (
            "mode",
            "path",
            "sha256",
            "size",
        ):
            failures.append(f"{label} keys must match exactly")
            continue
        path = record.get("path")
        mode = record.get("mode")
        size = record.get("size")
        sha256 = record.get("sha256")
        if (
            type(path) is not str
            or not path
            or path.startswith("/")
            or "\\" in path
            or any(part in ("", ".", "..") for part in path.split("/"))
            or "\n" in path
            or "\0" in path
        ):
            failures.append(f"{label}.path must be one safe relative POSIX path")
            continue
        if type(mode) is not str or re.fullmatch(r"0(?:644|755)", mode) is None:
            failures.append(f"{label}.mode must be 0644 or 0755")
            continue
        if type(size) is not int or size < 0:
            failures.append(f"{label}.size must be an exact nonnegative integer")
            continue
        if type(sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            failures.append(f"{label}.sha256 must be one lowercase SHA-256")
            continue
        paths.append(path)
        digest.update(f"{path}\0{mode}\0{size}\0{sha256}\n".encode("ascii"))
    if paths != sorted(paths, key=lambda value: value.encode("ascii")):
        failures.append("lifecycle source files must use exact ASCII-byte path order")
    if len(set(paths)) != len(paths):
        failures.append("lifecycle source files must not repeat a path")
    if source.get("sha256") != digest.hexdigest():
        failures.append("lifecycle source sha256 must reconstruct from every record")
    return failures


def _git_command(
    checkout: Path,
    *arguments: str,
    text: bool = False,
) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", os.fspath(checkout), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=text,
    )


def source_git_binding_failures(
    source: object,
    *,
    git_checkout: Path,
    commit: str,
) -> list[str]:
    failures = _source_record_failures(source)
    if failures or type(source) is not dict:
        return failures
    checkout = _absolute_path(git_checkout)
    head = _git_command(checkout, "rev-parse", "--verify", "HEAD", text=True)
    if head.returncode != 0 or head.stdout.strip() != commit:
        return failures + ["Git checkout HEAD must equal GITHUB_SHA"]
    files = source["files"]
    assert isinstance(files, list)
    for record in files:
        assert isinstance(record, dict)
        path = record["path"]
        assert isinstance(path, str)
        tree = _git_command(checkout, "ls-tree", "-z", commit, "--", path)
        if tree.returncode != 0:
            failures.append(f"cannot read Git tree identity for source path: {path}")
            continue
        entries = [entry for entry in tree.stdout.split(b"\0") if entry]
        if len(entries) != 1 or b"\t" not in entries[0]:
            failures.append(f"source path must be one Git blob at GITHUB_SHA: {path}")
            continue
        metadata, encoded_path = entries[0].split(b"\t", 1)
        fields = metadata.split(b" ")
        if len(fields) != 3 or fields[1] != b"blob":
            failures.append(f"source path must resolve to one Git blob: {path}")
            continue
        try:
            tree_path = encoded_path.decode("utf-8")
        except UnicodeDecodeError:
            failures.append(f"source Git path must be UTF-8: {path}")
            continue
        if tree_path != path:
            failures.append(f"source Git path identity differs: {path}")
            continue
        expected_mode = "0755" if fields[0] == b"100755" else "0644"
        if fields[0] not in (b"100644", b"100755") or record.get("mode") != expected_mode:
            failures.append(f"source Git mode differs: {path}")
        blob = _git_command(checkout, "cat-file", "blob", f"{commit}:{path}")
        if blob.returncode != 0:
            failures.append(f"cannot read source Git blob: {path}")
            continue
        if (
            len(blob.stdout) != record.get("size")
            or hashlib.sha256(blob.stdout).hexdigest() != record.get("sha256")
        ):
            failures.append(f"source bytes differ from GITHUB_SHA: {path}")
    return failures


def _lifecycle_module(lane: str):
    if lane == "v1":
        from script import check_android_headless_emulator_product_lifecycle as lifecycle
    elif lane == "v2":
        from script import check_android_headless_emulator_product_lifecycle_v2 as lifecycle
    else:
        raise NightlyContractError(f"unknown lifecycle lane: {lane!r}")
    return lifecycle


class _CapturedLaneSnapshot:
    def __init__(self, result_path: Path, expected_paths: Sequence[str]) -> None:
        self.result_directory = _absolute_path(result_path).parent
        self.expected_paths = tuple(expected_paths) + ("result.json",)
        self.evidence = self._capture()

    def _capture(self) -> dict[str, CapturedRegularFile]:
        captured: dict[str, CapturedRegularFile] = {}
        for relative in self.expected_paths:
            limit = MAX_RESULT_BYTES if relative == "result.json" else MAX_ARCHIVE_BYTES
            captured[relative] = capture_regular_file(
                self.result_directory / relative,
                max_bytes=limit,
            )
        return captured

    def verify_unchanged(self) -> None:
        current = self._capture()
        if tuple(current) != tuple(self.evidence):
            raise NightlyContractError("lifecycle evidence path order changed")
        for relative in self.evidence:
            if current[relative] != self.evidence[relative]:
                raise NightlyContractError(
                    f"lifecycle evidence changed during binding: {relative}"
                )

    def close(self) -> None:
        return None


def _open_validated_lifecycle_snapshot(
    lane: str,
    result_path: Path,
    *,
    sdk_root: Path,
    java_home: Path,
):
    lifecycle = _lifecycle_module(lane)
    snapshot = None
    try:
        if lane == "v2":
            snapshot = lifecycle.EvidenceSnapshot(_absolute_path(result_path))
            evidence = snapshot.capture()
            result_capture = evidence["result.json"]
            result = lifecycle.load_canonical_json(
                result_capture.data,
                label=f"{lane} result.json",
            )
            failures = lifecycle.captured_result_failures(
                snapshot,
                evidence,
                result,
                root=ROOT,
                sdk_root=_absolute_path(sdk_root),
                java_home=_absolute_path(java_home),
            )
        else:
            snapshot = _CapturedLaneSnapshot(result_path, lifecycle.EVIDENCE_PATHS)
            evidence = snapshot.evidence
            result_capture = evidence["result.json"]
            result = parse_canonical_json(
                result_capture.data,
                label=f"{lane} result.json",
            )
            with tempfile.TemporaryDirectory(
                prefix="aetherlink-nightly-v1-captured-readback-"
            ) as temporary:
                captured_root = Path(temporary) / snapshot.result_directory.name
                captured_root.mkdir(mode=0o700)
                for relative, captured in evidence.items():
                    target = captured_root / relative
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    target.write_bytes(captured.data)
                    target.chmod(int(captured.mode, 8))
                failures = lifecycle.result_failures(
                    captured_root / "result.json",
                    root=ROOT,
                    sdk_root=_absolute_path(sdk_root),
                    java_home=_absolute_path(java_home),
                )
            snapshot.verify_unchanged()
    except (Exception, OSError, KeyError) as error:
        if snapshot is not None:
            snapshot.close()
        if isinstance(error, NightlyContractError):
            raise
        raise NightlyContractError(str(error)) from error
    if failures:
        snapshot.close()
        raise NightlyContractError(
            f"lifecycle {lane} result is not independently valid: "
            + "; ".join(failures)
        )
    return lifecycle, snapshot, evidence, result_capture, result


def _lane_provenance_from_capture(
    lane: str,
    *,
    lifecycle: object,
    result_directory: Path,
    result_capture: object,
    result: object,
    evidence_capture: Mapping[str, object],
    context: Mapping[str, object],
    git_checkout: Path,
) -> dict[str, object]:
    if type(result) is not dict:
        raise NightlyContractError(f"lifecycle {lane} result must be a mapping")
    run = result.get("run")
    source = result.get("source")
    evidence = result.get("evidence")
    scenarios = result.get("scenarios")
    cleanup = result.get("cleanup")
    if not all(type(value) is dict for value in (run, source, cleanup)) or type(evidence) is not list:
        raise NightlyContractError(f"lifecycle {lane} result mappings are incomplete")
    if type(scenarios) is not list:
        raise NightlyContractError(f"lifecycle {lane} scenarios must be a list")
    run_id = run.get("id")
    if type(run_id) is not str or LANE_RUN_ID_PATTERNS[lane].fullmatch(run_id) is None:
        raise NightlyContractError(f"lifecycle {lane} run id is invalid")
    if result_directory.name != run_id:
        raise NightlyContractError(f"lifecycle {lane} result directory must equal its run id")
    expected_names = [name for name, _checks in lifecycle.SCENARIO_CHECKS]
    actual_names = [item.get("name") if type(item) is dict else None for item in scenarios]
    if (
        len(scenarios) != LANE_SCENARIO_COUNTS[lane]
        or actual_names != expected_names
        or any(type(item) is not dict or item.get("status") != "passed" for item in scenarios)
    ):
        raise NightlyContractError(
            f"lifecycle {lane} must bind exact passed scenarios "
            f"{LANE_SCENARIO_COUNTS[lane]}/{LANE_SCENARIO_COUNTS[lane]}"
        )
    if result.get("contract") != lifecycle.CONTRACT or result.get("status") != "passed":
        raise NightlyContractError(f"lifecycle {lane} contract/status is invalid")
    source_count = _require_exact_int(
        source.get("fileCount"), label=f"lifecycle {lane} source fileCount", minimum=1
    )
    source_sha256 = _require_sha256(
        source.get("sha256"), label=f"lifecycle {lane} source sha256"
    )
    git_failures = source_git_binding_failures(
        source,
        git_checkout=git_checkout,
        commit=context["sha"],  # type: ignore[arg-type]
    )
    if git_failures:
        raise NightlyContractError(
            f"lifecycle {lane} source is not bound to GITHUB_SHA: "
            + "; ".join(git_failures)
        )
    if len(evidence) != LANE_EVIDENCE_FILE_COUNTS[lane]:
        raise NightlyContractError(
            f"lifecycle {lane} evidence manifest must contain exactly "
            f"{LANE_EVIDENCE_FILE_COUNTS[lane]} files"
        )
    expected_evidence: list[dict[str, object]] = []
    for record in evidence:
        if type(record) is not dict or type(record.get("path")) is not str:
            raise NightlyContractError(f"lifecycle {lane} evidence records must be mappings")
        relative = record["path"]
        try:
            expected_evidence.append(evidence_capture[relative].record(relative))  # type: ignore[attr-defined]
        except (KeyError, AttributeError) as error:
            raise NightlyContractError(
                f"captured lifecycle {lane} evidence is missing: {relative}"
            ) from error
    if evidence != expected_evidence:
        raise NightlyContractError(
            f"lifecycle {lane} evidence manifest differs from captured bytes"
        )
    if set(evidence_capture) != set(lifecycle.EVIDENCE_PATHS) | {"result.json"}:
        raise NightlyContractError(f"lifecycle {lane} captured evidence graph is not closed")
    try:
        result_raw = result_capture.data  # type: ignore[attr-defined]
        result_mode = result_capture.mode  # type: ignore[attr-defined]
    except AttributeError as error:
        raise NightlyContractError(
            f"captured lifecycle {lane} result identity is invalid"
        ) from error
    return {
        "cleanupSha256": hashlib.sha256(canonical_json_bytes(cleanup)).hexdigest(),
        "contract": lifecycle.CONTRACT,
        "evidenceFileCount": len(evidence),
        "evidenceManifestSha256": hashlib.sha256(canonical_json_bytes(evidence)).hexdigest(),
        "finishedAt": run.get("finishedAt"),
        "lane": lane,
        "result": {
            "mode": result_mode,
            "path": f"{ARCHIVE_LANE_PREFIXES[lane]}result.json",
            "sha256": hashlib.sha256(result_raw).hexdigest(),
            "size": len(result_raw),
        },
        "runId": run_id,
        "scenarioCount": len(scenarios),
        "scenarioManifestSha256": hashlib.sha256(
            canonical_json_bytes(actual_names)
        ).hexdigest(),
        "sourceFileCount": source_count,
        "sourceGitCommit": context["sha"],
        "sourceSha256": source_sha256,
        "startedAt": run.get("startedAt"),
    }


def _bundle_id(lifecycle_records: Sequence[Mapping[str, object]]) -> str:
    if tuple(record.get("lane") for record in lifecycle_records) != LANE_ORDER:
        raise NightlyContractError("nightly lifecycle order must be exactly V1 then V2")
    v1_run = lifecycle_records[0].get("runId")
    v2_run = lifecycle_records[1].get("runId")
    if type(v1_run) is not str or type(v2_run) is not str:
        raise NightlyContractError("nightly lifecycle run ids must be strings")
    v1_started = lifecycle_records[0].get("startedAt")
    v1_finished = lifecycle_records[0].get("finishedAt")
    v2_started = lifecycle_records[1].get("startedAt")
    v2_finished = lifecycle_records[1].get("finishedAt")
    if not all(type(value) is str for value in (v1_started, v1_finished, v2_started, v2_finished)):
        raise NightlyContractError("nightly lifecycle timestamps must be strings")
    if not (v1_started < v1_finished <= v2_started < v2_finished):
        raise NightlyContractError("nightly lifecycle timestamps must bind V1 before V2")
    return f"{v1_run}--{v2_run}"


def _expected_provenance_from_captures(
    captures: Mapping[str, tuple[object, object, Mapping[str, object], object, object]],
    *,
    environment: Mapping[str, str],
    git_checkout: Path,
) -> dict[str, object]:
    if tuple(captures) != LANE_ORDER:
        raise NightlyContractError("nightly captures must be ordered V1 then V2")
    context = github_context(environment)
    records = []
    for lane in LANE_ORDER:
        lifecycle, snapshot, evidence, result_capture, result = captures[lane]
        records.append(
            _lane_provenance_from_capture(
                lane,
                lifecycle=lifecycle,
                result_directory=snapshot.result_directory,  # type: ignore[attr-defined]
                result_capture=result_capture,
                result=result,
                evidence_capture=evidence,
                context=context,
                git_checkout=git_checkout,
            )
        )
    bundle_id = _bundle_id(records)
    return {
        "artifactState": ARCHIVE_PROVENANCE_STATE,
        "bundleId": bundle_id,
        "checker": file_record(
            CHECKER_PATH, relative=CHECKER_RELATIVE, max_bytes=MAX_CHECKER_BYTES
        ),
        "contract": PROVENANCE_CONTRACT,
        "github": context,
        "lifecycles": records,
        "schemaVersion": PROVENANCE_SCHEMA_VERSION,
        "status": "passed",
        "testManifest": {
            "contractCount": CONTRACT_TEST_COUNT,
            "contractSha256": CONTRACT_TEST_MANIFEST_SHA256,
            "lifecycleCount": LIFECYCLE_TEST_COUNT,
            "lifecycleSha256": LIFECYCLE_TEST_MANIFEST_SHA256,
            "successorCount": SUCCESSOR_TEST_COUNT,
            "successorSha256": SUCCESSOR_TEST_MANIFEST_SHA256,
        },
        "workflow": file_record(
            WORKFLOW_PATH, relative=WORKFLOW_RELATIVE, max_bytes=MAX_WORKFLOW_BYTES
        ),
    }


def _open_dual_captures(
    v1_result_path: Path,
    v2_result_path: Path,
    *,
    sdk_root: Path,
    java_home: Path,
) -> dict[str, tuple[object, object, Mapping[str, object], object, object]]:
    captures: dict[str, tuple[object, object, Mapping[str, object], object, object]] = {}
    try:
        for lane, path in zip(LANE_ORDER, (v1_result_path, v2_result_path)):
            captures[lane] = _open_validated_lifecycle_snapshot(
                lane, path, sdk_root=sdk_root, java_home=java_home
            )
        return captures
    except BaseException:
        for _lifecycle, snapshot, _evidence, _capture, _result in captures.values():
            snapshot.close()  # type: ignore[attr-defined]
        raise


def _close_captures(
    captures: Mapping[str, tuple[object, object, Mapping[str, object], object, object]],
) -> None:
    for _lifecycle, snapshot, _evidence, _capture, _result in captures.values():
        snapshot.close()  # type: ignore[attr-defined]


def expected_provenance_payload(
    v1_result_path: Path,
    v2_result_path: Path,
    *,
    sdk_root: Path,
    java_home: Path,
    environment: Mapping[str, str],
    git_checkout: Path = ROOT,
) -> dict[str, object]:
    captures = _open_dual_captures(
        v1_result_path, v2_result_path, sdk_root=sdk_root, java_home=java_home
    )
    try:
        payload = _expected_provenance_from_captures(
            captures, environment=environment, git_checkout=git_checkout
        )
        for _lifecycle, snapshot, _evidence, _capture, _result in captures.values():
            snapshot.verify_unchanged()  # type: ignore[attr-defined]
        return payload
    finally:
        _close_captures(captures)


def write_provenance(
    provenance_path: Path,
    v1_result_path: Path,
    v2_result_path: Path,
    *,
    sdk_root: Path,
    java_home: Path,
    environment: Mapping[str, str],
    git_checkout: Path = ROOT,
) -> None:
    payload = expected_provenance_payload(
        v1_result_path,
        v2_result_path,
        sdk_root=sdk_root,
        java_home=java_home,
        environment=environment,
        git_checkout=git_checkout,
    )
    if _absolute_path(provenance_path).name != f"{payload['bundleId']}.json":
        raise NightlyContractError("provenance filename must derive from both run ids")
    write_exclusive_regular(provenance_path, canonical_json_bytes(payload))


def provenance_failures(
    provenance_path: Path,
    v1_result_path: Path,
    v2_result_path: Path,
    *,
    sdk_root: Path,
    java_home: Path,
    environment: Mapping[str, str],
    git_checkout: Path = ROOT,
) -> list[str]:
    try:
        raw = read_regular_file(provenance_path, max_bytes=MAX_PROVENANCE_BYTES)
        actual = parse_canonical_json(raw, label="nightly provenance")
        expected = expected_provenance_payload(
            v1_result_path,
            v2_result_path,
            sdk_root=sdk_root,
            java_home=java_home,
            environment=environment,
            git_checkout=git_checkout,
        )
        if _absolute_path(provenance_path).name != f"{expected['bundleId']}.json":
            return ["provenance filename does not bind both lifecycle run ids"]
        if actual != expected:
            return ["nightly provenance bytes do not reconstruct from both inputs"]
        if read_regular_file(provenance_path, max_bytes=MAX_PROVENANCE_BYTES) != raw:
            return ["nightly provenance changed during readback"]
        return []
    except (NightlyContractError, OSError, ValueError, TypeError) as error:
        return [str(error)]


def _archive_bytes(
    lane_evidence: Mapping[str, Mapping[str, object]],
    provenance_raw: bytes,
) -> bytes:
    if tuple(lane_evidence) != LANE_ORDER:
        raise NightlyContractError("archive evidence must be ordered V1 then V2")
    members: list[tuple[str, bytes, int]] = []
    for lane in LANE_ORDER:
        for relative, captured in lane_evidence[lane].items():
            try:
                data = captured.data  # type: ignore[attr-defined]
                mode = int(captured.mode, 8)  # type: ignore[attr-defined]
            except (AttributeError, TypeError, ValueError) as error:
                raise NightlyContractError(
                    f"captured {lane} archive member identity is invalid: {relative}"
                ) from error
            members.append((ARCHIVE_LANE_PREFIXES[lane] + relative, data, mode))
    members.append((ARCHIVE_PROVENANCE_PATH, provenance_raw, 0o600))
    members.sort(key=lambda member: member[0].encode("ascii"))
    buffer = io.BytesIO()
    try:
        with tarfile.open(fileobj=buffer, mode="w:", format=tarfile.USTAR_FORMAT) as archive:
            for name, data, mode in members:
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                info.mode = mode
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    except (OSError, tarfile.TarError, UnicodeError, ValueError) as error:
        raise NightlyContractError(
            f"cannot build deterministic nightly archive: {error}"
        ) from error
    raw = buffer.getvalue()
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise NightlyContractError("nightly archive exceeds its byte bound")
    return raw


def _archive_contents(raw: bytes):
    lifecycles = {lane: _lifecycle_module(lane) for lane in LANE_ORDER}
    expected_names = tuple(
        sorted(
            (
                *(
                    ARCHIVE_LANE_PREFIXES[lane] + relative
                    for lane in LANE_ORDER
                    for relative in (*lifecycles[lane].EVIDENCE_PATHS, "result.json")
                ),
                ARCHIVE_PROVENANCE_PATH,
            ),
            key=lambda value: value.encode("ascii"),
        )
    )
    captured: dict[str, dict[str, object]] = {lane: {} for lane in LANE_ORDER}
    totals = {lane: 0 for lane in LANE_ORDER}
    provenance_raw: Optional[bytes] = None
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            members = archive.getmembers()
            names = tuple(member.name for member in members)
            if names != expected_names or len(set(names)) != len(names):
                raise NightlyContractError(
                    "nightly archive member names and order must match both lanes exactly"
                )
            for member in members:
                if (
                    not member.isfile()
                    or member.type != tarfile.REGTYPE
                    or member.mtime != 0
                    or member.uid != 0
                    or member.gid != 0
                    or member.uname != ""
                    or member.gname != ""
                    or member.linkname != ""
                    or member.pax_headers
                    or member.size < 0
                    or member.size > MAX_ARCHIVE_BYTES
                ):
                    raise NightlyContractError(
                        f"nightly archive member identity is invalid: {member.name}"
                    )
                lane = next(
                    (candidate for candidate in LANE_ORDER if member.name.startswith(ARCHIVE_LANE_PREFIXES[candidate])),
                    None,
                )
                if member.name == ARCHIVE_PROVENANCE_PATH:
                    member_limit = MAX_PROVENANCE_BYTES
                elif lane is not None and member.name.endswith("/result.json"):
                    member_limit = MAX_RESULT_BYTES
                elif lane is not None:
                    member_limit = getattr(
                        lifecycles[lane], "MAX_EVIDENCE_FILE_BYTES", 256 * 1024 * 1024
                    )
                else:
                    raise NightlyContractError(f"unexpected archive path: {member.name}")
                if member.size > member_limit:
                    raise NightlyContractError(
                        f"nightly archive member exceeds its byte bound: {member.name}"
                    )
                if lane is not None:
                    totals[lane] += member.size
                    lane_total_limit = getattr(
                        lifecycles[lane], "MAX_EVIDENCE_TOTAL_BYTES", 512 * 1024 * 1024
                    )
                    if totals[lane] > lane_total_limit:
                        raise NightlyContractError(
                            f"nightly archive {lane} members exceed their total byte bound"
                        )
                stream = archive.extractfile(member)
                if stream is None:
                    raise NightlyContractError(f"cannot read archive member: {member.name}")
                data = stream.read(member.size + 1)
                if len(data) != member.size:
                    raise NightlyContractError(f"archive member size changed: {member.name}")
                mode = f"{member.mode:04o}"
                if member.name == ARCHIVE_PROVENANCE_PATH:
                    if mode != "0600":
                        raise NightlyContractError("nightly archive provenance mode must equal 0600")
                    provenance_raw = data
                else:
                    assert lane is not None
                    relative = member.name.removeprefix(ARCHIVE_LANE_PREFIXES[lane])
                    captured[lane][relative] = CapturedRegularFile(data=data, identity=(), mode=mode)
    except (OSError, tarfile.TarError, UnicodeError, ValueError) as error:
        if isinstance(error, NightlyContractError):
            raise
        raise NightlyContractError(f"cannot read nightly archive: {error}") from error
    if provenance_raw is None:
        raise NightlyContractError("nightly archive is missing provenance")
    return lifecycles, captured, provenance_raw


def archive_failures(
    archive_path: Path,
    *,
    expected_sha256: str,
    environment: Mapping[str, str],
    git_checkout: Path,
    deep_result_readback: bool = False,
    sdk_root: Optional[Path] = None,
    java_home: Optional[Path] = None,
) -> list[str]:
    try:
        _require_sha256(expected_sha256, label="expected nightly archive sha256")
        archive_capture = capture_regular_file(
            archive_path,
            max_bytes=MAX_ARCHIVE_BYTES,
        )
        actual_sha256 = hashlib.sha256(archive_capture.data).hexdigest()
        if actual_sha256 != expected_sha256:
            return [
                "nightly archive SHA-256 differs: "
                f"expected {expected_sha256}, got {actual_sha256}"
            ]
        lifecycles, lane_evidence, provenance_raw = _archive_contents(archive_capture.data)
        context = github_context(environment)
        records = []
        results: dict[str, object] = {}
        captures: dict[str, tuple[object, object, Mapping[str, object], object, object]] = {}
        for lane in LANE_ORDER:
            evidence = lane_evidence[lane]
            result_capture = evidence["result.json"]
            result = parse_canonical_json(
                result_capture.data,  # type: ignore[attr-defined]
                label=f"archived {lane} result.json",
            )
            if type(result) is not dict or type(result.get("run")) is not dict:
                return [f"archived lifecycle {lane} result must contain one run mapping"]
            run_id = result["run"].get("id")
            if type(run_id) is not str:
                return [f"archived lifecycle {lane} run id must be a string"]
            snapshot = type(
                "ArchivedSnapshot",
                (),
                {"result_directory": Path(os.sep) / "archive" / lane / run_id},
            )()
            captures[lane] = (
                lifecycles[lane], snapshot, evidence, result_capture, result
            )
            records.append(
                _lane_provenance_from_capture(
                    lane,
                    lifecycle=lifecycles[lane],
                    result_directory=snapshot.result_directory,
                    result_capture=result_capture,
                    result=result,
                    evidence_capture=evidence,
                    context=context,
                    git_checkout=git_checkout,
                )
            )
            results[lane] = result
        bundle_id = _bundle_id(records)
        if _absolute_path(archive_path).name != f"{ARCHIVE_FILENAME_PREFIX}{bundle_id}.tar":
            return ["nightly archive filename must derive from both lifecycle run ids"]
        expected = _expected_provenance_from_captures(
            captures,
            environment=environment,
            git_checkout=git_checkout,
        )
        actual = parse_canonical_json(
            provenance_raw,
            label="archived nightly provenance",
        )
        if actual != expected:
            return ["archived provenance does not reconstruct from archived bytes"]
        if deep_result_readback:
            if sdk_root is None or java_home is None:
                return ["deep archive readback requires SDK and Java roots"]
            deep_failures: list[str] = []
            with tempfile.TemporaryDirectory(prefix="aetherlink-nightly-readback-") as temporary:
                temporary_root = Path(temporary)
                for lane in LANE_ORDER:
                    result = results[lane]
                    assert isinstance(result, dict)
                    run_id = result["run"]["id"]  # type: ignore[index]
                    lane_root = temporary_root / lane / run_id
                    lane_root.mkdir(parents=True)
                    for relative, captured in lane_evidence[lane].items():
                        target = lane_root / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(captured.data)  # type: ignore[attr-defined]
                        target.chmod(int(captured.mode, 8))  # type: ignore[attr-defined]
                    lane_failures = lifecycles[lane].result_failures(
                        lane_root / "result.json",
                        root=ROOT,
                        sdk_root=_absolute_path(sdk_root),
                        java_home=_absolute_path(java_home),
                    )
                    deep_failures.extend(
                        f"{lane}: {failure}" for failure in lane_failures
                    )
            if deep_failures:
                return [
                    "archived lifecycle results are not independently valid: "
                    + "; ".join(deep_failures)
                ]
        rebuilt = _archive_bytes(lane_evidence, provenance_raw)
        if rebuilt != archive_capture.data:
            return ["nightly archive bytes are not the exact deterministic encoding"]
        return []
    except Exception as error:
        return [str(error)]


def seal_nightly_artifact(
    archive_path: Path,
    provenance_path: Path,
    v1_result_path: Path,
    v2_result_path: Path,
    *,
    sdk_root: Path,
    java_home: Path,
    environment: Mapping[str, str],
    git_checkout: Path,
) -> str:
    captures = _open_dual_captures(
        v1_result_path,
        v2_result_path,
        sdk_root=sdk_root,
        java_home=java_home,
    )
    try:
        payload = _expected_provenance_from_captures(
            captures,
            environment=environment,
            git_checkout=git_checkout,
        )
        bundle_id = payload["bundleId"]
        if _absolute_path(provenance_path).name != f"{bundle_id}.json":
            raise NightlyContractError("provenance filename must derive from both run ids")
        if _absolute_path(archive_path).name != (
            f"{ARCHIVE_FILENAME_PREFIX}{bundle_id}.tar"
        ):
            raise NightlyContractError("archive filename must derive from both run ids")
        provenance_raw = canonical_json_bytes(payload)
        write_exclusive_regular(
            provenance_path,
            provenance_raw,
            max_bytes=MAX_PROVENANCE_BYTES,
        )
        lane_evidence = {
            lane: captures[lane][2]
            for lane in LANE_ORDER
        }
        archive_raw = _archive_bytes(lane_evidence, provenance_raw)
        write_exclusive_regular(
            archive_path,
            archive_raw,
            max_bytes=MAX_ARCHIVE_BYTES,
        )
        for _lifecycle, snapshot, _evidence, _capture, _result in captures.values():
            snapshot.verify_unchanged()  # type: ignore[attr-defined]
        archive_sha256 = hashlib.sha256(archive_raw).hexdigest()
        failures = archive_failures(
            archive_path,
            expected_sha256=archive_sha256,
            environment=environment,
            git_checkout=git_checkout,
            deep_result_readback=True,
            sdk_root=sdk_root,
            java_home=java_home,
        )
        if failures:
            raise NightlyContractError("; ".join(failures))
        for _lifecycle, snapshot, _evidence, _capture, _result in captures.values():
            snapshot.verify_unchanged()  # type: ignore[attr-defined]
        return archive_sha256
    finally:
        _close_captures(captures)


def self_test(workflow: str) -> list[str]:
    failures: list[str] = []
    mutations = (
        ("removed schedule", '  schedule:\n    - cron: "37 18 * * *"\n', ""),
        ("changed schedule", 'cron: "37 18 * * *"', 'cron: "0 0 * * 0"'),
        (
            "removed job condition",
            "    if: >-\n      ${{ github.event_name == 'schedule' &&\n"
            "      github.ref == 'refs/heads/main' }}\n",
            "",
        ),
        (
            "wrong system image",
            "system-images;android-36.1;google_apis_playstore;arm64-v8a",
            "system-images;android-36;google_apis;arm64-v8a",
        ),
        (
            "omitted exact test runner",
            "          PYTHONPATH=. python3 -B script/check_product_nightly_ci.py "
            "--run-contract-tests\n",
            "",
        ),
        (
            "omitted independent V1 checker",
            "          python3 -B "
            "script/check_android_headless_emulator_product_lifecycle.py \\\n"
            '            "$LIFECYCLE_V1_RESULT" \\\n'
            '            --sdk-root "$ANDROID_HOME" \\\n'
            '            --java-home "$JAVA_HOME"\n',
            "",
        ),
        (
            "omitted independent V2 checker",
            "          python3 -B "
            "script/check_android_headless_emulator_product_lifecycle_v2.py \\\n"
            '            "$LIFECYCLE_V2_RESULT" \\\n'
            '            --sdk-root "$ANDROID_HOME" \\\n'
            '            --java-home "$JAVA_HOME"\n',
            "",
        ),
        (
            "cross-bound V1 result",
            '--v1-result "$LIFECYCLE_V1_RESULT"',
            '--v1-result "$LIFECYCLE_V2_RESULT"',
        ),
        ("ignored failure", "          java -version\n", "          java -version || true\n"),
        ("long retention", "          retention-days: 14\n", "          retention-days: 90\n"),
        (
            "old upload action",
            "actions/upload-artifact@v7",
            "actions/upload-artifact@v6",
        ),
    )
    for label, source, replacement in mutations:
        mutated = workflow.replace(source, replacement, 1)
        if mutated == workflow:
            failures.append(f"nightly workflow self-test mutation did not apply: {label}")
        elif not workflow_failures(mutated, check_canonical_bytes=False):
            failures.append(f"nightly workflow self-test accepted mutation: {label}")

    try:
        _, identities = discover_contract_tests()
    except Exception as error:
        return failures + [f"cannot discover baseline contract tests: {error}"]
    failures.extend(contract_test_selection_failures(identities))
    for label, changed in (
        ("omission", identities[:-1]),
        ("duplication", identities + (identities[-1],)),
        ("order", tuple(reversed(identities))),
        ("replacement", identities[:-1] + ("script.Replaced.test_replaced",)),
    ):
        if not contract_test_selection_failures(changed):
            failures.append(f"nightly test self-test accepted {label}")
    baseline = unittest.TestResult()
    baseline.testsRun = len(identities)
    baseline.started_test_ids = list(identities)
    if contract_test_result_failures(baseline, expected_ids=identities):
        failures.append("nightly result self-test rejected its baseline")
    for label, count in (
        ("short", len(identities) - 1),
        ("long", len(identities) + 1),
        ("boolean", True),
    ):
        result = unittest.TestResult()
        result.testsRun = count
        result.started_test_ids = list(identities)
        if not contract_test_result_failures(result, expected_ids=identities):
            failures.append(f"nightly result self-test accepted {label} count")
    for label, attribute, record in (
        ("skip", "skipped", (None, "skip")),
        ("failure", "failures", (None, "failure")),
        ("error", "errors", (None, "error")),
        ("expected failure", "expectedFailures", (None, "expected")),
        ("unexpected success", "unexpectedSuccesses", None),
    ):
        result = unittest.TestResult()
        result.testsRun = len(identities)
        result.started_test_ids = list(identities)
        getattr(result, attribute).append(record)
        if not contract_test_result_failures(result, expected_ids=identities):
            failures.append(f"nightly result self-test accepted {label}")
    return failures


def _load_workflow() -> str:
    raw = read_regular_file(WORKFLOW_PATH, max_bytes=MAX_WORKFLOW_BYTES)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise NightlyContractError(f"nightly workflow is not UTF-8: {error}") from error


def _default_sdk_root() -> Path:
    configured = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if configured:
        return Path(configured)
    return Path.home() / "Library/Android/sdk"


def _default_java_home() -> Path:
    configured = os.environ.get("JAVA_HOME")
    if configured:
        return Path(configured)
    return Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home")


def _default_git_checkout() -> Path:
    configured = os.environ.get("GITHUB_WORKSPACE")
    return Path(configured) if configured else ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--run-contract-tests", action="store_true")
    mode.add_argument("--write-provenance", type=Path, metavar="PATH")
    mode.add_argument("--readback-provenance", type=Path, metavar="PATH")
    mode.add_argument("--seal-artifact", type=Path, metavar="PATH")
    mode.add_argument("--readback-artifact", type=Path, metavar="PATH")
    parser.add_argument("--v1-result", type=Path)
    parser.add_argument("--v2-result", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--deep-result-readback", action="store_true")
    parser.add_argument("--sdk-root", type=Path, default=_default_sdk_root())
    parser.add_argument("--java-home", type=Path, default=_default_java_home())
    parser.add_argument("--git-checkout", type=Path, default=_default_git_checkout())
    args = parser.parse_args()

    try:
        workflow = _load_workflow()
    except NightlyContractError as error:
        print(f"- {error}", file=sys.stderr)
        return 1
    failures = workflow_failures(workflow)
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    if args.self_test:
        failures = self_test(workflow)
        if failures:
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
            return 1
        print("Product nightly CI contract and self-test passed.")
        return 0
    if args.run_contract_tests:
        failures = run_contract_tests()
        if failures:
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
            return 1
        print(
            "Product nightly contract tests passed: "
            f"{CONTRACT_TEST_COUNT}/{CONTRACT_TEST_COUNT}; skipped=0; "
            "failures=0; errors=0."
        )
        return 0
    if args.seal_artifact is not None:
        if args.v1_result is None or args.v2_result is None or args.provenance is None:
            parser.error(
                "--seal-artifact requires --v1-result, --v2-result, and --provenance"
            )
        try:
            archive_sha256 = seal_nightly_artifact(
                args.seal_artifact,
                args.provenance,
                args.v1_result,
                args.v2_result,
                sdk_root=args.sdk_root,
                java_home=args.java_home,
                environment=os.environ,
                git_checkout=args.git_checkout,
            )
        except (NightlyContractError, OSError, ValueError, TypeError) as error:
            print(f"- {error}", file=sys.stderr)
            return 1
        print(archive_sha256)
        return 0
    if args.readback_artifact is not None:
        if args.expected_sha256 is None:
            parser.error("--readback-artifact requires --expected-sha256")
        failures = archive_failures(
            args.readback_artifact,
            expected_sha256=args.expected_sha256,
            environment=os.environ,
            git_checkout=args.git_checkout,
            deep_result_readback=args.deep_result_readback,
            sdk_root=args.sdk_root,
            java_home=args.java_home,
        )
        if failures:
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
            return 1
        print("Nightly sealed artifact readback passed.")
        return 0
    if args.write_provenance is not None or args.readback_provenance is not None:
        if args.v1_result is None or args.v2_result is None:
            parser.error("--v1-result and --v2-result are required for provenance modes")
        if args.write_provenance is not None:
            try:
                write_provenance(
                    args.write_provenance,
                    args.v1_result,
                    args.v2_result,
                    sdk_root=args.sdk_root,
                    java_home=args.java_home,
                    environment=os.environ,
                    git_checkout=args.git_checkout,
                )
            except (NightlyContractError, OSError, ValueError, TypeError) as error:
                print(f"- {error}", file=sys.stderr)
                return 1
            print(f"Nightly provenance written: {args.write_provenance}")
            return 0
        failures = provenance_failures(
            args.readback_provenance,
            args.v1_result,
            args.v2_result,
            sdk_root=args.sdk_root,
            java_home=args.java_home,
            environment=os.environ,
            git_checkout=args.git_checkout,
        )
        if failures:
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
            return 1
        print("Nightly lifecycle provenance readback passed.")
        return 0

    print("Product nightly CI contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
