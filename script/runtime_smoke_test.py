#!/usr/bin/env python3
import argparse
import json
import socket
import struct
from datetime import datetime, timezone
from uuid import uuid4

SUCCESS_PAYLOAD_KEYS = {
    "runtime.health": {"status", "ollama"},
    "models.list": {"models"},
}

BACKEND_LEAK_MARKERS = (
    "127.0.0.1:11434",
    "localhost:11434",
    "0.0.0.0:11434",
    ":11434",
    "http://",
    "https://",
    "ws://",
    "wss://",
)


def frame(envelope):
    body = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def read_frame(sock):
    length_bytes = read_exactly(sock, 4)
    length = struct.unpack(">I", length_bytes)[0]
    body = read_exactly(sock, length)
    return json.loads(body.decode("utf-8"))


def read_exactly(sock, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError("socket closed while reading frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def envelope(message_type, payload=None, request_id=None):
    return {
        "version": 1,
        "type": message_type,
        "request_id": request_id or str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payload or {},
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run the default AetherLink v0.1 security smoke. "
            "Unauthenticated runtime commands must be rejected before pairing/auth."
        )
    )
    parser.add_argument("host", nargs="?", default="127.0.0.1")
    parser.add_argument("port", nargs="?", type=int, default=43170)
    return parser.parse_args()


def contains_backend_leak(value):
    if isinstance(value, dict):
        return any(contains_backend_leak(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_backend_leak(child) for child in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in BACKEND_LEAK_MARKERS)
    return False


def assert_authentication_required(command_type, request_id, response):
    rendered = json.dumps(response, sort_keys=True)
    print(json.dumps(response, indent=2, sort_keys=True))

    if contains_backend_leak(response):
        raise SystemExit(f"backend URL leaked in {command_type} response: {rendered}")

    response_type = response.get("type")
    if response_type != "error":
        raise SystemExit(
            f"{command_type} was not rejected before authentication: "
            f"expected type=error, got type={response_type!r}"
        )

    if response.get("request_id") != request_id:
        raise SystemExit(
            f"{command_type} response request_id mismatch: "
            f"expected {request_id!r}, got {response.get('request_id')!r}"
        )

    payload = response.get("payload")
    if not isinstance(payload, dict):
        raise SystemExit(f"{command_type} error response has non-object payload: {payload!r}")

    code = payload.get("code")
    if code != "authentication_required":
        raise SystemExit(
            f"{command_type} returned wrong error code before authentication: {code!r}"
        )

    leaked_success_keys = SUCCESS_PAYLOAD_KEYS[command_type].intersection(payload.keys())
    if leaked_success_keys:
        raise SystemExit(
            f"{command_type} error response included successful runtime payload keys: "
            f"{sorted(leaked_success_keys)}"
        )

    print(f"OK: {command_type} rejected with authentication_required before pairing/auth.")


def main():
    args = parse_args()
    commands = (
        ("runtime.health", "smoke-health"),
        ("models.list", "smoke-models"),
    )

    print(
        "Running AetherLink security smoke: unauthenticated runtime commands "
        "must return error.authentication_required."
    )

    with socket.create_connection((args.host, args.port), timeout=5) as sock:
        sock.settimeout(5)
        for command_type, request_id in commands:
            sock.sendall(frame(envelope(command_type, request_id=request_id)))
            response = read_frame(sock)
            assert_authentication_required(command_type, request_id, response)

    print("OK: default security smoke passed.")


if __name__ == "__main__":
    main()
