# libnice dependency closure v3

The exact acquired closure stops at libnice 0.1.23 and GLib 2.64.2 because the libnice candidate failed its mandatory static security audit before compilation.

The audit still identified the minimum remaining source set: libffi 3.7.1, GNU libiconv 1.19 for Android API 26, proxy-libintl 0.1 in stub-only mode, and OpenSSL 3.5.7 LTS. None was acquired, checksum-pinned, extracted, or executed. Those versions are retained only as historical dependency-planning evidence.

Android NDK r28c and the pinned macOS SDK would supply platform libc, threads, loaders, system zlib, and macOS iconv inputs; GLib contains the selected internal PCRE source. No cross file, configure output, generated source, product C ABI, or compile contract was created.

All remaining source, compiler, socket, runtime network, Phase B, and production authority is closed. A different library candidate requires a new versioned review rather than inheriting this plan implicitly.
