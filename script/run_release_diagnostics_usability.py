#!/usr/bin/env python3
"""Prove that current Release diagnostics can recover one real source frame."""

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
from typing import Callable, Iterator, Sequence

if __package__:
    from script import check_release_artifact_archive as archive
else:
    import check_release_artifact_archive as archive


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "aetherlink-release-diagnostics-usability-v1"
SCHEMA_VERSION = 1
AGP_VERSION = "9.2.1"
RETRACE_VERSION = "9.2.14"
RETRACE_MAIN_CLASS = "com.android.tools.r8.retrace.Retrace"
RESULT_MAX_BYTES = 256 * 1024
COMMAND_MAX_BYTES = 4 * 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 60
SOURCE_MAX_BYTES = 8 * 1024 * 1024
ANDROID_MAPPING_MAX_BYTES = 256 * 1024 * 1024
ANDROID_ARTIFACT_MAX_BYTES = 256 * 1024 * 1024
MACOS_BINARY_MAX_BYTES = 1024 * 1024 * 1024
ANDROID_PROBE_EXCEPTION = (
    "java.lang.IllegalStateException: aetherlink-release-diagnostics-probe-v1"
)
ANDROID_PROBE_CANDIDATE_LIMIT = 64
QUALIFICATION = {
    "canonicalG6ExitClaimed": False,
    "deviceOrNetworkClaimed": False,
    "productionReleaseClaimed": False,
    "signedArtifactClaimed": False,
}
IMPLEMENTATION_PATHS = (
    Path("script/run_release_diagnostics_usability.py"),
    Path("script/check_release_diagnostics_usability.py"),
)
ANDROID_SOURCE_ROOTS = tuple(
    Path(value)
    for value in archive.SOURCE_ROOTS
    if value.startswith("apps/android/") and "/src" in value
)
MACOS_SOURCE_ROOTS = tuple(
    Path(value)
    for value in archive.SOURCE_ROOTS
    if value.startswith("apps/macos/")
)
ANDROID_MAPPING_PATH = (
    archive.ANDROID_RELEASE_MAPPING_RELATIVE_PATH / "mapping.txt"
)
MACOS_EXECUTABLE_PATH = (
    archive.MACOS_UNSEALED_OUTPUT_RELATIVE_PATH
    / "AetherLink.app/Contents/MacOS/AetherLink"
)
MACOS_DSYM_DWARF_PATH = (
    archive.MACOS_UNSEALED_OUTPUT_RELATIVE_PATH
    / "AetherLink.dSYM/Contents/Resources/DWARF/AetherLink"
)
MACOS_SOURCE_RECEIPT_PATH = (
    archive.MACOS_UNSEALED_OUTPUT_RELATIVE_PATH
    / archive.MACOS_UNSEALED_SOURCE_RECEIPT_NAME
)


