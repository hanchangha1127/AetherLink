#!/usr/bin/env python3
"""Check the protocol JSON schema and v0.1 active message enum."""

from __future__ import annotations

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
    "memory.summary.drafts.list",
    "memory.summary.draft.approve",
    "memory.summary.draft.dismiss",
}
ALLOWED_INDEX_TYPES = {
    "index.documents.list",
}
ALLOWED_TOOL_TYPES = frozenset()
ALLOWED_ROUTE_TYPES = {"route.refresh"}
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
        "retrieval.query",
        "index.build",
        "research.brief.create",
        "citation.sources.list",
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
        "retrieval.query",
        "index.build",
        "research.brief.create",
        "citation.sources.list",
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
            "file.*, terminal.*, network.*, backend.*, embeddings.*, retrieval.*, "
            "unsupported index.*, research.*, citation.*, source_control.*, p2p.*, rendezvous.*, "
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
        "memory.summary.drafts.list",
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
        allowed_keys = {"session_id", "model", "locale", "messages"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append(
                "$defs.chatSendPayload.properties must stay limited to session_id, model, locale, and messages"
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
    if chat_send_payload.get("additionalProperties") is not False:
        failures.append("$defs.chatSendPayload.additionalProperties must be false")
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
        },
        "helloPayload": {
            "device_id",
            "device_name",
            "client_capabilities",
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
            ]:
                failures.append("$defs.pairingRequestPayload request must require only pairing_nonce, pairing_code, device_id, device_name, and public_key")
            for field in [
                "pairing_nonce",
                "pairing_code",
                "device_id",
                "device_name",
                "public_key",
            ]:
                if properties.get(field, {}).get("$ref") != "#/$defs/nonBlankString":
                    failures.append(f"$defs.pairingRequestPayload request {field} must use nonBlankString")
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
                if client_capabilities.get("uniqueItems") is not True:
                    failures.append("$defs.helloPayload client_capabilities must keep uniqueItems true")

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
    elif set(properties.keys()) != {"device_id", "nonce", "signature"}:
        failures.append("$defs.authResponsePayload request properties must stay limited to device_id, nonce, and signature")
    else:
        for field in ["device_id", "nonce", "signature"]:
            if properties.get(field, {}).get("$ref") != "#/$defs/nonBlankString":
                failures.append(f"$defs.authResponsePayload request {field} must use nonBlankString")
    if request_option.get("additionalProperties") is not False:
        failures.append("$defs.authResponsePayload request additionalProperties must be false")

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
        return ["$defs.memoryListPayload must include a query-only request payload option"]
    if not isinstance(response_option, dict):
        failures.append("$defs.memoryListPayload must include an entries response payload option")

    properties = request_option.get("properties")
    if not isinstance(properties, dict):
        failures.append("$defs.memoryListPayload request properties must be an object")
    else:
        allowed_keys = {"query"}
        actual_keys = set(properties.keys())
        if actual_keys != allowed_keys:
            failures.append("$defs.memoryListPayload request properties must stay limited to query")
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


def main() -> int:
    failures: list[str] = []

    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{SCHEMA_PATH.relative_to(ROOT)}: invalid JSON: {error}", file=sys.stderr)
        return 1

    try:
        pairing_qr_schema = json.loads(PAIRING_QR_SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"{PAIRING_QR_SCHEMA_PATH.relative_to(ROOT)}: missing QR payload schema", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"{PAIRING_QR_SCHEMA_PATH.relative_to(ROOT)}: invalid JSON: {error}", file=sys.stderr)
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
        failures.extend(check_memory_upsert_payload_schema_contract(schema))
        failures.extend(check_memory_delete_payload_schema_contract(schema))
        failures.extend(check_chat_send_payload_schema_contract(schema))
        failures.extend(check_chat_title_request_payload_schema_contract(schema))
        failures.extend(check_chat_message_schema_contract(schema))
        failures.extend(check_chat_attachment_schema_contract(schema))

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
    for error_code in [
        "unexpected_message_direction",
        "memory_summary_draft_unavailable",
        "memory_summary_draft_stale",
    ]:
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
    if actual != expected:
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
        missing = sorted(schema_message_types - platform_message_types)
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
