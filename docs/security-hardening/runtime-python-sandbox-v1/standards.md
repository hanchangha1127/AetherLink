# Runtime Python Sandbox v1 Primary References

The review uses these primary platform and language references. They support the
security rationale but do not by themselves prove that a future implementation
is correctly sandboxed.

## Apple Platform Isolation

- [Protecting user data with App Sandbox](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox)
  describes kernel-enforced containment, entitlement minimization, sandboxed
  app containers, and embedded-tool inheritance.
- [Configuring the macOS App Sandbox](https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox)
  describes explicit capability declarations and runtime verification.
- [XPC](https://developer.apple.com/documentation/xpc) describes XPC services as
  a mechanism for privilege isolation and independently scoped work.
- [Creating XPC Services](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingXPCServices.html)
  explains that ordinary task spawning does not create a separate sandbox while
  an XPC service can have its own restricted sandbox.

These capability and inheritance controls are not treated as an executable
identity allowlist after native compromise. The one-shot embedded-worker shape
avoids an approved interpreter child process, while live validation must still
test that a replacement process image cannot gain broader sandbox or resource
authority.

## Python Runtime Controls

- [Python command-line and environment](https://docs.python.org/3/using/cmdline.html)
  defines `-I` isolated mode, `-S` site-initialization suppression, and `-B`
  bytecode-write suppression. The review requires a pinned equivalent of all
  three before untrusted source is parsed and treats them as defense in depth,
  not OS containment.
- [Python audit hooks](https://docs.python.org/3/library/sys.html#sys.addaudithook)
  explicitly warns that Python-level audit hooks are not suitable for
  implementing a sandbox.
- [Python subinterpreter caveats](https://docs.python.org/3/c-api/init.html#bugs-and-caveats)
  documents shared-process and extension caveats, including the ability to
  affect shared file descriptors.
- [Python resource limits](https://docs.python.org/3/library/resource.html)
  describes Unix soft and hard resource limits and their platform-dependent
  availability.

## Unicode Source Review

- [Unicode Bidirectional Algorithm](https://www.unicode.org/reports/tr9/)
  defines bidi control behavior. The proposed restricted profile rejects bidi
  controls, default-ignorable code points, and non-ASCII line separators before
  source digest and approval display, then uses token-aware escaped rendering.

## Operating-System Resource Limits

- [POSIX getrlimit and setrlimit](https://pubs.opengroup.org/onlinepubs/7908799/xsh/getrlimit.html)
  defines per-process soft and hard resource ceilings. A future implementation
  must separately prove which limits are effective on every supported macOS
  release and fail closed when a required ceiling is unavailable.
