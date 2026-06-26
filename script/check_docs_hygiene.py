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
            r"\b(?:system language|Device language|System/Device language)\b",
            re.IGNORECASE,
        ),
        "Visible app language choices must stay exactly English, Korean, Japanese, Simplified Chinese, and French; System is only for appearance.",
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

CONTRACT_TARGETS = HYGIENE_TARGETS + (
    "docs/progress.md",
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
)


def target_files() -> list[Path]:
    return [path for path in (ROOT / target for target in HYGIENE_TARGETS) if path.is_file()]


def contract_text() -> str:
    chunks: list[str] = []
    for target in CONTRACT_TARGETS:
        path = ROOT / target
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


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

    if failures:
        print("Docs hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Docs hygiene OK across {len(target_files())} current documentation file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
