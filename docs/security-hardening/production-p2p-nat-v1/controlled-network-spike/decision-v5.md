# Controlled spike decision v5

## Decision

The retained explicit approval for minimum GLib-family dependencies authorizes one-shot acquisition of the exact GLib 2.64.2 release archive and its official SHA-256 list. This does not select libnice or authorize compilation.

## Exact acquisition

- Index: `https://download.gnome.org/sources/glib/2.64/`
- Checksum: `https://download.gnome.org/sources/glib/2.64/glib-2.64.2.sha256sum`
- Archive: `https://download.gnome.org/sources/glib/2.64/glib-2.64.2.tar.xz`
- Required archive SHA-256: `9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277`

Exactly two HTTPS requests to `download.gnome.org` are allowed. Redirects, environment proxies, package managers, alternate URLs, and alternate hosts are forbidden. The checksum is capped at 4 KiB, the archive at 64 MiB, and extraction at 512 MiB.

## Closed authority

All other dependency acquisition remains disabled until the exact GLib source yields a transitive closure. OpenSSL is outside the effective GLib-family scope and remains blocked pending explicit expansion. Compiler, static-library archiver, build-system, configure, source or generator, and test execution remain forbidden, as do sockets, runtime networking, Phase B, and production.
