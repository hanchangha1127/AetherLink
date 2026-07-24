#!/usr/bin/env python3
"""Pure, bounded lexical-candidate aggregation for the G2 Pion v3 review.

This module accepts only caller-supplied ``(repository_relative_path, bytes)``
source entries.  It performs no filesystem, archive, network, device, Git, or
authentication work.

Candidate semantics are intentionally lexical and exactly preserve the v2
``re.search(pattern, logical_line)`` behavior.  A hit is one
``(path, one_based_line_number, rule_id)`` tuple; repeated words matching the
same rule on the same logical line are one hit.

Complete-observation SHA-256 encoding, version 1
------------------------------------------------
Each patch-unit digest is initialized with ``COMPLETE_OBSERVATION_HASH_DOMAIN``
followed by the unit ID as ``u16be(length) || UTF-8 bytes``.  Every hit is then
streamed in byte-path, line, fixed-unit, fixed-rule order as:

``u32be(path length) || path UTF-8 || u64be(line) ||
u16be(rule ID length) || rule ID UTF-8 || SHA256(logical line UTF-8)``

The logical-line digest excludes its line terminator because Python
``str.splitlines()`` supplies the exact v2 logical-line semantics.  It is not
included in output representatives.  Representative rank SHA-256 encoding,
version 1, is ``REPRESENTATIVE_RANK_DOMAIN`` followed by the same path, line,
and rule-ID fields (without patch-unit or line digest).  Rank ties are broken
by the full hit tuple ``(path UTF-8, line, rule ID UTF-8)``.
"""

from __future__ import annotations

import hashlib
import re
import struct
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional
import unicodedata


MAXIMUM_SOURCE_ENTRIES = 4_096
MAXIMUM_PATH_BYTES = 1_024
MAXIMUM_PATH_COMPONENTS = 32
MAXIMUM_COMPONENT_BYTES = 255
MAXIMUM_SOURCE_BYTES = 2_097_152
MAXIMUM_TOTAL_SOURCE_BYTES = 67_108_864
MAXIMUM_LOGICAL_LINES_PER_SOURCE = 262_144
MAXIMUM_TOTAL_LOGICAL_LINES = 1_048_576
REPRESENTATIVE_LIMIT_PER_RULE = 8

COMPLETE_OBSERVATION_ENCODING_VERSION = 1
COMPLETE_OBSERVATION_HASH_DOMAIN = (
    b"aetherlink.g2.pion.candidate-inventory.v3.complete-observation.v1\x00"
)
REPRESENTATIVE_RANK_ENCODING_VERSION = 1
REPRESENTATIVE_RANK_DOMAIN = (
    b"aetherlink.g2.pion.candidate-inventory.v3.representative-rank.v1\x00"
)
LEXICAL_MEANING = (
    "lexical_candidate_locations_only_not_type_control_or_data_flow_proof"
)

PATCH_UNITS = (
    "split_egress_capability_and_ingress_admission_boundaries",
    "remove_secret_bearing_diagnostics",
    "replace_callbacks_with_bounded_pull_events_and_sticky_terminal_latch",
    "deadline_bounded_shutdown",
    "disable_nonprofile_network_paths",
    "inject_bounded_resolver_interface_and_turn_tls_identity_inputs",
    "add_one_use_pre_auth_path_and_exact_secure_session_promotion",
)

