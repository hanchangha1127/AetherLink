#!/usr/bin/env python3
"""Resolve one missing module ZIP H1 through a claimed SumDB proof attempt."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True
if not (
    sys.flags.isolated == 1
    and sys.flags.dont_write_bytecode == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_user_site == 1
    and sys.flags.no_site == 1
    and sys.flags.optimize == 0
):
    raise RuntimeError("resolver requires `python3 -I -B -S`")

import argparse
import base64
import binascii
import ctypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import signal
import ssl
import stat
import time
import types
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PERMIT_CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_execution_permit_v1.py"
)
EXPECTED_PERMIT_CHECKER_RAW = "14b628e788dcd216e9102596f95681dfe1fbb6e97e6b6170ece19fee6499ab6c"


def load_permit_checker() -> types.ModuleType:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(PERMIT_CHECKER_PATH, flags)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid not in {0, os.geteuid()}
            or stat.S_IMODE(before.st_mode) & 0o022
            or not 0 < before.st_size <= 4 * 1024 * 1024
        ):
            raise RuntimeError("invalid permit checker shape")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                raise RuntimeError("short permit checker read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise RuntimeError("permit checker grew while held")
        after = os.fstat(fd)
        raw = b"".join(chunks)
        if (
            before != after
            or hashlib.sha256(raw).hexdigest()
            != EXPECTED_PERMIT_CHECKER_RAW
        ):
            raise RuntimeError("permit checker identity mismatch")
    finally:
        os.close(fd)
    module = types.ModuleType("sumdb_identity_execution_permit_v1")
    module.__file__ = str(PERMIT_CHECKER_PATH)
    module.__package__ = ""
    exec(compile(raw, str(PERMIT_CHECKER_PATH), "exec"), module.__dict__)
    return module


PERMIT = load_permit_checker()

TARGET_MODULE = PERMIT.DECISION.TARGET_MODULE
TARGET_VERSION = PERMIT.DECISION.TARGET_VERSION
TARGET_MOD_H1 = PERMIT.DECISION.TARGET_MOD_H1
LOOKUP_URL = PERMIT.DECISION.LOOKUP_URL
LOOKUP_HOST = PERMIT.DECISION.LOOKUP_HOST
OLD_TREE_SIZE = PERMIT.DECISION.OLD_TREE_SIZE
OLD_ROOT = base64.b64decode(
    PERMIT.DECISION.OLD_ROOT_HASH_BASE64,
    validate=True,
)
MAXIMUM_REQUEST_COUNT = PERMIT.DECISION.MAXIMUM_REQUEST_COUNT
MAXIMUM_AGGREGATE_BYTES = (
    PERMIT.DECISION.MAXIMUM_AGGREGATE_RESPONSE_BYTES
)
MAXIMUM_LOOKUP_BYTES = PERMIT.DECISION.MAXIMUM_LOOKUP_RESPONSE_BYTES
MAXIMUM_TILE_BYTES = PERMIT.DECISION.MAXIMUM_TILE_RESPONSE_BYTES
MAXIMUM_HEADER_BYTES = PERMIT.DECISION.MAXIMUM_HEADER_BYTES
PER_REQUEST_TIMEOUT_SECONDS = (
    PERMIT.DECISION.PER_REQUEST_DEADLINE_MS / 1000
)
WHOLE_ATTEMPT_TIMEOUT_SECONDS = (
    PERMIT.DECISION.WHOLE_ATTEMPT_DEADLINE_MS / 1000
)
TILE_HEIGHT = PERMIT.DECISION.TILE_HEIGHT
FULL_TILE_WIDTH = PERMIT.DECISION.FULL_TILE_WIDTH
RENAME_EXCL = 0x00000004

Expr = tuple[Any, ...]
Fetch = Callable[[str, int, float], bytes]


class ResolverError(RuntimeError):
    def __init__(self, code: str, phase: str) -> None:
        super().__init__(f"{code}:{phase}")
        self.code = code
        self.phase = phase


def require(value: bool, code: str, phase: str) -> None:
    if not value:
        raise ResolverError(code, phase)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def decode_base64(value: str, length: int, phase: str) -> bytes:
    require(type(value) is str, "E_BASE64", phase)
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ResolverError("E_BASE64", phase) from error
    require(
        len(raw) == length
        and base64.b64encode(raw).decode("ascii") == value,
        "E_BASE64",
        phase,
    )
    return raw


def decode_h1(value: str, phase: str) -> bytes:
    require(value.startswith("h1:"), "E_H1", phase)
    return decode_base64(value[3:], 32, phase)


def verifier_material() -> tuple[bytes, bytes]:
    match = re.fullmatch(
        r"([^+]+)[+]([0-9a-f]{8})[+](.+)",
        PERMIT.DECISION.SUMDB_VERIFIER_KEY,
    )
    require(match is not None, "E_KEY", "signed_note")
    name, key_hash_hex, payload_text = match.groups()
    payload = decode_base64(payload_text, 33, "signed_note")
    require(payload[0] == 1, "E_KEY", "signed_note")
    key_hash = hashlib.sha256(
        name.encode("utf-8") + b"\n" + payload
    ).digest()[:4]
    require(key_hash.hex() == key_hash_hex, "E_KEY", "signed_note")
    return payload[1:], key_hash


def verify_signed_note(note_raw: bytes) -> dict[str, Any]:
    phase = "signed_note"
    require(
        b"\r" not in note_raw
        and b"\x00" not in note_raw
        and note_raw.endswith(b"\n"),
        "E_NOTE",
        phase,
    )
    delimiter = b"\n\n\xe2\x80\x94 sum.golang.org "
    require(note_raw.count(delimiter) == 1, "E_NOTE", phase)
    message, signature_tail = note_raw.split(delimiter)
    require(
        signature_tail.endswith(b"\n")
        and b"\n" not in signature_tail[:-1],
        "E_NOTE",
        phase,
    )
    try:
        message_lines = message.decode("ascii", errors="strict").split("\n")
        signature_text = signature_tail[:-1].decode(
            "ascii",
            errors="strict",
        )
    except UnicodeDecodeError as error:
        raise ResolverError("E_NOTE", phase) from error
    require(
        len(message_lines) == 3
        and message_lines[0] == "go.sum database tree",
        "E_NOTE",
        phase,
    )
    size_text = message_lines[1]
    require(
        re.fullmatch(r"0|[1-9][0-9]*", size_text) is not None,
        "E_NOTE",
        phase,
    )
    tree_size = int(size_text)
    require(0 < tree_size <= 2**62, "E_NOTE", phase)
    root = decode_base64(message_lines[2], 32, phase)
    signature = decode_base64(signature_text, 68, phase)
    public_key, key_hash = verifier_material()
    require(signature[:4] == key_hash, "E_SIGNATURE", phase)
    signed_text = message + b"\n"
    try:
        PERMIT.DECISION.RUNG2.verify_ed25519(
            public_key,
            signed_text,
            signature[4:],
        )
    except Exception as error:
        raise ResolverError("E_SIGNATURE", phase) from error
    return {
        "treeSize": tree_size,
        "root": root,
        "rootHashBase64": message_lines[2],
        "signatureBase64": signature_text,
        "signedTreeTextSha256": sha256(signed_text),
    }


def parse_lookup_response(raw: bytes) -> dict[str, Any]:
    phase = "lookup"
    require(
        0 < len(raw) <= MAXIMUM_LOOKUP_BYTES
        and raw.endswith(b"\n")
        and b"\r" not in raw
        and b"\x00" not in raw,
        "E_LOOKUP",
        phase,
    )
    separator = raw.find(b"\n\n")
    require(separator > 0, "E_LOOKUP", phase)
    record_header = raw[:separator]
    note_raw = raw[separator + 2 :]
    try:
        lines = record_header.decode("utf-8", errors="strict").split("\n")
    except UnicodeDecodeError as error:
        raise ResolverError("E_LOOKUP", phase) from error
    require(len(lines) == 3, "E_RECORD", phase)
    number_text, zip_line, mod_line = lines
    require(
        re.fullmatch(r"0|[1-9][0-9]*", number_text) is not None,
        "E_RECORD",
        phase,
    )
    record_number = int(number_text)
    zip_prefix = f"{TARGET_MODULE} {TARGET_VERSION} "
    require(
        zip_line.startswith(zip_prefix)
        and zip_line.count(" ") == 2,
        "E_RECORD",
        phase,
    )
    zip_h1 = zip_line[len(zip_prefix) :]
    decode_h1(zip_h1, phase)
    expected_mod_line = (
        f"{TARGET_MODULE} {TARGET_VERSION}/go.mod {TARGET_MOD_H1}"
    )
    require(mod_line == expected_mod_line, "E_RECORD", phase)
    note = verify_signed_note(note_raw)
    require(
        0 <= record_number < note["treeSize"],
        "E_RECORD",
        phase,
    )
    record_payload = (zip_line + "\n" + mod_line + "\n").encode("utf-8")
    return {
        "recordNumber": record_number,
        "recordPayload": record_payload,
        "recordLeafHash": hashlib.sha256(
            b"\x00" + record_payload
        ).digest(),
        "moduleZipH1": zip_h1,
        "goModH1": TARGET_MOD_H1,
        **note,
    }


def largest_power_two_less(value: int) -> int:
    require(value > 1, "E_TREE", "proof_plan")
    return 1 << ((value - 1).bit_length() - 1)


def node_expr(level: int, index: int) -> Expr:
    require(level >= 0 and index >= 0, "E_TREE", "proof_plan")
    return ("node", level, index)


def hash_expr(left: Expr, right: Expr) -> Expr:
    return ("hash", left, right)


def tree_expr(start: int, count: int) -> Expr:
    require(start >= 0 and count > 0, "E_TREE", "proof_plan")
    if count & (count - 1) == 0 and start % count == 0:
        return node_expr(count.bit_length() - 1, start // count)
    split = largest_power_two_less(count)
    return hash_expr(
        tree_expr(start, split),
        tree_expr(start + split, count - split),
    )


def inclusion_exprs(
    record_number: int,
    tree_size: int,
    start: int = 0,
) -> list[Expr]:
    require(
        tree_size > 0 and 0 <= record_number < tree_size,
        "E_TREE",
        "inclusion_plan",
    )
    if tree_size == 1:
        return []
    split = largest_power_two_less(tree_size)
    if record_number < split:
        return inclusion_exprs(record_number, split, start) + [
            tree_expr(start + split, tree_size - split)
        ]
    return inclusion_exprs(
        record_number - split,
        tree_size - split,
        start + split,
    ) + [tree_expr(start, split)]


def consistency_exprs(
    old_size: int,
    new_size: int,
) -> list[Expr]:
    require(
        0 < old_size <= new_size,
        "E_TREE",
        "consistency_plan",
    )

    def subproof(
        old_count: int,
        new_count: int,
        start: int,
        complete: bool,
    ) -> list[Expr]:
        if old_count == new_count:
            return [] if complete else [tree_expr(start, new_count)]
        split = largest_power_two_less(new_count)
        if old_count <= split:
            return subproof(old_count, split, start, complete) + [
                tree_expr(start + split, new_count - split)
            ]
        return subproof(
            old_count - split,
            new_count - split,
            start + split,
            False,
        ) + [tree_expr(start, split)]

    return subproof(old_size, new_size, 0, True)


def stored_hash_count(record_count: int) -> int:
    require(record_count >= 0, "E_TREE", "stored_hash")
    return 2 * record_count - bin(record_count).count("1")


def stored_hash_index(level: int, node: int) -> int:
    require(level >= 0 and node >= 0, "E_TREE", "stored_hash")
    completed_records = ((node + 1) << level) - 1
    return stored_hash_count(completed_records) + level


def split_stored_hash_index(index: int) -> tuple[int, int]:
    require(index >= 0, "E_TREE", "stored_hash")
    low = 1
    high = 1
    while stored_hash_count(high) <= index:
        high <<= 1
    while low < high:
        middle = (low + high) // 2
        if stored_hash_count(middle) > index:
            high = middle
        else:
            low = middle + 1
    completed_records = low
    level = index - stored_hash_count(completed_records - 1)
    node = (completed_records >> level) - 1
    require(
        stored_hash_index(level, node) == index,
        "E_TREE",
        "stored_hash",
    )
    return level, node


def expr_nodes(expr: Expr) -> set[tuple[int, int]]:
    if expr[0] == "node":
        return {(expr[1], expr[2])}
    require(expr[0] == "hash", "E_TREE", "proof_plan")
    return expr_nodes(expr[1]) | expr_nodes(expr[2])


def encode_tile_index(index: int) -> str:
    require(index >= 0, "E_TILE_PATH", "tile_plan")
    result = f"{index % 1000:03d}"
    while index >= 1000:
        index //= 1000
        result = f"x{index % 1000:03d}/{result}"
    return result


def encode_tile_path(
    tile_level: int,
    tile_index: int,
    width: int,
) -> str:
    require(
        tile_level >= 0
        and tile_index >= 0
        and 1 <= width <= FULL_TILE_WIDTH,
        "E_TILE_PATH",
        "tile_plan",
    )
    path = (
        f"/tile/{TILE_HEIGHT}/{tile_level}/"
        f"{encode_tile_index(tile_index)}"
    )
    if width < FULL_TILE_WIDTH:
        path += f".p/{width}"
    return path


def parse_tile_path(path: str) -> tuple[int, int, int]:
    match = re.fullmatch(
        r"/tile/8/(0|[1-9][0-9]*)/"
        r"((?:x[0-9]{3}/)*[0-9]{3})"
        r"(?:[.]p/([1-9][0-9]*))?",
        path,
    )
    require(match is not None, "E_TILE_PATH", "tile_plan")
    level_text, index_text, width_text = match.groups()
    tile_index = 0
    components = index_text.split("/")
    for position, component in enumerate(components):
        if position < len(components) - 1:
            require(
                component.startswith("x") and len(component) == 4,
                "E_TILE_PATH",
                "tile_plan",
            )
            digits = component[1:]
        else:
            require(
                len(component) == 3 and not component.startswith("x"),
                "E_TILE_PATH",
                "tile_plan",
            )
            digits = component
        tile_index = tile_index * 1000 + int(digits)
    width = FULL_TILE_WIDTH if width_text is None else int(width_text)
    result = (int(level_text), tile_index, width)
    require(
        1 <= width <= FULL_TILE_WIDTH
        and encode_tile_path(*result) == path
        and PERMIT.DECISION.valid_tile_path(path),
        "E_TILE_PATH",
        "tile_plan",
    )
    return result


def tile_spec_for_node(
    level: int,
    index: int,
    tree_size: int,
) -> dict[str, Any]:
    phase = "tile_plan"
    require(
        level >= 0 and index >= 0 and tree_size > 0,
        "E_TILE_PLAN",
        phase,
    )
    tile_level = level // TILE_HEIGHT
    residual = level % TILE_HEIGHT
    base_start = index << residual
    base_count = tree_size >> (tile_level * TILE_HEIGHT)
    hash_count = 1 << residual
    require(
        base_start + hash_count <= base_count,
        "E_TILE_PLAN",
        phase,
    )
    tile_index = base_start // FULL_TILE_WIDTH
    offset = base_start % FULL_TILE_WIDTH
    width = min(
        FULL_TILE_WIDTH,
        base_count - tile_index * FULL_TILE_WIDTH,
    )
    require(
        1 <= width <= FULL_TILE_WIDTH
        and offset + hash_count <= width,
        "E_TILE_PLAN",
        phase,
    )
    path = encode_tile_path(tile_level, tile_index, width)
    require(
        parse_tile_path(path) == (tile_level, tile_index, width),
        "E_TILE_PATH",
        phase,
    )
    return {
        "path": path,
        "tileLevel": tile_level,
        "tileIndex": tile_index,
        "width": width,
        "expectedBytes": width * 32,
        "offset": offset,
        "hashCount": hash_count,
        "nodeLevel": level,
        "nodeIndex": index,
    }


def derive_tile_plan(
    record_number: int,
    new_tree_size: int,
) -> dict[str, Any]:
    inclusion = inclusion_exprs(record_number, new_tree_size)
    consistency = consistency_exprs(OLD_TREE_SIZE, new_tree_size)
    nodes: set[tuple[int, int]] = set()
    for expr in (*inclusion, *consistency):
        nodes |= expr_nodes(expr)
    path_map: dict[str, dict[str, Any]] = {}
    node_specs: dict[tuple[int, int], dict[str, Any]] = {}
    for level, index in sorted(nodes):
        spec = tile_spec_for_node(level, index, new_tree_size)
        node_specs[(level, index)] = spec
        existing = path_map.get(spec["path"])
        if existing is None:
            path_map[spec["path"]] = {
                key: spec[key]
                for key in (
                    "path",
                    "tileLevel",
                    "tileIndex",
                    "width",
                    "expectedBytes",
                )
            }
        else:
            require(
                existing["width"] == spec["width"]
                and existing["expectedBytes"] == spec["expectedBytes"],
                "E_TILE_PLAN",
                "tile_plan",
            )
    tiles = sorted(
        path_map.values(),
        key=lambda row: (
            row["tileLevel"],
            row["tileIndex"],
            row["width"],
        ),
    )
    require(
        len(tiles) <= MAXIMUM_REQUEST_COUNT - 1,
        "E_LIMIT",
        "tile_plan",
    )
    return {
        "inclusionExpressions": inclusion,
        "consistencyExpressions": consistency,
        "nodeSpecs": node_specs,
        "tiles": tiles,
    }


def rfc6962_node_hash(left: bytes, right: bytes) -> bytes:
    require(
        len(left) == len(right) == 32,
        "E_PROOF",
        "proof_verify",
    )
    return hashlib.sha256(b"\x01" + left + right).digest()


def evaluate_expr(
    expr: Expr,
    node_specs: Mapping[tuple[int, int], Mapping[str, Any]],
    tile_bodies: Mapping[str, bytes],
) -> bytes:
    if expr[0] == "hash":
        return rfc6962_node_hash(
            evaluate_expr(expr[1], node_specs, tile_bodies),
            evaluate_expr(expr[2], node_specs, tile_bodies),
        )
    require(expr[0] == "node", "E_PROOF", "proof_verify")
    key = (expr[1], expr[2])
    require(key in node_specs, "E_PROOF", "proof_verify")
    spec = node_specs[key]
    path = spec["path"]
    require(path in tile_bodies, "E_PROOF", "proof_verify")
    raw = tile_bodies[path]
    require(
        len(raw) == spec["width"] * 32,
        "E_TILE_BODY",
        "proof_verify",
    )
    hashes = [raw[offset : offset + 32] for offset in range(0, len(raw), 32)]
    start = spec["offset"]
    count = spec["hashCount"]
    values = hashes[start : start + count]
    require(len(values) == count, "E_PROOF", "proof_verify")
    while len(values) > 1:
        require(len(values) % 2 == 0, "E_PROOF", "proof_verify")
        values = [
            rfc6962_node_hash(values[index], values[index + 1])
            for index in range(0, len(values), 2)
        ]
    return values[0]


def verify_inclusion(
    record_payload: bytes,
    record_number: int,
    tree_size: int,
    proof: Sequence[bytes],
    expected_root: bytes,
) -> None:
    try:
        PERMIT.DECISION.RUNG2.verify_rfc6962_inclusion(
            record_payload,
            record_number,
            tree_size,
            proof,
            expected_root,
        )
    except Exception as error:
        raise ResolverError("E_INCLUSION", "proof_verify") from error


def verify_consistency(
    old_size: int,
    new_size: int,
    old_root: bytes,
    new_root: bytes,
    proof: Sequence[bytes],
) -> None:
    phase = "proof_verify"
    require(
        0 < old_size <= new_size
        and len(old_root) == len(new_root) == 32
        and all(len(item) == 32 for item in proof),
        "E_CONSISTENCY",
        phase,
    )
    if old_size == new_size:
        require(
            not proof and old_root == new_root,
            "E_CONSISTENCY",
            phase,
        )
        return
    require(bool(proof), "E_CONSISTENCY", phase)
    fn = old_size - 1
    sn = new_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    proof_index = 0
    if old_size & (old_size - 1) == 0:
        first = old_root
    else:
        first = proof[0]
        proof_index = 1
    old_candidate = first
    new_candidate = first
    for sibling in proof[proof_index:]:
        require(sn != 0, "E_CONSISTENCY", phase)
        if (fn & 1) == 1 or fn == sn:
            old_candidate = rfc6962_node_hash(sibling, old_candidate)
            new_candidate = rfc6962_node_hash(sibling, new_candidate)
            while fn != 0 and (fn & 1) == 0:
                fn >>= 1
                sn >>= 1
        else:
            new_candidate = rfc6962_node_hash(new_candidate, sibling)
        fn >>= 1
        sn >>= 1
    require(
        fn == 0
        and sn == 0
        and old_candidate == old_root
        and new_candidate == new_root,
        "E_CONSISTENCY",
        phase,
    )


def verify_proof_bundle(
    lookup: Mapping[str, Any],
    plan: Mapping[str, Any],
    tile_bodies: Mapping[str, bytes],
) -> dict[str, Any]:
    inclusion = [
        evaluate_expr(expr, plan["nodeSpecs"], tile_bodies)
        for expr in plan["inclusionExpressions"]
    ]
    consistency = [
        evaluate_expr(expr, plan["nodeSpecs"], tile_bodies)
        for expr in plan["consistencyExpressions"]
    ]
    verify_inclusion(
        lookup["recordPayload"],
        lookup["recordNumber"],
        lookup["treeSize"],
        inclusion,
        lookup["root"],
    )
    verify_consistency(
        OLD_TREE_SIZE,
        lookup["treeSize"],
        OLD_ROOT,
        lookup["root"],
        consistency,
    )
    inclusion_values = [
        base64.b64encode(value).decode("ascii") for value in inclusion
    ]
    consistency_values = [
        base64.b64encode(value).decode("ascii") for value in consistency
    ]
    canonical_proof = canonical_bytes(
        {
            "consistencyProofHashesBase64": consistency_values,
            "inclusionProofHashesBase64": inclusion_values,
        }
    )
    return {
        "inclusionProofHashCount": len(inclusion),
        "consistencyProofHashCount": len(consistency),
        "inclusionProofHashesBase64": inclusion_values,
        "consistencyProofHashesBase64": consistency_values,
        "canonicalProofBundleSha256": sha256(canonical_proof),
        "recordInclusionVerified": True,
        "oldToNewConsistencyVerified": True,
    }


def validate_request_url(url: str) -> None:
    parsed = urlsplit(url)
    require(
        parsed.scheme == "https"
        and parsed.hostname == LOOKUP_HOST
        and parsed.netloc == LOOKUP_HOST
        and parsed.port is None
        and not parsed.query
        and not parsed.fragment
        and (
            url == LOOKUP_URL
            or PERMIT.DECISION.valid_tile_path(parsed.path)
        ),
        "E_URL",
        "network",
    )


def response_header_bytes(headers: Sequence[tuple[str, str]]) -> int:
    total = 0
    for key, value in headers:
        require(
            "\r" not in key
            and "\n" not in key
            and "\r" not in value
            and "\n" not in value,
            "E_HEADERS",
            "network",
        )
        total += len(key.encode("ascii", errors="strict"))
        total += len(value.encode("latin-1", errors="strict")) + 4
    return total + 2


def remaining_request_seconds(request_deadline: float) -> float:
    remaining = request_deadline - time.monotonic()
    require(remaining > 0, "E_DEADLINE", "network")
    return remaining


def refresh_connection_timeout(
    connection: http.client.HTTPSConnection,
    request_deadline: float,
) -> None:
    remaining = remaining_request_seconds(request_deadline)
    connection.timeout = remaining
    transport = getattr(connection, "sock", None)
    if transport is not None:
        transport.settimeout(remaining)


def direct_fetch(url: str, maximum_bytes: int, deadline: float) -> bytes:
    validate_request_url(url)
    parsed = urlsplit(url)
    request_started = time.monotonic()
    request_deadline = min(
        deadline,
        request_started + PER_REQUEST_TIMEOUT_SECONDS,
    )
    request_budget = remaining_request_seconds(request_deadline)
    existing_timer = signal.getitimer(signal.ITIMER_REAL)
    if existing_timer[0] > 0:
        request_budget = min(request_budget, existing_timer[0])

    def request_alarm_handler(signum: int, frame: Any) -> None:
        raise ResolverError("E_DEADLINE", "network")

    previous_handler = signal.signal(signal.SIGALRM, request_alarm_handler)
    previous_timer = signal.setitimer(
        signal.ITIMER_REAL,
        request_budget,
    )
    connection = None
    try:
        context = ssl.create_default_context()
        connection = http.client.HTTPSConnection(
            LOOKUP_HOST,
            443,
            timeout=remaining_request_seconds(request_deadline),
            context=context,
        )
        request_headers = {
            "Accept": "text/plain, application/octet-stream",
            "Accept-Encoding": "identity",
            "User-Agent": "AetherLink-SumDB-Identity/1",
        }
        forbidden = {
            "authorization",
            "proxy-authorization",
            "cookie",
            "range",
        }
        require(
            not forbidden.intersection(
                {key.lower() for key in request_headers}
            ),
            "E_AUTH",
            "network",
        )
        refresh_connection_timeout(connection, request_deadline)
        connection.request(
            "GET",
            parsed.path,
            body=None,
            headers=request_headers,
            encode_chunked=False,
        )
        refresh_connection_timeout(connection, request_deadline)
        response = connection.getresponse()
        try:
            remaining_request_seconds(request_deadline)
            headers = response.getheaders()
            require(
                response.status == 200
                and response.getheader("Location") is None
                and response.getheader("WWW-Authenticate") is None
                and response.getheader("Proxy-Authenticate") is None
                and response.getheader("Set-Cookie") is None,
                "E_HTTP",
                "network",
            )
            encoding = response.getheader("Content-Encoding")
            require(
                encoding is None or encoding.lower() == "identity",
                "E_ENCODING",
                "network",
            )
            require(
                response_header_bytes(headers) <= MAXIMUM_HEADER_BYTES,
                "E_HEADERS",
                "network",
            )
            lengths = [
                value
                for key, value in headers
                if key.lower() == "content-length"
            ]
            require(len(lengths) <= 1, "E_LENGTH", "network")
            declared = None
            if lengths:
                require(
                    re.fullmatch(r"0|[1-9][0-9]*", lengths[0]) is not None,
                    "E_LENGTH",
                    "network",
                )
                declared = int(lengths[0])
                require(declared <= maximum_bytes, "E_LIMIT", "network")
            chunks: list[bytes] = []
            total = 0
            while True:
                refresh_connection_timeout(connection, request_deadline)
                chunk = response.read(min(65_536, maximum_bytes + 1 - total))
                remaining_request_seconds(request_deadline)
                if not chunk:
                    break
                total += len(chunk)
                require(total <= maximum_bytes, "E_LIMIT", "network")
                chunks.append(chunk)
            raw = b"".join(chunks)
            require(
                declared is None or declared == len(raw),
                "E_LENGTH",
                "network",
            )
            return raw
        finally:
            response.close()
    except ResolverError:
        raise
    except (http.client.HTTPException, OSError, ssl.SSLError) as error:
        raise ResolverError("E_NETWORK", "network") from error
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            if connection is not None:
                connection.close()
        finally:
            signal.signal(signal.SIGALRM, previous_handler)
            if previous_timer[0] > 0:
                elapsed = time.monotonic() - request_started
                restored = max(previous_timer[0] - elapsed, 0.000001)
                signal.setitimer(
                    signal.ITIMER_REAL,
                    restored,
                    previous_timer[1],
                )


def write_all(fd: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(fd, raw[offset:])
        require(written > 0, "E_WRITE", "filesystem")
        offset += written


def exclusive_file(
    directory_fd: int,
    name: str,
    raw: bytes,
) -> dict[str, Any]:
    require(
        "/" not in name and name not in {"", ".", ".."},
        "E_PATH",
        "filesystem",
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        os.fchmod(fd, 0o600)
        write_all(fd, raw)
        os.fsync(fd)
        info = os.fstat(fd)
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size == len(raw),
            "E_WRITE",
            "filesystem",
        )
    finally:
        os.close(fd)
    return {
        "name": name,
        "bytes": len(raw),
        "rawSha256": sha256(raw),
    }


def create_claim(
    parent_fd: int,
    attempt_id: str,
    authority_binding: Mapping[str, Any],
) -> dict[str, Any]:
    claim_name = Path(PERMIT.CLAIM_PATH).name
    payload = canonical_bytes(
        {
            "claimType": (
                "aetherlink.sumdb-identity-resolution-one-use-claim"
            ),
            "attemptId": attempt_id,
            "permitPath": PERMIT.PERMIT_PATH,
            "authorityBinding": authority_binding,
            "rule": "claim_persists_after_any_network_attempt",
        }
    )
    result = exclusive_file(parent_fd, claim_name, payload)
    os.fsync(parent_fd)
    return result


def rename_exclusive(
    source_parent_fd: int,
    source_name: str,
    target_parent_fd: int,
    target_name: str,
) -> None:
    require(sys.platform == "darwin", "E_RENAME", "publication")
    libc = ctypes.CDLL(None, use_errno=True)
    renameatx = getattr(libc, "renameatx_np", None)
    require(renameatx is not None, "E_RENAME", "publication")
    renameatx.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameatx.restype = ctypes.c_int
    result = renameatx(
        source_parent_fd,
        source_name.encode(),
        target_parent_fd,
        target_name.encode(),
        RENAME_EXCL,
    )
    if result != 0:
        ctypes.get_errno()
        raise ResolverError("E_RENAME", "publication")


def write_terminal_at(
    root: Path,
    path: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    target = root / path
    parent_fd = os.open(
        target.parent,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        result = exclusive_file(parent_fd, target.name, canonical_bytes(payload))
        os.fsync(parent_fd)
        return result
    finally:
        os.close(parent_fd)


def write_terminal(path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return write_terminal_at(ROOT, path, payload)


def stable_read(path: Path, maximum_bytes: int) -> bytes:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= maximum_bytes,
            "E_HELD",
            "preflight",
        )
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_HELD", "preflight")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(fd, 1), "E_HELD", "preflight")
        after = os.fstat(fd)
        require(before == after, "E_HELD", "preflight")
        return b"".join(chunks)
    finally:
        os.close(fd)


def preflight() -> dict[str, Any]:
    expected, summary = PERMIT.evaluate(True)
    require(
        summary["validationPassed"] is True
        and summary["status"] == "authorized_not_consumed"
        and summary["claimExists"] is False
        and summary["sourceAcquisitionAuthorized"] is False
        and summary["externalAuthenticationRequired"] is False,
        "E_PERMIT",
        "preflight",
    )
    tool_bindings = {
        row["path"]: row["rawSha256"]
        for row in expected["toolBindings"]
    }
    permit_raw = stable_read(ROOT / PERMIT.PERMIT_PATH, 4 * 1024 * 1024)
    checker_raw = stable_read(PERMIT_CHECKER_PATH, 4 * 1024 * 1024)
    runner_raw = stable_read(Path(__file__), 4 * 1024 * 1024)
    require(
        tool_bindings.get(PERMIT.THIS_CHECKER_PATH) == sha256(checker_raw)
        and tool_bindings.get(PERMIT.RUNNER_PATH) == sha256(runner_raw)
        and sha256(permit_raw)
        == sha256(PERMIT.canonical_bytes(expected))
        and expected["contentBinding"]["sha256"]
        == summary.get("permitContentSha256", expected["contentBinding"]["sha256"]),
        "E_PERMIT",
        "preflight",
    )
    authority_binding = {
        "permit": {
            "path": PERMIT.PERMIT_PATH,
            "rawSha256": sha256(permit_raw),
            "contentSha256": expected["contentBinding"]["sha256"],
        },
        "checker": {
            "path": PERMIT.THIS_CHECKER_PATH,
            "rawSha256": sha256(checker_raw),
        },
        "runner": {
            "path": PERMIT.RUNNER_PATH,
            "rawSha256": sha256(runner_raw),
        },
    }
    return {
        "status": "preflight_passed_no_network_no_writes",
        "permitContentSha256": expected["contentBinding"]["sha256"],
        "authorityBinding": authority_binding,
        "networkRequestAttemptCount": 0,
        "fileWriteCount": 0,
        "sourceAcquisitionCount": 0,
    }


def check_deadline(deadline: float, phase: str) -> None:
    require(time.monotonic() < deadline, "E_DEADLINE", phase)


def _execute_attempt(
    fetch: Fetch,
    deadline: float,
    *,
    root: Path = ROOT,
    preflight_fn: Callable[[], dict[str, Any]] = preflight,
    rename_fn: Callable[[int, str, int, str], None] = rename_exclusive,
    terminal_writer: Callable[
        [str, Mapping[str, Any]], dict[str, Any]
    ]
    | None = None,
    parse_lookup_fn: Callable[[bytes], dict[str, Any]] = parse_lookup_response,
    derive_plan_fn: Callable[[int, int], dict[str, Any]] = derive_tile_plan,
    verify_bundle_fn: Callable[
        [Mapping[str, Any], Mapping[str, Any], Mapping[str, bytes]],
        dict[str, Any],
    ] = verify_proof_bundle,
    old_tree_size: int = OLD_TREE_SIZE,
    old_root: bytes = OLD_ROOT,
) -> dict[str, Any]:
    check_deadline(deadline, "preflight")
    preflight_result = preflight_fn()
    check_deadline(deadline, "preclaim")
    if terminal_writer is None:
        terminal_writer = lambda path, payload: write_terminal_at(
            root,
            path,
            payload,
        )
    parent_path = root / PERMIT.DEPENDENCY_ROOT
    parent_fd = os.open(
        parent_path,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    attempt_id = secrets.token_hex(16)
    staging_name = f"{PERMIT.STAGING_PREFIX}{attempt_id}"
    staging_path = parent_path / staging_name
    claim = None
    request_count = 0
    aggregate_bytes = 0
    published = False
    try:
        parent_info = os.fstat(parent_fd)
        require(
            stat.S_ISDIR(parent_info.st_mode)
            and parent_info.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(parent_info.st_mode) & 0o022 == 0,
            "E_NAMESPACE",
            "preclaim",
        )
        claim = create_claim(
            parent_fd,
            attempt_id,
            preflight_result["authorityBinding"],
        )
        os.mkdir(staging_name, 0o700, dir_fd=parent_fd)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            os.mkdir("evidence", 0o700, dir_fd=staging_fd)
            evidence_fd = os.open(
                "evidence",
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_CLOEXEC
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=staging_fd,
            )
            try:
                check_deadline(deadline, "lookup")
                request_count += 1
                lookup_raw = fetch(LOOKUP_URL, MAXIMUM_LOOKUP_BYTES, deadline)
                check_deadline(deadline, "lookup")
                aggregate_bytes += len(lookup_raw)
                require(
                    aggregate_bytes <= MAXIMUM_AGGREGATE_BYTES,
                    "E_LIMIT",
                    "lookup",
                )
                lookup_file = exclusive_file(
                    evidence_fd,
                    "lookup.response",
                    lookup_raw,
                )
                lookup = parse_lookup_fn(lookup_raw)
                require(
                    lookup["treeSize"] >= old_tree_size,
                    "E_ROLLBACK",
                    "lookup",
                )
                if lookup["treeSize"] == old_tree_size:
                    require(
                        lookup["root"] == old_root,
                        "E_EQUIVOCATION",
                        "lookup",
                    )
                plan = derive_plan_fn(
                    lookup["recordNumber"],
                    lookup["treeSize"],
                )
                check_deadline(deadline, "tile_plan")
                tile_bodies: dict[str, bytes] = {}
                tile_files = []
                for ordinal, tile in enumerate(plan["tiles"], 1):
                    check_deadline(deadline, "tiles")
                    require(
                        request_count < MAXIMUM_REQUEST_COUNT,
                        "E_LIMIT",
                        "tiles",
                    )
                    url = f"https://{LOOKUP_HOST}{tile['path']}"
                    request_count += 1
                    raw = fetch(url, tile["expectedBytes"], deadline)
                    check_deadline(deadline, "tiles")
                    aggregate_bytes += len(raw)
                    require(
                        len(raw) == tile["expectedBytes"]
                        and aggregate_bytes <= MAXIMUM_AGGREGATE_BYTES,
                        "E_TILE_BODY",
                        "tiles",
                    )
                    tile_bodies[tile["path"]] = raw
                    name = (
                        f"tile-{ordinal:03d}-"
                        f"{sha256(tile['path'].encode())[:16]}.bin"
                    )
                    file_result = exclusive_file(evidence_fd, name, raw)
                    tile_files.append(
                        {
                            **tile,
                            "requestOrdinal": ordinal + 1,
                            "url": url,
                            "file": file_result,
                        }
                    )
                proof = verify_bundle_fn(lookup, plan, tile_bodies)
                check_deadline(deadline, "proof_verify")
                evidence = PERMIT.content_bound(
                    {
                        "documentType": (
                            "aetherlink.sumdb-identity-resolution-evidence"
                        ),
                        "schemaVersion": "1.0",
                        "status": "locally_verified_pending_independent_readback",
                        "attemptId": attempt_id,
                        "authorityBinding": preflight_result[
                            "authorityBinding"
                        ],
                        "target": {
                            "module": TARGET_MODULE,
                            "version": TARGET_VERSION,
                            "goModH1": TARGET_MOD_H1,
                            "moduleZipH1": lookup["moduleZipH1"],
                        },
                        "lookup": {
                            "recordNumber": lookup["recordNumber"],
                            "treeSize": lookup["treeSize"],
                            "rootHashBase64": lookup["rootHashBase64"],
                            "signatureBase64": lookup["signatureBase64"],
                            "signedTreeTextSha256": (
                                lookup["signedTreeTextSha256"]
                            ),
                            "recordLeafHashBase64": base64.b64encode(
                                lookup["recordLeafHash"]
                            ).decode(),
                            "file": lookup_file,
                        },
                        "proof": proof,
                        "tiles": tile_files,
                        "counters": {
                            "networkRequestAttemptCount": request_count,
                            "lookupResponseCompletedCount": 1,
                            "signedHeadVerifiedCount": 1,
                            "derivedUniqueTileCount": len(plan["tiles"]),
                            "tileResponseCompletedCount": len(tile_bodies),
                            "recordInclusionVerifiedCount": 1,
                            "treeConsistencyVerifiedCount": 1,
                            "aggregateResponseBodyBytes": aggregate_bytes,
                        },
                        "boundary": {
                            "metadataOnly": True,
                            "sourceAcquired": False,
                            "sourceExtracted": False,
                            "sourceLoadedOrExecuted": False,
                            "externalAuthenticationRequired": False,
                            "userActionRequired": False,
                        },
                    }
                )
                evidence_file = exclusive_file(
                    evidence_fd,
                    "evidence.json",
                    canonical_bytes(evidence),
                )
                os.fsync(evidence_fd)
            finally:
                os.close(evidence_fd)
            os.fsync(staging_fd)
        finally:
            os.close(staging_fd)
        rename_fn(
            parent_fd,
            staging_name,
            parent_fd,
            Path(PERMIT.FINAL_ROOT).name,
        )
        published = True
        os.fsync(parent_fd)
        check_deadline(deadline, "publication")
        receipt = PERMIT.content_bound(
            {
                "documentType": (
                    "aetherlink.sumdb-identity-resolution-execution-receipt"
                ),
                "schemaVersion": "1.0",
                "status": "identity_resolved_pending_independent_readback",
                "attemptId": attempt_id,
                "claim": claim,
                "authorityBinding": preflight_result["authorityBinding"],
                "evidence": {
                    "directoryPath": PERMIT.FINAL_EVIDENCE_PATH,
                    "evidenceFile": evidence_file,
                    "resolvedModuleZipH1": lookup["moduleZipH1"],
                },
                "networkRequestAttemptCount": request_count,
                "aggregateResponseBodyBytes": aggregate_bytes,
                "sourceAcquired": False,
                "externalAuthenticationRequired": False,
                "userActionRequired": False,
                "nextAction": (
                    "run_separate_offline_identity_evidence_readback"
                ),
            }
        )
        receipt_result = terminal_writer(PERMIT.RECEIPT_PATH, receipt)
        manifest = PERMIT.content_bound(
            {
                "documentType": (
                    "aetherlink.sumdb-identity-resolution-manifest"
                ),
                "schemaVersion": "1.0",
                "status": (
                    "identity_resolution_publication_complete_"
                    "pending_independent_readback"
                ),
                "attemptId": attempt_id,
                "authorityBinding": preflight_result["authorityBinding"],
                "receipt": {
                    "path": PERMIT.RECEIPT_PATH,
                    "rawSha256": receipt_result["rawSha256"],
                },
                "evidenceDirectoryPath": PERMIT.FINAL_EVIDENCE_PATH,
                "manifestWrittenLast": True,
                "sourceAcquired": False,
            }
        )
        terminal_writer(PERMIT.MANIFEST_PATH, manifest)
        return {
            "status": manifest["status"],
            "attemptId": attempt_id,
            "networkRequestAttemptCount": request_count,
            "moduleZipH1Resolved": True,
            "sourceAcquired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    except BaseException as error:
        if claim is not None and not (root / PERMIT.RECEIPT_PATH).exists():
            code = error.code if isinstance(error, ResolverError) else "E_INTERNAL"
            phase = error.phase if isinstance(error, ResolverError) else "internal"
            failure = PERMIT.content_bound(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-failure"
                    ),
                    "schemaVersion": "1.0",
                    "status": "identity_resolution_failed_permit_consumed",
                    "attemptId": attempt_id,
                    "authorityBinding": preflight_result[
                        "authorityBinding"
                    ],
                    "failureCode": code,
                    "failurePhase": phase,
                    "claimRetained": True,
                    "stagingRetained": staging_path.exists() and not published,
                    "networkRequestAttemptCount": request_count,
                    "aggregateResponseBodyBytes": aggregate_bytes,
                    "sourceAcquired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
            try:
                terminal_writer(PERMIT.FAILURE_PATH, failure)
            except BaseException:
                pass
        if isinstance(error, ResolverError):
            raise
        raise ResolverError("E_INTERNAL", "internal") from error
    finally:
        os.close(parent_fd)


def execute(fetch: Fetch = direct_fetch) -> dict[str, Any]:
    previous_umask = os.umask(0o077)
    deadline = time.monotonic() + WHOLE_ATTEMPT_TIMEOUT_SECONDS

    def alarm_handler(signum: int, frame: Any) -> None:
        raise ResolverError("E_DEADLINE", "whole_attempt")

    previous_handler = signal.signal(signal.SIGALRM, alarm_handler)
    previous_timer = signal.setitimer(
        signal.ITIMER_REAL,
        WHOLE_ATTEMPT_TIMEOUT_SECONDS,
    )
    try:
        return _execute_attempt(fetch, deadline)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(
                signal.ITIMER_REAL,
                previous_timer[0],
                previous_timer[1],
            )
        os.umask(previous_umask)


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise ResolverError("E_ARGUMENT", "arguments")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        parser = CanonicalArgumentParser(add_help=False)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--preflight", action="store_true")
        mode.add_argument("--execute", action="store_true")
        args = parser.parse_args(argv)
        result = preflight() if args.preflight else execute()
        sys.stdout.buffer.write(canonical_bytes(result))
        return 0
    except ResolverError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-runner-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "failurePhase": error.phase,
                    "sourceAcquired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1
    except Exception:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-runner-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "failurePhase": "internal",
                    "sourceAcquired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
