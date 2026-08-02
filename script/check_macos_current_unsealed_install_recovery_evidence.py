#!/usr/bin/env python3
"""Read back one closed Build 24 unsealed install/recovery generation.

This checker deliberately does not import the producer or its helper modules.
It binds their exact bytes as provenance, holds every evidence/output/source
file descriptor before reading any bytes, and independently validates the
closed result and repeatability contracts. It is a historical verifier, not a
gate for the mutable current output; freshly produced generations are checked
by ``check_macos_current_unsealed_ci_lifecycle.py`` in their producer run.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Iterable, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
MAXIMUM_CAPTURE_BYTES = 128 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024


class EvidenceError(RuntimeError):
    """Raised when the retained evidence differs from its closed contract."""


class DuplicateKeyError(ValueError):
    """Raised when strict JSON contains a duplicate object key."""


@dataclass(frozen=True)
class FileSpec:
    size: int
    sha256: str
    mode: int
    capture: bool = False

    def __post_init__(self) -> None:
        if type(self.size) is not int or self.size < 0:
            raise ValueError("file size must be a non-negative exact integer")
        if (
            type(self.sha256) is not str
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError("file SHA-256 must be lowercase hexadecimal")
        if type(self.mode) is not int or self.mode not in (0o600, 0o644, 0o755):
            raise ValueError("file mode must be one supported exact mode")
        if type(self.capture) is not bool:
            raise ValueError("file capture flag must be an exact boolean")


@dataclass(frozen=True)
class DirectorySpec:
    mode: int | None = None
    entries: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.mode is not None and (
            type(self.mode) is not int or self.mode not in (0o700, 0o755)
        ):
            raise ValueError("directory mode must be 0700, 0755, or omitted")
        if self.entries is not None and (
            type(self.entries) is not frozenset
            or any(type(entry) is not str or not entry for entry in self.entries)
        ):
            raise ValueError("directory entries must be exact non-empty strings")


RESULT_RELATIVE = Path(
    "dist/lifecycle/macos-current-source-unsealed-build-24-clean-home-"
    "install-abrupt-process-state-recovery-v1-source-closure-five.json"
)
RECEIPT_RELATIVE = Path(
    "dist/lifecycle/macos-current-source-unsealed-build-24-clean-home-"
    "install-abrupt-process-state-recovery-repeatability-v1-"
    "source-closure-five.json"
)
PREDECESSOR_EVIDENCE_ROWS = (
    (
        "macos-current-source-unsealed-build-24-clean-home-install-"
        "state-recovery-v1-source-closure-one.json",
        5_068,
        "3ee2e3685415fceed72ae4f37c0530be42b5e19d8b7ac11d8c4890bcb6394c3f",
    ),
    (
        "macos-current-source-unsealed-build-24-clean-home-install-"
        "state-recovery-repeatability-v1-source-closure-one.json",
        1_279,
        "aca7f4794418161bf090e68eeb45c55a356e63b632aa6469849bc9b0d492d654",
    ),
    (
        "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
        "process-state-recovery-v1-source-closure-two.json",
        7_431,
        "174292b479283f31da6b3507118cec95117e907ba740ae916b32306637fd0e3e",
    ),
    (
        "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
        "process-state-recovery-repeatability-v1-source-closure-two.json",
        1_571,
        "914a89d7b131f73df0bff29489738263445d23cdfa65e0dbea5ed9d5d6708838",
    ),
    (
        "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
        "process-state-recovery-v1-source-closure-three.json",
        7_617,
        "401ebb8d385758a59ce4bd6220461a9762f9fe4560d157dec5c7239dffbed953",
    ),
    (
        "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
        "process-state-recovery-repeatability-v1-source-closure-three.json",
        1_573,
        "71af474be5781b8223d22ce6391be665f8b23cfcd09405fcd35e6780cbc5b40c",
    ),
    (
        "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
        "process-state-recovery-v1-source-closure-four.json",
        7_628,
        "f360d4c6cd203ef35602192d93c4e6f764dce605a594e011b4a54b088f753848",
    ),
    (
        "macos-current-source-unsealed-build-24-clean-home-install-abrupt-"
        "process-state-recovery-repeatability-v1-source-closure-four.json",
        1_572,
        "132e1bd92a63a77e2f30090ff91568a16cd728fef5a3557d379a03ebbb11b9bd",
    ),
)
PREDECESSOR_EVIDENCE_PATHS = tuple(
    Path("dist/lifecycle") / name
    for name, _size, _digest in PREDECESSOR_EVIDENCE_ROWS
)
PREDECESSOR_EVIDENCE_SPECS = {
    Path("dist/lifecycle") / name: FileSpec(size, digest, 0o600)
    for name, size, digest in PREDECESSOR_EVIDENCE_ROWS
}
OUTPUT_ROOT_RELATIVE = Path("dist/unsealed-package-only")
LEDGER_RELATIVE = Path("release/version-ledger.tsv")

RESULT_SIZE = 7_628
RESULT_SHA256 = "9b4521b0ca765ca3d8bd8561fd9aaaafd817939d9ebf172ab61b9e2b0bc78e6b"
RECEIPT_SIZE = 1_572
RECEIPT_SHA256 = "c15620728aa7f82d127e652da69fc8c58d71f488e90ff820fbc8eb9e6476a899"
EXPECTED_UUID = "2777D1B6-E198-3A60-8607-65AA068D530E"
EXPECTED_SOURCE_FILE_COUNT = 268
EXPECTED_SOURCE_SHA256 = "99cebb6b02127c29ba71cc5190bac0543607fd6acb29d86091a21e6e25df3778"
EXPECTED_SOURCE_RECEIPT_SHA256 = (
    "15bfbd155140b2b97d8d1a4c8a44860fccc4da00fe7da17dc3ff559b0c5ef4da"
)
EXPECTED_APP_TREE_SHA256 = (
    "3f4f624ef968ed017c1f74d73ba39519039de8b1d07b66482fc608e76d369321"
)
EXPECTED_DSYM_TREE_SHA256 = (
    "e27cdaf134cca4a21bd250625a432d1bb6d18f0df5bea2b8086fb793150f80cc"
)

LIMITATIONS = (
    "same-host-per-user-temporary-home-only",
    "post-persisted-sqlite-readback-observation-sigkill-only",
    "no-in-flight-write-checkpoint-or-open-transaction-observed",
    "not-write-durability-crash-consistency-power-loss-or-kernel-crash-evidence",
    "not-os-restart-ui-force-quit-arbitrary-history-or-soak-evidence",
    "not-a-clean-machine-or-separate-account-installation",
    "not-finder-quarantine-or-gatekeeper-evidence",
    "not-tcc-keychain-or-user-consent-evidence",
    "not-developer-id-signing-or-notarization-evidence",
    "not-network-provider-device-ui-or-accessibility-evidence",
    "not-upgrade-rollback-or-n-n-minus-one-evidence",
    "not-production-canonical-g6-g7-or-v1-qualification",
)
QUALIFICATION = {
    "canonicalG6ExitClaimed": False,
    "canonicalG7ExitClaimed": False,
    "cleanMachineClaimed": False,
    "productionQualificationClaimed": False,
    "signedOrNotarizedClaimed": False,
    "v1QualificationClaimed": False,
}
RESULT_SCOPE = (
    "same-host-per-user-current-source-unsealed-clean-home-install-"
    "abrupt-process-state-recovery-v1"
)
RECEIPT_SCOPE = RESULT_SCOPE + "-repeatability-v1"
OUTPUT_CONTRACT = "macos-unsealed-app-dsym-source-bound-v1"
SOURCE_ALGORITHM = "sha256(path-nul-mode-nul-size-nul-sha256-lf)-v1"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


APP_FILES = (
    "Contents/Info.plist",
    "Contents/MacOS/AetherLink",
    "Contents/Resources/AppIcon.icns",
    "Contents/Resources/AetherLink_LocalAgentBridge.bundle/Info.plist",
    *(
        "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
        f"{locale}.lproj/Localizable.strings"
        for locale in ("en", "fr", "ja", "ko", "zh-hans")
    ),
)
DSYM_FILES = (
    "Contents/Info.plist",
    "Contents/Resources/DWARF/AetherLink",
    "Contents/Resources/Relocations/aarch64/AetherLink.yml",
)


def _output_path(tree: str, relative: str) -> Path:
    return OUTPUT_ROOT_RELATIVE / tree / PurePosixPath(relative)


# Stable resource pins are filled now. Link output, receipt, evidence, and
# execution-source pins are replaced after the final rebuild.
OUTPUT_FILE_SPECS: dict[Path, FileSpec] = {
    _output_path("AetherLink.app", "Contents/Info.plist"): FileSpec(
        977,
        "0148a8267544e94721414e99ef050e7260f07f215ec18ae28b2c770a374c2276",
        0o644,
        True,
    ),
    _output_path("AetherLink.app", "Contents/MacOS/AetherLink"): FileSpec(
        18_889_576,
        "8141752c3e4778fb8f316d940ddc3e160ec5bc2cad53ec7575dea89f6b4fdf0c",
        0o755,
        True,
    ),
    _output_path("AetherLink.app", "Contents/Resources/AppIcon.icns"): FileSpec(
        2_244_614,
        "4c8b549805c2d451a15be40fd0a1f71b09c9eb5dccb769e96b7e5be593b21419",
        0o644,
        True,
    ),
    _output_path(
        "AetherLink.app",
        "Contents/Resources/AetherLink_LocalAgentBridge.bundle/Info.plist",
    ): FileSpec(
        252,
        "80a1c5d437d69170a04c679917173d19fe011976a81ee9577192bd5781232ad6",
        0o644,
        True,
    ),
    **{
        _output_path(
            "AetherLink.app",
            "Contents/Resources/AetherLink_LocalAgentBridge.bundle/"
            f"{locale}.lproj/Localizable.strings",
        ): FileSpec(size, digest, 0o644, True)
        for locale, size, digest in (
            (
                "en",
                56_278,
                "741652ed97b63cfc7cd1b33a0d1ee6ed0105030be3dc7b88e538aaf8c620b1c3",
            ),
            (
                "fr",
                64_685,
                "aaaac1499d022eccd10d9c4e577e41a38eeb4c48f6426b34acd4e7df44d4b2f5",
            ),
            (
                "ja",
                70_527,
                "d84a391666372517ac6d355c69bde0258c6b42a3500a482caba7b56abc2014d5",
            ),
            (
                "ko",
                62_368,
                "5b2db6812ec5fedbaf0fa7659987ecb318c7f120a04cfc47d1016af4e1633d80",
            ),
            (
                "zh-hans",
                54_884,
                "48e5c6d6eedb8f2c99c7095e83d8f1f1e6f8f1e9f59a90c1f4be365319c6932a",
            ),
        )
    },
    _output_path("AetherLink.dSYM", "Contents/Info.plist"): FileSpec(
        639,
        "666492b65ac3ba85899612ad91735b2518336b503e408466bd2cd99ca26d8759",
        0o644,
        True,
    ),
    _output_path(
        "AetherLink.dSYM", "Contents/Resources/DWARF/AetherLink"
    ): FileSpec(
        32_399_425,
        "e96691969c287dd90a82ce3863d3e4e74c291ccce5e065364c34fad98338657f",
        0o644,
        True,
    ),
    _output_path(
        "AetherLink.dSYM",
        "Contents/Resources/Relocations/aarch64/AetherLink.yml",
    ): FileSpec(
        5_883_763,
        "0ff3cced68c76ebb40b6aeeb54b547b570b565e0df0ddc157e84dcced85a4191",
        0o644,
        True,
    ),
    OUTPUT_ROOT_RELATIVE / "source-receipt.json": FileSpec(
        355,
        "15bfbd155140b2b97d8d1a4c8a44860fccc4da00fe7da17dc3ff559b0c5ef4da",
        0o644,
        True,
    ),
}

EXECUTION_SOURCE_CLOSURE = (
    Path("script/check_release_artifact_archive.py"),
    Path("script/check_release_compliance.py"),
    Path("script/check_release_version_ledger.py"),
    Path("script/run_macos_clean_home_installed_app_smoke.py"),
    Path("script/run_macos_clean_home_installed_state_recovery_smoke.py"),
    Path("script/run_macos_current_unsealed_install_recovery_smoke.py"),
    Path("script/run_macos_isolated_uninstall_reinstall_smoke.py"),
    Path("script/run_macos_isolated_upgrade_smoke.py"),
    Path("script/run_macos_packaged_app_lifecycle_smoke.py"),
    Path("script/run_macos_packaged_app_state_recovery_smoke.py"),
    Path("script/test_run_macos_current_unsealed_install_recovery_smoke.py"),
)
EXECUTION_SOURCE_SPECS: dict[Path, FileSpec] = {
    Path(path): FileSpec(size, digest, mode)
    for path, size, digest, mode in (
        (
            "script/check_release_artifact_archive.py",
            255_305,
            "db5ba718e2623e16b2a235bb08f336ae03a22fbc8d86ba950c79ce45b9f7b850",
            0o755,
        ),
        (
            "script/check_release_compliance.py",
            56_756,
            "2738b8e1be0eee652245a3335c50f81dd45af42d5ee0b5d860a19fb3d05e813a",
            0o644,
        ),
        (
            "script/check_release_version_ledger.py",
            13_996,
            "b869bb300161937b66ae775d6e742decf6d208db097408d96ffef3d34a4f78f2",
            0o644,
        ),
        (
            "script/run_macos_clean_home_installed_app_smoke.py",
            35_114,
            "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29",
            0o644,
        ),
        (
            "script/run_macos_clean_home_installed_state_recovery_smoke.py",
            26_367,
            "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a",
            0o644,
        ),
        (
            "script/run_macos_current_unsealed_install_recovery_smoke.py",
            96_711,
            "24b8e328d6974d55a8b33034eee7667b11180e4d609234faa09411ec42ae4890",
            0o644,
        ),
        (
            "script/run_macos_isolated_uninstall_reinstall_smoke.py",
            18_890,
            "36bb3771aedc55c4c80c32a100e4feec83ee402a821dce168730543ebfd07afa",
            0o644,
        ),
        (
            "script/run_macos_isolated_upgrade_smoke.py",
            46_668,
            "abfd7bf5b0ef5154a4f001e1baafc134567a26e930714dffb0f057bcdb9fb095",
            0o644,
        ),
        (
            "script/run_macos_packaged_app_lifecycle_smoke.py",
            39_857,
            "3d7ae7ac5b29236babb239769e7e76f6e51b2fc054accb7d53bd88509aa6ee12",
            0o644,
        ),
        (
            "script/run_macos_packaged_app_state_recovery_smoke.py",
            26_782,
            "4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca",
            0o644,
        ),
        (
            "script/test_run_macos_current_unsealed_install_recovery_smoke.py",
            47_896,
            "7b75e9523b78ac5d29d308bd60c3217eaef97e8e115828204866e3a8eb2792a0",
            0o644,
        ),
    )
}

LEDGER_SPEC = FileSpec(
    238,
    "dce3c8615a44c11c7b1cdb505bed1d80d6ea7bdb082c9b714bc9c2ff930d19e0",
    0o644,
    True,
)


def all_file_specs() -> dict[Path, FileSpec]:
    if (
        len(PREDECESSOR_EVIDENCE_PATHS) != 8
        or len(set(PREDECESSOR_EVIDENCE_PATHS)) != 8
        or set(PREDECESSOR_EVIDENCE_PATHS)
        != set(PREDECESSOR_EVIDENCE_SPECS)
    ):
        raise EvidenceError("predecessor evidence closure differs from its pins")
    specs = {
        RESULT_RELATIVE: FileSpec(RESULT_SIZE, RESULT_SHA256, 0o600, True),
        RECEIPT_RELATIVE: FileSpec(RECEIPT_SIZE, RECEIPT_SHA256, 0o600, True),
        **PREDECESSOR_EVIDENCE_SPECS,
        LEDGER_RELATIVE: LEDGER_SPEC,
        **EXECUTION_SOURCE_SPECS,
        **OUTPUT_FILE_SPECS,
    }
    if len(specs) != (
        3
        + len(PREDECESSOR_EVIDENCE_SPECS)
        + len(EXECUTION_SOURCE_SPECS)
        + len(OUTPUT_FILE_SPECS)
    ):
        raise EvidenceError("pinned file paths must be unique")
    return specs


OUTPUT_DIRECTORY_SPECS: dict[Path, DirectorySpec] = {
    OUTPUT_ROOT_RELATIVE: DirectorySpec(
        0o700, frozenset({"AetherLink.app", "AetherLink.dSYM", "source-receipt.json"})
    ),
    OUTPUT_ROOT_RELATIVE / "AetherLink.app": DirectorySpec(
        0o755, frozenset({"Contents"})
    ),
    OUTPUT_ROOT_RELATIVE / "AetherLink.app/Contents": DirectorySpec(
        0o755, frozenset({"Info.plist", "MacOS", "Resources"})
    ),
    OUTPUT_ROOT_RELATIVE / "AetherLink.app/Contents/MacOS": DirectorySpec(
        0o755, frozenset({"AetherLink"})
    ),
    OUTPUT_ROOT_RELATIVE / "AetherLink.app/Contents/Resources": DirectorySpec(
        0o755, frozenset({"AetherLink_LocalAgentBridge.bundle", "AppIcon.icns"})
    ),
    OUTPUT_ROOT_RELATIVE
    / "AetherLink.app/Contents/Resources/AetherLink_LocalAgentBridge.bundle": DirectorySpec(
        0o755,
        frozenset(
            {"Info.plist", "en.lproj", "fr.lproj", "ja.lproj", "ko.lproj", "zh-hans.lproj"}
        ),
    ),
    **{
        OUTPUT_ROOT_RELATIVE
        / "AetherLink.app/Contents/Resources/AetherLink_LocalAgentBridge.bundle"
        / f"{locale}.lproj": DirectorySpec(
            0o755, frozenset({"Localizable.strings"})
        )
        for locale in ("en", "fr", "ja", "ko", "zh-hans")
    },
    OUTPUT_ROOT_RELATIVE / "AetherLink.dSYM": DirectorySpec(
        0o755, frozenset({"Contents"})
    ),
    OUTPUT_ROOT_RELATIVE / "AetherLink.dSYM/Contents": DirectorySpec(
        0o755, frozenset({"Info.plist", "Resources"})
    ),
    OUTPUT_ROOT_RELATIVE / "AetherLink.dSYM/Contents/Resources": DirectorySpec(
        0o755, frozenset({"DWARF", "Relocations"})
    ),
    OUTPUT_ROOT_RELATIVE
    / "AetherLink.dSYM/Contents/Resources/DWARF": DirectorySpec(
        0o755, frozenset({"AetherLink"})
    ),
    OUTPUT_ROOT_RELATIVE
    / "AetherLink.dSYM/Contents/Resources/Relocations": DirectorySpec(
        0o755, frozenset({"aarch64"})
    ),
    OUTPUT_ROOT_RELATIVE
    / "AetherLink.dSYM/Contents/Resources/Relocations/aarch64": DirectorySpec(
        0o755, frozenset({"AetherLink.yml"})
    ),
}


def _all_parent_directories(paths: Iterable[Path]) -> set[Path]:
    directories: set[Path] = set()
    for path in paths:
        parent = path.parent
        while parent != Path("."):
            directories.add(parent)
            parent = parent.parent
    return directories


def all_directory_specs(
    file_specs: Mapping[Path, FileSpec] | None = None,
) -> dict[Path, DirectorySpec]:
    files = all_file_specs() if file_specs is None else file_specs
    directories = {
        relative: DirectorySpec()
        for relative in _all_parent_directories(files)
    }
    directories.update(OUTPUT_DIRECTORY_SPECS)
    return directories


def _normalized_relative(path: Path) -> tuple[str, ...]:
    if (
        not isinstance(path, Path)
        or path.is_absolute()
        or path in (Path(""), Path("."), Path(".."))
        or any(part in ("", ".", "..") for part in path.parts)
        or Path(*path.parts) != path
    ):
        raise EvidenceError(f"invalid repository-relative path: {path!r}")
    return path.parts


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


class RepositorySnapshot:
    """Hold one descriptor-relative physical graph for a complete readback."""

    def __init__(
        self,
        root: Path,
        file_specs: Mapping[Path, FileSpec],
        directory_specs: Mapping[Path, DirectorySpec],
    ) -> None:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise EvidenceError("held snapshot requires O_NOFOLLOW and O_DIRECTORY")
        if not file_specs:
            raise EvidenceError("held snapshot file contract must not be empty")
        self.root = root
        self.file_specs = dict(file_specs)
        self.directory_specs = dict(directory_specs)
        self.directory_fds: dict[Path, int] = {}
        self.directory_identities: dict[Path, tuple[int, ...]] = {}
        self.directory_inventories: dict[Path, frozenset[str]] = {}
        self.file_fds: dict[Path, int] = {}
        self.file_identities: dict[Path, tuple[int, ...]] = {}
        self._closed = False
        self._open_all()

    def _open_all(self) -> None:
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
                raise EvidenceError("repository root must be one physical directory")
            self.directory_fds[Path(".")] = root_fd
            self.directory_identities[Path(".")] = _identity(root_status)

            for relative in sorted(
                self.directory_specs,
                key=lambda value: (len(value.parts), value.as_posix()),
            ):
                parts = _normalized_relative(relative)
                parent = Path(*parts[:-1]) if len(parts) > 1 else Path(".")
                if parent not in self.directory_fds:
                    raise EvidenceError(f"directory contract omits parent: {relative}")
                descriptor = os.open(
                    parts[-1], directory_flags, dir_fd=self.directory_fds[parent]
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
                    raise EvidenceError(f"directory identity differs: {relative}")
                self.directory_fds[relative] = descriptor
                self.directory_identities[relative] = _identity(status)
                inventory = frozenset(os.listdir(descriptor))
                self.directory_inventories[relative] = inventory
                if spec.entries is not None and inventory != spec.entries:
                    raise EvidenceError(f"directory inventory differs: {relative}")

            for relative, spec in sorted(
                self.file_specs.items(), key=lambda item: item[0].as_posix()
            ):
                parts = _normalized_relative(relative)
                parent = Path(*parts[:-1]) if len(parts) > 1 else Path(".")
                if parent not in self.directory_fds:
                    raise EvidenceError(f"file contract omits parent: {relative}")
                descriptor = os.open(
                    parts[-1], file_flags, dir_fd=self.directory_fds[parent]
                )
                status = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(status.st_mode)
                    or status.st_uid != os.getuid()
                    or status.st_nlink != 1
                    or stat.S_IMODE(status.st_mode) != spec.mode
                    or status.st_size != spec.size
                ):
                    os.close(descriptor)
                    raise EvidenceError(f"file identity differs: {relative}")
                self.file_fds[relative] = descriptor
                self.file_identities[relative] = _identity(status)
            self._verify_entries()
        except BaseException:
            self.close()
            raise

    def _verify_entries(self) -> None:
        for relative, expected in self.directory_identities.items():
            if relative == Path("."):
                current = self.root.lstat()
            else:
                parent = relative.parent if relative.parent != Path(".") else Path(".")
                current = os.stat(
                    relative.name,
                    dir_fd=self.directory_fds[parent],
                    follow_symlinks=False,
                )
            if (
                not stat.S_ISDIR(current.st_mode)
                or _identity(current) != expected
                or _identity(os.fstat(self.directory_fds[relative])) != expected
            ):
                raise EvidenceError(f"directory graph changed: {relative}")
            inventory = frozenset(os.listdir(self.directory_fds[relative]))
            if inventory != self.directory_inventories.get(relative, inventory):
                raise EvidenceError(f"directory inventory changed: {relative}")
            spec = self.directory_specs.get(relative)
            if spec is not None and spec.entries is not None and inventory != spec.entries:
                raise EvidenceError(f"directory inventory differs: {relative}")

        for relative, expected in self.file_identities.items():
            parent = relative.parent if relative.parent != Path(".") else Path(".")
            current = os.stat(
                relative.name,
                dir_fd=self.directory_fds[parent],
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or _identity(current) != expected
                or _identity(os.fstat(self.file_fds[relative])) != expected
            ):
                raise EvidenceError(f"file graph changed: {relative}")

    def read_all(self) -> dict[Path, bytes]:
        captured: dict[Path, bytes] = {}
        capture_total = 0
        for relative, descriptor in self.file_fds.items():
            spec = self.file_specs[relative]
            before = os.fstat(descriptor)
            if _identity(before) != self.file_identities[relative]:
                raise EvidenceError(f"file changed before readback: {relative}")
            os.lseek(descriptor, 0, os.SEEK_SET)
            digest = hashlib.sha256()
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > spec.size:
                    raise EvidenceError(f"file grew during readback: {relative}")
                digest.update(chunk)
                if spec.capture:
                    chunks.append(chunk)
            after = os.fstat(descriptor)
            if (
                _identity(before) != _identity(after)
                or total != spec.size
                or digest.hexdigest() != spec.sha256
            ):
                raise EvidenceError(f"file bytes changed: {relative}")
            if spec.capture:
                capture_total += total
                if capture_total > MAXIMUM_CAPTURE_BYTES:
                    raise EvidenceError("captured evidence exceeds the total byte limit")
                captured[relative] = b"".join(chunks)
        self._verify_entries()
        return captured

    def verify_unchanged(self) -> None:
        self._verify_entries()
        current = RepositorySnapshot(
            self.root, self.file_specs, self.directory_specs
        )
        try:
            if (
                current.directory_identities != self.directory_identities
                or current.directory_inventories != self.directory_inventories
                or current.file_identities != self.file_identities
            ):
                raise EvidenceError("repository graph changed during readback")
        finally:
            current.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for descriptor in tuple(self.file_fds.values()):
            try:
                os.close(descriptor)
            except OSError:
                pass
        self.file_fds.clear()
        for relative in sorted(
            self.directory_fds,
            key=lambda value: len(value.parts),
            reverse=True,
        ):
            try:
                os.close(self.directory_fds[relative])
            except OSError:
                pass
        self.directory_fds.clear()

    def __enter__(self) -> RepositorySnapshot:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


@contextmanager
def pinned_payloads(
    file_specs: Mapping[Path, FileSpec] | None = None,
    directory_specs: Mapping[Path, DirectorySpec] | None = None,
    *,
    root: Path = ROOT,
) -> Iterator[dict[Path, bytes]]:
    files = all_file_specs() if file_specs is None else dict(file_specs)
    directories = (
        all_directory_specs(files)
        if directory_specs is None
        else dict(directory_specs)
    )
    with RepositorySnapshot(root, files, directories) as snapshot:
        payloads = snapshot.read_all()
        yield payloads
        snapshot.verify_unchanged()


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def reject_nonfinite(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise EvidenceError(f"value cannot be canonical JSON: {error}") from error


def parse_canonical_json(payload: bytes, *, label: str) -> dict[str, object]:
    if type(payload) is not bytes:
        raise EvidenceError(f"{label} must be exact bytes")
    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as error:
        raise EvidenceError(f"{label} is not strict JSON: {error}") from error
    if type(value) is not dict or canonical_json_bytes(value) != payload:
        raise EvidenceError(f"{label} is not canonical object JSON")
    return value


def exact_equal(first: object, second: object) -> bool:
    if type(first) is not type(second):
        return False
    if type(first) is dict:
        return set(first) == set(second) and all(
            exact_equal(first[key], second[key]) for key in first
        )
    if type(first) is list:
        return len(first) == len(second) and all(
            exact_equal(left, right) for left, right in zip(first, second)
        )
    return first == second


def logical_member_digest(members: Mapping[str, bytes], domain: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(domain)
    digest.update(len(members).to_bytes(8, "big"))
    for name, payload in sorted(
        members.items(), key=lambda item: item[0].encode("ascii")
    ):
        name_bytes = name.encode("ascii")
        digest.update(len(name_bytes).to_bytes(8, "big"))
        digest.update(name_bytes)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def output_tree_identity(
    payloads: Mapping[Path, bytes],
    *,
    tree: str,
    files: Sequence[str],
    domain: bytes,
    specs: Mapping[Path, FileSpec] | None = None,
) -> dict[str, object]:
    pinned_specs = OUTPUT_FILE_SPECS if specs is None else specs
    members: dict[str, bytes] = {}
    total = 0
    for relative in files:
        path = _output_path(tree, relative)
        if path not in payloads or path not in pinned_specs:
            raise EvidenceError(f"output tree file was not captured: {path}")
        data = payloads[path]
        mode = pinned_specs[path].mode
        members[relative] = f"{mode:04o}\0".encode("ascii") + data
        total += len(data)
    return {
        "fileCount": len(files),
        "sha256": logical_member_digest(members, domain),
        "size": total,
    }


def expected_source_receipt() -> dict[str, object]:
    return {
        "build": {
            "buildNumber": 24,
            "configuration": "release",
            "marketingVersion": "1.0.0",
            "mode": "unsealed-package-only",
        },
        "outputContract": OUTPUT_CONTRACT,
        "schemaVersion": 1,
        "source": {
            "algorithm": SOURCE_ALGORITHM,
            "fileCount": EXPECTED_SOURCE_FILE_COUNT,
            "sha256": EXPECTED_SOURCE_SHA256,
        },
    }


def expected_result(
    *,
    app_identity: dict[str, object],
    dsym_identity: dict[str, object],
    receipt_identity: dict[str, object],
) -> dict[str, object]:
    generation = {
        "app": app_identity,
        "currentSourceBound": True,
        "dSYM": dsym_identity,
        "independentReadbackStableAcrossExercise": True,
        "liveOutputMatchesPrivateSnapshotBeforeAndAfterExercise": True,
        "outerBundleSeal": "absent",
        "outputContract": OUTPUT_CONTRACT,
        "outputRelativePath": OUTPUT_ROOT_RELATIVE.as_posix(),
        "source": expected_source_receipt()["source"],
        "sourceReceipt": receipt_identity,
    }
    canary = {
        "eventID": "packaged-state-recovery-canary-event-v1",
        "eventJsonSha256": "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef",
        "eventJsonSize": 344,
        "legacyJsonlSha256": "0e51fc924836465c4c0921eb3b3709b387f89787aabf2e100c7cff338f0aea2e",
        "legacyJsonlSize": 345,
        "model": "qa:packaged-state-recovery-canary-v1",
        "requestID": "packaged-state-recovery-canary-request-v1",
        "sessionID": "packaged-state-recovery-canary-session-v1",
    }
    observation = {
        "migration": {
            "mode": "migration-read-v1",
            "sha256": "558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9",
            "size": 70,
            "status": "passed",
        },
        "sqliteReadback": {
            "mode": "sqlite-readback-v1",
            "sha256": "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07",
            "size": 71,
            "status": "passed",
        },
    }
    sqlite = {
        "eventJsonSha256": canary["eventJsonSha256"],
        "eventJsonSize": 344,
        "integrityCheck": "ok",
        "totalEventCount": 1,
    }
    graceful_run = {
        "activationPolicy": 0,
        "appKitBundleIdentifierPolicy": (
            "validated-generation-bundle-id-and-direct-owned-executable-path-v1"
        ),
        "appKitExecutablePathMatched": True,
        "exitCode": 0,
        "finishedLaunching": True,
        "minimumObservationSeconds": 5.0,
        "observationDeadlineReached": True,
        "ownedChildProcessCaptured": True,
        "terminationAccepted": True,
    }
    abrupt_run = {
        "activationPolicy": 0,
        "appKitBundleIdentifierPolicy": (
            "validated-generation-bundle-id-and-direct-owned-executable-path-v1"
        ),
        "appKitExecutablePathMatched": True,
        "appKitProcessAbsentAfterReap": True,
        "capturedLogsRevalidatedAfterReap": True,
        "exactExecutableIdentityMatchedImmediatelyBeforeSignal": True,
        "exitCode": -9,
        "finishedLaunching": True,
        "installedExecutableDescriptorHeldAcrossSignal": True,
        "launchMethod": "direct-installed-executable-owned-child",
        "minimumObservationSeconds": 5.0,
        "observationDeadlineReached": True,
        "ordinal": 2,
        "ownedChildProcessCaptured": True,
        "pathIdentityStableAcrossSignal": True,
        "persistenceProbePassedBeforeSignal": True,
        "processReaped": True,
        "runningExecutableCodeIdentityMatchedHeldBytes": True,
        "signalName": "SIGKILL",
        "signalNumber": 9,
    }
    return {
        "abruptTermination": {
            "appKitProcessAbsentAfterReap": True,
            "capturedLogsRevalidatedAfterReap": True,
            "exactExecutableRevalidatedBeforeSignal": True,
            "exitCode": -9,
            "gracefulTerminationRequested": False,
            "inFlightWriteCheckpointObserved": False,
            "installedExecutableDescriptorHeldAcrossSignal": True,
            "launchMethod": "direct-installed-executable-owned-child",
            "migrationCommittedBeforeAbruptLaunch": True,
            "observationCompletedBeforeSignal": True,
            "pathIdentityStableAcrossSignal": True,
            "persistenceProbePassedBeforeSignal": True,
            "processDisposition": (
                "exact-owned-child-pid-sigkill-reaped-and-appkit-absent"
            ),
            "processReaped": True,
            "runningExecutableCodeIdentityMatchedHeldBytes": True,
            "signal": "SIGKILL",
            "signalNumber": 9,
            "signalTargetPolicy": "exact-popen-owned-child-pid-only-v1",
        },
        "app": {
            "architecture": "arm64",
            "buildNumber": 24,
            "bundleIdentifier": "dev.aetherlink.companion",
            "marketingVersion": "1.0.0",
            "minimumSystemVersion": "14.0",
            "uuid": EXPECTED_UUID,
        },
        "canary": canary,
        "cleanup": {
            "applicationSupportCleanupPerformed": False,
            "exactTemporaryAppPathOnly": True,
            "installedAppAbsentAfterFinalRemoval": True,
            "stateBytesAndModesUnchangedAfterAppRemoval": True,
            "temporaryRootRemoved": True,
        },
        "generation": generation,
        "installation": {
            "codesignVerified": False,
            "copyTool": "ditto",
            "installedAppMatchesPrivateSnapshot": True,
            "installedRelativePath": "Applications/AetherLink.app",
            "outerBundleSeal": "absent",
            "tree": app_identity,
        },
        "isolation": {
            "afInetBindDeniedByPreflight": True,
            "cleanHomeConfigured": True,
            "nonTemporaryWriteDeniedByPreflight": True,
            "preexistingAetherLinkApplicationsPreserved": True,
            "runtimeIdentityFileOverrideConfigured": True,
            "sandboxProfile": "allow-default-deny-network-and-non-temp-writes-v1",
            "sandboxed": True,
            "temporaryCFUserHomeConfigured": True,
        },
        "lifecycle": {
            "commandPolicy": (
                "sandbox-exec-direct-owned-child-held-code-directory-"
                "graceful-sigkill-recovery-v4"
            ),
            "distinctProcessIdentifiers": True,
            "runs": [
                {**graceful_run, "ordinal": 1},
                abrupt_run,
                {**graceful_run, "ordinal": 3},
            ],
        },
        "limitations": list(LIMITATIONS),
        "qualification": dict(QUALIFICATION),
        "schemaVersion": 1,
        "scope": RESULT_SCOPE,
        "stateRecovery": {
            "auxiliarySQLite": [
                {"filename": filename, "integrityCheck": "ok"}
                for filename in (
                    "runtime-document-index.sqlite",
                    "runtime-model-pull-approvals.sqlite",
                )
            ],
            (
                "installedStateBytesAndModesUnchangedAcrossAbruptTermination"
                "AndRelaunch"
            ): True,
            "legacyAbsentBeforeAbruptAndRecoveryReadback": True,
            "legacyFixturePreservedUnchanged": True,
            "migrationObservation": observation["migration"],
            "migrationSQLite": dict(sqlite),
            "ownedAbruptReadbackObservation": observation["sqliteReadback"],
            "ownedAbruptReadbackSQLite": dict(sqlite),
            "postAbruptSQLite": dict(sqlite),
            "recoveryReadbackObservation": observation["sqliteReadback"],
            "recoveryReadbackSQLite": dict(sqlite),
            "runtimeIdentityFilePresent": False,
            (
                "sqliteCanaryUnchangedAcrossAbruptTerminationAndRelaunch"
            ): True,
            (
                "stateBytesAndModesUnchangedImmediatelyAfterAbruptTermination"
            ): True,
            "stderr": {
                key: {"sha256": EMPTY_SHA256, "size": 0}
                for key in ("abruptReadback", "migration", "recoveryReadback")
            },
        },
        "status": "passed",
    }


def expected_receipt(result_identity: dict[str, object]) -> dict[str, object]:
    run_identity = {
        "sha256": result_identity["sha256"],
        "size": result_identity["size"],
        "status": "passed",
    }
    return {
        "canonicalResult": {
            "fileName": RESULT_RELATIVE.name,
            "sha256": result_identity["sha256"],
            "size": result_identity["size"],
        },
        "limitations": list(LIMITATIONS),
        "qualification": dict(QUALIFICATION),
        "resultBytesEqual": True,
        "runCount": 2,
        "runs": [
            {"ordinal": ordinal, **run_identity} for ordinal in (1, 2)
        ],
        "schemaVersion": 1,
        "scope": RECEIPT_SCOPE,
        "status": "passed",
    }


def validate_ledger(payload: bytes) -> None:
    expected = ["build_number\tmarketing_version"] + [
        f"{build}\t1.0.0" for build in range(1, 25)
    ]
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise EvidenceError(f"release ledger is not ASCII: {error}") from error
    if lines != expected or not payload.endswith(b"\n"):
        raise EvidenceError("release ledger is not the exact Build 1-24 lineage")


def validate_payloads(
    *,
    result_payload: bytes,
    receipt_payload: bytes,
    source_receipt_payload: bytes,
    app_identity: dict[str, object],
    dsym_identity: dict[str, object],
) -> None:
    source_receipt = parse_canonical_json(
        source_receipt_payload, label="source receipt"
    )
    if not exact_equal(source_receipt, expected_source_receipt()):
        raise EvidenceError("source receipt differs from the current generation")
    receipt_identity = {
        "sha256": hashlib.sha256(source_receipt_payload).hexdigest(),
        "size": len(source_receipt_payload),
    }
    if receipt_identity != {
        "sha256": EXPECTED_SOURCE_RECEIPT_SHA256,
        "size": 355,
    }:
        raise EvidenceError("source receipt byte identity differs")
    result = parse_canonical_json(result_payload, label="lifecycle result")
    expected = expected_result(
        app_identity=app_identity,
        dsym_identity=dsym_identity,
        receipt_identity=receipt_identity,
    )
    if not exact_equal(result, expected):
        raise EvidenceError("lifecycle result closed contract differs")
    result_identity = {
        "sha256": hashlib.sha256(result_payload).hexdigest(),
        "size": len(result_payload),
    }
    receipt = parse_canonical_json(receipt_payload, label="repeatability receipt")
    if not exact_equal(receipt, expected_receipt(result_identity)):
        raise EvidenceError("repeatability receipt closed contract differs")


def check() -> dict[str, object]:
    files = all_file_specs()
    if set(EXECUTION_SOURCE_CLOSURE) != set(EXECUTION_SOURCE_SPECS):
        raise EvidenceError("execution source closure differs from its pins")
    if any(
        path.name
        in {
            "check_macos_current_unsealed_install_recovery_evidence.py",
            "test_check_macos_current_unsealed_install_recovery_evidence.py",
        }
        for path in EXECUTION_SOURCE_CLOSURE
    ):
        raise EvidenceError("checker files must not enter the producer source closure")
    with pinned_payloads(files, all_directory_specs(files)) as payloads:
        validate_ledger(payloads[LEDGER_RELATIVE])
        app_identity = output_tree_identity(
            payloads,
            tree="AetherLink.app",
            files=APP_FILES,
            domain=b"aetherlink-macos-unsealed-app-tree-v1\0",
        )
        dsym_identity = output_tree_identity(
            payloads,
            tree="AetherLink.dSYM",
            files=DSYM_FILES,
            domain=b"aetherlink-macos-unsealed-dsym-tree-v1\0",
        )
        if app_identity != {
            "fileCount": 9,
            "sha256": EXPECTED_APP_TREE_SHA256,
            "size": 21_444_161,
        }:
            raise EvidenceError("held app tree identity differs")
        if dsym_identity != {
            "fileCount": 3,
            "sha256": EXPECTED_DSYM_TREE_SHA256,
            "size": 38_283_827,
        }:
            raise EvidenceError("held dSYM tree identity differs")
        validate_payloads(
            result_payload=payloads[RESULT_RELATIVE],
            receipt_payload=payloads[RECEIPT_RELATIVE],
            source_receipt_payload=payloads[
                OUTPUT_ROOT_RELATIVE / "source-receipt.json"
            ],
            app_identity=app_identity,
            dsym_identity=dsym_identity,
        )
    return {
        "appSha256": app_identity["sha256"],
        "dSYMSha256": dsym_identity["sha256"],
        "resultSha256": RESULT_SHA256,
        "sourceSha256": EXPECTED_SOURCE_SHA256,
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        print(
            "usage: check_macos_current_unsealed_install_recovery_evidence.py",
            file=sys.stderr,
        )
        return 2
    try:
        report = check()
    except (EvidenceError, OSError, ValueError) as error:
        print(
            f"macOS closed Build 24 unsealed evidence failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "macOS closed Build 24 unsealed evidence passed: "
        f"result={report['resultSha256']}; app={report['appSha256']}; "
        f"dSYM={report['dSYMSha256']}; source={report['sourceSha256']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
