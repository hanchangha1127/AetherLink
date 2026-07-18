# Controlled spike decision v4

## Decision

The explicit user approval authorizes a bounded Phase A evaluation of `libnice-0.1.23-glib-c-abi`. The candidate is not selected for implementation or production. This record opens one-shot acquisition of the official libnice 0.1.23 source archive and its detached signature only.

## Exact acquisition boundary

- Official release index: `https://libnice.freedesktop.org/`
- Source archive: `https://libnice.freedesktop.org/releases/libnice-0.1.23.tar.gz`
- Detached signature: `https://libnice.freedesktop.org/releases/libnice-0.1.23.tar.gz.asc`
- HTTPS is mandatory. Redirects, environment proxies, package managers, alternate hosts, and alternate URLs are forbidden.
- The source archive is capped at 32 MiB, the signature at 64 KiB, and the extracted tree at 128 MiB.

The approval also covers the minimum required GLib-family source closure, but that authority is not yet effective. The exact versions and URLs must first be derived from the pinned libnice build metadata and locked in a new versioned decision and handoff. Dependencies outside the approved GLib-family scope require a new explicit scope-expansion approval.

## Closed authority

Compiler, static-library archiver, build-system, configure, source, and test execution remain forbidden. Source forks, sockets, runtime or harness network I/O, controlled-spike socket execution, Phase B, and production remain forbidden.

Archive extraction is data handling, not source or build execution. It must reject path traversal, links escaping the destination, device nodes, and size-limit violations before material is accepted.

## Completion condition

This decision is consumed only after both exact artifacts are acquired within the locked policy, hashed, safely extracted, and recorded in a versioned intake. The next record must derive the minimum dependency closure before any dependency download. A security-floor failure rejects the candidate before compilation.

This evidence cannot establish compile, ABI, runtime, socket, network, NAT, device, Phase B, or production behavior.
