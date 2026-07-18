# P2P/NAT implementation handoff v8

This handoff permits exactly two requests to `download.gnome.org`: the official GLib 2.64.2 checksum file and source archive. The archive is locked to SHA-256 `9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277`.

GLib source extraction, hashing, manifest generation, and read-only inspection are allowed. All other dependency acquisition, including OpenSSL, is disabled. Compiler, static-library archiver, build system, configure, source or generator, test, socket, runtime network, Phase B, and production actions remain forbidden.

The next handoff requires a completed GLib intake and exact transitive dependency closure. It cannot open compile or runtime authority.
