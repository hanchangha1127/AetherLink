#!/usr/bin/env python3
"""Independently verify the main-branch current-unsealed lifecycle run.

The lifecycle producer is intentionally not imported. This checker holds the
current source inputs, unsealed app/dSYM generation, source receipt, and the
two CI lifecycle records through one descriptor-relative graph. It then runs
the generic build-output verifier while those descriptors remain open,
validates the closed lifecycle payloads, and reopens the complete graph.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import sys
from typing import Iterable, Mapping, Sequence

if __package__:
    from script import check_macos_current_unsealed_install_recovery_evidence as closed
    from script import check_release_artifact_archive as reader
else:
    import check_macos_current_unsealed_install_recovery_evidence as closed
    import check_release_artifact_archive as reader


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIRECTORY_RELATIVE = Path(
    ".build/aetherlink-current-unsealed-lifecycle-v1"
)
RESULT_RELATIVE = RESULT_DIRECTORY_RELATIVE / "result.json"
RECEIPT_RELATIVE = RESULT_DIRECTORY_RELATIVE / "repeatability.json"
OUTPUT_ROOT_RELATIVE = Path(reader.MACOS_UNSEALED_OUTPUT_RELATIVE_PATH)
SOURCE_RECEIPT_RELATIVE = (
    OUTPUT_ROOT_RELATIVE / reader.MACOS_UNSEALED_SOURCE_RECEIPT_NAME
)
LEDGER_RELATIVE = Path("release/version-ledger.tsv")
CHECKER_SUPPORT_RELATIVES = (
    Path("script/check_macos_current_unsealed_ci_lifecycle.py"),
    Path("script/check_macos_current_unsealed_install_recovery_evidence.py"),
)

MAXIMUM_RESULT_BYTES = 64 * 1024
MAXIMUM_RECEIPT_BYTES = 16 * 1024
MAXIMUM_SOURCE_RECEIPT_BYTES = 4 * 1024
MAXIMUM_SOURCE_FILE_BYTES = 64 * 1024 * 1024
MAXIMUM_OUTPUT_FILE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class FilePolicy:
    expected_mode: int | None
    maximum_bytes: int
    capture: bool = False

    def __post_init__(self) -> None:
        if self.expected_mode is not None and (
            type(self.expected_mode) is not int
            or self.expected_mode not in (0o600, 0o644, 0o755)
        ):
            raise ValueError("expected file mode must be supported or omitted")
        if type(self.maximum_bytes) is not int or self.maximum_bytes < 1:
            raise ValueError("maximum file bytes must be a positive exact integer")
        if type(self.capture) is not bool:
            raise ValueError("file capture flag must be an exact boolean")


def _identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_mode,
        status.st_uid,
        status.st_nlink,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _relative_parts(relative: Path) -> tuple[str, ...]:
    if (
        not isinstance(relative, Path)
        or relative.is_absolute()
        or relative in (Path(""), Path("."), Path(".."))
        or any(part in ("", ".", "..") for part in relative.parts)
        or Path(*relative.parts) != relative
    ):
        raise closed.EvidenceError(
            f"invalid repository-relative current-run path: {relative!r}"
        )
    return relative.parts


def lifecycle_result_paths(
    result_relative: Path,
    receipt_relative: Path,
) -> tuple[Path, Path]:
    result_parts = _relative_parts(result_relative)
    receipt_parts = _relative_parts(receipt_relative)
    if (
        result_relative.name != "result.json"
        or receipt_relative.name != "repeatability.json"
        or result_relative.parent != receipt_relative.parent
        or len(result_parts) < 3
        or len(receipt_parts) < 3
        or result_parts[0] != ".build"
        or receipt_parts[0] != ".build"
    ):
        raise closed.EvidenceError(
            "current-run result paths must be one canonical .build directory "
            "containing result.json and repeatability.json"
        )
    return result_relative, receipt_relative


def current_source_paths(root: Path = ROOT) -> tuple[Path, ...]:
    try:
        paths = tuple(
            Path(relative) for relative in reader.collect_current_source_paths(root)
        )
    except reader.ReleaseArchiveVerificationError as error:
        raise closed.EvidenceError(
            f"current source path discovery failed: {error}"
        ) from error
    for relative in paths:
        _relative_parts(relative)
    if (
        not paths
        or len(paths) != len(set(paths))
        or paths
        != tuple(sorted(paths, key=lambda value: value.as_posix().encode("ascii")))
    ):
        raise closed.EvidenceError("current source paths differ from their closure")
    return paths


def _output_mode(relative: Path) -> int:
    executable = OUTPUT_ROOT_RELATIVE / "AetherLink.app/Contents/MacOS/AetherLink"
    return 0o755 if relative == executable else 0o644


def current_run_file_policies(
    root: Path = ROOT,
    *,
    source_paths: Sequence[Path] | None = None,
    result_relative: Path = RESULT_RELATIVE,
    receipt_relative: Path = RECEIPT_RELATIVE,
) -> dict[Path, FilePolicy]:
    result_relative, receipt_relative = lifecycle_result_paths(
        result_relative,
        receipt_relative,
    )
    sources = current_source_paths(root) if source_paths is None else tuple(source_paths)
    for relative in sources:
        _relative_parts(relative)
    if (
        not sources
        or len(sources) != len(set(sources))
        or sources
        != tuple(sorted(sources, key=lambda value: value.as_posix().encode("ascii")))
    ):
        raise closed.EvidenceError("current source policy paths differ")

    policies: dict[Path, FilePolicy] = {}
    for relative in sources:
        policies[relative] = FilePolicy(
            expected_mode=None,
            maximum_bytes=MAXIMUM_SOURCE_FILE_BYTES,
            capture=relative == LEDGER_RELATIVE,
        )

    for relative in CHECKER_SUPPORT_RELATIVES:
        _relative_parts(relative)
        policies.setdefault(
            relative,
            FilePolicy(
                expected_mode=None,
                maximum_bytes=MAXIMUM_SOURCE_FILE_BYTES,
            ),
        )

    dynamic_rows = (
        (result_relative, 0o600, MAXIMUM_RESULT_BYTES),
        (receipt_relative, 0o600, MAXIMUM_RECEIPT_BYTES),
        (
            SOURCE_RECEIPT_RELATIVE,
            0o644,
            MAXIMUM_SOURCE_RECEIPT_BYTES,
        ),
        *(
            (
                OUTPUT_ROOT_RELATIVE / "AetherLink.app" / relative,
                _output_mode(
                    OUTPUT_ROOT_RELATIVE / "AetherLink.app" / relative
                ),
                MAXIMUM_OUTPUT_FILE_BYTES,
            )
            for relative in closed.APP_FILES
        ),
        *(
            (
                OUTPUT_ROOT_RELATIVE / "AetherLink.dSYM" / relative,
                0o644,
                MAXIMUM_OUTPUT_FILE_BYTES,
            )
            for relative in closed.DSYM_FILES
        ),
    )
    for relative, mode, maximum in dynamic_rows:
        if relative in policies:
            raise closed.EvidenceError(
                f"current-run file roles overlap: {relative}"
            )
        policies[relative] = FilePolicy(
            expected_mode=mode,
            maximum_bytes=maximum,
            capture=True,
        )
    expected_paths = set(sources) | set(CHECKER_SUPPORT_RELATIVES)
    expected_paths.update(relative for relative, _mode, _maximum in dynamic_rows)
    if (
        set(policies) != expected_paths
        or LEDGER_RELATIVE not in policies
        or len(policies) != len(expected_paths)
    ):
        raise closed.EvidenceError("current-run held file closure differs")
    return policies


def _all_parent_directories(paths: Iterable[Path]) -> set[Path]:
    directories: set[Path] = set()
    for path in paths:
        parent = path.parent
        while parent != Path("."):
            directories.add(parent)
            parent = parent.parent
    return directories


def current_run_directory_specs(
    files: Mapping[Path, object],
    *,
    result_relative: Path = RESULT_RELATIVE,
    receipt_relative: Path = RECEIPT_RELATIVE,
) -> dict[Path, closed.DirectorySpec]:
    result_relative, receipt_relative = lifecycle_result_paths(
        result_relative,
        receipt_relative,
    )
    directories = {
        relative: closed.DirectorySpec()
        for relative in _all_parent_directories(files)
    }
    directories.update(closed.OUTPUT_DIRECTORY_SPECS)
    directories[result_relative.parent] = closed.DirectorySpec(
        0o700,
        frozenset({result_relative.name, receipt_relative.name}),
    )
    return directories


class CurrentRunSnapshot(closed.RepositorySnapshot):
    """Acquire dynamic file identities from one retained physical graph."""

    def __init__(
        self,
        root: Path,
        file_policies: Mapping[Path, FilePolicy],
        directory_specs: Mapping[Path, closed.DirectorySpec],
    ) -> None:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise closed.EvidenceError(
                "held snapshot requires O_NOFOLLOW and O_DIRECTORY"
            )
        if not file_policies:
            raise closed.EvidenceError("held snapshot file policy must not be empty")
        self.root = root
        self.file_policies = dict(file_policies)
        self.file_specs: dict[Path, closed.FileSpec] = {}
        self.directory_specs = dict(directory_specs)
        self.directory_fds: dict[Path, int] = {}
        self.directory_identities: dict[Path, tuple[int, ...]] = {}
        self.directory_inventories: dict[Path, frozenset[str]] = {}
        self.file_fds: dict[Path, int] = {}
        self.file_identities: dict[Path, tuple[int, ...]] = {}
        self._closed = False
        self._open_dynamic()

    def _open_dynamic(self) -> None:
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | os.O_NOFOLLOW
            | os.O_DIRECTORY
        )
        file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
        try:
            root_fd = os.open(self.root, directory_flags)
            root_status = os.fstat(root_fd)
            root_path_status = self.root.lstat()
            if (
                not stat.S_ISDIR(root_status.st_mode)
                or stat.S_ISLNK(root_path_status.st_mode)
                or _identity(root_status) != _identity(root_path_status)
            ):
                os.close(root_fd)
                raise closed.EvidenceError(
                    "repository root must be one physical directory"
                )
            self.directory_fds[Path(".")] = root_fd
            self.directory_identities[Path(".")] = _identity(root_status)

            for relative in sorted(
                self.directory_specs,
                key=lambda value: (len(value.parts), value.as_posix()),
            ):
                parts = _relative_parts(relative)
                parent = Path(*parts[:-1]) if len(parts) > 1 else Path(".")
                if parent not in self.directory_fds:
                    raise closed.EvidenceError(
                        f"directory contract omits parent: {relative}"
                    )
                descriptor = os.open(
                    parts[-1],
                    directory_flags,
                    dir_fd=self.directory_fds[parent],
                )
                status = os.fstat(descriptor)
                spec = self.directory_specs[relative]
                if (
                    not stat.S_ISDIR(status.st_mode)
                    or status.st_uid != os.getuid()
                    or (
                        spec.mode is not None
                        and stat.S_IMODE(status.st_mode) != spec.mode
                    )
                ):
                    os.close(descriptor)
                    raise closed.EvidenceError(
                        f"directory identity differs: {relative}"
                    )
                self.directory_fds[relative] = descriptor
                self.directory_identities[relative] = _identity(status)
                inventory = frozenset(os.listdir(descriptor))
                self.directory_inventories[relative] = inventory
                if spec.entries is not None and inventory != spec.entries:
                    raise closed.EvidenceError(
                        f"directory inventory differs: {relative}"
                    )

            for relative, policy in sorted(
                self.file_policies.items(), key=lambda item: item[0].as_posix()
            ):
                parts = _relative_parts(relative)
                parent = Path(*parts[:-1]) if len(parts) > 1 else Path(".")
                if parent not in self.directory_fds:
                    raise closed.EvidenceError(
                        f"file contract omits parent: {relative}"
                    )
                descriptor = os.open(
                    parts[-1], file_flags, dir_fd=self.directory_fds[parent]
                )
                status = os.fstat(descriptor)
                mode = stat.S_IMODE(status.st_mode)
                if (
                    not stat.S_ISREG(status.st_mode)
                    or status.st_uid != os.getuid()
                    or status.st_nlink != 1
                    or mode not in (0o600, 0o644, 0o755)
                    or (
                        policy.expected_mode is not None
                        and mode != policy.expected_mode
                    )
                    or status.st_size > policy.maximum_bytes
                ):
                    os.close(descriptor)
                    raise closed.EvidenceError(
                        f"current-run file identity differs: {relative}"
                    )
                self.file_fds[relative] = descriptor
                self.file_identities[relative] = _identity(status)

            self._verify_entries()
            for relative, descriptor in self.file_fds.items():
                policy = self.file_policies[relative]
                before = os.fstat(descriptor)
                os.lseek(descriptor, 0, os.SEEK_SET)
                digest = hashlib.sha256()
                total = 0
                while True:
                    chunk = os.read(descriptor, closed.READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > policy.maximum_bytes:
                        raise closed.EvidenceError(
                            f"current-run file exceeds its byte limit: {relative}"
                        )
                    digest.update(chunk)
                after = os.fstat(descriptor)
                if (
                    _identity(before) != self.file_identities[relative]
                    or _identity(before) != _identity(after)
                    or total != after.st_size
                ):
                    raise closed.EvidenceError(
                        f"current-run file changed during acquisition: {relative}"
                    )
                self.file_specs[relative] = closed.FileSpec(
                    total,
                    digest.hexdigest(),
                    stat.S_IMODE(after.st_mode),
                    policy.capture,
                )
            if set(self.file_specs) != set(self.file_policies):
                raise closed.EvidenceError(
                    "current-run dynamic file identities are incomplete"
                )
            self._verify_entries()
        except BaseException:
            self.close()
            raise


def held_source_snapshot_summary(
    source_paths: Sequence[Path],
    file_specs: Mapping[Path, closed.FileSpec],
) -> dict[str, object]:
    paths = tuple(source_paths)
    for relative in paths:
        _relative_parts(relative)
    if (
        not paths
        or len(paths) != len(set(paths))
        or paths
        != tuple(sorted(paths, key=lambda value: value.as_posix().encode("ascii")))
    ):
        raise closed.EvidenceError("held source path closure differs")
    digest = hashlib.sha256()
    for relative in paths:
        spec = file_specs.get(relative)
        if not isinstance(spec, closed.FileSpec):
            raise closed.EvidenceError(
                f"held source file identity is absent: {relative}"
            )
        digest.update(
            relative.as_posix().encode("ascii")
            + b"\0"
            + f"{reader.normalized_mode(spec.mode):o}".encode("ascii")
            + b"\0"
            + str(spec.size).encode("ascii")
            + b"\0"
            + spec.sha256.encode("ascii")
            + b"\n"
        )
    return {
        "algorithm": closed.SOURCE_ALGORITHM,
        "fileCount": len(paths),
        "sha256": digest.hexdigest(),
    }


def expected_source_receipt(
    report: Mapping[str, object],
    *,
    source: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "build": {
            "buildNumber": report["buildNumber"],
            "configuration": "release",
            "marketingVersion": report["marketingVersion"],
            "mode": "unsealed-package-only",
        },
        "outputContract": reader.MACOS_UNSEALED_OUTPUT_CONTRACT,
        "schemaVersion": reader.MACOS_UNSEALED_SOURCE_RECEIPT_SCHEMA_VERSION,
        "source": report["source"] if source is None else source,
    }


def expected_current_result(
    *,
    report: Mapping[str, object],
    app_identity: dict[str, object],
    dsym_identity: dict[str, object],
    source_receipt_identity: dict[str, object],
    source: Mapping[str, object] | None = None,
) -> dict[str, object]:
    expected = closed.expected_result(
        app_identity=app_identity,
        dsym_identity=dsym_identity,
        receipt_identity=source_receipt_identity,
    )
    expected["app"] = {
        "architecture": report["architecture"],
        "buildNumber": report["buildNumber"],
        "bundleIdentifier": report["bundleId"],
        "marketingVersion": report["marketingVersion"],
        "minimumSystemVersion": report["minimumSystemVersion"],
        "uuid": report["uuid"],
    }
    generation = expected["generation"]
    assert isinstance(generation, dict)
    generation["app"] = app_identity
    generation["dSYM"] = dsym_identity
    generation["outerBundleSeal"] = report["outerBundleSeal"]
    generation["outputContract"] = reader.MACOS_UNSEALED_OUTPUT_CONTRACT
    generation["source"] = report["source"] if source is None else source
    generation["sourceReceipt"] = source_receipt_identity
    installation = expected["installation"]
    assert isinstance(installation, dict)
    installation["outerBundleSeal"] = report["outerBundleSeal"]
    installation["tree"] = app_identity
    return expected


def expected_current_receipt(
    result_identity: dict[str, object],
    *,
    result_file_name: str = RESULT_RELATIVE.name,
) -> dict[str, object]:
    expected = closed.expected_receipt(result_identity)
    canonical = expected["canonicalResult"]
    assert isinstance(canonical, dict)
    canonical["fileName"] = result_file_name
    return expected


def validate_current_run_payloads(
    *,
    result_payload: bytes,
    receipt_payload: bytes,
    source_receipt_payload: bytes,
    app_identity: dict[str, object],
    dsym_identity: dict[str, object],
    held_source: Mapping[str, object],
    report: Mapping[str, object],
    result_file_name: str = RESULT_RELATIVE.name,
) -> dict[str, object]:
    expected_report_keys = {
        "app",
        "architecture",
        "buildNumber",
        "bundleId",
        "dSYM",
        "locales",
        "marketingVersion",
        "minimumSystemVersion",
        "outerBundleSeal",
        "source",
        "sourceReceipt",
        "uuid",
    }
    if set(report) != expected_report_keys:
        raise closed.EvidenceError("current build-output report keys differ")
    if not closed.exact_equal(report["app"], app_identity):
        raise closed.EvidenceError("held app tree differs from build-output readback")
    if not closed.exact_equal(report["dSYM"], dsym_identity):
        raise closed.EvidenceError("held dSYM tree differs from build-output readback")
    if not closed.exact_equal(report["source"], held_source):
        raise closed.EvidenceError(
            "held source tree differs from build-output readback"
        )

    source_receipt = closed.parse_canonical_json(
        source_receipt_payload,
        label="current-run source receipt",
    )
    if not closed.exact_equal(
        source_receipt,
        expected_source_receipt(report, source=held_source),
    ):
        raise closed.EvidenceError(
            "current-run source receipt differs from build-output readback"
        )
    source_receipt_identity = {
        "sha256": hashlib.sha256(source_receipt_payload).hexdigest(),
        "size": len(source_receipt_payload),
    }
    if not closed.exact_equal(
        report["sourceReceipt"], source_receipt_identity
    ):
        raise closed.EvidenceError(
            "current-run source receipt identity differs"
        )

    result = closed.parse_canonical_json(
        result_payload,
        label="current-run lifecycle result",
    )
    expected_result = expected_current_result(
        report=report,
        app_identity=app_identity,
        dsym_identity=dsym_identity,
        source_receipt_identity=source_receipt_identity,
        source=held_source,
    )
    if not closed.exact_equal(result, expected_result):
        raise closed.EvidenceError(
            "current-run lifecycle result closed contract differs"
        )
    result_identity = {
        "sha256": hashlib.sha256(result_payload).hexdigest(),
        "size": len(result_payload),
    }
    receipt = closed.parse_canonical_json(
        receipt_payload,
        label="current-run repeatability receipt",
    )
    if not closed.exact_equal(
        receipt,
        expected_current_receipt(
            result_identity,
            result_file_name=result_file_name,
        ),
    ):
        raise closed.EvidenceError(
            "current-run repeatability receipt closed contract differs"
        )
    return result_identity


def check(
    root: Path = ROOT,
    *,
    result_relative: Path = RESULT_RELATIVE,
    receipt_relative: Path = RECEIPT_RELATIVE,
) -> dict[str, object]:
    result_relative, receipt_relative = lifecycle_result_paths(
        result_relative,
        receipt_relative,
    )
    source_paths = current_source_paths(root)
    policies = current_run_file_policies(
        root,
        source_paths=source_paths,
        result_relative=result_relative,
        receipt_relative=receipt_relative,
    )
    directories = current_run_directory_specs(
        policies,
        result_relative=result_relative,
        receipt_relative=receipt_relative,
    )
    with CurrentRunSnapshot(
        root,
        policies,
        directories,
    ) as snapshot:
        payloads = snapshot.read_all()
        files = snapshot.file_specs
        held_source = held_source_snapshot_summary(source_paths, files)
        if current_source_paths(root) != source_paths:
            raise closed.EvidenceError(
                "current source path closure changed after acquisition"
            )
        closed.validate_ledger(payloads[LEDGER_RELATIVE])
        app_identity = closed.output_tree_identity(
            payloads,
            tree="AetherLink.app",
            files=closed.APP_FILES,
            domain=b"aetherlink-macos-unsealed-app-tree-v1\0",
            specs=files,
        )
        dsym_identity = closed.output_tree_identity(
            payloads,
            tree="AetherLink.dSYM",
            files=closed.DSYM_FILES,
            domain=b"aetherlink-macos-unsealed-dsym-tree-v1\0",
            specs=files,
        )
        try:
            report = reader.verify_macos_release_build_outputs(
                root=root,
                output_root=root / OUTPUT_ROOT_RELATIVE,
            )
        except reader.ReleaseArchiveVerificationError as error:
            raise closed.EvidenceError(
                f"current build-output readback failed: {error}"
            ) from error
        if current_source_paths(root) != source_paths:
            raise closed.EvidenceError(
                "current source path closure changed during build-output readback"
            )
        result_identity = validate_current_run_payloads(
            result_payload=payloads[result_relative],
            receipt_payload=payloads[receipt_relative],
            source_receipt_payload=payloads[SOURCE_RECEIPT_RELATIVE],
            app_identity=app_identity,
            dsym_identity=dsym_identity,
            held_source=held_source,
            report=report,
            result_file_name=result_relative.name,
        )
        snapshot.verify_unchanged()
    return {
        "appSha256": app_identity["sha256"],
        "dSYMSha256": dsym_identity["sha256"],
        "resultSha256": result_identity["sha256"],
        "sourceSha256": held_source["sha256"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_macos_current_unsealed_ci_lifecycle.py",
        description=__doc__,
    )
    parser.add_argument("--result", type=Path, default=RESULT_RELATIVE)
    parser.add_argument(
        "--repeatability-result",
        type=Path,
        default=RECEIPT_RELATIVE,
    )
    try:
        arguments = parser.parse_args(
            list(sys.argv[1:] if argv is None else argv)
        )
    except SystemExit as error:
        return int(error.code)
    try:
        report = check(
            result_relative=arguments.result,
            receipt_relative=arguments.repeatability_result,
        )
    except (closed.EvidenceError, OSError, ValueError) as error:
        print(
            f"macOS current-unsealed CI lifecycle readback failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "macOS current-unsealed CI lifecycle readback passed: "
        f"result={report['resultSha256']}; app={report['appSha256']}; "
        f"dSYM={report['dSYMSha256']}; source={report['sourceSha256']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
