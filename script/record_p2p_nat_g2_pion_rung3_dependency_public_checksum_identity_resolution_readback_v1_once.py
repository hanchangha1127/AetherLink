#!/usr/bin/env python3
"""Record one independent offline readback of frozen SumDB evidence."""

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
    raise RuntimeError("readback recorder requires `python3 -I -B -S`")

import argparse
import base64
import binascii
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time
import types
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
READBACK_CHECKER_PATH = Path(__file__).with_name(
    "check_p2p_nat_g2_pion_rung3_dependency_public_checksum_"
    "identity_resolution_readback_execution_permit_v1.py"
)
EXPECTED_READBACK_CHECKER_RAW = "7b741d232b4d0e64b5c6cffcc1fab2f2942b421089f8ddf117e9399b4f5a8bfa"
RENAME_EXCL = 0x00000004
MAXIMUM_JSON_BYTES = 4 * 1024 * 1024


class ReadbackError(RuntimeError):
    def __init__(self, code: str, phase: str) -> None:
        super().__init__(f"{code}:{phase}")
        self.code = code
        self.phase = phase


def require(value: bool, code: str, phase: str) -> None:
    if not value:
        raise ReadbackError(code, phase)


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


def content_bound(payload: Mapping[str, Any]) -> dict[str, Any]:
    require("contentBinding" not in payload, "E_CONTENT", "json")
    result = dict(payload)
    result["contentBinding"] = {
        "algorithm": "sha256(canonical-json-without-contentBinding)",
        "sha256": sha256(canonical_bytes(payload)),
    }
    return result


def strict_json(raw: bytes, phase: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "E_JSON", phase)
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(
                ReadbackError("E_JSON", phase)
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                ReadbackError("E_JSON", phase)
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReadbackError("E_JSON", phase) from error
    require(type(value) is dict, "E_JSON", phase)
    require(raw == canonical_bytes(value), "E_CANONICAL", phase)
    return value


def verify_content_binding(
    value: Mapping[str, Any],
    phase: str,
) -> None:
    binding = value.get("contentBinding")
    require(type(binding) is dict, "E_CONTENT", phase)
    unbound = dict(value)
    del unbound["contentBinding"]
    require(
        binding
        == {
            "algorithm": "sha256(canonical-json-without-contentBinding)",
            "sha256": sha256(canonical_bytes(unbound)),
        },
        "E_CONTENT",
        phase,
    )


def load_readback_checker() -> types.ModuleType:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(READBACK_CHECKER_PATH, flags)
    try:
        before = os.fstat(fd)
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) & 0o022 == 0
            and 0 < before.st_size <= MAXIMUM_JSON_BYTES,
            "E_CHECKER",
            "bootstrap",
        )
        raw = b""
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_CHECKER", "bootstrap")
            raw += chunk
            remaining -= len(chunk)
        require(
            not os.read(fd, 1)
            and os.fstat(fd) == before
            and sha256(raw) == EXPECTED_READBACK_CHECKER_RAW,
            "E_CHECKER",
            "bootstrap",
        )
    finally:
        os.close(fd)
    module = types.ModuleType("sumdb_identity_readback_permit_v1")
    module.__file__ = str(READBACK_CHECKER_PATH)
    module.__package__ = ""
    exec(compile(raw, str(READBACK_CHECKER_PATH), "exec"), module.__dict__)
    return module


PERMIT = load_readback_checker()


def decode_base64(value: str, expected: int, phase: str) -> bytes:
    require(type(value) is str, "E_BASE64", phase)
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ReadbackError("E_BASE64", phase) from error
    require(
        len(raw) == expected
        and base64.b64encode(raw).decode("ascii") == value,
        "E_BASE64",
        phase,
    )
    return raw


ED_Q = 2**255 - 19
ED_L = 2**252 + 27742317777372353535851937790883648493


def field_inverse(value: int) -> int:
    return pow(value, ED_Q - 2, ED_Q)