_REVIEW_RULE_ROWS = (
    (
        PATCH_UNITS[0],
        (
            ("egress-dial", r"\b(?:Dial|DialContext|DialUDP|WriteTo|WriteToUDP)\b"),
            ("egress-listen", r"\b(?:Listen|ListenPacket|ListenUDP|PacketConn)\b"),
            ("candidate-io", r"\b(?:Candidate|UDPMux|UniversalUDPMux|sendBindingRequest)\b"),
        ),
    ),
    (
        PATCH_UNITS[1],
        (
            ("diagnostic-call", r"\b(?:Tracef|Debugf|Infof|Warnf|Errorf|Logf|Logger)\b"),
            ("credential-token", r"(?i)\b(?:credential|password|username|ufrag|pwd|secret)\b"),
        ),
    ),
    (
        PATCH_UNITS[2],
        (
            ("callback", r"\bOn(?:ConnectionStateChange|SelectedCandidatePairChange)\b"),
            ("channel", r"\b(?:chan|close)\b|make\s*\(\s*chan\b"),
            ("event", r"(?i)\b(?:event|callback|handler)\b"),
        ),
    ),
    (
        PATCH_UNITS[3],
        (
            ("deadline", r"\b(?:SetDeadline|SetReadDeadline|SetWriteDeadline|WithTimeout)\b"),
            ("shutdown", r"\b(?:Close|cancel|WaitGroup|Done)\b"),
            ("time-bound", r"(?i)\b(?:deadline|timeout|shutdown)\b"),
        ),
    ),
    (
        PATCH_UNITS[4],
        (
            ("transport-path", r"(?i)\b(?:tcp|udp|mdns|proxy|relay|host|srflx|upnp)\b"),
            ("network-type", r"\b(?:NetworkType|CandidateType|TCPType)\b"),
        ),
    ),
    (
        PATCH_UNITS[5],
        (
            ("resolver", r"\b(?:Resolver|LookupIP|LookupHost|ResolveIPAddr)\b"),
            ("turn-tls", r"\b(?:ServerName|InsecureSkipVerify|TLSConfig|tls\.Config|TURN)\b"),
            ("network-injection", r"\b(?:Net|TransportNet|vnet)\b"),
        ),
    ),
    (
        PATCH_UNITS[6],
        (
            ("pre-auth", r"(?i)\b(?:auth|credential|username|password|ufrag|pwd)\b"),
            ("promotion-state", r"\b(?:ConnectionState|setState|validate|Validate)\b"),
            ("one-use", r"(?i)\b(?:one.?use|single.?use|nonce|replay)\b"),
        ),
    ),
)
REVIEW_RULES: Mapping[str, tuple[tuple[str, str], ...]] = MappingProxyType(
    dict(_REVIEW_RULE_ROWS)
)
_COMPILED_RULE_ROWS = tuple(
    (
        patch_unit,
        tuple((rule_id, pattern, re.compile(pattern)) for rule_id, pattern in rules),
    )
    for patch_unit, rules in _REVIEW_RULE_ROWS
)


class CandidateInventoryError(ValueError):
    """A caller-supplied source entry or bound is invalid."""


class InventoryLimits:
    """Caller-reducible limits, each capped by a fixed module maximum."""

    def __init__(
        self,
        *,
        source_entries: int = MAXIMUM_SOURCE_ENTRIES,
        path_bytes: int = MAXIMUM_PATH_BYTES,
        path_components: int = MAXIMUM_PATH_COMPONENTS,
        component_bytes: int = MAXIMUM_COMPONENT_BYTES,
        source_bytes: int = MAXIMUM_SOURCE_BYTES,
        total_source_bytes: int = MAXIMUM_TOTAL_SOURCE_BYTES,
        logical_lines_per_source: int = MAXIMUM_LOGICAL_LINES_PER_SOURCE,
        total_logical_lines: int = MAXIMUM_TOTAL_LOGICAL_LINES,
    ) -> None:
        self.source_entries = source_entries
        self.path_bytes = path_bytes
        self.path_components = path_components
        self.component_bytes = component_bytes
        self.source_bytes = source_bytes
        self.total_source_bytes = total_source_bytes
        self.logical_lines_per_source = logical_lines_per_source
        self.total_logical_lines = total_logical_lines


_LIMIT_CEILINGS = (
    ("source_entries", MAXIMUM_SOURCE_ENTRIES),
    ("path_bytes", MAXIMUM_PATH_BYTES),
    ("path_components", MAXIMUM_PATH_COMPONENTS),
    ("component_bytes", MAXIMUM_COMPONENT_BYTES),
    ("source_bytes", MAXIMUM_SOURCE_BYTES),
    ("total_source_bytes", MAXIMUM_TOTAL_SOURCE_BYTES),
    ("logical_lines_per_source", MAXIMUM_LOGICAL_LINES_PER_SOURCE),
    ("total_logical_lines", MAXIMUM_TOTAL_LOGICAL_LINES),
)


def _validated_limits(limits: InventoryLimits) -> InventoryLimits:
    if type(limits) is not InventoryLimits:
        raise CandidateInventoryError("limits must be an exact InventoryLimits value")
    for name, ceiling in _LIMIT_CEILINGS:
        value = getattr(limits, name)
        if type(value) is not int:
            raise CandidateInventoryError(f"{name} must be an integer, not bool or another type")
        if value < 1 or value > ceiling:
            raise CandidateInventoryError(f"{name} is outside its fixed safe range")
    return InventoryLimits(
        **{name: getattr(limits, name) for name, _ceiling in _LIMIT_CEILINGS}
    )


