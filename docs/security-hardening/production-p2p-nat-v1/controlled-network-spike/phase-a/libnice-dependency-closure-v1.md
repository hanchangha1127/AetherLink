# libnice dependency closure v1

## Direct requirements

The pinned libnice 0.1.23 source requires GLib/GIO/GThread at GLib 2.56 or newer and requires either GnuTLS 3.6.0 or newer or OpenSSL. The upstream wrap pins GLib 2.64.2 with SHA-256 `9a2f21ed8f13b9303399de13a0252b7cbcede593d26971378ec6cb90e87f2277`.

The minimum closure recommendation is GLib 2.64.2 plus OpenSSL. GnuTLS has a larger mandatory transitive closure. OpenSSL is not part of the currently effective GLib-family acquisition scope and therefore remains blocked pending explicit scope expansion.

## Disabled optional inputs

GStreamer, GUPnP IGD, GObject introspection, gtk-doc, examples, and tests are excluded from the bounded static C ABI target. Their sources must not be acquired or accepted as ambient inputs.

## Exact next lock

The next permitted dependency artifact is `https://download.gnome.org/sources/glib/2.64/glib-2.64.2.tar.xz`, capped at 64 MiB and locked to the upstream SHA-256. The canonical `download.gnome.org` URL avoids the redirect-prone `ftp.gnome.org` URL in the upstream wrap.

GLib's transitive requirements must be derived from that exact source before any further dependency acquisition. No build system, generator, compiler, static-library archiver, socket, runtime network, Phase B, or production authority is opened.
