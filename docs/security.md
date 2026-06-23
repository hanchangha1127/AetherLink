# AetherLink Security Model

The project is local-first: no cloud backend, no account server, and no default remote relay. The Mac is the runtime. Android is a controller/client. That split is the main security boundary.

## Local-First Threat Model

Assets to protect:

- Mac runtime access.
- Local model prompts and responses.
- Trusted device identities.
- Future memory, files, tool calls, MCP calls, and audit logs.

Primary threats:

- Any device on the same Wi-Fi attempts to control the Mac runtime.
- A malicious client sends protocol messages directly to the local transport.
- A paired phone is lost or should no longer be trusted.
- Future tool execution gains file, terminal, network, or MCP access without explicit permission.
- A future cloud/relay shortcut weakens the local-first guarantee.

v0.1 may use a small development transport while the product matures, but it must not normalize unauthenticated same-network runtime access as the product model.

## Trusted Devices

The target design is persistent device identity on both sides:

- Mac has a stable device id and keypair.
- Android has a stable device id and keypair.
- Mac stores trusted Android public keys.
- Android pins the trusted Mac identity.
- Mac exposes remove-trusted-device controls.

Pairing creates the persistent trust record used by later runtime sessions. Removing a trusted device invalidates future authentication attempts from that Android identity.

## Pairing Design

Target pairing flow:

1. User opens pairing on the Mac companion.
2. Mac displays a QR code plus a one-time pairing code.
3. QR pairing data includes Mac device id, pairing nonce, service identity, and Mac public key or certificate fingerprint.
4. Android submits pairing nonce, code, Android device id, Android device name, and Android public key.
5. Mac stores the Android public key only if the pairing window is active and user confirmation succeeds.
6. Future sessions use challenge-response authentication before runtime commands.

v0.1 persists the scanned trusted Mac record on Android only after the Mac accepts `pairing.request` and stores the Android device as trusted. Android connects to the Mac runtime, not to Ollama or LM Studio directly.

An active pairing session allows only a bounded number of invalid nonce/code submissions. After the limit is reached, the Mac invalidates that pairing session and returns structured `pairing.result` rejection details while preserving the existing `accepted: false` response shape.

Implementation note: QR pairing and discovery can be simple in v0.1, but the docs must remain clear that the trusted-device gate is required before runtime commands execute.

Development note: `AETHERLINK_DEV_PAIRING=1` is only for local automated smoke tests with RuntimeDevServer. It opens and prints a temporary pairing session for scripts, but runtime commands still require the normal pairing/trusted-device and challenge-response path. Do not enable this flag for production or normal trusted-device use.

## Session Authentication

After pairing, each runtime connection authenticates before model or command messages are accepted:

1. Android sends `hello` with its trusted device id.
2. Mac checks the trusted-device store and returns `auth.challenge` with a one-time nonce.
3. Android signs the nonce with its paired private key and sends `auth.response`.
4. Mac verifies the signature against the stored Android public key.
5. Mac allows runtime commands only after the connection is authenticated.

Runtime commands include `runtime.health`, `models.list`, `models.pull`, `chat.send`, and `chat.cancel`. Requests sent before authentication fail with `authentication_required`; unknown or removed device ids fail with `pairing_required`; invalid signatures fail with `authentication_failed`.

## Encryption Roadmap

v0.1 development transport:

- Local network socket with length-prefixed JSON.
- Clear runtime module boundary so transport can be replaced.
- No direct backend URL exposed to Android.
- Runtime commands rejected until the device is trusted and authenticated.

Hardening roadmap:

- TLS or Noise-style encrypted channel between Android and Mac.
- Mac identity pinning on Android.
- Android public-key challenge-response on Mac.
- Session keys derived after pairing.
- Protocol commands rejected until authenticated.
- Optional BLE/QR/mDNS only for discovery or key exchange, not LLM streaming.

## Same-Network Unauthenticated Access Is Forbidden

Same Wi-Fi is not a trust boundary. A guest phone, compromised laptop, or any local network process could otherwise send `chat.send`, list models, or later trigger tools.

Therefore:

- Runtime commands must require a trusted-device check and successful challenge-response authentication.
- Ollama remains bound to the Mac runtime adapter and is never exposed as the Android API. Android must not call Ollama `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, or LM Studio endpoints directly.
- Model installation is also a runtime command: Android may request `models.pull`, but only the authenticated Mac runtime may call Ollama `/api/pull`.
- Future file, terminal, MCP, skills, and web search actions must pass through a Mac-side permission broker and audit log.