def _validated_path(path: str, limits: InventoryLimits) -> bytes:
    if type(path) is not str:
        raise CandidateInventoryError("source path must be an exact string")
    try:
        raw_path = path.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise CandidateInventoryError("source path is not strict UTF-8") from error
    if not raw_path or len(raw_path) > limits.path_bytes:
        raise CandidateInventoryError("source path is empty or exceeds its byte bound")
    if (
        path.startswith("/")
        or path.endswith("/")
        or "\\" in path
        or ":" in path
        or "\x00" in path
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
    ):
        raise CandidateInventoryError(f"source path is unsafe: {path!r}")
    if unicodedata.normalize("NFC", path) != path:
        raise CandidateInventoryError(f"source path is not NFC-normalized: {path!r}")
    components = path.split("/")
    if (
        len(components) > limits.path_components
        or any(component in ("", ".", "..") for component in components)
    ):
        raise CandidateInventoryError(f"source path is noncanonical: {path!r}")
    for component in components:
        if len(component.encode("utf-8")) > limits.component_bytes:
            raise CandidateInventoryError(f"source path component exceeds its byte bound: {path!r}")
    return raw_path


def _u16_field(raw: bytes) -> bytes:
    if len(raw) > 0xFFFF:
        raise CandidateInventoryError("internal u16 field length overflow")
    return struct.pack(">H", len(raw)) + raw


def _hit_identity_encoding(path_bytes: bytes, line_number: int, rule_id: str) -> bytes:
    rule_bytes = rule_id.encode("utf-8")
    return (
        struct.pack(">I", len(path_bytes))
        + path_bytes
        + struct.pack(">Q", line_number)
        + _u16_field(rule_bytes)
    )


def representative_rank_sha256(path_bytes: bytes, line_number: int, rule_id: str) -> str:
    """Return the fixed rank digest for a validated hit identity."""

    if type(path_bytes) is not bytes or type(line_number) is not int or line_number < 1:
        raise CandidateInventoryError("representative rank identity is invalid")
    if type(rule_id) is not str:
        raise CandidateInventoryError("representative rank rule ID is invalid")
    return hashlib.sha256(
        REPRESENTATIVE_RANK_DOMAIN
        + _hit_identity_encoding(path_bytes, line_number, rule_id)
    ).hexdigest()


def _new_unit_hasher(patch_unit: str) -> Any:
    hasher = hashlib.sha256()
    hasher.update(COMPLETE_OBSERVATION_HASH_DOMAIN)
    hasher.update(_u16_field(patch_unit.encode("utf-8")))
    return hasher


def _representative_sort_key(representative: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        representative["rankSha256"],
        representative["path"].encode("utf-8"),
        representative["line"],
        representative["ruleId"].encode("utf-8"),
    )


def _retain_representative(
    representatives: list[dict[str, Any]],
    *,
    path: str,
    path_bytes: bytes,
    line_number: int,
    rule_id: str,
) -> None:
    representative = {
        "path": path,
        "line": line_number,
        "ruleId": rule_id,
        "rankSha256": representative_rank_sha256(path_bytes, line_number, rule_id),
    }
    representatives.append(representative)
    representatives.sort(key=_representative_sort_key)
    if len(representatives) > REPRESENTATIVE_LIMIT_PER_RULE:
        representatives.pop()


