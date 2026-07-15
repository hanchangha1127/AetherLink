#!/usr/bin/env python3
"""Check the protocol JSON schema and v0.1 active message enum."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import sys
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "packages" / "protocol-schema" / "protocol.schema.json"
PAIRING_QR_SCHEMA_PATH = ROOT / "packages" / "protocol-schema" / "pairing-qr.schema.json"
ANDROID_PROTOCOL_MODELS_PATH = ROOT / "apps" / "android" / "core" / "protocol" / "src" / "main" / "java" / "com" / "localagentbridge" / "android" / "core" / "protocol" / "ProtocolModels.kt"
SWIFT_PROTOCOL_ENVELOPE_PATH = ROOT / "apps" / "macos" / "Protocol" / "Sources" / "ProtocolEnvelope.swift"
COMPACT_RELAY_QR_FIXTURE_PATH = ROOT / "shared" / "protocol" / "fixtures" / "macos-compact-relay-pairing-uri.txt"
COMPACT_PRIVATE_OVERLAY_RELAY_QR_FIXTURE_PATH = ROOT / "shared" / "protocol" / "fixtures" / "macos-compact-private-overlay-pairing-uri.txt"
COMPACT_P2P_RENDEZVOUS_QR_FIXTURE_PATH = ROOT / "shared" / "protocol" / "fixtures" / "macos-compact-p2p-rendezvous-pairing-uri.txt"


class DuplicateJSONNameError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"duplicate JSON object name {name!r}")
        self.name = name


def reject_duplicate_json_names(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for name, member in pairs:
        if name in value:
            raise DuplicateJSONNameError(name)
        value[name] = member
    return value


def load_json_rejecting_duplicate_names(text: str) -> object:
    return json.loads(text, object_pairs_hook=reject_duplicate_json_names)


def json_values_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            json_values_equal(actual[name], expected[name]) for name in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            json_values_equal(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected)
        )
    return actual == expected


def check_json_contract_guard_regressions() -> list[str]:
    failures: list[str] = []
    duplicate_samples = [
        '{"type":"runtime.health","type":"research.brief.create"}',
        '{"payload":{"authority":{"grant_id":"first","grant_id":"second"}}}',
    ]
    for sample in duplicate_samples:
        try:
            load_json_rejecting_duplicate_names(sample)
        except DuplicateJSONNameError:
            pass
        else:
            failures.append("protocol schema JSON loader must reject duplicate object names at every depth")

    for actual, expected in [
        (True, 1),
        (8.0, 8),
        ({"maxItems": 8.0}, {"maxItems": 8}),
        ({"uniqueItems": 1}, {"uniqueItems": True}),
    ]:
        if json_values_equal(actual, expected):
            failures.append(
                f"exact JSON contract comparison must distinguish {actual!r} from {expected!r}"
            )
    if not json_values_equal(
        {"type": "array", "maxItems": 8, "uniqueItems": True},
        {"type": "array", "maxItems": 8, "uniqueItems": True},
    ):
        failures.append("exact JSON contract comparison must accept identical concrete JSON values")
    return failures

RESERVED_PREFIXES = (
    "skills.",
    "mcp.",
    "web_search.",
    "python.",
    "projects.",
    "automation.",
    "permission.",
    "approval.",
    "audit.",
    "file.",
    "terminal.",
    "network.",
    "backend.",
    "embeddings.",
    "retrieval.",
    "index.",
    "research.",
    "citation.",
    "source_anchor.",
    "trusted_source.",
    "source_control.",
    "p2p.",
    "rendezvous.",
    "bootstrap.",
    "dht.",
    "nat.",
    "stun.",
    "turn.",
    "session.",
    "key_exchange.",
    "encrypted_session.",
    "anti_replay.",
    "transport.",
    "crypto.",
)
REQUIRED_RESERVED_PREFIXES = frozenset(RESERVED_PREFIXES)
ALLOWED_MEMORY_TYPES = {
    "memory.list",
    "memory.upsert",
    "memory.delete",
    "memory.duplicate_suggestions.list",
    "memory.semantic_duplicate_suggestions.list",
    "memory.semantic_duplicate_clusters.list",
    "memory.summary.drafts.list",
    "memory.summary.draft.generate",
    "memory.summary.draft.approve",
    "memory.summary.draft.dismiss",
}
ALLOWED_INDEX_TYPES = {
    "index.documents.list",
}
ALLOWED_RETRIEVAL_TYPES = {
    "retrieval.query",
}
ALLOWED_CITATION_TYPES = {
    "citation.resolve",
}
ALLOWED_CHAT_SOURCE_ATTRIBUTION_TYPES = {
    "chat.source_attribution.resolve",
}
ALLOWED_SOURCE_ANCHOR_TYPES = {
    "source_anchor.resolve",
}
ALLOWED_TRUSTED_SOURCE_TYPES = {
    "trusted_source.approve",
    "trusted_source.dismiss",
    "trusted_source.list",
    "trusted_source.revoke",
}
ALLOWED_RESEARCH_TYPES = {
    "research.brief.create",
    "research.notebooks.list",
}
SCHEMA_ONLY_MESSAGE_TYPES = (
    ALLOWED_CITATION_TYPES
    | ALLOWED_CHAT_SOURCE_ATTRIBUTION_TYPES
    | ALLOWED_TRUSTED_SOURCE_TYPES
)
ALLOWED_TOOL_TYPES = frozenset()
ALLOWED_ROUTE_TYPES = {"route.refresh"}
INDEX_DOCUMENT_MIME_TYPE_PATTERN = r"^[a-z0-9!#$%&'*+.^_`|~-]+/[a-z0-9!#$%&'*+.^_`|~-]+$"
CHAT_SOURCE_DOCUMENT_NAME_PATTERN = r"^[^\u0000-\u001F\u007F-\u009F/\\]+$"
REQUIRED_RELAY_QR_FIELDS = {
    "relay_host",
    "relay_port",
    "relay_id",
    "relay_secret",
    "relay_expires_at",
    "relay_nonce",
}
REMOTE_RELAY_QR_FIELDS = {
    "remote_host",
    "remote_port",
    "remote_id",
    "remote_secret",
    "remote_expires_at",
    "remote_nonce",
}
ROUTE_RELAY_QR_FIELDS = {
    "route_host",
    "route_port",
    "route_id",
    "route_secret",
    "route_expires_at",
    "route_nonce",
}
RENDEZVOUS_RELAY_QR_FIELDS = {
    "rendezvous_host",
    "rendezvous_port",
    "rendezvous_id",
    "rendezvous_secret",
    "rendezvous_expires_at",
    "rendezvous_nonce",
}
PRIVATE_RELAY_HOST_FIELDS = {
    "relay_host",
    "remote_host",
    "route_host",
    "rendezvous_host",
    "rh",
}
PAIRING_QR_REQUIRED_FIELD_GROUPS = {
    "version": {"version", "v"},
    "pairing_nonce": {"pairing_nonce", "nonce", "n"},
    "pairing_code": {"pairing_code", "code", "c"},
    "runtime_device_id": {"runtime_device_id", "mac_device_id", "device_id", "rid"},
    "runtime_key_fingerprint": {
        "runtime_key_fingerprint",
        "fingerprint",
        "cert_fingerprint",
        "rf",
    },
}
PAIRING_QR_SEMANTIC_ALIAS_GROUPS = {
    **PAIRING_QR_REQUIRED_FIELD_GROUPS,
    "runtime_name": {"runtime_name", "mac_name", "name", "rn"},
    "runtime_public_key": {"runtime_public_key", "mac_public_key", "public_key", "rk"},
    "route_token": {"route_token", "discovery_token", "rt"},
    "host": {"host", "runtime_host", "h"},
    "port": {"port", "runtime_port", "p"},
    "relay_id": {"relay_id", "network_id"},
    "relay_scope": {"relay_scope", "remote_scope", "route_scope", "rsc"},
}
COMPACT_RELAY_QR_FIELDS = {"rh", "rp", "ri", "rs", "rx", "rrn"}
RELAY_QR_ALIAS_FAMILIES = {
    "canonical": REQUIRED_RELAY_QR_FIELDS,
    "remote": REMOTE_RELAY_QR_FIELDS,
    "route": ROUTE_RELAY_QR_FIELDS,
    "rendezvous": RENDEZVOUS_RELAY_QR_FIELDS,
    "compact": COMPACT_RELAY_QR_FIELDS,
}
P2P_RENDEZVOUS_QR_FIELDS = {
    "p2p_class",
    "p2p_record_id",
    "p2p_encrypted_body",
    "p2p_expires_at",
    "p2p_anti_replay_nonce",
    "p2p_protocol_version",
}
COMPACT_P2P_RENDEZVOUS_QR_FIELDS = {"pc", "prid", "peb", "px", "pn", "pv"}
OPAQUE_ROUTE_VALUE_MAX_CHARS = 512
OPAQUE_ROUTE_BODY_MAX_CHARS = 2048
PAIRING_QR_NO_WHITESPACE_FIELDS = {
    "pairing_nonce",
    "nonce",
    "n",
    "runtime_device_id",
    "mac_device_id",
    "device_id",
    "rid",
    "runtime_public_key",
    "mac_public_key",
    "public_key",
    "rk",
    "runtime_key_fingerprint",
    "fingerprint",
    "cert_fingerprint",
    "rf",
    "route_token",
    "discovery_token",
    "rt",
    "relay_id",
    "remote_id",
    "route_id",
    "rendezvous_id",
    "network_id",
    "ri",
    "relay_nonce",
    "remote_nonce",
    "route_nonce",
    "rendezvous_nonce",
    "rrn",
}
PAIRING_QR_OPAQUE_VALUE_FIELDS = {
    "route_token",
    "discovery_token",
    "rt",
    "relay_id",
    "remote_id",
    "route_id",
    "rendezvous_id",
    "network_id",
    "ri",
    "relay_nonce",
    "remote_nonce",
    "route_nonce",
    "rendezvous_nonce",
    "rrn",
    "p2p_record_id",
    "prid",
    "p2p_anti_replay_nonce",
    "pn",
}
PAIRING_QR_OPAQUE_SECRET_FIELDS = {
    "relay_secret",
    "remote_secret",
    "route_secret",
    "rendezvous_secret",
    "rs",
}
PAIRING_QR_OPAQUE_BODY_FIELDS = {
    "p2p_encrypted_body",
    "peb",
}
ROUTE_REFRESH_OPAQUE_VALUE_FIELDS = {
    "runtime_device_id",
    "runtime_key_fingerprint",
    "relay_id",
    "relay_nonce",
    "p2p_record_id",
    "p2p_anti_replay_nonce",
}
ROUTE_REFRESH_OPAQUE_SECRET_FIELDS = {"relay_secret"}
ROUTE_REFRESH_OPAQUE_BODY_FIELDS = {"p2p_encrypted_body"}
PRIVATE_OVERLAY_RELAY_HOST_PATTERNS = [
    "^10\\.",
    "^100\\.",
    "^172\\.",
    "^192\\.168\\.",
    "f[c-d]",
]
LOOPBACK_RELAY_HOST_ENUMS = [
    "localhost",
    "127.0.0.1",
    "::1",
    "[::1]",
    "0:0:0:0:0:0:0:1",
    "[0:0:0:0:0:0:0:1]",
]
LOOPBACK_RELAY_HOST_PATTERNS = [
    "^127\\.",
]
ROUTE_REFRESH_RELAY_HOST_FORBIDDEN_ENUMS = [
    "0.0.0.0",
    "::",
    "[::]",
    "255.255.255.255",
]
ROUTE_REFRESH_RELAY_HOST_FORBIDDEN_PATTERNS = [
    "://",
    "[/?#@]",
    "^0\\.",
    "^169\\.254\\.",
    "^(22[4-9]|23[0-9]|24[0-9]|25[0-5])\\.",
    "^(\\[)?fe80:",
    "(^|\\.)local$",
]
PAIRING_QR_REMOTE_RELAY_SCOPE_FIELDS = ["relay_scope", "remote_scope", "route_scope", "rsc"]
PAIRING_QR_ALLOWED_SERVICE_TYPES = [
    "_aetherlink._tcp.",
    "_aetherlink._tcp.local.",
    "_localagentbridge._tcp.",
    "_localagentbridge._tcp.local.",
]


def reserved_future_message_types(message_types: list[str] | tuple[str, ...]) -> list[str]:
    return [
        message_type
        for message_type in message_types
        if message_type.startswith(RESERVED_PREFIXES)
        and message_type not in ALLOWED_INDEX_TYPES
        and message_type not in ALLOWED_RETRIEVAL_TYPES
        and message_type not in ALLOWED_CITATION_TYPES
        and message_type not in ALLOWED_SOURCE_ANCHOR_TYPES
        and message_type not in ALLOWED_TRUSTED_SOURCE_TYPES
        and message_type not in ALLOWED_RESEARCH_TYPES
    ]


def check_protocol_schema_rejects_reserved_future_runtime_namespaces() -> list[str]:
    failures: list[str] = []
    missing_prefixes = sorted(REQUIRED_RESERVED_PREFIXES - set(RESERVED_PREFIXES))
    if missing_prefixes:
        failures.append(f"reserved protocol prefixes missing {missing_prefixes}")

    synthetic_reserved = reserved_future_message_types([
        "skills.run",
        "mcp.tool.call",
        "web_search.query",
        "python.run",
        "python.exec",
        "projects.sessions.list",
        "automation.runs.create",
        "permission.request",
        "approval.prompt",
        "audit.events.list",
        "file.read",
        "file.write",
        "file.index",
        "terminal.exec",
        "terminal.kill",
        "network.request",
        "network.open",
        "backend.call",
        "backend.configure",
        "embeddings.create",
        "index.build",
        "research.brief.create",
        "research.notebooks.list",
        "research.web.query",
        "citation.sources.list",
        "citation.resolve",
        "source_anchor.resolve",
        "source_anchor.metadata.get",
        "trusted_source.approve",
        "trusted_source.dismiss",
        "trusted_source.list",
        "trusted_source.revoke",
        "trusted_source.metadata.get",
        "source_control.status",
        "p2p.session.open",
        "rendezvous.records.publish",
        "bootstrap.records.lookup",
        "dht.records.put",
        "nat.candidates.gather",
        "stun.binding.request",
        "turn.relay.allocate",
        "session.key.exchange",
        "key_exchange.begin",
        "encrypted_session.open",
        "anti_replay.window.commit",
        "transport.handshake",
        "transport.rekey",
        "crypto.session.open",
        "crypto.key.rotate",
    ])
    if synthetic_reserved != [
        "skills.run",
        "mcp.tool.call",
        "web_search.query",
        "python.run",
        "python.exec",
        "projects.sessions.list",
        "automation.runs.create",
        "permission.request",
        "approval.prompt",
        "audit.events.list",
        "file.read",
        "file.write",
        "file.index",
        "terminal.exec",
        "terminal.kill",
        "network.request",
        "network.open",
        "backend.call",
        "backend.configure",
        "embeddings.create",
        "index.build",
        "research.web.query",
        "citation.sources.list",
        "source_anchor.metadata.get",
        "trusted_source.metadata.get",
        "source_control.status",
        "p2p.session.open",
        "rendezvous.records.publish",
        "bootstrap.records.lookup",
        "dht.records.put",
        "nat.candidates.gather",
        "stun.binding.request",
        "turn.relay.allocate",
        "session.key.exchange",
        "key_exchange.begin",
        "encrypted_session.open",
        "anti_replay.window.commit",
        "transport.handshake",
        "transport.rekey",
        "crypto.session.open",
        "crypto.key.rotate",
    ]:
        failures.append(
            "reserved protocol namespace guard must reject skills.*, mcp.*, web_search.*, "
            "python.*, projects.*, automation.*, permission.*, approval.*, audit.*, "
            "file.*, terminal.*, network.*, backend.*, embeddings.*, "
            "unsupported retrieval.* beyond retrieval.query, unsupported index.*, "
            "unsupported research.* beyond research.brief.create/research.notebooks.list, unsupported citation.* beyond citation.resolve, unsupported source_anchor.* beyond source_anchor.resolve, unsupported trusted_source.* beyond approve/dismiss/list/revoke, source_control.*, p2p.*, rendezvous.*, "
            "bootstrap.*, dht.*, nat.*, stun.*, turn.*, session.*, key_exchange.*, "
            "encrypted_session.*, anti_replay.*, transport.*, and crypto.* message names"
        )

    return failures


def future_memory_message_types(message_types: list[str] | tuple[str, ...]) -> list[str]:
    return [
        message_type
        for message_type in message_types
        if message_type.startswith("memory.") and message_type not in ALLOWED_MEMORY_TYPES
    ]


def check_protocol_schema_rejects_future_memory_namespaces() -> list[str]:
    failures: list[str] = []
    synthetic_memory_types = future_memory_message_types([
        "memory.list",
        "memory.upsert",
        "memory.duplicate_suggestions.list",
        "memory.semantic_duplicate_suggestions.list",
        "memory.semantic_duplicate_clusters.list",
        "memory.summary.drafts.list",
        "memory.summary.draft.generate",
        "memory.search",
        "memory.reflect",
    ])
    if synthetic_memory_types != ["memory.search", "memory.reflect"]:
        failures.append(
            "memory namespace guard must allow only documented active memory.* messages "
            "while future advanced memory messages stay reserved"
        )
    return failures


def future_tool_message_types(message_types: list[str] | tuple[str, ...]) -> list[str]:
    return [
        message_type
        for message_type in message_types
        if message_type.startswith("tool.") and message_type not in ALLOWED_TOOL_TYPES
    ]


def check_protocol_schema_rejects_future_tool_namespaces() -> list[str]:
    failures: list[str] = []
    synthetic_tool_types = future_tool_message_types([
        "tool.call",
        "tool.result",
        "tool.run",
    ])
    if synthetic_tool_types != ["tool.call", "tool.result", "tool.run"]:
        failures.append(
            "protocol tool namespace guard must reject tool.call, tool.result, and tool.run "
            "until runtime tool permissions, execution, result handling, and audit semantics are designed"
        )
    return failures


def check_protocol_schema_rejects_future_route_namespaces() -> list[str]:
    failures: list[str] = []
    synthetic_route_types = [
        "route.refresh",
        "route.candidates.exchange",
        "route.diagnostics.report",
        "route.allocation.status",
        "route.failure.report",
    ]
    unsupported_route_types = [
        message_type
        for message_type in synthetic_route_types
        if message_type.startswith("route.") and message_type not in ALLOWED_ROUTE_TYPES
    ]
    if unsupported_route_types != [
        "route.candidates.exchange",
        "route.diagnostics.report",
        "route.allocation.status",
        "route.failure.report",
    ]:
        failures.append(
            "route namespace guard must allow only route.refresh while future route.* messages stay reserved"
        )
    return failures


def check_chat_attachment_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatAttachment schema"]
    chat_attachment = defs.get("chatAttachment")
    if not isinstance(chat_attachment, dict):
        return ["$defs.chatAttachment schema is missing"]

    properties = chat_attachment.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.chatAttachment.properties must be an object")
    else:
        allowed_keys = {"type", "mime_type", "name", "data_base64", "text"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatAttachment.properties must stay limited to type, mime_type, name, data_base64, and text"
            )
        forbidden_keys = {
            "source_path",
            "file_path",
            "workspace_id",
            "source_control_status",
            "backend_url",
            "backend_credentials",
            "route_token",
            "trusted_source",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatAttachment.properties includes future source/workspace/backend metadata "
                f"{leaked_keys}"
            )
    if chat_attachment.get("additionalProperties") is not False:
        failures.append("$defs.chatAttachment.additionalProperties must be false")
    return failures


def schema_max_length(schema: object) -> int | None:
    if not isinstance(schema, dict):
        return None
    direct_max_length = schema.get("maxLength")
    if isinstance(direct_max_length, int) and not isinstance(direct_max_length, bool):
        return direct_max_length
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for schema_part in all_of:
            nested_max_length = schema_max_length(schema_part)
            if nested_max_length is not None:
                return nested_max_length
    return None


def schema_pattern(schema: object) -> str | None:
    if not isinstance(schema, dict):
        return None
    direct_pattern = schema.get("pattern")
    if isinstance(direct_pattern, str):
        return direct_pattern
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for schema_part in all_of:
            nested_pattern = schema_pattern(schema_part)
            if nested_pattern is not None:
                return nested_pattern
    return None


def check_index_documents_list_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include indexDocumentsListPayload schema"]

    index_document = defs.get("indexDocument")
    if not isinstance(index_document, dict):
        failures.append("$defs.indexDocument schema is missing")
    else:
        document_properties = index_document.get("properties")
        allowed_index_document_properties = {
            "id",
            "display_name",
            "mime_type",
            "content_fingerprint",
            "extracted_character_count",
            "chunk_count",
            "quality",
        }
        expected_index_document_property_schemas = {
            "id": {"allOf": [{"$ref": "#/$defs/nonEmptyString"}, {"maxLength": 128}]},
            "display_name": {"allOf": [{"$ref": "#/$defs/nonEmptyString"}, {"maxLength": 256}]},
            "mime_type": {
                "allOf": [
                    {"$ref": "#/$defs/nonEmptyString"},
                    {"maxLength": 128},
                    {"pattern": INDEX_DOCUMENT_MIME_TYPE_PATTERN},
                ]
            },
            "content_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{16}$"},
            "extracted_character_count": {"type": "integer", "minimum": 0},
            "chunk_count": {"type": "integer", "minimum": 0},
            "quality": {"enum": ["no_usable_text", "single_chunk", "chunked"]},
        }
        if not isinstance(document_properties, dict):
            failures.append("$defs.indexDocument.properties must be an object")
        else:
            if set(document_properties.keys()) != allowed_index_document_properties:
                failures.append(
                    "$defs.indexDocument properties must stay limited to id, display_name, mime_type, content_fingerprint, extracted_character_count, chunk_count, and quality"
                )
            for field_name, expected_schema in expected_index_document_property_schemas.items():
                if document_properties.get(field_name) != expected_schema:
                    failures.append(f"$defs.indexDocument.properties.{field_name} has drifted")

        document_required = index_document.get("required")
        if not isinstance(document_required, list):
            failures.append("$defs.indexDocument.required must be a list")
        elif set(document_required) != allowed_index_document_properties:
            failures.append(
                "$defs.indexDocument.required must stay limited to id, display_name, mime_type, content_fingerprint, extracted_character_count, chunk_count, and quality"
            )
        expected_index_document_quality_chunk_count_consistency = [
            {
                "if": {
                    "properties": {"chunk_count": {"const": 0}},
                    "required": ["chunk_count"],
                },
                "then": {
                    "properties": {"quality": {"const": "no_usable_text"}},
                },
            },
            {
                "if": {
                    "properties": {"chunk_count": {"const": 1}},
                    "required": ["chunk_count"],
                },
                "then": {
                    "properties": {"quality": {"const": "single_chunk"}},
                },
            },
            {
                "if": {
                    "properties": {"chunk_count": {"type": "integer", "minimum": 2}},
                    "required": ["chunk_count"],
                },
                "then": {
                    "properties": {"quality": {"const": "chunked"}},
                },
            },
        ]
        if index_document.get("allOf") != expected_index_document_quality_chunk_count_consistency:
            failures.append(
                "$defs.indexDocument allOf must bind chunk_count 0/1/2+ to no_usable_text/single_chunk/chunked quality"
            )
        if index_document.get("additionalProperties") is not False:
            failures.append("$defs.indexDocument additionalProperties must be false")

    index_summary = defs.get("indexDocumentsSummary")
    if not isinstance(index_summary, dict):
        failures.append("$defs.indexDocumentsSummary schema is missing")
    else:
        summary_properties = index_summary.get("properties")
        allowed_summary_properties = {
            "document_count",
            "chunk_count",
            "extracted_character_count",
            "quality_counts",
        }
        expected_quality_counts_schema = {
            "type": "object",
            "required": ["no_usable_text", "single_chunk", "chunked"],
            "properties": {
                "no_usable_text": {"type": "integer", "minimum": 0},
                "single_chunk": {"type": "integer", "minimum": 0},
                "chunked": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        }
        expected_summary_property_schemas = {
            "document_count": {"type": "integer", "minimum": 0},
            "chunk_count": {"type": "integer", "minimum": 0},
            "extracted_character_count": {"type": "integer", "minimum": 0},
            "quality_counts": expected_quality_counts_schema,
        }
        if not isinstance(summary_properties, dict):
            failures.append("$defs.indexDocumentsSummary.properties must be an object")
        else:
            if set(summary_properties.keys()) != allowed_summary_properties:
                failures.append(
                    "$defs.indexDocumentsSummary properties must stay limited to document_count, chunk_count, extracted_character_count, and quality_counts"
                )
            for field_name, expected_schema in expected_summary_property_schemas.items():
                if summary_properties.get(field_name) != expected_schema:
                    failures.append(f"$defs.indexDocumentsSummary.properties.{field_name} has drifted")

        summary_required = index_summary.get("required")
        if not isinstance(summary_required, list):
            failures.append("$defs.indexDocumentsSummary.required must be a list")
        elif set(summary_required) != allowed_summary_properties:
            failures.append(
                "$defs.indexDocumentsSummary.required must stay limited to document_count, chunk_count, extracted_character_count, and quality_counts"
            )
        if index_summary.get("additionalProperties") is not False:
            failures.append("$defs.indexDocumentsSummary additionalProperties must be false")

    index_payload = defs.get("indexDocumentsListPayload")
    if not isinstance(index_payload, dict):
        failures.append("$defs.indexDocumentsListPayload schema is missing")
    else:
        variants = index_payload.get("oneOf")
        if not isinstance(variants, list) or len(variants) != 2:
            failures.append("$defs.indexDocumentsListPayload must keep separate request and response variants")
        else:
            request_variant = variants[0]
            if not isinstance(request_variant, dict):
                failures.append("$defs.indexDocumentsListPayload request variant must be an object")
            else:
                request_properties = request_variant.get("properties")
                if not isinstance(request_properties, dict):
                    failures.append("$defs.indexDocumentsListPayload request properties must be an object")
                else:
                    allowed_index_request_properties = {"limit"}
                    if set(request_properties.keys()) != allowed_index_request_properties:
                        failures.append(
                            "$defs.indexDocumentsListPayload request properties must stay limited to limit"
                        )
                    if request_properties.get("limit") != {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    }:
                        failures.append(
                            "$defs.indexDocumentsListPayload request limit must be an integer between 0 and 100"
                        )
                    if "documents" in request_properties or "summary" in request_properties:
                        failures.append(
                            "$defs.indexDocumentsListPayload request properties must not accept response-only catalog fields"
                        )

                    canonical_index_documents_request_payload_samples = (
                        ("empty-request", build_index_documents_list_request_sample(include_limit=False)),
                        ("bounded-limit", build_index_documents_list_request_sample(limit=25)),
                    )
                    for label, payload_sample in canonical_index_documents_request_payload_samples:
                        for sample_failure in index_documents_list_request_sample_failures(
                            payload_sample,
                            request_variant,
                        ):
                            failures.append(
                                "$defs.indexDocumentsListPayload request sample must accept "
                                f"{label}: {sample_failure}"
                            )

                    rejected_index_documents_request_payload_samples = (
                        ("string-limit", build_index_documents_list_request_sample(limit="25")),
                        ("float-limit", build_index_documents_list_request_sample(limit=25.5)),
                        ("bool-limit", build_index_documents_list_request_sample(limit=True)),
                        ("negative-limit", build_index_documents_list_request_sample(limit=-1)),
                        ("over-limit", build_index_documents_list_request_sample(limit=101)),
                        (
                            "response-documents",
                            build_index_documents_list_request_sample(
                                extra_fields={"documents": []}
                            ),
                        ),
                        (
                            "response-summary",
                            build_index_documents_list_request_sample(
                                extra_fields={"summary": build_index_documents_summary_sample()}
                            ),
                        ),
                        (
                            "unknown-request-metadata",
                            build_index_documents_list_request_sample(
                                extra_fields={"source_path": "/private/source.txt"}
                            ),
                        ),
                    )
                    for label, payload_sample in rejected_index_documents_request_payload_samples:
                        if not index_documents_list_request_sample_failures(
                            payload_sample,
                            request_variant,
                        ):
                            failures.append(
                                "$defs.indexDocumentsListPayload request sample must reject "
                                f"{label}"
                            )

                if request_variant.get("additionalProperties") is not False:
                    failures.append(
                        "$defs.indexDocumentsListPayload request additionalProperties must be false"
                    )

            response_variant = variants[1]
            if not isinstance(response_variant, dict):
                failures.append("$defs.indexDocumentsListPayload response variant must be an object")
            else:
                response_required = response_variant.get("required")
                if not isinstance(response_required, list):
                    failures.append("$defs.indexDocumentsListPayload response required must be a list")
                elif set(response_required) != {"documents", "summary"}:
                    failures.append(
                        "$defs.indexDocumentsListPayload response required must stay limited to documents and summary"
                    )

                response_properties = response_variant.get("properties")
                if not isinstance(response_properties, dict):
                    failures.append("$defs.indexDocumentsListPayload response properties must be an object")
                else:
                    if set(response_properties.keys()) != {"documents", "summary"}:
                        failures.append(
                            "$defs.indexDocumentsListPayload response properties must stay limited to documents and summary"
                        )
                    documents_schema = response_properties.get("documents")
                    if not isinstance(documents_schema, dict):
                        failures.append(
                            "$defs.indexDocumentsListPayload response properties.documents must be an object"
                        )
                    else:
                        if documents_schema.get("type") != "array":
                            failures.append(
                                "$defs.indexDocumentsListPayload response documents must be an array"
                            )
                        if documents_schema.get("maxItems") != 100:
                            failures.append(
                                "$defs.indexDocumentsListPayload response documents must set maxItems 100"
                            )
                        if documents_schema.get("items") != {"$ref": "#/$defs/indexDocument"}:
                            failures.append(
                                "$defs.indexDocumentsListPayload response documents.items must use #/$defs/indexDocument"
                            )
                    if response_properties.get("summary") != {
                        "$ref": "#/$defs/indexDocumentsSummary"
                    }:
                        failures.append(
                            "$defs.indexDocumentsListPayload response summary must use #/$defs/indexDocumentsSummary"
                        )

                if response_variant.get("additionalProperties") is not False:
                    failures.append(
                        "$defs.indexDocumentsListPayload response additionalProperties must be false"
                    )

                if isinstance(index_document, dict) and isinstance(index_summary, dict):
                    canonical_index_documents_response_payload_sample = (
                        build_index_documents_list_response_sample()
                    )
                    for sample_failure in index_documents_list_response_sample_failures(
                        canonical_index_documents_response_payload_sample,
                        response_variant,
                        index_document,
                        index_summary,
                    ):
                        failures.append(
                            "$defs.indexDocumentsListPayload response sample must accept "
                            f"canonical catalog payload: {sample_failure}"
                        )

                    rejected_index_documents_response_payload_samples = (
                        (
                            "unknown-response-metadata",
                            build_index_documents_list_response_sample(
                                payload_overrides={"embedding_model_id": "future-embedder"}
                            ),
                        ),
                        (
                            "missing-documents",
                            build_index_documents_list_response_sample(
                                omit_payload_fields=("documents",)
                            ),
                        ),
                        (
                            "missing-summary",
                            build_index_documents_list_response_sample(
                                omit_payload_fields=("summary",)
                            ),
                        ),
                        (
                            "documents-not-array",
                            build_index_documents_list_response_sample(
                                payload_overrides={"documents": "not-array"}
                            ),
                        ),
                        (
                            "over-documents",
                            build_index_documents_list_response_sample(document_count=101),
                        ),
                        (
                            "unknown-document-metadata",
                            build_index_documents_list_response_sample(
                                document_overrides={"source_path": "/private/source.txt"}
                            ),
                        ),
                        (
                            "missing-document-quality",
                            build_index_documents_list_response_sample(
                                omit_document_fields=("quality",)
                            ),
                        ),
                        (
                            "empty-document-display-name",
                            build_index_documents_list_response_sample(
                                document_overrides={"display_name": ""}
                            ),
                        ),
                        (
                            "overlong-document-id",
                            build_index_documents_list_response_sample(
                                document_overrides={"id": "d" * 129}
                            ),
                        ),
                        (
                            "overlong-document-display-name",
                            build_index_documents_list_response_sample(
                                document_overrides={"display_name": "d" * 257}
                            ),
                        ),
                        (
                            "overlong-document-mime-type",
                            build_index_documents_list_response_sample(
                                document_overrides={"mime_type": "text/" + ("a" * 124)}
                            ),
                        ),
                        (
                            "whitespace-document-mime-type",
                            build_index_documents_list_response_sample(
                                document_overrides={"mime_type": " text/plain\n"}
                            ),
                        ),
                        (
                            "uppercase-document-mime-type",
                            build_index_documents_list_response_sample(
                                document_overrides={"mime_type": "Text/markdown"}
                            ),
                        ),
                        (
                            "missing-slash-document-mime-type",
                            build_index_documents_list_response_sample(
                                document_overrides={"mime_type": "textplain"}
                            ),
                        ),
                        (
                            "parameterized-document-mime-type",
                            build_index_documents_list_response_sample(
                                document_overrides={"mime_type": "text/plain; charset=utf-8"}
                            ),
                        ),
                        (
                            "url-shaped-document-mime-type",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "mime_type": "https://example.invalid/text/plain"
                                }
                            ),
                        ),
                        (
                            "empty-document-content-fingerprint",
                            build_index_documents_list_response_sample(
                                document_overrides={"content_fingerprint": ""}
                            ),
                        ),
                        (
                            "whitespace-document-content-fingerprint",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "content_fingerprint": " 0011223344556677\n"
                                }
                            ),
                        ),
                        (
                            "uppercase-document-content-fingerprint",
                            build_index_documents_list_response_sample(
                                document_overrides={"content_fingerprint": "001122334455667A"}
                            ),
                        ),
                        (
                            "short-document-content-fingerprint",
                            build_index_documents_list_response_sample(
                                document_overrides={"content_fingerprint": "001122334455667"}
                            ),
                        ),
                        (
                            "long-document-content-fingerprint",
                            build_index_documents_list_response_sample(
                                document_overrides={"content_fingerprint": "00112233445566770"}
                            ),
                        ),
                        (
                            "nonhex-document-content-fingerprint",
                            build_index_documents_list_response_sample(
                                document_overrides={"content_fingerprint": "001122334455667g"}
                            ),
                        ),
                        (
                            "invalid-document-quality",
                            build_index_documents_list_response_sample(
                                document_overrides={"quality": "trusted_source"}
                            ),
                        ),
                        (
                            "zero-chunk-document-quality-mismatch",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "chunk_count": 0,
                                    "quality": "chunked",
                                }
                            ),
                        ),
                        (
                            "zero-chunk-single-document-quality-mismatch",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "chunk_count": 0,
                                    "quality": "single_chunk",
                                }
                            ),
                        ),
                        (
                            "single-chunk-document-quality-mismatch",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "chunk_count": 1,
                                    "quality": "no_usable_text",
                                }
                            ),
                        ),
                        (
                            "single-chunk-chunked-document-quality-mismatch",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "chunk_count": 1,
                                    "quality": "chunked",
                                }
                            ),
                        ),
                        (
                            "multi-chunk-document-quality-mismatch",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "chunk_count": 2,
                                    "quality": "single_chunk",
                                }
                            ),
                        ),
                        (
                            "multi-chunk-no-usable-document-quality-mismatch",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "chunk_count": 2,
                                    "quality": "no_usable_text",
                                }
                            ),
                        ),
                        (
                            "three-chunk-single-document-quality-mismatch",
                            build_index_documents_list_response_sample(
                                document_overrides={
                                    "chunk_count": 3,
                                    "quality": "single_chunk",
                                }
                            ),
                        ),
                        (
                            "string-document-chunk-count",
                            build_index_documents_list_response_sample(
                                document_overrides={"chunk_count": "1"}
                            ),
                        ),
                        (
                            "negative-document-extracted-character-count",
                            build_index_documents_list_response_sample(
                                document_overrides={"extracted_character_count": -1}
                            ),
                        ),
                        (
                            "unknown-summary-metadata",
                            build_index_documents_list_response_sample(
                                summary_overrides={"retrieval_context": "future context"}
                            ),
                        ),
                        (
                            "string-summary-document-count",
                            build_index_documents_list_response_sample(
                                summary_overrides={"document_count": "1"}
                            ),
                        ),
                        (
                            "negative-summary-chunk-count",
                            build_index_documents_list_response_sample(
                                summary_overrides={"chunk_count": -1}
                            ),
                        ),
                        (
                            "quality-counts-not-object",
                            build_index_documents_list_response_sample(
                                summary_overrides={"quality_counts": "not-object"}
                            ),
                        ),
                        (
                            "missing-no-usable-text-quality-count",
                            build_index_documents_list_response_sample(
                                omit_quality_counts_fields=("no_usable_text",)
                            ),
                        ),
                        (
                            "missing-single-chunk-quality-count",
                            build_index_documents_list_response_sample(
                                omit_quality_counts_fields=("single_chunk",)
                            ),
                        ),
                        (
                            "missing-chunked-quality-count",
                            build_index_documents_list_response_sample(
                                omit_quality_counts_fields=("chunked",)
                            ),
                        ),
                        (
                            "unknown-quality-count",
                            build_index_documents_list_response_sample(
                                quality_counts_overrides={"trusted_source": 1}
                            ),
                        ),
                        (
                            "string-quality-count",
                            build_index_documents_list_response_sample(
                                quality_counts_overrides={"chunked": "1"}
                            ),
                        ),
                        (
                            "negative-quality-count",
                            build_index_documents_list_response_sample(
                                quality_counts_overrides={"single_chunk": -1}
                            ),
                        ),
                    )
                    for label, payload_sample in rejected_index_documents_response_payload_samples:
                        if not index_documents_list_response_sample_failures(
                            payload_sample,
                            response_variant,
                            index_document,
                            index_summary,
                        ):
                            failures.append(
                                "$defs.indexDocumentsListPayload response sample must reject "
                                f"{label}"
                            )

    return failures


def build_index_documents_list_request_sample(
    *,
    include_limit: bool = True,
    limit: object = 25,
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if include_limit:
        payload["limit"] = limit
    if extra_fields is not None:
        payload.update(extra_fields)
    return payload


def build_index_document_sample(
    *,
    document_overrides: dict[str, object] | None = None,
    omit_document_fields: tuple[str, ...] = (),
) -> dict[str, object]:
    document: dict[str, object] = {
        "id": "protocol-index-sample",
        "display_name": "Protocol Index Sample",
        "mime_type": "text/plain",
        "content_fingerprint": "0011223344556677",
        "extracted_character_count": 64,
        "chunk_count": 2,
        "quality": "chunked",
    }
    if document_overrides is not None:
        document.update(document_overrides)
    for field_name in omit_document_fields:
        document.pop(field_name, None)
    return document


def build_index_documents_summary_sample(
    *,
    summary_overrides: dict[str, object] | None = None,
    quality_counts_overrides: dict[str, object] | None = None,
    omit_quality_counts_fields: tuple[str, ...] = (),
) -> dict[str, object]:
    quality_counts: dict[str, object] = {
        "no_usable_text": 0,
        "single_chunk": 0,
        "chunked": 1,
    }
    if quality_counts_overrides is not None:
        quality_counts.update(quality_counts_overrides)
    for field_name in omit_quality_counts_fields:
        quality_counts.pop(field_name, None)
    summary: dict[str, object] = {
        "document_count": 1,
        "chunk_count": 2,
        "extracted_character_count": 64,
        "quality_counts": quality_counts,
    }
    if summary_overrides is not None:
        summary.update(summary_overrides)
    return summary


def build_index_documents_list_response_sample(
    *,
    payload_overrides: dict[str, object] | None = None,
    document_overrides: dict[str, object] | None = None,
    summary_overrides: dict[str, object] | None = None,
    quality_counts_overrides: dict[str, object] | None = None,
    omit_quality_counts_fields: tuple[str, ...] = (),
    omit_payload_fields: tuple[str, ...] = (),
    omit_document_fields: tuple[str, ...] = (),
    document_count: int = 1,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "documents": [
            build_index_document_sample(
                document_overrides=document_overrides,
                omit_document_fields=omit_document_fields,
            )
            for _ in range(document_count)
        ],
        "summary": build_index_documents_summary_sample(
            summary_overrides=summary_overrides,
            quality_counts_overrides=quality_counts_overrides,
            omit_quality_counts_fields=omit_quality_counts_fields,
        ),
    }
    if payload_overrides is not None:
        payload.update(payload_overrides)
    for field_name in omit_payload_fields:
        payload.pop(field_name, None)
    return payload


def index_documents_list_request_sample_failures(
    payload: object,
    request_variant: dict[str, object],
) -> list[str]:
    if not isinstance(payload, dict):
        return ["index.documents.list request payload sample must be an object"]

    properties = request_variant.get("properties")
    if not isinstance(properties, dict):
        return ["index.documents.list request variant properties must be an object"]

    failures: list[str] = []
    unknown_fields = sorted(set(payload) - set(properties))
    if unknown_fields:
        failures.append(
            "index.documents.list request payload sample includes unknown fields: "
            + ", ".join(unknown_fields)
        )

    if "limit" in payload:
        value = payload.get("limit")
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append("index.documents.list request payload sample limit must be an integer")
        else:
            limit_schema = properties.get("limit")
            if isinstance(limit_schema, dict):
                minimum = limit_schema.get("minimum")
                if isinstance(minimum, int) and value < minimum:
                    failures.append("index.documents.list request payload sample limit below minimum")
                maximum = limit_schema.get("maximum")
                if isinstance(maximum, int) and value > maximum:
                    failures.append("index.documents.list request payload sample limit above maximum")

    return failures


def index_documents_list_response_sample_failures(
    payload: object,
    response_variant: dict[str, object],
    document_schema: dict[str, object],
    summary_schema: dict[str, object],
) -> list[str]:
    if not isinstance(payload, dict):
        return ["index.documents.list response payload sample must be an object"]

    response_properties = response_variant.get("properties")
    if not isinstance(response_properties, dict):
        return ["index.documents.list response variant properties must be an object"]

    response_required = response_variant.get("required")
    if not isinstance(response_required, list):
        return ["index.documents.list response variant required fields must be a list"]

    failures: list[str] = []
    unknown_fields = sorted(set(payload) - set(response_properties))
    if unknown_fields:
        failures.append(
            "index.documents.list response payload sample includes unknown fields: "
            + ", ".join(unknown_fields)
        )

    for field_name in response_required:
        if isinstance(field_name, str) and field_name not in payload:
            failures.append(f"index.documents.list response payload sample missing {field_name}")

    documents = payload.get("documents")
    if "documents" in payload:
        if not isinstance(documents, list):
            failures.append("index.documents.list response payload sample documents must be an array")
        else:
            documents_schema = response_properties.get("documents")
            documents_max_items = (
                documents_schema.get("maxItems")
                if isinstance(documents_schema, dict)
                and isinstance(documents_schema.get("maxItems"), int)
                else None
            )
            if isinstance(documents_max_items, int) and len(documents) > documents_max_items:
                failures.append(
                    "index.documents.list response payload sample documents above maximum items"
                )
            for index, document in enumerate(documents):
                failures.extend(index_document_sample_failures(document, document_schema, index))

    summary = payload.get("summary")
    if "summary" in payload:
        failures.extend(index_documents_summary_sample_failures(summary, summary_schema))

    return failures


def index_document_sample_failures(
    document: object,
    document_schema: dict[str, object],
    index: int,
    *,
    path: str | None = None,
) -> list[str]:
    document_path = path or f"documents[{index}]"
    if not isinstance(document, dict):
        return [f"{document_path} must be an object"]

    properties = document_schema.get("properties")
    if not isinstance(properties, dict):
        return ["index.documents.list document schema properties must be an object"]

    required = document_schema.get("required")
    if not isinstance(required, list):
        return ["index.documents.list document schema required fields must be a list"]

    failures: list[str] = []
    unknown_fields = sorted(set(document) - set(properties))
    if unknown_fields:
        failures.append(
            f"{document_path} includes unknown fields: " + ", ".join(unknown_fields)
        )

    for field_name in required:
        if isinstance(field_name, str) and field_name not in document:
            failures.append(f"{document_path} missing {field_name}")

    for string_field_name in ("id", "display_name", "mime_type", "content_fingerprint"):
        if string_field_name not in document:
            continue
        value = document.get(string_field_name)
        if not isinstance(value, str) or not value:
            failures.append(f"{document_path}.{string_field_name} must be a non-empty string")
            continue
        max_length = schema_max_length(properties.get(string_field_name))
        if (
            string_field_name in {"id", "display_name", "mime_type"}
            and isinstance(max_length, int)
            and len(value) > max_length
        ):
            failures.append(f"{document_path}.{string_field_name} above maximum length")
        if string_field_name == "mime_type":
            mime_type_pattern = schema_pattern(properties.get("mime_type"))
            if isinstance(mime_type_pattern, str):
                try:
                    compiled_mime_type_pattern = re.compile(mime_type_pattern)
                except re.error:
                    failures.append("index.documents.list document mime_type pattern is invalid")
                else:
                    if not compiled_mime_type_pattern.fullmatch(value):
                        failures.append(
                            f"{document_path}.mime_type must match lowercase type/subtype token"
                        )

    content_fingerprint = document.get("content_fingerprint")
    if isinstance(content_fingerprint, str) and content_fingerprint:
        content_fingerprint_schema = properties.get("content_fingerprint")
        content_fingerprint_pattern = (
            content_fingerprint_schema.get("pattern")
            if isinstance(content_fingerprint_schema, dict)
            and isinstance(content_fingerprint_schema.get("pattern"), str)
            else None
        )
        if isinstance(content_fingerprint_pattern, str):
            try:
                compiled_content_fingerprint_pattern = re.compile(content_fingerprint_pattern)
            except re.error:
                failures.append("index.documents.list document content_fingerprint pattern is invalid")
            else:
                if not compiled_content_fingerprint_pattern.fullmatch(content_fingerprint):
                    failures.append(
                        f"{document_path}.content_fingerprint must match 16 lowercase hex"
                    )

    for integer_field_name in ("extracted_character_count", "chunk_count"):
        if integer_field_name not in document:
            continue
        value = document.get(integer_field_name)
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append(f"{document_path}.{integer_field_name} must be an integer")
            continue
        field_schema = properties.get(integer_field_name)
        if isinstance(field_schema, dict):
            minimum = field_schema.get("minimum")
            if isinstance(minimum, int) and value < minimum:
                failures.append(f"{document_path}.{integer_field_name} below minimum")

    if "quality" in document:
        quality = document.get("quality")
        quality_schema = properties.get("quality")
        allowed_quality_values = (
            quality_schema.get("enum")
            if isinstance(quality_schema, dict) and isinstance(quality_schema.get("enum"), list)
            else []
        )
        if quality not in allowed_quality_values:
            failures.append(f"{document_path}.quality must be a known document quality")
        chunk_count = document.get("chunk_count")
        if (
            isinstance(chunk_count, int)
            and not isinstance(chunk_count, bool)
            and chunk_count >= 0
            and quality in allowed_quality_values
        ):
            expected_quality = (
                "no_usable_text"
                if chunk_count == 0
                else "single_chunk"
                if chunk_count == 1
                else "chunked"
            )
            if quality != expected_quality:
                failures.append(
                    f"{document_path}.quality must match chunk_count-derived document quality"
                )

    return failures


def index_documents_summary_sample_failures(
    summary: object,
    summary_schema: dict[str, object],
) -> list[str]:
    if not isinstance(summary, dict):
        return ["index.documents.list response payload sample summary must be an object"]

    properties = summary_schema.get("properties")
    if not isinstance(properties, dict):
        return ["index.documents.list summary schema properties must be an object"]

    required = summary_schema.get("required")
    if not isinstance(required, list):
        return ["index.documents.list summary schema required fields must be a list"]

    failures: list[str] = []
    unknown_fields = sorted(set(summary) - set(properties))
    if unknown_fields:
        failures.append(
            "index.documents.list summary includes unknown fields: "
            + ", ".join(unknown_fields)
        )

    for field_name in required:
        if isinstance(field_name, str) and field_name not in summary:
            failures.append(f"index.documents.list summary missing {field_name}")

    for integer_field_name in ("document_count", "chunk_count", "extracted_character_count"):
        if integer_field_name not in summary:
            continue
        value = summary.get(integer_field_name)
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append(f"index.documents.list summary {integer_field_name} must be an integer")
            continue
        field_schema = properties.get(integer_field_name)
        if isinstance(field_schema, dict):
            minimum = field_schema.get("minimum")
            if isinstance(minimum, int) and value < minimum:
                failures.append(f"index.documents.list summary {integer_field_name} below minimum")

    quality_counts = summary.get("quality_counts")
    if "quality_counts" in summary:
        quality_counts_schema = properties.get("quality_counts")
        if not isinstance(quality_counts_schema, dict):
            failures.append("index.documents.list summary quality_counts schema must be an object")
        elif not isinstance(quality_counts, dict):
            failures.append("index.documents.list summary quality_counts must be an object")
        else:
            quality_count_properties = quality_counts_schema.get("properties")
            if not isinstance(quality_count_properties, dict):
                failures.append(
                    "index.documents.list summary quality_counts properties must be an object"
                )
            else:
                unknown_quality_counts = sorted(set(quality_counts) - set(quality_count_properties))
                if unknown_quality_counts:
                    failures.append(
                        "index.documents.list summary quality_counts includes unknown fields: "
                        + ", ".join(unknown_quality_counts)
                    )
                required_quality_counts = quality_counts_schema.get("required")
                if not isinstance(required_quality_counts, list):
                    failures.append(
                        "index.documents.list summary quality_counts required fields must be a list"
                    )
                else:
                    for field_name in required_quality_counts:
                        if isinstance(field_name, str) and field_name not in quality_counts:
                            failures.append(
                                f"index.documents.list summary quality_counts missing {field_name}"
                            )
                for field_name, value in quality_counts.items():
                    if field_name not in quality_count_properties:
                        continue
                    if not isinstance(value, int) or isinstance(value, bool):
                        failures.append(
                            f"index.documents.list summary quality_counts.{field_name} must be an integer"
                        )
                        continue
                    field_schema = quality_count_properties.get(field_name)
                    if isinstance(field_schema, dict):
                        minimum = field_schema.get("minimum")
                        if isinstance(minimum, int) and value < minimum:
                            failures.append(
                                f"index.documents.list summary quality_counts.{field_name} below minimum"
                            )

    return failures


def check_retrieval_query_source_anchor_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include retrievalQueryResult schema"]

    index_document = defs.get("indexDocument")
    retrieval_result = defs.get("retrievalQueryResult")
    source_anchor_id = defs.get("sourceAnchorID")
    if source_anchor_id != {
        "type": "string",
        "pattern": "^source_anchor_[0-9a-f]{16}$",
    }:
        failures.append(
            "$defs.sourceAnchorID must pin retrieval.query response anchors to source_anchor_[16 lowercase hex]"
        )
    source_anchor_pattern = (
        source_anchor_id.get("pattern")
        if isinstance(source_anchor_id, dict) and isinstance(source_anchor_id.get("pattern"), str)
        else None
    )
    retrieval_response_results_max_items: int | None = None
    if source_anchor_pattern is not None:
        try:
            compiled_source_anchor_pattern = re.compile(source_anchor_pattern)
        except re.error as error:
            failures.append(f"$defs.sourceAnchorID.pattern must compile: {error}")
        else:
            accepted_source_anchor_samples = (
                "source_anchor_0000000000000000",
                "source_anchor_0123456789abcdef",
                "source_anchor_ffffffffffffffff",
            )
            rejected_source_anchor_samples = (
                " source_anchor_0123456789abcdef",
                "source_anchor_0123456789abcdef ",
                "source_anchor_0123456789abcdef\n",
                "source_anchor_0123456789ABCDEF",
                "source_anchor_0123456789abcde",
                "source_anchor_0123456789abcdeg",
                "source_anchor_0123456789abcdef0",
                "source_anchor_not_a_handle",
                "sourceanchor_0123456789abcdef",
                "",
            )
            for sample in accepted_source_anchor_samples:
                if not compiled_source_anchor_pattern.fullmatch(sample):
                    failures.append(
                        f"$defs.sourceAnchorID.pattern must accept canonical sample {sample!r}"
                    )
            for sample in rejected_source_anchor_samples:
                if compiled_source_anchor_pattern.fullmatch(sample):
                    failures.append(
                        f"$defs.sourceAnchorID.pattern must reject noncanonical sample {sample!r}"
                    )
            canonical_retrieval_query_response_payload_sample = (
                build_retrieval_query_response_source_anchor_sample(
                    "source_anchor_0123456789abcdef"
                )
            )
            for sample_failure in retrieval_query_response_source_anchor_sample_failures(
                canonical_retrieval_query_response_payload_sample,
                compiled_source_anchor_pattern,
                retrieval_result if isinstance(retrieval_result, dict) else {},
                document_schema=index_document if isinstance(index_document, dict) else None,
            ):
                failures.append(
                    "$defs.retrievalQueryPayload response sample must accept canonical "
                    f"source_anchor_id: {sample_failure}"
                )
            rejected_retrieval_query_response_payload_samples = (
                ("missing-source-anchor", None),
                ("whitespace-source-anchor", " source_anchor_0123456789abcdef"),
                ("uppercase-source-anchor", "source_anchor_0123456789ABCDEF"),
                ("short-source-anchor", "source_anchor_0123456789abcde"),
                ("long-source-anchor", "source_anchor_0123456789abcdef0"),
                ("nonhex-source-anchor", "source_anchor_0123456789abcdeg"),
                ("empty-source-anchor", ""),
            )
            for label, source_anchor_sample in rejected_retrieval_query_response_payload_samples:
                payload_sample = build_retrieval_query_response_source_anchor_sample(
                    source_anchor_sample
                )
                if not retrieval_query_response_source_anchor_sample_failures(
                    payload_sample,
                    compiled_source_anchor_pattern,
                    retrieval_result if isinstance(retrieval_result, dict) else {},
                    document_schema=index_document if isinstance(index_document, dict) else None,
                ):
                    failures.append(
                        "$defs.retrievalQueryPayload response sample must reject "
                        f"{label} in results[].source_anchor_id"
                    )

    if not isinstance(retrieval_result, dict):
        failures.append("$defs.retrievalQueryResult schema is missing")
    else:
        result_properties = retrieval_result.get("properties")
        if not isinstance(result_properties, dict):
            failures.append("$defs.retrievalQueryResult.properties must be an object")
        else:
            allowed_result_properties = {
                "document",
                "source_anchor_id",
                "chunk_index",
                "start_character_offset",
                "end_character_offset",
                "rank",
                "matched_terms",
                "match_kind",
                "snippet",
            }
            if set(result_properties.keys()) != allowed_result_properties:
                failures.append(
                    "$defs.retrievalQueryResult properties must stay limited to document, source_anchor_id, chunk_index, start_character_offset, end_character_offset, rank, matched_terms, match_kind, and snippet"
                )
            if result_properties.get("document") != {"$ref": "#/$defs/indexDocument"}:
                failures.append(
                    "$defs.retrievalQueryResult.properties.document must use #/$defs/indexDocument"
                )
            if result_properties.get("source_anchor_id") != {"$ref": "#/$defs/sourceAnchorID"}:
                failures.append(
                    "$defs.retrievalQueryResult.properties.source_anchor_id must use #/$defs/sourceAnchorID"
                )
            expected_result_integer_schemas = {
                "chunk_index": {"type": "integer", "minimum": 0},
                "start_character_offset": {"type": "integer", "minimum": 0},
                "end_character_offset": {"type": "integer", "minimum": 0},
                "rank": {"type": "integer", "minimum": 1},
            }
            for field_name, expected_schema in expected_result_integer_schemas.items():
                if result_properties.get(field_name) != expected_schema:
                    failures.append(
                        f"$defs.retrievalQueryResult.properties.{field_name} must use {expected_schema}"
                    )
            expected_matched_terms_schema = {
                "type": "array",
                "maxItems": 16,
                "items": {
                    "allOf": [
                        {"$ref": "#/$defs/nonBlankString"},
                        {"maxLength": 64},
                    ]
                },
            }
            if result_properties.get("matched_terms") != expected_matched_terms_schema:
                failures.append(
                    "$defs.retrievalQueryResult.properties.matched_terms must cap matched terms at 16 items of 64 characters"
                )
            if result_properties.get("match_kind") != {
                "type": "string",
                "enum": ["lexical", "semantic"],
            }:
                failures.append(
                    "$defs.retrievalQueryResult.properties.match_kind must be lexical or semantic"
                )
            expected_snippet_schema = {
                "allOf": [
                    {"$ref": "#/$defs/nonEmptyString"},
                    {"maxLength": 500},
                ],
            }
            if result_properties.get("snippet") != expected_snippet_schema:
                failures.append(
                    "$defs.retrievalQueryResult.properties.snippet must use nonEmptyString with maxLength 500"
                )
        required_fields = retrieval_result.get("required")
        if not isinstance(required_fields, list):
            failures.append("$defs.retrievalQueryResult.required must be a list")
        else:
            if "source_anchor_id" not in required_fields:
                failures.append("$defs.retrievalQueryResult.required must include source_anchor_id")
            expected_required_fields = {
                "document",
                "source_anchor_id",
                "chunk_index",
                "start_character_offset",
                "end_character_offset",
                "rank",
                "matched_terms",
                "snippet",
            }
            if set(required_fields) != expected_required_fields:
                failures.append(
                    "$defs.retrievalQueryResult.required must stay limited to document, source_anchor_id, chunk_index, start_character_offset, end_character_offset, rank, matched_terms, and snippet"
                )
        expected_match_kind_condition = [
            {
                "if": {
                    "properties": {"match_kind": {"const": "semantic"}},
                    "required": ["match_kind"],
                },
                "else": {"properties": {"matched_terms": {"minItems": 1}}},
            }
        ]
        if retrieval_result.get("allOf") != expected_match_kind_condition:
            failures.append(
                "$defs.retrievalQueryResult must allow empty matched_terms only for explicit semantic matches"
            )
        if retrieval_result.get("additionalProperties") is not False:
            failures.append("$defs.retrievalQueryResult additionalProperties must be false")

    retrieval_payload = defs.get("retrievalQueryPayload")
    if not isinstance(retrieval_payload, dict):
        failures.append("$defs.retrievalQueryPayload schema is missing")
    else:
        variants = retrieval_payload.get("oneOf")
        if not isinstance(variants, list) or len(variants) != 2:
            failures.append("$defs.retrievalQueryPayload must keep separate request and response variants")
        else:
            request_variant = variants[0]
            if not isinstance(request_variant, dict):
                failures.append("$defs.retrievalQueryPayload request variant must be an object")
            else:
                request_required = request_variant.get("required")
                if not isinstance(request_required, list):
                    failures.append("$defs.retrievalQueryPayload request required must be a list")
                elif "query" not in request_required:
                    failures.append("$defs.retrievalQueryPayload request required must include query")

                request_properties = request_variant.get("properties")
                if not isinstance(request_properties, dict):
                    failures.append("$defs.retrievalQueryPayload request properties must be an object")
                else:
                    allowed_request_properties = {
                        "query",
                        "limit",
                        "max_snippet_characters",
                        "embedding_model_id",
                    }
                    if set(request_properties.keys()) != allowed_request_properties:
                        failures.append(
                            "$defs.retrievalQueryPayload request properties must stay limited to query, limit, max_snippet_characters, and embedding_model_id"
                        )
                    expected_query_schema = {
                        "allOf": [
                            {"$ref": "#/$defs/nonBlankString"},
                            {"maxLength": 1024},
                        ]
                    }
                    if request_properties.get("query") != expected_query_schema:
                        failures.append(
                            "$defs.retrievalQueryPayload request query must use #/$defs/nonBlankString with maxLength 1024"
                        )
                    if request_properties.get("embedding_model_id") != {
                        "$ref": "#/$defs/nonBlankString"
                    }:
                        failures.append(
                            "$defs.retrievalQueryPayload request embedding_model_id must use #/$defs/nonBlankString"
                        )
                    if "source_anchor_id" in request_properties:
                        failures.append(
                            "$defs.retrievalQueryPayload request properties must not accept source_anchor_id"
                        )

                    canonical_retrieval_query_request_payload_sample = (
                        build_retrieval_query_request_source_anchor_sample()
                    )
                    for sample_failure in retrieval_query_request_source_anchor_sample_failures(
                        canonical_retrieval_query_request_payload_sample,
                        request_variant,
                    ):
                        failures.append(
                            "$defs.retrievalQueryPayload request sample must accept canonical "
                            f"query payload: {sample_failure}"
                        )
                    rejected_retrieval_query_request_payload_samples = (
                        (
                            "missing-query",
                            build_retrieval_query_request_source_anchor_sample(include_query=False),
                        ),
                        (
                            "blank-query",
                            build_retrieval_query_request_source_anchor_sample(query="   "),
                        ),
                        (
                            "non-string-query",
                            build_retrieval_query_request_source_anchor_sample(query=42),
                        ),
                        (
                            "oversized-query",
                            build_retrieval_query_request_source_anchor_sample(query="a" * 1025),
                        ),
                        (
                            "source-anchor-id",
                            build_retrieval_query_request_source_anchor_sample(
                                source_anchor_id="source_anchor_0123456789abcdef"
                            ),
                        ),
                        (
                            "blank-embedding-model-id",
                            build_retrieval_query_request_source_anchor_sample(
                                embedding_model_id="   "
                            ),
                        ),
                        (
                            "non-string-embedding-model-id",
                            build_retrieval_query_request_source_anchor_sample(
                                embedding_model_id=42
                            ),
                        ),
                        (
                            "string-limit",
                            build_retrieval_query_request_source_anchor_sample(limit="3"),
                        ),
                        (
                            "float-limit",
                            build_retrieval_query_request_source_anchor_sample(limit=1.5),
                        ),
                        (
                            "bool-limit",
                            build_retrieval_query_request_source_anchor_sample(limit=True),
                        ),
                        (
                            "negative-limit",
                            build_retrieval_query_request_source_anchor_sample(limit=-1),
                        ),
                        (
                            "over-limit",
                            build_retrieval_query_request_source_anchor_sample(limit=101),
                        ),
                        (
                            "string-max-snippet-characters",
                            build_retrieval_query_request_source_anchor_sample(
                                max_snippet_characters="160"
                            ),
                        ),
                        (
                            "float-max-snippet-characters",
                            build_retrieval_query_request_source_anchor_sample(
                                max_snippet_characters=160.5
                            ),
                        ),
                        (
                            "bool-max-snippet-characters",
                            build_retrieval_query_request_source_anchor_sample(
                                max_snippet_characters=True
                            ),
                        ),
                        (
                            "negative-max-snippet-characters",
                            build_retrieval_query_request_source_anchor_sample(
                                max_snippet_characters=-1
                            ),
                        ),
                        (
                            "over-max-snippet-characters",
                            build_retrieval_query_request_source_anchor_sample(
                                max_snippet_characters=501
                            ),
                        ),
                    )
                    for label, payload_sample in rejected_retrieval_query_request_payload_samples:
                        if not retrieval_query_request_source_anchor_sample_failures(
                            payload_sample,
                            request_variant,
                        ):
                            failures.append(
                                "$defs.retrievalQueryPayload request sample must reject "
                                f"{label}"
                            )

                if request_variant.get("additionalProperties") is not False:
                    failures.append(
                        "$defs.retrievalQueryPayload request additionalProperties must be false"
                    )
            response_variant = variants[1]
            if not isinstance(response_variant, dict):
                failures.append("$defs.retrievalQueryPayload response variant must be an object")
            else:
                response_required = response_variant.get("required")
                if not isinstance(response_required, list):
                    failures.append("$defs.retrievalQueryPayload response required must be a list")
                elif "results" not in response_required:
                    failures.append("$defs.retrievalQueryPayload response required must include results")

                response_properties = response_variant.get("properties")
                if not isinstance(response_properties, dict):
                    failures.append("$defs.retrievalQueryPayload response properties must be an object")
                else:
                    results_schema = response_properties.get("results")
                    if not isinstance(results_schema, dict):
                        failures.append(
                            "$defs.retrievalQueryPayload response properties.results must be an object"
                        )
                    else:
                        if results_schema.get("type") != "array":
                            failures.append(
                                "$defs.retrievalQueryPayload response results must be an array"
                            )
                        if results_schema.get("maxItems") != 100:
                            failures.append(
                                "$defs.retrievalQueryPayload response results must set maxItems 100"
                            )
                        elif isinstance(results_schema.get("maxItems"), int):
                            retrieval_response_results_max_items = results_schema.get("maxItems")
                        if results_schema.get("items") != {"$ref": "#/$defs/retrievalQueryResult"}:
                            failures.append(
                                "$defs.retrievalQueryPayload response results.items must use "
                                "#/$defs/retrievalQueryResult"
                            )
                if response_variant.get("additionalProperties") is not False:
                    failures.append(
                        "$defs.retrievalQueryPayload response additionalProperties must be false"
                    )

    if source_anchor_pattern is not None and isinstance(retrieval_result, dict):
        try:
            compiled_source_anchor_pattern = re.compile(source_anchor_pattern)
        except re.error:
            compiled_source_anchor_pattern = None
        if compiled_source_anchor_pattern is not None:
            rejected_retrieval_query_response_integer_payload_samples = []
            for integer_field_name in (
                "chunk_index",
                "start_character_offset",
                "end_character_offset",
                "rank",
            ):
                rejected_retrieval_query_response_integer_payload_samples.extend(
                    (
                        (
                            f"string-{integer_field_name.replace('_', '-')}",
                            build_retrieval_query_response_source_anchor_sample(
                                "source_anchor_0123456789abcdef",
                                result_overrides={integer_field_name: "1"},
                            ),
                        ),
                        (
                            f"float-{integer_field_name.replace('_', '-')}",
                            build_retrieval_query_response_source_anchor_sample(
                                "source_anchor_0123456789abcdef",
                                result_overrides={integer_field_name: 1.5},
                            ),
                        ),
                        (
                            f"bool-{integer_field_name.replace('_', '-')}",
                            build_retrieval_query_response_source_anchor_sample(
                                "source_anchor_0123456789abcdef",
                                result_overrides={integer_field_name: True},
                            ),
                        ),
                        (
                            f"negative-{integer_field_name.replace('_', '-')}",
                            build_retrieval_query_response_source_anchor_sample(
                                "source_anchor_0123456789abcdef",
                                result_overrides={integer_field_name: -1},
                            ),
                        ),
                    )
                )

            rejected_retrieval_query_response_result_shape_samples = (
                (
                    "unknown-result-metadata",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"retrieval_context": "future semantic context"},
                    ),
                ),
                (
                    "over-results",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_count=101,
                    ),
                ),
                (
                    "missing-rank",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        omit_result_fields=("rank",),
                    ),
                ),
                (
                    "zero-rank",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"rank": 0},
                    ),
                ),
                (
                    "empty-snippet",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"snippet": ""},
                    ),
                ),
                (
                    "overlong-snippet",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"snippet": "a" * 501},
                    ),
                ),
                (
                    "empty-matched-terms",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"matched_terms": []},
                    ),
                ),
                (
                    "unknown-match-kind",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"match_kind": "hybrid"},
                    ),
                ),
                (
                    "empty-matched-term",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"matched_terms": [""]},
                    ),
                ),
                (
                    "blank-matched-term",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"matched_terms": ["  \n  "]},
                    ),
                ),
                (
                    "over-matched-terms",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={
                            "matched_terms": [f"term{index}" for index in range(17)]
                        },
                    ),
                ),
                (
                    "overlong-matched-term",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={"matched_terms": ["a" * 65]},
                    ),
                ),
                (
                    "end-before-start-character-offset",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        result_overrides={
                            "start_character_offset": 42,
                            "end_character_offset": 7,
                        },
                    ),
                ),
                (
                    "unknown-result-document-metadata",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={"source_path": "/private/source.txt"},
                    ),
                ),
                (
                    "missing-result-document-quality",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        omit_document_fields=("quality",),
                    ),
                ),
                (
                    "zero-chunk-result-document-quality-mismatch",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={
                            "chunk_count": 0,
                            "quality": "chunked",
                        },
                    ),
                ),
                (
                    "zero-chunk-single-result-document-quality-mismatch",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={
                            "chunk_count": 0,
                            "quality": "single_chunk",
                        },
                    ),
                ),
                (
                    "single-chunk-result-document-quality-mismatch",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={
                            "chunk_count": 1,
                            "quality": "no_usable_text",
                        },
                    ),
                ),
                (
                    "single-chunk-chunked-result-document-quality-mismatch",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={
                            "chunk_count": 1,
                            "quality": "chunked",
                        },
                    ),
                ),
                (
                    "multi-chunk-result-document-quality-mismatch",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={
                            "chunk_count": 2,
                            "quality": "single_chunk",
                        },
                    ),
                ),
                (
                    "multi-chunk-no-usable-result-document-quality-mismatch",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={
                            "chunk_count": 2,
                            "quality": "no_usable_text",
                        },
                    ),
                ),
                (
                    "three-chunk-single-result-document-quality-mismatch",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={
                            "chunk_count": 3,
                            "quality": "single_chunk",
                        },
                    ),
                ),
                (
                    "overlong-result-document-id",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={"id": "d" * 129},
                    ),
                ),
                (
                    "uppercase-result-document-mime-type",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={"mime_type": "Text/markdown"},
                    ),
                ),
                (
                    "parameterized-result-document-mime-type",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={"mime_type": "text/plain; charset=utf-8"},
                    ),
                ),
                (
                    "uppercase-result-document-content-fingerprint",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={"content_fingerprint": "001122334455667A"},
                    ),
                ),
                (
                    "string-result-document-chunk-count",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={"chunk_count": "1"},
                    ),
                ),
                (
                    "negative-result-document-extracted-character-count",
                    build_retrieval_query_response_source_anchor_sample(
                        "source_anchor_0123456789abcdef",
                        document_overrides={"extracted_character_count": -1},
                    ),
                ),
            )
            for label, payload_sample in (
                *rejected_retrieval_query_response_integer_payload_samples,
                *rejected_retrieval_query_response_result_shape_samples,
            ):
                if not retrieval_query_response_source_anchor_sample_failures(
                    payload_sample,
                    compiled_source_anchor_pattern,
                    retrieval_result,
                    max_results_count=retrieval_response_results_max_items,
                    document_schema=index_document if isinstance(index_document, dict) else None,
                ):
                    failures.append(
                        "$defs.retrievalQueryPayload response result sample must reject "
                        f"{label}"
                    )
            semantic_payload_sample = build_retrieval_query_response_source_anchor_sample(
                "source_anchor_0123456789abcdef",
                result_overrides={"match_kind": "semantic", "matched_terms": []},
            )
            semantic_failures = retrieval_query_response_source_anchor_sample_failures(
                semantic_payload_sample,
                compiled_source_anchor_pattern,
                retrieval_result,
                max_results_count=retrieval_response_results_max_items,
                document_schema=index_document if isinstance(index_document, dict) else None,
            )
            if semantic_failures:
                failures.append(
                    "$defs.retrievalQueryPayload response result sample must accept "
                    "explicit semantic match_kind with empty matched_terms: "
                    + "; ".join(semantic_failures)
                )

    return failures


def check_source_anchor_resolve_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include sourceAnchorResolvePayload schema"]

    source_anchor_id = defs.get("sourceAnchorID")
    if source_anchor_id != {
        "type": "string",
        "pattern": "^source_anchor_[0-9a-f]{16}$",
    }:
        failures.append(
            "$defs.sourceAnchorID must pin source_anchor.resolve handles to source_anchor_[16 lowercase hex]"
        )
    compiled_source_anchor_pattern: re.Pattern[str] | None = None
    if isinstance(source_anchor_id, dict) and isinstance(source_anchor_id.get("pattern"), str):
        try:
            compiled_source_anchor_pattern = re.compile(source_anchor_id["pattern"])
        except re.error:
            failures.append("$defs.sourceAnchorID pattern must compile")

    chunk_summary = defs.get("sourceAnchorChunkSummary")
    if not isinstance(chunk_summary, dict):
        failures.append("$defs.sourceAnchorChunkSummary schema is missing")
    else:
        chunk_required = chunk_summary.get("required")
        expected_chunk_fields = {
            "chunk_index",
            "start_character_offset",
            "end_character_offset",
            "character_count",
        }
        if not isinstance(chunk_required, list):
            failures.append("$defs.sourceAnchorChunkSummary.required must be a list")
        elif set(chunk_required) != expected_chunk_fields:
            failures.append(
                "$defs.sourceAnchorChunkSummary.required must stay limited to chunk_index, start_character_offset, end_character_offset, and character_count"
            )
        chunk_properties = chunk_summary.get("properties")
        if not isinstance(chunk_properties, dict):
            failures.append("$defs.sourceAnchorChunkSummary.properties must be an object")
        else:
            if set(chunk_properties.keys()) != expected_chunk_fields:
                failures.append(
                    "$defs.sourceAnchorChunkSummary properties must stay limited to chunk_index, start_character_offset, end_character_offset, and character_count"
                )
            for field_name in expected_chunk_fields:
                if chunk_properties.get(field_name) != {"type": "integer", "minimum": 0}:
                    failures.append(
                        f"$defs.sourceAnchorChunkSummary.properties.{field_name} must be a nonnegative integer"
                    )
        if chunk_summary.get("additionalProperties") is not False:
            failures.append("$defs.sourceAnchorChunkSummary additionalProperties must be false")

    source_anchor_payload = defs.get("sourceAnchorResolvePayload")
    if not isinstance(source_anchor_payload, dict):
        failures.append("$defs.sourceAnchorResolvePayload schema is missing")
        return failures

    variants = source_anchor_payload.get("oneOf")
    if not isinstance(variants, list) or len(variants) != 2:
        failures.append("$defs.sourceAnchorResolvePayload must keep separate request and response variants")
        return failures

    request_variant = variants[0]
    if not isinstance(request_variant, dict):
        failures.append("$defs.sourceAnchorResolvePayload request variant must be an object")
    else:
        request_required = request_variant.get("required")
        if not isinstance(request_required, list):
            failures.append("$defs.sourceAnchorResolvePayload request required must be a list")
        elif set(request_required) != {"source_anchor_id"}:
            failures.append(
                "$defs.sourceAnchorResolvePayload request required must stay limited to source_anchor_id"
            )
        request_properties = request_variant.get("properties")
        if not isinstance(request_properties, dict):
            failures.append("$defs.sourceAnchorResolvePayload request properties must be an object")
        else:
            if set(request_properties.keys()) != {"source_anchor_id"}:
                failures.append(
                    "$defs.sourceAnchorResolvePayload request properties must stay limited to source_anchor_id"
                )
            if request_properties.get("source_anchor_id") != {"$ref": "#/$defs/sourceAnchorID"}:
                failures.append(
                    "$defs.sourceAnchorResolvePayload request source_anchor_id must use #/$defs/sourceAnchorID"
                )
        if request_variant.get("additionalProperties") is not False:
            failures.append("$defs.sourceAnchorResolvePayload request additionalProperties must be false")

        canonical_source_anchor_request_sample = build_source_anchor_resolve_request_sample()
        for sample_failure in source_anchor_resolve_request_sample_failures(
            canonical_source_anchor_request_sample,
            request_variant,
            compiled_source_anchor_pattern,
        ):
            failures.append(
                "$defs.sourceAnchorResolvePayload request sample must accept canonical request: "
                + sample_failure
            )
        for label, payload_sample in (
            (
                "missing-source-anchor",
                build_source_anchor_resolve_request_sample(source_anchor_id=None),
            ),
            (
                "uppercase-source-anchor",
                build_source_anchor_resolve_request_sample(
                    source_anchor_id="source_anchor_0123456789ABCDEF"
                ),
            ),
            (
                "non-string-source-anchor",
                build_source_anchor_resolve_request_sample(source_anchor_id=1234),
            ),
            (
                "response-document",
                build_source_anchor_resolve_request_sample(
                    extra_fields={"document": build_index_document_sample()}
                ),
            ),
            (
                "response-chunk-summary",
                build_source_anchor_resolve_request_sample(
                    extra_fields={"chunk_summary": build_source_anchor_chunk_summary_sample()}
                ),
            ),
            (
                "future-request-metadata",
                build_source_anchor_resolve_request_sample(
                    extra_fields={
                        "source_path": "/private/source.md",
                        "citation": "future citation",
                        "trusted_source": True,
                    }
                ),
            ),
        ):
            if not source_anchor_resolve_request_sample_failures(
                payload_sample,
                request_variant,
                compiled_source_anchor_pattern,
            ):
                failures.append(
                    "$defs.sourceAnchorResolvePayload request sample must reject "
                    f"{label}"
                )

    response_variant = variants[1]
    if not isinstance(response_variant, dict):
        failures.append("$defs.sourceAnchorResolvePayload response variant must be an object")
    else:
        response_required = response_variant.get("required")
        expected_response_fields = {"source_anchor_id", "document", "chunk_summary"}
        if not isinstance(response_required, list):
            failures.append("$defs.sourceAnchorResolvePayload response required must be a list")
        elif set(response_required) != expected_response_fields:
            failures.append(
                "$defs.sourceAnchorResolvePayload response required must stay limited to source_anchor_id, document, and chunk_summary"
            )
        response_properties = response_variant.get("properties")
        if not isinstance(response_properties, dict):
            failures.append("$defs.sourceAnchorResolvePayload response properties must be an object")
        else:
            if set(response_properties.keys()) != expected_response_fields:
                failures.append(
                    "$defs.sourceAnchorResolvePayload response properties must stay limited to source_anchor_id, document, and chunk_summary"
                )
            expected_refs = {
                "source_anchor_id": {"$ref": "#/$defs/sourceAnchorID"},
                "document": {"$ref": "#/$defs/indexDocument"},
                "chunk_summary": {"$ref": "#/$defs/sourceAnchorChunkSummary"},
            }
            for field_name, expected_ref in expected_refs.items():
                if response_properties.get(field_name) != expected_ref:
                    failures.append(
                        f"$defs.sourceAnchorResolvePayload response {field_name} must use {expected_ref}"
                    )
            forbidden_response_fields = {
                "chunk_text",
                "snippet",
                "source_path",
                "workspace_id",
                "project_id",
                "retrieval_context",
                "embedding",
                "citation",
                "trusted_source",
                "approval",
            }
            leaked_fields = sorted(set(response_properties) & forbidden_response_fields)
            if leaked_fields:
                failures.append(
                    "$defs.sourceAnchorResolvePayload response properties include future/private metadata "
                    f"{leaked_fields}"
                )
        if response_variant.get("additionalProperties") is not False:
            failures.append("$defs.sourceAnchorResolvePayload response additionalProperties must be false")

        index_document = defs.get("indexDocument")
        if isinstance(chunk_summary, dict) and isinstance(index_document, dict):
            canonical_source_anchor_response_sample = build_source_anchor_resolve_response_sample()
            for sample_failure in source_anchor_resolve_response_sample_failures(
                canonical_source_anchor_response_sample,
                response_variant,
                compiled_source_anchor_pattern,
                index_document,
                chunk_summary,
            ):
                failures.append(
                    "$defs.sourceAnchorResolvePayload response sample must accept canonical response: "
                    + sample_failure
                )
            for label, payload_sample in (
                (
                    "missing-source-anchor",
                    build_source_anchor_resolve_response_sample(omit_payload_fields=("source_anchor_id",)),
                ),
                (
                    "missing-document",
                    build_source_anchor_resolve_response_sample(omit_payload_fields=("document",)),
                ),
                (
                    "missing-chunk-summary",
                    build_source_anchor_resolve_response_sample(omit_payload_fields=("chunk_summary",)),
                ),
                (
                    "uppercase-source-anchor",
                    build_source_anchor_resolve_response_sample(
                        source_anchor_id="source_anchor_0123456789ABCDEF"
                    ),
                ),
                (
                    "unknown-response-metadata",
                    build_source_anchor_resolve_response_sample(
                        payload_overrides={
                            "chunk_text": "future full chunk text",
                            "snippet": "future snippet",
                            "source_path": "/private/source.md",
                            "retrieval_context": "future retrieval context",
                            "citation": "future citation",
                            "trusted_source": True,
                            "approval": "future approval",
                        }
                    ),
                ),
                (
                    "unknown-document-metadata",
                    build_source_anchor_resolve_response_sample(
                        document_overrides={"source_path": "/private/source.md"}
                    ),
                ),
                (
                    "missing-chunk-index",
                    build_source_anchor_resolve_response_sample(
                        omit_chunk_summary_fields=("chunk_index",)
                    ),
                ),
                (
                    "string-chunk-index",
                    build_source_anchor_resolve_response_sample(
                        chunk_summary_overrides={"chunk_index": "0"}
                    ),
                ),
                (
                    "bool-character-count",
                    build_source_anchor_resolve_response_sample(
                        chunk_summary_overrides={"character_count": True}
                    ),
                ),
                (
                    "negative-character-count",
                    build_source_anchor_resolve_response_sample(
                        chunk_summary_overrides={"character_count": -1}
                    ),
                ),
                (
                    "end-before-start-character-offset",
                    build_source_anchor_resolve_response_sample(
                        chunk_summary_overrides={
                            "start_character_offset": 10,
                            "end_character_offset": 3,
                        }
                    ),
                ),
                (
                    "unknown-chunk-summary-metadata",
                    build_source_anchor_resolve_response_sample(
                        chunk_summary_overrides={"chunk_text": "future chunk text"}
                    ),
                ),
            ):
                if not source_anchor_resolve_response_sample_failures(
                    payload_sample,
                    response_variant,
                    compiled_source_anchor_pattern,
                    index_document,
                    chunk_summary,
                ):
                    failures.append(
                        "$defs.sourceAnchorResolvePayload response sample must reject "
                        f"{label}"
                    )

    return failures


def check_trusted_source_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include citation and trusted source schemas"]

    expected_defs: dict[str, dict[str, object]] = {
        "citationID": {"type": "string", "pattern": "^citation_[0-9a-f]{32}$"},
        "assistantMessageID": {
            "type": "string",
            "pattern": "^assistant_message_[0-9a-f]{32}$",
        },
        "sourceReviewID": {"type": "string", "pattern": "^source_review_[0-9a-f]{32}$"},
        "sourceConfirmationToken": {
            "type": "string",
            "pattern": "^source_confirmation_[0-9a-f]{64}$",
        },
        "trustedSourceGrantID": {
            "type": "string",
            "pattern": "^trusted_source_[0-9a-f]{32}$",
        },
        "iso8601DateTime": {"type": "string", "minLength": 1, "format": "date-time"},
        "citation": {
            "type": "object",
            "required": [
                "schema_version",
                "citation_id",
                "source_anchor_id",
                "document",
                "chunk_summary",
            ],
            "properties": {
                "schema_version": {"const": 1},
                "citation_id": {"$ref": "#/$defs/citationID"},
                "source_anchor_id": {"$ref": "#/$defs/sourceAnchorID"},
                "document": {"$ref": "#/$defs/indexDocument"},
                "chunk_summary": {"$ref": "#/$defs/sourceAnchorChunkSummary"},
            },
            "additionalProperties": False,
        },
        "sourceReview": {
            "type": "object",
            "required": [
                "review_id",
                "confirmation_token",
                "disclosure_version",
                "usage_scope",
                "expires_at",
            ],
            "properties": {
                "review_id": {"$ref": "#/$defs/sourceReviewID"},
                "confirmation_token": {"$ref": "#/$defs/sourceConfirmationToken"},
                "disclosure_version": {"const": "runtime-trusted-source-v1"},
                "usage_scope": {"const": "chat_context"},
                "expires_at": {"$ref": "#/$defs/iso8601DateTime"},
            },
            "additionalProperties": False,
        },
        "trustedSource": {
            "type": "object",
            "required": [
                "grant_id",
                "citation_id",
                "source_anchor_id",
                "document",
                "usage_scope",
                "approved_at",
            ],
            "properties": {
                "grant_id": {"$ref": "#/$defs/trustedSourceGrantID"},
                "citation_id": {"$ref": "#/$defs/citationID"},
                "source_anchor_id": {"$ref": "#/$defs/sourceAnchorID"},
                "document": {"$ref": "#/$defs/indexDocument"},
                "usage_scope": {"const": "chat_context"},
                "approved_at": {"$ref": "#/$defs/iso8601DateTime"},
            },
            "additionalProperties": False,
        },
    }

    def closed_object(
        required: list[str], properties: dict[str, object]
    ) -> dict[str, object]:
        return {
            "type": "object",
            "required": required,
            "properties": properties,
            "additionalProperties": False,
        }

    expected_defs.update(
        {
            "citationResolvePayload": {
                "oneOf": [
                    closed_object(
                        ["source_anchor_id"],
                        {"source_anchor_id": {"$ref": "#/$defs/sourceAnchorID"}},
                    ),
                    closed_object(
                        ["citation", "review"],
                        {
                            "citation": {"$ref": "#/$defs/citation"},
                            "review": {"$ref": "#/$defs/sourceReview"},
                            "trusted_source": {"$ref": "#/$defs/trustedSource"},
                        },
                    ),
                ]
            },
            "chatSourceAttributionResolvePayload": {
                "oneOf": [
                    closed_object(
                        ["session_id", "assistant_message_id", "source_index"],
                        {
                            "session_id": {"$ref": "#/$defs/nonBlankString"},
                            "assistant_message_id": {"$ref": "#/$defs/assistantMessageID"},
                            "source_index": {"type": "integer", "minimum": 1, "maximum": 8},
                        },
                    ),
                    closed_object(
                        ["citation", "review"],
                        {
                            "citation": {"$ref": "#/$defs/citation"},
                            "review": {"$ref": "#/$defs/sourceReview"},
                            "trusted_source": {"$ref": "#/$defs/trustedSource"},
                        },
                    ),
                ]
            },
            "trustedSourceApprovePayload": {
                "oneOf": [
                    closed_object(
                        ["review_id", "confirmation_token", "disclosure_version", "usage_scope"],
                        {
                            "review_id": {"$ref": "#/$defs/sourceReviewID"},
                            "confirmation_token": {"$ref": "#/$defs/sourceConfirmationToken"},
                            "disclosure_version": {"const": "runtime-trusted-source-v1"},
                            "usage_scope": {"const": "chat_context"},
                        },
                    ),
                    closed_object(
                        ["trusted_source"],
                        {"trusted_source": {"$ref": "#/$defs/trustedSource"}},
                    ),
                ]
            },
            "trustedSourceDismissPayload": {
                "oneOf": [
                    closed_object(
                        ["review_id"],
                        {"review_id": {"$ref": "#/$defs/sourceReviewID"}},
                    ),
                    closed_object(
                        ["review_id", "dismissed"],
                        {
                            "review_id": {"$ref": "#/$defs/sourceReviewID"},
                            "dismissed": {"const": True},
                        },
                    ),
                ]
            },
            "trustedSourceListPayload": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "minimum": 0, "maximum": 100}
                        },
                        "additionalProperties": False,
                    },
                    closed_object(
                        ["trusted_sources"],
                        {
                            "trusted_sources": {
                                "type": "array",
                                "maxItems": 100,
                                "items": {"$ref": "#/$defs/trustedSource"},
                            }
                        },
                    ),
                ]
            },
            "trustedSourceRevokePayload": {
                "oneOf": [
                    closed_object(
                        ["grant_id"],
                        {"grant_id": {"$ref": "#/$defs/trustedSourceGrantID"}},
                    ),
                    closed_object(
                        ["grant_id", "revoked"],
                        {
                            "grant_id": {"$ref": "#/$defs/trustedSourceGrantID"},
                            "revoked": {"const": True},
                        },
                    ),
                ]
            },
        }
    )

    for def_name, expected_schema in expected_defs.items():
        if defs.get(def_name) != expected_schema:
            failures.append(f"$defs.{def_name} must match the active trusted-source contract exactly")

    expected_payload_refs = {
        "citation.resolve": "#/$defs/citationResolvePayload",
        "chat.source_attribution.resolve": "#/$defs/chatSourceAttributionResolvePayload",
        "trusted_source.approve": "#/$defs/trustedSourceApprovePayload",
        "trusted_source.dismiss": "#/$defs/trustedSourceDismissPayload",
        "trusted_source.list": "#/$defs/trustedSourceListPayload",
        "trusted_source.revoke": "#/$defs/trustedSourceRevokePayload",
    }
    actual_payload_refs: dict[str, object] = {}
    for rule in schema.get("allOf", []):
        if not isinstance(rule, dict):
            continue
        message_type = rule.get("if", {}).get("properties", {}).get("type", {}).get("const")
        payload_ref = rule.get("then", {}).get("properties", {}).get("payload", {}).get("$ref")
        if message_type in expected_payload_refs:
            actual_payload_refs[message_type] = payload_ref
    for message_type, expected_ref in expected_payload_refs.items():
        if actual_payload_refs.get(message_type) != expected_ref:
            failures.append(f"{message_type} payload must use {expected_ref}")

    if any(defs.get(name) != expected for name, expected in expected_defs.items()):
        return failures

    document = build_index_document_sample()
    chunk_summary = build_source_anchor_chunk_summary_sample()
    citation = {
        "schema_version": 1,
        "citation_id": "citation_0123456789abcdef0123456789abcdef",
        "source_anchor_id": "source_anchor_0123456789abcdef",
        "document": document,
        "chunk_summary": chunk_summary,
    }
    review = {
        "review_id": "source_review_0123456789abcdef0123456789abcdef",
        "confirmation_token": "source_confirmation_" + "a" * 64,
        "disclosure_version": "runtime-trusted-source-v1",
        "usage_scope": "chat_context",
        "expires_at": "2026-07-12T12:30:45Z",
    }
    trusted_source = {
        "grant_id": "trusted_source_0123456789abcdef0123456789abcdef",
        "citation_id": citation["citation_id"],
        "source_anchor_id": citation["source_anchor_id"],
        "document": document,
        "usage_scope": "chat_context",
        "approved_at": "2026-07-12T12:31:00+09:00",
    }
    approve_request = {
        key: review[key]
        for key in ("review_id", "confirmation_token", "disclosure_version", "usage_scope")
    }

    canonical_samples = {
        "citationResolvePayload": [
            {"source_anchor_id": citation["source_anchor_id"]},
            {"citation": citation, "review": review},
            {"citation": citation, "review": review, "trusted_source": trusted_source},
        ],
        "chatSourceAttributionResolvePayload": [
            {
                "session_id": "session-1",
                "assistant_message_id": "assistant_message_" + "4" * 32,
                "source_index": 1,
            },
            {"citation": citation, "review": review},
            {"citation": citation, "review": review, "trusted_source": trusted_source},
        ],
        "trustedSourceApprovePayload": [
            approve_request,
            {"trusted_source": trusted_source},
        ],
        "trustedSourceDismissPayload": [
            {"review_id": review["review_id"]},
            {"review_id": review["review_id"], "dismissed": True},
        ],
        "trustedSourceListPayload": [
            {},
            {"limit": 0},
            {"limit": 100},
            {"trusted_sources": []},
            {"trusted_sources": [trusted_source]},
        ],
        "trustedSourceRevokePayload": [
            {"grant_id": trusted_source["grant_id"]},
            {"grant_id": trusted_source["grant_id"], "revoked": True},
        ],
    }

    def changed(value: object, path: tuple[object, ...], replacement: object) -> object:
        clone = json.loads(json.dumps(value))
        target = clone
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        return clone

    invalid_samples = {
        "citationResolvePayload": [
            {},
            {"source_anchor_id": "source_anchor_0123456789ABCDEF"},
            {"source_anchor_id": citation["source_anchor_id"], "query": "secret"},
            {"citation": citation},
            changed({"citation": citation, "review": review}, ("citation", "schema_version"), 2),
            changed({"citation": citation, "review": review}, ("citation", "citation_id"), "citation_bad"),
            changed({"citation": citation, "review": review}, ("citation", "snippet"), "secret"),
            changed({"citation": citation, "review": review}, ("review", "confirmation_token"), "source_confirmation_bad"),
            changed({"citation": citation, "review": review}, ("review", "disclosure_version"), "v2"),
            changed({"citation": citation, "review": review}, ("review", "usage_scope"), "indexing"),
            changed({"citation": citation, "review": review}, ("review", "expires_at"), "not-a-date"),
            changed({"citation": citation, "review": review}, ("review", "approval_id"), "approval_1"),
            changed({"citation": citation, "review": review}, ("citation", "document", "path"), "/tmp/private"),
            changed({"citation": citation, "review": review, "trusted_source": trusted_source}, ("trusted_source", "grant_id"), "trusted_source_bad"),
        ],
        "chatSourceAttributionResolvePayload": [
            {},
            {
                "session_id": "   ",
                "assistant_message_id": "assistant_message_" + "4" * 32,
                "source_index": 1,
            },
            {
                "session_id": "session-1",
                "assistant_message_id": "assistant_message_bad",
                "source_index": 1,
            },
            {
                "session_id": "session-1",
                "assistant_message_id": "assistant_message_" + "4" * 32,
                "source_index": 0,
            },
            {
                "session_id": "session-1",
                "assistant_message_id": "assistant_message_" + "4" * 32,
                "source_index": 9,
            },
            {
                "session_id": "session-1",
                "assistant_message_id": "assistant_message_" + "4" * 32,
                "source_index": 1,
                "revision": 1,
            },
            {"citation": citation},
            changed({"citation": citation, "review": review}, ("citation", "text"), "secret"),
            changed({"citation": citation, "review": review}, ("review", "revision"), 1),
        ],
        "trustedSourceApprovePayload": [
            {"review_id": review["review_id"]},
            changed(approve_request, ("confirmation_token",), "source_confirmation_bad"),
            changed(approve_request, ("disclosure_version",), "runtime-trusted-source-v2"),
            changed(approve_request, ("usage_scope",), "retrieval"),
            changed(approve_request, ("body",), "secret"),
            changed({"trusted_source": trusted_source}, ("trusted_source", "approved_at"), ""),
            changed({"trusted_source": trusted_source}, ("trusted_source", "model"), "private-model"),
        ],
        "trustedSourceDismissPayload": [
            {},
            {"review_id": "source_review_bad"},
            {"review_id": review["review_id"], "dismissed": False},
            {"review_id": review["review_id"], "dismissed": True, "revision": 1},
        ],
        "trustedSourceListPayload": [
            {"limit": -1},
            {"limit": 101},
            {"limit": True},
            {"limit": "10"},
            {"query": "secret"},
            {"trusted_sources": [trusted_source] * 101},
            changed({"trusted_sources": [trusted_source]}, ("trusted_sources", 0, "vector"), [0.1]),
        ],
        "trustedSourceRevokePayload": [
            {},
            {"grant_id": "trusted_source_bad"},
            {"grant_id": trusted_source["grant_id"], "revoked": False},
            {"grant_id": trusted_source["grant_id"], "revoked": True, "approval_id": "approval_1"},
        ],
    }

    for def_name, samples in canonical_samples.items():
        payload_schema = defs[def_name]
        for index, sample in enumerate(samples):
            sample_failures = simple_schema_sample_failures(
                sample, payload_schema, defs, path=f"{def_name} canonical[{index}]"
            )
            if sample_failures:
                failures.append(
                    f"$defs.{def_name} must accept canonical sample {index}: "
                    + "; ".join(sample_failures)
                )
        for index, sample in enumerate(invalid_samples[def_name]):
            if not simple_schema_sample_failures(
                sample, payload_schema, defs, path=f"{def_name} negative[{index}]"
            ):
                failures.append(f"$defs.{def_name} must reject negative sample {index}")

    return failures


def build_source_anchor_chunk_summary_sample(
    *,
    chunk_summary_overrides: dict[str, object] | None = None,
    omit_chunk_summary_fields: tuple[str, ...] = (),
) -> dict[str, object]:
    chunk_summary: dict[str, object] = {
        "chunk_index": 0,
        "start_character_offset": 0,
        "end_character_offset": 42,
        "character_count": 42,
    }
    if chunk_summary_overrides is not None:
        chunk_summary.update(chunk_summary_overrides)
    for field_name in omit_chunk_summary_fields:
        chunk_summary.pop(field_name, None)
    return chunk_summary


def build_source_anchor_resolve_request_sample(
    *,
    source_anchor_id: object | None = "source_anchor_0123456789abcdef",
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if source_anchor_id is not None:
        payload["source_anchor_id"] = source_anchor_id
    if extra_fields is not None:
        payload.update(extra_fields)
    return payload


def build_source_anchor_resolve_response_sample(
    *,
    source_anchor_id: object | None = "source_anchor_0123456789abcdef",
    payload_overrides: dict[str, object] | None = None,
    document_overrides: dict[str, object] | None = None,
    omit_document_fields: tuple[str, ...] = (),
    chunk_summary_overrides: dict[str, object] | None = None,
    omit_chunk_summary_fields: tuple[str, ...] = (),
    omit_payload_fields: tuple[str, ...] = (),
) -> dict[str, object]:
    payload: dict[str, object] = {
        "document": build_index_document_sample(
            document_overrides=document_overrides,
            omit_document_fields=omit_document_fields,
        ),
        "chunk_summary": build_source_anchor_chunk_summary_sample(
            chunk_summary_overrides=chunk_summary_overrides,
            omit_chunk_summary_fields=omit_chunk_summary_fields,
        ),
    }
    if source_anchor_id is not None:
        payload["source_anchor_id"] = source_anchor_id
    if payload_overrides is not None:
        payload.update(payload_overrides)
    for field_name in omit_payload_fields:
        payload.pop(field_name, None)
    return payload


def source_anchor_resolve_request_sample_failures(
    payload: object,
    request_variant: dict[str, object],
    compiled_source_anchor_pattern: re.Pattern[str] | None,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["source_anchor.resolve request payload sample must be an object"]

    properties = request_variant.get("properties")
    if not isinstance(properties, dict):
        return ["source_anchor.resolve request variant properties must be an object"]

    required = request_variant.get("required")
    if not isinstance(required, list):
        return ["source_anchor.resolve request variant required fields must be a list"]

    failures: list[str] = []
    unknown_fields = sorted(set(payload) - set(properties))
    if unknown_fields:
        failures.append(
            "source_anchor.resolve request payload sample includes unknown fields: "
            + ", ".join(unknown_fields)
        )

    for field_name in required:
        if isinstance(field_name, str) and field_name not in payload:
            failures.append(f"source_anchor.resolve request payload sample missing {field_name}")

    source_anchor_id = payload.get("source_anchor_id")
    if "source_anchor_id" in payload:
        if not isinstance(source_anchor_id, str):
            failures.append("source_anchor.resolve request source_anchor_id must be a string")
        elif compiled_source_anchor_pattern is not None and not compiled_source_anchor_pattern.fullmatch(source_anchor_id):
            failures.append(
                "source_anchor.resolve request source_anchor_id must match source_anchor_[16 lowercase hex]"
            )

    return failures


def source_anchor_resolve_response_sample_failures(
    payload: object,
    response_variant: dict[str, object],
    compiled_source_anchor_pattern: re.Pattern[str] | None,
    document_schema: dict[str, object],
    chunk_summary_schema: dict[str, object],
) -> list[str]:
    if not isinstance(payload, dict):
        return ["source_anchor.resolve response payload sample must be an object"]

    properties = response_variant.get("properties")
    if not isinstance(properties, dict):
        return ["source_anchor.resolve response variant properties must be an object"]

    required = response_variant.get("required")
    if not isinstance(required, list):
        return ["source_anchor.resolve response variant required fields must be a list"]

    failures: list[str] = []
    unknown_fields = sorted(set(payload) - set(properties))
    if unknown_fields:
        failures.append(
            "source_anchor.resolve response payload sample includes unknown fields: "
            + ", ".join(unknown_fields)
        )

    for field_name in required:
        if isinstance(field_name, str) and field_name not in payload:
            failures.append(f"source_anchor.resolve response payload sample missing {field_name}")

    source_anchor_id = payload.get("source_anchor_id")
    if "source_anchor_id" in payload:
        if not isinstance(source_anchor_id, str):
            failures.append("source_anchor.resolve response source_anchor_id must be a string")
        elif compiled_source_anchor_pattern is not None and not compiled_source_anchor_pattern.fullmatch(source_anchor_id):
            failures.append(
                "source_anchor.resolve response source_anchor_id must match source_anchor_[16 lowercase hex]"
            )

    document = payload.get("document")
    if "document" in payload:
        failures.extend(
            index_document_sample_failures(
                document,
                document_schema,
                0,
                path="source_anchor.resolve.document",
            )
        )

    chunk_summary = payload.get("chunk_summary")
    if "chunk_summary" in payload:
        failures.extend(
            source_anchor_chunk_summary_sample_failures(
                chunk_summary,
                chunk_summary_schema,
            )
        )

    return failures


def source_anchor_chunk_summary_sample_failures(
    chunk_summary: object,
    chunk_summary_schema: dict[str, object],
) -> list[str]:
    if not isinstance(chunk_summary, dict):
        return ["source_anchor.resolve chunk_summary must be an object"]

    properties = chunk_summary_schema.get("properties")
    if not isinstance(properties, dict):
        return ["sourceAnchorChunkSummary properties must be an object"]

    required = chunk_summary_schema.get("required")
    if not isinstance(required, list):
        return ["sourceAnchorChunkSummary required fields must be a list"]

    failures: list[str] = []
    unknown_fields = sorted(set(chunk_summary) - set(properties))
    if unknown_fields:
        failures.append(
            "source_anchor.resolve chunk_summary includes unknown fields: "
            + ", ".join(unknown_fields)
        )

    for field_name in required:
        if isinstance(field_name, str) and field_name not in chunk_summary:
            failures.append(f"source_anchor.resolve chunk_summary missing {field_name}")

    for integer_field_name in (
        "chunk_index",
        "start_character_offset",
        "end_character_offset",
        "character_count",
    ):
        if integer_field_name not in chunk_summary:
            continue
        value = chunk_summary.get(integer_field_name)
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append(f"source_anchor.resolve chunk_summary.{integer_field_name} must be an integer")
            continue
        field_schema = properties.get(integer_field_name)
        if not isinstance(field_schema, dict):
            continue
        minimum = field_schema.get("minimum")
        if isinstance(minimum, int) and value < minimum:
            failures.append(f"source_anchor.resolve chunk_summary.{integer_field_name} below minimum")

    start_character_offset = chunk_summary.get("start_character_offset")
    end_character_offset = chunk_summary.get("end_character_offset")
    if (
        isinstance(start_character_offset, int)
        and not isinstance(start_character_offset, bool)
        and isinstance(end_character_offset, int)
        and not isinstance(end_character_offset, bool)
        and end_character_offset < start_character_offset
    ):
        failures.append(
            "source_anchor.resolve chunk_summary.end_character_offset must be greater than or equal to start_character_offset"
        )

    return failures


def build_retrieval_query_response_source_anchor_sample(
    source_anchor_id: object | None,
    *,
    document_overrides: dict[str, object] | None = None,
    omit_document_fields: tuple[str, ...] = (),
    result_overrides: dict[str, object] | None = None,
    omit_result_fields: tuple[str, ...] = (),
    result_count: int = 1,
) -> dict[str, object]:
    document: dict[str, object] = {
        "id": "protocol-source-anchor-sample",
        "display_name": "Protocol Source Anchor Sample",
        "mime_type": "text/plain",
        "content_fingerprint": "0011223344556677",
        "extracted_character_count": 42,
        "chunk_count": 1,
        "quality": "single_chunk",
    }
    if document_overrides is not None:
        document.update(document_overrides)
    for field_name in omit_document_fields:
        document.pop(field_name, None)

    result: dict[str, object] = {
        "document": document,
        "chunk_index": 0,
        "start_character_offset": 0,
        "end_character_offset": 42,
        "rank": 101,
        "matched_terms": ["protocol"],
        "snippet": "protocol source anchor sample",
    }
    if source_anchor_id is not None:
        result["source_anchor_id"] = source_anchor_id
    if result_overrides is not None:
        result.update(result_overrides)
    for field_name in omit_result_fields:
        result.pop(field_name, None)
    return {"results": [dict(result) for _ in range(result_count)]}


def build_retrieval_query_request_source_anchor_sample(
    *,
    include_query: bool = True,
    query: object = "protocol source anchor",
    limit: object = 3,
    max_snippet_characters: object = 160,
    embedding_model_id: object | None = "ollama:nomic-embed-text",
    source_anchor_id: object | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "limit": limit,
        "max_snippet_characters": max_snippet_characters,
    }
    if include_query:
        payload["query"] = query
    if embedding_model_id is not None:
        payload["embedding_model_id"] = embedding_model_id
    if source_anchor_id is not None:
        payload["source_anchor_id"] = source_anchor_id
    return payload


def retrieval_query_request_source_anchor_sample_failures(
    payload: object,
    request_variant: dict[str, object],
) -> list[str]:
    if not isinstance(payload, dict):
        return ["retrieval.query request payload sample must be an object"]

    properties = request_variant.get("properties")
    if not isinstance(properties, dict):
        return ["retrieval.query request variant properties must be an object"]

    required = request_variant.get("required")
    if not isinstance(required, list):
        return ["retrieval.query request variant required fields must be a list"]

    failures: list[str] = []
    unknown_fields = sorted(set(payload) - set(properties))
    if unknown_fields:
        failures.append(
            "retrieval.query request payload sample includes unknown fields: "
            + ", ".join(unknown_fields)
        )

    for field_name in required:
        if isinstance(field_name, str) and field_name not in payload:
            failures.append(f"retrieval.query request payload sample missing {field_name}")

    query = payload.get("query")
    if not isinstance(query, str):
        failures.append("retrieval.query request payload sample query must be a string")
    elif not query.strip():
        failures.append("retrieval.query request payload sample query must be nonblank")
    else:
        query_schema = properties.get("query")
        query_max_length: object | None = None
        if isinstance(query_schema, dict):
            direct_max_length = query_schema.get("maxLength")
            if isinstance(direct_max_length, int):
                query_max_length = direct_max_length
            all_of = query_schema.get("allOf")
            if isinstance(all_of, list):
                for schema_part in all_of:
                    if not isinstance(schema_part, dict):
                        continue
                    nested_max_length = schema_part.get("maxLength")
                    if isinstance(nested_max_length, int):
                        query_max_length = nested_max_length
        if isinstance(query_max_length, int) and len(query) > query_max_length:
            failures.append("retrieval.query request payload sample query above maximum length")

    embedding_model_id = payload.get("embedding_model_id")
    if embedding_model_id is not None:
        if not isinstance(embedding_model_id, str):
            failures.append(
                "retrieval.query request payload sample embedding_model_id must be a string"
            )
        elif not embedding_model_id.strip():
            failures.append(
                "retrieval.query request payload sample embedding_model_id must be nonblank"
            )

    for integer_field_name in ("limit", "max_snippet_characters"):
        if integer_field_name not in payload:
            continue
        value = payload.get(integer_field_name)
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append(
                f"retrieval.query request payload sample {integer_field_name} must be an integer"
            )
            continue

        field_schema = properties.get(integer_field_name)
        if not isinstance(field_schema, dict):
            continue
        minimum = field_schema.get("minimum")
        if isinstance(minimum, int) and value < minimum:
            failures.append(
                f"retrieval.query request payload sample {integer_field_name} below minimum"
            )
        maximum = field_schema.get("maximum")
        if isinstance(maximum, int) and value > maximum:
            failures.append(
                f"retrieval.query request payload sample {integer_field_name} above maximum"
            )

    return failures


def retrieval_query_response_source_anchor_sample_failures(
    payload: object,
    compiled_source_anchor_pattern: re.Pattern[str],
    result_schema: dict[str, object],
    max_results_count: int | None = None,
    document_schema: dict[str, object] | None = None,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["retrieval.query response payload sample must be an object"]

    results = payload.get("results")
    if not isinstance(results, list):
        return ["retrieval.query response payload sample must include results array"]

    properties = result_schema.get("properties")
    if not isinstance(properties, dict):
        return ["retrieval.query result schema properties must be an object"]

    required = result_schema.get("required")
    if not isinstance(required, list):
        return ["retrieval.query result schema required fields must be a list"]

    failures: list[str] = []
    if isinstance(max_results_count, int) and len(results) > max_results_count:
        failures.append("retrieval.query response payload sample results above maximum items")

    for index, result in enumerate(results):
        if not isinstance(result, dict):
            failures.append(f"results[{index}] must be an object")
            continue

        unknown_fields = sorted(set(result) - set(properties))
        if unknown_fields:
            failures.append(
                f"results[{index}] includes unknown fields: " + ", ".join(unknown_fields)
            )

        for field_name in required:
            if isinstance(field_name, str) and field_name not in result:
                failures.append(f"results[{index}] missing {field_name}")

        document = result.get("document")
        if not isinstance(document, dict):
            failures.append(f"results[{index}].document must be an object")
        elif isinstance(document_schema, dict):
            failures.extend(
                index_document_sample_failures(
                    document,
                    document_schema,
                    index,
                    path=f"results[{index}].document",
                )
            )

        if "source_anchor_id" not in result:
            failures.append(f"results[{index}].source_anchor_id is required")
        else:
            source_anchor_id = result.get("source_anchor_id")
            if not isinstance(source_anchor_id, str):
                failures.append(f"results[{index}].source_anchor_id must be a string")
            elif not compiled_source_anchor_pattern.fullmatch(source_anchor_id):
                failures.append(
                    f"results[{index}].source_anchor_id must match source_anchor_[16 lowercase hex]"
                )

        for integer_field_name in (
            "chunk_index",
            "start_character_offset",
            "end_character_offset",
            "rank",
        ):
            if integer_field_name not in result:
                continue
            value = result.get(integer_field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                failures.append(f"results[{index}].{integer_field_name} must be an integer")
                continue

            field_schema = properties.get(integer_field_name)
            if not isinstance(field_schema, dict):
                continue
            minimum = field_schema.get("minimum")
            if isinstance(minimum, int) and value < minimum:
                failures.append(f"results[{index}].{integer_field_name} below minimum")

        start_character_offset = result.get("start_character_offset")
        end_character_offset = result.get("end_character_offset")
        if (
            isinstance(start_character_offset, int)
            and not isinstance(start_character_offset, bool)
            and isinstance(end_character_offset, int)
            and not isinstance(end_character_offset, bool)
            and end_character_offset < start_character_offset
        ):
            failures.append(
                f"results[{index}].end_character_offset must be greater than or equal to start_character_offset"
            )

        matched_terms = result.get("matched_terms")
        match_kind = result.get("match_kind", "lexical")
        if match_kind not in {"lexical", "semantic"}:
            failures.append(f"results[{index}].match_kind must be lexical or semantic")
        if "matched_terms" in result:
            if not isinstance(matched_terms, list):
                failures.append(f"results[{index}].matched_terms must be an array")
            else:
                matched_terms_schema = properties.get("matched_terms")
                matched_terms_max_items = (
                    matched_terms_schema.get("maxItems")
                    if isinstance(matched_terms_schema, dict)
                    and isinstance(matched_terms_schema.get("maxItems"), int)
                    else None
                )
                matched_terms_min_items = (
                    matched_terms_schema.get("minItems")
                    if isinstance(matched_terms_schema, dict)
                    and isinstance(matched_terms_schema.get("minItems"), int)
                    else None
                )
                matched_term_max_length: object | None = None
                matched_terms_items = (
                    matched_terms_schema.get("items")
                    if isinstance(matched_terms_schema, dict)
                    else None
                )
                if isinstance(matched_terms_items, dict):
                    direct_max_length = matched_terms_items.get("maxLength")
                    if isinstance(direct_max_length, int):
                        matched_term_max_length = direct_max_length
                    all_of = matched_terms_items.get("allOf")
                    if isinstance(all_of, list):
                        for schema_part in all_of:
                            if not isinstance(schema_part, dict):
                                continue
                            nested_max_length = schema_part.get("maxLength")
                            if isinstance(nested_max_length, int):
                                matched_term_max_length = nested_max_length
                if isinstance(matched_terms_min_items, int) and len(matched_terms) < matched_terms_min_items:
                    failures.append(f"results[{index}].matched_terms below minimum items")
                if match_kind != "semantic" and not matched_terms:
                    failures.append(
                        f"results[{index}].matched_terms must be nonempty for lexical matches"
                    )
                if isinstance(matched_terms_max_items, int) and len(matched_terms) > matched_terms_max_items:
                    failures.append(f"results[{index}].matched_terms above maximum items")
                for term_index, matched_term in enumerate(matched_terms):
                    if not isinstance(matched_term, str) or not matched_term.strip():
                        failures.append(
                            f"results[{index}].matched_terms[{term_index}] must be a non-empty string"
                        )
                    elif (
                        isinstance(matched_term_max_length, int)
                        and len(matched_term) > matched_term_max_length
                    ):
                        failures.append(
                            f"results[{index}].matched_terms[{term_index}] above maximum length"
                        )

        snippet = result.get("snippet")
        if "snippet" in result and (not isinstance(snippet, str) or not snippet):
            failures.append(f"results[{index}].snippet must be a non-empty string")
        elif isinstance(snippet, str):
            snippet_schema = properties.get("snippet")
            snippet_max_length: object | None = None
            if isinstance(snippet_schema, dict):
                direct_max_length = snippet_schema.get("maxLength")
                if isinstance(direct_max_length, int):
                    snippet_max_length = direct_max_length
                all_of = snippet_schema.get("allOf")
                if isinstance(all_of, list):
                    for schema_part in all_of:
                        if not isinstance(schema_part, dict):
                            continue
                        nested_max_length = schema_part.get("maxLength")
                        if isinstance(nested_max_length, int):
                            snippet_max_length = nested_max_length
            if isinstance(snippet_max_length, int) and len(snippet) > snippet_max_length:
                failures.append(f"results[{index}].snippet above maximum length")
    return failures


def check_chat_message_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatMessage schema"]
    chat_message = defs.get("chatMessage")
    if not isinstance(chat_message, dict):
        return ["$defs.chatMessage schema is missing"]

    properties = chat_message.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.chatMessage.properties must be an object")
    else:
        allowed_keys = {"role", "content", "attachments"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append("$defs.chatMessage.properties must stay limited to role, content, and attachments")
        forbidden_keys = {
            "source_path",
            "file_path",
            "workspace_id",
            "source_control_status",
            "backend_url",
            "backend_credentials",
            "route_token",
            "trusted_source",
            "runtime_memory",
            "tool_results",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatMessage.properties includes future source/workspace/backend metadata "
                f"{leaked_keys}"
            )
    if chat_message.get("additionalProperties") is not False:
        failures.append("$defs.chatMessage.additionalProperties must be false")
    return failures


def check_chat_send_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatSendPayload schema"]
    chat_send_payload = defs.get("chatSendPayload")
    if not isinstance(chat_send_payload, dict):
        return ["$defs.chatSendPayload schema is missing"]

    properties = chat_send_payload.get("properties")
    if chat_send_payload.get("required") != ["session_id", "model", "messages"]:
        failures.append("$defs.chatSendPayload must require session_id, model, and messages")
    if not isinstance(properties, dict):
        failures.append("$defs.chatSendPayload.properties must be an object")
    else:
        allowed_keys = {
            "session_id",
            "model",
            "locale",
            "messages",
            "trusted_source_grant_ids",
        }
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatSendPayload.properties must stay limited to session_id, model, locale, messages, and trusted_source_grant_ids"
            )
        forbidden_keys = {
            "project_id",
            "workspace_id",
            "retrieval_context",
            "permission_grant",
            "source_path",
            "source_control_status",
            "backend_url",
            "backend_credentials",
            "route_token",
            "trusted_source",
            "tool_results",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatSendPayload.properties includes future project/RAG/backend metadata "
                f"{leaked_keys}"
            )
        if properties.get("session_id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatSendPayload request session_id must use nonBlankString")
        if properties.get("model", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatSendPayload request model must use nonBlankString")
        if properties.get("locale") != {"type": "string"}:
            failures.append("$defs.chatSendPayload request locale must be an optional string")
        if properties.get("messages", {}).get("minItems") != 1:
            failures.append("$defs.chatSendPayload request messages must require at least one item")
        trusted_source_grant_ids = properties.get("trusted_source_grant_ids")
        if trusted_source_grant_ids != {
            "type": "array",
            "items": {"$ref": "#/$defs/trustedSourceGrantID"},
            "minItems": 1,
            "maxItems": 8,
            "uniqueItems": True,
        }:
            failures.append(
                "$defs.chatSendPayload request trusted_source_grant_ids must be an optional unique array of 1 through 8 canonical grant ids"
            )
    if chat_send_payload.get("additionalProperties") is not False:
        failures.append("$defs.chatSendPayload.additionalProperties must be false")
    return failures


def check_research_notebook_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include research notebook schemas"]

    def bounded_non_blank(maximum: int) -> dict[str, object]:
        return {
            "allOf": [
                {"$ref": "#/$defs/nonBlankString"},
                {"maxLength": maximum},
            ]
        }

    expected_defs = {
        "researchNotebookID": {
            "type": "string",
            "pattern": r"^research_notebook_[0-9a-f]{32}$",
        },
        "researchBriefCreatePayload": {
            "type": "object",
            "required": [
                "notebook_id",
                "session_id",
                "topic",
                "model",
                "trusted_source_grant_ids",
            ],
            "properties": {
                "notebook_id": {"$ref": "#/$defs/researchNotebookID"},
                "session_id": bounded_non_blank(256),
                "topic": bounded_non_blank(2048),
                "model": bounded_non_blank(256),
                "locale": bounded_non_blank(64),
                "trusted_source_grant_ids": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/trustedSourceGrantID"},
                    "minItems": 1,
                    "maxItems": 8,
                    "uniqueItems": True,
                },
            },
            "additionalProperties": False,
        },
        "researchNotebook": {
            "type": "object",
            "required": [
                "notebook_id",
                "session_id",
                "title",
                "model",
                "source_count",
                "created_at",
                "updated_at",
            ],
            "properties": {
                "notebook_id": {"$ref": "#/$defs/researchNotebookID"},
                "session_id": bounded_non_blank(256),
                "title": bounded_non_blank(256),
                "model": bounded_non_blank(256),
                "source_count": {"type": "integer", "minimum": 1, "maximum": 8},
                "created_at": {"$ref": "#/$defs/iso8601DateTime"},
                "updated_at": {"$ref": "#/$defs/iso8601DateTime"},
                "archived_at": {"$ref": "#/$defs/iso8601DateTime"},
            },
            "additionalProperties": False,
        },
        "researchNotebooksListPayload": {
            "oneOf": [
                {
                    "type": "object",
                    "required": ["include_archived", "limit"],
                    "properties": {
                        "include_archived": {"type": "boolean"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "required": ["cursor"],
                    "properties": {
                        "cursor": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 512,
                            "pattern": "^[A-Za-z0-9._-]+$",
                        }
                    },
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "required": ["notebooks"],
                    "properties": {
                        "notebooks": {
                            "type": "array",
                            "maxItems": 100,
                            "uniqueItems": True,
                            "items": {"$ref": "#/$defs/researchNotebook"},
                        }
                    },
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "required": ["notebooks", "snapshot_count"],
                    "properties": {
                        "notebooks": {
                            "type": "array",
                            "maxItems": 200,
                            "uniqueItems": True,
                            "items": {"$ref": "#/$defs/researchNotebook"},
                        },
                        "snapshot_count": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 10000,
                        },
                        "next_cursor": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 512,
                            "pattern": "^[A-Za-z0-9._-]+$",
                        },
                    },
                    "additionalProperties": False,
                },
            ]
        },
    }

    for name, expected in expected_defs.items():
        if not json_values_equal(defs.get(name), expected):
            failures.append(f"$defs.{name} must match the exact research contract and JSON types")

    expected_payload_refs = {
        "research.brief.create": "#/$defs/researchBriefCreatePayload",
        "research.notebooks.list": "#/$defs/researchNotebooksListPayload",
    }
    actual_payload_refs: dict[str, list[object]] = {
        message_type: [] for message_type in expected_payload_refs
    }
    for rule in schema.get("allOf", []):
        if not isinstance(rule, dict):
            continue
        message_type = rule.get("if", {}).get("properties", {}).get("type", {}).get("const")
        if message_type in expected_payload_refs:
            actual_payload_refs[message_type].append(
                rule.get("then", {}).get("properties", {}).get("payload", {}).get("$ref")
            )
    expected_payload_ref_lists = {
        message_type: [payload_ref]
        for message_type, payload_ref in expected_payload_refs.items()
    }
    if not json_values_equal(actual_payload_refs, expected_payload_ref_lists):
        failures.append("research message payload mappings must match the exact active contract")

    return failures


def check_chat_title_request_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatTitleRequestPayload schema"]
    title_payload = defs.get("chatTitleRequestPayload")
    if not isinstance(title_payload, dict):
        return ["$defs.chatTitleRequestPayload schema is missing"]

    properties = title_payload.get("properties")
    if title_payload.get("required") != ["session_id", "model", "messages"]:
        failures.append("$defs.chatTitleRequestPayload must require session_id, model, and messages")
    if not isinstance(properties, dict):
        failures.append("$defs.chatTitleRequestPayload.properties must be an object")
    else:
        allowed_keys = {"session_id", "model", "locale", "messages"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatTitleRequestPayload.properties must stay limited to session_id, model, locale, and messages"
            )
        forbidden_keys = {
            "title",
            "project_id",
            "workspace_id",
            "retrieval_context",
            "permission_grant",
            "source_path",
            "source_control_status",
            "backend_url",
            "backend_credentials",
            "route_token",
            "trusted_source",
            "tool_results",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatTitleRequestPayload.properties includes response/project/RAG/backend metadata "
                f"{leaked_keys}"
            )
        if properties.get("session_id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatTitleRequestPayload request session_id must use nonBlankString")
        if properties.get("model", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatTitleRequestPayload request model must use nonBlankString")
        if properties.get("locale") != {"type": "string"}:
            failures.append("$defs.chatTitleRequestPayload request locale must be an optional string")
        if properties.get("messages", {}).get("minItems") != 1:
            failures.append("$defs.chatTitleRequestPayload request messages must require at least one item")
    if title_payload.get("additionalProperties") is not False:
        failures.append("$defs.chatTitleRequestPayload.additionalProperties must be false")
    return failures


def check_pre_auth_payload_schema_contracts(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include pre-auth payload schemas"]

    closed_object_payloads = {
        "pairingRequestPayload": {
            "pairing_nonce",
            "pairing_code",
            "device_id",
            "device_name",
            "public_key",
            "pairing_proof_scheme",
            "pairing_signature",
            "transport_binding",
        },
        "helloPayload": {
            "device_id",
            "device_name",
            "client_capabilities",
            "transport_binding",
        },
    }
    for payload_name, expected_keys in closed_object_payloads.items():
        payload_schema = defs.get(payload_name)
        if not isinstance(payload_schema, dict):
            failures.append(f"$defs.{payload_name} schema is missing")
            continue
        properties = payload_schema.get("properties")
        if not isinstance(properties, dict):
            failures.append(f"$defs.{payload_name}.properties must be an object")
        elif set(properties.keys()) != expected_keys:
            failures.append(f"$defs.{payload_name} request properties must stay limited to {sorted(expected_keys)}")
        if payload_schema.get("additionalProperties") is not False:
            failures.append(f"$defs.{payload_name} request additionalProperties must be false")
        if payload_name == "pairingRequestPayload" and isinstance(properties, dict):
            if payload_schema.get("required") != [
                "pairing_nonce",
                "pairing_code",
                "device_id",
                "device_name",
                "public_key",
                "pairing_proof_scheme",
                "pairing_signature",
            ]:
                failures.append("$defs.pairingRequestPayload request must require identity fields and pairing proof fields")
            for field in [
                "pairing_nonce",
                "pairing_code",
                "device_id",
                "device_name",
                "public_key",
                "pairing_signature",
            ]:
                if properties.get(field, {}).get("$ref") != "#/$defs/nonBlankString":
                    failures.append(f"$defs.pairingRequestPayload request {field} must use nonBlankString")
            if properties.get("pairing_proof_scheme", {}).get("$ref") != "#/$defs/pairingProofScheme":
                failures.append("$defs.pairingRequestPayload pairing_proof_scheme must use pairingProofScheme")
            if properties.get("transport_binding", {}).get("$ref") != "#/$defs/transportBinding":
                failures.append("$defs.pairingRequestPayload transport_binding must use transportBinding")
        if payload_name == "helloPayload" and isinstance(properties, dict):
            if payload_schema.get("required") != ["device_id"]:
                failures.append("$defs.helloPayload request must require only device_id")
            if properties.get("device_id", {}).get("$ref") != "#/$defs/nonBlankString":
                failures.append("$defs.helloPayload request device_id must use nonBlankString")
            if properties.get("device_name", {}).get("$ref") != "#/$defs/nonBlankString":
                failures.append("$defs.helloPayload request device_name must use nonBlankString")
            client_capabilities = properties.get("client_capabilities", {})
            if not isinstance(client_capabilities, dict):
                failures.append("$defs.helloPayload client_capabilities must be an object schema")
            else:
                if client_capabilities.get("type") != "array":
                    failures.append("$defs.helloPayload client_capabilities must be an array")
                if client_capabilities.get("items", {}).get("$ref") != "#/$defs/nonBlankString":
                    failures.append("$defs.helloPayload client_capabilities items must use nonBlankString")
                if client_capabilities.get("maxItems") != 64:
                    failures.append("$defs.helloPayload client_capabilities must allow at most 64 values")
                if client_capabilities.get("uniqueItems") is not True:
                    failures.append("$defs.helloPayload client_capabilities must keep uniqueItems true")
            if properties.get("transport_binding", {}).get("$ref") != "#/$defs/transportBinding":
                failures.append("$defs.helloPayload transport_binding must use transportBinding")

    transport_binding = defs.get("transportBinding")
    if transport_binding != {
        "type": "string",
        "minLength": 64,
        "maxLength": 64,
        "pattern": "^[0-9a-f]{64}$",
    }:
        failures.append("$defs.transportBinding must require exactly 64 lowercase hexadecimal characters")

    if defs.get("pairingProofScheme") != {"const": "p256-sha256-der-v1"}:
        failures.append("$defs.pairingProofScheme must use p256-sha256-der-v1")
    if defs.get("sha256HexDigest") != {
        "type": "string",
        "minLength": 64,
        "maxLength": 64,
        "pattern": "^[0-9a-f]{64}$",
    }:
        failures.append("$defs.sha256HexDigest must require exactly 64 lowercase hexadecimal characters")

    pairing_result = defs.get("pairingResultPayload")
    if not isinstance(pairing_result, dict) or not isinstance(pairing_result.get("oneOf"), list):
        failures.append("$defs.pairingResultPayload must separate accepted and rejected results")
    else:
        result_options = pairing_result["oneOf"]
        accepted_result = next(
            (
                option for option in result_options
                if isinstance(option, dict)
                and isinstance(option.get("properties"), dict)
                and option["properties"].get("accepted") == {"const": True}
            ),
            None,
        )
        rejected_result = next(
            (
                option for option in result_options
                if isinstance(option, dict)
                and isinstance(option.get("properties"), dict)
                and option["properties"].get("accepted") == {"const": False}
            ),
            None,
        )
        proof_fields = {
            "pairing_proof_scheme",
            "pairing_request_digest",
            "runtime_pairing_signature",
        }
        if not isinstance(accepted_result, dict):
            failures.append("$defs.pairingResultPayload accepted=true branch is missing")
        else:
            accepted_properties = accepted_result.get("properties", {})
            accepted_required_fields = {
                "accepted",
                "runtime_device_id",
                "runtime_public_key",
                "runtime_key_fingerprint",
                "trusted_device_id",
                "message",
                *proof_fields,
            }
            if set(accepted_result.get("required", [])) != accepted_required_fields:
                failures.append(
                    "$defs.pairingResultPayload accepted=true must require runtime identity, "
                    "trusted device, message, and all pairing proof fields"
                )
            if accepted_result.get("additionalProperties") is not False:
                failures.append("$defs.pairingResultPayload accepted=true additionalProperties must be false")
            if accepted_properties.get("pairing_proof_scheme", {}).get("$ref") != "#/$defs/pairingProofScheme":
                failures.append("$defs.pairingResultPayload accepted pairing_proof_scheme must use pairingProofScheme")
            if accepted_properties.get("pairing_request_digest", {}).get("$ref") != "#/$defs/sha256HexDigest":
                failures.append("$defs.pairingResultPayload accepted pairing_request_digest must use sha256HexDigest")
            if accepted_properties.get("runtime_pairing_signature", {}).get("$ref") != "#/$defs/nonBlankString":
                failures.append("$defs.pairingResultPayload accepted runtime_pairing_signature must use nonBlankString")
            if accepted_properties.get("transport_binding", {}).get("$ref") != "#/$defs/transportBinding":
                failures.append("$defs.pairingResultPayload accepted transport_binding must use transportBinding")
        if not isinstance(rejected_result, dict):
            failures.append("$defs.pairingResultPayload accepted=false branch is missing")
        else:
            rejected_properties = rejected_result.get("properties", {})
            if proof_fields & set(rejected_properties):
                failures.append("$defs.pairingResultPayload rejected results must not allow pairing proof fields")
            if "transport_binding" in rejected_properties:
                failures.append("$defs.pairingResultPayload rejected results must not allow transport_binding")
            if rejected_result.get("required") != ["accepted"]:
                failures.append("$defs.pairingResultPayload rejected results must require only accepted")
            if rejected_result.get("additionalProperties") is not False:
                failures.append("$defs.pairingResultPayload rejected additionalProperties must be false")

    auth_challenge_payload = defs.get("authChallengePayload")
    if not isinstance(auth_challenge_payload, dict):
        failures.append("$defs.authChallengePayload schema is missing")
    else:
        properties = auth_challenge_payload.get("properties")
        expected_keys = {
            "device_id",
            "nonce",
            "runtime_key_fingerprint",
            "runtime_signature",
            "transport_binding",
        }
        if not isinstance(properties, dict) or set(properties.keys()) != expected_keys:
            failures.append(
                "$defs.authChallengePayload properties must stay limited to device identity, nonce, runtime proof, and transport binding"
            )
        elif properties.get("transport_binding", {}).get("$ref") != "#/$defs/transportBinding":
            failures.append("$defs.authChallengePayload transport_binding must use transportBinding")
        if auth_challenge_payload.get("required") != ["device_id", "nonce"]:
            failures.append("$defs.authChallengePayload must require only device_id and nonce")
        if auth_challenge_payload.get("additionalProperties") is not False:
            failures.append("$defs.authChallengePayload additionalProperties must be false")

    auth_response_payload = defs.get("authResponsePayload")
    if not isinstance(auth_response_payload, dict):
        failures.append("$defs.authResponsePayload schema is missing")
        return failures
    options = auth_response_payload.get("oneOf")
    if not isinstance(options, list):
        failures.append("$defs.authResponsePayload.oneOf must describe request and accepted response payloads")
        return failures
    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["device_id", "nonce", "signature"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        failures.append("$defs.authResponsePayload must include a device_id nonce signature request payload option")
        return failures
    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.authResponsePayload request properties must be an object")
    elif set(properties.keys()) != {"device_id", "nonce", "signature", "transport_binding"}:
        failures.append(
            "$defs.authResponsePayload request properties must stay limited to device_id, nonce, signature, and transport_binding"
        )
    else:
        for field in ["device_id", "nonce", "signature"]:
            if properties.get(field, {}).get("$ref") != "#/$defs/nonBlankString":
                failures.append(f"$defs.authResponsePayload request {field} must use nonBlankString")
        if properties.get("transport_binding", {}).get("$ref") != "#/$defs/transportBinding":
            failures.append("$defs.authResponsePayload request transport_binding must use transportBinding")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.authResponsePayload request additionalProperties must be false")

    accepted_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["accepted", "device_id"]
        ),
        None,
    )
    if not isinstance(accepted_option, dict):
        failures.append("$defs.authResponsePayload must include an accepted device response payload option")
    else:
        properties = accepted_option.get("properties")
        if not isinstance(properties, dict) or set(properties.keys()) != {
            "accepted",
            "device_id",
            "transport_binding",
        }:
            failures.append(
                "$defs.authResponsePayload accepted response properties must stay limited to accepted, device_id, and transport_binding"
            )
        elif properties.get("transport_binding", {}).get("$ref") != "#/$defs/transportBinding":
            failures.append("$defs.authResponsePayload accepted transport_binding must use transportBinding")
        if accepted_option.get("additionalProperties") is not False:
            failures.append("$defs.authResponsePayload accepted additionalProperties must be false")

    return failures


def check_empty_request_payload_schema_contracts(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include empty-request payload schemas"]

    empty_payload = defs.get("emptyPayload")
    if not isinstance(empty_payload, dict):
        return ["$defs.emptyPayload schema is missing"]
    if empty_payload.get("type") != "object" or empty_payload.get("maxProperties") != 0:
        failures.append("$defs.emptyPayload request must stay an object with maxProperties 0")

    payload_defs = {
        "runtimeHealthPayload": "runtime.health",
        "modelsListPayload": "models.list",
        "routeRefreshPayload": "route.refresh",
    }
    empty_request_failure_messages = {
        "runtimeHealthPayload": "$defs.runtimeHealthPayload request must stay empty for runtime.health",
        "modelsListPayload": "$defs.modelsListPayload request must stay empty for models.list",
        "routeRefreshPayload": "$defs.routeRefreshPayload request must stay empty for route.refresh",
    }
    for payload_def, message_type in payload_defs.items():
        payload_schema = defs.get(payload_def)
        if not isinstance(payload_schema, dict):
            failures.append(f"$defs.{payload_def} schema is missing")
            continue
        options = payload_schema.get("oneOf")
        if not isinstance(options, list):
            failures.append(f"$defs.{payload_def}.oneOf must describe empty request and response payloads")
            continue
        has_empty_request = any(
            isinstance(option, dict) and option.get("$ref") == "#/$defs/emptyPayload"
            for option in options
        )
        if not has_empty_request:
            failures.append(empty_request_failure_messages[payload_def])

    models_result = defs.get("modelsResultPayload")
    if not isinstance(models_result, dict):
        failures.append("$defs.modelsResultPayload schema is missing")
    elif models_result.get("required") != ["models"]:
        failures.append("$defs.modelsResultPayload response must require models")
    elif models_result.get("additionalProperties") is not False:
        failures.append("$defs.modelsResultPayload additionalProperties must be false")

    return failures


def check_models_pull_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include modelsPullPayload schema"]
    models_pull_payload = defs.get("modelsPullPayload")
    if not isinstance(models_pull_payload, dict):
        return ["$defs.modelsPullPayload schema is missing"]

    options = models_pull_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.modelsPullPayload.oneOf must describe request and result payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["model"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.modelsPullPayload must include a model-only request payload option"]

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.modelsPullPayload request properties must be an object")
    else:
        allowed_keys = {"model", "backend"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append("$defs.modelsPullPayload request properties must stay limited to model and backend")
        forbidden_keys = {
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.modelsPullPayload request properties includes future backend/route/workspace metadata "
                f"{leaked_keys}"
            )
        if properties.get("model", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.modelsPullPayload request model must use nonBlankString")
        if properties.get("backend", {}).get("enum") != ["ollama"]:
            failures.append("$defs.modelsPullPayload request backend must stay limited to ollama")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.modelsPullPayload request additionalProperties must be false")
    return failures


def check_chat_cancel_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatCancelPayload schema"]
    chat_cancel_payload = defs.get("chatCancelPayload")
    if not isinstance(chat_cancel_payload, dict):
        return ["$defs.chatCancelPayload schema is missing"]

    options = chat_cancel_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.chatCancelPayload.oneOf must describe request and acknowledgement payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["target_request_id"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.chatCancelPayload must include a target_request_id-only request payload option"]

    acknowledgement_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["target_request_id", "cancelled"]
        ),
        None,
    )
    if not isinstance(acknowledgement_option, dict):
        failures.append("$defs.chatCancelPayload must include a target_request_id plus cancelled acknowledgement payload option")

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.chatCancelPayload request properties must be an object")
    else:
        allowed_keys = {"target_request_id"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append("$defs.chatCancelPayload request properties must stay limited to target_request_id")
        forbidden_keys = {
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "workspace_id",
            "permission_grant",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatCancelPayload request properties includes future backend/route/workspace metadata "
                f"{leaked_keys}"
            )
        if properties.get("target_request_id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatCancelPayload request target_request_id must use nonBlankString")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.chatCancelPayload request additionalProperties must be false")

    if isinstance(acknowledgement_option, dict):
        acknowledgement_properties = acknowledgement_option.get("properties")
        if not isinstance(acknowledgement_properties, dict):
            failures.append("$defs.chatCancelPayload acknowledgement properties must be an object")
        else:
            allowed_acknowledgement_keys = {"target_request_id", "cancelled"}
            actual_acknowledgement_keys = set(acknowledgement_properties.keys())
            if actual_acknowledgement_keys != allowed_acknowledgement_keys:
                failures.append(
                    "$defs.chatCancelPayload acknowledgement properties must stay limited to target_request_id and cancelled"
                )
            if acknowledgement_properties.get("target_request_id", {}).get("$ref") != "#/$defs/nonBlankString":
                failures.append("$defs.chatCancelPayload acknowledgement target_request_id must use nonBlankString")
            if acknowledgement_properties.get("cancelled") != {"type": "boolean"}:
                failures.append("$defs.chatCancelPayload acknowledgement cancelled must stay boolean")
        if acknowledgement_option.get("additionalProperties") is not False:
            failures.append("$defs.chatCancelPayload acknowledgement additionalProperties must be false")
    return failures


def check_chat_sessions_list_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatSessionsListPayload schema"]
    chat_sessions_list_payload = defs.get("chatSessionsListPayload")
    if not isinstance(chat_sessions_list_payload, dict):
        return ["$defs.chatSessionsListPayload schema is missing"]

    options = chat_sessions_list_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.chatSessionsListPayload.oneOf must describe request and response payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and isinstance(option.get("properties"), dict)
            and "limit" in option.get("properties", {})
            and "sessions" not in option.get("properties", {})
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.chatSessionsListPayload must include a session-list request payload option"]

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.chatSessionsListPayload request properties must be an object")
    else:
        allowed_keys = {"limit", "include_archived", "query", "embedding_model_id"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatSessionsListPayload request properties must stay limited to limit, include_archived, query, and embedding_model_id"
            )
        forbidden_keys = {
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
            "source_path",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatSessionsListPayload request properties includes future backend/route/workspace/source metadata "
                f"{leaked_keys}"
            )
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.chatSessionsListPayload request additionalProperties must be false")

    cursor_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["cursor"]
        ),
        None,
    )
    if not isinstance(cursor_option, dict):
        failures.append("$defs.chatSessionsListPayload must include a cursor-only continuation request")
    else:
        cursor_properties = cursor_option.get("properties")
        if not isinstance(cursor_properties, dict) or set(cursor_properties.keys()) != {"cursor"}:
            failures.append("$defs.chatSessionsListPayload cursor request must contain only cursor")
        else:
            cursor_schema = cursor_properties.get("cursor")
            if not isinstance(cursor_schema, dict) or cursor_schema.get("type") != "string":
                failures.append("$defs.chatSessionsListPayload cursor must stay a string")
            elif cursor_schema.get("minLength") != 1 or cursor_schema.get("maxLength") != 512:
                failures.append("$defs.chatSessionsListPayload cursor must stay bounded to 1...512 characters")
        if cursor_option.get("additionalProperties") is not False:
            failures.append("$defs.chatSessionsListPayload cursor request additionalProperties must be false")

    legacy_response = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["sessions"]
        ),
        None,
    )
    authoritative_response = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["sessions", "snapshot_count"]
        ),
        None,
    )
    if not isinstance(legacy_response, dict):
        failures.append("$defs.chatSessionsListPayload must preserve the legacy sessions-only response")
    if not isinstance(authoritative_response, dict):
        failures.append("$defs.chatSessionsListPayload must include the authoritative snapshot response")
    else:
        response_properties = authoritative_response.get("properties")
        if not isinstance(response_properties, dict):
            failures.append("$defs.chatSessionsListPayload authoritative response properties must be an object")
        else:
            if set(response_properties.keys()) != {"sessions", "snapshot_count", "next_cursor"}:
                failures.append(
                    "$defs.chatSessionsListPayload authoritative response must stay limited to sessions, snapshot_count, and next_cursor"
                )
            if response_properties.get("snapshot_count") != {
                "type": "integer",
                "minimum": 0,
                "maximum": 10000,
            }:
                failures.append("$defs.chatSessionsListPayload snapshot_count must stay bounded 0...10000")
            next_cursor = response_properties.get("next_cursor")
            if not isinstance(next_cursor, dict) or next_cursor.get("type") != "string":
                failures.append("$defs.chatSessionsListPayload next_cursor must stay an optional string")
            elif next_cursor.get("minLength") != 1 or next_cursor.get("maxLength") != 512:
                failures.append("$defs.chatSessionsListPayload next_cursor must stay bounded to 1...512 characters")
        if authoritative_response.get("additionalProperties") is not False:
            failures.append("$defs.chatSessionsListPayload authoritative response additionalProperties must be false")
    return failures


def check_chat_messages_list_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatMessagesListPayload schema"]
    chat_messages_list_payload = defs.get("chatMessagesListPayload")
    if not isinstance(chat_messages_list_payload, dict):
        return ["$defs.chatMessagesListPayload schema is missing"]

    options = chat_messages_list_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.chatMessagesListPayload.oneOf must describe request and response payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["session_id"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.chatMessagesListPayload must include a session_id-only request payload option"]

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.chatMessagesListPayload request properties must be an object")
    else:
        allowed_keys = {"session_id", "limit"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatMessagesListPayload request properties must stay limited to session_id and limit"
            )
        forbidden_keys = {
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
            "source_path",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatMessagesListPayload request properties includes future backend/route/workspace/source metadata "
                f"{leaked_keys}"
            )
        if properties.get("session_id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatMessagesListPayload request session_id must use nonBlankString")
        if properties.get("limit") != {"type": "integer", "minimum": 0, "maximum": 500}:
            failures.append("$defs.chatMessagesListPayload request limit must stay bounded 0...500")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.chatMessagesListPayload request additionalProperties must be false")

    response_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["session_id", "messages"]
        ),
        None,
    )
    if not isinstance(response_option, dict):
        failures.append("$defs.chatMessagesListPayload must include a session_id/messages response payload option")
    else:
        response_properties = response_option.get("properties")
        if not isinstance(response_properties, dict):
            failures.append("$defs.chatMessagesListPayload response properties must be an object")
        else:
            response_allowed_keys = {"session_id", "messages"}
            response_actual_keys = set(response_properties.keys())
            if response_actual_keys != response_allowed_keys:
                failures.append(
                    "$defs.chatMessagesListPayload response properties must stay limited to session_id and messages"
                )
            if response_properties.get("session_id", {}).get("$ref") != "#/$defs/nonEmptyString":
                failures.append("$defs.chatMessagesListPayload response session_id must use nonEmptyString")
            messages = response_properties.get("messages")
            message_items = messages.get("items") if isinstance(messages, dict) else None
            if not isinstance(message_items, dict) or message_items.get("$ref") != "#/$defs/chatStoredMessage":
                failures.append(
                    "$defs.chatMessagesListPayload response messages must reference chatStoredMessage"
                )
        if response_option.get("additionalProperties") is not False:
            failures.append("$defs.chatMessagesListPayload response additionalProperties must be false")

    chat_stored_message = defs.get("chatStoredMessage")
    if not isinstance(chat_stored_message, dict):
        failures.append("$defs.chatStoredMessage schema is missing")
    else:
        stored_message_properties = chat_stored_message.get("properties")
        if not isinstance(stored_message_properties, dict):
            failures.append("$defs.chatStoredMessage.properties must be an object")
        else:
            attachments = stored_message_properties.get("attachments")
            attachment_items = attachments.get("items") if isinstance(attachments, dict) else None
            if not isinstance(attachment_items, dict) or attachment_items.get("$ref") != "#/$defs/storedChatAttachment":
                failures.append("$defs.chatStoredMessage.attachments must reference storedChatAttachment")

    stored_chat_attachment = defs.get("storedChatAttachment")
    if not isinstance(stored_chat_attachment, dict):
        failures.append("$defs.storedChatAttachment schema is missing")
    else:
        if stored_chat_attachment.get("required") != ["type", "mime_type"]:
            failures.append("$defs.storedChatAttachment must require only type and mime_type")
        stored_attachment_properties = stored_chat_attachment.get("properties")
        if not isinstance(stored_attachment_properties, dict):
            failures.append("$defs.storedChatAttachment.properties must be an object")
        else:
            stored_allowed_keys = {"type", "mime_type", "name", "text"}
            stored_actual_keys = set(stored_attachment_properties.keys())
            if stored_actual_keys != stored_allowed_keys:
                failures.append(
                    "$defs.storedChatAttachment.properties must stay limited to type, mime_type, name, and text"
                )
            if "data_base64" in stored_attachment_properties:
                failures.append("$defs.storedChatAttachment must not include data_base64")
        if stored_chat_attachment.get("additionalProperties") is not False:
            failures.append("$defs.storedChatAttachment.additionalProperties must be false")
    return failures


def check_chat_session_lifecycle_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatSessionLifecycleRequestPayload schema"]
    lifecycle_payload = defs.get("chatSessionLifecycleRequestPayload")
    if not isinstance(lifecycle_payload, dict):
        return ["$defs.chatSessionLifecycleRequestPayload schema is missing"]

    if lifecycle_payload.get("required") != ["session_id"]:
        failures.append("$defs.chatSessionLifecycleRequestPayload must require only session_id")

    properties = lifecycle_payload.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.chatSessionLifecycleRequestPayload properties must be an object")
    else:
        allowed_keys = {"session_id"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatSessionLifecycleRequestPayload properties must stay limited to session_id"
            )
        forbidden_keys = {
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
            "source_path",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatSessionLifecycleRequestPayload properties includes future backend/route/workspace/source metadata "
                f"{leaked_keys}"
            )
        if properties.get("session_id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatSessionLifecycleRequestPayload session_id must use nonBlankString")
    if lifecycle_payload.get("additionalProperties") is not False:
        failures.append("$defs.chatSessionLifecycleRequestPayload additionalProperties must be false")

    bulk_request = defs.get("chatSessionBulkLifecycleRequestPayload")
    if not isinstance(bulk_request, dict):
        failures.append("$defs.chatSessionBulkLifecycleRequestPayload schema is missing")
    else:
        if bulk_request.get("required") != ["scope"]:
            failures.append("$defs.chatSessionBulkLifecycleRequestPayload must require only scope")
        bulk_request_properties = bulk_request.get("properties")
        if not isinstance(bulk_request_properties, dict) or set(bulk_request_properties.keys()) != {"scope", "limit"}:
            failures.append("$defs.chatSessionBulkLifecycleRequestPayload must stay limited to scope and limit")
        else:
            if bulk_request_properties.get("scope") != {
                "type": "string",
                "enum": ["all_active", "all_archived"],
            }:
                failures.append("$defs.chatSessionBulkLifecycleRequestPayload scope must stay closed")
            if bulk_request_properties.get("limit") != {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "default": 200,
            }:
                failures.append("$defs.chatSessionBulkLifecycleRequestPayload limit must stay bounded 1...200")
        if bulk_request.get("additionalProperties") is not False:
            failures.append("$defs.chatSessionBulkLifecycleRequestPayload additionalProperties must be false")

    bulk_result = defs.get("chatSessionBulkLifecycleResultPayload")
    expected_bulk_result_required = [
        "scope",
        "status",
        "affected_count",
        "remaining_count",
        "completed_at",
    ]
    if not isinstance(bulk_result, dict):
        failures.append("$defs.chatSessionBulkLifecycleResultPayload schema is missing")
    else:
        if bulk_result.get("required") != expected_bulk_result_required:
            failures.append("$defs.chatSessionBulkLifecycleResultPayload must require the complete bounded result")
        bulk_result_properties = bulk_result.get("properties")
        if not isinstance(bulk_result_properties, dict) or set(bulk_result_properties.keys()) != set(expected_bulk_result_required):
            failures.append("$defs.chatSessionBulkLifecycleResultPayload properties must stay closed")
        else:
            if bulk_result_properties.get("affected_count") != {
                "type": "integer",
                "minimum": 0,
                "maximum": 200,
            }:
                failures.append("$defs.chatSessionBulkLifecycleResultPayload affected_count must stay bounded 0...200")
            if bulk_result_properties.get("remaining_count") != {"type": "integer", "minimum": 0}:
                failures.append("$defs.chatSessionBulkLifecycleResultPayload remaining_count must stay nonnegative")
            if bulk_result_properties.get("completed_at") != {"type": "string", "format": "date-time"}:
                failures.append("$defs.chatSessionBulkLifecycleResultPayload completed_at must stay date-time")
        if bulk_result.get("additionalProperties") is not False:
            failures.append("$defs.chatSessionBulkLifecycleResultPayload additionalProperties must be false")

    for payload_name, scope, status in (
        ("chatSessionArchivePayload", "all_active", "archived"),
        ("chatSessionDeletePayload", "all_archived", "deleted"),
    ):
        payload = defs.get(payload_name)
        options = payload.get("oneOf") if isinstance(payload, dict) else None
        if not isinstance(options, list):
            failures.append(f"$defs.{payload_name} must include single and bulk lifecycle shapes")
            continue
        has_bulk_request = any(
            isinstance(option, dict)
            and isinstance(option.get("allOf"), list)
            and any(
                isinstance(part, dict)
                and part.get("$ref") == "#/$defs/chatSessionBulkLifecycleRequestPayload"
                for part in option["allOf"]
            )
            and any(
                isinstance(part, dict)
                and part.get("properties", {}).get("scope", {}).get("const") == scope
                for part in option["allOf"]
            )
            for option in options
        )
        has_bulk_result = any(
            isinstance(option, dict)
            and isinstance(option.get("allOf"), list)
            and any(
                isinstance(part, dict)
                and part.get("$ref") == "#/$defs/chatSessionBulkLifecycleResultPayload"
                for part in option["allOf"]
            )
            and any(
                isinstance(part, dict)
                and part.get("properties", {}).get("scope", {}).get("const") == scope
                and part.get("properties", {}).get("status", {}).get("const") == status
                for part in option["allOf"]
            )
            for option in options
        )
        if not has_bulk_request:
            failures.append(f"$defs.{payload_name} must bind its runtime-authoritative bulk request scope")
        if not has_bulk_result:
            failures.append(f"$defs.{payload_name} must bind its runtime-authoritative bulk result scope/status")
    return failures


def check_chat_session_rename_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include chatSessionRenamePayload schema"]
    rename_payload = defs.get("chatSessionRenamePayload")
    if not isinstance(rename_payload, dict):
        return ["$defs.chatSessionRenamePayload schema is missing"]

    options = rename_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.chatSessionRenamePayload.oneOf must describe request and acknowledgement payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["session_id", "title"]
        ),
        None,
    )
    response_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["session_id", "title", "renamed_at"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.chatSessionRenamePayload must include a session_id/title request payload option"]
    if not isinstance(response_option, dict):
        failures.append("$defs.chatSessionRenamePayload must include a renamed_at acknowledgement payload option")

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.chatSessionRenamePayload request properties must be an object")
    else:
        allowed_keys = {"session_id", "title"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatSessionRenamePayload request properties must stay limited to session_id and title"
            )
        forbidden_keys = {
            "renamed_at",
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
            "source_path",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.chatSessionRenamePayload request properties includes runtime/backend/route/workspace/source metadata "
                f"{leaked_keys}"
            )
        if properties.get("session_id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatSessionRenamePayload request session_id must use nonBlankString")
        if properties.get("title", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.chatSessionRenamePayload request title must use nonBlankString")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.chatSessionRenamePayload request additionalProperties must be false")
    return failures


def check_memory_list_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include memoryListPayload schema"]
    memory_list_payload = defs.get("memoryListPayload")
    if not isinstance(memory_list_payload, dict):
        return ["$defs.memoryListPayload schema is missing"]

    options = memory_list_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.memoryListPayload.oneOf must describe request and response payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and isinstance(option.get("properties"), dict)
            and "entries" not in option.get("properties", {})
        ),
        None,
    )
    response_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["entries"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.memoryListPayload must include a query/embedding-hint request payload option"]
    if not isinstance(response_option, dict):
        failures.append("$defs.memoryListPayload must include an entries response payload option")

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.memoryListPayload request properties must be an object")
    else:
        allowed_keys = {"query", "embedding_model_id"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.memoryListPayload request properties must stay limited to query and embedding_model_id"
            )
        if properties.get("query", {}).get("$ref") != "#/$defs/nonEmptyString":
            failures.append("$defs.memoryListPayload request query must use nonEmptyString")
        if properties.get("embedding_model_id", {}).get("$ref") != "#/$defs/nonEmptyString":
            failures.append("$defs.memoryListPayload request embedding_model_id must use nonEmptyString")
        forbidden_keys = {
            "entries",
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
            "source_path",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.memoryListPayload request properties includes response/backend/route/workspace/source metadata "
                f"{leaked_keys}"
            )
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.memoryListPayload request additionalProperties must be false")
    return failures


def check_memory_duplicate_suggestions_payload_schema_contract(
    schema: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include memory duplicate suggestion schemas"]

    payload = defs.get("memoryDuplicateSuggestionsListPayload")
    group = defs.get("memoryDuplicateSuggestionGroup")
    if not isinstance(payload, dict):
        return ["$defs.memoryDuplicateSuggestionsListPayload schema is missing"]
    if not isinstance(group, dict):
        return ["$defs.memoryDuplicateSuggestionGroup schema is missing"]

    options = payload.get("oneOf")
    if not isinstance(options, list) or len(options) != 2:
        return [
            "$defs.memoryDuplicateSuggestionsListPayload.oneOf must describe only empty request and bounded response payloads"
        ]
    if {
        option.get("$ref")
        for option in options
        if isinstance(option, dict) and "$ref" in option
    } != {
        "#/$defs/emptyPayload"
    }:
        failures.append(
            "$defs.memoryDuplicateSuggestionsListPayload request must use emptyPayload"
        )
    response = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["groups", "scanned_count", "truncated"]
        ),
        None,
    )
    if not isinstance(response, dict):
        failures.append(
            "$defs.memoryDuplicateSuggestionsListPayload must require the complete bounded response"
        )
    else:
        properties = response.get("properties")
        expected_keys = {"groups", "scanned_count", "truncated"}
        if not isinstance(properties, dict) or set(properties) != expected_keys:
            failures.append(
                "$defs.memoryDuplicateSuggestionsListPayload response properties must stay closed"
            )
        else:
            if properties.get("groups") != {
                "type": "array",
                "items": {"$ref": "#/$defs/memoryDuplicateSuggestionGroup"},
                "maxItems": 100,
                "uniqueItems": True,
            }:
                failures.append(
                    "$defs.memoryDuplicateSuggestionsListPayload groups must stay unique and bounded to 100"
                )
            if properties.get("scanned_count") != {
                "type": "integer",
                "minimum": 0,
                "maximum": 200,
            }:
                failures.append(
                    "$defs.memoryDuplicateSuggestionsListPayload scanned_count must stay bounded 0...200"
                )
            if properties.get("truncated") != {"type": "boolean"}:
                failures.append(
                    "$defs.memoryDuplicateSuggestionsListPayload truncated must stay boolean"
                )
            forbidden = {
                "content",
                "content_hash",
                "embedding",
                "embedding_model_id",
                "model_id",
                "source",
                "source_revision",
                "audit_handle",
                "backend_url",
                "route_token",
            }
            leaked = sorted(set(properties) & forbidden)
            if leaked:
                failures.append(
                    "$defs.memoryDuplicateSuggestionsListPayload response leaks protected metadata "
                    f"{leaked}"
                )
        if response.get("additionalProperties") is not False:
            failures.append(
                "$defs.memoryDuplicateSuggestionsListPayload response additionalProperties must be false"
            )

    if group.get("required") != ["entry_ids"]:
        failures.append("$defs.memoryDuplicateSuggestionGroup must require only entry_ids")
    group_properties = group.get("properties")
    if not isinstance(group_properties, dict) or set(group_properties) != {"entry_ids"}:
        failures.append("$defs.memoryDuplicateSuggestionGroup properties must stay closed")
    else:
        entry_ids = group_properties.get("entry_ids")
        expected_entry_ids = {
            "type": "array",
            "items": {"$ref": "#/$defs/nonBlankString"},
            "minItems": 2,
            "maxItems": 200,
            "uniqueItems": True,
        }
        if entry_ids != expected_entry_ids:
            failures.append(
                "$defs.memoryDuplicateSuggestionGroup entry_ids must be unique nonblank IDs with 2...200 members"
            )
    if group.get("additionalProperties") is not False:
        failures.append(
            "$defs.memoryDuplicateSuggestionGroup additionalProperties must be false"
        )
    return failures


def check_memory_semantic_duplicate_suggestions_payload_schema_contract(
    schema: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include memory semantic duplicate suggestion schemas"]

    payload = defs.get("memorySemanticDuplicateSuggestionsListPayload")
    pair = defs.get("memorySemanticDuplicateSuggestionPair")
    if not isinstance(payload, dict):
        return ["$defs.memorySemanticDuplicateSuggestionsListPayload schema is missing"]
    if not isinstance(pair, dict):
        return ["$defs.memorySemanticDuplicateSuggestionPair schema is missing"]

    options = payload.get("oneOf")
    if not isinstance(options, list) or len(options) != 2:
        return [
            "$defs.memorySemanticDuplicateSuggestionsListPayload.oneOf must describe only request and response payloads"
        ]
    request = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required")
            == ["embedding_model_id", "minimum_similarity_basis_points"]
        ),
        None,
    )
    response = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required")
            == ["pairs", "scanned_count", "omitted_count", "truncated"]
        ),
        None,
    )
    if not isinstance(request, dict):
        failures.append(
            "$defs.memorySemanticDuplicateSuggestionsListPayload must require the complete request"
        )
    else:
        properties = request.get("properties")
        expected_keys = {"embedding_model_id", "minimum_similarity_basis_points"}
        if not isinstance(properties, dict) or set(properties) != expected_keys:
            failures.append(
                "$defs.memorySemanticDuplicateSuggestionsListPayload request properties must stay closed"
            )
        else:
            if properties.get("embedding_model_id") != {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "pattern": "\\S",
            }:
                failures.append(
                    "$defs.memorySemanticDuplicateSuggestionsListPayload embedding_model_id must be bounded nonblank text"
                )
            if properties.get("minimum_similarity_basis_points") != {
                "type": "integer",
                "minimum": 8000,
                "maximum": 10000,
                "x-aetherlink-wire-kind": "exact-json-integer-token",
            }:
                failures.append(
                    "$defs.memorySemanticDuplicateSuggestionsListPayload threshold must stay exact-wire integer 8000...10000"
                )
        if request.get("additionalProperties") is not False:
            failures.append(
                "$defs.memorySemanticDuplicateSuggestionsListPayload request additionalProperties must be false"
            )

    if not isinstance(response, dict):
        failures.append(
            "$defs.memorySemanticDuplicateSuggestionsListPayload must require the complete response"
        )
    else:
        properties = response.get("properties")
        expected_keys = {"pairs", "scanned_count", "omitted_count", "truncated"}
        if not isinstance(properties, dict) or set(properties) != expected_keys:
            failures.append(
                "$defs.memorySemanticDuplicateSuggestionsListPayload response properties must stay closed"
            )
        else:
            if properties.get("pairs") != {
                "type": "array",
                "items": {"$ref": "#/$defs/memorySemanticDuplicateSuggestionPair"},
                "maxItems": 100,
                "uniqueItems": True,
            }:
                failures.append(
                    "$defs.memorySemanticDuplicateSuggestionsListPayload pairs must stay unique and bounded to 100"
                )
            for key in ("scanned_count", "omitted_count"):
                if properties.get(key) != {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 200,
                }:
                    failures.append(
                        f"$defs.memorySemanticDuplicateSuggestionsListPayload {key} must stay bounded 0...200"
                    )
            if properties.get("truncated") != {"type": "boolean"}:
                failures.append(
                    "$defs.memorySemanticDuplicateSuggestionsListPayload truncated must stay boolean"
                )
            forbidden = {
                "content",
                "content_hash",
                "embedding",
                "embedding_model_id",
                "model_fingerprint",
                "source",
                "source_revision",
                "audit_handle",
                "backend_url",
                "route_token",
            }
            leaked = sorted(set(properties) & forbidden)
            if leaked:
                failures.append(
                    "$defs.memorySemanticDuplicateSuggestionsListPayload response leaks protected metadata "
                    f"{leaked}"
                )
        if response.get("additionalProperties") is not False:
            failures.append(
                "$defs.memorySemanticDuplicateSuggestionsListPayload response additionalProperties must be false"
            )

    if pair.get("required") != ["entry_ids", "similarity_basis_points"]:
        failures.append(
            "$defs.memorySemanticDuplicateSuggestionPair must require IDs and integer similarity"
        )
    pair_properties = pair.get("properties")
    if not isinstance(pair_properties, dict) or set(pair_properties) != {
        "entry_ids",
        "similarity_basis_points",
    }:
        failures.append("$defs.memorySemanticDuplicateSuggestionPair properties must stay closed")
    else:
        if pair_properties.get("entry_ids") != {
            "type": "array",
            "items": {"$ref": "#/$defs/nonBlankString"},
            "minItems": 2,
            "maxItems": 2,
            "uniqueItems": True,
        }:
            failures.append(
                "$defs.memorySemanticDuplicateSuggestionPair entry_ids must be exactly two unique nonblank IDs"
            )
        if pair_properties.get("similarity_basis_points") != {
            "type": "integer",
            "minimum": 0,
            "maximum": 10000,
        }:
            failures.append(
                "$defs.memorySemanticDuplicateSuggestionPair similarity must stay integer 0...10000"
            )
    if pair.get("additionalProperties") is not False:
        failures.append(
            "$defs.memorySemanticDuplicateSuggestionPair additionalProperties must be false"
        )
    return failures


def check_memory_semantic_duplicate_clusters_payload_schema_contract(
    schema: dict[str, object],
) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include memory semantic duplicate cluster schemas"]

    payload = defs.get("memorySemanticDuplicateClustersListPayload")
    cluster = defs.get("memorySemanticDuplicateCluster")
    if not isinstance(payload, dict):
        return ["$defs.memorySemanticDuplicateClustersListPayload schema is missing"]
    if not isinstance(cluster, dict):
        return ["$defs.memorySemanticDuplicateCluster schema is missing"]

    options = payload.get("oneOf")
    if not isinstance(options, list) or len(options) != 2:
        return [
            "$defs.memorySemanticDuplicateClustersListPayload.oneOf must describe only request and response payloads"
        ]
    request = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required")
            == ["embedding_model_id", "minimum_similarity_basis_points"]
        ),
        None,
    )
    response = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required")
            == ["clusters", "scanned_count", "omitted_count", "truncated"]
        ),
        None,
    )

    if not isinstance(request, dict):
        failures.append(
            "$defs.memorySemanticDuplicateClustersListPayload must require the complete request"
        )
    else:
        properties = request.get("properties")
        expected_keys = {"embedding_model_id", "minimum_similarity_basis_points"}
        if not isinstance(properties, dict) or set(properties) != expected_keys:
            failures.append(
                "$defs.memorySemanticDuplicateClustersListPayload request properties must stay closed"
            )
        else:
            if properties.get("embedding_model_id") != {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "pattern": "\\S",
            }:
                failures.append(
                    "$defs.memorySemanticDuplicateClustersListPayload embedding_model_id must be bounded nonblank text"
                )
            if properties.get("minimum_similarity_basis_points") != {
                "type": "integer",
                "minimum": 8000,
                "maximum": 10000,
                "x-aetherlink-wire-kind": "exact-json-integer-token",
            }:
                failures.append(
                    "$defs.memorySemanticDuplicateClustersListPayload threshold must stay exact-wire integer 8000...10000"
                )
        if request.get("additionalProperties") is not False:
            failures.append(
                "$defs.memorySemanticDuplicateClustersListPayload request additionalProperties must be false"
            )

    if not isinstance(response, dict):
        failures.append(
            "$defs.memorySemanticDuplicateClustersListPayload must require the complete response"
        )
    else:
        properties = response.get("properties")
        expected_keys = {"clusters", "scanned_count", "omitted_count", "truncated"}
        if not isinstance(properties, dict) or set(properties) != expected_keys:
            failures.append(
                "$defs.memorySemanticDuplicateClustersListPayload response properties must stay closed"
            )
        else:
            if properties.get("clusters") != {
                "type": "array",
                "items": {"$ref": "#/$defs/memorySemanticDuplicateCluster"},
                "maxItems": 100,
                "uniqueItems": True,
            }:
                failures.append(
                    "$defs.memorySemanticDuplicateClustersListPayload clusters must stay unique and bounded to 100"
                )
            for key in ("scanned_count", "omitted_count"):
                if properties.get(key) != {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 200,
                }:
                    failures.append(
                        f"$defs.memorySemanticDuplicateClustersListPayload {key} must stay bounded 0...200"
                    )
            if properties.get("truncated") != {"type": "boolean"}:
                failures.append(
                    "$defs.memorySemanticDuplicateClustersListPayload truncated must stay boolean"
                )
            forbidden = {
                "content",
                "content_hash",
                "embedding",
                "embedding_model_id",
                "model_fingerprint",
                "source",
                "source_revision",
                "audit_handle",
                "backend_url",
                "route_token",
            }
            leaked = sorted(set(properties) & forbidden)
            if leaked:
                failures.append(
                    "$defs.memorySemanticDuplicateClustersListPayload response leaks protected metadata "
                    f"{leaked}"
                )
        if response.get("additionalProperties") is not False:
            failures.append(
                "$defs.memorySemanticDuplicateClustersListPayload response additionalProperties must be false"
            )

    if cluster.get("required") != ["entry_ids", "minimum_similarity_basis_points"]:
        failures.append(
            "$defs.memorySemanticDuplicateCluster must require IDs and minimum integer similarity"
        )
    cluster_properties = cluster.get("properties")
    if not isinstance(cluster_properties, dict) or set(cluster_properties) != {
        "entry_ids",
        "minimum_similarity_basis_points",
    }:
        failures.append("$defs.memorySemanticDuplicateCluster properties must stay closed")
    else:
        if cluster_properties.get("entry_ids") != {
            "type": "array",
            "items": {"$ref": "#/$defs/nonBlankString"},
            "minItems": 2,
            "maxItems": 200,
            "uniqueItems": True,
        }:
            failures.append(
                "$defs.memorySemanticDuplicateCluster entry_ids must contain 2...200 unique nonblank IDs"
            )
        if cluster_properties.get("minimum_similarity_basis_points") != {
            "type": "integer",
            "minimum": 0,
            "maximum": 10000,
            "x-aetherlink-wire-kind": "exact-json-integer-token",
        }:
            failures.append(
                "$defs.memorySemanticDuplicateCluster minimum similarity must stay exact-wire integer 0...10000"
            )
    if cluster.get("additionalProperties") is not False:
        failures.append(
            "$defs.memorySemanticDuplicateCluster additionalProperties must be false"
        )
    return failures


def check_memory_upsert_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include memoryUpsertPayload schema"]
    memory_upsert_payload = defs.get("memoryUpsertPayload")
    if not isinstance(memory_upsert_payload, dict):
        return ["$defs.memoryUpsertPayload schema is missing"]

    options = memory_upsert_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.memoryUpsertPayload.oneOf must describe request and response payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["content"]
        ),
        None,
    )
    response_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["entry"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.memoryUpsertPayload must include a content request payload option"]
    if not isinstance(response_option, dict):
        failures.append("$defs.memoryUpsertPayload must include an entry response payload option")

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.memoryUpsertPayload request properties must be an object")
    else:
        allowed_keys = {"id", "content", "enabled"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append("$defs.memoryUpsertPayload request properties must stay limited to id, content, and enabled")
        forbidden_keys = {
            "entry",
            "source",
            "search",
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
            "source_path",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.memoryUpsertPayload request properties includes response/backend/route/workspace/source metadata "
                f"{leaked_keys}"
            )
        if properties.get("id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.memoryUpsertPayload request id must use nonBlankString")
        if properties.get("content", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.memoryUpsertPayload request content must use nonBlankString")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.memoryUpsertPayload request additionalProperties must be false")
    return failures


def check_memory_delete_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include memoryDeletePayload schema"]
    memory_delete_payload = defs.get("memoryDeletePayload")
    if not isinstance(memory_delete_payload, dict):
        return ["$defs.memoryDeletePayload schema is missing"]

    options = memory_delete_payload.get("oneOf")
    if not isinstance(options, list):
        return ["$defs.memoryDeletePayload.oneOf must describe request and acknowledgement payloads"]

    request_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["id"]
        ),
        None,
    )
    response_option = next(
        (
            option
            for option in options
            if isinstance(option, dict)
            and option.get("required") == ["id", "deleted_at"]
        ),
        None,
    )
    if not isinstance(request_option, dict):
        return ["$defs.memoryDeletePayload must include an id-only request payload option"]
    if not isinstance(response_option, dict):
        failures.append("$defs.memoryDeletePayload must include a deleted_at acknowledgement payload option")

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.memoryDeletePayload request properties must be an object")
    else:
        allowed_keys = {"id"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append("$defs.memoryDeletePayload request properties must stay limited to id")
        forbidden_keys = {
            "deleted_at",
            "backend_url",
            "backend_credentials",
            "provider_url",
            "route_token",
            "relay_secret",
            "requested_route_token",
            "workspace_id",
            "permission_grant",
            "source_path",
            "source_control_status",
        }
        leaked_keys = sorted(actual_keys & forbidden_keys)
        if leaked_keys:
            failures.append(
                "$defs.memoryDeletePayload request properties includes runtime/backend/route/workspace/source metadata "
                f"{leaked_keys}"
            )
        if properties.get("id", {}).get("$ref") != "#/$defs/nonBlankString":
            failures.append("$defs.memoryDeletePayload request id must use nonBlankString")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.memoryDeletePayload request additionalProperties must be false")
    return failures


def simple_schema_sample_failures(
    value: object,
    schema_fragment: object,
    defs: dict[str, object],
    *,
    path: str,
) -> list[str]:
    if schema_fragment is False:
        return [f"{path} is forbidden by schema"]
    if schema_fragment is True:
        return []
    if not isinstance(schema_fragment, dict):
        return [f"{path} schema must be an object"]

    ref = schema_fragment.get("$ref")
    if isinstance(ref, str):
        prefix = "#/$defs/"
        if not ref.startswith(prefix):
            return [f"{path} uses unsupported ref {ref}"]
        target = defs.get(ref.removeprefix(prefix))
        if target is None:
            return [f"{path} ref {ref} is missing"]
        return simple_schema_sample_failures(value, target, defs, path=path)

    failures: list[str] = []
    all_of = schema_fragment.get("allOf")
    if isinstance(all_of, list):
        for index, option in enumerate(all_of):
            failures.extend(
                simple_schema_sample_failures(
                    value,
                    option,
                    defs,
                    path=f"{path}.allOf[{index}]",
                )
            )

    one_of = schema_fragment.get("oneOf")
    if isinstance(one_of, list):
        option_failures = [
            simple_schema_sample_failures(value, option, defs, path=path)
            for option in one_of
        ]
        matching_options = sum(not option_failure for option_failure in option_failures)
        if matching_options != 1:
            failures.append(f"{path} must match exactly one oneOf option")
        return failures

    if "const" in schema_fragment and value != schema_fragment["const"]:
        failures.append(f"{path} must equal {schema_fragment['const']!r}")
    enum_values = schema_fragment.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        failures.append(f"{path} must be one of {enum_values!r}")

    value_type = schema_fragment.get("type")
    if value_type == "object" or "properties" in schema_fragment or "required" in schema_fragment:
        if not isinstance(value, dict):
            return failures + [f"{path} must be an object"]
        properties = schema_fragment.get("properties")
        required = schema_fragment.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            return failures + [f"{path} object schema must define properties and required"]
        for field in required:
            if isinstance(field, str) and field not in value:
                failures.append(f"{path} missing {field}")
        if schema_fragment.get("additionalProperties") is False:
            for field in sorted(set(value) - set(properties)):
                failures.append(f"{path} contains unknown field {field}")
        for field, field_value in value.items():
            if field in properties:
                failures.extend(
                    simple_schema_sample_failures(
                        field_value,
                        properties[field],
                        defs,
                        path=f"{path}.{field}",
                    )
                )
        return failures

    if value_type == "array" or any(
        key in schema_fragment for key in ("minItems", "maxItems", "prefixItems", "items")
    ):
        if not isinstance(value, list):
            return failures + [f"{path} must be an array"]
        minimum_items = schema_fragment.get("minItems")
        if isinstance(minimum_items, int) and len(value) < minimum_items:
            failures.append(f"{path} must contain at least {minimum_items} items")
        maximum_items = schema_fragment.get("maxItems")
        if isinstance(maximum_items, int) and len(value) > maximum_items:
            failures.append(f"{path} must contain at most {maximum_items} items")
        prefix_items = schema_fragment.get("prefixItems", [])
        if isinstance(prefix_items, list):
            for index, item_schema in enumerate(prefix_items[:len(value)]):
                failures.extend(
                    simple_schema_sample_failures(
                        value[index],
                        item_schema,
                        defs,
                        path=f"{path}[{index}]",
                    )
                )
        item_schema = schema_fragment.get("items")
        if item_schema is not None:
            start_index = len(prefix_items) if isinstance(prefix_items, list) else 0
            for index, item in enumerate(value[start_index:], start=start_index):
                failures.extend(
                    simple_schema_sample_failures(
                        item,
                        item_schema,
                        defs,
                        path=f"{path}[{index}]",
                    )
                )
        return failures

    if value_type == "boolean":
        if not isinstance(value, bool):
            failures.append(f"{path} must be a boolean")
        return failures

    if value_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return failures + [f"{path} must be an integer"]
        minimum = schema_fragment.get("minimum")
        if isinstance(minimum, int) and value < minimum:
            failures.append(f"{path} must be at least {minimum}")
        maximum = schema_fragment.get("maximum")
        if isinstance(maximum, int) and value > maximum:
            failures.append(f"{path} must be at most {maximum}")
        return failures

    if value_type == "string" or any(
        key in schema_fragment for key in ("minLength", "maxLength", "pattern")
    ):
        if not isinstance(value, str):
            return failures + [f"{path} must be a string"]
        minimum_length = schema_fragment.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            failures.append(f"{path} is shorter than {minimum_length}")
        maximum_length = schema_fragment.get("maxLength")
        if isinstance(maximum_length, int) and len(value) > maximum_length:
            failures.append(f"{path} is longer than {maximum_length}")
        pattern = schema_fragment.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            failures.append(f"{path} does not match {pattern}")
        if schema_fragment.get("format") == "date-time":
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value) is None:
                failures.append(f"{path} must be an RFC3339 date-time")
            else:
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    failures.append(f"{path} must be a valid RFC3339 date-time")
    return failures


def check_relay_allocation_payload_schema_contract(schema: dict[str, object]) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        return ["$defs must include relay allocation payload schemas"]

    challenge_schema = defs.get("relayAllocationChallengePayload")
    authorization_schema = defs.get("relayAllocationAuthorizationPayload")
    challenge_fields = {
        "proof_scheme",
        "protocol_version",
        "operation",
        "authorization_id",
        "current_relay_id",
        "next_relay_id",
        "route_token_hash",
        "runtime_key_fingerprint",
        "client_key_fingerprint",
        "current_ticket_generation",
        "next_ticket_generation",
        "current_relay_expires_at",
        "current_relay_nonce",
        "next_relay_expires_at",
        "next_relay_nonce",
        "challenge",
        "challenge_expires_at",
        "transport_binding",
    }
    authorization_fields = {
        "proof_scheme",
        "authorization_id",
        "challenge",
        "client_key_fingerprint",
        "transport_binding",
        "client_signature",
    }
    expected_challenge_properties = {
        "proof_scheme": {"$ref": "#/$defs/relayAllocationProofScheme"},
        "protocol_version": {"const": 2},
        "operation": {"$ref": "#/$defs/relayAllocationOperation"},
        "authorization_id": {"$ref": "#/$defs/boundedNonBlankString"},
        "current_relay_id": {"$ref": "#/$defs/runtimeKeyBoundRelayID"},
        "next_relay_id": {"$ref": "#/$defs/runtimeKeyBoundRelayID"},
        "route_token_hash": {"$ref": "#/$defs/sha256HexDigest"},
        "runtime_key_fingerprint": {"$ref": "#/$defs/sha256HexDigest"},
        "client_key_fingerprint": {"$ref": "#/$defs/sha256HexDigest"},
        "current_ticket_generation": {"type": "integer", "minimum": 1},
        "next_ticket_generation": {"type": "integer", "minimum": 1},
        "current_relay_expires_at": {"type": "integer", "minimum": 1},
        "current_relay_nonce": {"$ref": "#/$defs/opaqueRouteValue"},
        "next_relay_expires_at": {"type": "integer", "minimum": 1},
        "next_relay_nonce": {"$ref": "#/$defs/opaqueRouteValue"},
        "challenge": {"$ref": "#/$defs/sha256HexDigest"},
        "challenge_expires_at": {"type": "integer", "minimum": 1},
        "transport_binding": {"$ref": "#/$defs/transportBinding"},
    }
    expected_authorization_properties = {
        "proof_scheme": {"$ref": "#/$defs/relayAllocationProofScheme"},
        "authorization_id": {"$ref": "#/$defs/boundedNonBlankString"},
        "challenge": {"$ref": "#/$defs/sha256HexDigest"},
        "client_key_fingerprint": {"$ref": "#/$defs/sha256HexDigest"},
        "transport_binding": {"$ref": "#/$defs/transportBinding"},
        "client_signature": {"$ref": "#/$defs/canonicalBase64"},
    }

    for label, payload_schema, expected_fields, expected_properties in (
        (
            "relay.allocation.challenge",
            challenge_schema,
            challenge_fields,
            expected_challenge_properties,
        ),
        (
            "relay.allocation.authorization",
            authorization_schema,
            authorization_fields,
            expected_authorization_properties,
        ),
    ):
        if not isinstance(payload_schema, dict):
            failures.append(f"$defs {label} payload schema is missing")
            continue
        if payload_schema.get("type") != "object":
            failures.append(f"$defs {label} payload must be an object")
        if set(payload_schema.get("required", [])) != expected_fields:
            failures.append(f"$defs {label} payload must require exactly {sorted(expected_fields)}")
        if payload_schema.get("properties") != expected_properties:
            failures.append(f"$defs {label} payload properties must preserve the exact wire contract")
        if payload_schema.get("additionalProperties") is not False:
            failures.append(f"$defs {label} payload must reject additional properties")

    if defs.get("relayAllocationProofScheme") != {"const": "runtime-client-p256-v2"}:
        failures.append("relay allocation proof scheme must be runtime-client-p256-v2")
    if defs.get("relayAllocationOperation") != {"enum": ["claim", "renew"]}:
        failures.append("relay allocation operation must stay limited to claim and renew")
    if defs.get("runtimeKeyBoundRelayID") != {
        "type": "string",
        "minLength": 68,
        "maxLength": 68,
        "pattern": "^rt2-[0-9a-f]{64}$",
    }:
        failures.append("relay allocation relay_id must match rt2-[64 lowercase hex]")
    if defs.get("boundedNonBlankString") != {
        "type": "string",
        "minLength": 1,
        "maxLength": OPAQUE_ROUTE_VALUE_MAX_CHARS,
        "pattern": "\\S",
    }:
        failures.append("relay allocation authorization_id must be nonblank and bounded")
    if defs.get("canonicalBase64") != {
        "type": "string",
        "minLength": 1,
        "maxLength": OPAQUE_ROUTE_VALUE_MAX_CHARS,
        "pattern": "^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?(?![\\s\\S])",
    }:
        failures.append("relay allocation client_signature must use bounded canonical Base64 shape")

    if not isinstance(challenge_schema, dict) or not isinstance(authorization_schema, dict):
        return failures

    hex_a = "0123456789abcdef" * 4
    hex_b = "fedcba9876543210" * 4
    challenge_sample: dict[str, object] = {
        "proof_scheme": "runtime-client-p256-v2",
        "protocol_version": 2,
        "operation": "claim",
        "authorization_id": "authorization-1",
        "current_relay_id": f"rt2-{hex_a}",
        "next_relay_id": f"rt2-{hex_b}",
        "route_token_hash": hex_b,
        "runtime_key_fingerprint": hex_a,
        "client_key_fingerprint": hex_b,
        "current_ticket_generation": 1,
        "next_ticket_generation": 2,
        "current_relay_expires_at": 1,
        "current_relay_nonce": "current-nonce",
        "next_relay_expires_at": 9_223_372_036_854_775_807,
        "next_relay_nonce": "next-nonce",
        "challenge": hex_a,
        "challenge_expires_at": 1,
        "transport_binding": hex_b,
    }
    authorization_sample: dict[str, object] = {
        "proof_scheme": "runtime-client-p256-v2",
        "authorization_id": "authorization-1",
        "challenge": hex_a,
        "client_key_fingerprint": hex_b,
        "transport_binding": hex_a,
        "client_signature": "MEUCIQ==",
    }
    for label, sample, payload_schema in (
        ("claim challenge", challenge_sample, challenge_schema),
        ("renew challenge", {**challenge_sample, "operation": "renew"}, challenge_schema),
        ("authorization", authorization_sample, authorization_schema),
    ):
        sample_failures = simple_schema_sample_failures(
            sample,
            payload_schema,
            defs,
            path=label,
        )
        if sample_failures:
            failures.append(f"relay allocation valid {label} sample rejected: {sample_failures}")

    invalid_challenges: list[tuple[str, dict[str, object]]] = [
        ("missing field", {key: value for key, value in challenge_sample.items() if key != "authorization_id"}),
        ("unknown field", {**challenge_sample, "unknown": "metadata"}),
        ("route token secret", {**challenge_sample, "route_token": "secret"}),
        ("relay secret", {**challenge_sample, "relay_secret": "secret"}),
        ("wrong scheme", {**challenge_sample, "proof_scheme": "runtime-p256-v1"}),
        ("wrong version", {**challenge_sample, "protocol_version": 1}),
        ("wrong operation", {**challenge_sample, "operation": "create"}),
        ("blank authorization id", {**challenge_sample, "authorization_id": "   "}),
        ("oversized authorization id", {**challenge_sample, "authorization_id": "a" * 513}),
        ("malformed current relay id", {**challenge_sample, "current_relay_id": hex_a}),
        ("malformed next relay id", {**challenge_sample, "next_relay_id": hex_b}),
        ("malformed route token hash", {**challenge_sample, "route_token_hash": hex_a.upper()}),
        ("malformed runtime fingerprint", {**challenge_sample, "runtime_key_fingerprint": hex_a[:-1]}),
        ("malformed client fingerprint", {**challenge_sample, "client_key_fingerprint": hex_b.upper()}),
        ("malformed binding", {**challenge_sample, "transport_binding": hex_b[:-1]}),
        ("malformed challenge", {**challenge_sample, "challenge": hex_a.upper()}),
        ("newline challenge", {**challenge_sample, "challenge": f"{hex_a}\n"}),
        ("whitespace current nonce", {**challenge_sample, "current_relay_nonce": "current nonce"}),
        ("oversized next nonce", {**challenge_sample, "next_relay_nonce": "n" * 513}),
        ("noninteger generation", {**challenge_sample, "current_ticket_generation": 1.5}),
    ]
    for field in (
        "current_ticket_generation",
        "next_ticket_generation",
        "current_relay_expires_at",
        "next_relay_expires_at",
        "challenge_expires_at",
    ):
        invalid_challenges.append((f"nonpositive {field}", {**challenge_sample, field: 0}))

    invalid_authorizations: list[tuple[str, dict[str, object]]] = [
        ("missing field", {key: value for key, value in authorization_sample.items() if key != "client_signature"}),
        ("unknown field", {**authorization_sample, "unknown": "metadata"}),
        ("route token secret", {**authorization_sample, "route_token": "secret"}),
        ("relay secret", {**authorization_sample, "relay_secret": "secret"}),
        ("wrong scheme", {**authorization_sample, "proof_scheme": "runtime-p256-v1"}),
        ("blank authorization id", {**authorization_sample, "authorization_id": "\t"}),
        ("oversized authorization id", {**authorization_sample, "authorization_id": "a" * 513}),
        ("malformed challenge", {**authorization_sample, "challenge": hex_a[:-1]}),
        ("malformed client fingerprint", {**authorization_sample, "client_key_fingerprint": hex_b.upper()}),
        ("malformed binding", {**authorization_sample, "transport_binding": hex_a.upper()}),
        ("blank signature", {**authorization_sample, "client_signature": ""}),
        ("malformed signature", {**authorization_sample, "client_signature": "not-base64"}),
        ("newline signature", {**authorization_sample, "client_signature": "MEUCIQ==\n"}),
        ("oversized signature", {**authorization_sample, "client_signature": "A" * 516}),
    ]
    for payload_label, samples, payload_schema in (
        ("challenge", invalid_challenges, challenge_schema),
        ("authorization", invalid_authorizations, authorization_schema),
    ):
        for sample_label, sample in samples:
            if not simple_schema_sample_failures(
                sample,
                payload_schema,
                defs,
                path=f"invalid {payload_label} {sample_label}",
            ):
                failures.append(
                    f"relay allocation {payload_label} schema unexpectedly accepts {sample_label} sample"
                )

    route_refresh = defs.get("routeRefreshPayload", {})
    route_options = route_refresh.get("oneOf", []) if isinstance(route_refresh, dict) else []
    route_result = next(
        (
            option
            for option in route_options
            if isinstance(option, dict) and isinstance(option.get("properties"), dict)
        ),
        None,
    )
    if not isinstance(route_result, dict):
        failures.append("route.refresh relay result schema is missing")
    else:
        ticket_schema = route_result.get("properties", {}).get("ticket_generation")
        if ticket_schema != {"type": "integer", "minimum": 1}:
            failures.append("route.refresh ticket_generation must be an optional positive integer")
        if "ticket_generation" in route_result.get("required", []):
            failures.append("route.refresh ticket_generation must not be required yet")
        dependent_required = route_result.get("dependentRequired", {})
        expected_relay_dependencies = {
            "relay_host",
            "relay_port",
            "relay_id",
            "relay_secret",
            "relay_expires_at",
            "relay_nonce",
        }
        if set(dependent_required.get("ticket_generation", [])) != expected_relay_dependencies:
            failures.append("route.refresh ticket_generation must be limited to complete relay results")
        for field, dependencies in dependent_required.items():
            if field != "ticket_generation" and "ticket_generation" in dependencies:
                failures.append("route.refresh existing relay results must not require ticket_generation")
                break
        if simple_schema_sample_failures(1, ticket_schema, defs, path="ticket_generation"):
            failures.append("route.refresh ticket_generation must accept 1")
        if not simple_schema_sample_failures(0, ticket_schema, defs, path="ticket_generation"):
            failures.append("route.refresh ticket_generation must reject 0")

    return failures


def main() -> int:
    failures = check_json_contract_guard_regressions()

    try:
        schema = load_json_rejecting_duplicate_names(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, DuplicateJSONNameError) as error:
        print(f"{SCHEMA_PATH.relative_to(ROOT)}: invalid JSON: {error}", file=sys.stderr)
        return 1
    if not isinstance(schema, dict):
        print(f"{SCHEMA_PATH.relative_to(ROOT)}: root must be a JSON object", file=sys.stderr)
        return 1

    try:
        pairing_qr_schema = load_json_rejecting_duplicate_names(
            PAIRING_QR_SCHEMA_PATH.read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        print(f"{PAIRING_QR_SCHEMA_PATH.relative_to(ROOT)}: missing QR payload schema", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, DuplicateJSONNameError) as error:
        print(f"{PAIRING_QR_SCHEMA_PATH.relative_to(ROOT)}: invalid JSON: {error}", file=sys.stderr)
        return 1
    if not isinstance(pairing_qr_schema, dict):
        print(f"{PAIRING_QR_SCHEMA_PATH.relative_to(ROOT)}: root must be a JSON object", file=sys.stderr)
        return 1

    message_enum = (
        schema.get("properties", {})
        .get("type", {})
        .get("enum")
    )
    if not isinstance(message_enum, list) or not all(
        isinstance(message_type, str) for message_type in message_enum
    ):
        failures.append("properties.type.enum must be a list of message type strings")
    else:
        duplicates = sorted(
            {
                message_type
                for message_type in message_enum
                if message_enum.count(message_type) > 1
            }
        )
        if duplicates:
            failures.append(f"properties.type.enum has duplicate entries {duplicates}")

        failures.extend(check_protocol_schema_rejects_reserved_future_runtime_namespaces())

        reserved = reserved_future_message_types(message_enum)
        if reserved:
            failures.append(
                "properties.type.enum includes reserved future messages "
                f"{reserved}"
            )

        failures.extend(check_protocol_schema_rejects_future_memory_namespaces())
        unsupported_memory_types = future_memory_message_types(message_enum)
        if unsupported_memory_types:
            failures.append(
                "properties.type.enum includes future memory messages not documented "
                f"as active {unsupported_memory_types}"
            )

        failures.extend(check_protocol_schema_rejects_future_tool_namespaces())
        unsupported_tool_types = future_tool_message_types(message_enum)
        if unsupported_tool_types:
            failures.append(
                "properties.type.enum includes future tool messages not documented "
                f"as active v0.1 {unsupported_tool_types}"
            )

        failures.extend(check_protocol_schema_rejects_future_route_namespaces())
        unsupported_route_types = [
            message_type
            for message_type in message_enum
            if message_type.startswith("route.") and message_type not in ALLOWED_ROUTE_TYPES
        ]
        if unsupported_route_types:
            failures.append(
                "properties.type.enum includes future route messages not documented "
                f"as active {unsupported_route_types}"
            )

        failures.extend(check_pre_auth_payload_schema_contracts(schema))
        failures.extend(check_empty_request_payload_schema_contracts(schema))
        failures.extend(check_models_pull_payload_schema_contract(schema))
        failures.extend(check_chat_cancel_payload_schema_contract(schema))
        failures.extend(check_chat_sessions_list_payload_schema_contract(schema))
        failures.extend(check_chat_messages_list_payload_schema_contract(schema))
        failures.extend(check_chat_session_lifecycle_payload_schema_contract(schema))
        failures.extend(check_chat_session_rename_payload_schema_contract(schema))
        failures.extend(check_memory_list_payload_schema_contract(schema))
        failures.extend(check_memory_duplicate_suggestions_payload_schema_contract(schema))
        failures.extend(
            check_memory_semantic_duplicate_suggestions_payload_schema_contract(schema)
        )
        failures.extend(
            check_memory_semantic_duplicate_clusters_payload_schema_contract(schema)
        )
        failures.extend(check_memory_upsert_payload_schema_contract(schema))
        failures.extend(check_memory_delete_payload_schema_contract(schema))
        failures.extend(check_index_documents_list_payload_schema_contract(schema))
        failures.extend(check_retrieval_query_source_anchor_schema_contract(schema))
        failures.extend(check_source_anchor_resolve_payload_schema_contract(schema))
        failures.extend(check_trusted_source_payload_schema_contract(schema))
        failures.extend(check_chat_send_payload_schema_contract(schema))
        failures.extend(check_research_notebook_payload_schema_contract(schema))
        failures.extend(check_chat_title_request_payload_schema_contract(schema))
        failures.extend(check_chat_message_schema_contract(schema))
        failures.extend(check_chat_attachment_schema_contract(schema))
        failures.extend(check_relay_allocation_payload_schema_contract(schema))

        payload_contract_types = set()
        for rule in schema.get("allOf", []):
            if not isinstance(rule, dict):
                continue
            condition_type = (
                rule.get("if", {})
                .get("properties", {})
                .get("type", {})
                .get("const")
            )
            payload_schema = (
                rule.get("then", {})
                .get("properties", {})
                .get("payload")
            )
            if isinstance(condition_type, str) and isinstance(payload_schema, dict):
                payload_contract_types.add(condition_type)

        missing_payload_contracts = sorted(set(message_enum) - payload_contract_types)
        if missing_payload_contracts:
            failures.append(
                "active message types missing payload contracts "
                f"{missing_payload_contracts}"
            )

        unknown_payload_contracts = sorted(payload_contract_types - set(message_enum))
        if unknown_payload_contracts:
            failures.append(
                "payload contracts defined for non-active message types "
                f"{unknown_payload_contracts}"
            )
        failures.extend(check_platform_message_constants(set(message_enum)))

    required_envelope_fields = schema.get("required", [])
    if not isinstance(required_envelope_fields, list):
        failures.append("top-level required fields must be a list")
    else:
        missing_envelope_fields = [
            field
            for field in ("version", "type", "request_id", "timestamp", "payload")
            if field not in required_envelope_fields
        ]
        if missing_envelope_fields:
            failures.append(f"top-level required fields missing {missing_envelope_fields}")

    if schema.get("additionalProperties") is not False:
        failures.append("top-level additionalProperties must be false")

    type_schema = schema.get("properties", {}).get("type", {})
    if not isinstance(type_schema, dict):
        failures.append("properties.type must be an object schema")
    elif type_schema.get("type") != "string":
        failures.append("properties.type must require string values")

    version_schema = schema.get("properties", {}).get("version", {})
    if not isinstance(version_schema, dict):
        failures.append("properties.version must be an object schema")
    elif version_schema.get("const") != 1:
        failures.append("properties.version must require const 1")

    request_id_schema = schema.get("properties", {}).get("request_id", {})
    if not isinstance(request_id_schema, dict):
        failures.append("properties.request_id must be an object schema")
    else:
        if request_id_schema.get("$ref") != "#/$defs/nonBlankString":
            failures.append("properties.request_id must use nonBlankString")
        if request_id_schema.get("format") == "uuid":
            failures.append("properties.request_id must not require UUID format")

    timestamp_schema = schema.get("properties", {}).get("timestamp", {})
    if not isinstance(timestamp_schema, dict):
        failures.append("properties.timestamp must be an object schema")
    else:
        if timestamp_schema.get("type") != "string":
            failures.append("properties.timestamp must require string values")
        if timestamp_schema.get("format") != "date-time":
            failures.append("properties.timestamp must require date-time format")

    payload_schema = schema.get("properties", {}).get("payload", {})
    if not isinstance(payload_schema, dict):
        failures.append("properties.payload must be an object schema")
    elif payload_schema.get("type") != "object":
        failures.append("properties.payload must require object values")

    if failures:
        print("Protocol schema check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    failures.extend(check_chat_delta_schema(schema))
    failures.extend(check_chat_source_attribution_schema(schema))
    failures.extend(check_locale_payload_schemas(schema))
    failures.extend(check_runtime_health_model_residency_schema(schema))
    failures.extend(check_memory_summary_draft_schema(schema))
    failures.extend(check_route_refresh_route_material_schema(schema))
    if failures:
        print("Protocol schema check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Protocol schema OK: {SCHEMA_PATH.relative_to(ROOT)}")
    qr_failures = check_pairing_qr_schema(pairing_qr_schema)
    if qr_failures:
        print("Pairing QR schema check failed:", file=sys.stderr)
        for failure in qr_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Pairing QR schema OK: {PAIRING_QR_SCHEMA_PATH.relative_to(ROOT)}")
    return 0


def check_chat_delta_schema(schema: dict) -> list[str]:
    failures: list[str] = []
    chat_delta = schema.get("$defs", {}).get("chatDeltaPayload", {})
    properties = chat_delta.get("properties", {})
    for field in ["delta", "text", "reasoning_delta", "thinking_delta"]:
        if field not in properties:
            failures.append(f"chat.delta payload schema missing {field}")

    required_options = {
        tuple(option.get("required", []))
        for option in chat_delta.get("anyOf", [])
        if isinstance(option, dict)
    }
    for field in ["delta", "text", "reasoning_delta", "thinking_delta"]:
        if (field,) not in required_options:
            failures.append(f"chat.delta payload schema must allow {field}-only deltas")
    return failures


def check_chat_source_attribution_schema(schema: dict) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    if defs.get("assistantMessageID") != {
        "type": "string",
        "pattern": "^assistant_message_[0-9a-f]{32}$",
    }:
        failures.append("assistantMessageID must use the canonical 32-lowercase-hex shape")
    attribution = defs.get("chatSourceAttribution", {})
    if attribution.get("additionalProperties") is not False:
        failures.append("chatSourceAttribution additionalProperties must be false")
    required_attribution_fields = attribution.get("required")
    expected_fields = {"source_index", "document_name", "mime_type", "chunk_index"}
    if (
        not isinstance(required_attribution_fields, list)
        or len(required_attribution_fields) != len(expected_fields)
        or set(required_attribution_fields) != expected_fields
    ):
        failures.append("chatSourceAttribution must require only the safe ordered attribution fields")
    properties = attribution.get("properties", {})
    if not isinstance(properties, dict) or set(properties) != expected_fields:
        failures.append("chatSourceAttribution properties must stay limited to safe display metadata")
        properties = {}
    if properties.get("source_index") != {"type": "integer", "minimum": 1, "maximum": 8}:
        failures.append("chatSourceAttribution source_index must stay bounded 1...8")
    if schema_max_length(properties.get("document_name")) != 256:
        failures.append("chatSourceAttribution document_name must stay bounded to 256 characters")
    document_name = properties.get("document_name")
    if not isinstance(document_name, dict) or not any(
        isinstance(rule, dict) and rule.get("$ref") == "#/$defs/nonBlankString"
        for rule in document_name.get("allOf", [])
    ):
        failures.append("chatSourceAttribution document_name must use nonBlankString")
    if schema_pattern(document_name) != CHAT_SOURCE_DOCUMENT_NAME_PATTERN:
        failures.append("chatSourceAttribution document_name must reject control characters")
    mime_type = properties.get("mime_type")
    if schema_max_length(mime_type) != 128 or schema_pattern(mime_type) != INDEX_DOCUMENT_MIME_TYPE_PATTERN:
        failures.append("chatSourceAttribution mime_type must reuse the canonical bounded MIME shape")
    if properties.get("chunk_index") != {"type": "integer", "minimum": 0}:
        failures.append("chatSourceAttribution chunk_index must stay nonnegative")
    forbidden_fields = {
        "grant_id", "citation_id", "source_anchor_id", "source_revision", "approval_id",
        "document_id", "content_fingerprint", "text", "snippet", "source_path",
        "workspace_id", "project_id", "backend_url",
    }
    leaked_fields = sorted(set(properties) & forbidden_fields)
    if leaked_fields:
        failures.append(f"chatSourceAttribution exposes forbidden authority or source fields {leaked_fields}")

    expected_array = {"$ref": "#/$defs/chatSourceAttributions"}
    attribution_array = defs.get("chatSourceAttributions", {})
    if not isinstance(attribution_array, dict):
        failures.append("chatSourceAttributions must be a reusable array definition")
        attribution_array = {}
    if (
        attribution_array.get("type") != "array"
        or attribution_array.get("minItems") != 1
        or attribution_array.get("maxItems") != 8
    ):
        failures.append("chatSourceAttributions must stay bounded to 1...8 entries")
    array_options = attribution_array.get("oneOf", [])
    if not isinstance(array_options, list) or len(array_options) != 8:
        failures.append("chatSourceAttributions must define one contiguous-index shape per length")
    else:
        for length, option in enumerate(array_options, start=1):
            prefix_items = option.get("prefixItems", []) if isinstance(option, dict) else []
            if (
                not isinstance(option, dict)
                or option.get("minItems") != length
                or option.get("maxItems") != length
                or not isinstance(prefix_items, list)
                or len(prefix_items) != length
            ):
                failures.append(f"chatSourceAttributions length {length} shape must be exact")
                continue
            for source_index, item in enumerate(prefix_items, start=1):
                expected_item = {
                    "allOf": [
                        {"$ref": "#/$defs/chatSourceAttribution"},
                        {"properties": {"source_index": {"const": source_index}}},
                    ]
                }
                if item != expected_item:
                    failures.append(
                        f"chatSourceAttributions item {source_index} in length {length} must fix source_index"
                    )
    chat_done = defs.get("chatDonePayload", {})
    done_properties = chat_done.get("properties", {})
    if not isinstance(done_properties, dict) or done_properties.get("source_attributions") != expected_array:
        failures.append("chatDonePayload source_attributions must use the bounded safe attribution array")
    done_required = chat_done.get("required", [])
    if "source_attributions" in done_required or "assistant_message_id" in done_required:
        failures.append("chatDonePayload attribution fields must remain optional")
    if not any(
        isinstance(rule, dict)
        and rule.get("if") == {"required": ["source_attributions"]}
        and rule.get("then") == {
            "required": ["finish_reason"],
            "properties": {"finish_reason": {"const": "stop"}},
        }
        for rule in chat_done.get("allOf", [])
    ):
        failures.append("chatDonePayload attributions must require finish_reason stop")
    if not isinstance(done_properties, dict) or done_properties.get("assistant_message_id") != {
        "$ref": "#/$defs/assistantMessageID"
    }:
        failures.append("chatDonePayload assistant_message_id must use assistantMessageID")
    if not any(
        isinstance(rule, dict)
        and rule.get("if") == {"required": ["assistant_message_id"]}
        and rule.get("then") == {"required": ["source_attributions"]}
        for rule in chat_done.get("allOf", [])
    ):
        failures.append(
            "chatDonePayload assistant_message_id must require source_attributions"
        )

    stored_message = defs.get("chatStoredMessage", {})
    stored_properties = stored_message.get("properties", {})
    if not isinstance(stored_properties, dict) or stored_properties.get("source_attributions") != expected_array:
        failures.append("chatStoredMessage source_attributions must use the bounded safe attribution array")
    stored_required = stored_message.get("required", [])
    if "source_attributions" in stored_required or "assistant_message_id" in stored_required:
        failures.append("chatStoredMessage attribution fields must remain optional")
    if not any(
        isinstance(rule, dict)
        and rule.get("if") == {"required": ["source_attributions"]}
        and rule.get("then") == {"properties": {"role": {"const": "assistant"}}}
        for rule in stored_message.get("allOf", [])
    ):
        failures.append("chatStoredMessage attributions must be assistant-only")
    if not isinstance(stored_properties, dict) or stored_properties.get("assistant_message_id") != {
        "$ref": "#/$defs/assistantMessageID"
    }:
        failures.append("chatStoredMessage assistant_message_id must use assistantMessageID")
    if not any(
        isinstance(rule, dict)
        and rule.get("if") == {"required": ["assistant_message_id"]}
        and rule.get("then") == {
            "required": ["source_attributions"],
            "properties": {"role": {"const": "assistant"}},
        }
        for rule in stored_message.get("allOf", [])
    ):
        failures.append(
            "chatStoredMessage assistant_message_id must be limited to attribution-bearing assistant items"
        )

    attribution_sample = {
        "source_index": 1,
        "document_name": "source.txt",
        "mime_type": "text/plain",
        "chunk_index": 0,
    }
    legacy_samples = (
        ("legacy chat.done", {"finish_reason": "stop"}, chat_done),
        ("legacy chat history", {"role": "assistant", "content": "Answer"}, stored_message),
    )
    for label, sample, sample_schema in legacy_samples:
        sample_failures = simple_schema_sample_failures(sample, sample_schema, defs, path=label)
        if sample_failures:
            failures.append(f"{label} sample rejected: {sample_failures}")

    valid_attributions = [
        {**attribution_sample, "source_index": source_index}
        for source_index in range(1, 9)
    ]
    for length in range(1, 9):
        sample_failures = simple_schema_sample_failures(
            valid_attributions[:length],
            attribution_array,
            defs,
            path=f"valid source_attributions length {length}",
        )
        if sample_failures:
            failures.append(f"valid contiguous attribution sample length {length} rejected: {sample_failures}")
    unicode_boundary_attribution = {
        **attribution_sample,
        "document_name": "\U0001f4c4" * 256,
    }
    if simple_schema_sample_failures(
        [unicode_boundary_attribution],
        attribution_array,
        defs,
        path="valid 256-code-point source_attributions sample",
    ):
        failures.append("source attribution schema must accept a safe 256-code-point document_name")
    invalid_attribution_samples = (
        [],
        [{**attribution_sample, "source_index": 2}],
        [attribution_sample, {**attribution_sample, "source_index": 1}],
        [attribution_sample, {**attribution_sample, "source_index": 3}],
        valid_attributions + [{**attribution_sample, "source_index": 8}],
        [{**attribution_sample, "document_name": "\U0001f4c4" * 257}],
        [{**attribution_sample, "document_name": "folder/source.txt"}],
        [{**attribution_sample, "document_name": "folder\\source.txt"}],
        [{**attribution_sample, "document_name": "source\u0000name.txt"}],
        [{**attribution_sample, "document_name": "source\u0085name.txt"}],
        [{**attribution_sample, "document_name": "source\u009fname.txt"}],
    )
    for index, sample in enumerate(invalid_attribution_samples):
        if not simple_schema_sample_failures(
            sample,
            attribution_array,
            defs,
            path=f"invalid source_attributions sample {index}",
        ):
            failures.append(f"contiguous attribution schema unexpectedly accepts invalid sample {index}")

    try:
        android_models = ANDROID_PROTOCOL_MODELS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        failures.append("Android protocol models missing for source attribution capability check")
    else:
        expected_capability = (
            'const val CHAT_SOURCE_ATTRIBUTION_RESOLVE_CAPABILITY = '
            '"chat.source_attribution.resolve.v1"'
        )
        if expected_capability not in android_models:
            failures.append(
                "Android protocol models must declare chat.source_attribution.resolve.v1 capability"
            )
    return failures


def check_locale_payload_schemas(schema: dict) -> list[str]:
    failures: list[str] = []
    payload_defs = {
        "chat.send": "chatSendPayload",
        "chat.title.request": "chatTitleRequestPayload",
    }
    defs = schema.get("$defs", {})
    for message_type, definition_name in payload_defs.items():
        payload = defs.get(definition_name, {})
        locale = payload.get("properties", {}).get("locale")
        if locale != {"type": "string"}:
            failures.append(
                f"{message_type} payload schema must allow optional string locale"
            )
    return failures


def check_runtime_health_model_residency_schema(schema: dict) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    runtime_health = defs.get("runtimeHealthPayload", {})
    backend_health = defs.get("backendHealth", {})
    model_residency = defs.get("modelResidencyHealth", {})
    unload_failure = defs.get("modelResidencyUnloadFailure", {})
    runtime_options = runtime_health.get("oneOf", [])
    runtime_object = next(
        (
            option
            for option in runtime_options
            if isinstance(option, dict)
            and isinstance(option.get("properties"), dict)
            and "status" in option.get("properties", {})
        ),
        {},
    )
    runtime_properties = runtime_object.get("properties", {})
    backend_properties = backend_health.get("properties", {})
    if backend_health.get("required") != ["available"]:
        failures.append("backendHealth schema must require only available")
    if backend_properties.get("message", {}).get("type") != "string":
        failures.append("backendHealth message must stay optional string metadata")
    if backend_properties.get("code", {}).get("type") != "string":
        failures.append("backendHealth code must stay optional string metadata")
    if backend_properties.get("retryable", {}).get("type") != "boolean":
        failures.append("backendHealth retryable must stay optional boolean metadata")
    if backend_health.get("additionalProperties") is not False:
        failures.append("backendHealth must reject unspecified fields")
    if runtime_properties.get("status", {}).get("enum") != ["ok", "degraded", "unavailable"]:
        failures.append("runtime.health payload status must be limited to ok/degraded/unavailable")
    if runtime_properties.get("model_residency", {}).get("$ref") != "#/$defs/modelResidencyHealth":
        failures.append("runtime.health payload schema must allow optional model_residency snapshot")

    residency_properties = model_residency.get("properties", {})
    for field in ["supported", "in_flight_generations"]:
        if field not in model_residency.get("required", []):
            failures.append(f"modelResidencyHealth schema must require {field}")
    if residency_properties.get("active_provider", {}).get("enum") != ["ollama", "lm_studio"]:
        failures.append("modelResidencyHealth active_provider must be limited to runtime provider ids")
    if residency_properties.get("in_flight_generations", {}).get("minimum") != 0:
        failures.append("modelResidencyHealth in_flight_generations must be non-negative")
    if residency_properties.get("idle_unload_delay_seconds", {}).get("minimum") != 0:
        failures.append("modelResidencyHealth idle_unload_delay_seconds must be non-negative")
    if residency_properties.get("last_unload_failure", {}).get("$ref") != "#/$defs/modelResidencyUnloadFailure":
        failures.append("modelResidencyHealth must allow optional last_unload_failure details")
    if model_residency.get("additionalProperties") is not False:
        failures.append("modelResidencyHealth must reject unspecified fields")

    unload_properties = unload_failure.get("properties", {})
    for field in ["provider", "model_id", "reason"]:
        if field not in unload_failure.get("required", []):
            failures.append(f"modelResidencyUnloadFailure schema must require {field}")
    if unload_properties.get("provider", {}).get("enum") != ["ollama", "lm_studio"]:
        failures.append("modelResidencyUnloadFailure provider must be limited to runtime provider ids")
    if unload_properties.get("model_id", {}).get("$ref") != "#/$defs/nonEmptyString":
        failures.append("modelResidencyUnloadFailure model_id must use nonEmptyString")
    if unload_properties.get("reason", {}).get("enum") != ["model_switch", "idle_timeout", "manual"]:
        failures.append("modelResidencyUnloadFailure reason must be limited to known unload reasons")
    if "message" in unload_properties:
        failures.append("modelResidencyUnloadFailure must not expose raw provider error messages")
    if unload_failure.get("additionalProperties") is not False:
        failures.append("modelResidencyUnloadFailure must reject unspecified fields")
    return failures


def check_memory_summary_draft_schema(schema: dict) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    payload_refs = conditional_payload_refs(schema)

    expected_payload_refs = {
        "memory.summary.drafts.list": "#/$defs/memorySummaryDraftsListPayload",
        "memory.summary.draft.generate": "#/$defs/memorySummaryDraftGeneratePayload",
        "memory.summary.draft.approve": "#/$defs/memorySummaryDraftApprovePayload",
        "memory.summary.draft.dismiss": "#/$defs/memorySummaryDraftDismissPayload",
    }
    for message_type, expected_ref in expected_payload_refs.items():
        actual_ref = payload_refs.get(message_type)
        if actual_ref != expected_ref:
            failures.append(
                f"{message_type} must route payload schema to {expected_ref}, got {actual_ref!r}"
            )

    list_payload = defs.get("memorySummaryDraftsListPayload", {})
    list_request = find_one_of_branch(
        list_payload,
        lambda branch: "limit" in branch.get("properties", {}),
    )
    if list_request is None:
        failures.append("memorySummaryDraftsListPayload missing limit request branch")
    else:
        list_request_properties = list_request.get("properties", {})
        if not isinstance(list_request_properties, dict):
            failures.append("memorySummaryDraftsListPayload request properties must be an object")
        else:
            allowed_keys = {"limit"}
            actual_keys = set(list_request_properties.keys())
            if actual_keys != allowed_keys:
                failures.append("memorySummaryDraftsListPayload request properties must stay limited to limit")
            forbidden_keys = {
                "drafts",
                "backend_url",
                "backend_credentials",
                "provider_url",
                "route_token",
                "relay_secret",
                "requested_route_token",
                "workspace_id",
                "permission_grant",
                "source_path",
                "source_control_status",
            }
            leaked_keys = sorted(actual_keys & forbidden_keys)
            if leaked_keys:
                failures.append(
                    "memorySummaryDraftsListPayload request properties includes response/backend/route/workspace/source metadata "
                    f"{leaked_keys}"
                )
        require_additional_properties_false(
            failures,
            "memorySummaryDraftsListPayload request",
            list_request,
        )
        expect_schema_equal(
            failures,
            "memorySummaryDraftsListPayload request limit",
            list_request.get("properties", {}).get("limit"),
            {"type": "integer", "minimum": 0, "maximum": 50},
        )

    list_response = find_one_of_branch(
        list_payload,
        lambda branch: "drafts" in set(branch.get("required", [])),
    )
    if list_response is None:
        failures.append("memorySummaryDraftsListPayload missing drafts response branch")
    else:
        require_additional_properties_false(
            failures,
            "memorySummaryDraftsListPayload response",
            list_response,
        )
        expect_required_fields(
            failures,
            "memorySummaryDraftsListPayload response",
            list_response,
            {"drafts"},
        )
        expect_schema_equal(
            failures,
            "memorySummaryDraftsListPayload response drafts",
            list_response.get("properties", {}).get("drafts"),
            {
                "type": "array",
                "items": {"$ref": "#/$defs/memorySummaryDraft"},
            },
        )

    approve_payload = defs.get("memorySummaryDraftApprovePayload", {})
    approve_request = find_one_of_branch(
        approve_payload,
        lambda branch: (
            "draft_id" in set(branch.get("required", []))
            and "entry" not in branch.get("properties", {})
        ),
    )
    if approve_request is None:
        failures.append("memorySummaryDraftApprovePayload missing draft approval request branch")
    else:
        require_memory_summary_decision_request_fields(
            failures,
            "memorySummaryDraftApprovePayload request",
            approve_request,
            allow_content=True,
        )

    approve_response = find_one_of_branch(
        approve_payload,
        lambda branch: "entry" in branch.get("properties", {}),
    )
    if approve_response is None:
        failures.append("memorySummaryDraftApprovePayload missing approved response branch")
    else:
        require_additional_properties_false(
            failures,
            "memorySummaryDraftApprovePayload response",
            approve_response,
        )
        expect_required_fields(
            failures,
            "memorySummaryDraftApprovePayload response",
            approve_response,
            {"draft_id", "status", "entry"},
        )
        properties = approve_response.get("properties", {})
        expect_schema_equal(
            failures,
            "memorySummaryDraftApprovePayload response draft_id",
            properties.get("draft_id"),
            {"$ref": "#/$defs/nonBlankString"},
        )
        expect_schema_equal(
            failures,
            "memorySummaryDraftApprovePayload response status",
            properties.get("status"),
            {"const": "approved"},
        )
        expect_schema_equal(
            failures,
            "memorySummaryDraftApprovePayload response entry",
            properties.get("entry"),
            {"$ref": "#/$defs/memoryEntry"},
        )

    dismiss_payload = defs.get("memorySummaryDraftDismissPayload", {})
    dismiss_request = find_one_of_branch(
        dismiss_payload,
        lambda branch: (
            "draft_id" in set(branch.get("required", []))
            and "dismissed_at" not in branch.get("properties", {})
        ),
    )
    if dismiss_request is None:
        failures.append("memorySummaryDraftDismissPayload missing draft dismiss request branch")
    else:
        require_memory_summary_decision_request_fields(
            failures,
            "memorySummaryDraftDismissPayload request",
            dismiss_request,
            allow_content=False,
        )

    dismiss_response = find_one_of_branch(
        dismiss_payload,
        lambda branch: "dismissed_at" in branch.get("properties", {}),
    )
    if dismiss_response is None:
        failures.append("memorySummaryDraftDismissPayload missing dismissed response branch")
    else:
        require_additional_properties_false(
            failures,
            "memorySummaryDraftDismissPayload response",
            dismiss_response,
        )
        expect_required_fields(
            failures,
            "memorySummaryDraftDismissPayload response",
            dismiss_response,
            {"draft_id", "status", "dismissed_at"},
        )
        properties = dismiss_response.get("properties", {})
        expect_schema_equal(
            failures,
            "memorySummaryDraftDismissPayload response draft_id",
            properties.get("draft_id"),
            {"$ref": "#/$defs/nonBlankString"},
        )
        expect_schema_equal(
            failures,
            "memorySummaryDraftDismissPayload response status",
            properties.get("status"),
            {"const": "dismissed"},
        )
        expect_schema_equal(
            failures,
            "memorySummaryDraftDismissPayload response dismissed_at",
            properties.get("dismissed_at"),
            {"type": "string", "format": "date-time"},
        )

    memory_draft = defs.get("memorySummaryDraft", {})
    require_additional_properties_false(failures, "memorySummaryDraft", memory_draft)
    expect_required_fields(
        failures,
        "memorySummaryDraft",
        memory_draft,
        {
            "id",
            "session",
            "source_message_count",
            "source_range",
            "source_pointers",
            "summary_preview",
        },
    )
    draft_properties = memory_draft.get("properties", {})
    expect_schema_equal(
        failures,
        "memorySummaryDraft session",
        draft_properties.get("session"),
        {"$ref": "#/$defs/memorySummaryDraftSession"},
    )
    expect_schema_equal(
        failures,
        "memorySummaryDraft source_message_count",
        draft_properties.get("source_message_count"),
        {"type": "integer", "minimum": 1},
    )
    expect_schema_equal(
        failures,
        "memorySummaryDraft source_pointers",
        draft_properties.get("source_pointers"),
        {
            "type": "array",
            "items": {"$ref": "#/$defs/memorySummaryDraftSourcePointer"},
            "minItems": 1,
        },
    )

    source = defs.get("memoryEntrySource", {})
    require_additional_properties_false(failures, "memoryEntrySource", source)
    expect_required_fields(
        failures,
        "memoryEntrySource",
        source,
        {
            "kind",
            "draft_id",
            "summary_method",
            "session",
            "source_message_count",
            "source_range",
            "source_pointers",
        },
    )
    source_properties = source.get("properties", {})
    expect_schema_equal(
        failures,
        "memoryEntrySource kind",
        source_properties.get("kind"),
        {"const": "long_inactivity_summary_draft"},
    )
    expect_schema_equal(
        failures,
        "memoryEntrySource summary_method",
        source_properties.get("summary_method"),
        {"const": "deterministic_preview"},
    )
    expect_schema_equal(
        failures,
        "memoryEntrySource source_pointers",
        source_properties.get("source_pointers"),
        {
            "type": "array",
            "items": {"$ref": "#/$defs/memorySummaryDraftSourcePointer"},
            "minItems": 1,
        },
    )

    session = defs.get("memorySummaryDraftSession", {})
    require_additional_properties_false(failures, "memorySummaryDraftSession", session)
    expect_required_fields(
        failures,
        "memorySummaryDraftSession",
        session,
        {
            "session_id",
            "title",
            "model",
            "last_activity_at",
            "message_count",
            "inactive_seconds",
        },
    )
    session_properties = session.get("properties", {})
    expect_schema_equal(
        failures,
        "memorySummaryDraftSession last_activity_at",
        session_properties.get("last_activity_at"),
        {"type": "string", "format": "date-time"},
    )
    expect_schema_equal(
        failures,
        "memorySummaryDraftSession message_count",
        session_properties.get("message_count"),
        {"type": "integer", "minimum": 0},
    )
    expect_schema_equal(
        failures,
        "memorySummaryDraftSession inactive_seconds",
        session_properties.get("inactive_seconds"),
        {"type": "integer", "minimum": 0},
    )

    source_pointer = defs.get("memorySummaryDraftSourcePointer", {})
    require_additional_properties_false(
        failures,
        "memorySummaryDraftSourcePointer",
        source_pointer,
    )
    expect_required_fields(
        failures,
        "memorySummaryDraftSourcePointer",
        source_pointer,
        {"session_id", "message_index", "role", "excerpt"},
    )
    pointer_properties = source_pointer.get("properties", {})
    expect_schema_equal(
        failures,
        "memorySummaryDraftSourcePointer message_index",
        pointer_properties.get("message_index"),
        {"type": "integer", "minimum": 1},
    )
    expect_schema_equal(
        failures,
        "memorySummaryDraftSourcePointer role",
        pointer_properties.get("role"),
        {"enum": ["user", "assistant"]},
    )

    error_codes = (
        defs.get("errorPayload", {})
        .get("properties", {})
        .get("code", {})
        .get("enum", [])
    )
    expected_error_codes = [
        "unknown_message_type",
        "unexpected_message_direction",
        "invalid_payload",
        "not_connected",
        "pairing_required",
        "authentication_required",
        "authentication_failed",
        "backend_unavailable",
        "bad_backend_response",
        "no_models",
        "model_not_found",
        "model_not_installed",
        "generation_not_found",
        "generation_cancelled",
        "route_refresh_unavailable",
        "unsupported_operation",
        "unsupported_attachment",
        "unreadable_attachment",
        "chat_session_not_found",
        "chat_session_must_be_archived_before_delete",
        "chat_session_must_be_restored_before_send",
        "chat_store_unavailable",
        "chat_context_window_exceeded",
        "document_index_unavailable",
        "source_anchor_not_found",
        "citation_not_found",
        "chat_source_attribution_not_found",
        "trusted_source_review_not_found",
        "trusted_source_review_expired",
        "trusted_source_review_stale",
        "trusted_source_not_found",
        "research_notebook_store_unavailable",
        "memory_store_unavailable",
        "memory_summary_draft_unavailable",
        "memory_summary_draft_stale",
        "memory_summary_draft_generation_failed",
        "transport_error",
        "internal_error",
    ]
    if error_codes != expected_error_codes:
        failures.append("errorPayload code enum must match the canonical protocol error code list")
    for error_code in expected_error_codes:
        if error_code not in error_codes:
            failures.append(f"errorPayload code enum missing {error_code}")

    return failures


def conditional_payload_refs(schema: dict) -> dict[str, str]:
    refs: dict[str, str] = {}
    for rule in schema.get("allOf", []):
        if not isinstance(rule, dict):
            continue
        message_type = (
            rule.get("if", {})
            .get("properties", {})
            .get("type", {})
            .get("const")
        )
        payload_ref = (
            rule.get("then", {})
            .get("properties", {})
            .get("payload", {})
            .get("$ref")
        )
        if isinstance(message_type, str) and isinstance(payload_ref, str):
            refs[message_type] = payload_ref
    return refs


def find_one_of_branch(definition: object, predicate) -> dict | None:
    if not isinstance(definition, dict):
        return None
    for branch in definition.get("oneOf", []):
        if isinstance(branch, dict) and predicate(branch):
            return branch
    return None


def require_memory_summary_decision_request_fields(
    failures: list[str],
    label: str,
    schema: dict,
    *,
    allow_content: bool,
) -> None:
    require_additional_properties_false(failures, label, schema)
    expect_required_fields(failures, label, schema, {"draft_id"})
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        failures.append(f"{label} properties must be an object")
        return
    allowed_keys = {
        "draft_id",
        "expected_session_id",
        "expected_source_message_count",
    }
    if allow_content:
        allowed_keys.update({"content", "enabled"})
    actual_keys = set(properties.keys())
    if actual_keys != allowed_keys:
        failures.append(f"{label} properties must stay limited to {', '.join(sorted(allowed_keys))}")
    forbidden_keys = {
        "status",
        "entry",
        "dismissed_at",
        "source",
        "backend_url",
        "backend_credentials",
        "provider_url",
        "route_token",
        "relay_secret",
        "requested_route_token",
        "workspace_id",
        "permission_grant",
        "source_path",
        "source_control_status",
    }
    leaked_keys = sorted(actual_keys & forbidden_keys)
    if leaked_keys:
        failures.append(
            f"{label} properties includes response/backend/route/workspace/source metadata {leaked_keys}"
        )
    expect_schema_equal(
        failures,
        f"{label} draft_id",
        properties.get("draft_id"),
        {"$ref": "#/$defs/nonBlankString"},
    )
    expect_schema_equal(
        failures,
        f"{label} expected_session_id",
        properties.get("expected_session_id"),
        {"$ref": "#/$defs/nonBlankString"},
    )
    expect_schema_equal(
        failures,
        f"{label} expected_source_message_count",
        properties.get("expected_source_message_count"),
        {"type": "integer", "minimum": 1},
    )
    if allow_content:
        expect_schema_equal(
            failures,
            f"{label} content",
            properties.get("content"),
            {"$ref": "#/$defs/nonBlankString"},
        )
        expect_schema_equal(
            failures,
            f"{label} enabled",
            properties.get("enabled"),
            {"type": "boolean"},
        )


def require_additional_properties_false(
    failures: list[str],
    label: str,
    schema: object,
) -> None:
    if not isinstance(schema, dict):
        failures.append(f"{label} must be an object schema")
        return
    if schema.get("additionalProperties") is not False:
        failures.append(f"{label} must reject additional properties")


def expect_required_fields(
    failures: list[str],
    label: str,
    schema: object,
    expected_fields: set[str],
) -> None:
    if not isinstance(schema, dict):
        failures.append(f"{label} must be an object schema")
        return
    required = schema.get("required", [])
    if not isinstance(required, list):
        failures.append(f"{label} required must be a list")
        return
    missing = sorted(expected_fields - set(required))
    if missing:
        failures.append(f"{label} missing required fields {missing}")


def expect_schema_equal(
    failures: list[str],
    label: str,
    actual: object,
    expected: object,
) -> None:
    if not json_values_equal(actual, expected):
        failures.append(f"{label} schema must be {expected!r}, got {actual!r}")


def check_platform_message_constants(schema_message_types: set[str]) -> list[str]:
    failures: list[str] = []
    platform_sources = [
        (
            "Android MessageType",
            ANDROID_PROTOCOL_MODELS_PATH,
            r"object\s+MessageType\s*\{(?P<body>.*?)\n\}",
            r"const\s+val\s+\w+\s*=\s*\"([^\"]+)\"",
        ),
        (
            "Swift MessageType",
            SWIFT_PROTOCOL_ENVELOPE_PATH,
            r"enum\s+MessageType\s*\{(?P<body>.*?)\n\}",
            r"static\s+let\s+\w+\s*=\s*\"([^\"]+)\"",
        ),
    ]

    for label, path, block_pattern, constant_pattern in platform_sources:
        try:
            source = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            failures.append(f"{label} source missing at {path.relative_to(ROOT)}")
            continue

        block = re.search(block_pattern, source, flags=re.DOTALL)
        if block is None:
            failures.append(f"{label} declaration block not found")
            continue

        message_types = re.findall(constant_pattern, block.group("body"))
        if not message_types:
            failures.append(f"{label} has no message type constants")
            continue

        duplicates = sorted(
            {
                message_type
                for message_type in message_types
                if message_types.count(message_type) > 1
            }
        )
        if duplicates:
            failures.append(f"{label} has duplicate message constants {duplicates}")

        platform_message_types = set(message_types)
        missing = sorted(
            schema_message_types - SCHEMA_ONLY_MESSAGE_TYPES - platform_message_types
        )
        if missing:
            failures.append(f"{label} missing schema message constants {missing}")

        extra = sorted(platform_message_types - schema_message_types)
        if extra:
            failures.append(f"{label} has constants not present in schema {extra}")

    return failures


def check_pairing_qr_schema(schema: dict) -> list[str]:
    failures: list[str] = []
    schema_id = schema.get("$id")
    if schema_id != "https://aetherlink.dev/schema/pairing-qr.v1.json":
        failures.append("pairing QR schema must use the v1 AetherLink schema id")
    if schema.get("additionalProperties") is not False:
        failures.append("pairing QR schema must reject additional properties")

    properties = schema.get("properties", {})
    required_groups = pairing_qr_required_groups(schema)
    for canonical, aliases in PAIRING_QR_REQUIRED_FIELD_GROUPS.items():
        for field in aliases:
            if field not in properties:
                failures.append(f"pairing QR schema missing alias property {field}")
        if not any(group <= aliases for group in required_groups):
            failures.append(
                f"pairing QR schema must require one of {sorted(aliases)} for {canonical}"
            )

    for field in REQUIRED_RELAY_QR_FIELDS:
        if field not in properties:
            failures.append(f"pairing QR schema missing relay property {field}")
    for field in REMOTE_RELAY_QR_FIELDS:
        if field not in properties:
            failures.append(f"pairing QR schema missing remote relay alias property {field}")
    for field in ROUTE_RELAY_QR_FIELDS:
        if field not in properties:
            failures.append(f"pairing QR schema missing route relay alias property {field}")
    for field in RENDEZVOUS_RELAY_QR_FIELDS:
        if field not in properties:
            failures.append(f"pairing QR schema missing rendezvous relay alias property {field}")
    for field in COMPACT_RELAY_QR_FIELDS:
        if field not in properties:
            failures.append(f"pairing QR schema missing compact relay property {field}")
    for field in P2P_RENDEZVOUS_QR_FIELDS:
        if field not in properties:
            failures.append(f"pairing QR schema missing P2P rendezvous property {field}")
    for field in COMPACT_P2P_RENDEZVOUS_QR_FIELDS:
        if field not in properties:
            failures.append(f"pairing QR schema missing compact P2P rendezvous property {field}")

    for field in ["port", "runtime_port", "p", "relay_port", "remote_port", "route_port", "rendezvous_port", "rp"]:
        if properties.get(field, {}).get("$ref") != "#/$defs/portValue":
            failures.append(f"pairing QR schema {field} must use portValue")

    for field in ["relay_expires_at", "remote_expires_at", "route_expires_at", "rendezvous_expires_at", "rx", "p2p_expires_at", "px"]:
        if properties.get(field, {}).get("$ref") != "#/$defs/epochMillisValue":
            failures.append(f"pairing QR schema {field} must use epochMillisValue")

    for field in ["p2p_protocol_version", "pv"]:
        if properties.get(field, {}).get("$ref") != "#/$defs/p2pProtocolVersionValue":
            failures.append(f"pairing QR schema {field} must use p2pProtocolVersionValue")

    for scope_field in PAIRING_QR_REMOTE_RELAY_SCOPE_FIELDS:
        scope_enum = properties.get(scope_field, {}).get("enum", [])
        for expected_scope in ["remote", "private_overlay", "usb_reverse"]:
            if expected_scope not in scope_enum:
                failures.append(
                    f"pairing QR schema {scope_field} must allow {expected_scope} route scope"
                )

    if properties.get("service_type", {}).get("enum") != PAIRING_QR_ALLOWED_SERVICE_TYPES:
        failures.append(
            "pairing QR schema service_type must allow only AetherLink discovery service hints"
        )

    defs = schema.get("$defs", {})
    no_whitespace_def = defs.get("noWhitespaceString", {})
    if no_whitespace_def.get("type") != "string" or no_whitespace_def.get("minLength") != 1:
        failures.append("pairing QR schema noWhitespaceString must be a non-empty string")
    if no_whitespace_def.get("pattern") != "^\\S+$":
        failures.append("pairing QR schema noWhitespaceString must reject whitespace")
    port_value = defs.get("portValue", {})
    if port_value.get("anyOf") != [
        {"type": "integer", "minimum": 1, "maximum": 65535},
        {
            "type": "string",
            "pattern": "^([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$",
        },
    ]:
        failures.append(
            "pairing QR schema portValue must reject signed, zero-padded, or out-of-range port strings"
        )
    p2p_protocol_version = defs.get("p2pProtocolVersionValue", {})
    if p2p_protocol_version.get("anyOf") != [{"const": 1}, {"const": "1"}]:
        failures.append(
            'pairing QR schema p2pProtocolVersionValue must allow only exact 1 or "1"'
        )
    epoch_millis_value = defs.get("epochMillisValue", {})
    if epoch_millis_value.get("anyOf") != [
        {"type": "integer", "minimum": 1},
        {"type": "string", "pattern": "^[1-9][0-9]*$"},
    ]:
        failures.append(
            "pairing QR schema epochMillisValue must reject signed or zero-padded expiration strings"
        )
    failures.extend(check_opaque_route_material_defs(defs, label="pairing QR schema"))
    for field in PAIRING_QR_NO_WHITESPACE_FIELDS:
        if not pairing_qr_schema_disallows_whitespace(properties.get(field, {})):
            failures.append(f"pairing QR schema {field} must reject whitespace")
    for field in PAIRING_QR_OPAQUE_VALUE_FIELDS:
        if properties.get(field, {}).get("$ref") != "#/$defs/opaqueRouteValue":
            failures.append(
                f"pairing QR schema {field} must use opaqueRouteValue with "
                f"maxLength {OPAQUE_ROUTE_VALUE_MAX_CHARS}"
            )
    for field in PAIRING_QR_OPAQUE_SECRET_FIELDS:
        if properties.get(field, {}).get("$ref") != "#/$defs/opaqueRouteSecret":
            failures.append(
                f"pairing QR schema {field} must use opaqueRouteSecret with "
                f"maxLength {OPAQUE_ROUTE_VALUE_MAX_CHARS}"
            )
    for field in PAIRING_QR_OPAQUE_BODY_FIELDS:
        if properties.get(field, {}).get("$ref") != "#/$defs/opaqueRouteBody":
            failures.append(
                f"pairing QR schema {field} must use opaqueRouteBody with "
                f"maxLength {OPAQUE_ROUTE_BODY_MAX_CHARS}"
            )

    dependent_required = schema.get("dependentRequired", {})
    for field in REQUIRED_RELAY_QR_FIELDS:
        dependencies = set(dependent_required.get(field, []))
        missing = sorted((REQUIRED_RELAY_QR_FIELDS - {field}) - dependencies)
        if missing:
            failures.append(
                f"pairing QR schema must require {missing} when {field} is present"
            )
    for field in COMPACT_RELAY_QR_FIELDS:
        dependencies = set(dependent_required.get(field, []))
        missing = sorted((COMPACT_RELAY_QR_FIELDS - {field}) - dependencies)
        if missing:
            failures.append(
                f"pairing QR schema must require compact {missing} when {field} is present"
            )
    for field in P2P_RENDEZVOUS_QR_FIELDS:
        dependencies = set(dependent_required.get(field, []))
        missing = sorted((P2P_RENDEZVOUS_QR_FIELDS - {field}) - dependencies)
        if missing:
            failures.append(
                f"pairing QR schema must require P2P rendezvous {missing} when {field} is present"
            )
    for field in COMPACT_P2P_RENDEZVOUS_QR_FIELDS:
        dependencies = set(dependent_required.get(field, []))
        missing = sorted((COMPACT_P2P_RENDEZVOUS_QR_FIELDS - {field}) - dependencies)
        if missing:
            failures.append(
                f"pairing QR schema must require compact P2P rendezvous {missing} when {field} is present"
            )
    for label, fields in [
        ("remote relay alias", REMOTE_RELAY_QR_FIELDS),
        ("route relay alias", ROUTE_RELAY_QR_FIELDS),
        ("rendezvous relay alias", RENDEZVOUS_RELAY_QR_FIELDS),
    ]:
        for field in fields:
            dependencies = set(dependent_required.get(field, []))
            missing = sorted((fields - {field}) - dependencies)
            if missing:
                failures.append(
                    f"pairing QR schema must require {label} {missing} when {field} is present"
                )

    failures.extend(check_pairing_qr_relay_alias_family_isolation(schema))
    failures.extend(check_pairing_qr_p2p_alias_family_isolation(schema))
    failures.extend(check_pairing_qr_semantic_alias_exclusivity(schema))

    for field in PRIVATE_RELAY_HOST_FIELDS:
        if properties.get(field, {}).get("$ref") != "#/$defs/pairingRelayHost":
            failures.append(f"pairing QR schema {field} must use pairingRelayHost")

    pairing_host = schema.get("$defs", {}).get("pairingRelayHost", {})
    if not pairing_qr_relay_host_schema_allows_remote_or_usb_loopback(pairing_host):
        failures.append(
            "pairing QR schema pairingRelayHost must allow normal eligible relay hosts "
            "or explicit debug USB reverse loopback relay hosts"
        )

    eligible_host = schema.get("$defs", {}).get("eligibleRelayHost", {})
    forbidden_enums: set[str] = set()
    forbidden_patterns: list[str] = []
    for rule in eligible_host.get("allOf", []):
        not_rule = rule.get("not", {}) if isinstance(rule, dict) else {}
        enum_values = not_rule.get("enum", [])
        if isinstance(enum_values, list):
            forbidden_enums.update(value for value in enum_values if isinstance(value, str))
        pattern = not_rule.get("pattern")
        if isinstance(pattern, str):
            forbidden_patterns.append(pattern)

    for forbidden in ["localhost", "127.0.0.1", "::1", "0.0.0.0"]:
        if forbidden not in forbidden_enums:
            failures.append(f"eligibleRelayHost must reject {forbidden}")

    loopback_host = schema.get("$defs", {}).get("loopbackRelayHost", {})
    if not route_refresh_loopback_host_schema_is_canonical(loopback_host):
        failures.append(
            "pairing QR schema loopbackRelayHost must match localhost, IPv4 loopback, "
            "and IPv6 loopback relay hosts"
        )

    joined_patterns = "\n".join(forbidden_patterns)
    for forbidden in ["local$", "169\\.254", "fe80"]:
        if forbidden not in joined_patterns:
            failures.append(f"eligibleRelayHost must reject {forbidden}")

    failures.extend(check_usb_reverse_qr_scope_contract(schema))
    failures.extend(check_private_overlay_qr_scope_contract(schema))

    failures.extend(check_compact_relay_fixture(
        fixture_path=COMPACT_RELAY_QR_FIXTURE_PATH,
        label="shared compact relay QR fixture",
        expected_host="relay.example.test",
        expected_scope="remote",
    ))
    failures.extend(check_compact_relay_fixture(
        fixture_path=COMPACT_PRIVATE_OVERLAY_RELAY_QR_FIXTURE_PATH,
        label="shared compact private overlay relay QR fixture",
        expected_host="100.64.1.10",
        expected_scope="private_overlay",
    ))
    failures.extend(check_compact_p2p_rendezvous_fixture(
        fixture_path=COMPACT_P2P_RENDEZVOUS_QR_FIXTURE_PATH,
        label="shared compact P2P rendezvous QR fixture",
    ))
    return failures


def check_pairing_qr_relay_alias_family_isolation(schema: dict) -> list[str]:
    failures: list[str] = []
    family_items = list(RELAY_QR_ALIAS_FAMILIES.items())

    for family_label, payload_keys in family_items:
        if pairing_qr_has_mixed_alias_family_rejection(schema, set(payload_keys)):
            failures.append(
                f"pairing QR schema must allow complete {family_label} relay alias family fields"
            )

    for index, (left_label, left_fields) in enumerate(family_items):
        for right_label, right_fields in family_items[index + 1:]:
            if not pairing_qr_has_mixed_alias_family_rejection(
                schema,
                set(left_fields) | set(right_fields),
            ):
                failures.append(
                    "pairing QR schema must reject mixed relay alias families "
                    f"between {left_label} and {right_label}"
                )
    return failures


def check_pairing_qr_p2p_alias_family_isolation(schema: dict) -> list[str]:
    failures: list[str] = []
    canonical_payload = set(P2P_RENDEZVOUS_QR_FIELDS)
    compact_payload = set(COMPACT_P2P_RENDEZVOUS_QR_FIELDS)
    mixed_payloads = [
        {"p2p_class", "prid", "peb", "px", "pn", "pv"},
        {
            "pc",
            "p2p_record_id",
            "p2p_encrypted_body",
            "p2p_expires_at",
            "p2p_anti_replay_nonce",
            "p2p_protocol_version",
        },
        canonical_payload | compact_payload,
    ]

    if pairing_qr_has_mixed_alias_family_rejection(schema, canonical_payload):
        failures.append("pairing QR schema must allow complete canonical P2P rendezvous fields")
    if pairing_qr_has_mixed_alias_family_rejection(schema, compact_payload):
        failures.append("pairing QR schema must allow complete compact P2P rendezvous fields")
    for payload_keys in mixed_payloads:
        if not pairing_qr_has_mixed_alias_family_rejection(schema, payload_keys):
            failures.append(
                "pairing QR schema must reject mixed canonical and compact P2P rendezvous aliases"
            )
            break
    return failures


def check_pairing_qr_scope_alias_exclusivity(schema: dict) -> list[str]:
    failures: list[str] = []
    scope_fields = list(PAIRING_QR_REMOTE_RELAY_SCOPE_FIELDS)
    for index, left_field in enumerate(scope_fields):
        for right_field in scope_fields[index + 1:]:
            if not pairing_qr_rejects_required_field_pair(schema, left_field, right_field):
                failures.append(
                    "pairing QR schema must reject mixed relay-scope aliases "
                    f"between {left_field} and {right_field}"
                )
    return failures


def check_pairing_qr_semantic_alias_exclusivity(schema: dict) -> list[str]:
    failures: list[str] = []
    for canonical, fields in PAIRING_QR_SEMANTIC_ALIAS_GROUPS.items():
        ordered_fields = sorted(fields)
        for index, left_field in enumerate(ordered_fields):
            for right_field in ordered_fields[index + 1:]:
                if not pairing_qr_rejects_required_field_pair(schema, left_field, right_field):
                    failures.append(
                        "pairing QR schema must reject mixed semantic aliases "
                        f"for {canonical} between {left_field} and {right_field}"
                    )
    return failures


def pairing_qr_rejects_required_field_pair(schema: dict, left_field: str, right_field: str) -> bool:
    if pairing_qr_dependent_schema_rejects_field_pair(schema, left_field, right_field):
        return True
    for rule in schema.get("allOf", []):
        if not isinstance(rule, dict):
            continue
        not_rule = rule.get("not", {})
        if not isinstance(not_rule, dict):
            continue
        if required_field_pair_all_of_matches(not_rule.get("allOf", []), left_field, right_field):
            return True
        any_of = not_rule.get("anyOf", [])
        if isinstance(any_of, list):
            for option in any_of:
                if not isinstance(option, dict):
                    continue
                if required_field_pair_all_of_matches(option.get("allOf", []), left_field, right_field):
                    return True
    return False


def pairing_qr_dependent_schema_rejects_field_pair(
    schema: dict,
    left_field: str,
    right_field: str,
) -> bool:
    dependent_schemas = schema.get("dependentSchemas", {})
    if not isinstance(dependent_schemas, dict):
        return False
    return (
        dependent_schema_rejects_required_field(dependent_schemas, left_field, right_field)
        or dependent_schema_rejects_required_field(dependent_schemas, right_field, left_field)
    )


def dependent_schema_rejects_required_field(
    dependent_schemas: dict,
    present_field: str,
    rejected_field: str,
) -> bool:
    rule = dependent_schemas.get(present_field)
    if not isinstance(rule, dict):
        return False
    return schema_not_rejects_required_field(rule.get("not"), rejected_field)


def schema_not_rejects_required_field(not_rule: object, rejected_field: str) -> bool:
    if not isinstance(not_rule, dict):
        return False
    if single_required_field_matches(not_rule, rejected_field):
        return True
    any_of = not_rule.get("anyOf", [])
    if isinstance(any_of, list):
        return any(
            isinstance(option, dict) and single_required_field_matches(option, rejected_field)
            for option in any_of
        )
    return False


def single_required_field_matches(condition: dict, expected_field: str) -> bool:
    required = condition.get("required", [])
    return isinstance(required, list) and required == [expected_field]


def required_field_pair_all_of_matches(all_of: object, left_field: str, right_field: str) -> bool:
    if not isinstance(all_of, list) or len(all_of) != 2:
        return False
    required_fields = []
    for condition in all_of:
        if not isinstance(condition, dict):
            return False
        required = condition.get("required", [])
        if not isinstance(required, list) or len(required) != 1:
            return False
        required_fields.append(required[0])
    return set(required_fields) == {left_field, right_field}


def pairing_qr_has_mixed_alias_family_rejection(schema: dict, payload_keys: set[str]) -> bool:
    for rule in schema.get("allOf", []):
        if not isinstance(rule, dict):
            continue
        not_rule = rule.get("not", {})
        if not isinstance(not_rule, dict):
            continue
        if alias_family_all_of_matches(not_rule.get("allOf", []), payload_keys):
            return True
        any_of = not_rule.get("anyOf", [])
        if isinstance(any_of, list):
            for option in any_of:
                if not isinstance(option, dict):
                    continue
                if alias_family_all_of_matches(option.get("allOf", []), payload_keys):
                    return True
    return False


def alias_family_all_of_matches(all_of: object, payload_keys: set[str]) -> bool:
    return (
        isinstance(all_of, list)
        and len(all_of) == 2
        and alias_family_condition_matches(all_of[0], payload_keys)
        and alias_family_condition_matches(all_of[1], payload_keys)
    )


def alias_family_condition_matches(condition: object, payload_keys: set[str]) -> bool:
    if not isinstance(condition, dict):
        return False
    any_of = condition.get("anyOf", [])
    if not isinstance(any_of, list):
        return False
    for option in any_of:
        if not isinstance(option, dict):
            continue
        required = option.get("required", [])
        if isinstance(required, list) and set(required) <= payload_keys:
            return True
    return False


def pairing_qr_schema_disallows_whitespace(field_schema: object) -> bool:
    if not isinstance(field_schema, dict):
        return False
    if field_schema.get("$ref") in (
        "#/$defs/noWhitespaceString",
        "#/$defs/opaqueRouteValue",
        "#/$defs/opaqueRouteBody",
    ):
        return True
    return field_schema.get("pattern") == "^\\S+$" and field_schema.get("minLength") == 1


def check_opaque_route_material_defs(defs: dict, *, label: str) -> list[str]:
    failures: list[str] = []
    opaque_value = defs.get("opaqueRouteValue", {})
    if (
        opaque_value.get("type") != "string"
        or opaque_value.get("minLength") != 1
        or opaque_value.get("maxLength") != OPAQUE_ROUTE_VALUE_MAX_CHARS
        or opaque_value.get("pattern") != "^\\S+$"
    ):
        failures.append(
            f"{label} opaqueRouteValue must be a non-empty, whitespace-free string "
            f"capped at {OPAQUE_ROUTE_VALUE_MAX_CHARS} characters"
        )

    opaque_secret = defs.get("opaqueRouteSecret", {})
    if (
        opaque_secret.get("type") != "string"
        or opaque_secret.get("minLength") != 1
        or opaque_secret.get("maxLength") != OPAQUE_ROUTE_VALUE_MAX_CHARS
        or opaque_secret.get("pattern") != "^\\S+$"
    ):
        failures.append(
            f"{label} opaqueRouteSecret must be a non-empty, whitespace-free string "
            f"capped at {OPAQUE_ROUTE_VALUE_MAX_CHARS} characters"
        )

    opaque_body = defs.get("opaqueRouteBody", {})
    if (
        opaque_body.get("type") != "string"
        or opaque_body.get("minLength") != 1
        or opaque_body.get("maxLength") != OPAQUE_ROUTE_BODY_MAX_CHARS
        or opaque_body.get("pattern") != "^\\S+$"
    ):
        failures.append(
            f"{label} opaqueRouteBody must be a non-empty, whitespace-free string "
            f"capped at {OPAQUE_ROUTE_BODY_MAX_CHARS} characters"
        )
    return failures


def check_route_refresh_route_material_schema(schema: dict) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    failures.extend(check_opaque_route_material_defs(defs, label="protocol route.refresh schema"))

    private_host = defs.get("privateOverlayRelayHost", {})
    host_patterns = "\n".join(
        option.get("pattern", "")
        for option in private_host.get("anyOf", [])
        if isinstance(option, dict)
    )
    for expected_pattern in PRIVATE_OVERLAY_RELAY_HOST_PATTERNS:
        if expected_pattern not in host_patterns:
            failures.append(
                "protocol route.refresh privateOverlayRelayHost must match private/CGNAT/ULA relay hosts; "
                f"missing {expected_pattern}"
            )

    loopback_host = defs.get("loopbackRelayHost", {})
    if not route_refresh_loopback_host_schema_is_canonical(loopback_host):
        failures.append(
            "protocol route.refresh loopbackRelayHost must match localhost, IPv4 loopback, "
            "and IPv6 loopback relay hosts"
        )

    relay_host_schema = defs.get("routeRefreshRelayHost", {})
    if not route_refresh_relay_host_schema_is_canonical(relay_host_schema):
        failures.append(
            "protocol route.refresh routeRefreshRelayHost must require a non-empty, "
            "whitespace-free host and reject URL, path, query, fragment, user-info, "
            "mDNS-local, unspecified, link-local, multicast, and broadcast markers"
        )

    route_refresh = defs.get("routeRefreshPayload", {})
    route_refresh_options = route_refresh.get("oneOf", [])
    material_schema = None
    for option in route_refresh_options:
        if isinstance(option, dict) and "properties" in option:
            material_schema = option
            break
    if material_schema is None:
        return ["route.refresh schema must include a route-material payload option"]

    private_overlay_rules = material_schema.get("allOf", [])
    if not any(is_route_refresh_loopback_usb_reverse_scope_rule(rule) for rule in private_overlay_rules):
        failures.append(
            "route.refresh schema must require relay_scope=usb_reverse when relay_host "
            "uses a loopback relay literal"
        )
    if not any(is_route_refresh_private_overlay_scope_rule(rule) for rule in private_overlay_rules):
        failures.append(
            "route.refresh schema must require relay_scope=private_overlay when relay_host "
            "uses a private, CGNAT, or ULA relay literal"
        )

    properties = material_schema.get("properties", {})
    if properties.get("relay_host", {}).get("$ref") != "#/$defs/routeRefreshRelayHost":
        failures.append("route.refresh schema relay_host must use routeRefreshRelayHost")
    for field in ROUTE_REFRESH_OPAQUE_VALUE_FIELDS:
        if properties.get(field, {}).get("$ref") != "#/$defs/opaqueRouteValue":
            failures.append(
                f"route.refresh schema {field} must use opaqueRouteValue with "
                f"maxLength {OPAQUE_ROUTE_VALUE_MAX_CHARS}"
            )
    for field in ROUTE_REFRESH_OPAQUE_SECRET_FIELDS:
        if properties.get(field, {}).get("$ref") != "#/$defs/opaqueRouteSecret":
            failures.append(
                f"route.refresh schema {field} must use opaqueRouteSecret with "
                f"maxLength {OPAQUE_ROUTE_VALUE_MAX_CHARS}"
            )
    for field in ROUTE_REFRESH_OPAQUE_BODY_FIELDS:
        if properties.get(field, {}).get("$ref") != "#/$defs/opaqueRouteBody":
            failures.append(
                f"route.refresh schema {field} must use opaqueRouteBody with "
                f"maxLength {OPAQUE_ROUTE_BODY_MAX_CHARS}"
            )
    return failures


def route_refresh_relay_host_schema_is_canonical(schema: object) -> bool:
    if not isinstance(schema, dict):
        return False
    all_of = schema.get("allOf", [])
    if not isinstance(all_of, list):
        return False
    has_non_empty_ref = any(
        isinstance(rule, dict) and rule.get("$ref") == "#/$defs/nonEmptyString"
        for rule in all_of
    )
    has_no_whitespace_pattern = any(
        isinstance(rule, dict) and rule.get("pattern") == "^\\S+$"
        for rule in all_of
    )
    forbidden_patterns = {
        rule.get("not", {}).get("pattern")
        for rule in all_of
        if isinstance(rule, dict) and isinstance(rule.get("not"), dict)
    }
    forbidden_enums: set[str] = set()
    for rule in all_of:
        if not isinstance(rule, dict) or not isinstance(rule.get("not"), dict):
            continue
        enum_values = rule["not"].get("enum", [])
        if isinstance(enum_values, list):
            forbidden_enums.update(value for value in enum_values if isinstance(value, str))
    return (
        has_non_empty_ref
        and has_no_whitespace_pattern
        and set(ROUTE_REFRESH_RELAY_HOST_FORBIDDEN_ENUMS) <= forbidden_enums
        and set(ROUTE_REFRESH_RELAY_HOST_FORBIDDEN_PATTERNS) <= forbidden_patterns
    )


def route_refresh_loopback_host_schema_is_canonical(schema: object) -> bool:
    if not isinstance(schema, dict):
        return False
    any_of = schema.get("anyOf", [])
    if not isinstance(any_of, list):
        return False
    enum_values: set[str] = set()
    patterns: set[str] = set()
    for option in any_of:
        if not isinstance(option, dict):
            continue
        option_enum = option.get("enum", [])
        if isinstance(option_enum, list):
            enum_values.update(value for value in option_enum if isinstance(value, str))
        pattern = option.get("pattern")
        if isinstance(pattern, str):
            patterns.add(pattern)
    return (
        set(LOOPBACK_RELAY_HOST_ENUMS) <= enum_values
        and set(LOOPBACK_RELAY_HOST_PATTERNS) <= patterns
    )


def is_route_refresh_loopback_usb_reverse_scope_rule(rule: object) -> bool:
    return is_route_refresh_relay_scope_rule(
        rule,
        host_ref="#/$defs/loopbackRelayHost",
        expected_scope="usb_reverse",
    )


def is_route_refresh_private_overlay_scope_rule(rule: object) -> bool:
    return is_route_refresh_relay_scope_rule(
        rule,
        host_ref="#/$defs/privateOverlayRelayHost",
        expected_scope="private_overlay",
    )


def is_route_refresh_relay_scope_rule(
    rule: object,
    *,
    host_ref: str,
    expected_scope: str,
) -> bool:
    if not isinstance(rule, dict):
        return False
    condition = rule.get("if", {})
    if not isinstance(condition, dict):
        return False
    if "relay_host" not in condition.get("required", []):
        return False
    field_schema = (
        condition.get("properties", {})
        .get("relay_host", {})
    )
    then = rule.get("then", {})
    return (
        isinstance(field_schema, dict)
        and field_schema.get("$ref") == host_ref
        and isinstance(then, dict)
        and then.get("required") == ["relay_scope"]
        and then.get("properties", {}).get("relay_scope", {}).get("const") == expected_scope
    )


def pairing_qr_relay_host_schema_allows_remote_or_usb_loopback(schema: object) -> bool:
    if not isinstance(schema, dict):
        return False
    any_of = schema.get("anyOf", [])
    if not isinstance(any_of, list):
        return False
    refs = {
        option.get("$ref")
        for option in any_of
        if isinstance(option, dict)
    }
    return {
        "#/$defs/eligibleRelayHost",
        "#/$defs/loopbackRelayHost",
    } <= refs


def check_usb_reverse_qr_scope_contract(schema: dict) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    loopback_host = defs.get("loopbackRelayHost", {})
    if not route_refresh_loopback_host_schema_is_canonical(loopback_host):
        failures.append(
            "loopbackRelayHost must match localhost, IPv4 loopback, and IPv6 loopback relay hosts"
        )

    usb_reverse_scope = defs.get("usbReverseScopeRequired", {})
    usb_reverse_scope_json = json.dumps(usb_reverse_scope, sort_keys=True)
    for scope_field in PAIRING_QR_REMOTE_RELAY_SCOPE_FIELDS:
        if scope_field not in usb_reverse_scope_json:
            failures.append(
                f"usbReverseScopeRequired must allow {scope_field}=usb_reverse"
            )
    if "usb_reverse" not in usb_reverse_scope_json:
        failures.append("usbReverseScopeRequired must require usb_reverse")

    conditional_rules = schema.get("allOf", [])
    for field in PRIVATE_RELAY_HOST_FIELDS:
        if not any(is_usb_reverse_scope_rule(rule, field) for rule in conditional_rules):
            failures.append(
                f"pairing QR schema must require usb_reverse scope when {field} "
                "uses a loopback relay literal"
            )
    return failures


def check_private_overlay_qr_scope_contract(schema: dict) -> list[str]:
    failures: list[str] = []
    defs = schema.get("$defs", {})
    private_host = defs.get("privateOverlayRelayHost", {})
    host_patterns = "\n".join(
        option.get("pattern", "")
        for option in private_host.get("anyOf", [])
        if isinstance(option, dict)
    )
    for expected_pattern in [
        "^10\\.",
        "^100\\.",
        "^172\\.",
        "^192\\.168\\.",
        "f[c-d]",
    ]:
        if expected_pattern not in host_patterns:
            failures.append(
                "privateOverlayRelayHost must match private/CGNAT/ULA relay hosts; "
                f"missing {expected_pattern}"
            )

    private_scope = defs.get("privateOverlayScopeRequired", {})
    private_scope_json = json.dumps(private_scope, sort_keys=True)
    for scope_field in PAIRING_QR_REMOTE_RELAY_SCOPE_FIELDS:
        if scope_field not in private_scope_json:
            failures.append(
                f"privateOverlayScopeRequired must allow {scope_field}=private_overlay"
            )
    if "private_overlay" not in private_scope_json:
        failures.append("privateOverlayScopeRequired must require private_overlay")

    conditional_rules = schema.get("allOf", [])
    for field in PRIVATE_RELAY_HOST_FIELDS:
        if not any(is_private_overlay_scope_rule(rule, field) for rule in conditional_rules):
            failures.append(
                f"pairing QR schema must require private_overlay scope when {field} "
                "uses a private, CGNAT, or ULA relay host"
            )
    return failures


def is_usb_reverse_scope_rule(rule: object, field: str) -> bool:
    return is_pairing_qr_scope_requirement_rule(
        rule,
        field=field,
        host_ref="#/$defs/loopbackRelayHost",
        scope_ref="#/$defs/usbReverseScopeRequired",
    )


def is_private_overlay_scope_rule(rule: object, field: str) -> bool:
    return is_pairing_qr_scope_requirement_rule(
        rule,
        field=field,
        host_ref="#/$defs/privateOverlayRelayHost",
        scope_ref="#/$defs/privateOverlayScopeRequired",
    )


def is_pairing_qr_scope_requirement_rule(
    rule: object,
    *,
    field: str,
    host_ref: str,
    scope_ref: str,
) -> bool:
    if not isinstance(rule, dict):
        return False
    condition = rule.get("if", {})
    if not isinstance(condition, dict):
        return False
    required = condition.get("required", [])
    properties = condition.get("properties", {})
    if field not in required or not isinstance(properties, dict):
        return False
    field_schema = properties.get(field, {})
    if not isinstance(field_schema, dict):
        return False
    then = rule.get("then", {})
    return (
        field_schema.get("$ref") == host_ref
        and isinstance(then, dict)
        and then.get("$ref") == scope_ref
    )


def check_compact_relay_fixture(
    *,
    fixture_path: Path,
    label: str,
    expected_host: str,
    expected_scope: str,
) -> list[str]:
    failures: list[str] = []
    try:
        raw_value = fixture_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return [
            f"missing {label} {fixture_path.relative_to(ROOT)}"
        ]

    parsed = urlparse(raw_value)
    if parsed.scheme != "aetherlink" or parsed.netloc != "pair":
        failures.append(f"{label} must use aetherlink://pair")
        return failures

    query = {
        key: values[-1]
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
    }
    required_fields = {
        "v",
        "n",
        "c",
        "rid",
        "rn",
        "rf",
        "rk",
        "rt",
        "rh",
        "rp",
        "ri",
        "rs",
        "rx",
        "rrn",
        "rsc",
    }
    missing = sorted(required_fields - set(query))
    if missing:
        failures.append(f"{label} missing {missing}")

    forbidden_direct_fields = sorted({"h", "p", "host", "port"} & set(query))
    if forbidden_direct_fields:
        failures.append(
            f"{label} must not include local direct route fields "
            f"{forbidden_direct_fields}"
        )

    if query.get("rsc") != expected_scope:
        failures.append(f"{label} must use rsc={expected_scope}")
    if query.get("rh") != expected_host:
        failures.append(f"{label} must use relay host {expected_host}")
    if not query.get("rp", "").isdigit():
        failures.append(f"{label} rp must be a digit string")
    if not query.get("rx", "").isdigit():
        failures.append(f"{label} rx must be a digit string")

    return failures


def check_compact_p2p_rendezvous_fixture(
    *,
    fixture_path: Path,
    label: str,
) -> list[str]:
    failures: list[str] = []
    try:
        raw_value = fixture_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return [
            f"missing {label} {fixture_path.relative_to(ROOT)}"
        ]

    parsed = urlparse(raw_value)
    if parsed.scheme != "aetherlink" or parsed.netloc != "pair":
        failures.append(f"{label} must use aetherlink://pair")
        return failures

    query = {
        key: values[-1]
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
    }
    required_fields = {
        "v",
        "n",
        "c",
        "rid",
        "rn",
        "rf",
        "rk",
        "rt",
        "pc",
        "prid",
        "peb",
        "px",
        "pn",
        "pv",
    }
    missing = sorted(required_fields - set(query))
    if missing:
        failures.append(f"{label} missing {missing}")

    forbidden_route_fields = sorted(
        {
            "h",
            "p",
            "host",
            "port",
            "rh",
            "rp",
            "ri",
            "rs",
            "rx",
            "rrn",
            "relay_host",
            "relay_port",
            "relay_id",
            "relay_secret",
            "relay_expires_at",
            "relay_nonce",
        } & set(query)
    )
    if forbidden_route_fields:
        failures.append(
            f"{label} must not include local direct or relay route fields "
            f"{forbidden_route_fields}"
        )

    if query.get("pc") != "p2p_rendezvous":
        failures.append(f"{label} must use pc=p2p_rendezvous")
    if query.get("pv") != "1":
        failures.append(f"{label} must use pv=1")
    if not query.get("px", "").isdigit():
        failures.append(f"{label} px must be a digit string")

    return failures


def pairing_qr_required_groups(schema: dict) -> list[set[str]]:
    groups: list[set[str]] = []
    required = schema.get("required", [])
    if isinstance(required, list):
        groups.extend({field} for field in required if isinstance(field, str))
    for rule in schema.get("allOf", []):
        if not isinstance(rule, dict):
            continue
        for option in rule.get("anyOf", []):
            if not isinstance(option, dict):
                continue
            option_required = option.get("required", [])
            if isinstance(option_required, list):
                group = {field for field in option_required if isinstance(field, str)}
                if group:
                    groups.append(group)
    return groups


if __name__ == "__main__":
    raise SystemExit(main())