class DiagnosticsError(RuntimeError):
    """Raised when a diagnostics usability observation cannot be proven."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise DiagnosticsError(f"result is not canonical JSON: {error}") from error


def _identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def read_regular_bytes(
    path: Path,
    *,
    maximum_bytes: int,
    require_single_link: bool = True,
) -> bytes:
    try:
        before_path = path.lstat()
    except OSError as error:
        raise DiagnosticsError(f"cannot stat required file {path}: {error}") from error
    if (
        stat.S_ISLNK(before_path.st_mode)
        or not stat.S_ISREG(before_path.st_mode)
        or (require_single_link and before_path.st_nlink != 1)
        or before_path.st_size <= 0
        or before_path.st_size > maximum_bytes
    ):
        raise DiagnosticsError(
            f"required file must be bounded, regular, and single-link: {path}"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise DiagnosticsError(f"cannot open required file {path}: {error}") from error
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, maximum_bytes + 1 - total),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise DiagnosticsError(f"required file exceeds limit: {path}")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        final_path = path.lstat()
    except OSError as error:
        raise DiagnosticsError(f"required file disappeared: {path}: {error}") from error
    if (
        _identity(before_path) != _identity(before)
        or _identity(before) != _identity(after)
        or _identity(after) != _identity(final_path)
        or total != before.st_size
    ):
        raise DiagnosticsError(f"required file changed while read: {path}")
    return b"".join(chunks)


def file_record(path: Path, data: bytes, *, root: Path = ROOT) -> dict[str, object]:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as error:
        raise DiagnosticsError(f"artifact is outside the repository: {path}") from error
    return {"path": relative, "sha256": sha256(data), "size": len(data)}


def run_command(
    command: Sequence[str],
    *,
    root: Path = ROOT,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    maximum_bytes: int = COMMAND_MAX_BYTES,
    allow_stderr: bool = False,
) -> tuple[str, str]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            list(command),
            cwd=root,
            capture_output=True,
            check=False,
            env=environment,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise DiagnosticsError(f"command timed out: {list(command)!r}") from error
    except OSError as error:
        raise DiagnosticsError(f"command could not start: {list(command)!r}: {error}") from error
    if len(result.stdout) + len(result.stderr) > maximum_bytes:
        raise DiagnosticsError(f"command output exceeded limit: {list(command)!r}")
    try:
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DiagnosticsError(f"command output is not UTF-8: {list(command)!r}") from error
    if result.returncode != 0:
        raise DiagnosticsError(
            f"command failed with exit {result.returncode}: {list(command)!r}"
        )
    if stderr and not allow_stderr:
        raise DiagnosticsError(f"command emitted unexpected stderr: {list(command)!r}")
    return stdout, stderr


def prerequisite_digest(platform: str, *, root: Path = ROOT) -> str:
    try:
        if platform == "android":
            value = archive.verify_android_release_build_outputs(root)
        elif platform == "macos":
            value = archive.verify_macos_release_build_outputs(root)
        else:
            raise DiagnosticsError(f"unsupported platform: {platform}")
    except archive.ReleaseArchiveVerificationError as error:
        raise DiagnosticsError(f"{platform} Release readback failed: {error}") from error
    return sha256(archive.canonical_json_bytes(value))


def source_record(
    *,
    root: Path,
    roots: Sequence[Path],
    source_file: str,
    source_line: int,
) -> dict[str, object]:
    if (
        Path(source_file).name != source_file
        or re.fullmatch(r"[A-Za-z0-9_+.-]+\.(?:kt|java|swift)", source_file) is None
        or type(source_line) is not int
        or source_line <= 0
    ):
        raise DiagnosticsError("diagnostic source location is not canonical")
    candidates: list[tuple[Path, bytes, list[bytes]]] = []
    for relative_root in roots:
        base = root / relative_root
        if not base.is_dir() or base.is_symlink():
            continue
        for candidate in sorted(base.rglob(source_file)):
            if candidate.is_symlink() or not candidate.is_file():
                continue
            data = read_regular_bytes(candidate, maximum_bytes=SOURCE_MAX_BYTES)
            if b"\0" in data or b"\r" in data or not data.endswith(b"\n"):
                continue
            lines = data.splitlines(keepends=True)
            if source_line <= len(lines):
                candidates.append((candidate, data, lines))
    if len(candidates) != 1:
        raise DiagnosticsError(
            f"diagnostic source must resolve uniquely: {source_file}:{source_line}"
        )
    path, data, lines = candidates[0]
    line = lines[source_line - 1]
    return {
        **file_record(path, data, root=root),
        "line": source_line,
        "lineSha256": sha256(line),
    }


ANDROID_CLASS_RE = re.compile(
    r"(?P<original>com\.localagentbridge\.[A-Za-z0-9_.$]+) -> "
    r"(?P<obfuscated>[A-Za-z0-9_.$]+):\Z"
)
ANDROID_SOURCE_RE = re.compile(
    r'# \{"id":"sourceFile","fileName":"(?P<source>[A-Za-z0-9_+.-]+\.(?:kt|java))"\}\Z'
)
ANDROID_METHOD_RE = re.compile(
    r"    (?P<obfuscatedStart>[1-9][0-9]*):(?P<obfuscatedEnd>[1-9][0-9]*):"
    r"[^ ]+ (?P<originalMethod>[A-Za-z_$][A-Za-z0-9_$]*)\([^)]*\):"
    r"(?P<sourceStart>[1-9][0-9]*)(?::(?P<sourceEnd>[1-9][0-9]*))? -> "
    r"(?P<obfuscatedMethod>[A-Za-z_$][A-Za-z0-9_$]*)\Z"
)


def android_mapping_metadata(mapping: bytes) -> dict[str, str]:
    if b"\0" in mapping or b"\r" in mapping or not mapping.endswith(b"\n"):
        raise DiagnosticsError("R8 mapping must be nonempty UTF-8/LF text")
    try:
        text = mapping.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DiagnosticsError("R8 mapping is not UTF-8") from error
    values: dict[str, str] = {}
    patterns = {
        "compiler": re.compile(r"# compiler: (R8)\Z"),
        "compilerVersion": re.compile(r"# compiler_version: ([0-9]+(?:\.[0-9]+)+)\Z"),
        "mapId": re.compile(r"# pg_map_id: ([0-9a-f]{64})\Z"),
        "mapHash": re.compile(r"# pg_map_hash: SHA-256 ([0-9a-f]{64})\Z"),
    }
    for line in text.splitlines()[:16]:
        for key, pattern in patterns.items():
            match = pattern.fullmatch(line)
            if match is not None:
                values[key] = match.group(1)
    if set(values) != set(patterns) or values["compilerVersion"] != RETRACE_VERSION:
        raise DiagnosticsError("R8 mapping compiler metadata differs from the pinned gate")
    return values


def iter_android_probe_candidates(mapping: bytes) -> Iterator[dict[str, object]]:
    try:
        lines = mapping.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise DiagnosticsError("R8 mapping is not UTF-8") from error
    original_class: str | None = None
    obfuscated_class: str | None = None
    source_file: str | None = None
    for line in lines:
        class_match = ANDROID_CLASS_RE.fullmatch(line)
        if class_match is not None:
            original_class = class_match.group("original")
            obfuscated_class = class_match.group("obfuscated")
            source_file = None
            continue
        if line and not line.startswith((" ", "#")):
            original_class = obfuscated_class = source_file = None
            continue
        source_match = ANDROID_SOURCE_RE.fullmatch(line)
        if source_match is not None and original_class is not None:
            source_file = source_match.group("source")
            continue
        if original_class is None or obfuscated_class is None or source_file is None:
            continue
        method_match = ANDROID_METHOD_RE.fullmatch(line)
        if method_match is None:
            continue
        original_method = method_match.group("originalMethod")
        obfuscated_method = method_match.group("obfuscatedMethod")
        if (
            obfuscated_class == original_class
            or obfuscated_class.startswith("R8$$REMOVED$$CLASS$$")
            or obfuscated_method == original_method
            or original_method in {"<init>", "<clinit>"}
            or obfuscated_method in {"<init>", "<clinit>"}
        ):
            continue
        obfuscated_line = int(method_match.group("obfuscatedStart"))
        source_line = int(method_match.group("sourceStart"))
        if obfuscated_line > int(method_match.group("obfuscatedEnd")):
            continue
        yield {
            "mappingLineSha256": sha256((line + "\n").encode("utf-8")),
            "obfuscatedClass": obfuscated_class,
            "obfuscatedLine": obfuscated_line,
            "obfuscatedMethod": obfuscated_method,
            "originalClass": original_class,
            "originalMethod": original_method,
            "sourceFile": source_file,
            "sourceLine": source_line,
        }


def resolve_android_probe(
    mapping: bytes,
    *,
    root: Path,
    mapping_path: Path,
    java: Path,
    classpath: str,
) -> tuple[dict[str, object], dict[str, object], bytes, bytes]:
    eligible_count = 0
    for probe in iter_android_probe_candidates(mapping):
        eligible_count += 1
        if eligible_count > ANDROID_PROBE_CANDIDATE_LIMIT:
            break
        try:
            source = source_record(
                root=root,
                roots=ANDROID_SOURCE_ROOTS,
                source_file=str(probe["sourceFile"]),
                source_line=int(probe["sourceLine"]),
            )
        except DiagnosticsError:
            continue
        obfuscated_frame = (
            f"at {probe['obfuscatedClass']}.{probe['obfuscatedMethod']}"
            f"({probe['sourceFile']}:{probe['obfuscatedLine']})"
        )
        original_frame = (
            f"at {probe['originalClass']}.{probe['originalMethod']}"
            f"({probe['sourceFile']}:{probe['sourceLine']})"
        )
        stack = f"{ANDROID_PROBE_EXCEPTION}\n\t{obfuscated_frame}\n".encode(
            "utf-8"
        )
        expected_output = (
            f"{ANDROID_PROBE_EXCEPTION}\n\t{original_frame}\n"
        ).encode("utf-8")
        output = run_retrace(
            root=root,
            java=java,
            classpath=classpath,
            mapping_path=mapping_path,
            stack=stack,
        )
        if output == expected_output and output != stack:
            return probe, source, stack, output
    if eligible_count == 0:
        raise DiagnosticsError(
            "R8 mapping has no eligible project-owned obfuscated frame"
        )
    raise DiagnosticsError(
        "R8 mapping has no bounded candidate that uniquely recovers one "
        "repository source frame"
    )


def android_tool(root: Path) -> tuple[Path, str, Path, str]:
    try:
        java = archive.java_executable()
        classpath = archive.bundletool_runtime_classpath(root)
    except archive.ReleaseArchiveVerificationError as error:
        raise DiagnosticsError(f"cannot resolve the AGP runtime classpath: {error}") from error
    entries = [Path(value) for value in classpath.split(os.pathsep)]
    builders = [path for path in entries if path.name == f"builder-{AGP_VERSION}.jar"]
    if len(builders) != 1:
        raise DiagnosticsError("AGP runtime classpath must contain one pinned builder JAR")
    builder = builders[0]
    version_stdout, version_stderr = run_command(
        [
            str(java),
            "-Dfile.encoding=UTF-8",
            "-Duser.language=en",
            "-Duser.country=US",
            "-cp",
            classpath,
            RETRACE_MAIN_CLASS,
            "--version",
        ],
        root=root,
        allow_stderr=True,
    )
    version_text = (version_stdout + version_stderr).strip()
    if re.fullmatch(
        rf"Retrace {re.escape(RETRACE_VERSION)} \(build [ -~]{{1,512}}\)",
        version_text,
    ) is None:
        raise DiagnosticsError("AGP-pinned Retrace version output differs")
    return java, classpath, builder, version_text


def run_retrace(
    *,
    root: Path,
    java: Path,
    classpath: str,
    mapping_path: Path,
    stack: bytes,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="aetherlink-retrace-probe-") as temporary:
        stack_path = Path(temporary) / "stack.txt"
        stack_path.write_bytes(stack)
        stack_path.chmod(0o600)
        stdout, stderr = run_command(
            [
                str(java),
                "-Dfile.encoding=UTF-8",
                "-Duser.language=en",
                "-Duser.country=US",
                "-cp",
                classpath,
                RETRACE_MAIN_CLASS,
                str(mapping_path),
                str(stack_path),
            ],
            root=root,
        )
        if stderr:
            raise DiagnosticsError("Retrace emitted unexpected stderr")
    try:
        return stdout.encode("utf-8")
    except UnicodeEncodeError as error:
        raise DiagnosticsError("Retrace output could not be encoded") from error


def android_observation(root: Path = ROOT) -> dict[str, object]:
    prerequisite = prerequisite_digest("android", root=root)
    mapping_path = root / ANDROID_MAPPING_PATH
    apk_path = root / archive.ANDROID_RELEASE_APK_RELATIVE_PATH
    aab_path = root / archive.ANDROID_RELEASE_AAB_RELATIVE_PATH
    mapping = read_regular_bytes(mapping_path, maximum_bytes=ANDROID_MAPPING_MAX_BYTES)
    apk = read_regular_bytes(apk_path, maximum_bytes=ANDROID_ARTIFACT_MAX_BYTES)
    aab = read_regular_bytes(aab_path, maximum_bytes=ANDROID_ARTIFACT_MAX_BYTES)
    artifacts = {
        "aab": file_record(aab_path, aab, root=root),
        "apk": file_record(apk_path, apk, root=root),
        "mapping": file_record(mapping_path, mapping, root=root),
    }
    mapping_metadata = android_mapping_metadata(mapping)
    java, classpath, builder, retrace_version = android_tool(root)
    builder_data = read_regular_bytes(builder, maximum_bytes=256 * 1024 * 1024)
    probe, source, stack, output = resolve_android_probe(
        mapping,
        root=root,
        mapping_path=mapping_path,
        java=java,
        classpath=classpath,
    )
    obfuscated_frame = (
        f"at {probe['obfuscatedClass']}.{probe['obfuscatedMethod']}"
        f"({probe['sourceFile']}:{probe['obfuscatedLine']})"
    )
    original_frame = (
        f"at {probe['originalClass']}.{probe['originalMethod']}"
        f"({probe['sourceFile']}:{probe['sourceLine']})"
    )
    expected_output = f"{ANDROID_PROBE_EXCEPTION}\n\t{original_frame}\n".encode("utf-8")
    if output != expected_output or output == stack:
        raise DiagnosticsError("Retrace did not uniquely recover the selected source frame")
    final = {
        "aab": file_record(aab_path, read_regular_bytes(aab_path, maximum_bytes=ANDROID_ARTIFACT_MAX_BYTES), root=root),
        "apk": file_record(apk_path, read_regular_bytes(apk_path, maximum_bytes=ANDROID_ARTIFACT_MAX_BYTES), root=root),
        "mapping": file_record(mapping_path, read_regular_bytes(mapping_path, maximum_bytes=ANDROID_MAPPING_MAX_BYTES), root=root),
    }
    if final != artifacts:
        raise DiagnosticsError("Android Release diagnostics inputs changed during observation")
    return {
        "artifacts": artifacts,
        "contract": CONTRACT,
        "implementation": [
            file_record(
                root / relative,
                read_regular_bytes(root / relative, maximum_bytes=RESULT_MAX_BYTES),
                root=root,
            )
            for relative in IMPLEMENTATION_PATHS
        ],
        "mapping": mapping_metadata,
        "platform": "android",
        "prerequisiteReadbackSha256": prerequisite,
        "probe": {
            **probe,
            "inputSha256": sha256(stack),
            "obfuscatedFrame": obfuscated_frame,
            "originalFrame": original_frame,
            "outputSha256": sha256(output),
            "source": source,
        },
        "qualification": dict(QUALIFICATION),
        "result": "android-r8-retrace-resolved-one-project-frame",
        "schemaVersion": SCHEMA_VERSION,
        "tool": {
            "agpVersion": AGP_VERSION,
            "builderJar": {
                "name": builder.name,
                "sha256": sha256(builder_data),
                "size": len(builder_data),
            },
            "classpathEntryCount": len(classpath.split(os.pathsep)),
            "mainClass": RETRACE_MAIN_CLASS,
            "retraceVersion": retrace_version,
        },
    }


NM_TEXT_RE = re.compile(r"(?P<address>[0-9a-f]{16}) [Tt] (?P<symbol>\S+)\Z")
ATOS_RE = re.compile(
    r"(?P<symbol>.+) \(in AetherLink\) "
    r"\((?P<source>[A-Za-z0-9_+.-]+\.swift):(?P<line>[1-9][0-9]*)\)\Z"
)
UUID_RE = re.compile(
    r"UUID: (?P<uuid>[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}) "
    r"\(arm64\) .+\Z"
)


def macos_uuid(path: Path, *, root: Path) -> str:
    stdout, _ = run_command(["/usr/bin/dwarfdump", "--uuid", str(path)], root=root)
    lines = stdout.splitlines()
    if len(lines) != 1:
        raise DiagnosticsError("dwarfdump must emit one UUID line")
    match = UUID_RE.fullmatch(lines[0])
    if match is None:
        raise DiagnosticsError("dwarfdump UUID output differs")
    return match.group("uuid")


def macos_probe(
    *,
    executable: Path,
    dwarf: Path,
    root: Path,
) -> dict[str, object]:
    stdout, _ = run_command(
        ["/usr/bin/nm", "-n", "-arch", "arm64", str(executable)],
        root=root,
        maximum_bytes=16 * 1024 * 1024,
    )
    candidates: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        match = NM_TEXT_RE.fullmatch(line)
        if match is not None and match.group("symbol") != "__mh_execute_header":
            candidates.append((match.group("address"), match.group("symbol")))
    if not candidates:
        raise DiagnosticsError("Release executable has no defined text symbol probe")
    for offset in range(0, len(candidates), 100):
        batch = candidates[offset : offset + 100]
        atos_stdout, _ = run_command(
            [
                "/usr/bin/atos",
                "-arch",
                "arm64",
                "-o",
                str(dwarf),
                *(f"0x{address}" for address, _ in batch),
            ],
            root=root,
            maximum_bytes=1024 * 1024,
        )
        outputs = atos_stdout.splitlines()
        if len(outputs) != len(batch):
            raise DiagnosticsError("atos output count differs from the address batch")
        for (address, nm_symbol), output in zip(batch, outputs):
            match = ATOS_RE.fullmatch(output)
            if match is None:
                continue
            source_line = int(match.group("line"))
            try:
                source = source_record(
                    root=root,
                    roots=MACOS_SOURCE_ROOTS,
                    source_file=match.group("source"),
                    source_line=source_line,
                )
            except DiagnosticsError:
                continue
            return {
                "address": f"0x{address}",
                "nmSymbol": nm_symbol,
                "source": source,
                "sourceFile": match.group("source"),
                "sourceLine": source_line,
                "symbol": match.group("symbol"),
                "symbolicatedFrame": output,
                "symbolicatedFrameSha256": sha256((output + "\n").encode("utf-8")),
            }
    raise DiagnosticsError("dSYM could not recover one unique repository source frame")


def tool_file_record(path: Path) -> dict[str, object]:
    data = read_regular_bytes(
        path,
        maximum_bytes=64 * 1024 * 1024,
        require_single_link=False,
    )
    return {"path": str(path), "sha256": sha256(data), "size": len(data)}


def macos_observation(root: Path = ROOT) -> dict[str, object]:
    prerequisite = prerequisite_digest("macos", root=root)
    executable_path = root / MACOS_EXECUTABLE_PATH
    dwarf_path = root / MACOS_DSYM_DWARF_PATH
    receipt_path = root / MACOS_SOURCE_RECEIPT_PATH
    executable = read_regular_bytes(executable_path, maximum_bytes=MACOS_BINARY_MAX_BYTES)
    dwarf = read_regular_bytes(dwarf_path, maximum_bytes=MACOS_BINARY_MAX_BYTES)
    receipt = read_regular_bytes(receipt_path, maximum_bytes=archive.MACOS_UNSEALED_SOURCE_RECEIPT_MAX_BYTES)
    artifacts = {
        "dSYM": file_record(dwarf_path, dwarf, root=root),
        "executable": file_record(executable_path, executable, root=root),
        "sourceReceipt": file_record(receipt_path, receipt, root=root),
    }
    executable_uuid = macos_uuid(executable_path, root=root)
    dwarf_uuid = macos_uuid(dwarf_path, root=root)
    if executable_uuid != dwarf_uuid:
        raise DiagnosticsError("Release executable and dSYM UUID differ")
    probe = macos_probe(executable=executable_path, dwarf=dwarf_path, root=root)
    final = {
        "dSYM": file_record(dwarf_path, read_regular_bytes(dwarf_path, maximum_bytes=MACOS_BINARY_MAX_BYTES), root=root),
        "executable": file_record(executable_path, read_regular_bytes(executable_path, maximum_bytes=MACOS_BINARY_MAX_BYTES), root=root),
        "sourceReceipt": file_record(receipt_path, read_regular_bytes(receipt_path, maximum_bytes=archive.MACOS_UNSEALED_SOURCE_RECEIPT_MAX_BYTES), root=root),
    }
    if final != artifacts:
        raise DiagnosticsError("macOS Release diagnostics inputs changed during observation")
    return {
        "artifacts": artifacts,
        "contract": CONTRACT,
        "implementation": [
            file_record(
                root / relative,
                read_regular_bytes(root / relative, maximum_bytes=RESULT_MAX_BYTES),
                root=root,
            )
            for relative in IMPLEMENTATION_PATHS
        ],
        "platform": "macos",
        "prerequisiteReadbackSha256": prerequisite,
        "probe": {**probe, "uuid": executable_uuid},
        "qualification": dict(QUALIFICATION),
        "result": "macos-dsym-symbolicated-one-project-frame",
        "schemaVersion": SCHEMA_VERSION,
        "tool": {
            "atos": tool_file_record(Path("/usr/bin/atos")),
            "dwarfdump": tool_file_record(Path("/usr/bin/dwarfdump")),
            "nm": tool_file_record(Path("/usr/bin/nm")),
        },
    }


def write_result(path: Path, value: object) -> None:
    data = canonical_json_bytes(value)
    if len(data) > RESULT_MAX_BYTES:
        raise DiagnosticsError("diagnostics result exceeds its byte limit")
    parent = path.parent
    try:
        parent_status = parent.lstat()
    except OSError as error:
        raise DiagnosticsError(f"result parent does not exist: {parent}: {error}") from error
    if stat.S_ISLNK(parent_status.st_mode) or not stat.S_ISDIR(parent_status.st_mode):
        raise DiagnosticsError("result parent must be a physical directory")
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=parent
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        directory_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as error:
        raise DiagnosticsError(f"cannot publish diagnostics result: {error}") from error
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("android", "macos"), required=True)
    parser.add_argument("--result", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        value = (
            android_observation(ROOT)
            if arguments.platform == "android"
            else macos_observation(ROOT)
        )
        write_result(arguments.result, value)
    except DiagnosticsError as error:
        print(f"Release diagnostics usability failed: {error}", file=os.sys.stderr)
        return 1
    print(
        f"Release diagnostics usability passed for {arguments.platform}: "
        f"{arguments.result}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
