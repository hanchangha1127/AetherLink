#!/usr/bin/env python3
"""Check current docs for stale product-boundary wording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import runpy
import sys

if __package__:
    from script.check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )
else:
    from check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )


ROOT = Path(__file__).resolve().parents[1]
PHYSICAL_QR_OBSERVATION_MANIFEST = (
    ROOT / "docs/evidence/physical-qr-pairing-20260719.json"
)
LOCAL_RELEASE_ID = "aetherlink-1.0.0+1-local-v1"
LOCAL_RELEASE_DOC = ROOT / "docs/releases/1.0.0-build-1-local-v1.md"
LOCAL_RELEASE_ARCHIVE_DIR = ROOT / "dist/releases" / LOCAL_RELEASE_ID
LOCAL_RELEASE_LEDGER = ROOT / "release/version-ledger.tsv"
LOCAL_RELEASE_G0_DECISION = ROOT / "docs/v1/g0/decision-v1.json"
LOCAL_RELEASE_EXPECTED_ZIP_SIZE = 164_775_328
LOCAL_RELEASE_EXPECTED_ZIP_SHA256 = (
    "1944238784f7235b93e5e5889fdc903137ca6229bc39c870b5935cf3489c89ac"
)
LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE = 10_242
LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256 = (
    "60baac0fa0567d3929370d401475d5a773d7541025017e68cc4b06def1b4ae8a"
)
LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT = 234
LOCAL_RELEASE_EXPECTED_SOURCE_SHA256 = (
    "938b95c38c106aae73ecc7a8899364598780c21545bfcb73e5806befc6ac0282"
)
LOCAL_RELEASE_EXPECTED_SOURCE_HEAD = (
    "cde05acbaab0b77af6a3d87ea5c926f08597f7e6"
)
LOCAL_RELEASE_EXPECTED_MEMBER_COUNT = 25
LOCAL_RELEASE_EXPECTED_MACOS_UUID = "6B5402D4-F853-3A12-AD51-94C892EC7BD5"
LOCAL_RELEASE_EXPECTED_MEMBERS = {
    "android/apk/app-release-unsigned.apk": (
        9_568_738,
        "10a4e7f93786d24c519c53d59b383f1b875a4ced3e5a981603690e2ba63654e7",
    ),
    "android/bundle/app-release.aab": (
        10_658_234,
        "dec9eb9cf1397ccc58ddd57d7a7497c35966016fe78a96c8784592ec274b16e6",
    ),
    "android/mapping/mapping.txt": (
        71_646_798,
        "cb41d4afe7c4f5c6e99640e11a41cc1d624652e8c8629ff3a39a70128c9ef1f9",
    ),
    "macos/AetherLink.app/Contents/MacOS/AetherLink": (
        18_171_648,
        "f63193ff991fa7743dd74b2af0434006c842a864007a0f499abb8c590d899f59",
    ),
    "macos/AetherLink.dSYM/Contents/Resources/DWARF/AetherLink": (
        31_535_883,
        "b313e20ff5727b80f268250de72d3bcc305e470123a588137a48f5aaba715eab",
    ),
}
LOCAL_RELEASE_TRANSITION_FIXTURE_START = (
    "<!-- aetherlink-release-transition-fixture-v1:start -->"
)
LOCAL_RELEASE_TRANSITION_FIXTURE_END = (
    "<!-- aetherlink-release-transition-fixture-v1:end -->"
)
LOCAL_RELEASE_PROVIDER_FIXTURE_START = (
    "<!-- aetherlink-provider-compatibility-fixture-v1:start -->"
)
LOCAL_RELEASE_PROVIDER_FIXTURE_END = (
    "<!-- aetherlink-provider-compatibility-fixture-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START = (
    "<!-- aetherlink-ollama-exact-version-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END = (
    "<!-- aetherlink-ollama-exact-version-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER = (
    ROOT / "script/run_ollama_compatibility_matrix.py"
)
LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE = {
    "android": {
        "developmentBaseline": "0.1.0+1-debug",
        "inPlaceUpgradeSupported": False,
        "requiredAction": "clean-install-and-fresh-pair",
        "sourceApplicationId": "com.localagentbridge.android",
        "stateMigrationSupported": False,
    },
    "currentRelease": {
        "buildNumber": 1,
        "marketingVersion": "1.0.0",
        "releaseId": LOCAL_RELEASE_ID,
    },
    "evidenceBoundary": "policy-fixture-only-no-install-or-state-migration-executed",
    "fixtureId": "aetherlink-first-production-lineage-transition-v1",
    "macos": {
        "developmentBaseline": "pre-production-local-ad-hoc",
        "inPlaceUpgradeSupported": False,
        "requiredAction": "clean-install-and-fresh-pair",
        "sourceBundleId": "dev.aetherlink.companion",
        "stateMigrationSupported": False,
    },
    "nMinusOne": {
        "compatibleReleaseId": None,
        "status": "unproven-no-prior-production-release",
        "upgradePathTested": False,
    },
    "productionPredecessor": None,
    "schemaVersion": 1,
}
LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE = {
    "evidenceBoundary": (
        "exact-version-isolated-ollama-adapter-health-empty-catalog-restart-"
        "plus-focused-default-tests-no-live-chat-or-model-lifecycle"
    ),
    "fixtureId": "aetherlink-provider-compatibility-baseline-v1",
    "lmStudio": {
        "access": "runtime_host_only",
        "currentCandidate": {
            "build": 1,
            "qualified": False,
            "releaseDate": "2026-07-22",
            "schemaSmokeObserved": False,
            "version": "0.4.20",
        },
        "localObservation": {
            "channel": "beta",
            "cliCommit": "6041ae0",
            "fallbackModelsEndpoint": {
                "arrayField": "data",
                "httpStatus": 200,
                "objectField": "list",
                "path": "/v1/models",
            },
            "nativeModelsEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/v1/models",
            },
            "version": "0.4.17-beta+3",
        },
        "minimumSupportedVersion": None,
        "officialSource": "https://lmstudio.ai/changelog",
        "previousCandidate": {
            "build": 2,
            "qualified": False,
            "releaseDate": "2026-07-07",
            "schemaSmokeObserved": False,
            "version": "0.4.19",
        },
        "providerId": "lm_studio",
        "releasePolicy": (
            "exact_rc_current_stable_and_previous_verified_versions"
        ),
        "supportStatus": "unresolved-no-minimum-or-full-qualification",
    },
    "ollama": {
        "access": "runtime_host_only",
        "currentCandidate": {
            "darwinArchiveSha256": (
                "5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"
            ),
            "darwinArchiveUrl": (
                "https://github.com/ollama/ollama/releases/download/"
                "v0.32.5/ollama-darwin.tgz"
            ),
            "isolatedAdapterSmoke": {
                "coldStartPassed": True,
                "emptyCatalogPassed": True,
                "restartPassed": True,
                "stoppedEndpointUnavailable": True,
            },
            "qualified": False,
            "releaseDate": "2026-07-27",
            "schemaSmokeObserved": True,
            "version": "0.32.5",
        },
        "localObservation": {
            "catalogEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/tags",
            },
            "channel": "stable",
            "runningEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/ps",
            },
            "version": "0.32.4",
            "versionEndpoint": {
                "httpStatus": 200,
                "path": "/api/version",
                "versionField": "version",
            },
        },
        "minimumSupportedVersion": None,
        "officialSource": "https://github.com/ollama/ollama/releases",
        "previousCandidate": {
            "darwinArchiveSha256": (
                "15383493225d5e7e7fda052dc103ab4d2835a22eabb41655f1d6302c6d1577bc"
            ),
            "darwinArchiveUrl": (
                "https://github.com/ollama/ollama/releases/download/"
                "v0.32.4/ollama-darwin.tgz"
            ),
            "isolatedAdapterSmoke": {
                "coldStartPassed": True,
                "emptyCatalogPassed": True,
                "restartPassed": True,
                "stoppedEndpointUnavailable": True,
            },
            "qualified": False,
            "releaseDate": "2026-07-25",
            "schemaSmokeObserved": True,
            "version": "0.32.4",
        },
        "providerId": "ollama",
        "releasePolicy": (
            "exact_rc_current_stable_and_previous_verified_versions"
        ),
        "supportStatus": "unresolved-no-minimum-or-full-qualification",
    },
    "recordedDate": "2026-07-28",
    "schemaVersion": 1,
    "tests": {
        "isolatedOllamaExactVersion": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "lmStudio": {
            "executed": 71,
            "failures": 0,
            "passed": 70,
            "skipped": 1,
        },
        "ollama": {
            "executed": 73,
            "failures": 0,
            "passed": 71,
            "skipped": 2,
        },
        "testKind": "focused-default-plus-opt-in-isolated-exact-version",
    },
}


class DuplicateJSONKeyError(ValueError):
    pass


def reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


@dataclass(frozen=True)
class DocsRule:
    name: str
    pattern: re.Pattern[str]
    guidance: str


@dataclass(frozen=True)
class DocsContract:
    name: str
    required_patterns: tuple[re.Pattern[str], ...]
    guidance: str


@dataclass(frozen=True)
class DocsFileContract:
    name: str
    target: str
    required_patterns: tuple[re.Pattern[str], ...]
    guidance: str


RULES = (
    DocsRule(
        "companion-runtime",
        re.compile(r"\bcompanion runtime\b", re.IGNORECASE),
        "Use AetherLink Runtime, trusted runtime, or runtime host.",
    ),
    DocsRule(
        "runtime-server-hybrid",
        re.compile(r"\bruntime/server\b", re.IGNORECASE),
        "Use runtime host, trusted runtime, or runtime target.",
    ),
    DocsRule(
        "server-targets",
        re.compile(r"\bserver targets?\b", re.IGNORECASE),
        "Use runtime targets unless describing an external infrastructure service.",
    ),
    DocsRule(
        "finished-e2e-transport-claim",
        re.compile(r"\bauthenticated end-to-end encrypted session\b", re.IGNORECASE),
        "Do not imply production transport encryption is complete.",
    ),
    DocsRule(
        "desktop-host-copy",
        re.compile(r"\b(this Mac|Mac alone|this computer|paired computer)\b", re.IGNORECASE),
        "Use runtime host wording so docs stay OS-neutral.",
    ),
    DocsRule(
        "runtime-companion-label",
        re.compile(r"\bAetherLink Runtime companion\b", re.IGNORECASE),
        "Use AetherLink Runtime.",
    ),
    DocsRule(
        "visible-app-language-system-option",
        re.compile(
            r"\b(?:language selector|app-language|app language|language support)\b.*"
            r"\bSystem/Device language\b",
            re.IGNORECASE,
        ),
        "Use the localized Follow system language setting name rather than the stale System/Device language label.",
    ),
    DocsRule(
        "stale-remote-route-diagnostics-title",
        re.compile(r"\bRemote Route Diagnostics\b", re.IGNORECASE),
        "Use Advanced Connection Setup or Connection Setup to match the current runtime UI.",
    ),
    DocsRule(
        "stale-route-host-copy",
        re.compile(r"\broute host(?:/port| and port)?\b", re.IGNORECASE),
        "Use connection address and port.",
    ),
)


HYGIENE_TARGETS = (
    "README.md",
    "apps/android/README.md",
    "apps/macos/README.md",
    "docs/architecture.md",
    "docs/connection-overlay.md",
    "docs/handoff.md",
    "docs/mvp-v0.1.md",
    "docs/protocol.md",
    "docs/qa-evidence.md",
    "docs/releases/1.0.0-build-1-local-v1.md",
    "docs/roadmap.md",
    "docs/security.md",
    "examples/README.md",
)

CONTRACT_TARGETS = tuple(
    target for target in HYGIENE_TARGETS if target != "docs/handoff.md"
)

CONTRACTS = (
    DocsContract(
        "runtime-mediated-backends",
        (
            re.compile(r"\bclient\b.*\b(?:must not|never)\b.*\b(?:call|connects?\s+directly\s+to)\b.*\bOllama\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bclient\b.*\b(?:must not|never)\b.*\b(?:call|connects?\s+directly\s+to)\b.*\bLM Studio\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bAetherLink Runtime\b|\bruntime host\b", re.IGNORECASE),
        ),
        "Docs must preserve the boundary that clients talk to AetherLink Runtime, never directly to Ollama or LM Studio.",
    ),
    DocsContract(
        "qr-overlay-route-model",
        (
            re.compile(r"\bQR-only\b|\bQR\b.*\b(?:pair|route|refresh)", re.IGNORECASE | re.DOTALL),
            re.compile(r"\broute\.refresh\b", re.IGNORECASE),
            re.compile(r"\bprivate overlay\b|\bremote P2P\b|\bNAT traversal\b", re.IGNORECASE),
            re.compile(r"\brelay_secret\b.*\brelay_expires_at\b.*\brelay_nonce\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must describe QR-first pairing/route refresh and remote overlay or relay material instead of fixed-IP reconnect.",
    ),
    DocsContract(
        "runtime-owned-chat-history",
        (
            re.compile(r"\bruntime-owned\b.*\bchat\b|\bchat\b.*\bruntime-owned\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bchat\.sessions\.list\b", re.IGNORECASE),
            re.compile(r"\bchat\.messages\.list\b", re.IGNORECASE),
            re.compile(r"\b(?:redact|redacted|omits?)\b.*\bmessage bodies\b|\bmessage bodies\b.*\b(?:redact|redacted|omits?)\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must keep runtime-owned chat history and client-cache redaction explicit.",
    ),
    DocsContract(
        "five-language-locale-handoff",
        (
            re.compile(r"\bEnglish, Korean, Japanese, Simplified Chinese, and French\b", re.IGNORECASE),
            re.compile(r"\bchat\.send\.locale\b|\blocale handoff\b|\bruntime request locale\b", re.IGNORECASE),
        ),
        "Docs must keep the five-language launch set and runtime locale handoff visible.",
    ),
    DocsContract(
        "runtime-mediated-memory-embedding",
        (
            re.compile(r"\bmemory\b.*\bruntime-(?:owned|mediated)|\bruntime-(?:owned|mediated)\b.*\bmemory\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bembedding models?\b.*\bseparate(?:ly)?\b|\bseparate\b.*\bembedding models?\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bselected embedding model\b|\bMemory indexing model\b", re.IGNORECASE),
        ),
        "Docs must keep memory runtime-mediated and embedding model selection separate from chat model selection.",
    ),
    DocsContract(
        "runtime-mediated-attachments",
        (
            re.compile(r"\battachments?\b.*\bruntime-(?:mediated|side)\b|\bruntime-(?:mediated|side)\b.*\battachments?\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bvision\b.*\bgating\b|\bgating\b.*\bvision\b|\bimage/vision gating\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bdocument ingestion\b|\bdocument attachments?\b", re.IGNORECASE),
        ),
        "Docs must distinguish current runtime-mediated attachment support from remaining physical QA and future ingestion hardening.",
    ),
    DocsContract(
        "future-tools-runtime-only",
        (
            re.compile(r"\bMCP\b.*\b(?:roadmap|future|not v0\.1)\b|\b(?:roadmap|future|not v0\.1)\b.*\bMCP\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bweb search\b.*\b(?:roadmap|future|not v0\.1)\b|\b(?:roadmap|future|not v0\.1)\b.*\bweb search\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\b(?:MCP|web search)\b.*\b(?:AetherLink Runtime|runtime host)\b|\b(?:AetherLink Runtime|runtime host)\b.*\b(?:MCP|web search)\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bclient\b.*\b(?:does not|must not|never)\b.*\b(?:MCP|web search)\b|\b(?:MCP|web search)\b.*\bclient\b.*\b(?:does not|must not|never)\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must keep MCP and web search as future runtime-side features, never v0.1 client capabilities.",
    ),
)

FILE_CONTRACTS = (
    DocsFileContract(
        "local-release-qualification-boundary",
        "docs/releases/1.0.0-build-1-local-v1.md",
        (
            re.compile(
                r"\bStatus:\s*local release-engineering candidate,\s*not a production release\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bAndroid Debug\b.*\b0\.1\.0\+1\b.*\bnon-migratable\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bN/N-1\b.*\bnot yet qualified\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bAndroid channel\b.*\brollback\b.*\bhigher\s+`versionCode`",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bcurrent\s+or\s+immediately\s+previous\b.*\bsigned DMG\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\b1944238784f7235b93e5e5889fdc903137ca6229bc39c870b5935cf3489c89ac\b"
            ),
            re.compile(
                r"\b60baac0fa0567d3929370d401475d5a773d7541025017e68cc4b06def1b4ae8a\b"
            ),
        ),
        "The local release record must retain its exact artifact identity, non-production boundary, transition limits, and rollback posture.",
    ),
    DocsFileContract(
        "canonical-session-handoff",
        "docs/handoff.md",
        (
            re.compile(r"\bcanonical first document\b", re.IGNORECASE),
            re.compile(r"\bintentionally dirty\b.*\bworktree\b|\bworktree\b.*\bintentionally dirty\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bAndroid device state at handoff:\s*disconnected\b", re.IGNORECASE),
            re.compile(r"\bphysical\b.*\bcamera scan\b.*\bNo URI or deep-link injection\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bPairingQr\b.*\bBonjourDiscovery\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\blocal_diagnostic\b.*\brelease\b.*\bremote-required\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bCurrent Truth Versus Historical Evidence\b", re.IGNORECASE),
            re.compile(r"\bUI Callback Wiring Matrix\b", re.IGNORECASE),
            re.compile(r"\bPairingView\b.*\bmain\b.*\brequestPairingForUserInterface\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bPairing\b.*\bnested Connection Recovery\b.*\brequestRemotePairingForUserInterface\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bDebug And Release Evidence Matrix\b", re.IGNORECASE),
            re.compile(r"\bphysical-qr-pairing-20260719\.json\b", re.IGNORECASE),
            re.compile(r"\bprogress-v8\.json\b.*\bdecision-v6\.json\b.*\bhandoff-v9\.json\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bimplementationAuthorized=false\b.*\bruntimeNetworkIOAllowed=false\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bNot Yet Proven\b", re.IGNORECASE),
            re.compile(r"\bP2P/NAT\b.*\bPhase B\b.*\bproduction\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bGPT-5\.6 Sol\b", re.IGNORECASE),
            re.compile(r"\bHandoff Maintenance Rule\b", re.IGNORECASE),
        ),
        "docs/handoff.md must remain a current, bounded, and executable continuation contract rather than a stale narrative snapshot.",
    ),
    DocsFileContract(
        "roadmap-qr-history-supersession",
        "docs/roadmap.md",
        (
            re.compile(r"\bReading rule:.*\bHistorical Checkpoint\b.*\bcannot override\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bHistorical Checkpoint: macOS Pairing QR Recovery And Bounded Route Preparation \(Superseded\)", re.IGNORECASE),
            re.compile(r"\bProduct result at that checkpoint:", re.IGNORECASE),
            re.compile(r"\bHistorical Checkpoint: Cross-Platform Readiness UI Pass \(Superseded\)", re.IGNORECASE),
            re.compile(r"\blater physical debug result\b.*\bdoes not\b.*\bhistorical aggregate\b", re.IGNORECASE | re.DOTALL),
        ),
        "Historical QR and readiness checkpoints must remain explicitly superseded by the current handoff and roadmap sections.",
    ),
    DocsFileContract(
        "protocol-locale-contract",
        "docs/protocol.md",
        (
            re.compile(r"\bchat\.send\.locale\b", re.IGNORECASE),
            re.compile(r"\bEnglish, Korean, Japanese, Simplified Chinese, and French\b", re.IGNORECASE),
        ),
        "docs/protocol.md must directly define the runtime locale handoff and the five-language launch set.",
    ),
    DocsFileContract(
        "protocol-runtime-memory-client-boundary",
        "docs/protocol.md",
        (
            re.compile(r"\bCurrent clients\b.*\b(?:should not|do not)\b.*\bcached memory\b.*\bchat\.send\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bCompatibility clients?\b", re.IGNORECASE),
            re.compile(r"\bruntime-owned memory store\b|\bruntime-owned memory\b", re.IGNORECASE),
        ),
        "docs/protocol.md must distinguish current client behavior from stale compatibility memory stripping.",
    ),
    DocsFileContract(
        "readme-cross-platform-language-verification",
        "README.md",
        (
            re.compile(r"\bAndroid and macOS five-language app-language verification\b", re.IGNORECASE),
            re.compile(r"\bchat\.send\.locale\b", re.IGNORECASE),
        ),
        "README.md must keep cross-platform language verification and chat.send.locale handoff visible outside historical progress logs.",
    ),
    DocsFileContract(
        "readme-no-device-quality-caveats",
        "README.md",
        (
            re.compile(r"\bno-device gate\b", re.IGNORECASE),
            re.compile(r"\bdoes not require a connected phone\b", re.IGNORECASE),
            re.compile(r"\bphysical Android rendering\b", re.IGNORECASE),
            re.compile(r"\bTalkBack\b.*\bVoiceOver\b|\bVoiceOver\b.*\bTalkBack\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\boptical/camera QR\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat or cancel\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "README.md must keep no-device quality caveats explicit for physical rendering, screen-reader traversal, optical QR, live provider chat/cancel, and real different-network connectivity.",
    ),
    DocsFileContract(
        "qa-current-rule-no-device-quality-caveats",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bCurrent Rule\b", re.IGNORECASE),
            re.compile(r"\bNo-device evidence does not prove\b", re.IGNORECASE),
            re.compile(r"\bphysical Android rendering\b", re.IGNORECASE),
            re.compile(r"\bTalkBack\b.*\bVoiceOver\b|\bVoiceOver\b.*\bTalkBack\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\boptical/camera QR\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat/cancel\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md Current Rule must keep no-device quality caveats explicit before historical evidence entries.",
    ),
    DocsFileContract(
        "qa-owner-device-scoping-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Runtime Owner-Device History And Memory Scoping\b", re.IGNORECASE),
            re.compile(r"\bowner_device_id\b", re.IGNORECASE),
            re.compile(r"\btestAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeMemoryStoreScopesEntriesByOwnerDevice\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep the latest runtime history/memory owner-device scoping proof visible.",
    ),
    DocsFileContract(
        "qa-android-archived-chat-composer-cleanup",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Archived Chat Composer Cleanup\b", re.IGNORECASE),
            re.compile(r"\barchiveActiveChatClearsNoActiveDraftAndPendingAttachments\b", re.IGNORECASE),
            re.compile(r"\barchiveAllChatsClearsNoActiveDraftAndPendingAttachments\b", re.IGNORECASE),
            re.compile(r"\bsanitizedDropsArchivedSessionComposerDrafts\b", re.IGNORECASE),
            re.compile(r"\bAndroid transient attachment cleanup on chat lifecycle exits\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep archived chat composer cleanup proof visible.",
    ),
    DocsFileContract(
        "qa-android-runtime-transcript-loading-state",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Runtime Transcript Loading State\b", re.IGNORECASE),
            re.compile(r"\bchatComposerHintExplainsActiveTranscriptLoadingLockout\b", re.IGNORECASE),
            re.compile(r"\bopeningRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShowsLocalizedLoadingStateWhileRuntimeTranscriptLoads\b", re.IGNORECASE),
            re.compile(r"\bAndroid runtime transcript loading state\b", re.IGNORECASE),
            re.compile(r"\bAndroid runtime transcript lifecycle mutation lockout\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android runtime transcript loading proof visible.",
    ),
    DocsFileContract(
        "qa-macos-route-material-redaction",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Route Material Diagnostic Redaction\b", re.IGNORECASE),
            re.compile(r"\btestActivityTechnicalDetailsRedactRouteSecrets\b", re.IGNORECASE),
            re.compile(r"\btestRouteDiagnosticDisclosureRedactsSensitiveDetails\b", re.IGNORECASE),
            re.compile(r"\bmacOS route material diagnostic redaction\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep macOS route material diagnostic redaction proof visible.",
    ),
    DocsFileContract(
        "progress-macos-thinking-runtime-history-evidence",
        "docs/progress.md",
        (
            re.compile(r"\bmacOS Thinking Copy And Sidebar Header Accessibility\b", re.IGNORECASE),
            re.compile(r"\bRuntime History Inspector transcript reasoning\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep macOS Runtime History Thinking/reasoning evidence visible.",
    ),
    DocsFileContract(
        "qa-macos-thinking-runtime-history-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Thinking Copy And Sidebar Header Accessibility\b", re.IGNORECASE),
            re.compile(r"\bRuntime History Inspector transcript reasoning\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep macOS Runtime History Thinking/reasoning proof visible.",
    ),
    DocsFileContract(
        "progress-android-preference-system-detail-guard",
        "docs/progress.md",
        (
            re.compile(r"\bAndroid Appearance System Detail Polish\b", re.IGNORECASE),
            re.compile(r"\bR\.string\.appearance_system_detail\b", re.IGNORECASE),
            re.compile(r"\blanguage_follow_system_detail\b", re.IGNORECASE),
            re.compile(r"\bAndroid appearance system detail copy\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep Android Settings system appearance/language detail guard evidence visible.",
    ),
    DocsFileContract(
        "qa-android-preference-system-detail-guard",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Appearance System Detail Polish\b", re.IGNORECASE),
            re.compile(r"\bsettingsPreferenceRowsExposeSelectedStateToAccessibility\b", re.IGNORECASE),
            re.compile(r"\blanguage_follow_system_detail\b", re.IGNORECASE),
            re.compile(r"\bAndroid Settings Appearance\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android Settings system appearance/language detail proof visible.",
    ),
    DocsFileContract(
        "progress-android-static-thinking-state-evidence",
        "docs/progress.md",
        (
            re.compile(r"\bAndroid Static Thinking Accessibility\b", re.IGNORECASE),
            re.compile(r"\bassistant_reasoning_state_shown\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\bAndroid short reasoning static accessibility state\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep Android short Thinking static accessibility evidence visible.",
    ),
    DocsFileContract(
        "qa-android-static-thinking-state-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Static Thinking Accessibility\b", re.IGNORECASE),
            re.compile(r"\bassistant_reasoning_state_shown\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\bAndroid short reasoning static accessibility state\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android short Thinking static accessibility proof visible.",
    ),
    DocsFileContract(
        "connection-overlay-production-bootstrap-verifier",
        "docs/connection-overlay.md",
        (
            re.compile(r"\bscript/verify_pairing_qr\.swift\b", re.IGNORECASE),
            re.compile(r"--require-production-bootstrap\b", re.IGNORECASE),
            re.compile(r"\bruntime_public_key\b.*\broute_token\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"--require-relay-route\b", re.IGNORECASE),
            re.compile(r"--forbid-direct-endpoint\b", re.IGNORECASE),
        ),
        "docs/connection-overlay.md must document the QR verifier flags that prove production bootstrap fields, relay route material, and no direct endpoint fallback.",
    ),
    DocsFileContract(
        "protocol-product-qr-bootstrap-contract",
        "docs/protocol.md",
        (
            re.compile(r"\bNormal product client scans\b.*\bruntime_public_key\b.*\broute_token\b.*\bremote route material\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bIdentity-only QR\b.*\bcompatibility or diagnostic\b.*\bnormal product scan path\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bnormal product QR scans require\b.*\bruntime_public_key\b", re.IGNORECASE | re.DOTALL),
        ),
        "docs/protocol.md must state that normal product QR scans require runtime public key, route token, and remote route material while identity-only QR remains diagnostic/compatibility only.",
    ),
    DocsFileContract(
        "roadmap-no-device-live-proof-split",
        "docs/roadmap.md",
        (
            re.compile(r"\bContinue expanding smoke tests while separating no-device gate coverage from live proof gaps\b", re.IGNORECASE),
            re.compile(r"\bNamed no-device/default-gate coverage currently includes\b", re.IGNORECASE),
            re.compile(r"\bLive/physical proof that remains separate\b", re.IGNORECASE),
            re.compile(r"\bphysical Android QR scan\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat/cancel\b", re.IGNORECASE),
            re.compile(r"\bproduction relay allocation\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "docs/roadmap.md must separate named no-device/default-gate coverage from live physical or production proof gaps.",
    ),
)


PROGRESS_DOC = ROOT / "docs/progress.md"
QA_EVIDENCE_DOC = ROOT / "docs/qa-evidence.md"


def target_files() -> list[Path]:
    return [path for path in (ROOT / target for target in HYGIENE_TARGETS) if path.is_file()]


def contract_text() -> str:
    chunks: list[str] = []
    for target in CONTRACT_TARGETS:
        path = ROOT / target
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def file_contract_text(target: str) -> str:
    path = ROOT / target
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def embedded_json_fixture_body(
    document_text: str,
    *,
    start_marker: str,
    end_marker: str,
    fixture_label: str,
) -> tuple[str | None, list[str]]:
    pattern = re.compile(
        re.escape(start_marker)
        + r"\n```json\n(?P<body>.*?)\n```\n"
        + re.escape(end_marker),
        re.DOTALL,
    )
    matches = list(pattern.finditer(document_text))
    if (
        len(matches) != 1
        or document_text.count(start_marker) != 1
        or document_text.count(end_marker) != 1
    ):
        return (
            None,
            [
                "docs/releases/1.0.0-build-1-local-v1.md: expected exactly "
                f"one canonical {fixture_label} fixture block."
            ],
        )

    fixture_body = matches[0].group("body")

    try:
        json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, DuplicateJSONKeyError) as error:
        return (
            None,
            [
                "docs/releases/1.0.0-build-1-local-v1.md: invalid "
                f"{fixture_label} fixture JSON: {error}"
            ],
        )

    return fixture_body, []


def local_release_transition_fixture_failures(
    document_text: str,
) -> list[str]:
    failures: list[str] = []
    fixture_body, parse_failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_TRANSITION_FIXTURE_START,
        end_marker=LOCAL_RELEASE_TRANSITION_FIXTURE_END,
        fixture_label="release-transition",
    )
    if fixture_body is None:
        return parse_failures

    expected_body = json.dumps(
        LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-1-local-v1.md: release-transition "
            "fixture must match the canonical first-lineage schema, exact "
            "values, JSON types, and key order."
        )

    try:
        ledger_bytes = LOCAL_RELEASE_LEDGER.read_bytes()
        ledger_entries = parse_release_version_ledger(ledger_bytes)
        current_entry = ledger_entries[-1]
        ledger_current = {
            "buildNumber": current_entry.build_number,
            "marketingVersion": current_entry.marketing_version,
            "releaseId": (
                f"aetherlink-{current_entry.marketing_version}"
                f"+{current_entry.build_number}-local-v1"
            ),
        }
    except (OSError, LedgerError) as error:
        failures.append(
            "release/version-ledger.tsv: cannot cross-check local release "
            f"transition fixture: {error}"
        )
    else:
        if json.dumps(
            ledger_current,
            sort_keys=True,
        ) != json.dumps(
            LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"],
            sort_keys=True,
        ):
            failures.append(
                "release/version-ledger.tsv: current entry differs from the "
                "local release transition fixture."
            )

    try:
        g0 = json.loads(
            LOCAL_RELEASE_G0_DECISION.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        g0_projection = {
            "androidCurrentApplicationId": (
                g0["releasePolicy"]["android"]["currentApplicationId"]
            ),
            "androidDebugTransition": (
                g0["releasePolicy"]["android"]["currentDebugDataMigration"]
            ),
            "androidProductionApplicationId": (
                g0["releasePolicy"]["android"]["productionApplicationId"]
            ),
            "macosCurrentBundleId": (
                g0["releasePolicy"]["macos"]["currentBundleId"]
            ),
            "macosProductionBundleId": (
                g0["releasePolicy"]["macos"]["productionBundleId"]
            ),
            "marketingVersion": g0["productScope"]["releaseVersion"],
            "policyMarketingVersion": (
                g0["releasePolicy"]["versioning"]["marketingVersion"]
            ),
            "wireCompatibility": (
                g0["releasePolicy"]["compatibility"]["wireAndService"]
            ),
        }
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
        KeyError,
        TypeError,
    ) as error:
        failures.append(
            "docs/v1/g0/decision-v1.json: cannot cross-check local release "
            f"transition fixture: {error}"
        )
    else:
        expected_g0_projection = {
            "androidCurrentApplicationId": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["android"][
                    "sourceApplicationId"
                ]
            ),
            "androidDebugTransition": (
                "unsupported_clean_install_and_fresh_pair_required"
            ),
            "androidProductionApplicationId": None,
            "macosCurrentBundleId": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["macos"][
                    "sourceBundleId"
                ]
            ),
            "macosProductionBundleId": None,
            "marketingVersion": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"][
                    "marketingVersion"
                ]
            ),
            "policyMarketingVersion": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"][
                    "marketingVersion"
                ]
            ),
            "wireCompatibility": "n_and_n_minus_1",
        }
        if json.dumps(
            g0_projection,
            sort_keys=True,
        ) != json.dumps(
            expected_g0_projection,
            sort_keys=True,
        ):
            failures.append(
                "docs/v1/g0/decision-v1.json: non-security release version, "
                "identity, migration, or compatibility fields differ from "
                "the local transition fixture."
            )

    return failures


def local_release_provider_fixture_failures(
    document_text: str,
) -> list[str]:
    failures: list[str] = []
    fixture_body, parse_failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_PROVIDER_FIXTURE_START,
        end_marker=LOCAL_RELEASE_PROVIDER_FIXTURE_END,
        fixture_label="provider-compatibility",
    )
    if fixture_body is None:
        return parse_failures

    expected_body = json.dumps(
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-1-local-v1.md: "
            "provider-compatibility fixture must match the canonical "
            "recorded-date schema, exact values, JSON types, and key order."
        )

    try:
        g0 = json.loads(
            LOCAL_RELEASE_G0_DECISION.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        providers = g0["productScope"]["providers"]
        if not isinstance(providers, list):
            raise TypeError("productScope.providers must be an array")
        g0_projection = sorted(
            (
                {
                    "access": provider["access"],
                    "minimumSupportedVersion": (
                        provider["minimumSupportedVersion"]
                    ),
                    "providerId": provider["id"],
                    "releasePolicy": provider["releasePolicy"],
                }
                for provider in providers
            ),
            key=lambda provider: provider["providerId"],
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
        KeyError,
        TypeError,
    ) as error:
        failures.append(
            "docs/v1/g0/decision-v1.json: cannot cross-check local "
            f"provider-compatibility fixture: {error}"
        )
    else:
        expected_projection = sorted(
            (
                {
                    "access": provider["access"],
                    "minimumSupportedVersion": (
                        provider["minimumSupportedVersion"]
                    ),
                    "providerId": provider["providerId"],
                    "releasePolicy": provider["releasePolicy"],
                }
                for provider in (
                    LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"],
                    LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["lmStudio"],
                )
            ),
            key=lambda provider: provider["providerId"],
        )
        if json.dumps(g0_projection, sort_keys=True) != json.dumps(
            expected_projection,
            sort_keys=True,
        ):
            failures.append(
                "docs/v1/g0/decision-v1.json: non-security provider IDs, "
                "runtime-host access, minimum versions, or release policies "
                "differ from the local provider-compatibility fixture."
            )

    return failures


def local_release_ollama_runner_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START,
        end_marker=LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END,
        fixture_label="ollama-exact-version-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: missing exact-version runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        runner_id = runner["RUNNER_ID"]
        recorded_date = runner["RECORDED_DATE"]
        evidence_boundary = runner["EVIDENCE_BOUNDARY"]
        candidates = runner["EXACT_CANDIDATES"]
        live_test_filter = runner["LIVE_TEST_FILTER"]
        default_port = runner["DEFAULT_OLLAMA_PORT"]
        if not isinstance(runner_id, str) or not runner_id:
            raise TypeError("RUNNER_ID must be a non-empty string")
        if not isinstance(recorded_date, str) or not recorded_date:
            raise TypeError("RECORDED_DATE must be a non-empty string")
        if not isinstance(evidence_boundary, str) or not evidence_boundary:
            raise TypeError("EVIDENCE_BOUNDARY must be a non-empty string")
        if type(candidates) is not tuple or len(candidates) != 2:
            raise TypeError("EXACT_CANDIDATES must contain exactly two rows")
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionEmptyCatalogCompatibility"
        ):
            raise ValueError("LIVE_TEST_FILTER differs from the canonical test")
        if type(default_port) is not int or default_port != 11_434:
            raise ValueError("DEFAULT_OLLAMA_PORT differs from 11434")

        versions: list[dict[str, object]] = []
        for candidate in candidates:
            if type(candidate) is not dict:
                raise TypeError("candidate rows must be objects")
            archive_sha256 = candidate["archiveSha256"]
            archive_url = candidate["archiveUrl"]
            version = candidate["version"]
            if not all(
                isinstance(value, str) and value
                for value in (archive_sha256, archive_url, version)
            ):
                raise TypeError("candidate strings must be non-empty")
            versions.append(
                {
                    "archiveSha256": archive_sha256,
                    "archiveUrl": archive_url,
                    "coldStart": {
                        "adapterTestPassed": True,
                        "endpointUnavailableAfterStop": True,
                    },
                    "restart": {
                        "adapterTestPassed": True,
                        "endpointUnavailableAfterStop": True,
                    },
                    "testRuns": 2,
                    "version": version,
                }
            )
        expected_fixture = {
            "evidenceBoundary": evidence_boundary,
            "fixtureId": runner_id,
            "recordedDate": recorded_date,
            "schemaVersion": 1,
            "versions": versions,
        }
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            f"cannot derive canonical runner fixture: {error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-1-local-v1.md: "
            "ollama-exact-version-run fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        versions,
        strict=True,
    ):
        if (
            provider_candidate["version"] != runner_candidate["version"]
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate["archiveSha256"]
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate["archiveUrl"]
            or provider_candidate["isolatedAdapterSmoke"]
            != {
                "coldStartPassed": runner_candidate["coldStart"][
                    "adapterTestPassed"
                ],
                "emptyCatalogPassed": True,
                "restartPassed": runner_candidate["restart"][
                    "adapterTestPassed"
                ],
                "stoppedEndpointUnavailable": (
                    runner_candidate["coldStart"][
                        "endpointUnavailableAfterStop"
                    ]
                    and runner_candidate["restart"][
                        "endpointUnavailableAfterStop"
                    ]
                ),
            }
        ):
            failures.append(
                "provider-compatibility fixture and exact-version runner "
                "fixture differ in Ollama version, archive identity, or "
                "isolated adapter result."
            )
            break

    return failures


def local_release_document_failures() -> list[str]:
    try:
        relative_doc = LOCAL_RELEASE_DOC.relative_to(ROOT)
    except ValueError:
        relative_doc = LOCAL_RELEASE_DOC
    if not LOCAL_RELEASE_DOC.is_file():
        return [f"{relative_doc}: missing local release qualification record."]

    try:
        document_text = LOCAL_RELEASE_DOC.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [f"{relative_doc}: unreadable local release qualification record: {error}"]

    failures: list[str] = []
    required_claims = (
        ("release ID", f"`{LOCAL_RELEASE_ID}`"),
        (
            "ZIP size",
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SIZE:,} bytes",
        ),
        ("ZIP SHA-256", f"`{LOCAL_RELEASE_EXPECTED_ZIP_SHA256}`"),
        (
            "manifest size",
            f"{LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE:,} bytes",
        ),
        (
            "manifest SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256}`",
        ),
        (
            "source inventory count",
            f"{LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT}-file source inventory",
        ),
        (
            "source inventory SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_SHA256}`",
        ),
        ("source HEAD", f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`"),
        (
            "payload member count",
            f"{LOCAL_RELEASE_EXPECTED_MEMBER_COUNT} payload members",
        ),
        ("macOS app/dSYM UUID", f"`{LOCAL_RELEASE_EXPECTED_MACOS_UUID}`"),
    )
    for member_path, (size, sha256) in LOCAL_RELEASE_EXPECTED_MEMBERS.items():
        required_claims += (
            (f"{member_path} size", f"{size:,} bytes"),
            (f"{member_path} SHA-256", f"`{sha256}`"),
        )

    for label, expected_text in required_claims:
        if expected_text not in document_text:
            failures.append(
                f"{relative_doc}: missing exact {label} claim {expected_text!r}."
            )

    failures.extend(local_release_transition_fixture_failures(document_text))
    failures.extend(local_release_provider_fixture_failures(document_text))
    failures.extend(local_release_ollama_runner_fixture_failures(document_text))

    if not LOCAL_RELEASE_ARCHIVE_DIR.exists():
        return failures
    if not LOCAL_RELEASE_ARCHIVE_DIR.is_dir():
        failures.append(
            f"{LOCAL_RELEASE_ARCHIVE_DIR.relative_to(ROOT)}: local release archive path is not a directory."
        )
        return failures

    archive_path = LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip"
    manifest_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.manifest.json"
    )
    checksum_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip.sha256"
    )
    for path in (archive_path, manifest_path, checksum_path):
        if not path.is_file():
            failures.append(
                f"{path.relative_to(ROOT)}: missing local release readback input."
            )
    if failures and any(not path.is_file() for path in (archive_path, manifest_path, checksum_path)):
        return failures

    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(
            manifest_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
        checksum_fields = checksum_path.read_text(encoding="ascii").split()
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: unreadable local release identity: {error}"
        )
        return failures

    if not isinstance(manifest, dict):
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: manifest root must be a JSON object."
        )
        return failures

    def read_path(path: tuple[str, ...]) -> object:
        value: object = manifest
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    manifest_expectations = (
        (("release", "releaseId"), LOCAL_RELEASE_ID),
        (
            ("archive", "memberCountExcludingManifest"),
            LOCAL_RELEASE_EXPECTED_MEMBER_COUNT,
        ),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (("source", "snapshotSha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
        (("source", "head"), LOCAL_RELEASE_EXPECTED_SOURCE_HEAD),
        (("platforms", "android", "applicationId"), "com.localagentbridge.android"),
        (("platforms", "android", "versionCode"), 1),
        (("platforms", "android", "versionName"), "1.0.0"),
        (("platforms", "android", "minSdk"), 26),
        (("platforms", "android", "targetSdk"), 36),
        (("platforms", "android", "abis"), ["arm64-v8a"]),
        (("platforms", "android", "signatureState"), "unsigned"),
        (("platforms", "macos", "bundleId"), "dev.aetherlink.companion"),
        (("platforms", "macos", "marketingVersion"), "1.0.0"),
        (("platforms", "macos", "buildNumber"), 1),
        (("platforms", "macos", "minimumSystemVersion"), "14.0"),
        (("platforms", "macos", "architectures"), ["arm64"]),
        (("platforms", "macos", "signatureState"), "ad-hoc-local"),
        (("platforms", "macos", "uuid"), LOCAL_RELEASE_EXPECTED_MACOS_UUID),
        (
            ("platforms", "macos", "dSYM", "uuid"),
            LOCAL_RELEASE_EXPECTED_MACOS_UUID,
        ),
    )
    for path, expected in manifest_expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{manifest_path.relative_to(ROOT)}: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )

    member_rows = manifest.get("members")
    actual_members: dict[str, tuple[object, object]] = {}
    if not isinstance(member_rows, list):
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: members must be a JSON array."
        )
    else:
        for index, row in enumerate(member_rows):
            if not isinstance(row, dict):
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: members[{index}] must be an object."
                )
                continue
            path = row.get("path")
            if not isinstance(path, str):
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: members[{index}].path must be a string."
                )
                continue
            if path in actual_members:
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: duplicate member path {path!r}."
                )
                continue
            actual_members[path] = (row.get("size"), row.get("sha256"))

    for member_path, expected_identity in LOCAL_RELEASE_EXPECTED_MEMBERS.items():
        actual_identity = actual_members.get(member_path)
        if actual_identity != expected_identity:
            failures.append(
                f"{manifest_path.relative_to(ROOT)}: expected {member_path} "
                f"identity {expected_identity!r}, found {actual_identity!r}."
            )

    manifest_identity = (len(manifest_bytes), hashlib.sha256(manifest_bytes).hexdigest())
    expected_manifest_identity = (
        LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE,
        LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
    )
    if manifest_identity != expected_manifest_identity:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: expected manifest identity "
            f"{expected_manifest_identity!r}, found {manifest_identity!r}."
        )

    archive_size = archive_path.stat().st_size
    if archive_size != LOCAL_RELEASE_EXPECTED_ZIP_SIZE:
        failures.append(
            f"{archive_path.relative_to(ROOT)}: expected size "
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SIZE}, found {archive_size}."
        )
    if (
        len(checksum_fields) != 2
        or checksum_fields[0] != LOCAL_RELEASE_EXPECTED_ZIP_SHA256
        or checksum_fields[1] != archive_path.name
    ):
        failures.append(
            f"{checksum_path.relative_to(ROOT)}: checksum sidecar does not match "
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SHA256} and {archive_path.name}."
        )

    return failures


def latest_progress_entry() -> tuple[int, str]:
    if not PROGRESS_DOC.is_file():
        return (0, "")

    lines = PROGRESS_DOC.read_text(encoding="utf-8", errors="replace").splitlines()
    implemented_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "## Implemented So Far"),
        -1,
    )
    if implemented_index < 0:
        return (0, "")

    start_index = next(
        (
            index
            for index in range(implemented_index + 1, len(lines))
            if lines[index].startswith("### ")
        ),
        -1,
    )
    if start_index < 0:
        return (0, "")

    end_index = next(
        (
            index
            for index in range(start_index + 1, len(lines))
            if lines[index].startswith("### ")
        ),
        len(lines),
    )
    return (start_index + 1, "\n".join(lines[start_index:end_index]))


def latest_qa_evidence_entry() -> tuple[int, str]:
    if not QA_EVIDENCE_DOC.is_file():
        return (0, "")

    lines = QA_EVIDENCE_DOC.read_text(encoding="utf-8", errors="replace").splitlines()
    current_rule_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "## Current Rule"),
        -1,
    )
    if current_rule_index < 0:
        return (0, "")

    start_index = next(
        (
            index
            for index in range(current_rule_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        -1,
    )
    if start_index < 0:
        return (0, "")

    end_index = next(
        (
            index
            for index in range(start_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return (start_index + 1, "\n".join(lines[start_index:end_index]))


def latest_progress_evidence_failures() -> list[str]:
    failures: list[str] = []
    start_line, entry = latest_progress_entry()
    if not entry:
        return [
            "docs/progress.md: missing latest implemented progress entry under '## Implemented So Far'."
        ]

    required_patterns = (
        (
            re.compile(r"^### \d{4}-\d{2}-\d{2} .+", re.MULTILINE),
            "Latest progress entry must start with a dated implementation heading.",
        ),
        (
            re.compile(r"\bno-device\b", re.IGNORECASE),
            "Latest progress entry must state whether verification was no-device.",
        ),
        (
            re.compile(r"\bCaveat:", re.IGNORECASE),
            "Latest progress entry must include an explicit caveat.",
        ),
        (
            re.compile(r"\bphysical\b|\bcamera QR\b|\breal different-network\b", re.IGNORECASE),
            "Latest progress caveat must name physical or real-network coverage limits.",
        ),
        (
            re.compile(r"\bVerified after this change:", re.IGNORECASE),
            "Latest progress entry must list current verification commands.",
        ),
        (
            re.compile(r"`(?:swift|python3|JAVA_HOME=|git diff|bash)\b", re.IGNORECASE),
            "Latest progress entry must include concrete verification commands in backticks.",
        ),
    )

    for pattern, guidance in required_patterns:
        if not pattern.search(entry):
            failures.append(f"docs/progress.md:{start_line}: {guidance}")

    if "artifacts/" in entry and "device/runtime state" not in entry:
        failures.append(
            f"docs/progress.md:{start_line}: Progress entries that cite artifacts must explain the device/runtime state."
        )

    return failures


def latest_qa_evidence_failures() -> list[str]:
    failures: list[str] = []
    start_line, entry = latest_qa_evidence_entry()
    if not entry:
        return [
            "docs/qa-evidence.md: missing latest QA evidence entry after '## Current Rule'."
        ]

    required_patterns = (
        (
            re.compile(r"^## \d{4}-\d{2}-\d{2} .+", re.MULTILINE),
            "Latest QA evidence entry must start with a dated evidence heading.",
        ),
        (
            re.compile(r"\bproof-boundary\b|\bproof boundary\b", re.IGNORECASE),
            "Latest QA evidence entry must name the proof boundary.",
        ),
        (
            re.compile(r"\bno-device\b", re.IGNORECASE),
            "Latest QA evidence entry must state whether no-device evidence is involved.",
        ),
        (
            re.compile(r"\bphysical\b|\blive-provider\b|\blive provider\b", re.IGNORECASE),
            "Latest QA evidence entry must separate physical or live-provider proof from no-device evidence.",
        ),
        (
            re.compile(r"\bAgent state:.*\bGPT-5\.3-Codex-Spark was not used\b", re.IGNORECASE | re.DOTALL),
            "Latest QA evidence entry must record that GPT-5.3-Codex-Spark was not used.",
        ),
        (
            re.compile(r"\bCaveat:", re.IGNORECASE),
            "Latest QA evidence entry must include an explicit caveat.",
        ),
        (
            re.compile(r"\bVerification commands:", re.IGNORECASE),
            "Latest QA evidence entry must list verification commands.",
        ),
        (
            re.compile(r"`(?:swift|python3|JAVA_HOME=|git diff|bash|./script|script/)\b", re.IGNORECASE),
            "Latest QA evidence entry must include concrete verification commands in backticks.",
        ),
    )

    for pattern, guidance in required_patterns:
        if not pattern.search(entry):
            failures.append(f"docs/qa-evidence.md:{start_line}: {guidance}")

    if "artifacts/" in entry and "device/runtime state" not in entry:
        failures.append(
            f"docs/qa-evidence.md:{start_line}: QA entries that cite artifacts must explain the device/runtime state."
        )

    return failures


def syntax_only_no_device_gate_evidence_failures() -> list[str]:
    failures: list[str] = []
    syntax_command = "bash -n script/check_no_device_quality.sh"

    progress_start_line, progress_entry = latest_progress_entry()
    if syntax_command in progress_entry and "syntax only" not in progress_entry.lower():
        failures.append(
            f"docs/progress.md:{progress_start_line}: `{syntax_command}` is shell syntax validation only; "
            "label it as syntax only or record a real `bash script/check_no_device_quality.sh` run."
        )

    qa_path = ROOT / "docs/qa-evidence.md"
    if qa_path.exists():
        qa_lines = qa_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number, line in enumerate(qa_lines[:60], 1):
            if syntax_command in line and "syntax only" not in line.lower():
                failures.append(
                    f"docs/qa-evidence.md:{line_number}: `{syntax_command}` is shell syntax validation only; "
                    "label it as syntax only or record a real `bash script/check_no_device_quality.sh` run."
                )

    return failures


def physical_qr_observation_manifest_failures() -> list[str]:
    if not PHYSICAL_QR_OBSERVATION_MANIFEST.is_file():
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: missing sanitized physical QR observation manifest."
        ]

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        raw_text = PHYSICAL_QR_OBSERVATION_MANIFEST.read_text(encoding="utf-8")
        document = json.loads(raw_text, object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateJSONKeyError) as error:
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: unreadable or invalid JSON: "
            f"{error}"
        ]

    if not isinstance(document, dict):
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: root must be a JSON object."
        ]

    failures: list[str] = []

    def read_path(path: tuple[str, ...]) -> object:
        value: object = document
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    allowed_keys_by_path = {
        (): {
            "documentType",
            "schemaVersion",
            "recordedDate",
            "source",
            "device",
            "topology",
            "qrObservation",
            "observedMilestones",
            "retention",
            "proofBoundary",
        },
        ("source",): {
            "repository",
            "branch",
            "headAtObservation",
            "worktreeDirty",
            "exactTreeDigestRetained",
            "laterSourceDelta",
        },
        ("device",): {
            "model",
            "operatingSystem",
            "apiLevel",
            "appBuildVariant",
            "deviceIdentifierRetained",
        },
        ("topology",): {
            "runtimeHost",
            "deviceAndRuntimeNetwork",
            "usbRouteUsedForOpticalClaim",
            "externalRelayUsed",
            "p2pNatTraversalUsed",
        },
        ("qrObservation",): {
            "captureSurface",
            "scanMethod",
            "uriInjectionUsed",
            "routeScope",
            "queryKeyCount",
            "listenerPortAtObservation",
            "endpointReusable",
            "payloadSha256",
            "fullPayloadRetained",
        },
        ("observedMilestones",): {
            "pairingQrSourceConnected",
            "pairingRequestSent",
            "pairingResultReceived",
            "helloSent",
            "authenticationChallengeReceived",
            "authenticationResponseCompleted",
            "runtimeHealthCompleted",
            "trustedDeviceReportedByMacos",
            "bonjourReconnectAfterForceStop",
            "storedTrustAuthenticationCompleted",
            "runtimeHealthAfterReconnect",
        },
        ("retention",): {
            "rawLogcatRetained",
            "screenCaptureRetainedInRepository",
            "completeQrVerifierOutputRetained",
            "apkDigestRetained",
            "sanitizedManifestRetained",
            "sensitiveMaterialIncluded",
        },
        ("proofBoundary",): {"proves", "doesNotProve"},
    }
    for path, allowed_keys in allowed_keys_by_path.items():
        value = read_path(path)
        if not isinstance(value, dict):
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: expected object at "
                f"{'.'.join(path) or '<root>'}."
            )
            continue
        actual_keys = set(value)
        if actual_keys != allowed_keys:
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: closed schema mismatch at "
                f"{'.'.join(path) or '<root>'}; missing={sorted(allowed_keys - actual_keys)}, "
                f"unexpected={sorted(actual_keys - allowed_keys)}."
            )

    forbidden_key_names = {
        "serial",
        "deviceserial",
        "fullpayload",
        "fullqrpayload",
        "fullqruri",
        "verifieroutput",
        "completeqrverifieroutput",
        "pairingcode",
        "pairingnonce",
        "nonce",
        "relaysecret",
        "allocationtoken",
        "routetoken",
        "privatekey",
        "identityprivatekey",
        "privateidentitymaterial",
        "devicecredential",
        "devicecredentials",
    }
    sensitive_string_patterns = (
        re.compile(r"\baetherlink\s*:\s*//\s*pair\b", re.IGNORECASE),
        re.compile(
            r"\b(?:pairing[\s_-]*(?:code|nonce)|nonce|secret|token|"
            r"relay[\s_-]*secret|allocation[\s_-]*token|route[\s_-]*token|"
            r"private[\s_-]*(?:key|identity))\b\s*[:=]",
            re.IGNORECASE,
        ),
    )

    def reject_sensitive_content(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
                if normalized_key in forbidden_key_names:
                    failures.append(
                        "docs/evidence/physical-qr-pairing-20260719.json: prohibited sensitive key "
                        f"{'.'.join(path + (key,))}."
                    )
                reject_sensitive_content(child, path + (key,))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                reject_sensitive_content(child, path + (str(index),))
        elif isinstance(value, str) and any(
            pattern.search(value) for pattern in sensitive_string_patterns
        ):
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: prohibited credential-like string value at "
                f"{'.'.join(path) or '<root>'}."
            )

    reject_sensitive_content(document)

    expected_values = (
        (("documentType",), "aetherlink.physical-qr-pairing-observation"),
        (("schemaVersion",), 1),
        (("recordedDate",), "2026-07-19"),
        (("source", "repository"), "/Users/hanchangha/Desktop/project"),
        (("source", "branch"), "main"),
        (("source", "headAtObservation"), "df19c53a"),
        (("source", "worktreeDirty"), True),
        (("source", "exactTreeDigestRetained"), False),
        (("source", "laterSourceDelta"), "macos_ui_and_launcher_only_without_android_retest"),
        (("device", "model"), "SM-S936N"),
        (("device", "operatingSystem"), "Android 16"),
        (("device", "apiLevel"), 36),
        (("device", "appBuildVariant"), "debug"),
        (("device", "deviceIdentifierRetained"), False),
        (("topology", "runtimeHost"), "macos_development_app"),
        (("topology", "deviceAndRuntimeNetwork"), "same_wifi_lan"),
        (("topology", "usbRouteUsedForOpticalClaim"), False),
        (("topology", "externalRelayUsed"), False),
        (("topology", "p2pNatTraversalUsed"), False),
        (("qrObservation", "captureSurface"), "actual_macos_window_screen"),
        (("qrObservation", "scanMethod"), "physical_android_camera"),
        (("qrObservation", "uriInjectionUsed"), False),
        (("qrObservation", "routeScope"), "local_diagnostic"),
        (("qrObservation", "queryKeyCount"), 11),
        (("qrObservation", "listenerPortAtObservation"), 43170),
        (("qrObservation", "endpointReusable"), False),
        (("qrObservation", "payloadSha256"), "efc77b1402ed6270b741e5ee69bb30a7527ad563876f58eee31e7587ef9544ef"),
        (("qrObservation", "fullPayloadRetained"), False),
        (("observedMilestones", "pairingQrSourceConnected"), True),
        (("observedMilestones", "pairingRequestSent"), True),
        (("observedMilestones", "pairingResultReceived"), True),
        (("observedMilestones", "helloSent"), True),
        (("observedMilestones", "authenticationChallengeReceived"), True),
        (("observedMilestones", "authenticationResponseCompleted"), True),
        (("observedMilestones", "runtimeHealthCompleted"), True),
        (("observedMilestones", "trustedDeviceReportedByMacos"), True),
        (("observedMilestones", "bonjourReconnectAfterForceStop"), True),
        (("observedMilestones", "storedTrustAuthenticationCompleted"), True),
        (("observedMilestones", "runtimeHealthAfterReconnect"), True),
        (("retention", "rawLogcatRetained"), False),
        (("retention", "screenCaptureRetainedInRepository"), False),
        (("retention", "completeQrVerifierOutputRetained"), False),
        (("retention", "apkDigestRetained"), False),
        (("retention", "sanitizedManifestRetained"), True),
        (("retention", "sensitiveMaterialIncluded"), False),
        (("proofBoundary", "proves"), [
            "one_same_wifi_debug_optical_pairing",
            "challenge_response_and_runtime_health",
            "one_stored_trust_bonjour_reconnect",
        ]),
        (("proofBoundary", "doesNotProve"), [
            "release_apk_camera_pairing",
            "expired_or_rotated_qr_recovery",
            "camera_permission_recovery",
            "talkback_or_voiceover",
            "different_network_pairing",
            "external_relay_operation",
            "p2p_nat_or_phase_b",
            "production_capacity_reliability_or_readiness",
        ]),
    )
    for path, expected in expected_values:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )

    payload_digest = read_path(("qrObservation", "payloadSha256"))
    if not isinstance(payload_digest, str) or re.fullmatch(r"[0-9a-f]{64}", payload_digest) is None:
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: qrObservation.payloadSha256 must be one lowercase SHA-256 digest."
        )

    if isinstance(payload_digest, str):
        for relative_path in ("docs/progress.md", "docs/qa-evidence.md"):
            path = ROOT / relative_path
            if payload_digest not in path.read_text(encoding="utf-8", errors="replace"):
                failures.append(
                    f"{relative_path}: physical QR payload digest must match the sanitized observation manifest."
                )

    nonclaims = read_path(("proofBoundary", "doesNotProve"))
    required_nonclaims = {
        "release_apk_camera_pairing",
        "different_network_pairing",
        "external_relay_operation",
        "p2p_nat_or_phase_b",
        "production_capacity_reliability_or_readiness",
    }
    if not isinstance(nonclaims, list) or not required_nonclaims.issubset(
        {value for value in nonclaims if isinstance(value, str)}
    ):
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: proofBoundary.doesNotProve must retain release, different-network, relay, P2P/Phase B, and production limits."
        )

    if re.search(r"\baetherlink\s*:\s*(?:\\?/){2}\s*pair\b", raw_text, re.IGNORECASE):
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: full credential-bearing QR URI must not be retained."
        )

    return failures


def main() -> int:
    failures: list[str] = []

    for path in target_files():
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for rule in RULES:
                if rule.pattern.search(line):
                    failures.append(f"{relative}:{line_number}: {rule.name}: {rule.guidance}")

    docs_text = contract_text()
    for contract in CONTRACTS:
        missing = [
            pattern.pattern
            for pattern in contract.required_patterns
            if not pattern.search(docs_text)
        ]
        if missing:
            failures.append(
                f"documentation-contract:{contract.name}: {contract.guidance} "
                f"Missing pattern(s): {', '.join(missing)}"
            )

    for contract in FILE_CONTRACTS:
        target_text = file_contract_text(contract.target)
        if not target_text:
            failures.append(
                f"documentation-file-contract:{contract.name}: Missing target file {contract.target}. "
                f"{contract.guidance}"
            )
            continue
        missing = [
            pattern.pattern
            for pattern in contract.required_patterns
            if not pattern.search(target_text)
        ]
        if missing:
            failures.append(
                f"documentation-file-contract:{contract.name}: {contract.guidance} "
                f"Missing pattern(s): {', '.join(missing)}"
            )

    failures.extend(latest_progress_evidence_failures())
    failures.extend(latest_qa_evidence_failures())
    failures.extend(syntax_only_no_device_gate_evidence_failures())
    failures.extend(local_release_document_failures())
    failures.extend(physical_qr_observation_manifest_failures())

    if failures:
        print("Docs hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Docs hygiene OK across {len(target_files())} current documentation file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
