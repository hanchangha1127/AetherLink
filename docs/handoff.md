# AetherLink Session Handoff - 2026-06-29 KST

This file is the short handoff for continuing work in another Codex session.
Treat it as the first document to read before touching code.

## Read First

- `docs/connection-overlay.md`: current and target connection model, including QR-first remote route requirements.
- `docs/qa-evidence.md`: current verification rule and the latest evidence. Old screenshots and artifacts are historical unless explicitly named by current progress entries.
- `docs/progress.md`: chronological implementation notes and verification commands.
- `docs/protocol.md`: Android/client to AetherLink Runtime protocol boundary.
- `docs/security.md`: trust, pairing, and local-first threat model.

## Non-Negotiable Boundaries

- AetherLink is local-first. There is no cloud AI backend.
- Client targets are controllers. They must never call Ollama, LM Studio, or future model-provider URLs directly.
- AetherLink Runtime mediates all model access, provider health, chat streaming, cancellation, runtime-owned chat history, and runtime-owned memory.
- QR-first persistent pairing is the product path. Normal product QR payloads must include remote route material, not only identity material.
- Identity-only QR remains useful for diagnostics and local compatibility tests, but it is not enough for unrelated-network pairing.
- Different-network connectivity cannot rely on a fixed private IP, mDNS alone, or a stale last-known address.
- Product copy should stay OS-neutral because target support expands beyond the first client/runtime platforms.
- Do not use `gpt-5.3-codex-spark` in this workstream. A GPT-5.5 explorer named Harvey was closed before this handoff.

## Current Worktree Status

The tree is intentionally dirty. Do not revert unrelated files.

Current change areas include:

- Android client shell, chat UI, Settings, runtime state, local store, pairing QR handling, model/embedding selection, attachments, reasoning preview, localization, and no-device tests.
- Runtime host app UI, trusted devices, pairing view, status view, remote route preparation copy, localization, and runtime app model behavior.
- Runtime relay code and tests, including relay matching, allocation/probe behavior, route retention, and development relay readiness.
- Documentation in `README.md`, `docs/connection-overlay.md`, `docs/progress.md`, and `docs/qa-evidence.md`.
- QA scripts under `script/`, including no-device quality, docs/copy hygiene, Android string parity, external relay pairing, deeplink smoke, and relay reachability probes.
- Untracked runtime relay probe files:
  - `apps/macos/RelayServerCore/Sources/RelayProbe.swift`
  - `apps/macos/RelayServerCore/Tests/RelayProbeTests.swift`

## Latest Focused Change

Product QR pairing was tightened so scanner/deeplink product entry points require route-capable QR material.

Current behavior:

- Android product QR scans call `trustRuntimeFromPairingQr(... requireRemoteRoute = true)`.
- Pairing deeplink entry calls `trustRuntimeFromPairingQr(... requireRemoteRoute = true)`.
- `String.isAetherLinkPairingQrValue(requireRemoteRoute: Boolean = true)` defaults to product scanner policy.
- Identity-only QR can still be parsed explicitly with `requireRemoteRoute = false` for diagnostics/local compatibility tests.
- Route-less product QR now reports the existing route-unavailable path instead of appearing accepted and timing out later.

Focused tests updated around this:

- `AppNavigationTest.pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner`
- `AppNavigationTest.pairingQrScannerClassifiesRawValuesBeforeConsumingCameraResult`
- `RuntimeClientViewModelTest.productPairingQrParserRejectsIdentityOnlyQrWhenRemoteRouteIsRequired`
- `RuntimeClientViewModelTest.identityOnlyQrPlanStartsDiscoveryAndWaitsForRoute`

## Verified Evidence

