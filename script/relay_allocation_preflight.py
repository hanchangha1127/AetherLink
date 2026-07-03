#!/usr/bin/env python3
import argparse
import ipaddress
import json
import os
import socket
import sys
import time
import uuid


RESPONSE_PREFIX = "AETHERLINK_RELAY allocation "
ALLOWED_ALLOCATION_RESPONSE_FIELDS = {
    "relay_id",
    "relay_secret",
    "relay_expires_at",
    "relay_nonce",
}
UNSAFE_RELAY_HOST_TOKENS = ("://", "/", "\\", "?", "#", "@")
UNSAFE_RELAY_ID_TOKENS = ("://", "/", "\\", "?", "#", "@")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Validate an AetherLinkRelay allocation endpoint. By default the "
            "request is sent with preflight=1 so the relay does not persist a "
            "throwaway lease."
        )
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--allocation-token", default=default_allocation_token())
    parser.add_argument("--relay-secret", default="")
    parser.add_argument("--route-token", default="")
    parser.add_argument("--route-token-prefix", default="aetherlink-preflight")
    parser.add_argument("--timeout", default=5.0, type=float)
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Send a normal allocation request instead of a non-persisting preflight probe.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def default_allocation_token():
    return (
        os.environ.get("AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN")
        or os.environ.get("AETHERLINK_RELAY_ALLOCATION_TOKEN")
        or ""
    )


def validate_args(args):
    if not is_safe_relay_host(args.host):
        raise ValueError(
            "--host must be a relay host or IP literal without URL, path, user-info, "
            "whitespace, or embedded port"
        )
    if not 1 <= args.port <= 65535:
        raise ValueError(f"Invalid relay port: {args.port}")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    for label, value in (
        ("--allocation-token", args.allocation_token),
        ("--relay-secret", args.relay_secret),
        ("--route-token", args.route_token),
    ):
        if value and any(character.isspace() for character in value):
            raise ValueError(f"{label} must not contain whitespace")


def is_ip_literal(value):
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def is_safe_relay_host(value):
    if not value or value != value.strip() or value.startswith("-"):
        return False
    if any(character.isspace() for character in value):
        return False
    if any(token in value for token in UNSAFE_RELAY_HOST_TOKENS):
        return False
    if ":" in value and not is_ip_literal(value):
        return False
    return True


def safe_endpoint_label(host, port):
    if is_safe_relay_host(host):
        return f"{host}:{port}"
    return f"<invalid-host>:{port}"


def build_request(args):
    route_token = args.route_token or f"{args.route_token_prefix}-{uuid.uuid4()}"
    parts = ["AETHERLINK_RELAY", "allocate", route_token]
    if args.relay_secret:
        parts.append(args.relay_secret)
    if args.allocation_token:
        parts.append(f"allocation_token={args.allocation_token}")
    if not args.persist:
        parts.append("preflight=1")
    return route_token, " ".join(parts) + "\n"


def read_allocation(host, port, request_line, timeout):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        try:
            with socket.create_connection((host, port), timeout=min(remaining, 1.0)) as sock:
                sock.settimeout(remaining)
                sock.sendall(request_line.encode("utf-8"))
                buffer = b""
                while not buffer.endswith(b"\n") and len(buffer) < 8192:
                    chunk = sock.recv(1024)
                    if not chunk:
                        break
                    buffer += chunk
            return buffer.decode("utf-8", errors="replace").strip()
        except OSError as error:
            last_error = error
            time.sleep(0.1)
    raise OSError(str(last_error) if last_error else "timed out")


def redacted_unexpected_response(line):
    if not line:
        return "<empty relay response>"
    return f"<redacted unexpected relay response, {len(line)} characters>"


def validate_canonical_response_value(payload, key, host, port):
    value = payload[key]
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(character.isspace() for character in value)
    ):
        raise RuntimeError(f"Relay {host}:{port} returned invalid {key}")
    if key == "relay_id" and any(token in value for token in UNSAFE_RELAY_ID_TOKENS):
        raise RuntimeError(f"Relay {host}:{port} returned invalid {key}")


def validate_relay_expires_at(payload, host, port):
    expires_at = payload["relay_expires_at"]
    if type(expires_at) is not int:
        raise RuntimeError(f"Relay {host}:{port} returned invalid relay_expires_at")
    if expires_at <= 0:
        raise RuntimeError(f"Relay {host}:{port} returned expired relay_expires_at")


def parse_response(host, port, line, requested_route_token=""):
    if not line.startswith(RESPONSE_PREFIX):
        raise RuntimeError(
            f"Relay {host}:{port} did not return an allocation response: "
            f"{redacted_unexpected_response(line)}"
        )
    try:
        payload = json.loads(line[len(RESPONSE_PREFIX):])
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Relay {host}:{port} returned invalid allocation JSON: {error}") from error

    if not isinstance(payload, dict):
        raise RuntimeError(f"Relay {host}:{port} returned non-object allocation JSON")
    if set(payload) - ALLOWED_ALLOCATION_RESPONSE_FIELDS:
        raise RuntimeError(
            f"Relay {host}:{port} allocation response included unsupported metadata"
        )

    required = ["relay_id", "relay_secret", "relay_expires_at", "relay_nonce"]
    missing = [
        key
        for key in required
        if key not in payload or payload[key] is None or payload[key] == ""
    ]
    if missing:
        raise RuntimeError(
            f"Relay {host}:{port} allocation response missing: {', '.join(missing)}"
        )
    for key in ("relay_id", "relay_secret", "relay_nonce"):
        validate_canonical_response_value(payload, key, host, port)
    if requested_route_token and payload["relay_id"] == requested_route_token:
        raise RuntimeError(
            f"Relay {host}:{port} echoed the requested route token as relay_id; "
            "allocation relay IDs must be opaque"
        )
    validate_relay_expires_at(payload, host, port)
    return payload


def main():
    args = parse_args()
    try:
        validate_args(args)
        requested_route_token, request_line = build_request(args)
        line = read_allocation(args.host, args.port, request_line, args.timeout)
        payload = parse_response(args.host, args.port, line, requested_route_token)
    except Exception as error:
        print(
            f"Could not allocate relay route from {safe_endpoint_label(args.host, args.port)}: {error}",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print(json.dumps({
            "host": args.host,
            "port": args.port,
            "preflight": not args.persist,
            "relay_id_present": bool(payload.get("relay_id")),
            "relay_expires_at_present": bool(payload.get("relay_expires_at")),
            "relay_nonce_present": bool(payload.get("relay_nonce")),
            "has_relay_secret": bool(payload.get("relay_secret")),
            "route_material_redacted": True,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
