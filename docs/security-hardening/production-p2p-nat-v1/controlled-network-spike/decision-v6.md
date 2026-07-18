# Controlled spike decision v6

## Decision

`libnice-0.1.23-glib-c-abi` is rejected before compilation. Two independent static reviews found four P1 production-profile failures: non-cryptographic ICE randomness, secret-bearing diagnostics, automatic alternate-server destination changes before caller authorization, and consent refresh without success-class or source-tuple binding.

The earlier libjuice candidate remains rejected. No networking library is selected, and no next candidate is implicitly proposed.

## Acquisition Closure

The exact libnice 0.1.23 archive, detached-signature bytes, GLib 2.64.2 checksum, and GLib archive were acquired under consumed one-shot authorities. The remaining libffi, GNU libiconv, proxy-libintl, and OpenSSL sources were not acquired because the candidate failed before scope expansion.

## Compile Closure

No configure step, build system, compiler, static archiver, linker, symbol tool, generated source, C ABI adapter, or test executable was invoked. No compile contract is created.

## Next Decision

A new networking library requires a new versioned review and explicit approval before any source acquisition. Rejected-candidate authority cannot be reused. Source execution, sockets, runtime or harness networking, Phase B, production networking, and deployment remain prohibited.
