#!/usr/bin/env python3
import argparse
import ipaddress
import json
import os
import socket
import sys
import time
import uuid


RESPONSE_PREFIX = "AETHERLINK_RELAY preflight "
ALLOWED_PREFLIGHT_RESPONSE_FIELDS = {
    "preflight",
    "crypto_version",
    "allocation_auth",
}
UNSAFE_RELAY_HOST_TOKENS = ("://", "/", "\\", "?", "#", "@")


class StrictJSONError(ValueError):
    pass


def reject_duplicate_object_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError("duplicate object key")
        result[key] = value
    return result


def reject_non_finite_json_constant(_value):
    raise StrictJSONError("non-finite JSON number")


def strict_json_loads(value):
    return json.loads(
        value,
        object_pairs_hook=reject_duplicate_object_keys,
        parse_constant=reject_non_finite_json_constant,
    )


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
    parser.add_argument("--route-token", default="")
    parser.add_argument("--route-token-prefix", default="aetherlink-preflight")
    parser.add_argument("--timeout", default=5.0, type=float)
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
    parts = ["AETHERLINK_RELAY", "allocate", route_token, "crypto=2"]
    if args.allocation_token:
        parts.append(f"allocation_token={args.allocation_token}")
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


def parse_response(host, port, line):
    if not line.startswith(RESPONSE_PREFIX):
        raise RuntimeError(
            f"Relay {host}:{port} did not return a preflight response: "
            f"{redacted_unexpected_response(line)}"
        )
    try:
        payload = strict_json_loads(line[len(RESPONSE_PREFIX):])
    except (json.JSONDecodeError, StrictJSONError, RecursionError) as error:
        raise RuntimeError(f"Relay {host}:{port} returned invalid preflight JSON") from error

    if not isinstance(payload, dict):
        raise RuntimeError(f"Relay {host}:{port} returned non-object preflight JSON")
    unexpected_fields = set(payload) - ALLOWED_PREFLIGHT_RESPONSE_FIELDS
    if unexpected_fields:
        raise RuntimeError(
            f"Relay {host}:{port} preflight response included unsupported metadata"
        )
    if set(payload) != ALLOWED_PREFLIGHT_RESPONSE_FIELDS:
        raise RuntimeError(
            f"Relay {host}:{port} preflight response did not match the expected closed field set"
        )
    if payload["preflight"] is not True:
        raise RuntimeError(f"Relay {host}:{port} did not acknowledge preflight")
    if type(payload["crypto_version"]) is not int or payload["crypto_version"] != 2:
        raise RuntimeError(f"Relay {host}:{port} returned invalid crypto_version")
    if payload["allocation_auth"] != "runtime-p256-v1":
        raise RuntimeError(f"Relay {host}:{port} returned invalid allocation_auth")
    return payload


def main():
    args = parse_args()
    try:
        validate_args(args)
        _, request_line = build_request(args)
        line = read_allocation(args.host, args.port, request_line, args.timeout)
        payload = parse_response(args.host, args.port, line)
    except Exception as error:
        print(
            f"Could not validate relay allocation contract at {safe_endpoint_label(args.host, args.port)}: {error}",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print(json.dumps({
            "host": args.host,
            "port": args.port,
            "preflight": True,
            "preflight_acknowledged": payload.get("preflight") is True,
            "relay_id_present": False,
            "relay_expires_at_present": False,
            "relay_nonce_present": False,
            "has_relay_secret": False,
            "crypto_version": payload.get("crypto_version"),
            "allocation_auth": payload.get("allocation_auth"),
            "endpoint_owned_relay_secret": True,
            "route_material_returned": False,
            "route_material_redacted": True,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
