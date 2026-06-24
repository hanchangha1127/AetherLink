#!/usr/bin/env python3
"""Development relay for AetherLink remote route testing.

This is a connectivity bootstrap component, not an AI backend. It pairs one
runtime and one client by relay_id, sends a small ready line, and then forwards
bytes in both directions without decoding AetherLink protocol frames.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass


READY_LINE = b"AETHERLINK_RELAY ready\n"
HANDSHAKE_PREFIX = "AETHERLINK_RELAY"
VALID_ROLES = {"runtime", "client"}


@dataclass
class PendingPeer:
    role: str
    relay_id: str
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter


class RelayHub:
    def __init__(self) -> None:
        self._pending: dict[str, dict[str, PendingPeer]] = {}
        self._lock = asyncio.Lock()

    async def add(self, peer: PendingPeer) -> None:
        async with self._lock:
            room = self._pending.setdefault(peer.relay_id, {})
            old = room.pop(peer.role, None)
            if old is not None:
                old.writer.close()
            other_role = "client" if peer.role == "runtime" else "runtime"
            other = room.pop(other_role, None)
            if other is None:
                room[peer.role] = peer
                print(
                    f"[relay] waiting relay_id={short_id(peer.relay_id)} role={peer.role}",
                    flush=True,
                )
                return
            if not room:
                self._pending.pop(peer.relay_id, None)

        await bridge(peer, other)


async def bridge(first: PendingPeer, second: PendingPeer) -> None:
    print(
        f"[relay] matched relay_id={short_id(first.relay_id)} "
        f"{first.role}<->{second.role}",
        flush=True,
    )
    first.writer.write(READY_LINE)
    second.writer.write(READY_LINE)
    await asyncio.gather(first.writer.drain(), second.writer.drain())

    async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while not reader.at_eof():
                data = await reader.read(64 * 1024)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        finally:
            writer.close()

    await asyncio.gather(
        pipe(first.reader, second.writer),
        pipe(second.reader, first.writer),
        return_exceptions=True,
    )


async def handle_client(
    hub: RelayHub,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=10)
        role, relay_id = parse_handshake(raw.decode("utf-8", errors="replace"))
        peername = writer.get_extra_info("peername")
        print(
            f"[relay] accepted role={role} relay_id={short_id(relay_id)} peer={peername}",
            flush=True,
        )
        await hub.add(PendingPeer(role=role, relay_id=relay_id, reader=reader, writer=writer))
    except Exception:
        writer.close()


def parse_handshake(line: str) -> tuple[str, str]:
    parts = line.strip().split()
    if len(parts) != 3 or parts[0] != HANDSHAKE_PREFIX:
        raise ValueError("invalid handshake")
    role = parts[1]
    relay_id = parts[2]
    if role not in VALID_ROLES:
        raise ValueError("invalid role")
    if not relay_id or any(char.isspace() for char in relay_id):
        raise ValueError("invalid relay id")
    return role, relay_id


def short_id(value: str) -> str:
    if len(value) <= 12:
        return value
    return f"{value[:6]}...{value[-6:]}"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AetherLink development relay.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=43171)
    args = parser.parse_args()

    hub = RelayHub()
    server = await asyncio.start_server(
        lambda reader, writer: handle_client(hub, reader, writer),
        host=args.host,
        port=args.port,
    )
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    print(f"[relay] AetherLink development relay listening on {sockets}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
