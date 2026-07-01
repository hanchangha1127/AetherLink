#!/usr/bin/env python3
"""Check current docs for stale product-boundary wording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


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
    "docs/mvp-v0.1.md",
    "docs/protocol.md",
    "docs/qa-evidence.md",
    "docs/roadmap.md",
    "docs/security.md",
    "examples/README.md",
)

CONTRACT_TARGETS = HYGIENE_TARGETS

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
)


PROGRESS_DOC = ROOT / "docs/progress.md"


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
    failures.extend(syntax_only_no_device_gate_evidence_failures())

    if failures:
        print("Docs hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Docs hygiene OK across {len(target_files())} current documentation file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
