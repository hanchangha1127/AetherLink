#!/usr/bin/env python3
"""Check current docs for stale product-boundary wording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PHYSICAL_QR_OBSERVATION_MANIFEST = (
    ROOT / "docs/evidence/physical-qr-pairing-20260719.json"
)


class DuplicateJSONKeyError(ValueError):
    pass


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
