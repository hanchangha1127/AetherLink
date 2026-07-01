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
    for field in PAIRING_QR_NO_WHITESPACE_FIELDS:
        if not pairing_qr_schema_disallows_whitespace(properties.get(field, {})):
            failures.append(f"pairing QR schema {field} must reject whitespace")

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
    if field_schema.get("$ref") == "#/$defs/noWhitespaceString":
        return True
    return field_schema.get("pattern") == "^\\S+$" and field_schema.get("minLength") == 1


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
