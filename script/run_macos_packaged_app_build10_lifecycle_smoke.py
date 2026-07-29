#!/usr/bin/env python3
"""Run the frozen Build 10 packaged-macOS launch and relaunch smoke."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
import zipfile

if __package__:
    from script import run_macos_packaged_app_lifecycle_smoke as engine
else:
    import run_macos_packaged_app_lifecycle_smoke as engine


ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA_VERSION = 1
ENGINE_PATH = ROOT / "script/run_macos_packaged_app_lifecycle_smoke.py"
PRESERVED_BUILD9_IDENTITIES = (
    (
        ENGINE_PATH,
        "3d7ae7ac5b29236babb239769e7e76f6e51b2fc054accb7d53bd88509aa6ee12",
    ),
    (
        ROOT / "script/test_run_macos_packaged_app_lifecycle_smoke.py",
        "4b01ac0161969077b027d44aad9f4f838caa1c14d1f807020ef5bca98d9de138",
    ),
    (
        ROOT / "dist/lifecycle/macos-packaged-app-build-9-lifecycle-v1.json",
        "aad796ee3c768e37953f18eeea0e6642107750c3a8c398df798a46e96aabab53",
    ),
)


@dataclass(frozen=True)
class LifecycleContract:
    release_id: str
    marketing_version: str
    build_number: int
    bundle_identifier: str
    archive_sha256: str
    manifest_sha256: str
    executable_size: int
    executable_sha256: str
    macos_uuid: str


BUILD_10_CONTRACT = LifecycleContract(
    release_id="aetherlink-1.0.0+10-local-v1",
    marketing_version="1.0.0",
    build_number=10,
    bundle_identifier="dev.aetherlink.companion",
    archive_sha256=(
        "12a4fcccceac74248a0835765876bd9184c845696c83cbf3a6b1fe7613000cc0"
    ),
    manifest_sha256=(
        "fcda01d30c61be8182fc294ee76d2583b98ec78fee8b0e6c2ec2f9208ea31741"
    ),
    executable_size=18_248_464,
    executable_sha256=(
        "75f20fad8d5ce20ecdaa07bcdd526b20cb88f46b50dd1639f11f739858ad6ef4"
    ),
    macos_uuid="415765ED-429A-36D9-BC1A-BAC6DDF18B45",
)
DEFAULT_ARCHIVE_DIR = ROOT / "dist/releases" / BUILD_10_CONTRACT.release_id
DEFAULT_RESULT = (
    ROOT
    / "dist/lifecycle"
    / "macos-packaged-app-build-10-lifecycle-v1.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preserved_build9_evidence_failures() -> list[str]:
    failures: list[str] = []
    for path, expected_sha256 in PRESERVED_BUILD9_IDENTITIES:
        try:
            rendered_path = str(path.relative_to(ROOT))
        except ValueError:
            rendered_path = str(path)
        if not path.is_file():
            failures.append(
                f"missing preserved Build 9 file: {rendered_path}"
            )
            continue
        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected_sha256:
            failures.append(
                f"preserved Build 9 file drifted: {rendered_path}; "
                f"expected {expected_sha256}, found {actual_sha256}"
            )
    return failures


def verify_preserved_build9_evidence() -> None:
    failures = preserved_build9_evidence_failures()
    if failures:
        raise engine.LifecycleSmokeError("; ".join(failures))


def verify_archive_readback(archive_dir: Path) -> None:
    engine.run_checked(
        [
            sys.executable,
            "-B",
            str(engine.ARCHIVE_CHECKER),
            "--archive-dir",
            str(archive_dir),
        ],
        cwd=ROOT,
    )


def load_release_inputs(
    archive_dir: Path,
    *,
    verify_readback: bool = True,
    contract: LifecycleContract = BUILD_10_CONTRACT,
) -> engine.ReleaseInputs:
    archive_dir = archive_dir.resolve()
    if not archive_dir.is_dir():
        raise engine.LifecycleSmokeError(
            f"release archive directory is missing: {archive_dir}"
        )
    if archive_dir.name != contract.release_id:
        raise engine.LifecycleSmokeError(
            f"expected release directory {contract.release_id!r}, "
            f"found {archive_dir.name!r}"
        )

    archive_path = archive_dir / f"{contract.release_id}.zip"
    manifest_path = archive_dir / f"{contract.release_id}.manifest.json"
    checksum_path = archive_dir / f"{contract.release_id}.zip.sha256"
    for path in (archive_path, manifest_path, checksum_path):
        if not path.is_file():
            raise engine.LifecycleSmokeError(f"missing release input: {path}")

    if verify_readback:
        verify_archive_readback(archive_dir)

    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != contract.manifest_sha256:
        raise engine.LifecycleSmokeError(
            "release manifest does not match the qualified Build 10 identity"
        )
    manifest = engine.strict_json_loads(manifest_bytes, str(manifest_path))
    if not isinstance(manifest, dict):
        raise engine.LifecycleSmokeError(
            "release manifest root must be an object"
        )

    release = manifest.get("release")
    if not isinstance(release, dict):
        raise engine.LifecycleSmokeError(
            "release manifest is missing release metadata"
        )
    expected_release = {
        "buildNumber": contract.build_number,
        "marketingVersion": contract.marketing_version,
        "releaseId": contract.release_id,
    }
    actual_release = {key: release.get(key) for key in expected_release}
    if any(
        type(actual_release[key]) is not type(expected)
        or actual_release[key] != expected
        for key, expected in expected_release.items()
    ):
        raise engine.LifecycleSmokeError(
            f"unexpected release metadata: {actual_release!r}"
        )

    members = engine.manifest_member_map(manifest)
    executable_member = (
        engine.APP_MEMBER_PREFIX
        + engine.EXECUTABLE_RELATIVE_PATH.as_posix()
    )
    expected_executable = (
        contract.executable_size,
        contract.executable_sha256,
        0o755,
    )
    if members.get(executable_member) != expected_executable:
        raise engine.LifecycleSmokeError(
            "release manifest does not match the qualified Build 10 "
            "executable identity"
        )

    platforms = manifest.get("platforms")
    macos = platforms.get("macos") if isinstance(platforms, dict) else None
    uuid = macos.get("uuid") if isinstance(macos, dict) else None
    if type(uuid) is not str or uuid != contract.macos_uuid:
        raise engine.LifecycleSmokeError(
            "release manifest does not match the qualified Build 10 macOS UUID"
        )

    try:
        checksum_fields = checksum_path.read_text(encoding="ascii").split()
    except (OSError, UnicodeError) as error:
        raise engine.LifecycleSmokeError(
            f"release checksum sidecar is unreadable: {error}"
        ) from error
    if (
        len(checksum_fields) != 2
        or checksum_fields[1] != archive_path.name
        or len(checksum_fields[0]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in checksum_fields[0]
        )
    ):
        raise engine.LifecycleSmokeError(
            "release checksum sidecar is malformed"
        )
    archive_sha256 = checksum_fields[0]
    if sha256_file(archive_path) != archive_sha256:
        raise engine.LifecycleSmokeError(
            "release ZIP differs from its checksum sidecar"
        )
    if archive_sha256 != contract.archive_sha256:
        raise engine.LifecycleSmokeError(
            "release ZIP does not match the qualified Build 10 identity"
        )

    return engine.ReleaseInputs(
        archive_dir=archive_dir,
        archive_path=archive_path,
        manifest_path=manifest_path,
        checksum_path=checksum_path,
        archive_sha256=archive_sha256,
        manifest_sha256=manifest_sha256,
        manifest=manifest,
    )


def verify_packaged_app(
    app_path: Path,
    release: engine.ReleaseInputs,
    *,
    contract: LifecycleContract = BUILD_10_CONTRACT,
) -> dict[str, object]:
    info_plist = app_path / engine.INFO_PLIST_RELATIVE_PATH
    executable = app_path / engine.EXECUTABLE_RELATIVE_PATH
    if not info_plist.is_file() or not executable.is_file():
        raise engine.LifecycleSmokeError(
            "extracted app is missing Info.plist or executable"
        )
    if not os.access(executable, os.X_OK):
        raise engine.LifecycleSmokeError(
            "extracted app executable is not executable"
        )

    try:
        plist = plistlib.loads(info_plist.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise engine.LifecycleSmokeError(
            f"invalid packaged Info.plist: {error}"
        ) from error
    expected_plist = {
        "CFBundleIdentifier": contract.bundle_identifier,
        "CFBundleShortVersionString": contract.marketing_version,
        "CFBundleVersion": str(contract.build_number),
    }
    for key, expected in expected_plist.items():
        actual = plist.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise engine.LifecycleSmokeError(
                f"expected Info.plist {key}={expected!r}, found {actual!r}"
            )

    engine.run_checked(
        [
            str(engine.CODESIGN),
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app_path),
        ]
    )
    for key, expected in (
        ("CFBundleShortVersionString", contract.marketing_version),
        ("CFBundleVersion", str(contract.build_number)),
    ):
        completed = engine.run_checked(
            [
                str(engine.PLUTIL),
                "-extract",
                key,
                "raw",
                str(info_plist),
            ]
        )
        if completed.stdout.strip() != expected:
            raise engine.LifecycleSmokeError(
                f"plutil expected {key}={expected!r}, "
                f"found {completed.stdout.strip()!r}"
            )

    members = engine.manifest_member_map(release.manifest)
    executable_member = (
        engine.APP_MEMBER_PREFIX
        + engine.EXECUTABLE_RELATIVE_PATH.as_posix()
    )
    expected_executable = members.get(executable_member)
    qualified_executable = (
        contract.executable_size,
        contract.executable_sha256,
        0o755,
    )
    if expected_executable != qualified_executable:
        raise engine.LifecycleSmokeError(
            "manifest is missing the qualified Build 10 macOS executable"
        )
    actual_executable = (
        executable.stat().st_size,
        sha256_file(executable),
        stat.S_IMODE(executable.stat().st_mode),
    )
    if actual_executable != expected_executable:
        raise engine.LifecycleSmokeError(
            "extracted macOS executable differs from the release manifest"
        )

    platforms = release.manifest.get("platforms")
    macos = platforms.get("macos") if isinstance(platforms, dict) else None
    uuid = macos.get("uuid") if isinstance(macos, dict) else None
    if type(uuid) is not str or uuid != contract.macos_uuid:
        raise engine.LifecycleSmokeError(
            "release manifest has the wrong Build 10 macOS UUID"
        )
    return {
        "bundleIdentifier": contract.bundle_identifier,
        "buildNumber": contract.build_number,
        "executableSha256": contract.executable_sha256,
        "marketingVersion": contract.marketing_version,
        "uuid": contract.macos_uuid,
    }


def publish_result(path: Path, result: dict[str, object]) -> None:
    payload = engine.canonical_json_bytes(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_file() and path.read_bytes() == payload:
            return
        raise engine.LifecycleSmokeError(
            f"refusing to replace different lifecycle result bytes: {path}"
        )

    temporary_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with temporary_path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            if not path.is_file() or path.read_bytes() != payload:
                raise engine.LifecycleSmokeError(
                    "concurrent lifecycle result publication differed"
                )
    finally:
        temporary_path.unlink(missing_ok=True)


def execute(
    *,
    archive_dir: Path,
    result_path: Path,
    readiness_timeout_seconds: float,
    observation_seconds: float,
    termination_timeout_seconds: float,
) -> dict[str, object]:
    readiness_timeout_seconds = engine.validated_duration(
        readiness_timeout_seconds,
        "readiness timeout",
        0.1,
        60.0,
    )
    observation_seconds = engine.validated_duration(
        observation_seconds,
        "observation window",
        engine.MINIMUM_OBSERVATION_SECONDS,
        30.0,
    )
    termination_timeout_seconds = engine.validated_duration(
        termination_timeout_seconds,
        "termination timeout",
        0.1,
        30.0,
    )
    verify_preserved_build9_evidence()
    release = load_release_inputs(archive_dir)
    with tempfile.TemporaryDirectory(
        prefix="aetherlink-macos-build10-lifecycle-"
    ) as temporary_name:
        temporary_root = Path(temporary_name).resolve()
        extracted_staging = temporary_root / "extracted-app"
        app_path = engine.extract_packaged_app(release, extracted_staging)
        app_metadata = verify_packaged_app(app_path, release)
        executable = app_path / engine.EXECUTABLE_RELATIVE_PATH

        isolated_home = temporary_root / "home"
        isolated_temporary = temporary_root / "tmp"
        isolated_state = temporary_root / "state"
        logs = temporary_root / "logs"
        for path in (
            isolated_home,
            isolated_temporary,
            isolated_state,
            logs,
        ):
            path.mkdir(parents=True, exist_ok=False)
        identity_file = isolated_state / "runtime-identity.json"
        profile = engine.build_sandbox_profile(temporary_root)
        engine.preflight_sandbox(profile, temporary_root)
        environment = engine.isolated_environment(
            os.environ,
            home=isolated_home,
            temporary=isolated_temporary,
            identity_file=identity_file,
        )

        runs: list[engine.LifecycleRunResult] = []
        identity_digests: list[str | None] = []
        application_support_files_present_after_runs: list[bool] = []
        for ordinal in (1, 2):
            runs.append(
                engine.run_one_lifecycle(
                    ordinal=ordinal,
                    executable=executable,
                    profile=profile,
                    environment=environment,
                    working_directory=temporary_root,
                    log_directory=logs,
                    readiness_timeout_seconds=readiness_timeout_seconds,
                    observation_seconds=observation_seconds,
                    termination_timeout_seconds=termination_timeout_seconds,
                )
            )
            application_support = (
                isolated_home / "Library/Application Support/AetherLink"
            )
            missing_state_files = [
                name
                for name in engine.EXPECTED_ISOLATED_STATE_FILES
                if not (application_support / name).is_file()
            ]
            if missing_state_files:
                raise engine.LifecycleSmokeError(
                    "packaged app did not initialize isolated application "
                    f"support files {missing_state_files!r}; "
                    + engine.isolated_diagnostic_summary(temporary_root, logs)
                )
            application_support_files_present_after_runs.append(True)
            if identity_file.is_file() and identity_file.stat().st_size > 0:
                identity_digests.append(sha256_file(identity_file))
                if (
                    len(identity_digests) == 2
                    and identity_digests[0] is not None
                    and identity_digests[1] != identity_digests[0]
                ):
                    raise engine.LifecycleSmokeError(
                        "isolated runtime identity changed across relaunch"
                    )
            else:
                identity_digests.append(None)

        result = {
            "app": app_metadata,
            "isolation": {
                "afInetBindDeniedByPreflight": True,
                "nonTemporaryWriteDeniedByPreflight": True,
                "profile": (
                    "allow-default-deny-network-and-non-temp-writes-v1"
                ),
                "runtimeIdentity": (
                    "temporary-file-override-with-memory-fallback-allowed"
                ),
                "sandboxed": True,
                "temporaryCFUserHomeConfigured": True,
            },
            "release": {
                "archiveSha256": release.archive_sha256,
                "manifestSha256": release.manifest_sha256,
                "releaseId": BUILD_10_CONTRACT.release_id,
            },
            "runs": [
                {
                    "activationPolicy": run.activation_policy,
                    "exitCode": run.exit_code,
                    "finishedLaunching": run.finished_launching,
                    "minimumObservationSeconds": (
                        run.minimum_observation_seconds
                    ),
                    "observationDeadlineReached": (
                        run.observation_deadline_reached
                    ),
                    "ordinal": run.ordinal,
                    "terminationAccepted": run.termination_accepted,
                }
                for run in runs
            ],
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "status": "passed",
            "state": {
                "expectedApplicationSupportFilesPresentAfterRuns": (
                    application_support_files_present_after_runs
                ),
                "identityFilePresentAfterRuns": [
                    digest is not None for digest in identity_digests
                ],
                "identityFileUnchangedAcrossRuns": (
                    len(identity_digests) == 2
                    and identity_digests[0] is not None
                    and identity_digests[1] == identity_digests[0]
                ),
                "runtimeIdentityFileOverrideConfigured": True,
            },
        }
    publish_result(result_path, result)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=DEFAULT_RESULT,
    )
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "readiness timeout",
            0.1,
            60,
        ),
        default=15.0,
    )
    parser.add_argument(
        "--observation-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "observation window",
            engine.MINIMUM_OBSERVATION_SECONDS,
            30,
        ),
        default=engine.MINIMUM_OBSERVATION_SECONDS,
    )
    parser.add_argument(
        "--termination-timeout-seconds",
        type=lambda value: engine.bounded_float(
            value,
            "termination timeout",
            0.1,
            30,
        ),
        default=10.0,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = execute(
            archive_dir=args.archive_dir,
            result_path=args.result,
            readiness_timeout_seconds=args.readiness_timeout_seconds,
            observation_seconds=args.observation_seconds,
            termination_timeout_seconds=args.termination_timeout_seconds,
        )
    except KeyboardInterrupt:
        print(
            "Build 10 macOS packaged-app lifecycle smoke interrupted.",
            file=sys.stderr,
        )
        return 130
    except (
        engine.LifecycleSmokeError,
        OSError,
        zipfile.BadZipFile,
    ) as error:
        print(
            f"Build 10 macOS packaged-app lifecycle smoke failed: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "Build 10 macOS packaged-app lifecycle smoke passed: "
        f"{result['release']['releaseId']}; runs=2; "
        "network-bind=denied; temporary-user-home=configured."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
