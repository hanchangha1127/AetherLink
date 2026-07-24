#!/usr/bin/env python3
"""Validate the Wave3 decision and one-use 32-resource acquisition permit."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("Wave3 acquisition checker requires `python3 -I -B -S`")

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "docs/security-hardening/production-p2p-nat-v1/"
    "g2-pion-restricted-fork-v1/rung-three"
)
DECISION_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-decision-v1.json"
DECISION_READER_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-decision-v1.md"
PERMIT_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-execution-permit-v1.json"
PERMIT_READER_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-execution-permit-v1.md"
THIS_CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition_v1.py"
THIS_TESTS_PATH = "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_acquisition_v1.py"
RUNNER_PATH = "script/acquire_p2p_nat_g2_pion_rung3_dependency_wave3_v1_once.py"
RUNNER_TESTS_PATH = "script/test_acquire_p2p_nat_g2_pion_rung3_dependency_wave3_v1_once.py"
V2_CHECKER_PATH = "script/check_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v2.py"
EXPECTED_V2_CHECKER_RAW = "95578b6158f3080d93908d7c4aa59fb2172e1cb51b571bc45dfb1bf795c72c4a"
V2_PACKAGE = {
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-wave3-v2.json": "34d07a07dffe0c480f965192d8d81bc1961fd1ea2847e5ec5b0a2ca361d1c350",
    f"{BASE}/bounded-dependency-source-identity-and-acquisition-decision-wave3-v2.md": "220ee4b2f702da254c18b4985112928edc5bea42a8896a5527ed9c684772df4a",
    V2_CHECKER_PATH: EXPECTED_V2_CHECKER_RAW,
    "script/test_p2p_nat_g2_pion_rung3_dependency_wave3_decision_v2.py": "a83c408cf216335c2a0a6491344e5dbdc15028e5c00f1b2ec143ef2923cc9782",
}
EXPECTED_V2_CONTENT = "83f97eeece6f5802f4b2fc807469a8abd08971cc8712a3bad415e801258d2e9f"
EXPECTED_DECISION_READER_RAW = "3ea8982d4d7b552eacf351ad9261b33f5aa54242022923f77ae19b12f3951ae5"
EXPECTED_PERMIT_READER_RAW = "48d9e5a69cadf38b927f21b280f523011063b86a2c1d827d889d2a100604fc85"
EXPECTED_RUNNER_NORMALIZED_SHA256 = "f5d21fe4eac889ddc892f81185e7b5f78f59a02cf45d263318cf86b61316d2e6"
PROXY_HOST = "proxy.golang.org"
CLAIM_PATH = "build/offline-source/pion-ice-v4.3.0/dependencies/.wave-3-v1.claim"
DEPENDENCY_ROOT = "build/offline-source/pion-ice-v4.3.0/dependencies"
STAGING_PREFIX = ".wave-3-v1-staging-"
FINAL_ROOT = f"{DEPENDENCY_ROOT}/wave-3-v1"
FINAL_ACCEPTED = f"{FINAL_ROOT}/accepted"
RECEIPT_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-receipt-v1.json"
FAILURE_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-failure-v1.json"
MANIFEST_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-manifest-v1.json"
READBACK_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-readback-v1.json"
READBACK_MANIFEST_PATH = f"{BASE}/bounded-dependency-source-acquisition-wave3-readback-manifest-v1.json"
MAX_MOD_BYTES = 1 * 1024 * 1024
MAX_ZIP_BYTES = 16 * 1024 * 1024
MAX_AGGREGATE_MOD_BYTES = 8 * 1024 * 1024
MAX_AGGREGATE_ZIP_BYTES = 128 * 1024 * 1024
MAX_AGGREGATE_BYTES = 128 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
PER_REQUEST_DEADLINE_MS = 30_000
WHOLE_ATTEMPT_DEADLINE_MS = 600_000
MAX_ZIP_FILES = 20_000
MAX_ZIP_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ZIP_FILE_BYTES = 128 * 1024 * 1024
MAX_ZIP_NAME_BYTES = 1_024
MAXIMUM_TOOL_BYTES = 8 * 1024 * 1024


class CheckError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(value: bool, code: str) -> None:
    if not value:
        raise CheckError(code)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode() + b"\n"


def strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            require(key not in result, "E_JSON")
            result[key] = value
        return result
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(CheckError("E_JSON")),
            parse_constant=lambda _: (_ for _ in ()).throw(CheckError("E_JSON")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CheckError("E_JSON") from error
    require(type(value) is dict, "E_JSON")
    return value


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    require("contentBinding" not in value, "E_CONTENT")
    value["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(value)),
    }
    return value


def verify_bound(raw: bytes, expected: Mapping[str, Any], code: str) -> None:
    require(raw == canonical_bytes(expected) and strict_json(raw) == expected, code)
    value = dict(expected)
    binding = value.pop("contentBinding")
    require(
        binding == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": sha256(canonical_bytes(value)),
        },
        "E_CONTENT",
    )


def stable_read(path: str, expected: str | None = None) -> bytes:
    current = ROOT
    for component in path.split("/")[:-1]:
        current /= component
        info = current.lstat()
        require(
            stat.S_ISDIR(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(info.st_mode) & 0o022 == 0,
            "E_PATH",
        )
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(ROOT / path, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_TOOL_BYTES,
            "E_SHAPE",
        )
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_READ")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(fd, 1), "E_READ")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        stable_fields = (
            "st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid",
            "st_size", "st_mtime_ns", "st_ctime_ns",
        )
        require(
            all(getattr(before, field) == getattr(after, field) for field in stable_fields)
            and (expected is None or sha256(raw) == expected),
            "E_BINDING",
        )
        return raw
    finally:
        os.close(fd)


def load_v2() -> types.ModuleType:
    raw = stable_read(V2_CHECKER_PATH, EXPECTED_V2_CHECKER_RAW)
    module = types.ModuleType("wave3_v2_authority")
    module.__file__ = str(ROOT / V2_CHECKER_PATH)
    module.__package__ = ""
    exec(compile(raw, V2_CHECKER_PATH, "exec"), module.__dict__)
    return module


V2 = load_v2()


def escape_proxy_component(value: str) -> str:
    require(type(value) is str and value and "!" not in value, "E_ESCAPE")
    result = []
    for character in value:
        if "A" <= character <= "Z":
            result.extend(("!", character.lower()))
        else:
            require(
                character.isascii()
                and (character.isalnum() or character in "-._~/+"),
                "E_ESCAPE",
            )
            result.append(character)
    return "".join(result)


def resources_from_v2(v2: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    ordinal = 0
    for tuple_row in v2["wave"]["tuples"]:
        module = tuple_row["module"]
        version = tuple_row["version"]
        escaped_module = escape_proxy_component(module)
        escaped_version = escape_proxy_component(version)
        identity = tuple_row["checksumIdentity"]
        for kind, expected_h1, maximum in (
            ("mod", identity["goModH1"], MAX_MOD_BYTES),
            ("zip", identity["moduleZipH1"], MAX_ZIP_BYTES),
        ):
            ordinal += 1
            path = f"/{escaped_module}/@v/{escaped_version}.{kind}"
            rows.append(
                {
                    "requestOrdinal": ordinal,
                    "tupleOrder": tuple_row["tupleOrder"],
                    "tupleId": tuple_row["tupleId"],
                    "module": module,
                    "version": version,
                    "kind": kind,
                    "method": "GET",
                    "host": PROXY_HOST,
                    "path": path,
                    "url": f"https://{PROXY_HOST}{path}",
                    "expectedH1": expected_h1,
                    "maximumResponseBodyBytes": maximum,
                    "acceptedFileName": (
                        f"{tuple_row['tupleOrder']:03d}-"
                        f"{tuple_row['tupleDigestSha256'][:20]}.{kind}"
                    ),
                }
            )
    require(
        len(rows) == 32
        and [row["requestOrdinal"] for row in rows] == list(range(1, 33))
        and all(
            rows[index]["kind"] == ("mod" if index % 2 == 0 else "zip")
            for index in range(32)
        ),
        "E_RESOURCES",
    )
    return rows


def v2_expected() -> dict[str, Any]:
    expected, summary = V2.evaluate(True)
    require(
        summary["validationPassed"] is True
        and summary["identityRecordCount"] == 32
        and summary["acquisitionReady"] is True
        and summary["acquisitionAuthorized"] is False,
        "E_V2",
    )
    for path, digest in V2_PACKAGE.items():
        require(sha256(stable_read(path, digest)) == digest, "E_V2")
    return expected


def decision_payload(package_raw: Mapping[str, bytes]) -> dict[str, Any]:
    v2 = v2_expected()
    resources = resources_from_v2(v2)
    return {
        "documentType": "aetherlink.wave3-source-acquisition-decision",
        "schemaVersion": "1.0",
        "decisionId": "g2-pion-rung3-wave3-32-resource-source-acquisition-decision-v1",
        "recordedDate": "2026-07-24",
        "status": "exact_32_resource_contract_prepared_acquisition_not_authorized",
        "wave3IdentityDecisionBinding": {
            "files": [{"path": path, "rawSha256": digest} for path, digest in V2_PACKAGE.items()],
            "contentSha256": EXPECTED_V2_CONTENT,
            "requiredStatus": (
                "wave3_exact_16_frontier_identity_classified_"
                "16_complete_0_blocked_acquisition_ready_not_authorized"
            ),
        },
        "requestSet": {
            "tupleCount": 16,
            "resourcesPerTuple": 2,
            "requestCount": 32,
            "order": "tuple_order_ascending_mod_then_zip",
            "host": PROXY_HOST,
            "resources": resources,
            "canonicalSha256": sha256(canonical_bytes(resources)),
        },
        "verificationDesign": {
            "goModH1Algorithm": "golang.org/x/mod/sumdb/dirhash.Hash1_v1_single_go_mod",
            "moduleZipH1Algorithm": "golang.org/x/mod/sumdb/dirhash.HashZip(Hash1)_v1",
            "rawSha256RecordedSeparately": True,
            "zipExactModuleVersionPrefixRequired": True,
            "zipSafetyAndShapeValidationRequired": True,
            "sourceExtractionAllowed": False,
        },
        "reservedNamespace": {
            "claimPath": CLAIM_PATH,
            "stagingPrefix": STAGING_PREFIX,
            "finalAcceptedPath": FINAL_ACCEPTED,
            "receiptPath": RECEIPT_PATH,
            "failurePath": FAILURE_PATH,
            "manifestPath": MANIFEST_PATH,
            "readbackPath": READBACK_PATH,
            "readbackManifestPath": READBACK_MANIFEST_PATH,
            "allCurrentlyAbsent": True,
            "reservationIsWriteAuthority": False,
        },
        "authority": {
            "decisionRecorded": True,
            "decisionIsExecutionPermit": False,
            "networkAuthorized": False,
            "filesystemMutationAuthorized": False,
            "sourceAcquisitionAuthorized": False,
            "sourceExtractionAuthorized": False,
            "sourceLoadAuthorized": False,
            "sourceExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "closure": dict(v2["closure"]),
        "readerDocumentBinding": {
            "path": DECISION_READER_PATH,
            "rawSha256": EXPECTED_DECISION_READER_RAW,
        },
        "toolBindings": [
            {"path": path, "rawSha256": sha256(package_raw[path])}
            for path in (THIS_CHECKER_PATH, THIS_TESTS_PATH)
        ],
        "nonClaims": [
            "this decision is not acquisition or network authority",
            "checksum H1 values are not source author or repository attestation",
            "no source bytes were acquired extracted loaded executed reviewed or compiled",
            "no dependency fixed point semantic closure selection or release is established",
        ],
        "result": "exact_16_tuple_32_resource_request_contract_prepared_not_authorized",
        "nextAction": "validate_separate_one_use_wave3_source_acquisition_execution_permit",
    }


def normalized_runner(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    pattern = re.compile(r'EXPECTED_CHECKER_RAW = "[0-9a-f]{64}"')
    require(len(pattern.findall(text)) == 1, "E_RUNNER")
    return pattern.sub('EXPECTED_CHECKER_RAW = "' + "0" * 64 + '"', text).encode()


def validate_runner(runner_raw: bytes, checker_raw: bytes) -> None:
    require(sha256(normalized_runner(runner_raw)) == EXPECTED_RUNNER_NORMALIZED_SHA256, "E_RUNNER")
    source = runner_raw.decode("utf-8", errors="strict")
    tree = ast.parse(source)
    imports = set()
    functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, ast.FunctionDef):
            functions.add(node.name)
    require(
        not {"subprocess", "socket", "requests", "urllib.request"} & imports
        and {
            "direct_fetch", "go_mod_h1", "module_zip_h1", "validate_zip",
            "create_claim", "rename_exclusive", "preflight", "execute",
        } <= functions,
        "E_RUNNER",
    )
    for token in (
        "http.client.HTTPSConnection", "ssl.create_default_context",
        "os.O_EXCL", "os.fsync", "renameatx_np", "signal.setitimer",
        "zipfile.ZipFile", "body=None", "encode_chunked=False",
    ):
        require(token in source, "E_RUNNER")
    for token in ("urlopen", "ProxyHandler", "shutil.rmtree", "subprocess", "shell=True"):
        require(token not in source, "E_RUNNER")
    reverse = re.findall(r'EXPECTED_CHECKER_RAW = "([0-9a-f]{64})"', source)
    require(reverse == [sha256(checker_raw)], "E_RUNNER")


def namespace_absent() -> None:
    for path in (CLAIM_PATH, FINAL_ROOT, RECEIPT_PATH, FAILURE_PATH, MANIFEST_PATH, READBACK_PATH, READBACK_MANIFEST_PATH):
        require(not (ROOT / path).exists(), "E_NAMESPACE")
    parent = ROOT / DEPENDENCY_ROOT
    require(not any(p.name.startswith(STAGING_PREFIX) for p in parent.iterdir()), "E_NAMESPACE")


def permit_payload(
    decision: Mapping[str, Any],
    decision_raw: bytes,
    package_raw: Mapping[str, bytes],
) -> dict[str, Any]:
    resources = decision["requestSet"]["resources"]
    validate_runner(package_raw[RUNNER_PATH], package_raw[THIS_CHECKER_PATH])
    return {
        "documentType": "aetherlink.wave3-source-acquisition-execution-permit",
        "schemaVersion": "1.0",
        "permitId": "g2-pion-rung3-wave3-32-resource-source-acquisition-execution-permit-v1",
        "recordedDate": "2026-07-24",
        "status": "authorized_not_consumed",
        "decisionBinding": {
            "path": DECISION_PATH,
            "rawSha256": sha256(decision_raw),
            "contentSha256": decision["contentBinding"]["sha256"],
            "requiredStatus": decision["status"],
        },
        "requestContract": {
            "requestCount": 32,
            "method": "GET",
            "host": PROXY_HOST,
            "port": 443,
            "resources": resources,
            "resourcesCanonicalSha256": decision["requestSet"]["canonicalSha256"],
            "directHttpsOnly": True,
            "tlsCertificateAndHostnameValidationRequired": True,
            "identityContentEncodingRequired": True,
            "acceptedStatusCode": 200,
            "requestBodyAllowed": False,
            "redirectAllowed": False,
            "ambientProxyAllowed": False,
            "alternateHostAllowed": False,
            "authenticationAllowed": False,
            "authorizationHeaderAllowed": False,
            "proxyAuthorizationHeaderAllowed": False,
            "cookieAllowed": False,
            "clientCertificateAllowed": False,
            "rangeHeaderAllowed": False,
            "queryOrFragmentAllowed": False,
            "retryResumeOrBackfillAllowed": False,
        },
        "oneUseContract": {
            "claimPath": CLAIM_PATH,
            "claimCreatedOExcl0600AndFsyncedBeforeDnsOrNetwork": True,
            "claimPersistsAfterSuccessFailureTimeoutOrUncertainty": True,
            "secondExecutionAllowed": False,
            "stagingPrefix": STAGING_PREFIX,
            "finalAcceptedPath": FINAL_ACCEPTED,
            "failureRetainsStaging": True,
        },
        "verificationContract": decision["verificationDesign"],
        "zipLimits": {
            "maximumEntryCount": MAX_ZIP_FILES,
            "maximumAggregateUncompressedBytes": MAX_ZIP_UNCOMPRESSED_BYTES,
            "maximumSingleEntryBytes": MAX_ZIP_FILE_BYTES,
            "maximumEntryNameBytes": MAX_ZIP_NAME_BYTES,
            "encryptedEntriesAllowed": False,
            "symlinksAllowed": False,
            "directoryEntriesAllowed": False,
            "duplicateNamesAllowed": False,
            "backslashAbsoluteDotOrDotDotNamesAllowed": False,
        },
        "absoluteResourceLimits": {
            "maximumRequestCount": 32,
            "maximumModResponseBodyBytes": MAX_MOD_BYTES,
            "maximumZipResponseBodyBytes": MAX_ZIP_BYTES,
            "maximumAggregateModResponseBodyBytes": MAX_AGGREGATE_MOD_BYTES,
            "maximumAggregateZipResponseBodyBytes": MAX_AGGREGATE_ZIP_BYTES,
            "maximumAggregateResponseBodyBytes": MAX_AGGREGATE_BYTES,
            "maximumHeaderBytesPerResponse": MAX_HEADER_BYTES,
            "perRequestDeadlineMilliseconds": PER_REQUEST_DEADLINE_MS,
            "wholeAttemptDeadlineMilliseconds": WHOLE_ATTEMPT_DEADLINE_MS,
            "absoluteWallTimersRequired": True,
        },
        "filesystemAuthority": {
            "claimWriteAuthorized": True,
            "ownerOnlyStagingWriteAuthorized": True,
            "verifiedModAndZipWriteAuthorized": True,
            "receiptFailureAndManifestWriteAuthorized": True,
            "atomicNoReplacePublicationRequired": True,
            "manifestWrittenLast": True,
            "newFileMode": "0600",
            "newDirectoryMode": "0700",
            "sourceExtractionAuthorized": False,
            "otherRepositoryWritesAuthorized": False,
        },
        "authority": {
            "wave3SourceAcquisitionAuthorizedOnce": True,
            "dnsTcpTlsHttpsToExactProxyAuthorized": True,
            "sourceExtractionAuthorized": False,
            "sourceLoadOrExecutionAuthorized": False,
            "compileAuthorized": False,
            "packageManagerAuthorized": False,
            "subprocessAuthorized": False,
            "gitOperationAuthorized": False,
            "deviceAuthorized": False,
            "deploymentAuthorized": False,
            "productRuntimeNetworkAuthorized": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        },
        "terminalContract": {
            "receiptPath": RECEIPT_PATH,
            "failurePath": FAILURE_PATH,
            "manifestPath": MANIFEST_PATH,
            "successAndFailureMutuallyExclusive": True,
            "failurePublishesFailureOnly": True,
            "manifestWrittenLast": True,
            "independentReadbackRequired": True,
        },
        "readerDocumentBinding": {
            "path": PERMIT_READER_PATH,
            "rawSha256": EXPECTED_PERMIT_READER_RAW,
        },
        "toolBindings": [
            {"path": path, "rawSha256": sha256(package_raw[path])}
            for path in (THIS_CHECKER_PATH, THIS_TESTS_PATH, RUNNER_PATH, RUNNER_TESTS_PATH)
        ],
        "runnerNormalizedSha256": EXPECTED_RUNNER_NORMALIZED_SHA256,
        "result": "exact_32_resource_one_use_acquisition_authorized_not_consumed",
        "nextAction": "execute_bound_wave3_source_acquisition_once",
    }


def package_raw(include_documents: bool) -> dict[str, bytes]:
    paths = [DECISION_READER_PATH, PERMIT_READER_PATH, THIS_CHECKER_PATH, THIS_TESTS_PATH, RUNNER_PATH, RUNNER_TESTS_PATH]
    if include_documents:
        paths += [DECISION_PATH, PERMIT_PATH]
    return {path: stable_read(path) for path in paths}


def evaluate(verify_disk: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    namespace_absent()
    raw = package_raw(verify_disk)
    require(sha256(raw[DECISION_READER_PATH]) == EXPECTED_DECISION_READER_RAW, "E_READER")
    require(sha256(raw[PERMIT_READER_PATH]) == EXPECTED_PERMIT_READER_RAW, "E_READER")
    decision = content_bound(decision_payload(raw))
    if verify_disk:
        verify_bound(raw[DECISION_PATH], decision, "E_DECISION")
        decision_raw = raw[DECISION_PATH]
    else:
        decision_raw = canonical_bytes(decision)
    permit = content_bound(permit_payload(decision, decision_raw, raw))
    if verify_disk:
        verify_bound(raw[PERMIT_PATH], permit, "E_PERMIT")
    namespace_absent()
    return {"decision": decision, "permit": permit}, {
        "documentType": "aetherlink.wave3-source-acquisition-package-check",
        "schemaVersion": "1.0",
        "status": "authorized_not_consumed",
        "validationPassed": True,
        "tupleCount": 16,
        "requestCount": 32,
        "claimExists": False,
        "networkUsed": False,
        "sourceAcquired": False,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


class Parser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise CheckError("E_ARGUMENT")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = Parser(add_help=False)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--print-decision", action="store_true")
        group.add_argument("--print-permit", action="store_true")
        args = parser.parse_args(argv)
        values, summary = evaluate(False if (args.print_decision or args.print_permit) else True)
        output = values["decision"] if args.print_decision else values["permit"] if args.print_permit else summary
        sys.stdout.buffer.write(canonical_bytes(output))
        return 0
    except CheckError as error:
        sys.stdout.buffer.write(canonical_bytes({
            "documentType": "aetherlink.wave3-source-acquisition-package-error",
            "schemaVersion": "1.0", "status": "failed_closed", "failureCode": error.code,
            "networkAuthorized": False, "fileWriteAuthorized": False,
            "externalAuthenticationRequired": False, "userActionRequired": False,
        }))
        return 1
    except Exception:
        sys.stdout.buffer.write(canonical_bytes({
            "documentType": "aetherlink.wave3-source-acquisition-package-error",
            "schemaVersion": "1.0", "status": "failed_closed", "failureCode": "E_INTERNAL",
            "networkAuthorized": False, "fileWriteAuthorized": False,
            "externalAuthenticationRequired": False, "userActionRequired": False,
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