def aggregate_candidate_inventory(
    source_entries: Iterable[tuple[str, bytes]],
    *,
    limits: Optional[InventoryLimits] = None,
) -> dict[str, Any]:
    """Aggregate bounded lexical candidates without retaining the full hit set."""

    safe_limits = _validated_limits(InventoryLimits() if limits is None else limits)
    if isinstance(source_entries, (str, bytes, bytearray, memoryview)):
        raise CandidateInventoryError("source entries must be an iterable of path/bytes pairs")

    validated_entries: list[tuple[bytes, str, bytes]] = []
    seen_paths: set[bytes] = set()
    total_source_bytes = 0
    try:
        iterator = iter(source_entries)
    except TypeError as error:
        raise CandidateInventoryError("source entries are not iterable") from error
    for entry in iterator:
        if (
            not isinstance(entry, (tuple, list))
            or len(entry) != 2
        ):
            raise CandidateInventoryError("each source entry must be one path/bytes pair")
        path, raw = entry
        path_bytes = _validated_path(path, safe_limits)
        if type(raw) is not bytes:
            raise CandidateInventoryError(f"source bytes for {path!r} must be exact bytes")
        if len(raw) > safe_limits.source_bytes:
            raise CandidateInventoryError(f"source {path!r} exceeds its byte bound")
        total_source_bytes += len(raw)
        if total_source_bytes > safe_limits.total_source_bytes:
            raise CandidateInventoryError("source entries exceed the total byte bound")
        if path_bytes in seen_paths:
            raise CandidateInventoryError(f"source path is duplicated: {path!r}")
        seen_paths.add(path_bytes)
        validated_entries.append((path_bytes, path, raw))
        if len(validated_entries) > safe_limits.source_entries:
            raise CandidateInventoryError("source entry count exceeds its bound")
    validated_entries.sort(key=lambda entry: entry[0])

    unit_states: dict[str, dict[str, Any]] = {}
    for patch_unit, rules in _COMPILED_RULE_ROWS:
        unit_states[patch_unit] = {
            "hasher": _new_unit_hasher(patch_unit),
            "total": 0,
            "rules": {
                rule_id: {"total": 0, "representatives": []}
                for rule_id, _pattern, _compiled in rules
            },
        }

    total_logical_lines = 0
    for path_bytes, path, raw in validated_entries:
        if b"\x00" in raw:
            raise CandidateInventoryError(f"source {path!r} contains NUL")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise CandidateInventoryError(f"source {path!r} is not strict UTF-8") from error
        logical_lines = text.splitlines()
        if len(logical_lines) > safe_limits.logical_lines_per_source:
            raise CandidateInventoryError(f"source {path!r} exceeds its logical-line bound")
        total_logical_lines += len(logical_lines)
        if total_logical_lines > safe_limits.total_logical_lines:
            raise CandidateInventoryError("source entries exceed the total logical-line bound")
        for line_number, line in enumerate(logical_lines, start=1):
            line_sha256 = hashlib.sha256(line.encode("utf-8")).digest()
            for patch_unit, rules in _COMPILED_RULE_ROWS:
                unit_state = unit_states[patch_unit]
                for rule_id, _pattern, compiled in rules:
                    if compiled.search(line) is None:
                        continue
                    identity = _hit_identity_encoding(path_bytes, line_number, rule_id)
                    unit_state["hasher"].update(identity)
                    unit_state["hasher"].update(line_sha256)
                    unit_state["total"] += 1
                    rule_state = unit_state["rules"][rule_id]
                    rule_state["total"] += 1
                    _retain_representative(
                        rule_state["representatives"],
                        path=path,
                        path_bytes=path_bytes,
                        line_number=line_number,
                        rule_id=rule_id,
                    )

    patch_unit_rows: list[dict[str, Any]] = []
    overall_hit_count = 0
    overall_recorded_count = 0
    for patch_unit, rules in _COMPILED_RULE_ROWS:
        unit_state = unit_states[patch_unit]
        rule_rows: list[dict[str, Any]] = []
        unit_recorded_count = 0
        for rule_id, pattern, _compiled in rules:
            rule_state = unit_state["rules"][rule_id]
            representatives = rule_state["representatives"]
            total = rule_state["total"]
            recorded = len(representatives)
            if total > 0 and recorded < 1:
                raise AssertionError("nonzero rule lost all representatives")
            unit_recorded_count += recorded
            rule_rows.append(
                {
                    "ruleId": rule_id,
                    "regex": pattern,
                    "totalHitCount": total,
                    "recordedRepresentativeCount": recorded,
                    "omittedHitCount": total - recorded,
                    "truncated": total > recorded,
                    "representatives": representatives,
                }
            )
        unit_total = unit_state["total"]
        patch_unit_rows.append(
            {
                "patchUnit": patch_unit,
                "meaning": LEXICAL_MEANING,
                "totalHitCount": unit_total,
                "recordedRepresentativeCount": unit_recorded_count,
                "omittedHitCount": unit_total - unit_recorded_count,
                "truncated": unit_total > unit_recorded_count,
                "completeObservationSha256": unit_state["hasher"].hexdigest(),
                "rules": rule_rows,
            }
        )
        overall_hit_count += unit_total
        overall_recorded_count += unit_recorded_count

    return {
        "schemaVersion": "3.0",
        "meaning": LEXICAL_MEANING,
        "sourceEntryCount": len(validated_entries),
        "sourceTotalBytes": total_source_bytes,
        "sourceLogicalLineCount": total_logical_lines,
        "representativeLimitPerRule": REPRESENTATIVE_LIMIT_PER_RULE,
        "completeObservationEncodingVersion": COMPLETE_OBSERVATION_ENCODING_VERSION,
        "representativeRankEncodingVersion": REPRESENTATIVE_RANK_ENCODING_VERSION,
        "totals": {
            "hitCount": overall_hit_count,
            "recordedRepresentativeCount": overall_recorded_count,
            "omittedHitCount": overall_hit_count - overall_recorded_count,
            "truncated": overall_hit_count > overall_recorded_count,
        },
        "patchUnits": patch_unit_rows,
    }