The latest no-device quality gate passed before this handoff:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
ANDROID_HOME="$HOME/Library/Android/sdk" \
bash script/check_no_device_quality.sh
```

Targeted QR-policy tests passed:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
./gradlew --no-daemon :app:testDebugUnitTest \
  --tests com.localagentbridge.android.AppNavigationTest.pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner \
  --tests com.localagentbridge.android.AppNavigationTest.pairingQrScannerClassifiesRawValuesBeforeConsumingCameraResult \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.productPairingQrParserRejectsIdentityOnlyQrWhenRemoteRouteIsRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.identityOnlyQrPlanStartsDiscoveryAndWaitsForRoute \
  -Pkotlin.incremental=false
```

Fast hygiene checks passed:

```bash
python3 -m py_compile script/check_copy_hygiene.py script/check_docs_hygiene.py
python3 script/check_copy_hygiene.py
python3 script/check_docs_hygiene.py
git diff --check
```

## Not Yet Proven

Do not claim these as complete without a fresh physical run:

- Optical/camera QR scan on a physical phone.
- Physical Android rendering.
- Physical TalkBack or VoiceOver traversal.
- Android system/per-app locale mutation on hardware.
- Real device haptics.
- Live provider-backed streaming chat and cancel.
- Real unrelated-network runtime connectivity.
- Production NAT traversal, rendezvous, TURN-style relay allocation, replay protection, and production end-to-end transport encryption.

## Different-Network Connection State

The intended product requirement is QR-only connection even when devices are not on the same Wi-Fi.

Current implementation status:

- Local/direct and development relay routes exist.
- QR payloads can carry relay route material: `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- Android product scanner now requires route-capable QR material.
- A physical external relay QA wrapper exists, but this session did not prove it against a real phone on another network.

Next physical validation command when a phone is connected and a relay host reachable by both sides exists:

```bash
bash script/check_physical_external_relay_pairing.sh \
  --relay-host <public-or-vpn-host> \
  --relay-port <port>
```

Use `--allow-private-relay` only for a user-controlled VPN, tunnel, or private overlay where both devices can actually reach the relay address.

## Recommended Next Session Flow

1. Confirm no stale subagents are open. Harvey was closed before this handoff.
2. Run `git status --short` and inspect only the files relevant to the next task.
3. If continuing QA without a phone, run:

```bash
python3 script/check_docs_hygiene.py
python3 script/check_copy_hygiene.py
git diff --check
```

4. If the phone is connected and the task is pairing/connectivity, run a physical device check rather than relying on old artifacts.
5. If testing unrelated-network pairing, use a public, VPN, tunnel, or private-overlay relay address reachable from both devices. A same-machine loopback or same-Wi-Fi route is not evidence for the product requirement.
6. Keep commits small. The user said they will handle commit and push unless they explicitly ask otherwise.

## High-Priority Open Work

1. Prove QR-only pairing on a physical phone using route-capable QR material and a mutually reachable relay.
2. Prove saved trusted-route reconnect after relaunch on the physical phone.
3. Prove runtime-mediated `models.list`, streamed `chat.send`/`chat.delta`/`chat.done`, and `chat.cancel` over that route.
4. Keep AetherLink Runtime as the only model-provider caller for Ollama and LM Studio.
5. Continue replacing fixed-IP assumptions with identity plus route resolution.
6. Continue UI polish toward a modern, quiet ChatGPT-like chat surface while keeping product copy OS-neutral.
7. Keep embedding models separate from chat models.
8. Keep vision/document/file input gated by runtime provider capabilities.
9. Keep runtime-owned chat history and memory scoped by trusted device owner identity.
10. Move production transport toward private overlay, P2P candidate exchange, blind encrypted relay fallback, replay protection, and key rotation.

## Security Notes For Continuation

- Do not commit GitHub tokens, relay allocation secrets, pairing secrets, or local provider URLs.
- Do not expose Ollama or LM Studio endpoints to client code or QR payloads.
- Network reachability is not authorization. Pairing, trusted-device records, challenge-response, and encrypted sessions remain required.
- Remote relay infrastructure is not a cloud AI backend and must not see plaintext prompts, files, memory, or model output in the production design.

