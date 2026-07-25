# Wave4 bounded dependency-source acquisition permit v1

This document explains the machine-checked, one-use Wave4 acquisition permit.
The canonical authority record is the adjacent JSON file.

## Scope

- The permit covers exactly 32 public `GET` requests to
  `https://proxy.golang.org:443`: one `.mod` and one `.zip` resource for each
  of the 16 identity-complete Wave4 module/version vertices.
- Request order, paths, expected Go `h1:` values, response limits, accepted
  filenames, and the output namespace are fixed by the canonical JSON.
- The claim must be created with exclusive owner-only access and made durable
  before DNS, TCP, TLS, or HTTPS begins. The claim is never removed, and the
  permit cannot be retried, resumed, backfilled, or overwritten.
- Every accepted response is checked against its bound `h1:` value. Module ZIP
  files are also checked for their exact module/version prefix, safe names,
  structural consistency, CRCs, bounded expansion, and `.mod` parity.
- Successful publication is atomic and no-replace. The acquisition manifest is
  written last. Independent local byte readback remains mandatory afterward.

## Authentication boundary

This personal-project acquisition requires no account login, owner proof, SSH
or GPG key, password, private key, signature, token, cookie, client
certificate, authorization header, or user interaction. The endpoint is the
public Go module proxy and ordinary TLS certificate/hostname validation is the
only remote identity check.

## Explicit non-authority

The permit does not authorize source extraction, source loading or execution,
package-manager execution, compilation, product runtime networking, device
work, deployment, Git operations, or release publication. It does not establish
dependency fixed-point closure, semantic closure, library selection, rung-three
completion, or V1 release readiness.
