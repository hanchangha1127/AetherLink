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

RESERVED_PREFIXES = ("skills.", "mcp.", "web_search.")
ALLOWED_MEMORY_TYPES = {
    "memory.list",
    "memory.upsert",
    "memory.delete",
    "memory.summary.drafts.list",
    "memory.summary.draft.approve",
    "memory.summary.draft.dismiss",
}
ALLOWED_TOOL_TYPES = frozenset()
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
COMPACT_RELAY_QR_FIELDS = {"rh", "rp", "ri", "rs", "rx", "rrn"}
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
    "relay_id",
    "relay_nonce",
    "p2p_record_id",
    "p2p_anti_replay_nonce",
}
ROUTE_REFRESH_OPAQUE_SECRET_FIELDS = {"relay_secret"}
ROUTE_REFRESH_OPAQUE_BODY_FIELDS = {"p2p_encrypted_body"}


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

        reserved = [
            message_type
            for message_type in message_enum
            if message_type.startswith(RESERVED_PREFIXES)
        ]
        if reserved:
            failures.append(
                "properties.type.enum includes reserved future messages "
                f"{reserved}"
            )

        unsupported_memory_types = [
            message_type
            for message_type in message_enum
            if message_type.startswith("memory.") and message_type not in ALLOWED_MEMORY_TYPES
        ]
        if unsupported_memory_types:
            failures.append(
                "properties.type.enum includes future memory messages not documented "
                f"as active {unsupported_memory_types}"
            )

        unsupported_tool_types = [
            message_type
            for message_type in message_enum
            if message_type.startswith("tool.") and message_type not in ALLOWED_TOOL_TYPES
        ]
        if unsupported_tool_types:
            failures.append(
                "properties.type.enum includes future tool messages not documented "
                f"as active v0.1 {unsupported_tool_types}"
            )

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

    request_id_schema = schema.get("properties", {}).get("request_id", {})
    if not isinstance(request_id_schema, dict):
        failures.append("properties.request_id must be an object schema")
    else:
        if request_id_schema.get("type") != "string":
            failures.append("properties.request_id must be a string")
        if request_id_schema.get("format") == "uuid":
            failures.append("properties.request_id must not require UUID format")
        if request_id_schema.get("minLength") != 1:
            failures.append("properties.request_id must require minLength 1")

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
    expect_schema_equal(
        failures,
        f"{label} draft_id",
        properties.get("draft_id"),
        {"$ref": "#/$defs/nonEmptyString"},
    )
    expect_schema_equal(
        failures,
        f"{label} expected_session_id",
        properties.get("expected_session_id"),
        {"$ref": "#/$defs/nonEmptyString"},
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
            {"$ref": "#/$defs/nonEmptyString"},
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

    for scope_field in ["relay_scope", "remote_scope", "rsc"]:
        scope_enum = properties.get(scope_field, {}).get("enum", [])
        if "remote" not in scope_enum:
            failures.append(f"pairing QR schema {scope_field} must allow remote route scope")
        if "private_overlay" not in scope_enum:
            failures.append(f"pairing QR schema {scope_field} must allow private_overlay route scope")

    defs = schema.get("$defs", {})
    no_whitespace_def = defs.get("noWhitespaceString", {})
    if no_whitespace_def.get("type") != "string" or no_whitespace_def.get("minLength") != 1:
        failures.append("pairing QR schema noWhitespaceString must be a non-empty string")
    if no_whitespace_def.get("pattern") != "^\\S+$":
        failures.append("pairing QR schema noWhitespaceString must reject whitespace")
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

    relay_host = properties.get("relay_host", {})
    relay_ref = relay_host.get("$ref")
    if relay_ref != "#/$defs/eligibleRelayHost":
        failures.append("relay_host must use eligibleRelayHost")

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

    joined_patterns = "\n".join(forbidden_patterns)
    for forbidden in ["local$", "169\\.254", "fe80"]:
        if forbidden not in joined_patterns:
            failures.append(f"eligibleRelayHost must reject {forbidden}")

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
    ):
        failures.append(
            f"{label} opaqueRouteSecret must be a non-empty string capped at "
            f"{OPAQUE_ROUTE_VALUE_MAX_CHARS} characters"
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

    route_refresh = defs.get("routeRefreshPayload", {})
    route_refresh_options = route_refresh.get("oneOf", [])
    material_schema = None
    for option in route_refresh_options:
        if isinstance(option, dict) and "properties" in option:
            material_schema = option
            break
    if material_schema is None:
        return ["route.refresh schema must include a route-material payload option"]

    properties = material_schema.get("properties", {})
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
    for scope_field in ["relay_scope", "remote_scope", "rsc"]:
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


def is_private_overlay_scope_rule(rule: object, field: str) -> bool:
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
        field_schema.get("$ref") == "#/$defs/privateOverlayRelayHost"
        and isinstance(then, dict)
        and then.get("$ref") == "#/$defs/privateOverlayScopeRequired"
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