ED_D = (-121665 * field_inverse(121666)) % ED_Q
ED_I = pow(2, (ED_Q - 1) // 4, ED_Q)
Point = tuple[int, int]
IDENTITY: Point = (0, 1)


def recover_x(y: int) -> int:
    numerator = (y * y - 1) % ED_Q
    denominator = (ED_D * y * y + 1) % ED_Q
    require(denominator != 0, "E_SIGNATURE", "signed_note")
    xx = numerator * field_inverse(denominator) % ED_Q
    x = pow(xx, (ED_Q + 3) // 8, ED_Q)
    if (x * x - xx) % ED_Q:
        x = x * ED_I % ED_Q
    require((x * x - xx) % ED_Q == 0, "E_SIGNATURE", "signed_note")
    return ED_Q - x if x & 1 else x


def point_add(left: Point, right: Point) -> Point:
    x1, y1 = left
    x2, y2 = right
    product = ED_D * x1 * x2 * y1 * y2 % ED_Q
    dx = (1 + product) % ED_Q
    dy = (1 - product) % ED_Q
    require(dx != 0 and dy != 0, "E_SIGNATURE", "signed_note")
    return (
        (x1 * y2 + x2 * y1) * field_inverse(dx) % ED_Q,
        (y1 * y2 + x1 * x2) * field_inverse(dy) % ED_Q,
    )


def scalar_multiply(scalar: int, point: Point) -> Point:
    result = IDENTITY
    current = point
    while scalar:
        if scalar & 1:
            result = point_add(result, current)
        current = point_add(current, current)
        scalar >>= 1
    return result


BASE_Y = 4 * field_inverse(5) % ED_Q
BASE_POINT: Point = (recover_x(BASE_Y), BASE_Y)


def encode_point(point: Point) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def decode_point(raw: bytes) -> Point:
    require(len(raw) == 32, "E_SIGNATURE", "signed_note")
    packed = int.from_bytes(raw, "little")
    sign = packed >> 255
    y = packed & ((1 << 255) - 1)
    require(y < ED_Q, "E_SIGNATURE", "signed_note")
    x = recover_x(y)
    if (x & 1) != sign:
        x = ED_Q - x
    require(not (x == 0 and sign == 1), "E_SIGNATURE", "signed_note")
    point = (x, y)
    require(
        encode_point(point) == raw
        and point != IDENTITY
        and scalar_multiply(ED_L, point) == IDENTITY
        and scalar_multiply(8, point) != IDENTITY,
        "E_SIGNATURE",
        "signed_note",
    )
    return point


def verify_ed25519_signature(
    public_key: bytes,
    message: bytes,
    signature: bytes,
) -> None:
    require(
        len(public_key) == 32 and len(signature) == 64,
        "E_SIGNATURE",
        "signed_note",
    )
    encoded_r = signature[:32]
    scalar_s = int.from_bytes(signature[32:], "little")
    require(scalar_s < ED_L, "E_SIGNATURE", "signed_note")
    point_r = decode_point(encoded_r)
    point_a = decode_point(public_key)
    challenge = int.from_bytes(
        hashlib.sha512(encoded_r + public_key + message).digest(),
        "little",
    ) % ED_L
    require(
        scalar_multiply(scalar_s, BASE_POINT)
        == point_add(point_r, scalar_multiply(challenge, point_a)),
        "E_SIGNATURE",
        "signed_note",
    )


def verifier_material() -> tuple[bytes, bytes]:
    match = re.fullmatch(
        r"([^+]+)[+]([0-9a-f]{8})[+](.+)",
        PERMIT.SUMDB_VERIFIER_KEY,
    )
    require(match is not None, "E_KEY", "signed_note")
    name, key_hash_text, payload_text = match.groups()
    payload = decode_base64(payload_text, 33, "signed_note")
    require(payload[0] == 1, "E_KEY", "signed_note")
    key_hash = hashlib.sha256(
        name.encode() + b"\n" + payload
    ).digest()[:4]
    require(key_hash.hex() == key_hash_text, "E_KEY", "signed_note")
    return payload[1:], key_hash


def verify_signed_tree_note(note_raw: bytes) -> dict[str, Any]:
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
    message, tail = note_raw.split(delimiter)
    require(tail.endswith(b"\n") and b"\n" not in tail[:-1], "E_NOTE", phase)
    try:
        lines = message.decode("ascii", errors="strict").split("\n")
        signature_text = tail[:-1].decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise ReadbackError("E_NOTE", phase) from error
    require(
        len(lines) == 3
        and lines[0] == "go.sum database tree"
        and re.fullmatch(r"[1-9][0-9]*", lines[1]) is not None,
        "E_NOTE",
        phase,
    )
    tree_size = int(lines[1])
    require(tree_size <= 2**62, "E_NOTE", phase)
    root = decode_base64(lines[2], 32, phase)
    signature = decode_base64(signature_text, 68, phase)
    public_key, key_hash = verifier_material()
    require(signature[:4] == key_hash, "E_SIGNATURE", phase)
    signed_text = message + b"\n"
    verify_ed25519_signature(public_key, signed_text, signature[4:])
    return {
        "treeSize": tree_size,
        "root": root,
        "rootHashBase64": lines[2],
        "signatureBase64": signature_text,
        "signedTreeTextSha256": sha256(signed_text),
    }


def parse_lookup_record(raw: bytes) -> dict[str, Any]:
    phase = "lookup"
    require(
        0 < len(raw) <= 65_536
        and raw.endswith(b"\n")
        and b"\r" not in raw
        and b"\x00" not in raw,
        "E_LOOKUP",
        phase,
    )
    separator = raw.find(b"\n\n")
    require(separator > 0, "E_LOOKUP", phase)
    header = raw[:separator]
    note_raw = raw[separator + 2 :]
    try:
        lines = header.decode("utf-8", errors="strict").split("\n")
    except UnicodeDecodeError as error:
        raise ReadbackError("E_RECORD", phase) from error
    require(len(lines) == 3, "E_RECORD", phase)
    number_text, zip_line, mod_line = lines
    require(
        re.fullmatch(r"0|[1-9][0-9]*", number_text) is not None,
        "E_RECORD",
        phase,
    )
    zip_prefix = f"{PERMIT.TARGET_MODULE} {PERMIT.TARGET_VERSION} "
    require(
        zip_line.startswith(zip_prefix) and zip_line.count(" ") == 2,
        "E_RECORD",
        phase,
    )
    zip_h1 = zip_line[len(zip_prefix) :]
    require(
        zip_h1 == PERMIT.TARGET_ZIP_H1
        and zip_h1.startswith("h1:"),
        "E_H1",
        phase,
    )
    decode_base64(zip_h1[3:], 32, phase)
    require(
        mod_line
        == (
            f"{PERMIT.TARGET_MODULE} {PERMIT.TARGET_VERSION}/go.mod "
            f"{PERMIT.TARGET_MOD_H1}"
        ),
        "E_RECORD",
        phase,
    )
    record_number = int(number_text)
    note = verify_signed_tree_note(note_raw)
    require(0 <= record_number < note["treeSize"], "E_RECORD", phase)
    payload = (zip_line + "\n" + mod_line + "\n").encode()
    return {
        "recordNumber": record_number,
        "recordPayload": payload,
        "recordLeafHash": hashlib.sha256(b"\x00" + payload).digest(),
        "moduleZipH1": zip_h1,
        "goModH1": PERMIT.TARGET_MOD_H1,
        **note,
    }


Span = tuple[int, int]


def power_two_before(value: int) -> int:
    require(value > 1, "E_TREE", "proof_plan")
    return 1 << ((value - 1).bit_length() - 1)


def inclusion_spans(index: int, start: int, count: int) -> list[Span]:
    require(
        count > 0 and start <= index < start + count,
        "E_TREE",
        "inclusion_plan",
    )
    if count == 1:
        return []
    split = power_two_before(count)
    if index < start + split:
        return inclusion_spans(index, start, split) + [
            (start + split, count - split)
        ]
    return inclusion_spans(index, start + split, count - split) + [
        (start, split)
    ]


def consistency_spans(old_size: int, new_size: int) -> list[Span]:
    require(0 < old_size <= new_size, "E_TREE", "consistency_plan")

    def walk(old: int, new: int, start: int, complete: bool) -> list[Span]:
        if old == new:
            return [] if complete else [(start, new)]
        split = power_two_before(new)
        if old <= split:
            return walk(old, split, start, complete) + [
                (start + split, new - split)
            ]
        return walk(old - split, new - split, start + split, False) + [
            (start, split)
        ]

    return walk(old_size, new_size, 0, True)


def perfect_nodes(start: int, count: int) -> list[tuple[int, int]]:
    require(start >= 0 and count > 0, "E_TREE", "proof_plan")
    if count & (count - 1) == 0 and start % count == 0:
        return [(count.bit_length() - 1, start // count)]
    split = power_two_before(count)
    return perfect_nodes(start, split) + perfect_nodes(
        start + split,
        count - split,
    )


def encode_tile_index(index: int) -> str:
    require(index >= 0, "E_TILE_PATH", "tile_plan")
    parts = [f"{index % 1000:03d}"]
    index //= 1000
    while index:
        parts.append(f"x{index % 1000:03d}")
        index //= 1000
    return "/".join(reversed(parts))


def tile_for_node(level: int, index: int, tree_size: int) -> dict[str, Any]:
    tile_level = level // 8
    residual = level % 8
    base_start = index << residual
    base_count = tree_size >> (tile_level * 8)
    hash_count = 1 << residual
    require(base_start + hash_count <= base_count, "E_TILE", "tile_plan")
    tile_index = base_start // 256
    offset = base_start % 256
    width = min(256, base_count - tile_index * 256)
    require(
        1 <= width <= 256 and offset + hash_count <= width,
        "E_TILE",
        "tile_plan",
    )
    path = f"/tile/8/{tile_level}/{encode_tile_index(tile_index)}"
    if width < 256:
        path += f".p/{width}"
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


def derive_independent_plan(
    record_number: int,
    tree_size: int,
) -> dict[str, Any]:
    inclusion = inclusion_spans(record_number, 0, tree_size)
    consistency = consistency_spans(PERMIT.OLD_TREE_SIZE, tree_size)
    nodes = {
        node
        for span in (*inclusion, *consistency)
        for node in perfect_nodes(*span)
    }
    specs = {
        node: tile_for_node(*node, tree_size)
        for node in sorted(nodes)
    }
    paths: dict[str, dict[str, Any]] = {}
    for spec in specs.values():
        row = {
            key: spec[key]
            for key in (
                "path",
                "tileLevel",
                "tileIndex",
                "width",
                "expectedBytes",
            )
        }
        prior = paths.setdefault(spec["path"], row)
        require(prior == row, "E_TILE", "tile_plan")
    tiles = sorted(
        paths.values(),
        key=lambda row: (
            row["tileLevel"],
            row["tileIndex"],
            row["width"],
        ),
    )
    require(len(tiles) <= 128, "E_TILE", "tile_plan")
    return {
        "inclusionSpans": inclusion,
        "consistencySpans": consistency,
        "nodeSpecs": specs,
        "tiles": tiles,
    }


def node_hash(left: bytes, right: bytes) -> bytes:
    require(
        len(left) == len(right) == 32,
        "E_PROOF",
        "proof_verify",
    )
    return hashlib.sha256(b"\x01" + left + right).digest()


def node_from_tile(
    node: tuple[int, int],
    specs: Mapping[tuple[int, int], Mapping[str, Any]],
    bodies: Mapping[str, bytes],
) -> bytes:
    require(node in specs, "E_PROOF", "proof_verify")
    spec = specs[node]
    raw = bodies.get(spec["path"])
    require(
        raw is not None and len(raw) == spec["expectedBytes"],
        "E_TILE_BODY",
        "proof_verify",
    )
    values = [
        raw[offset : offset + 32]
        for offset in range(0, len(raw), 32)
    ][spec["offset"] : spec["offset"] + spec["hashCount"]]
    require(
        len(values) == spec["hashCount"],
        "E_PROOF",
        "proof_verify",
    )
    while len(values) > 1:
        require(len(values) % 2 == 0, "E_PROOF", "proof_verify")
        values = [
            node_hash(values[i], values[i + 1])
            for i in range(0, len(values), 2)
        ]
    return values[0]


def span_hash(
    span: Span,
    specs: Mapping[tuple[int, int], Mapping[str, Any]],
    bodies: Mapping[str, bytes],
) -> bytes:
    start, count = span
    if count & (count - 1) == 0 and start % count == 0:
        return node_from_tile(
            (count.bit_length() - 1, start // count),
            specs,
            bodies,
        )
    split = power_two_before(count)
    return node_hash(
        span_hash((start, split), specs, bodies),
        span_hash((start + split, count - split), specs, bodies),
    )


def verify_inclusion_path(
    leaf_hash: bytes,
    index: int,
    tree_size: int,
    proof: Sequence[bytes],
    root: bytes,
) -> None:
    require(
        len(leaf_hash) == len(root) == 32
        and 0 <= index < tree_size,
        "E_INCLUSION",
        "proof_verify",
    )
    fn = index
    sn = tree_size - 1
    candidate = leaf_hash
    for sibling in proof:
        require(len(sibling) == 32 and sn > 0, "E_INCLUSION", "proof_verify")
        if fn & 1 or fn == sn:
            candidate = node_hash(sibling, candidate)
            while fn and not (fn & 1):
                fn >>= 1
                sn >>= 1
        else:
            candidate = node_hash(candidate, sibling)
        fn >>= 1
        sn >>= 1
    require(sn == 0 and candidate == root, "E_INCLUSION", "proof_verify")


def verify_consistency_path(
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
        require(not proof and old_root == new_root, "E_CONSISTENCY", phase)
        return
    require(bool(proof), "E_CONSISTENCY", phase)
    fn = old_size - 1
    sn = new_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    position = 0
    if old_size & (old_size - 1) == 0:
        seed = old_root
    else:
        seed = proof[0]
        position = 1
    old_candidate = seed
    new_candidate = seed
    for sibling in proof[position:]:
        require(sn != 0, "E_CONSISTENCY", phase)
        if fn & 1 or fn == sn:
            old_candidate = node_hash(sibling, old_candidate)
            new_candidate = node_hash(sibling, new_candidate)
            while fn and not (fn & 1):
                fn >>= 1
                sn >>= 1
        else:
            new_candidate = node_hash(new_candidate, sibling)
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


class SnapshotFile:
    def __init__(self, expected: Mapping[str, Any]) -> None:
        self.expected = expected
        self.path = ROOT / expected["path"]
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        self.fd = os.open(self.path, flags)
        self.before = os.fstat(self.fd)
        require(
            stat.S_ISREG(self.before.st_mode)
            and self.before.st_nlink == expected["linkCount"]
            and self.before.st_uid == expected["ownerUid"]
            and f"{stat.S_IMODE(self.before.st_mode):04o}"
            == expected["mode"]
            and self.before.st_size == expected["bytes"],
            "E_FROZEN",
            "snapshot",
        )
        chunks: list[bytes] = []
        remaining = self.before.st_size
        while remaining:
            chunk = os.read(self.fd, min(65_536, remaining))
            require(bool(chunk), "E_READ", "snapshot")
            chunks.append(chunk)
            remaining -= len(chunk)
        require(not os.read(self.fd, 1), "E_READ", "snapshot")
        self.raw = b"".join(chunks)
        require(
            sha256(self.raw) == expected["rawSha256"],
            "E_FROZEN",
            "snapshot",
        )
        self.check()

    def check(self) -> None:
        require(os.fstat(self.fd) == self.before, "E_CHANGED", "snapshot")

    def close(self) -> None:
        os.close(self.fd)


class FrozenSnapshot:
    def __init__(self) -> None:
        self.files: dict[str, SnapshotFile] = {}
        self.evidence_fd = -1
        try:
            for expected in PERMIT.ALL_FROZEN_FILES:
                item = SnapshotFile(expected)
                self.files[expected["path"]] = item
            self.evidence_fd = os.open(
                ROOT / PERMIT.EVIDENCE_DIRECTORY_PATH,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_CLOEXEC
                | getattr(os, "O_NOFOLLOW", 0),
            )
            self.evidence_before = os.fstat(self.evidence_fd)
            expected_dir = PERMIT.EVIDENCE_DIRECTORY
            require(
                stat.S_ISDIR(self.evidence_before.st_mode)
                and self.evidence_before.st_uid == expected_dir["ownerUid"]
                and self.evidence_before.st_nlink == expected_dir["linkCount"]
                and f"{stat.S_IMODE(self.evidence_before.st_mode):04o}"
                == expected_dir["mode"],
                "E_INVENTORY",
                "snapshot",
            )
            self.expected_names = {
                Path(row["path"]).name for row in PERMIT.EVIDENCE_FILES
            }
            require(
                set(os.listdir(self.evidence_fd)) == self.expected_names,
                "E_INVENTORY",
                "snapshot",
            )
        except BaseException:
            self.close()
            raise

    def raw(self, path: str) -> bytes:
        require(path in self.files, "E_FROZEN", "snapshot")
        return self.files[path].raw

    def final_barrier(self) -> None:
        for item in self.files.values():
            item.check()
        require(
            os.fstat(self.evidence_fd) == self.evidence_before
            and set(os.listdir(self.evidence_fd)) == self.expected_names,
            "E_CHANGED",
            "snapshot",
        )

    def close(self) -> None:
        for item in getattr(self, "files", {}).values():
            try:
                item.close()
            except BaseException:
                pass
        if getattr(self, "evidence_fd", -1) >= 0:
            try:
                os.close(self.evidence_fd)
            except BaseException:
                pass


def execution_authority_binding() -> dict[str, Any]:
    rows = {row["path"]: row for row in PERMIT.EXECUTION_AUTHORITY}
    permit = PERMIT.EXECUTION_AUTHORITY[0]
    checker = PERMIT.EXECUTION_AUTHORITY[1]
    runner = PERMIT.EXECUTION_AUTHORITY[2]
    require(len(rows) == 3, "E_AUTHORITY", "snapshot")
    return {
        "permit": {
            "path": permit["path"],
            "rawSha256": permit["rawSha256"],
            "contentSha256": (
                "41f2050c3e8a702da66adfdf5c890604756c7fa0e708d4b9fb062c8f5693a7fb"
            ),
        },
        "checker": {
            "path": checker["path"],
            "rawSha256": checker["rawSha256"],
        },
        "runner": {
            "path": runner["path"],
            "rawSha256": runner["rawSha256"],
        },
    }


def expected_file_result(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": Path(row["path"]).name,
        "bytes": row["bytes"],
        "rawSha256": row["rawSha256"],
    }


def verify_snapshot(snapshot: FrozenSnapshot) -> dict[str, Any]:
    phase = "snapshot"
    authority = execution_authority_binding()
    execution_permit = strict_json(
        snapshot.raw(PERMIT.EXECUTION_AUTHORITY[0]["path"]),
        phase,
    )
    verify_content_binding(execution_permit, phase)
    require(
        execution_permit["contentBinding"]["sha256"]
        == "41f2050c3e8a702da66adfdf5c890604756c7fa0e708d4b9fb062c8f5693a7fb",
        "E_AUTHORITY",
        phase,
    )
    claim = strict_json(snapshot.raw(PERMIT.EXECUTION_CLAIM["path"]), phase)
    require(
        claim
        == {
            "attemptId": PERMIT.ATTEMPT_ID,
            "authorityBinding": authority,
            "claimType": "aetherlink.sumdb-identity-resolution-one-use-claim",
            "permitPath": PERMIT.EXECUTION_AUTHORITY[0]["path"],
            "rule": "claim_persists_after_any_network_attempt",
        },
        "E_CLAIM",
        phase,
    )
    evidence = strict_json(
        snapshot.raw(f"{PERMIT.EVIDENCE_DIRECTORY_PATH}/evidence.json"),
        phase,
    )
    verify_content_binding(evidence, phase)
    lookup_raw = snapshot.raw(
        f"{PERMIT.EVIDENCE_DIRECTORY_PATH}/lookup.response"
    )
    lookup = parse_lookup_record(lookup_raw)
    require(
        lookup["treeSize"] >= PERMIT.OLD_TREE_SIZE,
        "E_ROLLBACK",
        phase,
    )
    plan = derive_independent_plan(
        lookup["recordNumber"],
        lookup["treeSize"],
    )
    observed_tiles = evidence.get("tiles")
    require(type(observed_tiles) is list, "E_TILE", phase)
    require(len(observed_tiles) == len(plan["tiles"]) == 9, "E_TILE", phase)
    tile_bodies: dict[str, bytes] = {}
    expected_tile_rows: list[dict[str, Any]] = []
    evidence_by_name = {
        Path(row["path"]).name: row
        for row in PERMIT.EVIDENCE_FILES
    }
    for ordinal, (planned, observed) in enumerate(
        zip(plan["tiles"], observed_tiles),
        1,
    ):
        require(type(observed) is dict, "E_TILE", phase)
        name = f"tile-{ordinal:03d}-{sha256(planned['path'].encode())[:16]}.bin"
        require(name in evidence_by_name, "E_TILE", phase)
        frozen_row = evidence_by_name[name]
        raw = snapshot.raw(frozen_row["path"])
        require(
            len(raw) == planned["expectedBytes"] == frozen_row["bytes"]
            and sha256(raw) == frozen_row["rawSha256"],
            "E_TILE_BODY",
            phase,
        )
        tile_bodies[planned["path"]] = raw
        expected_tile_rows.append(
            {
                **planned,
                "requestOrdinal": ordinal + 1,
                "url": f"https://sum.golang.org{planned['path']}",
                "file": expected_file_result(frozen_row),
            }
        )
    inclusion = [
        span_hash(span, plan["nodeSpecs"], tile_bodies)
        for span in plan["inclusionSpans"]
    ]
    consistency = [
        span_hash(span, plan["nodeSpecs"], tile_bodies)
        for span in plan["consistencySpans"]
    ]
    verify_inclusion_path(
        lookup["recordLeafHash"],
        lookup["recordNumber"],
        lookup["treeSize"],
        inclusion,
        lookup["root"],
    )
    old_root = decode_base64(
        PERMIT.OLD_ROOT_HASH_BASE64,
        32,
        phase,
    )
    verify_consistency_path(
        PERMIT.OLD_TREE_SIZE,
        lookup["treeSize"],
        old_root,
        lookup["root"],
        consistency,
    )
    inclusion_b64 = [base64.b64encode(item).decode() for item in inclusion]
    consistency_b64 = [base64.b64encode(item).decode() for item in consistency]
    proof = {
        "inclusionProofHashCount": len(inclusion),
        "consistencyProofHashCount": len(consistency),
        "inclusionProofHashesBase64": inclusion_b64,
        "consistencyProofHashesBase64": consistency_b64,
        "canonicalProofBundleSha256": sha256(
            canonical_bytes(
                {
                    "consistencyProofHashesBase64": consistency_b64,
                    "inclusionProofHashesBase64": inclusion_b64,
                }
            )
        ),
        "recordInclusionVerified": True,
        "oldToNewConsistencyVerified": True,
    }
    aggregate = len(lookup_raw) + sum(len(raw) for raw in tile_bodies.values())
    expected_evidence = content_bound(
        {
            "documentType": "aetherlink.sumdb-identity-resolution-evidence",
            "schemaVersion": "1.0",
            "status": "locally_verified_pending_independent_readback",
            "attemptId": PERMIT.ATTEMPT_ID,
            "authorityBinding": authority,
            "target": {
                "module": PERMIT.TARGET_MODULE,
                "version": PERMIT.TARGET_VERSION,
                "goModH1": PERMIT.TARGET_MOD_H1,
                "moduleZipH1": PERMIT.TARGET_ZIP_H1,
            },
            "lookup": {
                "recordNumber": lookup["recordNumber"],
                "treeSize": lookup["treeSize"],
                "rootHashBase64": lookup["rootHashBase64"],
                "signatureBase64": lookup["signatureBase64"],
                "signedTreeTextSha256": lookup["signedTreeTextSha256"],
                "recordLeafHashBase64": base64.b64encode(
                    lookup["recordLeafHash"]
                ).decode(),
                "file": expected_file_result(
                    evidence_by_name["lookup.response"]
                ),
            },
            "proof": proof,
            "tiles": expected_tile_rows,
            "counters": {
                "networkRequestAttemptCount": 1 + len(plan["tiles"]),
                "lookupResponseCompletedCount": 1,
                "signedHeadVerifiedCount": 1,
                "derivedUniqueTileCount": len(plan["tiles"]),
                "tileResponseCompletedCount": len(tile_bodies),
                "recordInclusionVerifiedCount": 1,
                "treeConsistencyVerifiedCount": 1,
                "aggregateResponseBodyBytes": aggregate,
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
    require(evidence == expected_evidence, "E_EVIDENCE", phase)
    receipt = strict_json(
        snapshot.raw(PERMIT.EXECUTION_RECEIPT["path"]),
        phase,
    )
    verify_content_binding(receipt, phase)
    expected_receipt = content_bound(
        {
            "documentType": (
                "aetherlink.sumdb-identity-resolution-execution-receipt"
            ),
            "schemaVersion": "1.0",
            "status": "identity_resolved_pending_independent_readback",
            "attemptId": PERMIT.ATTEMPT_ID,
            "claim": expected_file_result(PERMIT.EXECUTION_CLAIM),
            "authorityBinding": authority,
            "evidence": {
                "directoryPath": PERMIT.EVIDENCE_DIRECTORY_PATH,
                "evidenceFile": expected_file_result(
                    evidence_by_name["evidence.json"]
                ),
                "resolvedModuleZipH1": PERMIT.TARGET_ZIP_H1,
            },
            "networkRequestAttemptCount": 1 + len(plan["tiles"]),
            "aggregateResponseBodyBytes": aggregate,
            "sourceAcquired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
            "nextAction": "run_separate_offline_identity_evidence_readback",
        }
    )
    require(receipt == expected_receipt, "E_RECEIPT", phase)
    manifest = strict_json(
        snapshot.raw(PERMIT.EXECUTION_MANIFEST["path"]),
        phase,
    )
    verify_content_binding(manifest, phase)
    expected_manifest = content_bound(
        {
            "documentType": "aetherlink.sumdb-identity-resolution-manifest",
            "schemaVersion": "1.0",
            "status": (
                "identity_resolution_publication_complete_"
                "pending_independent_readback"
            ),
            "attemptId": PERMIT.ATTEMPT_ID,
            "authorityBinding": authority,
            "receipt": {
                "path": PERMIT.EXECUTION_RECEIPT["path"],
                "rawSha256": PERMIT.EXECUTION_RECEIPT["rawSha256"],
            },
            "evidenceDirectoryPath": PERMIT.EVIDENCE_DIRECTORY_PATH,
            "manifestWrittenLast": True,
            "sourceAcquired": False,
        }
    )
    require(manifest == expected_manifest, "E_MANIFEST", phase)
    execution_failure = (
        ROOT
        / PERMIT.BASE
        / "bounded-dependency-public-checksum-identity-resolution-failure-v1.json"
    )
    require(not execution_failure.exists(), "E_TERMINAL", phase)
    snapshot.final_barrier()
    return {
        "executionAttemptId": PERMIT.ATTEMPT_ID,
        "executionAuthorityBinding": authority,
        "resolvedModuleZipH1": PERMIT.TARGET_ZIP_H1,
        "recordNumber": lookup["recordNumber"],
        "treeSize": lookup["treeSize"],
        "rootHashBase64": lookup["rootHashBase64"],
        "evidenceFileCount": len(PERMIT.EVIDENCE_FILES),
        "tileFileCount": len(plan["tiles"]),
        "aggregateResponseBodyBytes": aggregate,
        "inclusionProofHashCount": len(inclusion),
        "consistencyProofHashCount": len(consistency),
        "canonicalProofBundleSha256": proof[
            "canonicalProofBundleSha256"
        ],
        "frozenSnapshotAggregateSha256": sha256(
            canonical_bytes(PERMIT.ALL_FROZEN_FILES)
        ),
    }


def stable_package_read(path: Path) -> bytes:
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
            and 0 < before.st_size <= MAXIMUM_JSON_BYTES,
            "E_PACKAGE",
            "preflight",
        )
        raw = b""
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65_536, remaining))
            require(bool(chunk), "E_PACKAGE", "preflight")
            raw += chunk
            remaining -= len(chunk)
        require(
            not os.read(fd, 1) and os.fstat(fd) == before,
            "E_PACKAGE",
            "preflight",
        )
        return raw
    finally:
        os.close(fd)


def preflight() -> dict[str, Any]:
    try:
        package_paths = (
            PERMIT.READER_PATH,
            PERMIT.THIS_CHECKER_PATH,
            PERMIT.THIS_TESTS_PATH,
            PERMIT.RECORDER_PATH,
            PERMIT.RECORDER_TESTS_PATH,
        )
        package_raw = {
            path: stable_package_read(ROOT / path)
            for path in package_paths
        }
        permit_raw = stable_package_read(ROOT / PERMIT.PERMIT_PATH)
        expected = PERMIT.content_bound(
            PERMIT.expected_payload_from_package(package_raw)
        )
        PERMIT.verify_bound_bytes(permit_raw, expected)
    except Exception as error:
        raise ReadbackError("E_PERMIT", "preflight") from error
    checker_raw = package_raw[PERMIT.THIS_CHECKER_PATH]
    recorder_raw = package_raw[PERMIT.RECORDER_PATH]
    bindings = {
        row["path"]: row["rawSha256"] for row in expected["toolBindings"]
    }
    namespace_absent = all(
        not os.path.lexists(ROOT / path)
        for path in (
            PERMIT.READBACK_CLAIM_PATH,
            PERMIT.READBACK_RECEIPT_PATH,
            PERMIT.READBACK_MANIFEST_PATH,
        )
    )
    require(
        sha256(permit_raw) == sha256(PERMIT.canonical_bytes(expected))
        and sha256(checker_raw) == EXPECTED_READBACK_CHECKER_RAW
        and bindings.get(PERMIT.THIS_CHECKER_PATH) == sha256(checker_raw)
        and bindings.get(PERMIT.RECORDER_PATH) == sha256(recorder_raw)
        and expected["executionBoundary"]["networkAuthorized"] is False
        and expected["executionBoundary"][
            "externalAuthenticationRequired"
        ]
        is False
        and expected["executionBoundary"]["userActionRequired"] is False
        and expected["executionBoundary"]["sourceAcquisitionAuthorized"]
        is False
        and namespace_absent,
        "E_PERMIT",
        "preflight",
    )
    return {
        "status": "preflight_passed_no_network_no_writes",
        "executionAttemptId": PERMIT.ATTEMPT_ID,
        "frozenEvidenceFileCount": 11,
        "authorityBinding": {
            "permit": {
                "path": PERMIT.PERMIT_PATH,
                "rawSha256": sha256(permit_raw),
                "contentSha256": expected["contentBinding"]["sha256"],
            },
            "checker": {
                "path": PERMIT.THIS_CHECKER_PATH,
                "rawSha256": sha256(checker_raw),
            },
            "recorder": {
                "path": PERMIT.RECORDER_PATH,
                "rawSha256": sha256(recorder_raw),
            },
        },
        "networkRequestAttemptCount": 0,
        "fileWriteCount": 0,
        "sourceAcquisitionCount": 0,
        "externalAuthenticationRequired": False,
        "userActionRequired": False,
    }


def write_all(fd: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(fd, raw[offset:])
        require(written > 0, "E_WRITE", "publication")
        offset += written


def create_readback_claim(
    root: Path,
    readback_attempt_id: str,
    authority_binding: Mapping[str, Any],
) -> dict[str, Any]:
    target = root / PERMIT.READBACK_CLAIM_PATH
    parent_fd = os.open(
        target.parent,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    raw = canonical_bytes(
        content_bound(
            {
                "documentType": (
                    "aetherlink.sumdb-identity-resolution-readback-one-use-claim"
                ),
                "schemaVersion": "1.0",
                "readbackAttemptId": readback_attempt_id,
                "executionAttemptId": PERMIT.ATTEMPT_ID,
                "authorityBinding": authority_binding,
                "rule": "claim_persists_after_success_failure_or_uncertainty",
            }
        )
    )
    try:
        fd = os.open(
            target.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
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
                "E_CLAIM",
                "claim",
            )
        finally:
            os.close(fd)
        os.fsync(parent_fd)
        return {
            "path": PERMIT.READBACK_CLAIM_PATH,
            "bytes": len(raw),
            "rawSha256": sha256(raw),
            "mode": "0600",
        }
    except FileExistsError as error:
        raise ReadbackError("E_CONSUMED", "claim") from error
    finally:
        os.close(parent_fd)


def rename_no_replace(
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
    require(result == 0, "E_RENAME", "publication")


def atomic_publish(
    root: Path,
    path: str,
    payload: Mapping[str, Any],
    rename_fn: Callable[[int, str, int, str], None] = rename_no_replace,
) -> dict[str, Any]:
    target = root / path
    parent_fd = os.open(
        target.parent,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    temporary = f".{target.name}.tmp-{secrets.token_hex(16)}"
    raw = canonical_bytes(payload)
    created = False
    try:
        require(not target.exists(), "E_OUTPUT", "publication")
        fd = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
        created = True
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
                "publication",
            )
        finally:
            os.close(fd)
        rename_fn(parent_fd, temporary, parent_fd, target.name)
        created = False
        os.fsync(parent_fd)
        return {
            "path": path,
            "bytes": len(raw),
            "rawSha256": sha256(raw),
            "mode": "0600",
        }
    finally:
        if created:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except OSError:
                pass
        os.close(parent_fd)


def execute() -> dict[str, Any]:
    previous_umask = os.umask(0o077)
    try:
        preflight_result = preflight()
        readback_attempt_id = secrets.token_hex(16)
        claim = create_readback_claim(
            ROOT,
            readback_attempt_id,
            preflight_result["authorityBinding"],
        )
        snapshot = FrozenSnapshot()
        try:
            verified = verify_snapshot(snapshot)
            snapshot.final_barrier()
            receipt = content_bound(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-readback"
                    ),
                    "schemaVersion": "1.0",
                    "status": "identity_resolution_independently_read_back",
                    "readbackAttemptId": readback_attempt_id,
                    "executionAttemptId": PERMIT.ATTEMPT_ID,
                    "authorityBinding": preflight_result[
                        "authorityBinding"
                    ],
                    "readbackClaim": claim,
                    "verified": verified,
                    "offline": True,
                    "networkRequestAttemptCount": 0,
                    "sourceAcquired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
            receipt_result = atomic_publish(
                ROOT,
                PERMIT.READBACK_RECEIPT_PATH,
                receipt,
            )
            manifest = content_bound(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-"
                        "readback-manifest"
                    ),
                    "schemaVersion": "1.0",
                    "status": (
                        "identity_resolution_readback_publication_complete"
                    ),
                    "readbackAttemptId": readback_attempt_id,
                    "executionAttemptId": PERMIT.ATTEMPT_ID,
                    "authorityBinding": preflight_result[
                        "authorityBinding"
                    ],
                    "receipt": receipt_result,
                    "manifestWrittenLast": True,
                    "offline": True,
                    "networkRequestAttemptCount": 0,
                    "sourceAcquired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
            atomic_publish(
                ROOT,
                PERMIT.READBACK_MANIFEST_PATH,
                manifest,
            )
            snapshot.final_barrier()
        finally:
            snapshot.close()
        return {
            "status": "identity_resolution_readback_publication_complete",
            "readbackAttemptId": readback_attempt_id,
            "executionAttemptId": PERMIT.ATTEMPT_ID,
            "networkRequestAttemptCount": 0,
            "sourceAcquired": False,
            "externalAuthenticationRequired": False,
            "userActionRequired": False,
        }
    finally:
        os.umask(previous_umask)


class CanonicalArgumentParser(argparse.ArgumentParser):
    def error(self, _: str) -> None:
        raise ReadbackError("E_ARGUMENT", "arguments")


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
    except ReadbackError as error:
        sys.stdout.buffer.write(
            canonical_bytes(
                {
                    "documentType": (
                        "aetherlink.sumdb-identity-resolution-"
                        "readback-recorder-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": error.code,
                    "failurePhase": error.phase,
                    "networkRequestAttemptCount": 0,
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
                        "aetherlink.sumdb-identity-resolution-"
                        "readback-recorder-error"
                    ),
                    "schemaVersion": "1.0",
                    "status": "failed_closed",
                    "failureCode": "E_INTERNAL",
                    "failurePhase": "internal",
                    "networkRequestAttemptCount": 0,
                    "sourceAcquired": False,
                    "externalAuthenticationRequired": False,
                    "userActionRequired": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
