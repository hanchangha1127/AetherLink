# AetherLink Progress And Forward Plan

Last updated: 2026-06-26 KST.

This document records what has been implemented so far and what should happen next. It is intentionally broader than the original v0.1 MVP because recent work has moved the prototype toward a more complete product shape.

## Product Boundary

The concrete remote 1:1 connection architecture is now tracked in [connection-overlay.md](connection-overlay.md).

- AetherLink is local-first.
- There is no cloud model backend, account server, production rendezvous fabric, or production relay in the current implementation.
- Client apps are controllers. Runtime host apps mediate model access, file ingestion, future tools, future web search, future project workspaces, and future automations.
- The client must not call Ollama, LM Studio, or future serving backends directly.
- Device connectivity must be based on paired device identity and keys, not on a fixed IP address.
- Same-network discovery, mDNS/Bonjour, explicit host/port values, raw local sockets, and USB/localhost forwarding are v0.1 development hints or local fast-path transports only; they cannot satisfy different-network product connectivity by themselves.
- The intended product connection model is a paired-device private P2P overlay, closer in spirit to decentralized or distributed peer discovery in networks such as Bitcoin than to a fixed server address. This analogy is only about rendezvous, peer identity, and discovery; AetherLink must not expose a public open peer network, and only QR-paired trusted devices should be able to discover, authenticate, and communicate with each other.
- The connection manager should work across different networks with a QR-only user flow: the QR bootstraps paired identity plus private overlay/rendezvous/relay material, local direct is an opportunistic fast path when available, remote peer-to-peer NAT traversal uses STUN-like address discovery and authenticated hole punching, and an end-to-end encrypted blind relay/TURN-style path handles networks where direct peer-to-peer fails. The client user should not enter hostnames, ports, Ollama URLs, LM Studio URLs, or backend URLs.
- Optional DHT/bootstrap-peer discovery can provide short-lived rendezvous records for paired devices where practical, but it must not become a public runtime directory, account system, backend URL registry, model-logic backend, or trust authority.
- Relay/signaling infrastructure must not see AI protocol payloads, model lists, prompts, files, memory, backend credentials, or backend URLs in production.
- Current code has local-direct route-candidate plumbing, development endpoint hints, and a temporary outbound TCP relay path keyed by stable paired-route material for different-Wi-Fi development testing. Normal QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`; the client and runtime host encrypt relay frame bodies before the relay forwards them and reject stale QR route material. The allocation relay now issues route-token-based `relay_id` values and can reuse a runtime-supplied stable frame secret, so stored trusted routes are less brittle across app restarts than one-off random relay IDs. A QR that only contains runtime identity can establish trust and resolve local routes, but it cannot cross unrelated networks by itself. For QR-only remote linking, the QR must carry complete remote-route material such as relay or future P2P rendezvous tokens. Remote P2P NAT traversal, DHT/bootstrap rendezvous, production signaling, hardened relay allocation renewal, replay-resistant session setup, and complete production end-to-end transport encryption remain future milestones.
- The runtime app can display compact QR aliases for camera scanning while retaining canonical QR field names for docs/debugging. Clients accept both forms. Compact aliases reduce QR density for route-bearing relay QR payloads, but they do not remove the requirement for a mutually reachable relay/P2P route.
- Next remote-connection increment: keep the normal user flow QR-only while making the QR production route bootstrap explicit. The QR should carry runtime identity, runtime public key or certificate fingerprint, a pairing/route token, and overlay/rendezvous/relay material for different-network routes; fixed host/port remains optional development diagnostics only.
- Current first targets are the mobile client and desktop runtime host.
- Future targets include additional client targets and runtime targets on Windows and DGX OS-class systems.

## Current Workstream Coordination Notes

- Do not use GPT-5.3-Codex-Spark for this workstream. Use GPT-5.5/inherited-model subagents only when delegation is useful.
- During the latest no-device Android chat-composer, reasoning, and relay-readiness pass, GPT-5.5 read-only audit subagents were used for Android chat UI/state review. No GPT-5.3-Codex-Spark subagent was used.
- The user will handle commits and pushes unless they explicitly ask otherwise.

## Implemented So Far

### 2026-06-26 Apache 2.0 License Guard

- Confirmed `LICENSE` contains the Apache License, Version 2.0 text with the AetherLink contributors copyright notice.
- Added an explicit License section to the root `README.md`.
- Added short Apache 2.0 License sections to the Android, macOS, protocol-schema, shared protocol, examples, and brand asset README files with correct relative links back to `LICENSE`.
- Updated the older tentative licensing wording to the current project state: AetherLink is licensed under the Apache License, Version 2.0.
- Added `script/check_license.py` to guard the Apache 2.0 declaration, README license sections, nested README license sections, and stale/conflicting license wording.
- No GPT-5.3-Codex-Spark subagent was used. One GPT-5.5 read-only audit subagent checked for stale or missing license wording and was closed after completion.

Verification after this change:

- `python3 -m py_compile script/check_license.py && python3 script/check_license.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- README.md apps/android/README.md apps/macos/README.md packages/protocol-schema/README.md shared/protocol/README.md examples/README.md assets/brand/README.md docs/progress.md script/check_license.py`

### 2026-06-26 No-Device App Icon Asset Guard

- The Android phone is currently disconnected, so physical-device launcher icon inspection, rendered Android home-screen icon validation, macOS Dock screenshot validation, camera-based QR scan, app-level pairing completion, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Confirmed the user-provided AetherLink icon source is stored in `assets/brand/aetherlink_icon_source.png`, with `assets/brand/generate_aetherlink_icons.swift` as the canonical offline generator for Android launcher assets and the macOS `AppIcon.icns`.
- Added `script/check_app_icons.py` to guard the branding asset chain. The script verifies the source/preview PNGs, Android manifest launcher icon references, Android density PNG dimensions, adaptive icon foreground/background references, and required macOS ICNS chunks.
- Verified that Android resource processing and the SwiftPM AetherLink product both still accept the current generated icon assets.

Verification after this change:

- `python3 -m py_compile script/check_app_icons.py && python3 script/check_app_icons.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:processDebugResources -Pkotlin.incremental=false`
- `swift build --product AetherLink`
- `git diff --check -- script/check_app_icons.py`

### 2026-06-26 No-Device Android Haptic Interaction Guard

- The Android phone is currently disconnected, so physical-device install, rendered UI inspection, actual vibration feel, camera-based QR scan, app-level pairing completion, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited the Android Compose haptic wiring with one GPT-5.5 read-only subagent. No GPT-5.3-Codex-Spark subagent was used, and the subagent was closed after completion.
- Confirmed the current high-value visible actions already route through the AetherLink haptic policy: QR scan success, new chat, navigation selection, chat rename/archive, attach/send/cancel, suggested next questions, attachment removal, copy actions, expandable settings, and selected-row de-duplication.
- Strengthened `script/check_copy_hygiene.py` with an Android haptic guard so the central helper, core action wiring, and focused haptic policy tests cannot silently disappear during future UI refactors.

Verification after this change:

- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.aetherLinkHapticPolicyKeepsOrdinaryActionsLightweight --tests com.localagentbridge.android.AppNavigationTest.aetherLinkHapticPolicyKeepsStrongActionsDistinct --tests com.localagentbridge.android.AppNavigationTest.selectionChangeHapticOnlyRunsWhenSelectionChanges -Pkotlin.incremental=false`
- `git diff --check -- script/check_copy_hygiene.py`

### 2026-06-26 No-Device Attachment MIME And HWPML Ingestion Guard

- The Android phone is currently disconnected, so physical-device install, rendered attachment picker behavior, camera-based QR scan, app-level pairing completion, haptic feel, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Tightened Android attachment picker MIME coverage so runtime-supported document inputs stay explicit for HWPML, Hancom HWPML, HTML, RTF, XHTML, Markdown, reStructuredText, and AsciiDoc while image selection still appears only when the selected chat model advertises vision/image/multimodal capability.
- Added Android filename fallback mapping for `.hwpml` to `application/x-hwpml`, keeping pasted/shared files aligned with the picker and runtime ingestion contract when the content resolver cannot provide a MIME type.
- Added macOS `DocumentIngestion` support for HWPML XML documents and the Hancom HWPML MIME alias. HWPML now goes through the XML text extraction path and returns `application/x-hwpml` metadata.
- Strengthened `script/check_copy_hygiene.py` with an attachment-ingestion guard so the Android picker, Android fallback MIME mapping, macOS HWPML extractor path, and focused regression tests cannot silently drift.
- No GPT-5.3-Codex-Spark subagent was used.

Verification after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerUsesDocumentTypesWhenSelectedModelIsNotVisionCapable --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerIncludesImageTypesWhenSelectedModelIsVisionCapable -Pkotlin.incremental=false`
- `swift test --filter DocumentTextExtractorTests`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt apps/macos/DocumentIngestion/Sources/DocumentTextExtractor.swift apps/macos/DocumentIngestion/Tests/DocumentTextExtractorTests.swift`

### 2026-06-26 No-Device macOS Saved Connection Copy Guard

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Updated the macOS Advanced Connection Setup status copy for saved cross-network connection details so it no longer says "saved connection settings" and instead uses the release-facing "connection details" wording across English, Korean, Japanese, Simplified Chinese, and French.
- Updated the Swift source key in `RemoteRelayRoutePanel` and the five locale entries together so `NSLocalizedString` key parity, localized value parity, and `%@` placeholder parity stay aligned.
- Added stale-copy guards so the old "Using %@ from saved connection settings..." key is forbidden by `script/check_macos_localization.py`, and the broader phrase "saved connection settings" is blocked by `script/check_copy_hygiene.py`.
- No GPT-5.3-Codex-Spark subagent was used. One GPT-5.5 read-only audit subagent was used to identify the exact macOS source, locale, and guard locations, then closed after completion.

Verification after this change:

- `python3 -m py_compile script/check_macos_localization.py && python3 script/check_macos_localization.py`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `swift test --filter AetherLinkLocalizationTests`

### 2026-06-26 No-Device Android Chat Model Menu Embedding Access

- The Android phone is currently disconnected, so physical-device install, rendered chat top-bar inspection, touch feel, camera-based QR scan, app-level pairing completion, and real runtime reconnect were not validated in this pass.
- Added a separate Memory indexing model section to the Android chat top-bar model menu. Chat model selection remains focused on installed runtime-host-local chat models, while embedding models are exposed separately and continue to use the persisted `selectedEmbeddingModelId` path.
- Kept embedding models out of the chat model list and preserved the existing Settings-based embedding model control as a secondary location.
- Added Android helper tests proving the chat top-bar embedding menu includes only installed runtime-host-local embedding models, pins the selected embedding model, and filters by model identity/provider/source without mixing embedding models into chat selection.
- Tightened the shared model-menu search behavior so the search field remains available even when the runtime currently exposes only embedding models, and the embedding section distinguishes "no matching search result" from "no embedding models available."
- Updated the five-language Android `select_embedding_model` error copy so it no longer sends the user specifically to Settings. The copy now asks for a Memory indexing model, matching the fact that the model can also be selected from the chat top-bar model menu.
- Pinned the new five-language `select_embedding_model` copy in `script/check_android_string_parity.py` to prevent a Settings-only instruction from returning.
- Strengthened `script/check_copy_hygiene.py` so the Android chat top-bar model menu must stay wired to `selectEmbeddingModel`, keep a visible Memory indexing model section, keep embedding filtering separate from chat filtering, and retain the focused regression tests.
- No GPT-5.3-Codex-Spark subagent was used. GPT-5.5 read-only audit subagents were used to identify Android UX and runtime-connection gaps before this patch.

Verification after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuShowsOnlyInstalledLocalEmbeddingModelsAndPinsSelection --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuSearchMatchesModelIdentityProviderAndSource -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.modelMenuSearchStaysAvailableWhenOnlyEmbeddingModelsExist --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuEmptyTextDistinguishesSearchFromUnavailableModels -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuShowsOnlyInstalledLocalEmbeddingModelsAndPinsSelection --tests com.localagentbridge.android.AppNavigationTest.modelMenuSearchStaysAvailableWhenOnlyEmbeddingModelsExist -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 -m py_compile script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 -m py_compile script/check_copy_hygiene.py`

### 2026-06-26 No-Device macOS Localization Surface Guard

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Strengthened `script/check_macos_localization.py` so macOS SwiftUI visible text constructors such as `Text`, `Button`, `Label`, `Picker`, `Toggle`, `TextField`, `SecureField`, `alert`, and `confirmationDialog` cannot use raw string literals. Visible strings must go through `NSLocalizedString`, preserving the in-app language setting across English, Korean, Japanese, Simplified Chinese, and French.
- Confirmed the current macOS SwiftUI sources pass the raw-visible-literal guard with no exceptions.

Verification after this change:

- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_macos_localization.py`

### 2026-06-26 No-Device Android QR Pairing Hardening

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited the Android QR pairing path with one GPT-5.5 read-only subagent. No GPT-5.3-Codex-Spark subagent was used, and the subagent was closed after completion.
- Tightened Android direct-route candidate generation so selected Bonjour routes and matching discovered routes cannot become direct TCP candidates when they point at local model-provider ports `11434` or `1234`. This preserves the product boundary that the client connects to AetherLink Runtime, not directly to Ollama or LM Studio.
- Tightened Android scanner raw-value acceptance so the camera flow only closes on QR values that the runtime pairing parser can actually accept under the same debug/product policy. Incomplete legacy `lab://pair` values are now ignored by the scanner instead of closing the scanner and surfacing a later invalid-pairing error.
- Narrowed the Android exported browsable deep-link manifest entry to `aetherlink://pair` and legacy `lab://pair` host matches, removing the broad scheme-only filter for unrelated custom-scheme actions.
- Added Android no-device regression coverage that a relay QR remains persisted after an initial relay connection failure and that a recreated ViewModel restores that pending relay QR and sends the pairing request without using direct TCP.
- Strengthened `script/check_copy_hygiene.py` so Android pairing deep links must stay pair-host scoped, scanner acceptance must keep using the runtime pairing parser policy, and DirectTcp route candidates must keep blocking model-provider ports `11434` and `1234` across selected, discovered, and target endpoints.

Verification after this change:

- `python3 -m py_compile script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesRejectDirectModelProviderPortsFromSelectedAndDiscoveredRoutes --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_protocol_schema.py`

### 2026-06-26 No-Device Product Copy And Localization Polish

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited Android and macOS user-facing copy with one GPT-5.5 read-only subagent. No GPT-5.3-Codex-Spark subagent was used, and the subagent was closed after completion.
- Softened Android QR text fallback copy so it reads as a camera-unavailable fallback using the same trust checks as scanning, instead of diagnostic/backdoor copy.
- Renamed Android local development route labels from prototype route wording to `USB connection` and `Emulator connection` across English, Korean, Japanese, Simplified Chinese, and French.
- Renamed Android provider diagnostic toggles and detail labels to user-facing details/reference-code wording across the five supported languages.
- Softened macOS Activity, provider redaction, and connection recovery copy across English, Korean, Japanese, Simplified Chinese, and French. Visible strings now use `Details`, `Provider address hidden`, `Connection Recovery`, and `Protected connection key` style wording instead of technical endpoint/advanced/secret framing.
- Updated macOS localization tests to expect the new product copy for endpoint redaction and connection recovery failures.
- Strengthened Android release-copy guards so QR fallback, USB/emulator connection labels, and provider detail/reference-code labels are pinned to exact expected values across English, Korean, Japanese, Simplified Chinese, and French.
- Strengthened macOS localization guards so release-facing display values for details, provider redaction, connection recovery, and protected connection keys are pinned across English, Korean, Japanese, Simplified Chinese, and French.
- Added macOS localization regression coverage that resolves the English release-facing connection/details strings directly.

Verification after this change:

- `python3 -m py_compile script/check_android_string_parity.py script/check_macos_localization.py script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest -Pkotlin.incremental=false`
- `swift test --filter AetherLinkLocalizationTests`
- `git diff --check -- apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ko.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ja.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/zh-Hans.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/fr.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`

### 2026-06-26 No-Device Android Thinking Preview And Code Block Guard

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Refined the Android assistant thinking display so reasoning stays in a short, dim three-line preview by default and can be expanded to the full text when the content is longer.
- Suppressed the generic assistant typing placeholder while a reasoning stream is still open, avoiding duplicate "thinking plus typing" rows before answer text starts.
- Opened the Android chat message content parser as an internal testable helper and added coverage for closed fenced code blocks, unclosed fenced code blocks, and malformed fences without a newline.
- Used one GPT-5.5 read-only Android chat UI audit subagent for this workstream. No GPT-5.3-Codex-Spark subagent was used, and the subagent was closed after completion.

Verification after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`

### 2026-06-26 No-Device Cloud Model-Source Copy Guard

- Added a targeted `script/check_copy_hygiene.py` guard for Android/macOS user-facing copy that rejects explicit `Cloud` model-source labels and wording that makes cloud models sound default, recommended, or preferred.
- Kept the guard scoped to user-facing app resources/source so protocol/schema/docs references, implementation enum values, and provider names can still use cloud/source terminology where they describe a data contract or provider fact.
- Updated Android and macOS user-facing model-source labels so provider-managed source metadata is no longer displayed as a Cloud model-source label.
- Tightened normal Android chat selection so the standard chat picker and send-state reconciliation use installed runtime-host-local chat models, while embedding models remain separate.
- Tightened runtime-host model routing so LM Studio OpenAI-compatible fallback classifies embedding model names as embedding models, and installed embedding models are not accepted as chat routes by the runtime router or aggregate backend.

Verification after this change:

- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `swift test --filter 'LMStudioBackendTests/testListModelsFallsBackToOpenAICompatibleModels|LocalRuntimeMessageRouterTests/testChatSendInstalledEmbeddingModelReturnsModelNotInstalled|AggregatingLlmBackendResidencyTests/testInstalledEmbeddingModelIsNotRoutedAsChat'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuEnablesOnlyInstalledLocalChatModels --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuShowsOnlyInstalledLocalChatModelsAndPrioritizesRunning --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuSearchMatchesModelIdentityProviderAndSource --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectedModelSendStateRequiresInstalledModelInCurrentList --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationOnlyAutoSelectsChatWhenSelectionIsEmpty -Pkotlin.incremental=false`

### 2026-06-26 No-Device Android Runtime Cleanup And Provider Detail Redaction

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited the Android trusted-runtime route-refresh cleanup path with one GPT-5.5 worker subagent, audited Android chat auto-scroll behavior with one GPT-5.5 read-only subagent, and audited the next no-device safety gap with one GPT-5.5 read-only subagent. No GPT-5.3-Codex-Spark subagent was used, and all subagents were closed after completion.
- Audited macOS Advanced Connection QR readiness copy with one GPT-5.5 read-only subagent. No GPT-5.3-Codex-Spark subagent was used, and the subagent was closed after completion.
- Fixed a stale route-refresh cleanup gap: `closeRuntimeConnection()` now clears the pending route-refresh request id as well as cancelling the lease/retry job.
- `forgetTrustedRuntime()` now closes the active runtime connection before removing trusted runtime state, so a forgotten runtime cannot keep an authenticated channel, scheduled route refresh, or pending refresh request alive.
- Added Android ViewModel regression coverage for manual disconnect and forget-trusted-runtime paths, proving delayed route-refresh retry jobs do not send another `route.refresh` after cleanup.
- The tests keep relay-route cleanup on the runtime-mediated path and fail if the route-refresh cleanup flow falls back to direct TCP.
- Extended Android connection cleanup so pending runtime-owned chat rename requests are also cleared on disconnect, matching existing cleanup for lifecycle, history, memory, suggestions, title, and route-refresh requests.
- Redacted Android provider status detail messages before storing them in UI state and again before rendering diagnostics. Safe product-level provider copy remains visible, but backend URLs, local model ports, and provider API paths are hidden from the client UI.
- Extended the Android provider diagnostic redaction guard to route/relay/pairing secrets. `route_token`, `routeToken`, `relay_secret`, `relaySecret`, `pairing_secret`, and compact `rt`/`rs` query material are now suppressed from runtime-visible error details, provider messages, and provider error-code display.
- Provider diagnostics now render only when at least one sanitized message or sanitized structured code remains, so a fully redacted provider status cannot open an empty diagnostics panel.
- `script/check_copy_hygiene.py` now requires Android source and tests to keep the endpoint and route-secret redaction guards in place.
- Added an Android interaction-feedback policy so ordinary taps, selection changes, and toggles use a lighter haptic feedback path while destructive and clipboard actions remain distinct.
- Replaced direct high-frequency `LongPress` feedback calls in the Android chat composer, navigation drawer, permanent navigation rail, model picker, search clear buttons, settings sections, pairing actions, route notices, memory controls, and QR scanner controls with the shared policy.
- Added unit coverage for the haptic policy and selection-change behavior, and confirmed no direct `LongPress` or `TextHandleMove` haptic calls remain in the main Android UI files outside the policy helper.
- Made Android route-safety notices actionable from the Status and Settings connection surfaces. Missing, expired, incomplete, or failed remote route states now resolve to a "scan latest QR" action, while a trusted runtime with a usable saved route resolves to a connect action.
- Route availability error notices now share the same action policy instead of always hard-wiring the route action to QR scanning. Remote route failures still prefer a fresh QR, preserving QR-first route refresh.
- Refined Android chat auto-scroll so incoming assistant-only appended messages no longer pull the user away from older messages. New local user-send bursts still scroll to the latest row, and streaming deltas continue to follow only when the list is already near the bottom.
- Refined macOS Advanced Connection QR readiness copy so a prepared-but-not-ready relay route now distinguishes stopped, connecting, reconnecting, failed, and ready states instead of showing one generic start/wait message.
- Added English, Korean, Japanese, Simplified Chinese, and French localization for the new relay QR readiness states.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.disconnectCancelsScheduledRouteRefreshRetry --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.forgetTrustedRuntimeClosesConnectionAndClearsPendingRouteRefresh -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderStatusesPreserveSafeBackendDetails --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderStatusesRedactBackendEndpointDetails --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.disconnectClearsPendingChatSessionRenameRequests --tests com.localagentbridge.android.AppNavigationTest.providerDiagnosticMessageRedactsBackendEndpointDetails -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailRedactsRouteSecretDetails --tests com.localagentbridge.android.AppNavigationTest.providerDiagnosticMessageRedactsRouteSecretDetails --tests com.localagentbridge.android.AppNavigationTest.providerDiagnosticCodeRedactsUnsafeCodes --tests com.localagentbridge.android.AppNavigationTest.providerDiagnosticsHiddenWhenAllDetailsAreRedacted --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderStatusesRedactRouteSecretDetails --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderSafeCodePreservesStructuredCodesOnly -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.aetherLinkHapticPolicyKeepsOrdinaryActionsLightweight --tests com.localagentbridge.android.AppNavigationTest.aetherLinkHapticPolicyKeepsStrongActionsDistinct --tests com.localagentbridge.android.AppNavigationTest.selectionChangeHapticOnlyRunsWhenSelectionChanges -Pkotlin.incremental=false`
- `rg -n "performHapticFeedback\\(HapticFeedbackType\\.LongPress\\)|performHapticFeedback\\(HapticFeedbackType\\.TextHandleMove\\)" apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt` returns no matches
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.routeNoticeActionScansQrWhenNoRuntimeIsTrusted --tests com.localagentbridge.android.AppNavigationTest.routeNoticeActionScansQrWhenTrustedRuntimeNeedsDifferentNetworkRouteRefresh --tests com.localagentbridge.android.AppNavigationTest.routeNoticeActionConnectsWhenTrustedRuntimeHasUsableRelayRoute --tests com.localagentbridge.android.AppNavigationTest.routeNoticeActionStaysInformationalWhenAlreadyConnected --tests com.localagentbridge.android.AppNavigationTest.routeAvailabilityNoticeUsesScanQrForRemoteRouteFailureInsteadOfGenericConnect -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollFollowsStreamingWhenAlreadyNearLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForStreamingDeltas --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollKeepsInitialAndNewMessageJumpBehavior --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForAssistantOnlyAppends --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDetectsUserSendBurstOnlyWhileStreaming --tests com.localagentbridge.android.AppNavigationTest.jumpToLatestChatButtonShowsOnlyWhenScrolledAwayFromLatestMessage -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_docs_hygiene.py`

### 2026-06-25 No-Device Private Overlay QR Relay Scope

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Added `relay_scope=private_overlay` to the QR route policy. Scope-less private/CGNAT/ULA relay literals are still rejected by the Android parser, but a QR that explicitly marks a user-controlled VPN, tunnel, or private-overlay route can now carry `10.x`, `100.64.x`, `172.16-31.x`, `192.168.x`, or ULA IPv6 relay addresses without being mistaken for stale same-network direct IP fallback.
- Updated Android trusted-runtime route persistence and route planning so private overlay relay routes survive restart and are attempted when their `relay_secret`, `relay_expires_at`, and `relay_nonce` lease material is still valid.
- Updated the macOS companion and RuntimeDevServer QR generation paths to support `relay_scope=private_overlay` for private/CGNAT/ULA relay literals. The macOS GUI now requires explicit private-overlay opt-in before it emits that scope. Loopback remains `relay_scope=usb_reverse` and debug-only; loopback, `.local`, unspecified, link-local, and multicast relay hosts are still blocked for normal remote QR.
- Updated the macOS Advanced Connection Setup flow so private relay hosts require a deliberate VPN/tunnel/private-overlay opt-in before they can be QR-ready. A QR is still generated only after a relay lease is prepared and the relay route is ready.
- Updated `script/verify_pairing_qr.swift` and `script/android_pairing_deeplink_smoke.sh` so private overlay QR routes can be verified with explicit scope/flags while default smoke paths still fail closed for accidental private fixed-IP routes.

### 2026-06-25 No-Device Development Relay Allocation Token

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Hardened the development relay allocation path used by QR-only different-network testing. `AetherLinkRelay` can now require an allocation token before issuing route material, so a public/VPN/tunnel test relay is not an open route-material minting endpoint.
- Extended the relay line protocol from `AETHERLINK_RELAY allocate <route_token> [relay_secret]` to also accept `allocation_token=<token>` while preserving the old development format.
- Wired `AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN` / `AETHERLINK_RELAY_ALLOCATION_TOKEN` through the runtime relay allocator and RuntimeDevServer bootstrap path.
- Updated `script/run_allocation_relay.sh`, `script/run_different_network_dev_runtime.sh`, and `script/no_adb_external_relay_pairing_smoke.sh` so relay startup, preflight, and QR emit-only smoke can use the allocation token consistently.
- Documented that the allocation token gates route-material issuance only; trusted-device pairing, runtime identity pinning, and challenge-response authentication still gate runtime commands.

Verified after this change:

- `swift test --filter RelayAllocationTests`
- `swift test --filter LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorPassesBootstrapAllocationToken`
- `swift build --target RuntimeDevServer`
- `bash -n script/run_allocation_relay.sh script/run_different_network_dev_runtime.sh script/no_adb_external_relay_pairing_smoke.sh`
- `script/run_allocation_relay.sh --dry-run --allocation-token allocation-token-1`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 43171 --start-local-relay --emit-only --allocation-token allocation-token-1 --work-dir /tmp/aetherlink-token-relay-qr-check`

### 2026-06-25 No-Device macOS QR Route Readiness Surface

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited the macOS Pairing QR route-readiness flow with one GPT-5.5 read-only subagent. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.
- Added a published `remoteRoutePreparationIssue` state on the macOS companion model. Automatic route allocation failures, unreachable allocated connection addresses, route lease refresh failures, missing route secrets, and relay connection failures now surface as structured state instead of only logs.
- Updated the macOS Pairing QR empty state, route notice, Advanced Connection Setup panel, and Status overview to show actionable route-preparation copy when a QR cannot be generated because cross-network connection details are unavailable or failed.
- Kept the normal QR-first flow unchanged: normal pairing still requires complete remote route material for different-network QR payloads, while local/direct endpoint material remains diagnostic-only.
- Added English, Korean, Japanese, Simplified Chinese, and French localization for the new route-preparation failure copy.
- Strengthened macOS localization and copy-hygiene guards so the new route-preparation UI path remains visible when needed and route diagnostics still stay hidden during the normal automatic-route flow.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRemoteRoutePreparationIssueWhenBootstrapAllocationThrows`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRelayConnectionStatus`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsPrivateRemoteRouteAllocationWithoutDirectFallback`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 -m py_compile script/check_macos_localization.py script/check_copy_hygiene.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`

### 2026-06-25 No-Device Runtime-Owned Chat Storage Boundary

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited runtime-host chat persistence and mobile local history with one GPT-5.5 read-only subagent. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.
- Confirmed AetherLink Runtime already records chat processing events to a runtime-host JSONL store: requests, assistant deltas, reasoning deltas, completion usage, cancellation, errors, generated titles, session summaries, and archive/restore/delete lifecycle events.
- Added runtime session summary processing metadata: `last_event`, `last_finish_reason`, and `last_error_code`. This lets clients display the latest runtime-side processing state without becoming the durable transcript authority.
- Updated the Android protocol model and protocol schema for the new optional runtime summary fields.
- Changed Android device storage behavior so runtime-owned chat sessions keep local metadata such as title, model, status, message count, and processing metadata, but runtime-owned message bodies are removed from the persisted SharedPreferences snapshot. Active in-memory UI state can still show the current stream, and transcripts should be rehydrated from AetherLink Runtime through `chat.messages.list`.
- Kept local-only drafts/notes unaffected by this redaction path.

Verified after this change:

- `swift test --filter 'LocalRuntimeMessageRouterTests/testRuntimeChatStoreSessionSummaryExposesCancelledAndErrorProcessingState|LocalRuntimeMessageRouterTests/testRuntimeChatStoreListsSessionsAndMessages|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotDropsRuntimeOwnedMessageBodiesButKeepsLocalDrafts --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummarySyncReplacesStaleRuntimeOwnedSessions -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`

### 2026-06-25 No-Device Cross-Platform QR Contract Guard

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited the current runtime-generated QR path and Android QR/deeplink parsing path with two GPT-5.5 read-only subagents. No GPT-5.3-Codex-Spark subagent was used, and both audits were closed after completion.
- Confirmed the default runtime QR flow stays `remoteRequired`: it refuses to create a normal pairing QR without complete remote route material, while local/direct endpoint material remains diagnostic-only.
- Tightened `packages/protocol-schema/pairing-qr.schema.json` so URL query numeric fields accept the real decoded representation: either typed integers or digit strings for ports and relay expiration values.
- Expanded `script/check_protocol_schema.py` so protocol schema checks also verify the shared compact relay QR fixture includes complete remote route fields, omits local direct endpoint fields, uses `rsc=remote`, and keeps relay port/expiration as digit strings.
- Added Android core pairing parser coverage for `shared/protocol/fixtures/macos-compact-relay-pairing-uri.txt`, so the parser itself fails if the Swift-generated compact relay QR fixture stops being accepted.
- Added Android ViewModel regression coverage that accepted compact relay QR pairing preserves `relayScope = "remote"` through trusted runtime reconnect planning.

Verified after this change:

- `python3 script/check_protocol_schema.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests.testCompactPairingQRCodePayloadMatchesSharedRelayFixture`
- `python3 script/check_docs_hygiene.py`

### 2026-06-25 No-Device Android Quiet Chat Composer Guard

- The Android phone is currently disconnected, so physical-device install, screenshots, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Confirmed the Android chat composer does not draw a visible generic input placeholder. `Message` remains only as an accessibility content description, not visible placeholder text.
- Added a small Android UI contract seam for the composer input accessibility label and the intentionally absent visual placeholder.
- Added unit coverage that keeps the composer accessibility label while requiring the visual placeholder resource to stay absent.
- Expanded copy hygiene so future `chat_input_placeholder`, `composer_placeholder`, or `placeholderText` additions are flagged before generic prompt copy returns to the composer.
- Used one GPT-5.5 read-only audit subagent for Android chat-composer review. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.

Verified after this change:

- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_docs_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt script/check_copy_hygiene.py`

### 2026-06-25 No-Device Platform-Neutral Copy Guard

- The Android phone is currently disconnected, so physical-device install, screenshots, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited normal Android and macOS product UI copy for platform-specific wording such as `Android`, `Mac`, `macOS`, `Windows`, `iPhone`, and `iOS`. Current product UI copy is already runtime/client neutral.
- Added a copy hygiene rule that blocks those platform-specific product UI terms from returning to Android resources/source, macOS app resources/source, runtime source, and provider-facing user copy.
- Expanded copy hygiene coverage to macOS `Pairing` source because pairing rejection/result messages are user-visible through protocol responses.
- Kept developer diagnostic script wording out of the platform-neutral UI rule so adb/local setup instructions can still name concrete tooling where needed.
- Used one GPT-5.5 read-only audit subagent for platform-neutral copy review. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.

Verified after this change:

- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- script/check_copy_hygiene.py`

### 2026-06-25 No-Device Android Chat Polish And Relay Auth Copy

- The Android phone is currently disconnected, so physical-device install, screenshots, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Tightened Android AI-generated next-question chips so long suggestions stay compact at two lines with ellipsis. This keeps the chat surface closer to a clean ChatGPT-style follow-up prompt row instead of allowing a single suggestion to push the composer upward.
- Added a small regression seam for the suggested-question compactness policy.
- Wired the existing `route_diagnostic_relay_auth_failed` diagnostic into Android route notices and runtime-error diagnostics. Relay authentication failures now guide users to scan a fresh QR from the trusted runtime instead of dropping the diagnostic detail.
- Added English, Korean, Japanese, Simplified Chinese, French, and default Android strings for the relay-auth diagnostic.
- Used one GPT-5.5 read-only audit subagent for Android chat UI polish review. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayReceiveAuthenticationFailureUsesRouteAuthError -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/main/res apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`

### 2026-06-25 No-Device Android QR Failure Classification

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Audited the Android QR/deeplink path after the headless runtime smoke passed. Camera scan and deeplink both feed `trustRuntimeFromPairingQr`, while the parser intentionally rejects loopback, local, private, or `.local` relay hosts for normal remote pairing.
- Added a dedicated Android UI error for scanned relay QR payloads whose relay host cannot be reached from the client route policy. These QR payloads now report `pairing_relay_route_rejected` with `route_diagnostic_relay_qr_unreachable` instead of falling back to a generic invalid QR error.
- Wired the new error into the route-availability notice flow so the chat empty state and bottom error behavior guide the user back to scanning a latest QR with reachable connection details.
- Added English, Korean, Japanese, Simplified Chinese, French, and default Android strings for the new relay-route QR failure.
- Used one GPT-5.5 read-only audit subagent for Android QR/deeplink pairing review. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest -Pkotlin.incremental=false`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/main/res apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`

### 2026-06-25 No-Device Headless QR Pairing Verification

- The Android phone is currently disconnected, so physical-device install, camera-based QR scan, app-level pairing completion, haptic feel, real device streamed chat/cancel, and true external-network runtime connectivity were not validated in this pass.
- Confirmed the existing headless runtime smoke already exercises the QR pairing contract end to end: it starts the runtime, reads the emitted `aetherlink://pair` URI, parses the QR fields, sends `pairing.request`, authenticates a fresh connection with challenge-response, calls `runtime.health`, runs model/chat/cancel checks, and verifies trusted-route reconnect.
- Verified the same headless pairing/auth/runtime loop over the development relay route, proving the code path no longer depends on a fixed same-network IP for the scripted relay case.
- Verified the no-ADB QR artifact path can allocate a development relay route, emit the pairing URI, render a QR PNG, and decode it back successfully.
- Used one GPT-5.5 read-only audit subagent for no-device QR smoke review. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.

Verified after this change:

- `./script/runtime_authenticated_mock_smoke.swift`
- `./script/runtime_authenticated_mock_smoke.swift --relay`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only`

Remaining before claiming user-visible QR pairing works on a phone:

- Reconnect the Android phone.
- Install the latest debug APK.
- Scan a fresh runtime QR with the device camera.
- Confirm the app sends `pairing.request`, receives `pairing.result`, persists the trusted runtime, reconnects without rescanning, and can call `runtime.health`.
- Repeat with a mutually reachable relay route from a different network, not a loopback/local diagnostic relay.

### 2026-06-25 No-Device QR Contract And Runtime Identity Hardening

- The Android phone is currently disconnected, so physical-device install, optical QR scan, pairing completion, haptic feel, streamed chat/cancel, and different-network runtime connectivity were not validated in this pass.
- Aligned the pairing QR schema with the current compact relay QR fixture by allowing `remote` route scope on `relay_scope`, `remote_scope`, and compact `rsc`.
- Strengthened the protocol schema guardrail so `remote` route scope must stay accepted by the pairing QR schema.
- Tightened Android saved-runtime relay route matching so a stored trusted runtime with pinned fingerprint or public key will not prepare a relay route for a matching device id with mismatched identity material.
- Added a focused Android unit test proving mismatched pinned runtime fingerprint/public key prevents relay route preparation.
- Used one GPT-5.5 read-only audit subagent for QR pairing flow review. No GPT-5.3-Codex-Spark subagent was used, and the audit was closed after completion.

Verified after this change:

- `python3 script/check_protocol_schema.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest :core:pairing:test :core:transport:test -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeRemoteRoutePlanner.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt packages/protocol-schema/pairing-qr.schema.json script/check_protocol_schema.py docs/progress.md`

### 2026-06-25 No-Device Android Composer Accessibility Guard

- The Android phone is currently disconnected, so physical-device install, optical QR scan, pairing completion, haptic feel, streamed chat/cancel, and different-network runtime connectivity were not validated in this pass.
- Fixed the Android chat composer accessibility state so the send button no longer reports `Ready to send` when the only blocker is an empty message/attachment set.
- Updated the not-installed model hint across English, Korean, Japanese, Simplified Chinese, French, and the default Android resources so the app tells users to install a model or choose an installed model before sending.
- Strengthened Android string hygiene in the current workstream so stale tab/composer labels and direct Ollama/LM Studio endpoint wording fail guardrails if reintroduced.
- Used one GPT-5.5 read-only explorer to audit Android chat UI/state behavior. No GPT-5.3-Codex-Spark subagent was used, and the explorer was closed after completion.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 No-Device macOS Localization Key Hygiene

- The Android phone is currently disconnected, so physical-device install, optical QR scan, pairing completion, haptic feel, streamed chat/cancel, and different-network runtime connectivity were not validated in this pass.
- Removed unused stale macOS localization keys such as `Desktop Runtime`, `Runtime Logs`, and old `on this device` model-provider fallback keys that were no longer referenced by Swift source.
- Updated active macOS Remote Route diagnostics source keys from earlier route-host / `this device` wording to connection-address and `runtime host` wording, matching the product direction that AetherLink should not read like a fixed desktop-only runtime.
- Strengthened `script/check_macos_localization.py` so those stale keys fail the macOS localization guardrail if reintroduced.
- Used one GPT-5.5 read-only explorer to audit stale platform-specific user-facing copy. No GPT-5.3-Codex-Spark subagent was used, and the explorer was closed after completion.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`

### 2026-06-25 No-Device QR Pairing Action And Route Failure Copy

- The Android phone is currently disconnected, so physical-device install, optical QR scan, pairing completion, haptic feel, streamed chat/cancel, and different-network runtime connectivity were not validated in this pass.
- Added direct `Generate Pairing QR` and `Generate New QR` actions inside the macOS Pairing screen. Users no longer need to leave the Pairing screen for the Status quick action when the QR is missing or expired.
- Tightened Android remote-route failure copy across English, Korean, Japanese, Simplified Chinese, French, and the default resources so unreachable saved routes explicitly tell the user to prepare remote connection details in AetherLink Runtime and then scan the latest QR.
- Used one GPT-5.5 read-only explorer to audit Android QR pairing UX/error routing. No GPT-5.3-Codex-Spark subagent was used, and the explorer was closed after completion.

Verified after this change:

- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 No-Device QA Evidence Checkpoint

- The Android phone is currently disconnected, so physical-device install, optical QR scan, pairing completion, haptic feel, live language switching, streamed chat/cancel, and different-network runtime connectivity were not validated in this checkpoint.
- Updated `docs/qa-evidence.md` so current no-device checks are separated from historical screenshots/XML captures and from the remaining physical-device acceptance work.
- Recorded that Android/macOS language guardrails, Android compile, macOS build, runtime model-route tests, and no-device relay/QR smoke checks are source-level or no-device evidence only.
- Reaffirmed that no GPT-5.3-Codex-Spark subagent was used for this workstream.

Verified after this change:

- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- docs/qa-evidence.md docs/progress.md`

### 2026-06-25 No-Device Android Language Guardrail

- The Android phone is intentionally disconnected for this pass, so no APK install or physical-device locale switching validation was run.
- Strengthened `script/check_android_string_parity.py` so it now verifies the Android app language enum and defaults, not only string resource key parity.
- Superseded on 2026-06-26: the checker now fails if Android visible language support drifts away from English, Korean, Japanese, Simplified Chinese, and French only; if the UI or persisted app language defaults stop being English; or if language selector labels are missing from the base resources.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 No-Device macOS Language Guardrail

- The Android phone is intentionally disconnected for this pass, so no phone pairing, QR scan, or client/runtime language interaction was validated.
- Strengthened `script/check_macos_localization.py` so it now verifies the macOS runtime app language selector itself, not only `Localizable.strings` parity.
- The checker now fails if the macOS app language list drifts away from English, Korean, Japanese, Simplified Chinese, and French, if the default stops being English, if the language storage key changes unexpectedly, or if language picker labels are missing from the base locale.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `swift build --target LocalAgentBridge`

### 2026-06-25 No-Device macOS Default Language Selector

- The Android phone is intentionally disconnected for this pass, so no phone pairing, QR scan, or client/runtime language interaction was validated.
- Added a macOS app localization layer that defaults AetherLink Runtime UI strings to English when no app language has been chosen.
- Added a compact language picker to the macOS runtime sidebar with English, Korean, Japanese, Simplified Chinese, and French options.
- The picker stores an app-local language tag and rerenders the macOS runtime window with the selected locale. It does not change model provider language, prompts, runtime protocol language, or device pairing semantics.

Verified after this change:

- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`

### 2026-06-25 No-Device Android Default Language Alignment

- The Android phone is intentionally disconnected for this pass, so no APK install or physical-device locale switching validation was run.
- Restored the Android first-run language default to English, matching the product requirement that the default UI language is English.
- Superseded on 2026-06-26: the explicit `Device language` Settings option was removed. Runtime-generated chat titles and suggested next questions now receive the normalized app language, and legacy blank/system stored values fall back to English.
- Corrupt or unsupported persisted language tags now sanitize back to English instead of silently switching the app to device language.

Verified after this change:

- Superseded command name update on 2026-06-26: use `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataDefaultsToEnglishAppLanguage --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.appLanguageTagHelperNormalizesSupportedAndInvalidTags --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 No-Device Runtime Model Route Guard

- The Android phone is intentionally disconnected for this pass, so no physical model-picker, chat send, or provider-switch validation was run.
- Used one GPT-5.5 worker subagent for the macOS runtime model-list semantics pass. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- Confirmed Ollama and LM Studio adapters derive model lists from backend responses and do not synthesize default model suggestions.
- Tightened `AggregatingLlmBackend` so chat routing now requires the requested model to match an installed model reported by the aggregated runtime model list.
- Unknown unqualified model names no longer fall back to Ollama, and provider-qualified model names must be reported by that exact provider before chat is routed.

Verified after this change:

- `swift test --filter AggregatingLlmBackendResidencyTests`
- `swift test --filter OllamaBackendTests`
- `swift test --filter LMStudioBackendTests`

### 2026-06-25 No-Device Android Input Haptic Polish

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, file-picker interaction, or physical-device haptic validation was run.
- Added haptic feedback to manual QR pairing text submit/cancel actions and pending attachment removal chips.
- Kept QR trust validation, attachment payload handling, and chat send/cancel behavior unchanged.
- A GPT-5.5 worker subagent was also opened in parallel to audit macOS runtime model-list semantics. GPT-5.3-Codex-Spark was not used.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 No-Device Android Haptic Polish

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, or physical-device haptic validation was run.
- Added haptic feedback to smaller Android interactions that previously felt silent: clearing chat history search, clearing the chat model picker search, closing the QR scanner from either cancel surface, and requesting camera permission from the QR scanner permission state.
- Kept existing pairing, model selection, send/cancel, suggestion, archive/delete, and settings haptic behavior unchanged.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 No-Device Runtime Locale Hint Cleanup

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, optical QR validation, or physical-device localization check was run.
- Superseded on 2026-06-26: legacy blank/system stored language values normalize to English instead of following the device language.
- Android runtime requests for automatic chat titles and suggested next questions now send the explicit normalized app language to the runtime.
- Explicit app language choices control runtime-generated titles and suggested questions. Unsupported or legacy blank language values fall back to English, matching the default UI fallback.

Verified after this change:

- Superseded command name update on 2026-06-26: use `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateBuildsAfterFirstCompletedExchange --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateRefreshesRuntimeHistoryWhenLatestAssistantHasNoSuggestions --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 No-Device Suggested Question Readability Cleanup

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, optical QR validation, or physical-device suggested-question UI check was run.
- Used one GPT-5.5 read-only audit subagent for generated assistant UI and localization quality. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- Hardened macOS runtime suggested-question parsing so strict JSON remains preferred, fenced JSON remains accepted, and numbered/bulleted fallback lists are accepted only when lines clearly start with a list prefix.
- Cleaned generated suggested-question strings on both macOS Runtime and Android cache paths by stripping leading list numbers, bullets, and wrapping quotes, then deduplicating case-insensitively before display/storage.
- Reworked Android suggested-question chips from a horizontally scrolling row into a wrapping `FlowRow`, with up to three visible lines per chip so Japanese, Chinese, Korean, French, and longer English suggestions are less likely to be truncated.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsEmptySuggestionsForInvalidJSON --filter LocalRuntimeMessageRouterTests/testChatSuggestionsRequestFallsBackToNumberedLocalizedList --filter LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsStructuredSuggestions`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionsAttachToLatestAssistantMessage --no-daemon -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`

### 2026-06-25 No-Device Fenced JSON Generation Cleanup

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, optical QR validation, or physical-device suggested-question/title UI check was run.
- Hardened macOS runtime parsing for generated chat titles and suggested next questions when local models wrap the required JSON in a fenced code block labelled `json`.
- Direct strict JSON remains the preferred path, fenced JSON is accepted as a compatibility cleanup, and malformed fenced title JSON now returns an empty title instead of saving the code fence as a visible chat title.
- Added runtime-router regression tests for fenced suggested questions, fenced chat titles, and malformed fenced title JSON.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testChatSuggestionsRequestAcceptsFencedStructuredSuggestions`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatTitleRequestAcceptsFencedStructuredTitle`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsEmptySuggestionsForInvalidJSON`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatTitleRequestReturnsEmptyTitleForInvalidJSONOrEmptyOutput`
- `swift build --target LocalAgentBridge`

### 2026-06-25 No-Device Runtime Title Thinking Cleanup

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, optical QR validation, or physical-device title/suggestion UI check was run.
- Tightened macOS runtime automatic chat-title generation so inline `<think>` / `<thinking>` text returned by a local model is stripped before parsing and storing the generated title.
- This makes the automatic first-turn title path match the explicit `chat.title.request` path and prevents reasoning text from becoming a visible chat title when a backend leaks thinking into ordinary text deltas.
- Added a runtime-router regression test covering automatic title generation after the first assistant response with inline thinking followed by JSON title output.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendGeneratedRuntimeTitleStripsInlineThinking`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse`

### 2026-06-25 No-Device Documentation Boundary Hygiene

- The Android phone is intentionally disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.
- Standardized current README and docs wording around AetherLink Runtime, trusted runtime, runtime host, client target, and runtime target.
- Removed stale `companion runtime` and `runtime/server` wording from current docs where it could read like a fixed platform or cloud/server product boundary.
- Clarified that authenticated runtime sessions and QR relay-frame encryption are current development foundations, while production end-to-end transport encryption remains future hardening work.
- Added `script/check_docs_hygiene.py` so current docs fail fast on stale runtime labels, `runtime/server` wording, OS-specific desktop-host copy, and premature production encryption claims.

Verified after this change:

- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_protocol_schema.py`
- `git diff --check`

### 2026-06-25 No-Device Android Chat Polish Guard

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, or physical-device screenshot was run.
- Re-audited the Android chat empty state and AI next-question suggestion flow with one GPT-5.5 read-only subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- Confirmed ready empty chat already stays visually blank: the central empty state renders only for pairing/connection/route/streaming blockers, while connected usable chats keep the conversation area clear.
- Confirmed AI-generated next-question chips show only after a latest assistant message has visible output and generation is no longer streaming.
- Added a regression test so `chatSuggestionsRequestCandidate` skips a blank assistant placeholder and does not request suggestions before real assistant output exists.
- Updated Android settings copy across English, Korean, Japanese, Simplified Chinese, French, and default resources so the model-access note says this device controls the session instead of naming a client role.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest`
- `git diff --check`

### 2026-06-25 No-Device Android Pairing-First Title Polish

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, or physical-device screenshot was run.
- Confirmed the Android app already uses a drawer-style shell, keeps Settings in the drawer, opens Settings for first-run pairing, and puts chat model selection in the chat top bar.
- Refined the first-run and pending-QR route title behavior: when the app routes to Settings because pairing is required or a QR route is pending, the top app bar now says `Pair AetherLink` instead of a generic settings title. Normal trusted-runtime Settings management still says `Settings`.
- Added navigation tests for the pairing title, pending-route title, and normal trusted Settings title.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 No-Device macOS Runtime Localization Polish

- The Android phone is intentionally disconnected for this pass, so no APK install, camera QR scan, or physical-device route validation was run.
- Audited the macOS AetherLink Runtime UI/localization surface with one GPT-5.5 read-only subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- Softened remote-route copy so it no longer reads like production end-to-end transport encryption is complete. The status surface now says current QR route protection is enabled and model providers remain private inside AetherLink Runtime.
- Reworded pairing instructions across English, Korean, Japanese, Simplified Chinese, and French so the awake/sleep instruction clearly refers to the runtime host, not an ambiguous device.
- Reworded the visible log summary for the Ollama health success event to the provider-neutral `Model provider health check passed`, while keeping the raw event string as the technical matcher.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `swift build --target LocalAgentBridge`
- `git diff --check`

### 2026-06-25 Physical Device Disconnected For Mac-Only Pass

- The Android phone is intentionally disconnected for this pass.
- Do not treat the current state as an on-device QR pairing validation. Physical install, camera scan, optical QR decoding, and different-network runtime connection testing must wait until the phone is reconnected.
- Continued only no-device work: macOS companion copy/localization checks, documentation updates, and static validation.
- Subagent usage remains constrained for this session: do not use GPT-5.3-Codex-Spark; use GPT-5.5/inherited-model agents only when delegation is useful.

### 2026-06-25 No-Device Relay QR Readiness And Runtime Log Polish

- Rechecked the Android chat reasoning surface while the phone is disconnected. Current Android code already separates runtime `reasoning`/`thinking` deltas and inline `<think>` blocks from final answer text, shows reasoning dimmed, limits the collapsed preview to about three lines, and allows expansion.
- Used one GPT-5.5 read-only audit subagent for this Android reasoning review. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- Re-ran the authenticated mock relay smoke. Pairing, P-256 challenge-response authentication, `runtime.health`, `models.list`, `models.pull`, streaming `chat.send`, `chat.cancel`, and saved trusted relay reconnect all passed through the relay route.
- Re-ran the no-ADB external relay QR emit-only smoke. It started an allocation-required relay, generated the pairing URI, rendered the QR PNG, and verified QR PNG round-trip decode without using a physical device.
- Polished `RuntimeDevServer` startup logging so a relay-backed QR route no longer prints USB reverse or fixed `127.0.0.1` connection instructions as the normal path. Relay runs now tell the user to scan the emitted `aetherlink://pair` QR/URI and explicitly state that no USB port forwarding, fixed network address, or model-provider address is required for that route.
- Cleaned user-facing development script output in the USB install/smoke, runtime launcher, pairing deep-link smoke, no-ADB relay smoke, and allocation relay helper so USB loopback and local ports read as diagnostics instead of the product connection model.
- Reworded the real Ollama smoke skip message so it tells the user to start Ollama on the runtime host instead of exposing a direct provider loopback URL as the action.
- Updated the different-network development runtime helper so help/error text uses trusted-device and runtime-host wording instead of generic client or machine wording.
- Updated RuntimeDevServer development pairing info so newly emitted `AETHERLINK_DEV_PAIRING_INFO` uses canonical `runtime_device_id`, `runtime_name`, and `runtime_key_fingerprint` fields. Legacy `mac_*` QR aliases remain accepted by clients for compatibility, but the current dev output no longer emits them as the primary visible fields.
- Added `AETHERLINK_DEV_RUNTIME_DEVICE_ID` and `AETHERLINK_DEV_RUNTIME_FINGERPRINT` as runtime-first development identity environment names while keeping the older `AETHERLINK_DEV_MAC_*` names as compatibility fallbacks.
- Extended `script/check_copy_hygiene.py` to include `RuntimeDevServer` source logs and user-facing shell smoke/helper scripts, so QR-first, OS-neutral, no-direct-provider wording is guarded in the development runtime surface as well as the app UI/resources.
- Added `docs/qa-evidence.md` and ignored newly generated `artifacts/*.png` / `artifacts/*.xml` files by default. Existing historical captures remain in place, but generated artifacts must be refreshed and explicitly referenced before they are treated as current proof of UI, QR, or route behavior.
- The Android phone remains disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `swift build --target RuntimeDevServer`
- `script/runtime_authenticated_mock_smoke.swift --relay`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 45`
- `python3 script/check_copy_hygiene.py`
- `bash -n script/*.sh`
- `git diff --check`

### 2026-06-25 macOS Localization Placeholder Guard

- Strengthened `script/check_macos_localization.py` so it now checks NSString-style format placeholder parity across English, Korean, Japanese, Simplified Chinese, and French `Localizable.strings` files.
- The checker still verifies `.strings` syntax, parseability, duplicate keys, locale key order/parity, and Swift `NSLocalizedString("...")` source coverage.
- Placeholder comparison preserves order for non-positional placeholders such as `%@` and `%d`, while explicitly positional placeholders can be reordered safely across translations.
- The Android phone remains disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `swift build --target LocalAgentBridge`

### 2026-06-25 Android Localization Placeholder Guard

- Strengthened `script/check_android_string_parity.py` so it now checks duplicate Android string keys and format placeholder parity across English, Korean, Japanese, Simplified Chinese, and French resources.
- The new placeholder guard compares placeholder sets rather than raw order, so translated strings can reorder `%1$s` and `%2$d` while still failing if a placeholder is missing or has the wrong type.
- This makes future Android translation work safer for runtime-formatted copy such as provider status, model metadata, route notices, delete confirmations, and attachment metadata.
- The Android phone remains disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Localization Guardrails And Android Metadata Polish

- Strengthened `script/check_macos_localization.py` so it now scans Swift `NSLocalizedString("...")` literal keys and fails when a key is missing from the English base `Localizable.strings`, in addition to the existing syntax, duplicate-key, order, and locale-parity checks.
- Added the missing macOS `Load models` localization key across English, Korean, Japanese, Simplified Chinese, and French. The strengthened checker caught this immediately.
- Updated Android chat persistence so newly created or still-untitled local chat sessions no longer store the English title `New chat`; legacy `New chat` values are treated as untitled for display and rename editing.
- Updated Android drawer and chat-history settings surfaces so legacy untitled chats render through the localized `untitled_chat` resource rather than showing an English persisted fallback.
- Updated Android attachment metadata so file sizes use Android's localized system formatter and the type/size separator is a localized string resource.
- Used one GPT-5.5 read-only audit subagent for this hardcoded-copy audit. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone remains disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `swift build --target LocalAgentBridge`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 Cross-Platform Runtime Copy Polish

- Audited Android and macOS visible copy for OS-specific, fixed-route, prototype, and direct-provider wording. No normal-flow Mac/Android labels were found.
- Updated Android pairing/security/settings copy so it says AetherLink trusts scanned runtime identities and keeps model access on the trusted runtime, while the client controls the session.
- Renamed Android "Developer diagnostics route" copy to "Advanced diagnostics route" across English, Korean, Japanese, Simplified Chinese, and French so the hidden diagnostics panel reads less prototype-oriented.
- Removed macOS normal pairing fallback wording that mentioned support/development relay addresses. Pairing and Status now describe Route Diagnostics as an exception only when automatic route preparation is unavailable.
- Removed one stale macOS localization key that still contained support/development wording even though its displayed values had already been softened.
- Used one GPT-5.5 read-only audit subagent for this cross-platform copy audit. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone remains disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`

### 2026-06-25 macOS QR Route-Material Copy

- Reworded macOS Pairing, Status, Remote Route Diagnostics, and Logs copy so cross-network pairing reads as a QR-first flow whose QR carries route material, not as a user-facing prerequisite to manually configure a route before QR pairing.
- Kept legacy log-line recognition for older runtime events, but changed the displayed summary to say route material is not ready instead of telling users to configure a remote route first.
- Updated English, Korean, Japanese, Simplified Chinese, and French macOS localization resources in lockstep.
- Used one GPT-5.5 read-only audit subagent for this macOS copy audit. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `swift build --target LocalAgentBridge`
- `swift test --filter LocalRuntimeMessageRouterTests`

### 2026-06-25 Android QR-Only Settings Connection Surface

- Moved Android local discovery UI behind the developer diagnostics flag so normal Settings no longer presents "discover and pick a runtime" as a user flow.
- Kept the trust gate intact: even in diagnostics, a discovered route only gets an action when its advertised identity matches the saved trusted runtime.
- Renamed the discovered-route action from a generic "Use" to "Use trusted connection" across English, Korean, Japanese, Simplified Chinese, and French resources.
- Tightened diagnostics copy so route discovery and host/port entry read as trusted-route/developer diagnostics, not normal fixed-IP setup.
- Added Android helper coverage that keeps discovered-route action copy tied to QR trust state.
- Used one GPT-5.5 read-only audit subagent for this connection-surface pass. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 macOS QR-First Runtime Host Copy

- Polished macOS Status and Pairing copy so the normal setup reads as "generate and scan a pairing QR" instead of route-first setup.
- When automatic remote-route preparation is available, the Status overview now says AetherLink prepares route material automatically as part of QR generation.
- When automatic route preparation is unavailable, Pairing empty-state copy points to Route Diagnostics only as support/development relay-address handling rather than a normal manual setup flow.
- Replaced provider-health guidance that said model providers are checked "on this device" with "runtime host" wording, preserving the future server/runtime target model beyond macOS.
- Updated English, Korean, Japanese, Simplified Chinese, and French macOS localization resources in lockstep.
- Used one GPT-5.5 read-only audit subagent for this macOS copy pass. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `swift build --target LocalAgentBridge`
- `swift test --filter LocalRuntimeMessageRouterTests`

### 2026-06-25 Android Chat Suggestion Chips And Reasoning Label

- Reworked Android suggested next questions from full-width outlined buttons into compact horizontally scrollable chips under the latest assistant answer.
- Renamed the Android reasoning preview label and expand/collapse controls from ongoing "Thinking" wording to completed "Reasoning" wording across English, Korean, Japanese, Simplified Chinese, and French.
- Kept the chat composer free of visible placeholder text; the GPT-5.5 audit suggested an in-field placeholder, but that was intentionally not applied because the user asked to remove unnecessary composer placeholder copy.
- Kept behavior unchanged: suggestions still come from the runtime-mediated `chat.suggestions.request` flow, and tapping a chip still goes through the normal chat composer/send path.
- Used one GPT-5.5 read-only audit subagent for this Android chat-surface pass. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, optical QR validation, or real runtime validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Android Runtime Memory Disconnected UX

- Polished Android Settings memory copy so disconnected runtime-owned memory no longer reads like a hard error.
- When disconnected with no cached memory entries, the panel now says to connect to the trusted runtime to load saved memory instead of claiming no memories exist.
- When cached runtime memory entries are visible while disconnected, the panel now explains that cached memory is read-only until the trusted runtime reconnects.
- Kept behavior unchanged: memory add, pause/resume, delete, and delete confirmation remain disabled unless the app is connected to a trusted runtime.
- Added Android helper coverage for disconnected empty-cache and cached read-only memory copy selection.
- Used one GPT-5.5 read-only audit subagent for this memory UX pass. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Android QR-First Discovery Trust Gate

- Tightened Android local discovery so identity-unknown or metadata-less discovered runtimes no longer show a normal `Use` action in Settings. Only discovered routes that match the saved trusted runtime identity can be selected as a trusted local route.
- Added passive discovery row labels for non-selectable routes: QR-required for unknown/unpaired discovery and not-trusted for mismatched runtime identity.
- Hardened `RuntimeClientViewModel.useDiscoveredRuntime` so internal callers also cannot save a discovered route unless it matches either the saved trusted runtime identity or the pending pairing QR identity.
- Preserved the pending QR flow: a discovered local route can still be accepted before trust is saved when it matches the scanned QR identity.
- Added Android tests for UI route selection gating and runtime-layer trusted/pending pairing discovery selection.
- Used one GPT-5.5 read-only audit subagent for this discovery trust-gate pass. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.discoveredRuntimeSelectionRequiresTrustedIdentityMetadata --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.discoveredRuntimeSelectionCanUsePendingPairingIdentityBeforeTrustIsSaved --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Android Chat History Bulk Action Hide And English Language Default

- Hid Android Settings bulk chat-history actions behind a collapsed "Manage all chats" row. Bulk archive and permanent deletion remain available only after opening that row, and the existing two-step confirmations still guard execution.
- Kept individual chat lifecycle behavior unchanged: active chats show archive, archived chats can restore or enter permanent-delete confirmation, and permanent delete is still scoped to archived chats.
- Kept Android first-run language default as English. Superseded on 2026-06-26: System/Device language is no longer a visible app-language Settings choice, and English remains the fallback for unsupported or legacy blank language values.
- Added Android helper coverage for the bulk-action visibility policy and persisted language default coverage.
- Used one GPT-5.5 read-only audit subagent to identify bounded no-device product gaps. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataDefaultsToEnglishAppLanguage --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Android Runtime Memory Settings Lock

- Locked the Android Settings memory mutation UI until the client is connected to a trusted AetherLink Runtime.
- Cached runtime memory entries remain viewable while disconnected, but add, pause/resume, delete, and delete confirmation actions are disabled until the runtime connection is available.
- Reused the existing localized runtime-required memory error copy in English, Korean, Japanese, Simplified Chinese, and French.
- This keeps memory runtime-owned: Android can present a local cache, but it should not create divergent client-only memory edits while offline.
- Used one GPT-5.5 worker subagent for the bounded Android UI/test slice. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Android Embedding Model Copy Scope Pass

- Tightened Android embedding-model Settings copy so it no longer reads as if embedding-backed semantic search, memory lookup, deep research, or broader retrieval workflows are active UI features.
- The setting now describes only the current concrete action: choosing a separate embedding model exposed by AetherLink Runtime, or choosing no separate embedding model.
- Kept the roadmap boundary intact: embedding-powered retrieval, ranking, indexing, and research remain documented future work in the runtime/server layer.
- Updated English, Korean, Japanese, Simplified Chinese, and French Android string resources together.
- Used one GPT-5.5 worker subagent for the bounded Android localization pass, then manually tightened the final wording. GPT-5.3-Codex-Spark was not used.
- The Android phone is disconnected for this pass, so no physical-device install, screenshots, camera scan, or real runtime validation was run.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `git diff --check`

### 2026-06-25 macOS Remote QR Pairing Copy Pass

- Refined macOS companion copy so QR pairing reads as the normal device flow and manual remote-route fields read as support/development diagnostics.
- Updated English, Korean, Japanese, Simplified Chinese, and French `Localizable.strings` values for remote QR pairing, route diagnostics, trusted-device wording, and model-provider privacy.
- Kept networking behavior unchanged. This pass did not implement production P2P rendezvous, production relay, NAT traversal, or physical QR validation.
- Used one GPT-5.5 worker subagent for the bounded macOS localization pass. GPT-5.3-Codex-Spark was not used.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Android Suggested Next Question Restore Guard

- Audited the Android chat surface after the no-device macOS pass. Current code already removes static example prompts from the empty chat screen, requests AI-generated next questions through the runtime, keeps reasoning collapsed/dimmed with a three-line preview, separates chat and embedding model pickers, and starts unpaired installs in Settings for QR pairing.
- Tightened the runtime-history reentry path: after Android reloads a chat message list from AetherLink Runtime, it now re-requests suggested next questions for the latest assistant answer when that answer has no saved suggestions.
- The refresh path deliberately avoids duplicate suggestion requests when the latest assistant message already has suggestions. Live `chat.done` suggestion requests continue to work as before.
- Kept Android behind AetherLink Runtime. No direct Ollama, LM Studio, or provider URL access was added.
- Used one GPT-5.5 read-only subagent for the Android UI/state audit. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network runtime validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateRefreshesRuntimeHistoryWhenLatestAssistantHasNoSuggestions --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateDoesNotRefreshRuntimeHistoryWhenSuggestionsAlreadyExist --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Android Compact Relay QR Reconnect Guard

- Added Android regression coverage for the compact route-bearing `aetherlink://pair` QR path from parser to trusted runtime restore.
- The new test parses compact QR aliases (`n`, `c`, `rid`, `rn`, `rf`, `rk`, `rt`, `rh`, `rp`, `ri`, `rs`, `rx`, `rrn`, `rsc`), accepts the pairing result, restores the trusted runtime, and verifies automatic reconnect prepares a relay route without using a manual endpoint or saved direct IP address.
- Confirmed direct host/port values embedded alongside relay material are stripped before persistence and reconnect, so the different-network path is relay/overlay material only.
- Used one GPT-5.5 read-only subagent to audit the QR parser and reconnect planner test gap. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network pairing validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 Android Compact Relay QR Scan Filter Guard

- Audited the Android scan/deep-link entry path. Camera scanner results, manual QR payload paste, and pairing deep links all converge on `RuntimeClientViewModel.trustRuntimeFromPairingQr(...)`; the destination wrapper only routes users into Settings while pairing is pending.
- Made the scanner raw-value pairing check testable and stable in JVM unit tests by parsing with `java.net.URI` instead of Android `Uri`, while still trimming scanner-provided raw text before validation.
- Added Android tests proving compact relay QR payloads are accepted by both the deep-link filter and scanner raw-value filter, including scanner strings with surrounding whitespace.
- Used one GPT-5.5 read-only subagent to audit the scan/deep-link path. GPT-5.3-Codex-Spark was not used.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network pairing validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 Android ViewModel Compact Relay QR Pairing Guard

- Added a narrow internal dependency seam to `RuntimeClientViewModel` so QR pairing can be tested with fake transport, fake local stores, fake trusted-runtime store, fake discovery, and fake device identity without launching a real socket, Android Keystore, DataStore, or Bonjour discovery.
- Kept the public Android ViewModel constructor unchanged. Production still wires the real `RuntimeTransportClient`, `RuntimeRelayTcpClient`, `BonjourDiscovery`, `PairingStore`, `DeviceIdentityStore`, `RuntimeLocalStore`, and lifecycle callbacks through the default dependency factory.
- Extracted the QR parse and pending-pairing connection-plan steps used by `trustRuntimeFromPairingQr(...)`, then added a direct ViewModel unit test that calls `trustRuntimeFromPairingQr(...)` with a compact relay QR URI.
- The new test proves compact relay QR pairing uses the relay connector, does not attempt direct TCP, binds relay host/port/id/secret/nonce from the QR route, and sends a `pairing.request` envelope with the expected pairing nonce, code, and client identity.
- Tightened pending pairing route planning so route-bearing relay QR payloads do not start local discovery just because they have no direct endpoint hint. Identity-only QR payloads still start discovery and wait for a reachable route.
- Enabled Android unit-test default return values and added `kotlinx-coroutines-test` so ViewModel coroutine tests can run under JVM unit tests.
- Used one GPT-5.5 read-only subagent to audit the smallest safe ViewModel test seam. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network pairing validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`

### 2026-06-25 Cross-Platform Compact Relay QR Contract Fixture

- Added `shared/protocol/fixtures/macos-compact-relay-pairing-uri.txt` as a canonical macOS-style compact relay QR URI fixture.
- Added Android app-level contract coverage that reads the shared fixture, parses it through `RuntimePairingPayloadParser`, verifies macOS compact aliases and percent-encoding such as `runtime%2Bpublic/key%3D`, confirms no direct endpoint survives, checks relay lease validity before and after expiration, and verifies `RuntimeRemoteRoutePlanner` prepares a relay route with the expected host, port, relay id, frame secret, expiration, and nonce.
- Added macOS contract coverage that generates a compact relay QR with `PairingCoordinator`, normalizes the random pairing nonce/code to fixture values, and compares the generated URI with the shared fixture. This makes the fixture bidirectional: Swift generation and Android parsing now validate the same QR contract.
- Extended the Android accepted-pairing/reconnect guard to use the same shared fixture instead of an inline URI. It now verifies the accepted pairing persists relay host, port, id, frame secret, expiration, and nonce while dropping direct host/port fallback before automatic reconnect planning.
- Added Android client capability coverage for runtime-owned memory. `hello` now advertises `memory.list`, `memory.upsert`, and `memory.delete`, matching the already-active runtime-owned memory command path.
- Used one GPT-5.5 read-only subagent to audit the cross-platform compact relay QR gap. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, optical QR validation, or real different-network pairing validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture`

### 2026-06-25 QR Pairing And Remote Route Testability Pass

- Audited the current QR pairing and different-network route path with a GPT-5.5 read-only subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after the audit.
- Confirmed the current implementation can pair across different networks only when the QR includes complete, fresh, mutually reachable relay route material. Identity-only QR still depends on local discovery and cannot cross unrelated networks by itself.
- Updated Android QR parsing from the app scan path so explicit `route_scope=local_diagnostic` direct-route QR payloads are accepted in debug builds only. Product/default parsing still rejects local direct endpoint QR routes, and relay route QR remains the normal path for different-network work.
- Added injectable time sources to Android remote relay route preparation/planning so relay lease expiry behavior can be tested deterministically instead of depending on wall-clock time.
- Added Android regression tests for saved relay lease and pending pairing relay lease expiry using injected clocks.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or actual different-network QR pairing validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForSavedRelayLease --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForPendingPairingRelayLease --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.pairingRuntimeTargetUsesRelayQrWithoutLocalEndpoint --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:transport:testDebugUnitTest --tests com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparationTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.allowsLocalDirectEndpointOnlyForExplicitDiagnosticParse --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsLocalDirectEndpointQrByDefault --no-daemon -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode`

### 2026-06-25 Platform-Neutral UI Copy Pass

- Continued the user-facing copy cleanup so the product surface speaks in terms of AetherLink, trusted devices, model providers, and routes instead of hard-coding Android, Mac, host-centric, or backend URL language.
- Kept the architecture boundary explicit: client apps control sessions, while AetherLink Runtime mediates all model provider access. Android still must not call Ollama, LM Studio, or future model services directly.
- Updated Android English, Korean, Japanese, Simplified Chinese, and French resource values for QR pairing, settings, private model access, memory empty state, and pair-first errors.
- Updated macOS English, Korean, Japanese, Simplified Chinese, and French route setup values from earlier route-host wording to connection-address wording while leaving localization keys stable for source compatibility.
- A GPT-5.5 read-only audit subagent was used for the scoped copy review. GPT-5.3-Codex-Spark was not used.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or QR pairing validation was run.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 Android Model Selection Persistence Guard

- Audited Android saved model selection and trusted-runtime auto-reconnect behavior after the earlier report that the embedding model selection appeared to reset after leaving and returning.
- Confirmed `PersistedRuntimeData` stores chat and embedding model selections separately, `publishPersistedRuntimeData` restores both into `RuntimeUiState`, and model refresh reconciliation preserves typed selections when the model list is temporarily empty or when the selected model is currently missing from the refreshed list.
- Confirmed auto-reconnect uses trusted runtime identity plus eligible discovered/relay routes, rejects expired or incomplete relay leases, and does not fall back to stale trusted-last-known direct endpoint hints as the product route.
- Added a regression test for the exact startup/restoring-model-list case: saved chat and embedding selections must survive while `models` is still empty.
- The Android phone is disconnected for this pass, so no physical-device install or on-device app restart validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsPersistedSelectionsWhileModelListIsRestoring --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsMissingPersistedSelectionsTypedAcrossRefresh --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresSelectedChatAndEmbeddingModelsSeparately --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectRejectsExpiredSavedRelayLease --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectRejectsIncompleteSavedRelayLease --no-daemon -Pkotlin.incremental=false`

### 2026-06-25 Runtime Inline Reasoning Hardening

- Audited the reasoning/think pipeline with two GPT-5.5 read-only subagents: one for Android UI/state and one for macOS runtime/protocol behavior. No GPT-5.3-Codex-Spark subagent was used.
- Confirmed the existing protocol path already carries `reasoning_delta`/`thinking_delta`, Android renders a muted collapsed reasoning section, and Ollama/LM Studio adapters preserve common field-based reasoning outputs separately from answer text.
- Added runtime-side inline `<think>...</think>` and `<thinking>...</thinking>` splitting in `LocalRuntimeMessageRouter`, including chunk-boundary handling when the tag itself is split across streamed deltas. Inline think text is now stored and forwarded as `reasoning_delta`; visible answer text stays in `delta`.
- Applied the same split to runtime-generated chat titles and suggested next questions so hidden thinking does not pollute generated title/suggestion text.
- Tightened Android reasoning preview expansion so short line counts still become expandable when the text is long enough to wrap beyond the compact three-line preview, and added an explicit expand/collapse click label for accessibility.
- Polished Android reasoning action copy in English, Korean, Japanese, Simplified Chinese, and French from developer-facing "reasoning" wording toward user-facing "thinking" wording. The UI still keeps reasoning text separate, dim, and collapsed by default.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or on-device reasoning expansion validation was run.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.thinkingDeltaAliasAppendsReasoning --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.inlineThinkTagsAreSeparatedFromAnswerContent --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkTagsKeepReasoningCollapsedOutOfAnswerContent --no-daemon -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendSplitsInline`
- `swift test --filter LocalRuntimeMessageRouterTests`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`

### 2026-06-25 macOS Runtime Status Copy Polish

- Refined macOS runtime/status/pairing copy so general user-facing UI avoids developer-heavy wording such as runtime host language.
- Updated the status overview, provider status details, remote-route helper copy, loopback route warning, and pairing QR instruction to use product/device wording like AetherLink Runtime and this device.
- Kept the technical route setup fields available for diagnostics, but moved the normal visible copy toward connection/readiness language.
- Updated English, Korean, Japanese, Simplified Chinese, and French localization resources in the same key order.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or on-device different-network validation was run.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`
- `swift build --target LocalAgentBridge`
- `git diff --check`

### 2026-06-25 macOS Device-Neutral Copy Cleanup

- Rechecked macOS user-facing SwiftUI source and localization resources for platform- or role-specific leftovers after the Android QR connection-detail copy pass.
- Replaced the remaining macOS `client` fallback keys with device-neutral wording: QR route expiration now says a new QR is needed if a device scans later, and runtime request logs summarize incoming work as device runtime requests.
- Updated English, Korean, Japanese, Simplified Chinese, and French localization keys together so fallback English and localized values use the same OS-neutral product vocabulary.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or on-device different-network validation was run.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`
- `git diff --check`

### 2026-06-25 Android QR Connection Detail Copy

- Rechecked the Android route-availability notice path for off-network QR failures. The UI already turns route-specific failures into a compact route notice with a direct scan-latest-QR action instead of a generic error card.
- Updated Android English, Korean, Japanese, Simplified Chinese, and French copy so route failures now say the latest AetherLink Runtime QR must include connection details. This makes identity-only QR, nearby diagnostics QR, stale route QR, and different-network route failures easier to distinguish for users without exposing backend URLs or host/port entry.
- Kept the product boundary intact: Android still does not ask for Ollama, LM Studio, model-provider URLs, raw endpoint hosts, or ports in the normal flow.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or on-device different-network validation was run.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `git diff --check`

### 2026-06-25 QR Remote Route Verifier Parity

- Audited the current different-network QR path with two GPT-5.5 read-only subagents. The current app architecture already fails closed for normal remote QR generation: macOS does not show a normal pairing QR unless a reachable, allocation-backed remote route is eligible and ready, and Android persists relay route material only after accepted pairing or route refresh.
- Confirmed the likely cause of off-network QR failure without a configured public/VPN/tunnel/future-overlay relay: identity-only QR cannot cross unrelated networks, local/private relay addresses are rejected, and complete QR relay route material must include `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- Tightened `script/verify_pairing_qr.swift` so QR image verification rejects private IPv4, carrier-grade NAT, link-local, multicast, and local/private IPv6 relay hosts. The verifier now matches the Android parser and macOS route-readiness policy more closely, so a QR that would fail on-device should not pass the pipeline just because the verifier only checked for loopback or `.local`.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or on-device different-network validation was run.

Verified after this change:

- `script/render_pairing_qr.swift --input <public-relay-uri> --output <tmp.png>`
- `script/verify_pairing_qr.swift --image <tmp.png> --require-relay-route --forbid-direct-endpoint --expected-relay-host relay.example.test --expected-relay-port 443`
- `script/render_pairing_qr.swift --input <private-relay-uri> --output <tmp.png>`
- `script/verify_pairing_qr.swift --image <tmp.png> --require-relay-route --forbid-direct-endpoint` fails with exit code 2 and `invalidRelayHost`
- `git diff --check`

### 2026-06-25 Android Chat Archive/Delete Safety Audit

- Audited the Android chat history surface and confirmed active chat rows expose archive only, permanent delete is reserved for archived chats in Settings, and bulk archive/delete controls require two confirmation steps.
- Tightened the Settings confirmation path so bulk archive and permanent archived-chat deletion remain disabled if the app starts streaming or the eligible chat list becomes empty while the confirmation dialog is open.
- Tightened individual archived-chat permanent delete confirmation so the final destructive confirmation is disabled if the chat becomes active or actions become unavailable while the dialog is open.
- Added helper coverage for the enabled-state rules that keep archive-all scoped to active chats and permanent delete scoped to archived chats.
- Revalidated the runtime-side archive-first policy that rejects `chat.session.delete` for active sessions with `chat_session_must_be_archived_before_delete`.
- The Android phone is disconnected for this pass, so no physical-device install, camera scan, or on-device UX validation was run.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle --filter LocalRuntimeMessageRouterTests/testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore --filter LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore`
- `git diff --check`

### 2026-06-25 macOS Remote Route Copy Polish

- Cleaned up macOS pairing/status/trusted-device/remote-route UI copy so user-visible text says `Remote Route`, `AetherLink Runtime`, and `model providers stay private` instead of exposing prototype wording such as Remote Relay, local runtime, or direct provider names.
- Kept internal transport type names and old-log parsing compatibility where needed, but changed new logs and route allocation errors to use remote-route wording.
- Updated macOS English, Korean, Japanese, Simplified Chinese, and French localizations for the changed QR/route/status strings.
- Updated Swift tests that assert route-related logs to match the new product copy.
- The Android phone is currently disconnected, so no physical-device install or real optical camera scan was run in this pass.

Verified after this change:

- `swift build`
- `swift test`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `git diff --check`

### 2026-06-25 Compact QR Payload For Camera Pairing

- Added `PairingSession.compactQRCodePayload` on the macOS side. The canonical `qrPayload` remains available for tests, docs, and debugging, while the SwiftUI pairing screen now renders the compact payload to improve optical scan reliability.
- Added Android parser support for compact QR aliases: `n`, `c`, `rid`, `rn`, `rf`, `rk`, `rt`, `h`, `p`, `rh`, `rp`, `ri`, `rs`, `rx`, `rrn`, and `rsc`.
- Updated the pairing QR schema and QR verification script so canonical and compact payloads are both first-class v1 QR forms.
- This improves scan robustness but does not claim completed production remote connectivity. Different-network QR pairing still needs a public/VPN/tunnel relay or future private P2P overlay route that both devices can reach.

### 2026-06-25 Runtime-Owned Basic Memory Store

- Added active runtime protocol messages for basic memory CRUD: `memory.list`, `memory.upsert`, and `memory.delete`.
- Added a macOS runtime-owned append-only JSONL memory store at `runtime-memory-events.jsonl`, separate from chat processing events. It supports create/update, enabled/paused state, delete tombstones, and sorted list reconstruction.
- `LocalRuntimeMessageRouter` now handles the memory messages only after the normal trusted-device/authenticated runtime gate, keeping memory content inside the encrypted client-to-runtime protocol boundary.
- The protocol schema now allows only the three basic memory messages. Advanced memory search, automatic extraction/reflection, embedding-backed recall, memory compaction, and project-scoped memory remain roadmap items.
- Android protocol model types and tests now understand the memory payload field names.

### 2026-06-25 Android Runtime Memory Sync

- Android Settings memory actions now require an authenticated trusted-runtime connection and send `memory.upsert` or `memory.delete` instead of mutating only local device storage.
- Android requests `memory.list` after authentication, pairing, and runtime health refresh, then treats runtime responses as the authoritative memory list while keeping a local UI cache for continuity.
- Android chat context now labels injected memory as runtime-owned memory, matching the Mac runtime JSONL memory store and protocol docs.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:protocol:testDebugUnitTest --no-daemon --console=plain`
- `python3 script/check_protocol_schema.py`

### 2026-06-25 Runtime-Owned Chat Lifecycle Sync

- Android now applies authenticated runtime `chat.session.archive`, `chat.session.restore`, and `chat.session.delete` acknowledgements back into the local chat cache instead of only removing the pending request id.
- After a lifecycle acknowledgement, Android immediately requests `chat.sessions.list` again so the drawer/history state follows the runtime-owned session store rather than relying only on optimistic local state.
- Runtime-confirmed deletes now create a local deleted-session suppression even if the deleted runtime session is no longer present in the local cache, preventing a later `chat.sessions.list` sync from reintroducing a server-owned chat that the runtime already confirmed as deleted.
- Lifecycle send/runtime errors now surface a localized `chat_session_sync_failed` message in English, Korean, Japanese, Simplified Chinese, and French instead of silently dropping the failure. The local optimistic archive/delete action remains visible, but the user can see that the runtime did not confirm the change.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

### 2026-06-25 Relay QR Pairing Smoke Pass

- Rechecked the QR pairing path after the Android phone was reconnected. Completed GPT-5.5 Android and runtime subagents were closed after their changes were integrated; GPT-5.3-Codex-Spark was not used.
- Android relay QR scans now keep the relay route as the active route and no longer fall back to stale direct `host`/`port`, mDNS, USB reverse, or previously saved loopback endpoint hints while relay pairing is in progress.
- The Android parser still rejects loopback, localhost, unspecified, `.local`, and otherwise client-unreachable relay hosts for normal/product QR pairing.
- Added a debug-only `relay_scope=usb_reverse` QR field for physical-device smoke tests where `adb reverse` maps the phone's loopback relay port back to the Mac. This lets debug builds validate the full QR protocol on a connected phone without weakening release/product QR validation.
- macOS RuntimeDevServer emits `relay_scope=usb_reverse` only for loopback development relay routes and persists generated development relay secrets so restart/reconnect tests are less brittle.
- The pairing QR schema and protocol docs now describe `relay_scope=usb_reverse` as a USB smoke-test-only escape hatch; production QR pairing must use a public, VPN, tunnel, or future P2P/rendezvous relay route reachable from both paired devices.
- Physical-device relay deeplink smoke passed on Android device `R3CXC0M76VM` in relay mode. The test paired through the QR URI, connected through the relay route, listed models, opened chat, and received mock streaming output.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:transport:testDebugUnitTest --no-daemon --console=plain`
- `swift test --filter CompanionCoreTests`
- `swift test --filter RelayAllocationTests`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="/Users/hanchangha/Library/Android/sdk" ADB="/Users/hanchangha/Library/Android/sdk/platform-tools/adb" script/android_pairing_deeplink_smoke.sh --relay`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && python3 script/check_macos_localization.py && git diff --check`

Remaining remote-connection work:

- Run a true no-ADB different-network scan with a relay/bootstrap endpoint that both the phone and runtime host can reach without USB forwarding.
- Replace development relay/bootstrap setup with the intended production private overlay path: QR-bootstrapped identity, short-lived rendezvous/relay material, NAT traversal where possible, and end-to-end encrypted relay fallback where direct peer-to-peer fails.
- Keep release builds rejecting loopback/local-only route material in QR payloads. QR-only pairing can be the user experience, but the QR must carry real reachable route material; it cannot make two unrelated NATed networks reachable by itself.
- Use `script/run_different_network_dev_runtime.sh --preflight-only` before a no-ADB QR smoke to distinguish a missing or unreachable allocation relay/bootstrap endpoint from later QR scan, pairing, authentication, or model-runtime failures.

### 2026-06-25 Stable Relay Allocation And Optical QR Scanner Guard

- The development allocation relay no longer has to issue a fresh random `relay_id` for every QR. `AETHERLINK_RELAY allocate <route_token> [relay_secret]` now returns route-token-based relay material and accepts an optional runtime-supplied frame secret, which lets a trusted client keep using the same saved relay host/id/secret after pairing instead of depending on a one-off QR id.
- The allocation-required relay default TTL was extended for the development path so the stored route is not invalidated after a short QR scan window. This is still development relay behavior, not production route renewal or a hardened relay service.
- macOS companion bootstrap allocation now passes a saved relay frame secret when one exists and saves successful bootstrap relay settings. On the next allocation, the runtime can reuse the same route secret instead of forcing the client to rescan solely because a random secret changed.
- RuntimeDevServer uses the same bootstrap allocation shape and can pass `AETHERLINK_DEV_RELAY_SECRET` or `AETHERLINK_BOOTSTRAP_RELAY_FRAME_SECRET` when a deterministic development relay secret is needed.
- RuntimeDevServer now treats `AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS` as bootstrap relay intent alongside the legacy single `AETHERLINK_BOOTSTRAP_RELAY_HOST/PORT` shape, so development QR pairing stays relay-only when a multi-bootstrap endpoint list is configured.
- Android's embedded CameraX/ML Kit QR scanner now consumes only `aetherlink://pair` or `lab://pair` QR values. Other QR codes in the camera frame are ignored instead of being treated as a failed pairing result.
- This improves QR pairing reliability, but it does not yet prove full "any network, no constraints, QR only" connectivity. A real external relay/bootstrap host reachable by both devices is still required for the current no-ADB different-network proof, and production still needs automatic bootstrap selection, route renewal, NAT traversal, and hardened end-to-end session setup.

Verified after this change:

- `swift test --filter RelayAllocationTests`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode --filter LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorRequestsBootstrapServiceAllocation --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsRelaySettingsAndIncludesRelayInQRCodeAfterRelayReady`
- `swift test --filter RelayAllocationTests --filter RelayHandshakeTests --filter RelayMatcherTests`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest --no-daemon --console=plain`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 5 --work-dir <tmp>`

Remaining QR work:

- Run a real no-ADB, different-network optical QR test against a public/VPN/tunnel relay host reachable by both devices.
- Add automatic bootstrap/rendezvous selection so normal users do not configure relay host/port.
- Add renewal for allocation-required relay routes and bind renewal to paired runtime identity, not just development route tokens.
- Add production NAT traversal/P2P and blind relay fallback with authenticated end-to-end encryption.

### Repository And Documentation

- Monorepo layout exists for Android, macOS, shared protocol, docs, examples, scripts, README, LICENSE, and protocol schema.
- `docs/architecture.md`, `docs/protocol.md`, `docs/security.md`, `docs/mvp-v0.1.md`, and `docs/roadmap.md` define the runtime boundary, protocol, security model, and roadmap.
- README and protocol docs now distinguish current Android/macOS implementation targets from the OS-neutral product boundary of client app, companion runtime, and runtime host.
- Protocol schema validation exists in `packages/protocol-schema/protocol.schema.json`.
- Pairing QR provisioning now has a separate decoded-payload schema at `packages/protocol-schema/pairing-qr.schema.json`, so route bootstrap fields are validated outside the runtime socket message schema.
- The shared protocol schema now covers active v0.1 payload shapes, not just the envelope/type enum. The checker verifies every active message type has a payload contract and still rejects roadmap namespaces such as memory, skills, MCP, and web search from the active enum.
- `chat.delta` keeps `delta` and `reasoning_delta` as the canonical runtime output fields, while the schema and Android protocol tests now explicitly allow `text` and `thinking_delta` as compatibility aliases accepted by clients.
- Security docs record local-first threat model, trusted devices, pairing design, encryption roadmap, and why same-network unauthenticated access is forbidden.

### macOS Companion Runtime

- SwiftPM macOS companion modules exist for the app shell, protocol, transport, pairing, trusted devices, companion core, Ollama backend, LM Studio backend, and document ingestion.
- The local companion runtime server exists and is the only supported gateway for Android client runtime commands.
- Runtime message router handles authenticated runtime commands.
- Runtime health supports Ollama and LM Studio provider status through the companion runtime.
- Model listing is backend-derived and does not invent default/recommended models when backend lists are empty.
- Ollama model listing uses installed local models and can classify chat vs embedding models.
- LM Studio model listing supports local LLM and embedding models through the runtime.
- Chat requests stream deltas back to the client.
- Ollama reasoning/think chunks are preserved separately from final assistant answer text.
- LM Studio native and OpenAI-compatible streaming paths now preserve common reasoning fields such as `reasoning_content`, `reasoning_delta`, `thinking_delta`, `reasoning`, `thinking`, and `thoughts` as separate reasoning events instead of dropping them or merging them into answer text.
- Cancellation is routed by request id through the backend abstraction.
- Runtime-side model residency now unloads the previous inactive model when switching providers/models and unloads the active model after 10 minutes without chat activity.
- Ollama unload is runtime-mediated through `/api/chat` with empty messages and `keep_alive = 0`; LM Studio unload is runtime-mediated through `/api/v1/models/unload` using loaded instance ids.
- Structured errors are returned through protocol `error` envelopes.
- Document ingestion exists as a standalone runtime-side module for many text/document formats, including PDF, DOCX/DOCM/DOTX, DOC best-effort, HWPX, HWP best-effort, ODT/ODS/ODP, XLSX/XLSM, XLS best-effort, PPTX/PPTM/PPSX, PPT/PPS best-effort, EPUB, RTF, WebArchive, HTML/XHTML, Markdown, AsciiDoc, reStructuredText, text/log/config, CSV/TSV, JSON/JSONL, YAML, TOML, INI/properties, XML, and best-effort Pages/Numbers/Keynote text-bearing archives.
- `chat.suggestions.request` and `chat.suggestions.result` were added so the runtime can generate suggested next questions after an assistant response without the client directly calling any model backend.

### Development Transport, Pairing, And Trust

- Development transport uses local JSON protocol framing over the runtime transport.
- Current dev connection paths are local runtime server routes: same-network/local discovery, USB or emulator forwarding, explicit local diagnostic host/port values, and the temporary relay. They are reachability routes for the paired runtime, not the product connection model.
- Android now has a first `RuntimeConnectionManager` slice in `core/transport`.
- Android connection targets now carry paired runtime identity plus an optional endpoint hint before delegating to the existing TCP transport.
- New route-resolver milestone: a paired peer identity is now the logical connection target, and resolver output is an ordered list of route candidates for that identity rather than a single durable host/port.
- The v0.1 direct endpoint hint remains only one route candidate. Hints from QR pairing, current Bonjour/local discovery, trusted last-known records, USB reverse, emulator, or manual diagnostics are reachability candidates for the current direct TCP transport, not the product address of the runtime host.
- Android `RuntimeConnectionManager` now has injectable remote route preparation, peer-to-peer connector, and relay connector seams. This lets a future NAT traversal implementation and a future blind relay implementation plug into the same ordered route attempt flow, while the current app still ships only the direct TCP/local-development connector.
- Android relay route materialization is now owned by `core/transport` through `RuntimeRelayRoutePreparation` and `RuntimeRelayRoutePreparer`. The app runtime layer only selects pending-QR or trusted-runtime relay material for the paired identity, which keeps ViewModel code out of transport frame construction and leaves room for future P2P route preparation.
- Android transport connectors now share a `RuntimeProtocolChannel` abstraction for framed protocol send/receive/close. The existing direct TCP transport and peer socket client implement this channel, and future P2P/relay connectors must return the same channel shape instead of leaking a backend URL or a transport-specific API into chat/model code.
- Android now includes `RuntimeRelayTcpClient`, an outbound relay connector that joins a private relay room by `relay_id`, waits for `AETHERLINK_RELAY ready`, and then sends/receives length-prefixed AetherLink protocol frames. QR-provisioned relay routes require `relay_secret`, so frame bodies are AES-GCM encrypted with direction-bound nonces before they leave the client.
- Android now attempts prepared remote routes, including the development relay route saved from QR pairing, before local direct routes. Future prepared P2P routes stay ahead of relay, relay now stays ahead of fresh same-network discovery, and stale trusted last-known private IP hints are fallback only. This makes the current different-network relay path the first real attempt when relay metadata exists.
- Android automatic reconnect no longer promotes a stale trusted last-known private IP address into the main product route. When there is no current discovery result or relay route, the reconnect target stays identity-first so debug USB/emulator forwarding or future P2P/relay preparation can be tried without silently falling back to an old private LAN address.
- Android connection state now records the active route kind after a successful connection, so the status UI can distinguish an active relay/P2P route from a stale saved endpoint or local diagnostic route. Relay status copy now says the encrypted relay is tried before local routes on another network.
- Android route-unavailable notices now make QR-only remote-route refresh explicit: when the runtime is already trusted, scanning a fresh remote-route QR updates the saved route instead of requiring users to delete trust or manually enter a host.
- Android first-run pairing prefers route-bearing QR payloads for immediate pairing. If a scanned QR is identity-only, the client now keeps the pending pairing state and waits for matching local discovery instead of failing before Bonjour/route discovery has time to resolve. Identity-only QR still cannot cross unrelated networks; different-network pairing or repair needs relay or future P2P rendezvous material in the QR.
- Android now distinguishes "no relay route saved" from "saved relay route failed". If a relay-backed connection attempt fails, the UI points users to the runtime's Remote Relay status and asks them to confirm that the relay host is reachable from both networks.
- Android now preserves expired remote route lease failures as `remote_route_expired` instead of flattening them into a generic connection failure. The route notice tells the user to scan the latest AetherLink Runtime QR, and expired QR pairing payloads stop retrying instead of looping on a stale relay route.
- Android accepted-pairing and route-refresh mapping reject already-expired relay QR material before saving trust. After a pairing succeeds, Android stores the relay host/id/secret plus the current QR lease/nonce as route material while keeping the trusted runtime identity as the long-lived pairing anchor.
- Android accepted-pairing, route-refresh mapping, relay route preparation, and trusted-runtime storage now require `relay_secret` for relay routes. Incomplete relay metadata is not persisted as a usable relay route and cannot mask a valid direct diagnostic endpoint.
- Android route status and trusted-runtime settings show a saved remote route when relay metadata is present. Stale first-scan QR material is rejected before it becomes trusted state.
- Android route notices now surface the saved relay endpoint as route diagnostics for different-network debugging, while model traffic remains routed only through AetherLink Runtime.
- Android now separates saved remote-route failures from generic runtime connection failures. If an encrypted relay route was saved but does not answer, the UI receives `remote_route_unreachable` with `route_diagnostic_relay_failed`, so the client can tell the user to check AetherLink Runtime route diagnostics or scan the latest QR instead of implying that the model runtime itself is invalid.
- Android connection status now shows a distinct "Relay route saved" state when a trusted runtime has relay metadata but is not connected yet. This makes a fresh relay QR rescan visibly different from a full re-pairing and tells the user to connect through the remote route outside the local network.
- Android relay pairing now treats relay metadata as the authoritative remote route. If a QR or saved trusted runtime has `relay_host`/`relay_port`/`relay_id`, the client builds an identity-only relay target, clears stale private LAN host/port hints, ignores debug USB fallback for that relay-backed reconnect attempt, and does not persist a direct endpoint in the trusted runtime store. This prevents an old same-Wi-Fi IP or USB route from masking different-network relay behavior.
- Android reasoning output now keeps the Ollama-style thinking panel collapsed to a dim three-line preview by default, with clearer localized show/hide thinking actions and safer header layout so the action text does not crowd the label.
- Android Settings now has a persisted Appearance selector with System, Light, and Dark options. `AetherLinkTheme` follows the saved choice, and physical-device screenshots confirmed Light mode switching and System mode restoration.
- Android receive-failure handling now removes an unsent blank assistant placeholder before persisting the active chat. Partial answer text or reasoning is preserved, but a relay/runtime disconnect no longer leaves an empty assistant row in chat history.
- Android chat requests now prepend a runtime capability guard system message before runtime-owned memory/context. It tells the selected model that the current build does not provide live web search, browsing, MCP tools, skills, automations, Python execution, or other external tools unless explicit tool output is present, reducing false claims that roadmap capabilities are already available.
- The macOS runtime now enforces the same capability guard for `chat.send` before forwarding to Ollama or LM Studio, with deduplication when a client already sent the guard. This keeps the roadmap-feature boundary on the runtime side for future iOS/desktop clients, not only in the Android UI.
- Android no longer injects the USB reverse debug fallback into trusted-runtime reconnect unless the user explicitly selected the USB reverse diagnostic route. This prevents different-network failures from being masked as a generic localhost connection failure when the real issue is a missing relay/remote route.
- `script/run_different_network_dev_runtime.sh` starts the development runtime with relay metadata in one command and can optionally start the local relay process when the configured relay host is actually reachable from both devices.
- Client route resolution now wires current Bonjour/local discovery results and explicitly selected local/dev endpoints into route candidates before stale trusted last-known endpoint hints, while staying same-network/local-direct only. Bonjour/local candidates should carry minimal route hints when available, preferably a pairing-derived `route_token`, so the client can route a pinned trusted runtime only to matching discovered endpoints. Stable `device_id`/fingerprint TXT values are legacy/development fallbacks. Metadata-less Bonjour endpoints are not trusted identity matches and are not used as automatic or selected trusted-runtime routes; explicit USB/emulator/manual diagnostics remain the local development escape hatch. This is not real remote P2P, NAT traversal, signaling, or relay transport yet.
- Discovery identity hints are routing metadata only. They must not expose backend URLs, Ollama or LM Studio details, model inventory, provider health, prompts, files, memory, or runtime command metadata, and they do not replace QR pairing, pinned identity, challenge-response authentication, or encrypted transport.
- Android trusted runtime storage now preserves paired runtime identity even when no last-known endpoint hint is available.
- Android QR parsing accepts identity-only pairing payloads; host/port are validated only when present.
- Android's Pairing screen scan action opens an in-app QR scanner and routes the scanned value into the same `trustRuntimeFromPairingQr` path as a deeplink.
- Android QR scanner failure now routes the user back to Pairing and opens a manual QR payload dialog automatically. This is a fallback for devices or environments where Google Code Scanner cannot start or return a result, not a replacement for product QR-only pairing.
- Android QR scanning now uses an embedded CameraX preview plus ML Kit barcode analyzer instead of relying on the external Google Code Scanner flow. The scanner requests camera permission inside the app, keeps manual QR payload entry as a fallback, and sends detected QR text through the same `trustRuntimeFromPairingQr` route as deep links.
- Android QR pairing no longer fails immediately when a scanned QR contains only identity and local discovery has not emitted yet. The pending pairing remains visible as route resolution, and `connectToPendingPairingRuntimeIfNeeded()` completes pairing when a matching discovered runtime appears. Route-bearing direct/relay QR payloads still connect immediately when their route is reachable.
- While a scanned identity-only QR is waiting for route resolution, the Pairing screen keeps QR scanning available and changes the action to "Scan latest QR" so the user can replace stale/incomplete QR material with a fresh direct or relay route QR without resetting the app or deleting trust.
- Successful QR route refresh now leaves a small non-error confirmation notice in the QR pairing panel, instead of relying on a transient `route_refreshed` status that is immediately replaced by the follow-up connection attempt.
- Android pairing UI still supports route diagnostics, but the normal pairing expectation is now "scan QR -> connect through QR route -> send `pairing.request` -> persist trust"; mDNS/Bonjour is a secondary route refresh and diagnostics path, not the core first-run pairing dependency.
- Android trusted runtime writes now persist identity/key/route-token material as the source of trust. If QR pairing included a valid development/local host/port, the client also stores it as an optional last-known direct route hint for reconnect; it is still treated as a route candidate, not as the product identity or durable address.
- Android now advertises and consumes the runtime-owned chat history messages. After authentication it requests `chat.sessions.list`, merges runtime-owned session summaries into the local UI cache without deleting local-only sessions, and when a previous runtime session is opened it requests `chat.messages.list` to refresh that transcript while preserving local archive/manual-title state.
- Android now keeps local suppression records for permanently deleted runtime-owned sessions, so a server-owned chat that the user deleted from archived history does not reappear after the next `chat.sessions.list` or `chat.messages.list` sync. This is a client-side bridge until authenticated runtime archive/delete protocol messages are added.
- Authenticated runtime archive/restore/delete protocol messages now exist as `chat.session.archive`, `chat.session.restore`, and `chat.session.delete`. The macOS runtime records them as append-only session lifecycle events, hides archived/deleted sessions from default `chat.sessions.list`, allows restored sessions to reappear, and returns no transcript for deleted sessions.
- `chat.sessions.list` now supports `include_archived`. The macOS runtime still omits archived sessions by default and never returns deleted sessions, but can return archived summaries with `status` and `archived_at` for authenticated clients that explicitly request them. Android requests archived summaries after reconnect and merges them into its archived history instead of losing runtime-owned archived chats.
- macOS `PairingSession` can still generate identity-first or local-direct QR payloads for tests and compatibility, but the companion app now generates route-bearing QR payloads for normal pairing. If a mutually reachable remote relay route is configured, QR includes `relay_host`/`relay_port`/`relay_id`/`relay_secret` plus fresh `relay_expires_at`/`relay_nonce`, and omits local host/port. If no eligible relay is available, normal QR generation stops instead of silently falling back to a local IP. Local direct QR remains an explicit diagnostic/development policy.
- macOS `PairingSession` can include temporary relay metadata (`relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`) when an eligible development relay is configured.
- macOS Transport now includes `RelayPeerClient`, an outbound relay client that registers the runtime side with a private `relay_id` and forwards matched client frames into the existing `LocalRuntimeMessageRouter`. With QR-provisioned `relay_secret`, it decrypts client frame bodies and encrypts runtime response bodies without exposing AI protocol JSON to the relay.
- `RuntimeDevServer` and the SwiftUI companion model can enable the development relay from `AETHERLINK_RELAY_HOST`, `AETHERLINK_RELAY_PORT`, and optional `AETHERLINK_RELAY_ID`.
- `script/run_runtime_dev_server.sh` and `RuntimeDevServer` now generate a relay frame secret when a relay host is configured without one. RuntimeDevServer development pairing info also includes fresh `relay_expires_at` and `relay_nonce`, matching the SwiftUI QR payload shape, and no longer puts the default `127.0.0.1` development host into relay-mode pairing QR payloads unless `AETHERLINK_DEV_PAIRING_HOST` is explicitly set.
- The SwiftUI companion now blocks normal QR generation for GUI-configured loopback, `.local`, or private-LAN relay hosts instead of presenting them as different-network-ready routes. Explicit environment-driven development/tunnel relay routes remain available for controlled testing.
- The macOS app Status screen now exposes a Remote Relay panel. It stores a mutually reachable relay host/port, generates a relay frame secret by default, restarts the outbound relay client when the runtime is already running, and includes the relay metadata in newly generated QR pairing payloads.
- The macOS runtime now reports live Remote Relay status instead of only saved configuration: connecting, waiting for the client to join the same relay id, connected, reconnecting, failed with the relay error, or stopped. `RuntimeDevServer` prints the same lifecycle labels, so different-network failures can be separated into relay reachability, stale QR/relay id, and post-auth protocol failures.
- `AetherLinkRelay` is now the SwiftPM-native development relay executable. It listens on configurable `--host`/`--port` values, allocates QR route lease material, accepts the existing `AETHERLINK_RELAY runtime <relay_id>` and `AETHERLINK_RELAY client <relay_id>` handshake lines, sends `AETHERLINK_RELAY ready` after matching one runtime and one client, and blindly forwards bytes without decoding protocol frames or calling Ollama, LM Studio, or another model backend.
- `script/aetherlink_relay.py` is legacy-only and is not valid for current QR pairing because it cannot allocate route leases.
- `script/runtime_authenticated_mock_smoke.swift --relay` now exercises the development relay path end to end: it starts `AetherLinkRelay`, starts RuntimeDevServer with matching relay metadata and a relay frame secret, verifies the generated pairing info includes the relay route, then performs pairing, fresh challenge-response authentication, model list, streaming chat, and cancel over encrypted relay frame bodies.
- Android relay connection setup now applies the route timeout while waiting for the relay ready line, then removes the socket read timeout after the relay is ready so long model streams are not interrupted.
- The next remote-connection increment should preserve identity-first trust while extending QR into the only normal route bootstrap surface: pairing records the runtime identity, pinned public key/fingerprint, route token, and any overlay/rendezvous/relay material needed for different-network routing without requiring the user to scan or enter a fixed host:port.
- Runtime-side chat processing now has a Mac/server-owned JSONL event store. `chat.send` records the request, assistant deltas, reasoning deltas, completion usage, cancellation, and errors on the runtime host, with inline attachment bytes stripped before storage. Authenticated clients can query runtime-owned summaries/transcripts through `chat.sessions.list` and `chat.messages.list`, which starts moving chat processing state to the server/runtime layer instead of treating the mobile client as the source of truth.
- Runtime-owned chat history now reconstructs multi-turn transcripts from stored request/response event pairs instead of only returning the latest request. Runtime-generated chat titles are also stored as runtime metadata events, so `chat.sessions.list` can return the summarized title after the first assistant response rather than falling back to the first user prompt.
- Android now marks a newly sent chat as runtime-owned as soon as `chat.send` is sent to the authenticated runtime, then refreshes runtime session summaries after chat completion or after a generated title result. This prevents archive/delete actions made before the next reconnect from being treated as local-only history and keeps the drawer closer to the runtime host's stored session state.
- Runtime-owned session summaries now keep a neutral `New chat` title until a generated title metadata event exists, so first user prompts are not exposed verbatim as chat titles during the gap before title generation succeeds.
- QR-based pairing is implemented for the current runtime/client loop.
- Trusted runtime records persist on the client after pairing.
- The runtime can publish Keychain-backed runtime public-key/fingerprint metadata through QR pairing and accepted `pairing.result`; the client stores it with the trusted runtime and rejects pairing if the accepted runtime identity does not match the scanned QR.
- Runtime identity key persistence and deletion/rotation are covered by SwiftPM tests using isolated Keychain service/account slots, so future reset/re-pair flows can rotate the runtime identity without touching unrelated app keys.
- Runtime commands are gated behind pairing/authentication.
- Untrusted clients are rejected before runtime commands reach Ollama or LM Studio.
- Authenticated runtime commands require QR pairing and trusted-device state first, regardless of whether the current route is same-network, USB/emulator forwarding, or a manual local diagnostic endpoint.
- The development transport remains replaceable by encrypted P2P/pairing transport later. A temporary outbound TCP relay is now available for different-Wi-Fi testing, with mandatory pairwise frame-body encryption for normal QR-provisioned relay routes. Production remote P2P, NAT traversal, DHT/bootstrap signaling, relay allocation, replay protection, and full production transport encryption remain future transport work.
- Cross-network 1:1 connectivity is not solved by mDNS or fixed private IPs; it needs a connection manager that can resolve route candidates from the same paired identity, then negotiate local direct, remote P2P, and encrypted relay paths.
- Public peer-discovery ideas can inspire the design, but AetherLink discovery must be privacy-preserving:
  - do not publish stable device ids directly,
  - use rotating rendezvous tokens derived from paired-device shared secrets,
  - use DHT/bootstrap peers only for short-lived paired-device rendezvous records,
  - use STUN-like candidate discovery and authenticated hole punching before falling back to relay,
  - keep prompts, responses, files, memory, model names, and runtime commands inside the end-to-end encrypted session,
  - prevent unpaired peers from learning usable routing or runtime metadata.
  - keep relay/signaling blind to encrypted AI protocol payloads and backend details.
- Current code now prepares that direction by advertising and matching a QR-provided `route_token` before falling back to legacy device id/fingerprint matching.
- Trusted-runtime restoration now starts local discovery from the saved runtime identity even when the saved record has no usable host/port endpoint. If a later Bonjour/local candidate advertises a matching route token or legacy identity hint, the route resolver can reconnect without treating the old fixed IP as the product address.
- Trusted-runtime restoration can also use a verified QR-provided host/port as a last-known direct route hint when present, while still blocking manual attempts to connect directly to common local model backend ports such as Ollama `11434` and LM Studio `1234`.
- Relay route preparation now consumes the same trusted runtime identity and route token to prepare a different-Wi-Fi development relay candidate. It requires persisted `relay_secret` for relay route preparation, so Android and macOS use matching AES-GCM relay frame encryption. Actual NAT traversal, DHT/bootstrap rendezvous, production signaling, hardened relay allocation, replay-resistant session setup, and complete production E2E session encryption are still not implemented.

### Android Client

- Kotlin/Jetpack Compose client skeleton has moved beyond basic scaffold.
- First-launch/onboarding flow is oriented around pairing instead of manual backend URL entry.
- Pairing and connection/status controls live under Settings, not as primary bottom tabs.
- A tested navigation resolver keeps first-run onboarding on Pairing, moves to Chat once a trusted runtime is established, and keeps post-onboarding pairing/status management in Settings.
- Main chat UI is closer to a ChatGPT-style layout: drawer for previous chats/settings, top model selector, composer at the bottom, and cleaner empty state.
- System light/dark appearance is supported.
- App language setting supports English, Korean, Japanese, Simplified Chinese, and French, with English as the default.
- Simplified Chinese language persistence now accepts Android/resource aliases such as `zh-rCN` and script aliases such as `zh-Hans`, normalizing them to the app's Simplified Chinese option instead of falling back to English.
- UI strings have been cleaned to avoid hardcoded Android/Mac wording where possible.
- Model and embedding pickers now display polished provider names such as Ollama, LM Studio, and Companion runtime instead of leaking raw ids like `lm_studio`; the stale `Local runtime` resource label was removed.
- Haptic feedback is used for important controls.
- Runtime connection restores from the trusted runtime record after app restart.
- Runtime connection restoration is also retried when the client app resumes, using the trusted runtime identity as the source of truth and preferring a currently discovered matching endpoint before the saved last-known endpoint.
- Explicit user disconnect is persisted locally: lifecycle resume and app restart do not silently re-enable trusted-runtime restoration until the user reconnects or pairs again.
- The Settings connection status panel now exposes whether trusted-runtime auto reconnect is enabled and explains when it is paused after an explicit disconnect.
- The Settings connection status panel now labels connectivity as a runtime route and no longer shows the development default `127.0.0.1:43170` as the apparent product endpoint before pairing; unpaired and identity-only QR states show pair/route-resolution status instead.
- Android no longer seeds a fixed development endpoint into the default UI state. USB reverse, emulator, and lab network host/port controls are developer diagnostics only: release builds hide them, and debug builds require opening Developer routes before they appear. Normal routing is presented as paired, resolving, local-discovery, saved-hint, or development route state.
- Android connection errors now surface route diagnostics without implying remote transport is already implemented: local direct can report missing or failed endpoints, while P2P and relay are explicitly labeled as not enabled in this build.
- Android connection status now includes a route-status notice that distinguishes local discovery, QR/local routes, development routes, and the temporary relay path. Relay routes warn when frame encryption material is missing and otherwise state that production P2P remains roadmap work.
- The trusted-runtime settings panel now uses the same route-label resolver as connection status, so relay-only trusted runtimes no longer appear as indefinitely resolving.
- Trusted runtime and discovered runtime rows no longer expose raw host/port as the primary user-facing route label; those details stay in diagnostics/logging paths.
- Settings now includes an explicit auto-reconnect toggle for the trusted runtime, so users can control restore behavior instead of inferring it only from connection status.
- Trusted runtime restoration no longer depends only on stale fixed endpoint hints: when local discovery later finds a runtime whose route token or legacy identity matches the saved trusted runtime, the client can automatically reconnect through the route resolver.
- Client-facing `models.result` no longer includes backend `remote_host` metadata. The runtime may use provider host fields internally to classify Ollama cloud models, but clients receive only runtime-mediated model identifiers and never backend URLs.
- Chat model picker filters out embedding models.
- Embedding models are selected separately from chat/text-generation models in Settings.
- Embedding model settings now expose an explicit "none" path, so a saved or missing embedding selection can be cleared without selecting another embedding model.
- Selected chat and embedding model ids persist locally.
- Model-list refresh reconciliation now preserves persisted chat and embedding selections across temporary backend/discovery gaps, clears selections only when a refreshed model with the same id is the wrong type, and prevents embedding-capable models from being treated as chat models.
- The Android model selector and embedding-model settings now keep showing the saved model id/name while the companion runtime is reconnecting or refreshing model lists, with localized restoring/unavailable messages so the selection does not appear to be silently cleared.
- The closed chat top-bar model pill now also shows the saved chat model name/id while the model list is restoring, instead of falling back to "Choose model" and making the persisted selection look lost.
- Android message/code copy now uses the current Compose `LocalClipboard` API instead of deprecated `LocalClipboardManager`, keeping debug builds free of that UI deprecation warning.
- Chat supports streaming answer deltas, cancellation, and structured error display.
- Reasoning/think text is shown separately as a muted compact section that can expand.
- Android reasoning/think rendering now shows a muted inline preview with a subtle rail, collapsed to about three lines by default, with tap-to-expand full reasoning.
- Reasoning visibility now covers Ollama `message.thinking` and LM Studio/OpenAI-compatible reasoning field variants. If a selected model or mock backend does not stream reasoning fields, the UI correctly has no reasoning section to show.
- Local previous chat history exists.
- New chats no longer use the first prompt verbatim as the title. After the first assistant response completes, the client asks the runtime for a concise `chat.title.request` result and applies it only while the user has not manually renamed the chat.
- The generated title is now persisted by the runtime event store as well as reflected in the Android UI cache, which moves title ownership closer to the runtime/server side.
- The Android previous-chat drawer now archives with an undo snackbar instead of making an irreversible-feeling one-tap change. Permanent delete remains hidden in Settings behind the existing two-step confirmation path.
- Archive and delete are separate chat actions: normal previous-chat rows expose archive/removal from active history, while permanent delete is reserved for archived chats.
- Dangerous bulk history operations are hidden inside Settings chat-history management and require two confirmation steps.
- Archived chats remain retained locally but are excluded from memory/research/compaction inputs unless restored or explicitly selected in a future source picker.
- User-managed memory notes can be added, disabled, and removed through the trusted runtime; enabled notes are included only through the runtime-mediated `chat.send` path.
- File/image attachment UI is present.
- Image input is gated to vision-capable models.
- The Android attachment picker now opens document/text types by default and includes image types only when the selected chat model advertises vision/image/multimodal support.
- Android attachment chips now show image/document type and file size, and image chips visibly indicate when the selected model requires a vision-capable replacement before sending.
- Document and image attachments are sent to the runtime boundary rather than directly to a serving backend.
- The companion runtime now rejects image attachments before backend calls unless the selected model advertises `vision`, `image`, or `multimodal`; LM Studio image attachments use native `/api/v1/chat` image input first, with OpenAI-compatible chat completions as fallback when native rejects the request shape.
- Fixed centered example prompts were removed.
- AI-generated suggested next questions now use the runtime-mediated `chat.suggestions.request` path and appear as chips under the latest assistant response. Tapping a chip fills the composer for editing/sending.
- Suggested next questions now require structured JSON from the runtime model call; invalid prose/list output becomes an empty suggestion list instead of arbitrary text chips.
- Latest Android UI polish pass applied:
  - Settings now opens with preferences, embedding model, and memory first, while connection/status and advanced endpoint controls are collapsed into secondary sections.
  - The chat composer no longer shows redundant helper or placeholder text while it is already ready for input; status text is reserved for blocked/error states.
  - The top model selector says "Choose model" when no model is selected, uses refresh wording, gives the selected model more room, and now renders as a compact pill-style control next to the drawer button.
  - The top model selector now shows a compact selected/search icon so selected vs unselected model state is easier to scan without adding extra text.
  - The left drawer now includes a compact runtime/model summary below the AetherLink title, giving users current trust/connection and selected-model context before they browse chat history.
  - Settings now presents runtime/pairing status before embedding, memory, and chat-history management, keeping the runtime-mediated product boundary visible while leaving previous chats primarily in the drawer.
  - Suggested next questions render as full-width follow-up actions instead of truncated horizontal chips.
  - Empty chat copy is more user-facing and less runtime-status-first.
  - The fully ready empty chat state is intentionally quiet: it shows only a compact centered status while keeping the bottom composer as the primary action surface until a real assistant answer can produce suggested next questions.
  - The chat composer no longer renders a generic placeholder such as "Ask anything"; the empty input stays visually quiet unless a real connection/model/file warning is needed.
  - The chat composer now keeps that quiet visual surface while adding accessibility semantics for the message field and send-button readiness, so screen readers can identify the control without reintroducing visible placeholder copy.
  - The chat composer was tightened into a compact single-row control. Generic connection/model helper text is no longer rendered inside the composer; only actionable file/model warnings can appear there.
  - The chat timeline now uses quieter neutral user bubbles, a constrained assistant reading width, tighter transcript padding, and a more docked composer surface so the default chat view feels closer to a modern/classic assistant app.
  - Assistant messages no longer show repeated assistant avatars or role labels in the timeline, making the chat surface quieter and closer to a modern assistant transcript.
  - Normal chat messages no longer show always-visible copy icons; long-press copies message text while code blocks keep an explicit copy affordance.
  - Chat-bottom route availability notices now render as a compact status chip instead of a taller two-line card, so connection-route guidance does not dominate the composer area.
  - Haptic feedback now covers more high-frequency controls, including drawer opening, chat history selection, chat history menus, model menu opening, Settings navigation, and expandable Settings sections.
  - User-facing Android copy now prefers "runtime host" over "paired computer" across supported languages, keeping the UI less tied to one operating-system pairing.
  - Chat-facing install/backend/file-type messages avoid "runtime host" implementation wording where possible.
  - Android visible model-service copy now avoids user-facing "backend" wording where practical, while preserving internal keys and structured error codes for compatibility.
  - Latest physical-device UI pass keeps empty chats from rendering as a blank screen, constrains the chat transcript and composer to a centered reading width, lowers the composer surface weight, and gives QR pairing a calmer compact card treatment.
  - Android provider health summary now uses localized readiness summaries instead of raw provider-name/status strings joined by a separator. Individual provider cards still show actionable Ollama or LM Studio detail.
- Latest discovery UI pass applied:
  - Discovered runtimes now show whether their advertised identity matches the trusted runtime, is missing, is unknown, or belongs to a different trusted runtime.
  - Known mismatched discovered runtimes cannot be selected when a trusted runtime is already saved.
  - Metadata-less local/dev discovery candidates are labeled as missing advertised identity and are not used as trusted-runtime routes.
  - Matching discovered trusted runtimes can trigger restore connection attempts, while metadata-less discoveries remain manual/dev candidates only.
- macOS companion copy now describes Bonjour/local transport status as a pairing service and keeps Local Network permission language scoped to completing local pairing, rather than implying local-network discovery is the final product connectivity model.
- macOS companion UI, menu bar actions, page headers, panels, pairing instructions, trusted-device controls, and empty-state messages are routed through localization resources for English, Korean, Japanese, Simplified Chinese, and French. Remaining source-visible system image names and log parsing tokens are implementation identifiers rather than user-facing strings.
- Latest macOS companion UI polish adds an explicit Connection Routes status card that distinguishes local routes from the temporary development relay, indicates whether relay frame-body encryption is configured, and states that production different-network P2P remains roadmap work. Runtime Logs and Trusted Devices copy now use AetherLink runtime/trust-management wording instead of visible "Companion" phrasing.
- The macOS Remote Relay panel now tells users to open Pairing, generate a new QR, and have already paired clients scan it again after relay settings change. This makes the current different-network development path clearer without exposing Ollama or LM Studio directly.
- The macOS Remote Relay panel now has a direct Generate Relay QR action. It creates a fresh pairing QR and switches to Pairing so already trusted clients can rescan and refresh their remote relay route without deleting trust.
- The macOS Remote Relay panel now includes a configured, eligible relay route in newly generated QR payloads immediately, so a client can scan once and retry while the runtime host reaches the relay. Loopback, `.local`, and GUI-configured private-LAN relay hosts remain blocked from normal remote QR material.
- Latest route UX copy now separates a saved remote route from an actually connected relay. Android status panels say "remote route saved" until a connection is active, Android retry errors explain that the runtime host and client are waiting to meet on the relay, and macOS overview warns only when the configured relay address cannot be used in a remote QR.
- The macOS Remote Relay panel now blocks loopback, `.local`, and private-network relay hosts from normal QR generation, because remote client devices cannot reliably reach them across unrelated networks. Private/VPN/tunnel addresses may be used only through explicit development or managed-overlay policy and must not be labeled normal QR-ready.
- Superseded by later QR-first cleanup: the Status screen keeps QR pairing as the primary quick action, while connection address and secret fields are hidden in advanced diagnostics rather than shown directly in normal status.
- The macOS Pairing QR card now uses QR-only instructions and no longer exposes the embedded 6-digit protocol code as a copyable/manual-entry affordance. The code remains inside the QR/protocol payload for pairing validation.
- The macOS Pairing QR card now states whether the current QR includes a configured remote relay route, warns when relay frame encryption material is missing, and shows a remote-route setup notice instead of implying a local QR exists when normal QR generation is blocked.
- The macOS Pairing QR card now shows the saved remote route lease expiration embedded in a relay QR. Relay metadata is included in newly generated QR payloads whenever the configured remote route is eligible; the client then retries until the relay is reachable. Loopback, `.local`, and GUI-configured private-LAN relay hosts are still blocked from normal QR route material because different-network clients cannot reach them reliably.
- Latest macOS localization polish maps remaining companion/local-runtime visible values to AetherLink Runtime or runtime-host wording across English, Korean, Japanese, Simplified Chinese, and French, while retaining legacy raw log keys only for compatibility mapping.
- Latest macOS copy polish maps visible backend/local-runtime/Companion phrasing to model provider, model service, AetherLink Runtime, or runtime-host wording across English, Korean, Japanese, Simplified Chinese, and French.
- Latest macOS localization cleanup also updates Swift fallback keys and runtime-protocol error/status messages so missing localizations or client-rendered errors no longer expose stale "backend", "Companion", "companion runtime", or "this Mac" phrasing. The UI now prefers model provider/model service/AetherLink Runtime wording at the source-key level, not only in translated values.
- New macOS runtime log events now use AetherLink Runtime wording at the source. Legacy `Companion started/stopped` raw log parsing remains only as a compatibility mapping for older in-memory events, and the copy hygiene checker now blocks those stale visible fallback keys from returning.
- Latest localization fit polish shortens pairing, route, history, status, provider, and error copy across Android and macOS locales while preserving the Android client -> AetherLink Runtime -> model provider boundary.
- Android relay route labels now use product-facing "encrypted relay route" wording across supported languages while the docs still identify the current implementation as a temporary development relay.
- Fresh relay QR payloads now include `relay_secret`, `relay_expires_at`, and `relay_nonce`; Android uses that relay route security material for the pending QR attempt and rejects missing, incomplete, or stale first-scan route material. After pairing succeeds, Android persists the trusted runtime identity plus relay host/id/secret/lease/nonce as the current route material. Scan-once pairing keeps the trust relationship across app restarts, but an expired route lease still requires fresh route material instead of being silently downgraded into identity-only local discovery.
- SwiftPM now includes an `AetherLinkRelay` development relay executable in addition to the Python compatibility script. It matches one runtime and one client by `relay_id`, sends the existing ready line, and blindly forwards bytes without decoding AetherLink frames or touching model providers.
- Android pairing and transport internals now use runtime-centered names for pairing payloads, trusted runtime records, discovered runtime records, transport clients, and UI state. Legacy `mac_*` QR/query and DataStore keys remain only as compatibility aliases for existing v0.1 pairings and wire payloads.
- macOS backend, pairing, and development-server status/error messages now prefer runtime-host/client wording. New pairing defaults use `AetherLink Runtime` as the display name while legacy `mac_*` protocol fields remain accepted for compatibility.
- Android chat/model-facing copy now avoids implementation-heavy phrases such as "install on runtime host" in favor of direct action labels like "Install model" and "Open the model app, then refresh health." Runtime-host wording remains in Settings, advanced endpoint controls, and security-oriented explanations where the trust boundary matters.
- Latest physical-device checks installed the debug APK on a connected Samsung device, fixed an Android startup crash caused by localized context replacement dropping `LocalActivityResultRegistryOwner`, and passed `script/android_pairing_deeplink_smoke.sh --relay`. The relay QR/deeplink smoke opened `aetherlink://pair` on the device and verified encrypted relay-frame `pairing.request`, accepted pairing, `runtime.health`, `chat.sessions.list`, and `models.list` through RuntimeDevServer. Earlier physical-device checks also verified USB-reverse runtime reconnect plus authenticated `runtime.health` and `models.list`.

### Branding And Assets

- App name is AetherLink.
- The user-provided AetherLink icon image is stored as `assets/brand/aetherlink_icon_source.png`.
- Android launcher PNGs, the adaptive icon foreground, the generated macOS iconset, and `apps/macos/LocalAgentBridgeApp/Sources/Resources/AppIcon.icns` are generated from that source.
- `assets/brand/generate_aetherlink_icons.swift` is the canonical offline regeneration script for app icon assets.
- The project is licensed under the Apache License, Version 2.0. `LICENSE` is the authoritative license file.

### Verification Already Run

- Android:
  - `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest :app:compileDebugKotlin :app:testDebugUnitTest`
  - `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug`
  - `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay`
  - Result: passed.
- macOS:
  - `swift test`
  - Result: passed, 97 tests.
- Schema/localization/copy:
  - `python3 script/check_android_string_parity.py`
  - `python3 script/check_protocol_schema.py`
  - `python3 script/check_macos_localization.py`
  - `python3 script/check_copy_hygiene.py`
  - Result: passed.

## Current Known Limits

- The local transport is still development-grade and must be replaced or hardened with encrypted authenticated transport.
- Current development connections can look like same-network or fixed endpoint connections. This must be treated as temporary diagnostics/scaffolding, not the final product.
- Different-network 1:1 connectivity now has a user-configurable temporary development relay path, but production-grade connectivity is not complete. The relay host must be public or otherwise mutually reachable, and clients paired before relay setup must scan a fresh relay QR from the same pinned runtime identity, or pair again if runtime trust was removed. The next transport milestone must replace or harden the temporary relay with real local-direct, remote P2P NAT traversal, DHT/bootstrap discovery, and encrypted relay transports.
- The current relay smoke test confirms the relay path can carry authenticated pairing, challenge-response auth, runtime health, model list, streaming chat, and cancel generation. It now also fails if RuntimeDevServer relay pairing info omits fresh `relay_expires_at` or `relay_nonce`. If a real different-Wi-Fi device still cannot connect, the first checks are whether the relay host is reachable from both networks, whether the runtime shows connected/waiting/failed in Remote Relay status, and whether the client scanned a fresh relay QR containing the current `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- Android can now treat a fresh QR from the same pinned runtime identity as a route refresh for an already trusted runtime. Relay QR payloads update stable relay host/id/secret material after rejecting expired QR route material, and direct local QR payloads update the saved direct host/port hint while clearing stale relay metadata. This lets existing trusted devices repair routes without deleting trust or depending on stale same-network private IPs, while still keeping model access behind AetherLink Runtime.
- Android relay QR pairing now keeps the scanned pending pairing payload after an initial relay connection failure and retries with bounded backoff instead of forcing the user to scan again immediately. The retry budget is long enough for the runtime host and client to meet on a relay after the scan, while still expiring when the QR route material expires or the runtime rejects pairing. Saved trusted relay routes also schedule reconnect after failed connection attempts, not only after an already-open protocol stream drops.
- Android now keeps a QR direct endpoint as a fallback when a QR payload contains both relay and direct route material. The connection manager still tries the prepared relay route first, but a bad relay route no longer blocks same-network QR pairing if the QR also carried a valid direct endpoint.
- Android trusted-runtime auto reconnect now prefers fresh Bonjour/local discovery for the pinned runtime identity, but falls back to the saved last-known direct endpoint when no current discovery route is available. This improves app-restart recovery for local/direct development routes without turning the endpoint into the trusted product identity; different-network use still requires a relay QR or future P2P overlay route.
- Android pairing QR parsing now rejects incomplete relay material such as `relay_secret` or `relay_id` without `relay_host`/`relay_port`, instead of silently downgrading the QR into identity-only local discovery. A fresh relay QR from the same pinned runtime identity can rotate the saved `route_token` when the runtime device id and key/fingerprint still match.
- DHT/bootstrap-peer discovery, STUN-like address discovery, authenticated hole punching, production TURN-style relay allocation, replay protection, and production end-to-end transport encryption are design targets only; none are implemented in the current transport.
- QR pairing exists, but production trust UX still needs certificate/public-key pinning polish and trusted-device management hardening.
- There is no cloud backend by design.
- A future relay/signaling service, if added for NAT traversal, must not become a cloud AI backend, account server, prompt store, model proxy, backend URL directory, or traffic observer for AI protocol payloads.
- Current code still has fixed-endpoint compatibility paths:
  - Android pairing store still persists legacy `mac_host` and `mac_port` keys only as optional last-known endpoint hints.
  - QR pairing and Bonjour discovery currently provide reachability endpoint hints.
  - Android route resolution prefers current Bonjour/local discovery candidates with matching route-token or legacy runtime identity hints before saved trusted last-known endpoint hints.
  - Bonjour/local endpoints without identity metadata are visible for diagnostics but are not used as trusted-runtime route candidates; explicit USB/emulator/manual diagnostic paths remain available for development.
  - Android `RuntimeConnectionManager` now delegates local direct routes to the existing TCP `connect(host, port)` implementation and prepared relay routes to the outbound relay connector. The connector boundary returns a common framed `RuntimeProtocolChannel` so future remote connectors can feed the same protocol stream.
  - macOS pairing QR can omit `host`/`port`, and can include development relay metadata when configured.
  These are now isolated behind identity, connection target, endpoint hint, and route-candidate concepts. The implemented remote path is still a development relay, not production P2P or encrypted relay. Production remote P2P, real NAT traversal, hardened relay fallback, and a full macOS-side connection-manager integration are not implemented yet.
- There is no MCP implementation.
- There is no skills runtime implementation.
- There is no web search implementation.
- There is no internal Python tool execution yet.
- Memory is still user-managed runtime-owned notes plus UI cache context, not full long-term memory, vector memory, or automatic memory compaction.
- Runtime archive/restore/delete protocol messages now exist for the authenticated runtime store. Client and runtime lifecycle state still need richer cross-device conflict handling, archived-session listing/filtering, and UI for runtime-owned archived sessions across future clients.
- Embedding model selection exists, but embedding-powered retrieval/research is not implemented.
- File/document ingestion is runtime-side and broad, but legacy binary formats remain best-effort until dedicated parsers are added.
- Vision input depends on model capability metadata and backend adapter support; Ollama and LM Studio image inputs are mediated by their runtime adapters, with LM Studio using native image input first and OpenAI-compatible multimodal fallback when needed.
- AI-generated next-question suggestions depend on the selected chat model and can be skipped silently if suggestion generation fails or returns invalid JSON.
- Full physical-device QA still needs to cover physical camera scanning, QR re-pairing after trust removal, real streaming chat, cancellation, reasoning expansion, suggested next questions, attachments, and all five app languages after the latest UI changes.
- Production packaging, signing, notarization, Play distribution, and release pipelines are not complete.

## Immediate Next Work

1. Replace the temporary relay/fixed-endpoint development assumption with a production QR-bootstrapped overlay plan:
   - define a full `ConnectionManager` abstraction on client and runtime,
   - store paired runtime identity rather than a raw host/IP as the primary connection target,
   - make QR the only normal user-facing pairing and route-refresh surface,
   - include runtime identity, public key/fingerprint, route token, and overlay/rendezvous/relay material for different-network routes,
   - keep fixed host:port only as an optional local/dev diagnostic hint,
   - try same-network discovery/direct connection as an opportunistic fast path,
   - let local discovery resolve a direct LAN endpoint from the trusted runtime identity and route token instead of from a fixed scanned address,
   - add a private P2P peer-discovery and NAT traversal implementation for different networks,
   - replace the development relay with key-bound encrypted relay allocation and forwarding,
   - use Bitcoin-like peer-network inspiration only for decentralized discovery concepts, not for public visibility or untrusted command routing,
   - add an end-to-end encrypted blind relay/TURN fallback design for networks where P2P fails,
   - keep every path behind the same pairing/authentication and backend mediation boundary.
2. Run a physical Android device QA pass:
   - install the debug build,
   - pair through QR,
   - verify reconnect after app restart,
   - load models,
   - select chat and embedding models separately,
   - stream chat,
   - cancel generation,
   - verify reasoning/think rendering,
   - verify AI-generated suggested next questions,
   - test image/document attachments,
   - check Korean/Japanese/Chinese/English/French UI strings.
3. Capture Android UI screenshots after the QA pass and continue polishing a modern/classic interface:
   - quieter transcript spacing and typography,
   - less visually noisy message actions,
   - more refined drawer and Settings surfaces,
   - model selector that feels integrated into chat,
   - small-screen behavior and touch targets,
   - consistent light/dark treatment.
4. Continue the `ConnectionManager` work:
   - expand the route resolver from v0.1 direct endpoint candidates to real remote P2P NAT traversal candidates and encrypted relay fallback candidates,
   - keep explicit source-aware endpoint hints for USB reverse, emulator, Bonjour, and manual diagnostics,
   - keep Bonjour/local TXT route hints minimal and continue auto-routing trusted runtimes only when those hints match the pinned identity,
   - keep metadata-less discovery results as local/dev/manual candidates rather than trusted identity matches,
   - add macOS-side connection-manager boundaries,
   - preserve current USB reverse, emulator, Bonjour, and dev-server flows while removing fixed IP from the normal product path.
5. Capture launcher/dock screenshots on real devices to verify the generated AetherLink icon reads correctly at small sizes.
6. Harden pairing and trusted-device UX:
   - trusted runtime details,
   - remove trusted device,
   - reconnect status,
   - error states,
   - no manual endpoint path for normal users.
7. Add production transport design:
   - TLS or Noise-style encrypted channel,
   - certificate/public-key pinning,
   - challenge-response from both sides,
   - replay protection,
   - device revocation.
8. Continue runtime resource policy polish:
   - surface model unload status in runtime logs/UI,
   - report provider-specific unload failures without breaking chat,
   - add manual unload controls when trusted-device UX is hardened.
9. Improve model capability metadata:
   - chat vs embedding vs vision,
   - context window,
   - reasoning/think support,
   - tool/Python/web/search support when those arrive.
10. Expand automated smoke tests for:
   - pairing,
   - authenticated model list,
   - streaming chat,
   - cancel generation,
   - suggested next questions,
   - attachment ingestion,
   - untrusted client rejection.

## Current QR And Different-Network Pairing State

- QR scanning is implemented on the client side through the app scanner and `aetherlink://pair` deep links.
- The client can parse and persist relay route metadata from QR payloads: `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- The runtime app can configure an outbound development relay route and include that route in QR payloads when the route is eligible.
- Normal runtime QR generation now requires eligible remote route material instead of silently falling back to a local-IP QR. Local direct QR generation remains a diagnostic/development mode only.
- Android direct route selection now rejects Ollama and LM Studio backend ports from QR, saved, discovered, or manual direct endpoint candidates; the client still connects only to the AetherLink runtime protocol.
- Verified on 2026-06-25 that the current Android debug build compiles, app unit tests pass, string/copy/diff hygiene checks pass, `app-debug.apk` installs on physical device `SM-S936N - 16`, first-run Pairing shows Scan QR, camera permission is requested, the embedded scanner screen displays a live CameraX `SurfaceView`, route-failure mapping distinguishes `remote_route_unreachable`, and the relay pairing deeplink smoke still completes `pairing.request` plus `runtime.health`.
- Remaining gap: true "no setup, different-network, QR-only" pairing still requires production rendezvous/P2P/relay allocation infrastructure. The current relay path proves the route shape but is not the final Bitcoin-like bootstrap network.

## Roadmap After Current v0.1-Plus Work

### v0.2 Session, History, And Memory Polish

- Search and rename previous chats.
- Improve archive/delete UX and make source inclusion rules explicit.
- Add Mac/runtime-side session storage where appropriate.
- Preserve final answer, reasoning/think text, attachments, suggested next questions, and usage metadata.
- Add context-window-aware session compaction:
  - detect when a session approaches or exceeds the selected model context window,
  - compact older turns into structured summaries,
  - keep recent messages raw,
  - preserve source pointers to original transcript segments.
- Add long-inactivity memory summarization:
  - define inactivity criteria separate from the 10-minute model-unload rule,
  - summarize long-unused chat history into modern compact memory summaries,
  - keep archived chats excluded unless restored or explicitly selected.

### v0.3 Embeddings And Research

- Keep embedding models separate from chat/text-generation models.
- Let the user choose one embedding model from the runtime-provided embedding list.
- Use the selected embedding model for:
  - semantic search over prior chats,
  - memory lookup,
  - duplicate detection,
  - clustering and deduplication suggestions,
  - retrieval over user-approved files,
  - deep-research-like notebooks and briefs.
- Add source snippets and citations for any research output.
- Keep indexing, retrieval, ranking, and research generation in the runtime/server layer.

### v0.4 File, Image, And Multimodal Workflows

- Route all file/image inputs through the runtime.
- Automatically expose image input when the selected model is vision-capable.
- Support broad document ingestion with chunking, metadata, and parse quality indicators.
- Add size limits, resumable transfer, and source permission prompts.
- Add project/workspace file source selection before using files as model context.

### v0.5 Permission Broker, Python Tools, And Skills

- Add a runtime-side permission broker for sensitive actions.
- Add internal Python execution for deterministic tasks such as calculations, tables, data inspection, and small scripts.
- Require approval and audit logs for Python, terminal, file, network, web search, MCP, and skills.
- Add a skill registry after the permission model exists.
- Keep mobile clients as approval/status surfaces, not execution environments.

### v0.6 Web Search

- Web search should be runtime-mediated.
- Do not rely on the client app calling search providers directly.
- Add a search provider abstraction so Ollama-provided web search, SearXNG/custom endpoints, browser-backed search, or future provider APIs can be swapped behind one runtime interface.
- Treat LM Studio web search as backend-dependent, not a universal assumption; if LM Studio does not expose equivalent search in the local server mode, AetherLink's runtime search abstraction should provide the feature independently.
- Store citation-ready metadata and source snippets.
- Require permission prompts when search is combined with project files, tools, or automation.

### v0.7 MCP

- Add runtime-side MCP server registry.
- Add scoped MCP permissions.
- Add mobile approval UI for tool calls.
- Keep MCP off the client and behind runtime trust boundaries.

### v0.8 Projects

- Add project/workspace objects similar to ChatGPT Projects:
  - project chats,
  - project files,
  - project instructions,
  - project memories,
  - project indexes,
  - project model/backend preferences.
- Add trusted-source controls for which files, folders, chats, memories, and search results may be used as context.
- Add project-level research reports with citations.
- Keep project indexing and retrieval in the runtime/server layer.

### v0.9 Scheduling And Automation

- Add runtime/server scheduler for:
  - scheduled tasks,
  - reminders,
  - monitors,
  - recurring automations,
  - runtime-triggered jobs.
- Add explicit permissions, audit logs, pause/resume/cancel, and result review.
- Require fresh approval before automations use sensitive files, tools, Python, terminal, web search, MCP, or model backends.

### v1.0 Platform Expansion

- Expand client/controller targets from Android to iOS.
- Expand runtime/server targets from macOS to Windows and DGX OS-class systems.
- Preserve the same trust boundary across platforms:
  - clients control and approve,
  - runtime/server targets mediate all model, file, tool, search, memory, and project access.
- Preserve the same device-identity connection model across all platforms so users do not manage IP addresses differently per operating system.

### v1.1 Serving Backend Expansion

- Add more serving backend adapters beyond Ollama and LM Studio.
- Normalize capability metadata across backends:
  - health,
  - installed/running models,
  - chat,
  - embeddings,
  - vision,
  - reasoning/think,
  - context window,
  - streaming,
  - cancellation,
  - structured errors.
- Never expose backend-specific local URLs to client apps.

## 2026-06-24 QR Pairing And Relay Status

- Current QR pairing is partially working, not complete product-grade QR-only pairing.
- Android can consume `aetherlink://pair` payloads through the QR/deeplink handler and can send `pairing.request` after it resolves a route.
- Physical device relay deeplink smoke passed on `SM-S936N` with the temporary development relay and USB reverse mappings.
- A relay encryption ordering bug was fixed by moving Android relay frame encryption inside the send mutex. This prevents concurrent post-pairing requests from corrupting the AES-GCM frame counter and producing `CryptoKitError` invalid-payload responses from the runtime.
- Android now has a relay regression test that opens a real local relay-style TCP handshake, sends many encrypted frames concurrently, and verifies the runtime side can decrypt every client frame in stream order.
- QR scanner failures now include a localized fallback detail when Google Code Scanner cannot start but does not provide a useful error message.
- Android's QR scanner enables Google Code Scanner auto zoom to improve real camera capture when the pairing QR is small or farther from the device.
- General UI copy now avoids presenting Ollama or LM Studio as client-visible connection targets. Provider names remain only in provider-specific health/status/error contexts.
- QR route status now treats relay retrying and identity-without-route cases as route guidance instead of a blocking generic error card.

Remaining QR work:

- Manual camera scan is still not fully verified. The passing smoke injects the QR URI as an Android VIEW intent and does not test Google Code Scanner optical scanning or Play Services scanner behavior.
- Different-network pairing requires a reachable remote route in the QR. An identity-only QR or raw local IP QR cannot cross unrelated networks.
- The current relay is development transport scaffolding. Product-grade QR-only pairing still needs automatic remote route allocation, NAT traversal or encrypted relay fallback, key rotation, replay-resistant session setup, and real end-to-end transport hardening.

## 2026-06-25 QR Remote Route Guardrails

- macOS runtime QR generation now separates "relay settings are syntactically eligible" from "relay route is actually ready for QR use".
- Normal remote pairing QR generation requires the runtime to be registered with the configured relay before the QR is produced. A configured relay that is still stopped, connecting, reconnecting, or failed no longer produces a remote pairing QR that is likely to fail after scan.
- Loopback and `.local` relay hosts remain blocked for normal remote QR generation because another network cannot reach them reliably.
- Private-network relay hosts are now allowed after warning when the relay is registered. This supports VPN, tunnel, and user-managed private overlay cases where a private address is reachable from both devices.
- The macOS relay diagnostics form now rejects URL-shaped relay host input such as schemes, paths, userinfo, query strings, or `host:port` values. The host/IP and port must be entered separately so QR payloads do not contain unusable socket targets.
- The Pairing and Status panels now tell the user to start the runtime and wait until relay registration before generating the QR, instead of presenting a configured but unregistered relay as ready.
- Logs localize the new `Remote pairing QR not generated: relay route <endpoint> is not ready` state.

Verified after this change:

- `swift test --filter CompanionCoreTests.LocalRuntimeMessageRouterTests`
- `swift test --filter RelayServerCoreTests`
- `swift build --product AetherLinkRelay`
- `python3 script/check_macos_localization.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest :app:compileDebugKotlin --no-daemon --console=plain`

Remaining QR work:

- Real optical camera scan still needs manual verification on the physical device. The current Android smoke injects the QR URI and validates post-scan app behavior, but it does not prove camera capture.
- A reachable relay still has to be provided by the user or future infrastructure. This change prevents bad QR generation and supports VPN/tunnel private relays, but it does not implement automatic relay allocation or P2P NAT traversal.
- Add a fallback path for Android devices where Google Play Services Code Scanner cannot start, such as manual QR payload paste first and CameraX scanner later.
- Run the no-`adb reverse` external relay smoke against a real mutually reachable relay host, so different-network QR/deeplink coverage is closer to the real product path.

## 2026-06-25 Android QR Payload Fallback

- Android Pairing and Settings now expose a secondary QR payload input path next to the scanner.
- The fallback accepts pasted `aetherlink://pair` text and sends it through the same `trustRuntimeFromPairingQr` parser, route selection, identity pinning, and pairing request flow as optical QR scan results.
- Blank pasted input is disabled before submit; copied QR text is trimmed before submission.
- Google Code Scanner failure copy now points users to the manual QR payload input as a recovery path.
- The fallback is localized across the current five UI languages plus the default resource set.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:installDebug --no-daemon --console=plain` on physical `SM-S936N`

Remaining QR work:

- Real optical camera scan still needs physical-device verification.
- A bundled CameraX/ML Kit scanner remains useful as a later fallback for devices without working Google Play Services Code Scanner.
- A no-`adb reverse` external relay smoke still needs to be run against a real mutually reachable relay host.

## 2026-06-25 Embedded QR Scanner And Remote Route Failure Split

- Android moved from the Play Services code-scanner dependency to an embedded CameraX + ML Kit QR scanner path.
- The scanner screen now shows a live camera preview with a centered scan frame and keeps the manual QR payload input fallback for recovery/debug use.
- Successful scanner reads trigger haptic feedback before the parsed `aetherlink://pair` payload enters the normal trust/route/pairing flow.
- Route availability notices in Chat, Pairing, and Connection Status now keep the scan-latest-QR action visible where possible.
- Android now distinguishes exhausted relay-pairing retries from identity-only QR route failure:
  - relay QR present but not reachable -> `remote_route_unreachable` with `route_diagnostic_relay_failed`;
  - identity-only QR with no reachable route -> `pairing_endpoint_unavailable`.
- This makes failed scans easier to diagnose without exposing Ollama, LM Studio, or raw backend URLs to the client.
- The decoded QR schema now matches the runtime policy for relay hosts: loopback and `.local` remain invalid remote QR hosts, while private relay addresses are allowed for user-managed VPN, tunnel, and private overlay routes. The schema checker now fails if private address ranges are reintroduced as forbidden relay hosts.
- `script/android_pairing_deeplink_smoke.sh` now supports `--external-relay-host` and `--external-relay-port`. In that mode the script injects the QR URI over USB but does not start a local relay or configure `adb reverse` for the relay; Android must reach the provided relay address through normal networking.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_protocol_schema.py`
- `git diff --check`
- `bash -n script/android_pairing_deeplink_smoke.sh`
- `script/android_pairing_deeplink_smoke.sh --help`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:installDebug --no-daemon --console=plain` on physical `SM-S936N`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install`

Remaining QR work:

- The CameraX screen and permission flow have been physically checked, but real optical decoding of the actual macOS QR should still be verified with a runtime-generated remote-route QR.
- Different-network QR-only pairing still requires a reachable route in the QR. The current implementation supports a configured encrypted development relay; it does not yet provide automatic relay allocation, NAT traversal, DHT/bootstrap rendezvous, or production P2P.
- Run `script/android_pairing_deeplink_smoke.sh --relay --external-relay-host <relay-host>` against a mutually reachable relay host. The script path exists now; this still needs a real relay endpoint outside USB reverse to prove closer different-network behavior.
- Add relay setup automation or a production bootstrap/relay design so users do not manually configure relay host/port in the final product.

## 2026-06-25 QR Relay Smoke Diagnostics

- `script/android_pairing_deeplink_smoke.sh` now preflights runtime-host TCP reachability when `--external-relay-host` is provided. If the runtime host cannot reach the relay, the smoke exits before generating a QR that the Android app cannot complete.
- `RuntimeDevServer` now mirrors the GUI runtime's relay QR readiness gate for development pairing. When `AETHERLINK_DEV_PAIRING=1` and a relay route is configured, it waits until the relay client reports `waiting_for_peer` or `ready` before emitting `AETHERLINK_DEV_PAIRING_INFO`. If the relay never becomes ready, it prints a clear diagnostic and does not emit a QR payload that is likely to fail after scan.
- Android runtime connection failures now write structured logcat fields: `code=<ui error code>`, `diagnostic=<route diagnostic code>`, and the target route label. This gives physical-device QR smoke tests a stable signal for whether the app handled the QR and then failed at relay routing.
- The smoke artifact dump now reads those structured Android logs and distinguishes "Android handled the QR but the relay was unreachable" from "the deeplink launched but no runtime route attempt appeared".
- The smoke now validates decoded pairing info before injecting the deeplink:
  - relay mode requires `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`;
  - external relay mode requires the QR relay host to match the requested external host;
  - default relay QR payloads must not silently include direct `host`/`port` fields;
  - direct QR payloads must not include relay fields.
- Pairing-timeout diagnostics now distinguish the main relay states:
  - `relay status=failed` means the runtime host could not register with the relay;
  - `relay status=waiting_for_peer` means the runtime host reached the relay and the Android client has not joined it;
  - `relay status=ready` means the relay matched both peers and failure is now in pairing/auth/protocol handling.
- This makes failed different-network smoke runs actionable, but it does not replace production automatic relay allocation, NAT traversal, or end-to-end transport hardening.

Verified after this change:

- `bash -n script/android_pairing_deeplink_smoke.sh`
- `script/android_pairing_deeplink_smoke.sh --help`
- `swift build --product RuntimeDevServer`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --external-relay-host localhost --skip-install` rejected loopback external relay input as expected.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay` passed on physical `SM-S936N` after installing the current debug APK.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install` passed on physical `SM-S936N` after the RuntimeDevServer relay readiness gate; the runtime log showed `Waiting for relay route ...`, `relay status=waiting_for_peer`, then `AETHERLINK_DEV_PAIRING_INFO`.

Remaining QR work:

- Real optical camera decoding of the macOS-generated QR still needs manual physical-device verification.
- The no-`adb reverse` external relay smoke still needs a mutually reachable relay host outside USB forwarding.
- Product QR-only different-network pairing still needs automatic relay/rendezvous allocation, NAT traversal, replay-resistant sessions, key rotation, and production transport hardening.

## 2026-06-25 Android Chat Route CTA Polish

- The empty Chat screen now uses the route failure state to choose its primary action. When a trusted runtime has a failed, expired, or missing remote route, the central empty-state CTA switches from reconnecting the stale route to `Scan latest QR`, matching the bottom route notice and the QR-first recovery flow.
- The same screen still keeps the normal connect action when there is a trusted runtime but no route-refresh error, so local/dev reconnect is not removed.
- The chat model picker now disables not-installed chat model rows instead of allowing selection of a model that immediately leaves the composer unsendable. Installing models should become a separate explicit action in a later model-management pass.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:installDebug --no-daemon --console=plain` on physical `SM-S936N`
- Physical-device screenshot confirmed the empty Chat CTA now reads `Scan latest QR` when the saved remote route failed.
- Physical-device check confirmed `Scan latest QR` opens the in-app QR scanner permission flow, but this does not mean product-grade QR pairing is complete. Full QR-only pairing across unrelated networks still needs reachable route material in the QR plus production rendezvous/P2P/relay allocation.

## 2026-06-25 Mac Pairing QR Auto-Generation

- The macOS companion now remembers a remote QR generation request when the user presses Generate Pairing QR before the configured relay route has reached `waiting_for_peer` or `ready`.
- Once the relay status becomes QR-ready, the companion automatically generates the pairing QR. The user no longer has to press Generate Pairing QR a second time after the runtime finishes registering with the relay.
- The Pairing view copy now tells users to keep the window open because the QR appears after the runtime registers with the relay. This copy is localized for English, Korean, Japanese, Simplified Chinese, and French.
- This reduces the most common "QR does not work" setup race in the current relay-backed development path. It does not implement automatic relay allocation, NAT traversal, DHT/bootstrap rendezvous, or production P2P.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsRelaySettingsAndIncludesRelayInQRCodeAfterRelayReady --filter LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsPrivateRelayHostAfterRelayRegistration --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRelayConnectionStatus`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --keep-app-data` passed on physical `SM-S936N`, confirming the relay QR deeplink path still reaches pairing and runtime health.

Remaining QR work:

- Real optical scanning of a macOS-generated remote-route QR should still be checked on the physical device.
- A no-USB, no-`adb reverse` different-network smoke still needs a mutually reachable external relay endpoint.
- Product QR-only different-network pairing still needs automatic route allocation and hardened P2P/relay session setup.

## 2026-06-25 Android Persistence And Reconnect Polish

- Android Settings now keeps a visible saved embedding-model row when the stored embedding model is not in the currently loaded runtime model list yet. This makes app restart, reconnect, and model-list loading states read as "restoring saved selection" instead of looking like the embedding selection was cleared.
- Saved model IDs use the same provider-prefix cleanup as the chat model selector, so stored IDs such as `ollama:nomic-embed-text` display as `nomic-embed-text` while the runtime model list is still loading.
- Trusted-runtime connection retry is now identity-based instead of relay-only. If auto reconnect is enabled and a trusted direct route fails, the app schedules the same delayed reconnect path used by relay routes. Explicit Disconnect still disables auto reconnect and cancels retries.
- This improves the "leave the app and come back" path for local/direct routes, but different-network QR-only pairing still depends on a QR-provisioned relay or future P2P route.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:installDebug --no-daemon --console=plain` on physical `SM-S936N`

## 2026-06-25 QR Pairing Route Hardening

- macOS pairing QR payloads now use canonical `runtime_device_id`, `runtime_name`, and `runtime_key_fingerprint` fields. Android still accepts legacy `mac_device_id`, `mac_name`, and `fingerprint` aliases for compatibility, but newly generated camera QR codes avoid those duplicate fields so dense relay QR payloads are easier to scan.
- Android trusted-route refresh no longer writes a scanned route-refresh QR into persistent trusted-runtime storage before trying the route. The app now keeps the scanned QR as temporary pending route material, attempts to connect through it, then persists the refreshed route only after the socket connection succeeds.
- This reduces the failure mode where an unreachable or stale QR immediately overwrites the last usable trusted runtime route.
- Initial QR pairing still requires reachable route material. If the client and runtime host are not on the same network, the QR must include a configured reachable relay route in the current implementation. Automatic relay allocation, NAT traversal, and production P2P remain unfinished roadmap work.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `swift test --filter LocalRuntimeMessageRouterTests`

## 2026-06-25 Runtime Proof In Auth Challenge

- The runtime now signs `auth.challenge` with its persistent runtime identity when a signer is available, and the challenge carries `runtime_key_fingerprint` plus `runtime_signature`.
- Android verifies the signed runtime proof before it signs the challenge nonce when a trusted runtime has a pinned `runtime_public_key`. A mismatch now fails client-side with `runtime_authentication_failed`.
- Pairing remains backward-compatible for legacy trusted records that do not yet have a pinned runtime public key, but QR records generated by the companion now carry the runtime key material needed for proof verification.
- This makes QR-based trust harder to spoof after pairing. It does not finish product-grade QR-only cross-network pairing: automatic relay allocation, NAT traversal, rendezvous, session encryption hardening, and route rotation are still required.
- The current debug build was installed on the physical `SM-S936N` Android device after verification.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `swift test --filter LocalRuntimeMessageRouterTests --filter RuntimeIdentityKeyStoreTests`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_protocol_schema.py`
- `git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :app:installDebug --no-daemon --console=plain` on physical `SM-S936N`

## 2026-06-25 Remote Route Allocator Seam

- The current QR failure mode was narrowed with two GPT-5.5 subagent audits and direct code inspection: identity-only QR cannot cross unrelated networks, and Android already waits for LAN discovery unless the QR carries remote route material. Android must still never call Ollama or LM Studio directly.
- macOS `CompanionAppModel` now has a `CompanionRemoteRelayRouteAllocating` seam. `beginPairing()` can ask this allocator for relay route material before falling back to the existing manual Remote Relay settings.
- The default allocator reads explicit bootstrap environment keys such as `AETHERLINK_BOOTSTRAP_RELAY_HOST`, `AETHERLINK_BOOTSTRAP_RELAY_PORT`, `AETHERLINK_BOOTSTRAP_RELAY_ID`, and `AETHERLINK_BOOTSTRAP_RELAY_SECRET`. This keeps the UI path from being hard-wired only to manually typed relay hosts and creates the insertion point for future automatic rendezvous/DHT/relay allocation.
- Automatically allocated relay hosts reject loopback/local-only style addresses before QR generation. Tests verify allocator-provided QR payloads include relay fields and omit local `host`/`port`.
- `RuntimeDevServer` now accepts the same `AETHERLINK_BOOTSTRAP_RELAY_*` keys as a relay source, while preserving the older `AETHERLINK_RELAY_*` path.
- This is not the final QR-only-any-network product path yet. A real production route allocator still needs bootstrap/rendezvous infrastructure, NAT traversal, relay allocation, route rotation, hardened session encryption, and no-USB optical QR verification.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsUnreachableRemoteRouteAllocation`
- `swift test --filter LocalRuntimeMessageRouterTests --filter RuntimeIdentityKeyStoreTests`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon --console=plain`

## 2026-06-25 Relay Allocation Service Slice

- The development relay now accepts `AETHERLINK_RELAY allocate <route_token>` and returns service-issued QR route material: `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- The relay stores allocated relay ids with TTL. Existing manual relay handshakes still work by default for legacy/dev scripts, but `AetherLinkRelay --require-allocation` rejects unknown or expired relay ids before matching runtime/client sockets.
- macOS bootstrap allocation now calls the relay allocation line protocol when `AETHERLINK_BOOTSTRAP_RELAY_HOST` is set without explicit `AETHERLINK_BOOTSTRAP_RELAY_ID` and `AETHERLINK_BOOTSTRAP_RELAY_SECRET`. Incomplete static bootstrap overrides are rejected instead of silently generating half-local route material.
- `RuntimeDevServer` now treats `AETHERLINK_RELAY_*` as the legacy/manual path and `AETHERLINK_BOOTSTRAP_RELAY_*` as the service-allocation path.
- This removes one more fixed/manual route-material step, but it still requires a mutually reachable relay host. Production QR-only any-network pairing still needs bootstrap peer selection, NAT traversal, relay allocation hardening, abuse controls, route rotation, and session encryption hardening.

Verified after this change:

- `swift test --filter RelayAllocationTests --filter RelayHandshakeTests --filter LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorRequestsBootstrapServiceAllocation --filter LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorRejectsIncompleteStaticBootstrapOverride`
- `swift test --filter RelayAllocationTests --filter RelayHandshakeTests --filter RelayMatcherTests --filter LocalRuntimeMessageRouterTests --filter RuntimeIdentityKeyStoreTests`
- `swift build --product AetherLinkRelay`
- Local socket smoke: `AETHERLINK_RELAY allocate <route_token>` returned relay allocation JSON from `AetherLinkRelay --require-allocation`.
- Local socket smoke: `AetherLinkRelay --require-allocation` rejected an unallocated `AETHERLINK_RELAY runtime <relay_id>` handshake.

## 2026-06-25 Relay Allocation QR Smoke Integration

- The RuntimeDevServer bootstrap relay path now carries the full service-issued allocation into the development QR payload. It preserves `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce` from the allocation service instead of replacing the lease fields locally.
- `script/runtime_authenticated_mock_smoke.swift --relay` now starts the Swift `AetherLinkRelay --require-allocation`, starts RuntimeDevServer with `AETHERLINK_BOOTSTRAP_RELAY_HOST/PORT`, reads the runtime-printed QR payload, and connects the smoke client using the QR-provided `relay_id` and `relay_secret`.
- `script/android_pairing_deeplink_smoke.sh --relay` now uses the same allocation-required Swift relay path instead of manually injecting `AETHERLINK_RELAY_ID` and `AETHERLINK_RELAY_SECRET`.
- `script/run_different_network_dev_runtime.sh` now defaults to `AETHERLINK_BOOTSTRAP_RELAY_*` allocation. The legacy manual `AETHERLINK_RELAY_ID/SECRET` path remains available only when both are explicitly provided.
- `script/run_different_network_dev_runtime.sh` accepts repeated `--relay-endpoint <host[:port]>` values or a comma-separated `AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS` value. It still supports `--relay-host/--relay-port` for the single-endpoint path and keeps the relay as development bootstrap infrastructure, not a cloud backend or production NAT traversal layer.
- Its multi-endpoint preflight mirrors the runtime allocator's ordered fallback behavior: try endpoints in order, proceed after the first allocation success, and fail only when every configured allocation endpoint fails.
- `AetherLinkRelay --require-allocation` now keeps an allocated relay id valid until TTL expiration instead of deleting it after the first runtime/client match. This is required because QR pairing opens a pairing connection first, then an authenticated runtime connection with the same route material.
- Physical-device QR deeplink smoke now passes through an allocation-required relay route on the connected Android device. This validates the app deeplink, pairing request, and runtime health path with QR route material. It still uses USB `adb reverse` for local relay reachability, so it is not yet a no-USB external-network proof.

Verified after this change:

- `./script/runtime_authenticated_mock_smoke.swift --relay`
- `script/android_pairing_deeplink_smoke.sh --relay` on physical Android device `R3CXC0M76VM`
- `swift test --filter RelayAllocationTests --filter RelayHandshakeTests --filter RelayMatcherTests --filter LocalRuntimeMessageRouterTests --filter RuntimeIdentityKeyStoreTests`
- `swift build --product RuntimeDevServer`
- `swift build --product AetherLinkRelay`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon --console=plain`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

Remaining QR work:

- True QR-only different-network pairing still needs a relay/bootstrap endpoint that both devices can reach without USB forwarding.
- Real optical scanning of the macOS-generated QR should still be checked against the same allocation route.
- Production-grade route allocation still needs hardened bootstrap identity, relay abuse controls, route rotation, replay protection, session encryption hardening, and NAT traversal/P2P fallback.

## 2026-06-25 External Relay Preflight Path

- Added `script/run_allocation_relay.sh` as the simplest way to run the Swift development relay in allocation-required mode on a public, VPN, tunnel, or overlay-reachable host.
- `script/android_pairing_deeplink_smoke.sh --relay --external-relay-host ...` now checks more than TCP reachability. It sends `AETHERLINK_RELAY allocate <route_token>` and validates the allocation response before starting RuntimeDevServer, so a plain open port or wrong relay process fails before a QR is generated.
- `script/run_different_network_dev_runtime.sh` now performs the same allocation preflight when using the bootstrap allocation path. This keeps the printed QR from containing route material from a relay endpoint that does not actually support AetherLink allocation.
- The legacy manual relay path remains available only when both `AETHERLINK_RELAY_ID` and `AETHERLINK_RELAY_SECRET` are explicitly provided. The default path is allocation-based.
- This closes another common "QR scanned but pairing never completes" development failure: wrong relay endpoint, stale relay process, or Python legacy relay running where allocation is expected.

Verified after this change:

- `bash -n script/android_pairing_deeplink_smoke.sh`
- `bash -n script/run_different_network_dev_runtime.sh`
- `bash -n script/run_allocation_relay.sh`
- `script/run_allocation_relay.sh --help`
- `script/run_different_network_dev_runtime.sh --help`
- `script/android_pairing_deeplink_smoke.sh --help`

Remaining QR work:

- Run the no-USB external relay smoke against a real mutually reachable host: first start `script/run_allocation_relay.sh` on that host, then run `script/android_pairing_deeplink_smoke.sh --relay --external-relay-host <host> --external-relay-port <port>`.
- Real product onboarding still needs automatic relay/bootstrap selection so users do not manually supply relay host/port.
- Optical QR scan of the macOS-generated allocation route still needs physical verification.

## 2026-06-25 Bootstrap Relay Fail-Closed And URI Output

- RuntimeDevServer now fails closed when `AETHERLINK_BOOTSTRAP_RELAY_HOST` is set but relay allocation does not produce route material. It no longer silently emits a fallback `127.0.0.1` development QR unless `AETHERLINK_DEV_PAIRING_HOST` is explicitly set for local diagnostics.
- RuntimeDevServer now prints `AETHERLINK_DEV_PAIRING_URI` next to `AETHERLINK_DEV_PAIRING_INFO`, using the same `PairingSession.qrPayload` generator as the macOS companion. This makes no-ADB external relay tests easier because the operator can turn the URI into a QR or paste it into Android's manual QR payload input.
- Added `script/no_adb_external_relay_pairing_smoke.sh`, a first-class no-ADB development smoke for external relay QR pairing. It starts RuntimeDevServer with bootstrap allocation, saves the exact `AETHERLINK_DEV_PAIRING_URI`, creates a QR PNG through `qrencode` or the repo-local Swift/CoreImage fallback, validates the emitted URI is relay-only and matches the requested relay host/port, and then waits for `relay status=ready`, `Development pairing accepted`, and `runtime.health`.
- The no-ADB smoke does not install the Android app, call `adb`, inject deeplinks, read logcat, or configure `adb reverse`. It is intended for optical QR or Android manual QR payload input against a relay host both devices can actually reach.
- The script does not print the full URI by default because it contains temporary pairing and relay secrets. `--print-uri` is explicit and warns before writing the secret-bearing URI to terminal scrollback.
- `script/run_allocation_relay.sh` now points users to the no-ADB smoke for different-network pairing and keeps the USB-assisted deeplink smoke as a separate regression path.
- Added `script/render_pairing_qr.swift`, a dependency-free Swift/CoreImage QR PNG renderer for pairing URIs. The no-ADB smoke now uses `qrencode` when available and falls back to this repo-local renderer, so optical QR artifacts can be generated on a stock macOS development machine without Homebrew.

Verified after this change:

- `swift build --product RuntimeDevServer`
- `swift build --product AetherLinkRelay`
- `swift test --filter RelayAllocationTests --filter RelayHandshakeTests --filter RelayMatcherTests --filter LocalRuntimeMessageRouterTests --filter RuntimeIdentityKeyStoreTests`
- `./script/runtime_authenticated_mock_smoke.swift --relay`
- Bootstrap fail-closed smoke: invalid static bootstrap relay override did not emit `AETHERLINK_DEV_PAIRING_INFO`.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `script/android_pairing_deeplink_smoke.sh --relay` on physical Android device `R3CXC0M76VM`
- `bash -n script/no_adb_external_relay_pairing_smoke.sh`
- `script/no_adb_external_relay_pairing_smoke.sh --help`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 5`
- `swiftc -typecheck script/render_pairing_qr.swift`
- `script/render_pairing_qr.swift --input 'aetherlink://pair?version=1&pairing_code=123456&relay_secret=test' --output <tmp>/qr.png`
- PNG header validation for the generated QR artifact.

Remaining QR work:

- Run a full no-ADB external relay test with `script/no_adb_external_relay_pairing_smoke.sh --relay-host <host> --relay-port <port>` against a mutually reachable relay host, then scan the generated QR or paste the URI from Android.
- Replace development relay allocation with production hardened rendezvous/relay allocation and P2P/NAT traversal.

## 2026-06-25 QR Pairing Reliability Pass

- Fixed a likely Android-side QR pairing failure where `relay_expires_at` values encoded as epoch seconds were interpreted as epoch milliseconds. A relay QR with `relay_expires_at=4102444800` is now normalized to `4102444800000`, so Android does not reject a valid remote route as already expired before sending `pairing.request`.
- Android now treats `relay_expires_at` and `relay_nonce` as saved relay route lease data, not as the lifetime of the stored trusted runtime relationship. Initial QR pairing and trusted route refresh still reject already-expired QR material, and successful trusted runtime records persist the relay host/id/secret/lease/nonce so reconnect can diagnose stale route material explicitly.
- Existing trusted runtime records that contain stale relay lease fields now preserve those fields so reconnect can report route expiration instead of flattening it into a generic unreachable route.
- macOS companion QR generation now requests a fresh bootstrap relay allocation even when an older relay route is already marked ready. The runtime relay client is restarted with the allocated `relay_id` and `relay_secret`, then QR generation waits until that exact fresh route reaches relay readiness.
- The pending macOS "generate remote QR when relay ready" flow now consumes the ready allocated route without re-allocating in a loop. The QR includes `relay_host`, `relay_port`, allocated `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`, and still does not expose Ollama or LM Studio details to the client.
- Latest Android APK was built, installed, and launched on physical device `R3CXC0M76VM` / `SM-S936N`.
- `script/android_pairing_deeplink_smoke.sh --relay --skip-install` passed on the physical device after these fixes. This validates the post-QR-result path: Android receives the `aetherlink://pair` URI, connects through the encrypted relay route, sends `pairing.request`, receives accepted pairing, and reaches `runtime.health`.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest --no-daemon --console=plain`
- `swift test --filter LocalRuntimeMessageRouterTests --filter RelayAllocationTests --filter RelayHandshakeTests --filter RelayMatcherTests`
- `python3 script/check_protocol_schema.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 5 --work-dir <tmp>`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_usb_install.sh`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install`

Remaining QR work:

- Real optical QR scanning with the phone camera still needs a manual check against a runtime-generated remote-route QR.
- True no-USB different-network proof still needs a relay/bootstrap host reachable from both the runtime host and the phone network, then `script/no_adb_external_relay_pairing_smoke.sh --relay-host <host> --relay-port <port>` should be run and completed by scanning the generated QR.
- Product-grade "no constraints, QR only" pairing still requires automatic bootstrap/rendezvous/relay selection plus hardened P2P/NAT traversal. The current path is a working development relay route, not the final Bitcoin-like private overlay.

## 2026-06-25 Android Chat Empty-State And Reasoning Polish

- Android chat no longer shows a static central "start a conversation" panel when the app is already connected and a usable chat model is selected. The empty chat surface stays quiet like a chat workspace and only shows an action panel when something needs attention, such as route refresh, runtime connection, model selection, or streaming state.
- Suggested next questions are now shown only when the runtime returns actual `message.suggestions`. The UI no longer displays an empty "generating suggestions" area as if suggestions already exist.
- Assistant reasoning remains collapsed by default to a subdued three-line preview, with clearer expand/collapse copy and lower visual emphasis so it reads closer to a secondary "thinking" trace instead of main answer content.
- The no-model empty-state copy is OS-neutral and no longer refers to a fixed "top menu"; it now tells the user to pick a model before sending.
- Latest Android debug APK was reinstalled on physical device `R3CXC0M76VM` / `SM-S936N`. A screenshot was captured at `artifacts/android-aetherlink-chat-empty-polish.png`; the visible center state is now a route-repair action (`Scan latest QR`) rather than a static example/start prompt.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" :app:compileDebugKotlin --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check -- <Android UI files>`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_usb_install.sh`
- Physical device screenshot capture with `adb exec-out screencap`.

## 2026-06-25 QR Route Fallback And Relay Bootstrap Hardening

- The current QR pairing failure mode was re-checked with two GPT-5.5 subagent audits and direct code inspection. The code can parse and submit QR pairing payloads, but different-network pairing still requires QR route material that is reachable by both the runtime host and client device.
- Android now preserves a scanned direct endpoint as a fallback even when the same QR also includes relay route material. The connection manager still prepares relay routes first, but a paired runtime record no longer loses its last-known direct/local route simply because a relay route exists.
- Android trusted-runtime restore now keeps local discovery active even for trusted runtimes that have a relay route. This allows a paired runtime to recover through Bonjour/local discovery when the saved relay is unreachable and the devices later return to the same local network.
- Android permanent chat deletion is now guarded at the ViewModel and store-helper level: active chats must be archived before permanent deletion. Bulk dangerous actions remain Settings-only and double-confirmed.
- The macOS companion now treats `AETHERLINK_BOOTSTRAP_RELAY_HOST/PORT` as configured relay context in the GUI path, and automatic relay allocation allows private relay addresses when the user controls a VPN/tunnel/private overlay that makes the address reachable from both devices.
- RuntimeDevServer no longer silently creates an unallocated static route from `AETHERLINK_RELAY_HOST` alone. If `AETHERLINK_RELAY_ID` and `AETHERLINK_RELAY_SECRET` are not both supplied, the legacy host is treated as an allocation relay and the printed QR uses allocated `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- README relay instructions now prefer `AETHERLINK_BOOTSTRAP_RELAY_HOST/PORT` and document the legacy static mode only as an explicit ID/secret path.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsUnreachableRemoteRouteAllocation --filter LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsPrivateRelayHostAfterRelayRegistration`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py`

Remaining QR work:

- A true no-USB different-network proof still needs a relay/bootstrap endpoint that the runtime host and the physical phone can both reach without ADB forwarding.
- Real optical QR scanning should be verified against a runtime-generated remote-route QR after that reachable relay is available.
- Product-grade "QR only with no network constraints" still requires automatic bootstrap/rendezvous/relay selection, hardened relay allocation, route rotation, P2P/NAT traversal, and production end-to-end transport hardening.

## 2026-06-25 QR Smoke Policy And Trusted Route Lease Cleanup

- Android trusted-runtime storage persists QR `relay_expires_at` and `relay_nonce` as saved relay route fields, separate from the long-lived trusted runtime identity. Saved trusted routes restore the route lease so stale relay material can be shown and rejected as expired instead of appearing ready in the UI.
- Android trusted-runtime state no longer ignores restored relay lease fields; route planning carries them into the connection layer so expiration diagnostics remain explicit.
- `script/android_pairing_deeplink_smoke.sh`, `script/no_adb_external_relay_pairing_smoke.sh`, and `script/runtime_authenticated_mock_smoke.swift` now keep relay-only QR validation as the default, but add an explicit `--allow-direct-fallback` mode for mixed-route diagnostics. When that mode is enabled, the smoke validates that direct `host` and `port` appear together and that the port is valid.
- This keeps the product/default remote QR policy strict while allowing tests to cover the Android behavior that preserves a direct fallback if a diagnostic QR intentionally carries both relay and direct route material.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/run_runtime_dev_server.sh script/run_allocation_relay.sh`
- `swiftc -typecheck script/runtime_authenticated_mock_smoke.swift`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install` passed on physical device `R3CXC0M76VM`.

Remaining QR work:

- Run an external no-ADB relay proof against a relay/bootstrap host that both the runtime host and physical phone can reach without USB forwarding.
- After that route exists, perform the real optical QR scan rather than only deeplink/manual URI injection.

## 2026-06-25 macOS Pairing QR Usability Fix

- Re-checked the current QR pairing flow after the user confirmed QR pairing still does not work as a real camera-based product flow.
- The Android camera/deeplink path already feeds scanned `aetherlink://pair` payloads into the same ViewModel method, and the post-QR deeplink smoke still validates `pairing.request` through the encrypted relay path.
- The main GUI blocker was on the macOS companion side: the Pairing screen called `beginPairing()` with the default remote-required policy, so if no eligible remote relay was configured or ready, the app showed no QR at all. That made ordinary optical QR testing impossible even on the same local network.
- The macOS Pairing button now uses a remote-required QR when a relay route is configured, but falls back to explicit local diagnostic QR generation when no relay route exists. This does not claim to solve different-network pairing; it restores a usable QR path for same-network or diagnostic validation while keeping remote relay policy strict whenever a relay is configured.
- The macOS QR image is larger to reduce real-camera scan fragility with dense identity/route payloads.
- The macOS empty QR copy was updated in English, Korean, Japanese, Simplified Chinese, and French so it no longer says a relay is mandatory before any QR can be generated.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelGeneratesDirectRoutePairingQRCode --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingRequiresRemoteQRCodeRoute`

Remaining QR work:

- Run the macOS companion app and physically scan the generated local diagnostic QR from Android on the same network.
- For different-network QR-only pairing, provide or build an automatic bootstrap/relay/P2P path reachable from both devices; without that route, QR can establish identity but cannot make two unrelated networks directly reachable.

## 2026-06-25 QR Payload Size Reduction

- macOS `PairingSession.qrPayload` now emits canonical runtime identity fields only: `runtime_device_id`, `runtime_name`, and `runtime_key_fingerprint`. Legacy QR duplicates `mac_device_id`, `mac_name`, `fingerprint`, and default `service_type` are no longer emitted in camera QR URIs.
- Android still accepts the legacy aliases for older QR payloads and trusted data migration, but newly generated QR codes are shorter and better aligned with `packages/protocol-schema/pairing-qr.schema.json`.
- `runtime_key_fingerprint` is now emitted even when `runtime_public_key` is unavailable, so the QR always carries the schema-required runtime fingerprint field.
- `script/no_adb_external_relay_pairing_smoke.sh` now validates canonical QR identity fields and no longer requires legacy `fingerprint`.
- `script/android_pairing_deeplink_smoke.sh` now reconstructs canonical QR URIs from development pairing JSON. The dev JSON may remain legacy-shaped for compatibility, but injected/scanned URIs follow the current QR schema.
- A local emit-only no-ADB relay QR generated after this change was 601 characters and contained no legacy duplicate fields.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testPairingQRCodePayloadCanOmitEndpointHints --filter LocalRuntimeMessageRouterTests/testPairingQRCodePayloadIncludesRelaySecretWhenPresent --filter LocalRuntimeMessageRouterTests/testCompanionAppModelGeneratesDirectRoutePairingQRCode --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 5 --work-dir <tmp>`

Remaining QR work:

- Run an actual optical camera scan against the shorter macOS-generated QR.
- For different-network proof, repeat the no-ADB flow with a relay/bootstrap address reachable from both the runtime host and phone without USB forwarding.

## 2026-06-25 QR PNG Round-Trip Verification

- Added `script/verify_pairing_qr.swift`, a dependency-free macOS Swift verifier that loads a generated PNG, detects exactly one QR code with built-in CoreImage APIs, validates that the decoded value is an `aetherlink://pair` URI, and optionally checks that it exactly matches an expected URI file.
- `script/no_adb_external_relay_pairing_smoke.sh` now runs this verifier immediately after QR PNG generation. This covers both paths: external `qrencode` when installed and the repo-local Swift/CoreImage renderer fallback.
- This still does not replace a physical phone-camera scan, but it closes the gap where a smoke could emit a PNG file that exists but is not actually decodable as the intended AetherLink pairing URI.

Verified after this change:

- `swiftc -typecheck script/verify_pairing_qr.swift`
- `script/render_pairing_qr.swift --input <uri-file> --output <qr.png>` followed by `script/verify_pairing_qr.swift --image <qr.png> --expected <uri-file>`
- `bash -n script/no_adb_external_relay_pairing_smoke.sh script/android_pairing_deeplink_smoke.sh`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 5 --work-dir <tmp>`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `swift build --product AetherLink`

Remaining QR work:

- Run an actual optical camera scan from the Android app against the generated QR.
- Repeat the full no-ADB relay flow with a mutually reachable relay/bootstrap host, not local loopback.

## 2026-06-25 QR Pairing Route And Scanner Fix

- Re-audited QR pairing after confirming that user-visible QR pairing was still not reliable. Two GPT-5.5 subagents checked the Android QR ingestion path and the macOS/runtime route-generation path; GPT-5.3 Codex Spark was not used.
- Android camera QR scanning now accepts any nonblank barcode `rawValue` that validates as an AetherLink pairing URI instead of requiring ML Kit to report `Barcode.FORMAT_QR_CODE`. This avoids silently ignoring valid QR payloads when the scanner reports a different or unknown barcode format.
- Android pairing URI action matching is now case-insensitive in both the camera/deeplink gate and `RuntimePairingPayloadParser`, so `aetherlink://PAIR?...` and equivalent host casing cannot break pairing before parsing.
- The macOS companion Pairing button no longer silently falls back to a local diagnostic QR when no remote route is configured. Normal GUI QR generation now requires an eligible remote route, matching the different-network product direction and avoiding QR codes that look valid but cannot be reached from a phone on another network.
- macOS local diagnostic route selection was hardened for the remaining explicit diagnostic paths: bridge, utun, awdl, llw, loopback, and other virtual interface prefixes are excluded; real `en*` interfaces are preferred before other physical candidates.
- `RuntimeDevServer` no longer defaults development pairing to `127.0.0.1` when no relay is configured. If a direct development QR is needed, it now tries to choose a usable non-loopback interface address unless `AETHERLINK_DEV_PAIRING_HOST` is explicitly set.
- Physical-device relay deeplink smoke passed on `R3CXC0M76VM`: the runtime log showed `pairing.request`, `pairing.result`, `runtime.health`, `chat.sessions.list`, and `models.list` over the relay path. This proves the app/runtime pairing protocol works when the QR URI reaches the app.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `swift build --product AetherLink --product RuntimeDevServer`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRequiresRemoteQRCodeForLoopbackSavedRelayHost`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsPrivateRelayHostAfterRelayRegistration`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelGeneratesDirectRoutePairingQRCode`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 5 --work-dir <tmp>`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay`

Remaining QR work:

- Perform a real optical scan from the Android app against a remote-route QR displayed by the macOS companion/runtime.
- Run the full no-ADB different-network proof with a relay/bootstrap host reachable from both devices without USB forwarding. The local relay smoke still uses `adb reverse`, so it does not prove different-network reachability.

## 2026-06-25 Remote QR Route Hardening And Device Recheck

- Continued the QR pairing repair with GPT-5.5 subagents for Android route persistence and macOS relay QR generation. GPT-5.3 Codex Spark was not used in this session.
- Confirmed the current physical-device failure mode: Android was no longer blocked by QR scanning itself; it was restoring a previously injected development relay route pointing at `127.0.0.1:<ephemeral-port>`, so the phone retried a relay endpoint that only existed on the device itself and immediately failed with `remote_route_unreachable`.
- Android pairing QR parsing now rejects relay hosts that cannot represent a different-network route: loopback, unspecified, localhost, and `.local` names. This prevents newly scanned QR payloads from saving fake remote routes.
- Android trusted-runtime route planning now also ignores already-saved loopback relay routes. Existing bad development data no longer produces a relay connection attempt after app restart.
- Android QR parser now accepts `remote_*` and `route_*` route aliases in addition to canonical `relay_*` fields, so future QR payload naming can evolve without breaking the client.
- macOS normal remote QR generation now rejects loopback, `.local`, and private-network relay hosts unless they are explicitly environment-overridden. This prevents same-Wi-Fi or fixed-private-IP routes from being presented as different-network QR pairing.
- macOS remote route allocation no longer silently falls back to direct `host`/`port` QR material when allocation returns an unreachable relay host.
- The physical Android device `R3CXC0M76VM` was rebuilt and reinstalled. After force-stop/relaunch, logcat no longer showed `RuntimeClientVM` connection attempts or `127.0.0.1` relay failures from the saved stale route.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest :app:testDebugUnitTest --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:installDebug --no-daemon --console=plain`
- `swift test --filter CompanionCoreTests`
- `swift build --product AetherLink --product RuntimeDevServer --product AetherLinkRelay`
- `python3 script/check_protocol_schema.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`
- Physical-device relaunch check with `/Users/hanchangha/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM logcat`: no `Runtime connection failed`, no `Connecting to runtime`, and no `127.0.0.1` relay retry after launch.
- Screenshot evidence: `artifacts/android-aetherlink-after-loopback-route-guard.png`.

Remaining QR work:

- Real different-network QR-only pairing still needs a relay/bootstrap endpoint that both devices can reach without USB, same Wi-Fi, port forwarding assumptions, or a fixed LAN IP.
- The next implementation step is to make relay/bootstrap route selection automatic for normal users instead of requiring manual environment variables. Until that exists, QR can carry correct identity and route material, but it cannot make two unrelated NATed networks reachable by itself.
- After an actual reachable bootstrap route exists, repeat the test as a real optical scan from Android against the macOS-generated QR, with ADB used only for observing logs and screenshots.

## 2026-06-25 Invalid Saved Remote Route UX Guard

- Android UI route notice logic now shares the remote relay host eligibility rule with the pairing/route planner layer. A stored `127.*`, localhost, unspecified, or `.local` relay host is no longer presented as a usable encrypted remote route.
- If a trusted runtime still has stale or malformed remote route fields from an older development QR, the route notice shows a warning that the saved route cannot work across networks and asks the user to scan the latest AetherLink Runtime QR.
- Added the new route warning copy in English/default, Korean, Japanese, Simplified Chinese, and French.
- Reinstalled the updated debug app on physical Android device `R3CXC0M76VM` and confirmed the app launches without `RuntimeClientVM` route retry failures in logcat.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:installDebug --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`
- Physical-device screenshot: `artifacts/android-aetherlink-route-notice-guard-app.png`

## 2026-06-25 Startup Relay Allocation Renewal

- macOS runtime startup now refreshes a saved development relay route before starting the relay peer client when bootstrap relay configuration is present.
- The renewal path reuses the saved relay frame secret as the preferred allocation secret, persists the returned relay host, port, relay id, and secret, then starts the relay client with the renewed configuration.
- This improves scan-once persistence after a relay/bootstrap server restart or registry expiration because the runtime can re-register the paired route before clients attempt to meet it.
- Startup renewal does not generate a pairing QR by itself and does not change behavior when no bootstrap relay configuration exists.
- If a running relay route fails and bootstrap configuration is present, the macOS runtime now attempts the same saved-secret allocation renewal and restarts the relay client with the refreshed route. This reduces failures after an allocation-required relay restarts while the runtime app is already open.
- This is still development bootstrap renewal, not final automatic NAT traversal or production relay infrastructure.

## 2026-06-25 macOS Pairing Screen Remote Route Setup

- Confirmed that QR pairing was still not a finished user flow: the macOS Pairing screen required a remote-route QR, but the remote relay setup controls lived in Status, so users could reach a dead end from the actual pairing screen.
- Extracted the macOS remote relay setup UI into a reusable `RemoteRelayRoutePanel` and wired it into both Status and Pairing.
- The Pairing screen now lets the user configure the reachable relay host, port, relay frame secret, save the route, and request the latest relay QR from the same screen.
- The relay QR action now starts the existing `remoteRequired` pairing path even when the relay is eligible but still registering. In that state the app tells the user to keep the window open and lets `CompanionAppModel` publish the QR when the relay reaches `waitingForPeer` or `ready`.
- The default Pairing screen still does not generate local-IP QR material for normal pairing. Local direct routes remain diagnostics only.
- Added the new remote-route preparation/failure copy in English/default, Korean, Japanese, Simplified Chinese, and French.

Remaining QR work:

- Prove real optical QR scan from the physical Android app against the macOS Pairing screen, using a relay/bootstrap endpoint reachable from both networks.
- Replace the development relay/bootstrap configuration with the planned automatic route allocation/discovery layer so users do not need to understand relay host details.

## 2026-06-25 Android Startup Pairing Destination Guard

- Reinstalled the current Android debug build on physical device `R3CXC0M76VM` and checked the live UI/logs.
- Found a stale-state startup issue: if `pairingOnboardingCompleted=true` remained from a previous pairing smoke but no trusted runtime was present, `resolveAppDestination` could redirect the initial Pairing destination to Settings.
- Updated Android navigation so a missing trusted runtime resolves startup to Settings with pairing/status expanded and the Pair AetherLink title, while an explicitly opened Settings screen remains stable for language, theme, status, and pairing management.
- This improves the requested first-run behavior without re-exposing Pairing as a drawer item.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" :app:installDebug --no-daemon --console=plain`
- Physical-device relaunch on `R3CXC0M76VM`: no `127.0.0.1` relay retry appeared in filtered logcat after app start.
- Screenshot evidence: `artifacts/android-after-pairing-start-fix.png`.

## 2026-06-25 macOS GUI Relay Allocation Attempt

- Continued reducing the "QR scans but relay never matches" class of failures in the different-network development path.
- The macOS remote relay panel now asks the configured relay for route allocation when the user saves the relay route. This sends the same route-token and preferred relay frame secret shape used by the bootstrap allocation path instead of only saving a static `relay_id`.
- When allocation succeeds, the companion stores the allocated `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce` material so the next QR can describe route material known by an allocation-required relay.
- When allocation fails, the route is still saved for legacy/manual relay diagnostics, but the UI warns that allocation failed and asks the user to check the relay service before generating the latest QR if the relay requires allocation.
- Added allocation success/failure messages in English/default, Korean, Japanese, Simplified Chinese, and French.
- This does not remove the need for a mutually reachable relay/bootstrap host, but it makes the normal macOS Pairing screen use the allocation path once such a relay is available.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelAllocatesRelayWhenSavingRelayWithAllocationAttempt --filter LocalRuntimeMessageRouterTests/testCompanionAppModelKeepsSavedRelayWhenAllocationAttemptFails`
- `swift build --product AetherLink`
- `swift test --filter CompanionCoreTests`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_protocol_schema.py`
- `git diff --check`

## 2026-06-25 GUI Allocated Relay Lease Expiration Guard

- Followed up the GUI relay allocation path to make QR generation respect service-issued route lease expiration, not only environment/bootstrap allocation leases.
- If the macOS companion saved relay route material through the GUI allocation attempt and the returned lease is expired, the route is no longer eligible for normal remote QR generation.
- Legacy/static relay routes without an allocation lease keep the existing diagnostic behavior: they can still get a short QR-side route lease generated locally.
- Added regression coverage for an expired GUI-allocated relay lease so stale relay material cannot be presented as a valid different-network QR.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotGenerateGUIAllocatedQRCodeWithExpiredLease --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotGenerateBootstrapQRCodeWithExpiredSavedLease --filter LocalRuntimeMessageRouterTests/testCompanionAppModelAllocatesRelayWhenSavingRelayWithAllocationAttempt`
- `swift build --product AetherLink`
- `swift test --filter CompanionCoreTests`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_protocol_schema.py`
- `git diff --check`

## 2026-06-25 QR Relay Route Regeneration And Reconnect Verification

- Continued the QR pairing work with GPT-5.5 subagents for Android and macOS. GPT-5.3 Codex Spark was not used in this session.
- Android relay QR parsing, persistence, and reconnect planning were rechecked. The client parses `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`, stores accepted relay route material with the trusted runtime, and uses the saved relay route on reconnect instead of falling back to stale direct/local endpoints.
- Android still rejects expired relay route material during initial QR pairing, and saved trusted-runtime reconnect preserves the QR `relay_expires_at` as the lifetime of the current route rather than the lifetime of the trust relationship.
- macOS QR generation now separates relay host eligibility from route preparation. Public/VPN/tunnel relay hosts can remain eligible while a relay lease or relay registration is being prepared; loopback, `.local`, and private-network relay hosts remain blocked for normal remote QR generation.
- When a GUI-allocated relay lease is expired, `beginPairing(routePolicy: .remoteRequired)` now attempts to allocate fresh relay material before generating a QR. The generated QR includes the fresh `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce` after the runtime registers with the relay.
- The Pairing screen now explains whether the remote route is ineligible, still preparing, or waiting for relay registration instead of presenting a generic inactive QR state.

Verified after this change:

- `swift test --filter CompanionCoreTests`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest :app:testDebugUnitTest --no-daemon --console=plain`
- `python3 script/check_protocol_schema.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`

Current QR status:

- Same-network/local-IP fallback is still intentionally not the normal pairing path.
- Code-level QR relay route generation, Android relay route persistence, and reconnect route planning are covered by unit tests.
- A real different-network optical QR test still requires a relay/bootstrap endpoint reachable from both devices. Without that mutually reachable relay/P2P route, QR can establish identity and carry route material, but it cannot make two unrelated NATed networks reachable by itself.

## 2026-06-25 QR Artifact Remote-Route Preflight

- Added remote-route validation flags to `script/verify_pairing_qr.swift`.
- The verifier can now assert that a generated QR PNG decodes to `aetherlink://pair`, includes complete relay route material (`relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, `relay_nonce`), matches an expected relay host/port, and does not include local direct `host`/`port` fallback fields.
- Loopback relay hosts are rejected by default in remote-route verification. `--allow-local-relay` exists only for local diagnostics such as `--start-local-relay` emit-only smoke runs.
- `script/no_adb_external_relay_pairing_smoke.sh` now uses the stricter verifier after rendering the QR PNG, so the no-ADB flow fails earlier if the image itself is missing relay route material.
- This separates QR payload correctness from actual network reachability. A QR can now be proven to contain the right relay fields before doing a physical Android optical scan, while the final different-network proof still requires a relay/bootstrap endpoint reachable by both devices.

Verified after this change:

- `swiftc -typecheck script/verify_pairing_qr.swift`
- Rendered a relay QR with `script/render_pairing_qr.swift` and verified it with `script/verify_pairing_qr.swift --require-relay-route --expected-relay-host relay.example.test --expected-relay-port 443 --forbid-direct-endpoint`
- Rendered a loopback relay QR and confirmed it fails without `--allow-local-relay`, then passes with the explicit diagnostic allowance
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 5 --work-dir <tmp>`

## 2026-06-25 Android Reasoning Preview Polish

- Rechecked Android reasoning support after the earlier UI request. The runtime protocol already carries `reasoning_delta` and `thinking_delta`, Android appends those chunks to `RuntimeChatMessage.reasoning`, and the chat UI renders a dim assistant thinking panel above the answer.
- Tightened the thinking panel UX so short reasoning that already fits the collapsed preview no longer shows an unnecessary show/hide action. Longer reasoning still opens from the dim three-line preview into the full text.
- Added a helper test that distinguishes short, expandable, blank-line, and whitespace-only reasoning content.
- GPT-5.3 Codex Spark was not used.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`

## 2026-06-25 Android Dead Surface And macOS Copy Polish

- Continued the completion-oriented UI pass with one GPT-5.5 macOS read-only audit agent. GPT-5.3 Codex Spark was not used, and the audit agent was closed.
- Removed the unused standalone Android `PairingScreen` surface after moving pairing/status into Settings.
- Removed obsolete Android tab strings for Pairing, Status, and Models, plus the unused centered empty-chat quick model picker copy.
- Removed the unused centered quick model picker from Android empty chat. Model selection now stays in the chat top bar, and the empty chat canvas stays clean when connected.
- Softened macOS companion copy in remote route, relay, and QR flows so user-facing text no longer reads as prototype-only. The UI now talks about reachable remote routes, protected relay traffic, secure route secrets, and keeping this computer awake instead of roadmap/testing/diagnostic/local-IP wording.
- Updated macOS source keys and all five localized resource sets together, so the required English, Korean, Japanese, Simplified Chinese, and French resources remain aligned.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `swift build --product AetherLink`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`

## 2026-06-25 Android QR Pairing Persistence Polish

- Continued QR pairing investigation with GPT-5.5 Android/macOS subagents. GPT-5.3 Codex Spark was not used.
- Confirmed the current QR scanner and deep link entry points exist, but trusted runtime persistence still requires the client to reach the runtime and receive an accepted `pairing.result`.
- Added `relay_scope` to the Android trusted runtime record so debug USB reverse relay QR material does not disappear after app restart. Scope-less loopback relay routes are still rejected.
- Changed trusted-runtime relay route planning to preserve stored `relay_expires_at` and `relay_nonce` when reconnecting. Expired saved route material can now be diagnosed as stale route material instead of being flattened into a generic unreachable route.
- Added broad `aetherlink:` and `lab:` deep link filters so external QR scanner apps can open path-style pairing URIs; app code still rejects non-`pair` actions.

Verified after this change:

- `python3 script/check_protocol_schema.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`

Remaining QR connectivity constraint:

- A real different-network QR-only pairing test still needs a relay/bootstrap endpoint reachable from both devices, or the future production P2P rendezvous layer. QR alone can carry identity and route material, but it cannot make two unrelated NATed networks reachable without some rendezvous or relay path.

## 2026-06-25 Relay Allocation Ticket Persistence

- Continued different-network QR reliability work with a GPT-5.5 relay allocation explorer. GPT-5.3 Codex Spark was not used.
- Fixed the development relay's allocation registry so issued `relay_id` tickets can survive `AetherLinkRelay` process restarts.
- `AetherLinkRelay` now persists allocation tickets to `~/.aetherlink-relay/allocations.json` by default, accepts `--allocation-store <path>` for an explicit store, and accepts `--ephemeral-allocations` for one-shot in-memory diagnostics.
- The persisted ticket store contains relay id, expiration, and nonce only. It intentionally does not persist the relay frame secret; runtime/client frame bodies still use the QR-provisioned secret for AES-GCM before relay forwarding.
- `script/run_allocation_relay.sh` now exposes the allocation store and ephemeral options and prints the persistence mode in dry-run output.
- Updated README and connection overlay docs to reflect allocation ticket persistence.

Verified after this change:

- `swift test --filter RelayAllocationTests`
- `swift test --filter RelayServerCoreTests`
- `swift build --product AetherLinkRelay`
- `bash -n script/run_allocation_relay.sh && script/run_allocation_relay.sh --dry-run --allocation-store /tmp/aetherlink-relay-test.json`
- `swift build --product AetherLink`
- `swift build --product RuntimeDevServer`
- `python3 script/check_copy_hygiene.py && git diff --check`

Remaining QR connectivity constraint:

- This improves restart resilience for an allocation-required relay that is already reachable by both devices. It still does not remove the need for a public, VPN, tunnel, private overlay, or future automatic P2P rendezvous path that both paired devices can reach.

## 2026-06-25 QR Relay Host Eligibility Tightening

- Continued the QR pairing failure investigation with two GPT-5.5 read-only subagents, one for Android and one for macOS. GPT-5.3 Codex Spark was not used.
- Confirmed Android already uses complete QR relay metadata first: QR scan or deep link flows into `RuntimeClientViewModel.trustRuntimeFromPairingQr()`, builds an identity-first target, prepares the relay route, and sends `pairing.request` through `RuntimeRelayTcpClient` when the QR has `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`.
- Tightened Android QR validation so normal remote relay hosts now reject private, link-local, carrier-grade NAT, loopback, unspecified, and `.local` IP/name forms before pairing state is saved or a relay socket is attempted. Debug USB reverse loopback remains allowed only with `relay_scope=usb_reverse` and debug parsing enabled.
- Tightened macOS companion QR eligibility so environment-provided relay settings no longer bypass loopback, `.local`, or private-network relay host blocking. A relay route from env vars can still start for diagnostics, but it will not be included in a normal remote pairing QR if the address is not QR-reachable.
- Updated protocol, security, and connection-overlay docs to match the fail-closed behavior. A real different-network scan still needs a public, VPN, tunnel, DNS route, or future private overlay/rendezvous endpoint that both devices can reach.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelBlocksEnvironmentPrivateRelayHostForRemoteQRCode`
- `swift test --filter LocalRuntimeMessageRouterTests`

## 2026-06-25 Physical Android Relay QR Result Smoke

- Re-ran the physical Android pairing result path on device `R3CXC0M76VM`.
- The smoke built `RuntimeDevServer` and `AetherLinkRelay`, started a local allocation-required development relay through USB reverse, injected an `aetherlink://pair` URI through Android's `VIEW` intent, and observed `Development pairing accepted` plus `runtime.health` on the runtime log.
- This proves the Android app path after QR delivery works: parsed pairing payload, relay route selection, `pairing.request`, trusted runtime persistence, and authenticated runtime health follow-up.
- This is not a proof of true different-network optical QR pairing. A real different-network scan still needs a public, VPN/tunnel, DNS, or future private-overlay/P2P rendezvous endpoint reachable by both devices.
- Hardened the development smoke scripts so remote QR checks fail earlier when they are accidentally configured with private, link-local, CGNAT, loopback, wildcard, multicast, or `.local` relay hosts.
- Updated relay QR validation in the Android physical-device smoke so `relay_scope` is optional for external relay QRs. The `usb_reverse` scope remains a diagnostic-only local path.
- GPT-5.3 Codex Spark was not used; GPT-5.5 subagents from the QR inspection pass were closed.

Verified after this change:

- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh`
- `script/android_pairing_deeplink_smoke.sh --relay --external-relay-host 192.168.50.10 --external-relay-port 43171` fails early with the expected private relay host rejection.
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 192.168.50.10 --relay-port 43171 --emit-only` fails early with the expected private relay host rejection.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install`

## 2026-06-25 Remote QR Allocation Lease Hardening

- Continued the different-network QR pairing work with a GPT-5.5 read-only inspection agent. GPT-5.3 Codex Spark was not used.
- Aligned the pairing QR schema, schema checker, Android parser expectations, macOS QR eligibility, and development smoke scripts around the same remote relay host policy.
- Normal remote QR pairing now rejects loopback, wildcard, `.local`, link-local, carrier-grade NAT, multicast, and private-network relay IP literals across schema/scripts/macOS/Android. Future private overlays should use a route name or explicit future route scope instead of a raw private IP literal.
- The macOS Remote Relay panel now blocks private-network relay IP literals at save time instead of saving them with a warning and later refusing to include them in QR. This removes a confusing "saved but QR not working" state.
- The macOS GUI pairing path no longer synthesizes `relay_expires_at` and `relay_nonce` for normal remote QR generation. A remote QR is ready only when an allocation-capable relay returns real route material and a current lease. Static/manual relay settings without a lease remain diagnostic configuration until allocation succeeds.
- Regenerating a relay frame secret clears the old lease and no longer allows QR generation until a fresh relay allocation succeeds.
- The physical Android relay QR-result smoke still passes on device `R3CXC0M76VM`. This validates the app path after QR delivery, not true optical different-network reachability.

Verified after this change:

- `swift test --filter CompanionCoreTests`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/run_allocation_relay.sh`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest --no-daemon --console=plain`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 100.64.1.10 --relay-port 43171 --emit-only` fails early with the expected CGNAT relay host rejection.
- `script/android_pairing_deeplink_smoke.sh --relay --external-relay-host 100.64.1.10 --external-relay-port 43171` fails early with the expected CGNAT relay host rejection.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install`

Remaining different-network requirement:

- True QR-only connectivity across unrelated networks still needs a relay/bootstrap endpoint, tunnel/VPN/DNS route, or future P2P rendezvous path that both devices can reach. The current changes make false-positive QR generation much harder, but they do not replace that production connectivity layer.

## 2026-06-25 QR Relay Readiness Reality Check

- Answered the current status plainly: QR delivery and relay-result handling exist, but fully unconstrained QR-only pairing across unrelated networks is still not complete without a mutually reachable relay/bootstrap/private-overlay path.
- Kept the user-requested agent policy: GPT-5.3 Codex Spark was not used. The GPT-5.5 read-only inspection agent used for this QR pass was closed.
- Fixed Android relay readiness so a saved relay route is considered usable only when it has complete route material: eligible relay host, valid port, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce`, and the lease is not expired.
- Tightened Android reconnect planning to reject incomplete saved relay material instead of treating host/id/secret alone as a valid different-network route. This prevents stale or half-saved QR material from hiding the real "route refresh required" state.
- Added Android tests for incomplete saved relay lease rejection and updated relay-route fixtures to include lease/nonce when the test intends a complete route.
- Fixed the macOS CompanionCore QR allocation tests so the default bootstrap allocator path and the GUI saved-relay lease-refresh path use the correct injected allocators.
- Updated `docs/connection-overlay.md`, `docs/protocol.md`, and earlier `docs/progress.md` entries to reflect the current model: trusted pairing identity is long-lived, but the relay lease is saved as route lifetime and can require refresh.
- Confirmed the physical Android relay deep link smoke still passes on device `R3CXC0M76VM`; this validates Android's post-QR path with USB reverse relay scaffolding, not true no-USB/no-same-Wi-Fi reachability.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon --console=plain`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRetriesGUIRelayAllocationWhenGeneratingQRCodeWithoutLease`
- `swift test --filter CompanionCoreTests`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest --no-daemon --console=plain`
- `python3 script/check_macos_localization.py`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`
- `PATH="$HOME/Library/Android/sdk/platform-tools:$PATH" JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install`

## 2026-06-25 No-ADB Reconnect Proof Hook

- Added an optional `--expect-reconnect` phase to `script/no_adb_external_relay_pairing_smoke.sh`.
- The no-ADB external relay smoke still validates the first QR pairing path by waiting for relay ready, accepted pairing, and `runtime.health`. With `--expect-reconnect`, it now keeps the runtime/relay alive after the first health check and waits for a second `runtime.health`, so a real test can prove the client reconnected from its saved trusted relay route after app restart or manual reconnect.
- This does not fake no-ADB behavior through adb intents, logcat, or reverse ports. It is a manual/real-device proof hook for a mutually reachable relay endpoint.
- Tightened Android route-refresh identity tests so mismatched runtime identity cases use complete relay QR material. That ensures the tests are checking the pinned runtime identity boundary, not accidentally passing because route material is incomplete.
- Cleaned up the saved relay route planner formatting after the relay readiness changes.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon --console=plain`
- `bash -n script/no_adb_external_relay_pairing_smoke.sh`
- `script/no_adb_external_relay_pairing_smoke.sh --help`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 100.64.1.10 --relay-port 43171 --expect-reconnect --emit-only` fails early with the expected CGNAT relay host rejection.
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 53491 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-reconnect-emit`

## 2026-06-25 QR Reconnect Signing Fix

- Rechecked the physical Android QR/deep-link relay pairing path after the user asked whether QR pairing was still not working.
- Confirmed the previous state was a real failure: first pairing could be accepted, but after app restart the runtime could not prove its pinned identity and the client showed "The runtime could not prove its paired identity."
- Root cause: the development smoke scripts were injecting a fake `AETHERLINK_DEV_RUNTIME_PUBLIC_KEY`. That let QR payloads pin a public key, but `RuntimeDevServer` had no matching private signer, so reconnect `auth.challenge` could not include a verifiable `runtime_signature`.
- A second blocker appeared after removing the fake key: the default development runtime identity path could block in Keychain during CLI smoke startup before printing `AETHERLINK_DEV_PAIRING_URI`.
- Added `FileRuntimeIdentityKeyStore` for development/test runtime identities. It persists a P-256 signing key to a JSON file, writes with `0600` permissions, exposes `loadOrCreate()`, and signs `auth.challenge` with the same verification format as the Keychain-backed store.
- `RuntimeDevServer` now uses `AETHERLINK_DEV_RUNTIME_IDENTITY_FILE` when provided. The smoke scripts pass a per-run identity file under their work directory, and `script/run_runtime_dev_server.sh` defaults development runs to `~/.aetherlink/runtime-dev-identity.json`.
- Removed fake runtime public-key/fingerprint injection from the QR smoke paths. The QR now carries a real public key whose private key can sign reconnect challenges.
- Extended `script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect` to force-stop and relaunch the Android app without clearing data, then wait for a second `runtime.health`.
- Physical device `R3CXC0M76VM` now passes the relay QR/deep-link smoke with reconnect: pairing is accepted, the trusted runtime route survives app restart, and the runtime observes a second `runtime.health`.
- GPT-5.3 Codex Spark was not used. A GPT-5.5 worker implemented the file-backed Pairing store and was closed after completion.

Verified after this change:

- `swift test --filter RuntimeIdentityKeyStoreTests`
- `swift build --product RuntimeDevServer`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_runtime_dev_server.sh`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 53492 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-signed-emit`
- `PATH="$HOME/Library/Android/sdk/platform-tools:$PATH" JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect`

Current QR status:

- QR pairing is no longer simply "not working" in the development relay path. The physical Android app can receive QR/deep-link route material, pair, persist trust, relaunch, and reconnect through the saved route.
- This is still not a claim that QR alone crosses arbitrary unrelated networks without infrastructure. A real no-USB, no-same-Wi-Fi optical QR test still needs a relay/bootstrap/VPN/tunnel/private-overlay endpoint reachable by both devices, or the future production P2P rendezvous layer.

## 2026-06-25 Android Navigation And Empty Chat Polish

- Continued the completion-oriented Android UI pass with one GPT-5.5 read-only audit agent. GPT-5.3 Codex Spark was not used, and the audit agent was closed.
- Removed `Pairing` as a standalone primary destination. The main destinations are now Chat and Settings; when no trusted runtime exists, navigation resolves to Settings where the pairing/status section is expanded.
- QR deep links, QR scan results, and manual QR payload entry now route to Settings instead of a separate Pairing screen. This keeps pairing and status management inside Settings while preserving first-run pairing guidance.
- Chat remains the primary surface once a trusted runtime exists. The model selector stays in the chat top bar next to the drawer button.
- Empty chat now keeps the center canvas blank when connected but no usable chat model is selected. The user should choose a model from the top model picker and rely on the composer hint, instead of seeing a centered instructional panel.
- Blocking empty states remain for disconnected trusted runtimes, QR route refresh, and no-message streaming progress.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py && git diff --check`

## 2026-06-25 Android First-Launch QR Placement Check

- Rechecked the physical Android first-launch flow after a fresh debug install and app data reset.
- Found that the app did route first launch to Settings, but Settings showed appearance/language preferences before the QR pairing action. That made QR pairing feel hidden even though the scanner code existed.
- Moved the Settings connection/status section above Preferences and placed the QR pairing panel before the runtime-mediated-access explanation inside that section.
- Rebuilt and installed the debug APK on physical device `R3CXC0M76VM`.
- Verified on-device that first launch now shows `Connection Status`, `QR Pairing`, `Scan QR`, and `Enter QR payload` in the first viewport.
- Verified on-device that tapping `Scan QR` opens the scanner flow, asks for Android camera permission, and then shows the camera preview with the QR scan frame.
- This validates the Android QR scanner entry path. It is not a full optical Mac-to-phone pairing success proof by itself; the full success path still depends on scanning a current runtime QR that contains valid trusted identity and reachable route material.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug --no-daemon --console=plain`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb shell pm clear com.localagentbridge.android`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb shell am start -n com.localagentbridge.android/.MainActivity`
- On-device screenshots saved at `artifacts/android-first-launch-qr-first.png`, `artifacts/android-first-launch-after-scan-tap.png`, and `artifacts/android-first-launch-qr-camera.png`.

## 2026-06-25 Android Pairing Success Returns To Chat

- Re-ran the physical Android relay pairing smoke after the first-launch QR placement fix.
- Confirmed that the latest app still accepts the QR/deep-link route material, sends `pairing.request`, receives accepted pairing, persists trusted runtime state, relaunches without clearing app data, and reconnects far enough for the runtime to observe a second `runtime.health`.
- Found a UX issue after successful pairing: because the QR/deep-link path routes into Settings first, the app could stay on Settings even after the runtime became trusted. The same pattern could also keep a relaunch on Settings if trusted runtime state loaded after the initial no-runtime routing decision.
- Added UI state in `MainActivity.kt` to distinguish Settings opened automatically for pairing/onboarding from Settings opened intentionally by the user.
- After QR/deep-link pairing succeeds and the runtime is connected, the app now returns to Chat. A relaunch that initially routed to Settings only because trusted state had not loaded yet can also return to Chat once trusted state is available.
- User-initiated Settings navigation remains sticky, so the app does not pull the user out of Settings when they deliberately open it.
- On-device screenshot after the second relay smoke is saved at `artifacts/android-after-pairing-chat-return.png`. It shows the Chat surface after the smoke runtime/relay have been cleaned up; the remaining `Route needed` state is expected because the temporary smoke runtime is no longer running.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon --console=plain`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon --console=plain`
- `PATH="$HOME/Library/Android/sdk/platform-tools:$PATH" JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect`

## 2026-06-25 Runtime Chat Request Storage Before Generation Checks

- Continued the runtime-owned chat data pass for the requirement that chat processing and history live on the serving runtime, with Android acting as a UI/cache client.
- Found that `chat.send` request events were recorded only after runtime model resolution and attachment capability validation. If a syntactically valid request failed before generation, for example because the selected model was not installed, the runtime could store an error event without also storing the user request that led to it.
- Changed `LocalRuntimeMessageRouter` so a parsed `chat.send` request is recorded in the runtime chat event store before model resolution, attachment validation, or generation starts.
- This keeps runtime-owned history more complete for failed generation attempts while still stripping inline attachment bytes in the JSONL event store.
- Added coverage that a non-installed model response returns the same structured `model_not_installed` error and records both `.request` and `.error` events, including the user message, on the runtime side.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendNonInstalledModelReturnsModelNotInstalled`
- `swift test --filter LocalRuntimeMessageRouterTests`

## 2026-06-25 Android QR Pairing Preemption And Install

- Rechecked the QR pairing path after the user asked whether QR was still not working.
- Confirmed the scanner/deep-link result reaches `RuntimeClientViewModel.trustRuntimeFromPairingQr()`.
- Found a concrete Android-side blocker: when a new QR is scanned while the app is already connected or connecting, identity-only QR pairing can remain pending because the pending pairing connector returns early on `isConnected || isConnecting`.
- Changed Android pairing handling so a new QR pairing attempt can preempt an active non-matching connection before waiting for discovery or connecting to the QR route.
- Paused automatic trusted-runtime reconnect while a pending QR pairing attempt exists, so the previous saved runtime cannot race against the new pairing flow.
- Added unit coverage for QR preemption with active untrusted connections, active different trusted-runtime connections, and same-runtime QR cases.
- Cleaned up misleading model UI: uninstalled chat and embedding model rows no longer show an inactive "Install model" affordance. They now show a localized "Not installed" status.
- Improved relay QR failure diagnostics on Android. If an encrypted relay route connects but frame authentication fails, the UI now maps that to `remote_route_auth_failed` and asks the user to scan the latest AetherLink QR instead of showing only a generic closed connection.
- Built and installed the debug Android APK on physical device `R3CXC0M76VM`.
- Captured the current device screen at `artifacts/android-aetherlink-after-qr-preempt-fix.png`. It shows the app running and correctly reporting `Route needed` for a saved trusted runtime with no usable current route.

Current QR status:

- Android QR intake, compact payload parsing, pending route state, relay route planning, saved trusted relay reconnect, and physical-device APK install are working in the current development paths.
- QR-only pairing across unrelated networks still requires a reachable relay/bootstrap/VPN/tunnel/private-overlay route in the QR. The current code does not yet implement the final production Bitcoin-like private overlay, NAT traversal, or decentralized rendezvous layer.
- If a QR contains only identity/local discovery data, it cannot make two devices on unrelated networks connect by itself.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --tests "com.localagentbridge.android.AppNavigationTest"`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `python3 script/check_protocol_schema.py`
- `git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`

## 2026-06-25 Runtime-Owned Attachment History

- Continued the runtime-owned chat history work so file/image inputs do not disappear from saved conversations.
- `chat.messages.list` now supports `attachments` on stored messages. The runtime returns safe metadata such as `type`, `mime_type`, `name`, and extracted `text`; it does not return inline `data_base64`.
- The macOS runtime JSONL chat store reconstructs user message attachment metadata from stored request events. Image bytes are stripped before storage, while document text that was already extracted or parsed can be retained as text metadata.
- The Android protocol model, local runtime cache, and chat message UI now understand stored message attachments. Sent messages keep read-only attachment chips in the chat history instead of only showing pending composer chips.
- Updated `packages/protocol-schema/protocol.schema.json` and `docs/protocol.md` so the socket contract matches the implementation.
- Rebuilt and installed the updated Android debug APK on physical device `R3CXC0M76VM`.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testRuntimeChatStoreListsSessionsAndMessages --filter LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:protocol:testDebugUnitTest --tests "com.localagentbridge.android.core.protocol.ProtocolCodecTest" :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMessagesReplaceSessionTranscriptAndPreserveReasoningWithStableIds"`
- `python3 script/check_protocol_schema.py`
- `swift build`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`

## 2026-06-25 Android Reasoning Preview Polish

- Tightened the Android assistant reasoning/think preview so short reasoning with blank-line-only formatting does not show an unnecessary expand control.
- Long single-paragraph reasoning now still shows the expand control, while the visible collapsed text remains capped to about three rendered lines with ellipsis.
- Rebuilt, installed, and launched the updated debug APK on physical Android device `R3CXC0M76VM`.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent" --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest.thinkingDeltaAliasAppendsReasoning"`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `python3 script/check_android_string_parity.py && git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb shell am start -n com.localagentbridge.android/.MainActivity`

## 2026-06-25 QR Direct Endpoint Fallback Removal

- Tightened Android QR parsing so normal product pairing rejects identity-plus-local `host`/`port` QR payloads. Local direct QR endpoints now require explicit diagnostic parsing with `route_scope=local_diagnostic`.
- Relay QR payloads may still contain legacy direct endpoint fields, but Android drops those fields before trusted-runtime storage and pending-route persistence. The trusted runtime record now keeps identity/key material plus relay route material, not stale private IP fallback data.
- Android trusted-runtime reconnect no longer promotes `TrustedLastKnown` private IP endpoints into automatic reconnect targets. It resolves the paired runtime identity through current matching discovery, explicit diagnostics, or QR-provisioned relay material instead.
- macOS local diagnostic QR generation now marks direct host/port payloads with `route_scope=local_diagnostic`; normal remote-required QR generation still requires eligible relay route material.
- Updated `docs/protocol.md`, `docs/connection-overlay.md`, `docs/architecture.md`, and `packages/protocol-schema/pairing-qr.schema.json` so the design record matches the code.

Current QR status after this change:

- The app is no longer treating same-network/fixed-IP QR material as the normal pairing route.
- QR-only different-network pairing still requires mutually reachable relay/bootstrap/VPN/tunnel/private-overlay route material in the QR. Production Bitcoin-like private overlay, real NAT traversal, and hardened decentralized/bootstrap rendezvous remain unfinished.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests "com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest" --tests "com.localagentbridge.android.core.pairing.PairingStoreTest"`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment --filter LocalRuntimeMessageRouterTests/testCompanionAppModelGeneratesDirectRoutePairingQRCode --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `python3 script/check_android_string_parity.py && python3 script/check_macos_localization.py && python3 script/check_protocol_schema.py && git diff --check`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb shell am start -n com.localagentbridge.android/.MainActivity`

## 2026-06-25 Android Pending QR Route Persistence

- Added a short-lived Android persistence layer for scanned QR pairing route material before the runtime has accepted pairing.
- The pending route is stored in `RuntimeLocalStore` separately from trusted runtimes, with a maximum five-minute TTL and a stricter cap when the QR relay lease expires earlier.
- Broken pending routes are discarded during sanitization: direct route data must include both host and port, and relay route data must include host, port, id, secret, expiration, and nonce together.
- `RuntimeClientViewModel` now restores a valid pending QR route at app startup, resumes discovery if the QR contains identity-only route data, and retries relay pairing while the temporary route remains valid.
- The pending route is cleared when pairing succeeds, is rejected, cannot create a usable route, expires, exhausts retry attempts, or the user stops discovery. Successful trust still moves into the normal trusted-runtime store only after accepted `pairing.result`.
- Rebuilt and installed the updated debug APK on physical Android device `R3CXC0M76VM`.

Current QR status after this change:

- Android now survives more QR failure/restart edges during the pre-trust pairing window.
- This still does not remove the requirement for mutually reachable route material when the devices are on unrelated networks. QR-only different-network pairing needs a relay/bootstrap/VPN/tunnel/private-overlay route in the QR, or the future production private overlay.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_protocol_schema.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `git diff --check`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:assembleDebug`
- `/Users/hanchangha/Library/Android/sdk/platform-tools/adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`

## 2026-06-25 QR Route Error Split

- Confirmed with a physical-device relay deeplink smoke that QR payload handling after scan is not globally broken: Android can consume a relay `aetherlink://pair` payload, connect through the development relay, send `pairing.request`, receive `runtime.health`, and reconnect after app relaunch from the saved trusted route.
- Split Android QR parse failures so a direct `host`/`port` QR is no longer surfaced as a generic invalid QR. It now reports `pairing_direct_route_rejected` with `route_diagnostic_direct_qr_rejected`.
- The rejected-direct-QR state participates in the same route-refresh UI as other remote-route problems, so the client prompts for the latest remote-route QR instead of implying manual host/port pairing.
- Added localized user-facing strings for the new direct-route rejection path across the current Android language set.

Current QR status after this change:

- Relay QR payload flow, runtime pairing, health request, and saved-route reconnect are verified through the Android deeplink smoke path.
- Real optical camera scanning still needs another physical-device pass after the phone is reconnected.
- Same-network or fixed-IP direct QR is intentionally not product pairing. Different-network QR pairing still requires QR-provisioned relay/bootstrap/VPN/tunnel/private-overlay route material until the future production overlay is implemented.

Verified after this change:

- `script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest.localDirectQrParseFailureReportsRouteQrRequired" --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest.genericQrParseFailureStillReportsInvalidPairingQr" --tests "com.localagentbridge.android.AppNavigationTest.emptyChatPrefersQrRefreshForRejectedDirectQrRoute"`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `python3 script/check_android_string_parity.py && git diff --check`

## 2026-06-25 Android Route Diagnostics Copy Polish

- Cleaned up Android connection, pairing, and route-diagnostic copy across English, Korean, Japanese, Chinese, and French.
- Removed remaining user-facing prototype terms such as `USB reverse`, `Emulator bridge`, `route material`, and development-endpoint wording from the Android resource strings.
- Kept diagnostic routes available behind Settings while making normal onboarding read as QR-first and runtime-mediated.
- The Android phone was disconnected during this pass, so verification was limited to local resource, compile, and unit-test checks.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"`

## 2026-06-25 Android Error Diagnostics Polish

- Removed the Android error banner fallback that rendered raw `RuntimeUiError.detail` directly. Low-level socket, route, backend, and protocol messages now remain in state for diagnostics but are not shown as default user-facing copy.
- Connected QR scan failures to an existing localized user-friendly detail instead of showing camera or barcode library exception text.
- Moved model-provider raw message/code details behind a collapsed diagnostics affordance in the provider status rows, with localized labels across the current five-language Android set.
- The Android phone was disconnected during this pass, so verification was limited to local resource, compile, and unit-test checks.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"`

## 2026-06-25 macOS Error Diagnostics Polish

- Removed raw runtime listener failure text from the default macOS Status and Readiness cards. The app now shows a localized recovery-oriented listener message while detailed failure text stays in diagnostics/logs.
- Moved model-provider raw status messages behind a collapsed `Provider Diagnostics` disclosure in the macOS Model Providers panel.
- Moved remote-route reconnect/failure detail and allocation failure detail behind `Route Diagnostics`, while keeping the default copy focused on what the user should do next.
- Added/updated English, Korean, Japanese, French, and Simplified Chinese localization strings for the new diagnostics affordances and cleaned up a few remaining untranslated trusted-device/remoteroute strings.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `swift build`
- `swift test`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 macOS Diagnostics View Polish

- Renamed the macOS sidebar `Logs` entry to `Diagnostics` while keeping the underlying runtime log storage unchanged.
- Reworked the Diagnostics page so rows show localized product-facing summaries by default, with raw runtime lines available only inside collapsed `Technical Details` disclosures.
- Added mappings for current AetherLink runtime start/stop, listener, route, provider, trusted-device, model-list, and model-residency events so prototype/internal log lines no longer fall through into the default UI.
- Updated English, Korean, Japanese, French, and Simplified Chinese strings for the diagnostics title, empty state, summary messages, and technical-details affordance.
- The Android phone was disconnected during this pass, so verification did not include physical-device install or optical QR scanning.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `swift build`
- `swift test --quiet`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Android And macOS Product Copy Polish

- Cleaned up Android route-diagnostics wording across English, Korean, Japanese, French, and Simplified Chinese so hidden diagnostics no longer expose `USB`, emulator, lab, or testing terminology in normal UI labels.
- Kept the same diagnostic route functionality, but renamed visible labels toward local/preview/manual diagnostics and troubleshooting language so the product remains QR-first.
- Updated macOS SwiftUI copy keys so current UI uses `Generate New QR`, `Load Models`, `Models`, `No models loaded`, and trusted-device wording directly instead of relying on older `Code`, `Local Models`, `client device`, `runtime host`, or `relay` phrasing.
- Added matching macOS translations for the new product-facing keys in English, Korean, Japanese, French, and Simplified Chinese.
- The Android phone was disconnected during this pass, so verification did not include physical-device install or optical QR scanning.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `swift build`
- `python3 script/check_copy_hygiene.py`

## 2026-06-25 Android Onboarding And Suggested Follow-Up Polish

- Polished first-run Settings copy across English, Korean, Japanese, French, and Simplified Chinese so the expanded setup section now reads as `Pairing & Connection` and leads with scanning a trusted AetherLink QR.
- Renamed the normal Settings diagnostics entry to troubleshooting language and kept manual route tools framed as support-only helpers, not the primary pairing path.
- Hid disconnected-only `Health` and `Disconnect` actions from the Settings connection section so first-run onboarding does not show dead-looking disabled controls.
- Fixed suggested next-question rendering so the latest assistant message can show a localized `Generating next questions...` state while AetherLink Runtime is still producing follow-up suggestions and before suggestion rows arrive.
- Extracted the assistant suggestion visibility rule into a tested UI helper so the loading state remains visible while suggestions are being generated, but not during active streaming or for older assistant messages.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest"`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --no-daemon -Pkotlin.incremental=false`

## 2026-06-25 QR Relay Lease And Compact QR Smoke Hardening

- Hardened trusted runtime route persistence so raw `host`/`port` endpoint hints are not restored as product reconnect routes, and saved relay routes are only exposed when complete, remote-eligible or explicit debug USB reverse, nonce-backed, and not expired.
- Hardened client remote route planning so expired or incomplete QR relay leases do not become long-lived fallback relay routes.
- Added macOS runtime identity fallback behavior so Keychain failure falls back to a persisted file-backed runtime identity before using a temporary fingerprint-only identity. This keeps QR identity and later challenge-response behavior more stable on machines where Keychain is unavailable to the dev process.
- Added relay allocation response validation before allocation data is used as QR route material.
- RuntimeDevServer now prints both canonical and compact pairing URIs. no-ADB and physical-device deeplink smoke paths now prefer the compact URI, which is closer to the QR shown by the companion app.
- no-ADB QR validation now accepts canonical and compact QR aliases, verifies the compact QR PNG round-trip, and still forbids direct endpoint fields for relay pairing unless an explicit diagnostic flag is used.
- The Android phone was disconnected during this pass, so optical camera scanning and on-device install were not re-run. Local relay, QR rendering, protocol relay, pairing, auth, model list, streaming chat, and cancel were revalidated without a phone.

Verified after this change:

- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-smoke-compact --qr-png /tmp/aetherlink-no-adb-smoke-compact/pairing.png --print-uri`
- `script/runtime_authenticated_mock_smoke.swift --relay`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon -Pkotlin.incremental=false`
- `swift test --filter RuntimeIdentityKeyStoreTests --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning --filter RelayAllocationTests`

## 2026-06-25 Runtime-Owned Memory Cache Guard

- Confirmed the companion runtime already stores chat processing events in `~/Library/Application Support/AetherLink/runtime-chat-events.jsonl` through the default `LocalRuntimeMessageRouter` path, and exposes authenticated `chat.sessions.list` / `chat.messages.list` reads.
- Removed the Android ViewModel's local-only `storeMemoryEntry` API so new memory entries can no longer be added through a client-only path by accident.
- Removed Android persistence helpers/tests that framed memory as directly editable local state. The remaining cache helpers now reflect memory entries received from the trusted runtime through `memory.list`, `memory.upsert`, and `memory.delete`.
- Kept the client-side memory list as a UI cache only. Enabled memory notes are still included in `chat.send` context, but the client sends the request to the trusted runtime and never calls Ollama, LM Studio, or future serving backends directly.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --no-daemon -Pkotlin.incremental=false`

## 2026-06-25 Companion QR Surface And Android Parser Guard

- Rechecked the macOS companion pairing surface and confirmed the visible QR renders `compactQRCodePayload`, not the verbose canonical URI.
- Added macOS test assertions that allocated remote QR material includes compact route aliases `rt`, `rh`, `rp`, `ri`, `rs`, `rx`, and `rrn`, omits local direct `h`/`p`, and does not fall back to verbose relay keys in the camera-facing payload.
- Added Android parser coverage for mixed compact QR payloads that accidentally include local `h`/`p` along with a valid relay route. The parser now has regression coverage that strips the local direct endpoint and keeps only the relay route.
- Re-ran no-ADB QR smoke to generate a compact QR PNG and verify QR round-trip decoding. This validates the QR payload path without requiring a connected phone.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests "com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest" --no-daemon -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-smoke-ui-qr --qr-png /tmp/aetherlink-no-adb-smoke-ui-qr/pairing.png --print-uri`

## 2026-06-25 Companion OS-Neutral Copy And Localization Guard

- Removed remaining user-facing desktop/client-specific wording from the companion source and localization resources. Visible copy now refers to AetherLink, devices, trusted devices, AetherLink Runtime, remote routes, and the runtime host rather than platform-specific or client-app wording.
- Updated remote route and pairing QR status strings so the user is guided to scan in AetherLink, without exposing implementation labels like client app, client device, local runtime, or this computer in normal UI.
- Aligned English, Korean, Japanese, Simplified Chinese, and French macOS localization keys with the current Swift source keys, including `Ready for Devices`, `Pair Device`, and the compact QR route messages.
- Extended copy hygiene checks so future user-facing source/resource changes catch stale desktop-specific, client-specific, direct-provider-URL, or generic chat-placeholder wording.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `git diff --check`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests "com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest" --no-daemon -Pkotlin.incremental=false`

## 2026-06-25 Android Reasoning Display And Route Copy Cleanup

- Used a GPT-5.5 worker for the bounded Android reasoning-display slice. No GPT-5.3-Codex-Spark agent was used.
- Added Android streaming handling for inline `<think>...</think>` and `<thinking>...</thinking>` blocks. The client now separates inline think text into `RuntimeChatMessage.reasoning` instead of leaking it into the final assistant answer.
- Preserved the existing protocol-native `reasoning_delta` / `thinking_delta` path, so Ollama and LM Studio runtime adapters can continue streaming reasoning separately through AetherLink Runtime.
- Kept reasoning UI visually subdued and collapsed by default through the existing Compose `AssistantReasoning` surface, with expansion/collapse available when the reasoning text is longer than the compact preview.
- Trimmed leading whitespace from the first visible answer delta after an inline think block, so streamed responses do not start with a stray separator space after `</think>`.
- Removed stale macOS remote-route localization entries that still mentioned client retries or relay registration as fallback keys. Current visible copy stays on AetherLink, devices, trusted devices, remote routes, and runtime host wording.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.runtime.RuntimeClientViewModelTest" --tests "com.localagentbridge.android.AppNavigationTest" --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build`
- `git diff --check`

## 2026-06-25 QR-First Route UX Polish

- Used a GPT-5.5 worker for the bounded macOS remote-route panel polish. No GPT-5.3-Codex-Spark agent was used.
- Reframed the macOS Remote Route panel so generating the latest QR remains the primary visible action when a route is saved.
- Moved connection address, port, and setup secret fields behind an `Advanced Route Setup` disclosure and described them as diagnostics for cases where a reachable route cannot be prepared automatically. This reduces the normal fixed-address/manual setup feel while keeping development and troubleshooting controls available.
- Changed the remote-route waiting state from client wording to device wording and removed the unused `Waiting for client` localization fallback key.
- Updated Android Settings/Troubleshooting copy so route helper fields read as diagnostics route address/port rather than manual route address/port. Normal Android copy now points users back to QR pairing and route refresh instead of manual endpoint entry.
- Rechecked Android resources for `manual route`, `fixed IP`, `client app`, `client device`, direct Ollama/LM Studio URL wording, and the old generic chat placeholder; no matches remained in Android user-facing source/resources.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`
- `git diff --check`

## 2026-06-25 Android QR-First Connection Status Polish

- Used a GPT-5.5 worker for the bounded Android connection/status route UI polish. No GPT-5.3-Codex-Spark agent was used.
- Removed normal Android status exposure of route labels, remote endpoint host/port, and route lease timestamps. Technical route details now stay out of the regular connection card.
- Reworked route notice copy toward QR refresh, trusted connection, and AetherLink Runtime wording instead of remote-route or relay internals.
- Kept lower-level route wording confined to troubleshooting and diagnostic concepts.
- Restored the `Locale` import needed by attachment size and saved model display helpers after endpoint date formatting was removed.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests "com.localagentbridge.android.AppNavigationTest" --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 QR Route Authority And macOS Status Privacy

- Used a GPT-5.5 worker for the bounded Android QR route parser/planner slice. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Strengthened Android QR parsing so complete relay route material remains authoritative even if stray raw direct host/port fields are present. Invalid direct endpoint fields no longer make a valid relay QR fail before those direct fields are discarded.
- Kept product parsing strict: raw local direct endpoint QR payloads are rejected by default unless explicitly parsed as diagnostic local-direct route material, and loopback relay hosts remain limited to explicit USB reverse diagnostics.
- Updated Android route planning so a matching pending QR payload is authoritative. If that QR has no usable relay route, planning returns no remote route instead of silently falling back to an older saved trusted relay route.
- Added Android regressions for relay QR precedence, incomplete pending QR no-fallback behavior, saved relay lease metadata, expired/incomplete relay leases, and debug USB reverse scope.
- Removed remote endpoint host/port interpolation from the macOS Status connection card. Normal macOS status now says the protected remote route is ready or needs a secure route secret without exposing route addresses; detailed endpoints remain in route setup and diagnostics areas.
- Added English, Korean, Japanese, Simplified Chinese, and French localization keys for the new endpoint-free macOS status copy.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning`
- `python3 script/check_macos_localization.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Runtime Delete Guard And Suggestion Visibility

- Used a GPT-5.5 worker for the bounded Android reasoning/suggestion UI audit. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Confirmed the Android reasoning surface already shows subdued assistant thinking with a compact three-line preview and an expandable full view.
- Tightened Android suggested-next-question visibility so suggestion chips and the loading row require actual assistant output. Empty assistant placeholders no longer trigger suggestion UI just because the latest assistant row is loading suggestions.
- Added Android regression coverage for hiding suggestion UI until assistant output exists.
- Hardened the macOS runtime chat store so `chat.session.delete` is accepted only for an already archived runtime-owned session. Active sessions now return `error` with `code = "chat_session_must_be_archived_before_delete"`, matching the Android UI rule and preventing future clients from bypassing archive-first semantics.
- Updated runtime lifecycle tests to prove active delete is rejected, archive-after-restore succeeds, and delete-after-archive still tombstones the session.
- Updated `docs/protocol.md` so permanent delete is documented as archive-only, with the runtime error code listed in the common error set.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle --filter LocalRuntimeMessageRouterTests/testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore --filter LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Android Legacy Chat Title Migration

- Used a GPT-5.5 worker for the bounded Android persisted-chat title migration. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Preserved the current rule that new local/persisted chat sessions start as `New chat` until the runtime returns generated title metadata or the user explicitly renames the session.
- Added a migration guard for older local cache entries where the title was exactly the first user prompt. Those legacy prompt-title sessions now sanitize back to `New chat` instead of continuing to expose the first prompt as the chat title.
- Preserved intentionally chosen titles: manually renamed sessions and runtime-generated titles are not rewritten by the legacy prompt-title migration.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Runtime-Generated Chat Title Flow

- Used a GPT-5.5 worker for the bounded runtime title-generation slice. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Added runtime-side automatic chat title generation after the first assistant response completes. The runtime now schedules title generation after `chat.done`, only for active sessions whose title is still the neutral placeholder and whose stored history is exactly the first answered user/assistant turn.
- Kept title generation runtime-mediated through the existing backend chat abstraction, so the device app still never calls Ollama, LM Studio, or another model backend directly.
- Added a deterministic fallback title derived from the assistant response when backend title output is empty or invalid. This avoids reverting to the first user prompt as the title while still giving the chat list a useful short label.
- Tightened explicit `chat.title.request` behavior so title requests require both user and assistant context.
- Refactored Android title-request eligibility into a testable `chatTitleRequestCandidate` helper and added regression coverage for the intended first-turn-only, authenticated, connected, untitled-session conditions.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse --filter LocalRuntimeMessageRouterTests/testChatSendTitleGenerationUsesDeterministicFallbackWhenBackendTitleIsInvalid --filter LocalRuntimeMessageRouterTests/testChatTitleRequestReturnsStructuredTitle`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Android Empty Chat And Composer Polish

- Used a GPT-5.5 worker for the bounded Android chat-surface polish. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Simplified the empty chat surface so disconnected/route-repair states keep a compact, lower-emphasis status message instead of a heavy card-like center panel.
- Preserved the no-sample-prompt rule: when the app is connected and ready for typing, the central empty-state prompt remains hidden and the bottom composer is the primary interaction.
- Added a small `chatEmptyPrimaryAction` policy so the empty state chooses `Scan QR` when no trusted runtime exists or when route refresh is needed, and `Connect` when a trusted runtime can be restored.
- Softened the bottom composer into a lighter dock with a subtle divider, keeping attachment, send, cancel, streaming progress, and haptic feedback behavior intact.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Android Quiet Composer Placeholder Removal

- Used a GPT-5.5 worker for the bounded Android composer cleanup. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Removed the visible empty chat composer placeholder text so the input surface stays visually quiet instead of showing generic copy such as `Message`.
- Preserved accessibility semantics by keeping the message field `contentDescription` backed by the localized `message` string.
- Removed the now-unused `chat_input_placeholder` key from all Android locale resource files.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 macOS QR-First Pairing Copy Cleanup

- Cleaned the macOS runtime pairing surface so visible fallback strings, localized values, and runtime log summaries use QR-first wording instead of manual pairing-code terminology.
- Kept the stable internal `"Pairing code generated"` log event unchanged for compatibility, while displaying it as a generated pairing QR in the macOS logs UI.
- Updated English, Korean, Japanese, Simplified Chinese, and French macOS localization values together.
- Removed unused legacy macOS localization keys that still mentioned manual pairing codes, while keeping the internal event key stable for tests and log mapping.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or end-to-end pairing on device.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift test --filter LocalRuntimeMessageRouterTests` from `apps/macos`
- `git diff --check`

## 2026-06-25 Android Drawer Delete Icon Alignment

- Used a GPT-5.5 worker for the bounded Android drawer icon fix. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Confirmed haptic feedback is already applied broadly across the Android chat, drawer, settings, model, memory, and confirmation actions.
- Fixed the chat session drawer dropdown so a delete action uses the delete/trash icon instead of the archive icon. This keeps destructive actions visually distinct from archive/restore actions if the drawer delete path is enabled for archived chats later.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 QR Pairing No-Device Checkpoint

- The Android phone was intentionally disconnected during this checkpoint, so optical QR scanning, physical install, and end-to-end pairing completion were not revalidated.
- Reconfirmed the no-device pairing surface that can be tested locally: Android pairing persistence/parser tests, transport route preparation tests, and macOS compact QR payload/remote route allocation tests.
- Current status: QR pairing code-level tests pass, but the QR flow should not be called fully fixed until the phone is reconnected and the camera scan plus runtime connection path is verified on device.

Verified after this check:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest :core:transport:testDebugUnitTest --no-daemon -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadUsesShortAliasesForCameraScanning`

## 2026-06-25 Remote Route Host Format Guard

- Used a GPT-5.5 worker for Android copy hygiene only. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion. The worker found no Android copy patch was needed.
- Hardened the macOS runtime model layer so remote connection address values shaped like URLs, user-info targets, paths, query strings, fragments, or `host:port` strings are rejected before they can overwrite saved route settings.
- Added a `HostReachabilityWarning.invalidFormat` state so the GUI and core route eligibility checks share the same route-host validation instead of relying only on the SwiftUI form.
- Added localized runtime-app copy for the invalid host warning across English, Korean, Japanese, Simplified Chinese, and French.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or end-to-end pairing on device.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Android Top Model Picker Polish

- Used a GPT-5.5 worker for the bounded Android top model picker slice. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Kept the chat model selector in the top chat bar beside the navigation control so model choice stays near the conversation surface instead of returning to bottom navigation or settings.
- Filtered the chat model selector to chat-capable models only. Embedding models remain available for embedding configuration but no longer appear as selectable chat generation models.
- Improved model ordering so the currently selected chat model stays pinned first, followed by running models, installed models, and then the remaining available models by name.
- Preserved saved selected-model labels during restore even when the runtime model list also contains embedding models or temporarily changes model availability.
- Expanded model search to match stable model identity fields, including id, name, backend, provider, provider model id, source, and description.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or optical QR scanning.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check`

## 2026-06-25 Android Runtime Copy Completion Audit

- Audited Android user-facing controls and copy in `MainActivity.kt`, `ClientScreens.kt`, and Android string resources for unfinished, manual-host, platform-specific, or prototype wording.
- Made a bounded Android-only resource patch across English, Korean, Japanese, Simplified Chinese, and French strings. Provider-unavailable guidance now points users to AetherLink Runtime instead of telling the device app user to open provider apps directly.
- Reworded remaining low-level route labels from endpoint/code/preview wording toward route, QR, and local fallback language while keeping the diagnostics controls available in Settings/Troubleshooting.
- Removed the automatic manual pairing-text dialog after QR scanner failure. Scanner failures now surface as errors, while pairing-text paste remains available only behind the explicit Settings/Troubleshooting diagnostics toggle.
- Removed the now-dead manual-pairing request counter and helper test path from the normal QR pairing panel.
- Did not touch macOS, protocol, transport, pairing core, Gradle config, or physical-device validation. No GPT-5.3-Codex-Spark agent was used.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or end-to-end pairing on device.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `git diff --check`

## 2026-06-25 Android Attachment Capability Audit

- Audited Android attachment UX and model capability gating in `MainActivity.kt`, `ClientScreens.kt`, Android string resources, and `AppNavigationTest`.
- Confirmed Android keeps file/image attachments at the runtime boundary: document attachments are allowed independent of vision support, while image sending remains blocked unless the selected chat model advertises vision/image/multimodal capability.
- Replaced the attachment picker MIME list's broad `application/*` request with a curated runtime-document set covering PDF, DOC/DOCX, HWP/HWPX, OpenDocument, spreadsheet, presentation, EPUB, RTF, JSON/XML/XHTML, and text files. Vision-capable selected models still add `image/*` automatically.
- Added Android regression assertions that non-vision models do not request image MIME types and that PDF, DOCX, HWPX, and text document selection remains available.
- Added runtime document-ingestion coverage for standalone XHTML files and Hancom HWPX MIME alias handling, keeping document text extraction on the runtime side.
- Did not touch protocol or physical-device validation. No GPT-5.3-Codex-Spark agent was used.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or attachment send on device.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `swift test --filter DocumentTextExtractorTests`
- `git diff --check`

## 2026-06-25 Relay Nonce Frame-Crypto Binding

- Used a GPT-5.5 read-only subagent to audit the Android/macOS relay encryption path. No GPT-5.3-Codex-Spark agent was used, and the subagent was closed after completion.
- Bound the QR/allocation `relay_nonce` into endpoint frame key derivation for encrypted relay traffic. Android now constructs relay frame crypto from both `relay_secret` and `RemoteRouteSecurityContext.antiReplayNonce`; macOS now carries `relayNonce` through `RelayPeerConfiguration` and into `RelayFrameCipher`.
- Preserved legacy/dev compatibility by keeping nonce optional for old secret-only frame vectors, while allocated QR routes use the lease nonce as part of the key material.
- Ensured saved and refreshed remote-route leases restore the same nonce into the macOS relay client configuration, so QR payload, persisted lease, and runtime relay connection agree after app restart.
- Fixed the standalone macOS development server's explicit relay path so a generated development lease nonce is also attached to the relay client configuration instead of emitting a QR-only nonce.
- Added shared Android/Swift ciphertext vectors for nonce-bound relay frames and mismatch tests proving the same `relay_secret` with a different `relay_nonce` cannot decrypt the frame.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, optical QR scanning, or end-to-end remote-network pairing on device.

Verified after this change:

- `swift test --filter ProtocolCodecTests`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator --filter LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode --filter LocalRuntimeMessageRouterTests/testCompanionAppModelStartRenewsSavedBootstrapRelayRouteBeforeRelayStart --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRetriesGUIRelayAllocationWhenGeneratingQRCodeWithoutLease --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithExpiredLease`
- `swift test --filter LocalRuntimeMessageRouterTests`
- `swift test --filter RelayAllocationTests`
- `swift build --target LocalAgentBridge`
- `swift build --target RuntimeDevServer`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:transport:testDebugUnitTest --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:transport:testDebugUnitTest --tests com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparationTest --no-daemon -Pkotlin.incremental=false`
- `git diff --check`

## 2026-06-25 Relay Smoke Nonce Alignment

- Updated the Swift authenticated mock relay smoke client to use the QR-provided `relay_nonce` when deriving its relay-frame AES-GCM key. The smoke now fails if relay route material is missing a nonce instead of accidentally testing a secret-only legacy path.
- Re-ran the mock authenticated relay E2E smoke after the nonce-binding change. The smoke paired through `AetherLinkRelay`, completed P-256 challenge-response authentication, then exercised `runtime.health`, `models.list`, `models.pull`, streaming `chat.send`, and `chat.cancel` through the encrypted relay frame path.
- Re-ran the no-ADB external relay QR smoke in local emit-only diagnostic mode. It started an allocation-required relay, started RuntimeDevServer with bootstrap relay allocation, generated the pairing URI, rendered the QR PNG, and verified QR PNG round-trip decode without adb or device install.
- Updated connection-overlay, protocol, and security docs to state that the current relay-frame key derivation binds both `relay_secret` and `relay_nonce`.
- The Android phone was disconnected during this pass, so this does not prove optical QR scan or real phone connectivity on a different network. It does prove the no-device relay path and QR artifacts are internally consistent after nonce binding.

Verified after this change:

- `script/runtime_authenticated_mock_smoke.swift --relay`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only --timeout 45`

## 2026-06-25 Android Model Menu Info Row Polish

- Replaced disabled `DropdownMenuItem` rows in the Android chat model picker with plain information rows. Empty model states, unavailable selected-model notices, and no-search-results messages no longer behave like disabled action buttons.
- Kept actual model rows as selectable menu items, preserving selection, installation gating, haptics, and the top chat-bar model picker structure.
- The Android phone was disconnected during this pass, so verification did not include physical-device screenshots or touch inspection.

Verified after this change:

- `rg -n "enabled = false,\\n\\s*onClick = \\{\\}|onClick = \\{\\},\\n\\s*enabled = false" apps/android/app/src/main/java/com/localagentbridge/android -U` returns no matches
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --no-daemon -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-25 macOS Remote QR Route Copy Polish

- Used a GPT-5.5 worker subagent for the bounded macOS copy/localization slice. No GPT-5.3-Codex-Spark agent was used, and the worker was closed after completion.
- Reworded the macOS remote-route panel so the normal flow reads as QR-based pairing instead of fixed host/port entry. The visible setup label now presents as a remote QR route, while manual route fields live under route diagnostics.
- Updated English, Korean, Japanese, Simplified Chinese, and French strings for route diagnostics, route address, QR pairing guidance, and port-field validation copy.
- Kept behavior unchanged: diagnostics route fields still exist for support/development relay addresses, and Android still does not connect directly to Ollama or LM Studio.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or end-to-end pairing on device.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`

## 2026-06-25 Runtime-Owned Chat History Guard

- Added an Android-side guard so runtime-owned chat sessions cannot be archived, restored, or permanently deleted while the trusted runtime is disconnected or unauthenticated. Local-only chat cache entries can still be managed locally.
- This moves chat history behavior closer to the requested source-of-truth model: chat processing/history is stored by AetherLink Runtime, and Android acts as a controller plus cache instead of mutating runtime-owned history offline.
- Added localized error copy in English, Korean, Japanese, Simplified Chinese, and French for runtime-saved chat history changes that require a runtime connection.
- Added a pure unit test for the runtime-owned lifecycle mutation policy.
- Used a GPT-5.5 read-only subagent to audit current gaps. No GPT-5.3-Codex-Spark agent was used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or end-to-end pairing on device.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --no-daemon -Pkotlin.incremental=false`

## 2026-06-25 Pairing URI Auth Smoke Coverage

- Updated the authenticated runtime smoke client so it parses the emitted `aetherlink://pair` URI and uses that URI-derived pairing nonce, pairing code, runtime identity, relay route, relay secret, and relay nonce for the actual pairing/authentication path.
- Kept `AETHERLINK_DEV_PAIRING_INFO` as cross-check evidence only. The smoke now fails if the URI and info disagree, if relay URI material is incomplete, if relay lease expiration is stale, or if relay-mode QR material unexpectedly includes direct host/port fallback.
- Re-ran the relay smoke through `AetherLinkRelay`. The test paired through the URI-derived relay route, authenticated with P-256 challenge-response, exercised `runtime.health`, `models.list`, `models.pull`, streaming `chat.send`, and `chat.cancel`, then reconnected through the saved trusted relay route and checked `runtime.health` again.
- Re-ran the direct mock smoke to confirm the URI parsing and saved-route reconnect changes do not break the local diagnostic development path.
- This still does not replace real optical QR scanning on a physical Android device, but it reduces the no-device gap by proving the emitted QR URI can drive the authenticated client path.

Verified after this change:

- `script/runtime_authenticated_mock_smoke.swift --relay`
- `script/runtime_authenticated_mock_smoke.swift`

## 2026-06-25 macOS Automatic Route Preparation Copy

- Exposed whether the macOS companion can prepare a remote relay route automatically from bootstrap route configuration. The environment allocator now reports availability only when bootstrap endpoints are present and static override credentials are complete.
- Updated the Pairing screen empty state and route notice so bootstrap-capable setups tell users to generate a pairing QR and wait for AetherLink to prepare the route, instead of making the normal flow look like manual host/port setup.
- Updated the Remote QR Route status copy to say AetherLink can prepare the remote route automatically when QR generation starts.
- Added English, Korean, Japanese, Simplified Chinese, and French strings for the automatic route-preparation copy.
- This is still a development/bootstrap relay path, not the final production P2P overlay. It does move the user-facing macOS flow closer to QR-first pairing.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift test --filter LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorReportsAutomaticAvailabilityFromBootstrapEnvironment`
- `swift build --target LocalAgentBridge`

## 2026-06-25 Android No-Device Chat Shell Polish

- Used a GPT-5.5 read-only subagent for a bounded Android UI audit. No GPT-5.3-Codex-Spark agent was used, and the subagent was closed after completion.
- Tuned the Android light and dark Material color schemes away from the older teal/yellow-heavy palette toward a more neutral, modern chat-app base with a restrained green primary accent.
- Added a thin divider under the Android top app bar so the chat shell reads as a cleaner application frame instead of a single flat surface.
- Added an in-field placeholder to the Android chat composer when the input is empty. The composer no longer depends only on bottom status text to communicate readiness.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or different-network pairing. Those remain the next device-dependent checks after reconnection.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check`

## 2026-06-25 Android Split Think-Tag Fallback Hardening

- Used a GPT-5.5 read-only subagent for the Android reasoning/think UI audit. No GPT-5.3-Codex-Spark agent was used, and the subagent was closed after completion.
- Confirmed the main reasoning UI path is already present: runtime `reasoning_delta`/`thinking_delta` values are stored separately from answer text and rendered as a muted, compact, expandable section.
- Hardened Android's compatibility fallback for inline `<think>`/`<thinking>` tags when a backend or mock transport splits the tag across streamed chunks. Partial tag fragments such as `<thi` or `</thi` are now held across deltas instead of leaking into the visible answer or reasoning body.
- Added regression coverage for split opening tags, split closing tags, and cleanup of an incomplete tag fragment when generation completes.
- This is no-device validation only. Physical-device QA still needs a live streamed response from a reasoning-capable model and tap-to-expand validation after the Android phone is reconnected.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkOpeningTagAcrossDeltasDoesNotLeakTagToAnswer --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkClosingTagAcrossDeltasDoesNotLeakTagToReasoning --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.incompleteInlineThinkTagPlaceholderIsClearedOnDone --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.inlineThinkTagsAreSeparatedFromAnswerContent --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkTagsKeepReasoningCollapsedOutOfAnswerContent`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --tests com.localagentbridge.android.AppNavigationTest`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check`

## 2026-06-25 Runtime-Owned Chat Rename

- Added `chat.session.rename` to the Android/macOS protocol surface so user-provided chat titles for runtime-owned sessions are stored by AetherLink Runtime instead of remaining Android-local cache state only.
- Android now blocks runtime-owned chat rename while disconnected or unauthenticated, matching the existing archive/restore/delete guard for runtime-owned history changes. Local-only cached chats can still be renamed locally.
- Android sends a `chat.session.rename` command after an optimistic local rename and accepts the runtime acknowledgement to re-sync the cached title.
- macOS Runtime now handles authenticated `chat.session.rename` by appending a runtime-side `title` event and returning `session_id`, `title`, and `renamed_at`.
- Updated the JSON protocol schema and protocol documentation with the new message type.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, optical QR scanning, or live runtime rename from the app.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:protocol:testDebugUnitTest --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSessionRenamePayloadUsesProtocolFieldNames :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest --tests com.localagentbridge.android.AppNavigationTest`
- `swift test --filter LocalRuntimeMessageRouterTests/testRuntimeChatSessionRenameStoresRuntimeTitle`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`

## 2026-06-25 Android Chat Composer Placeholder Correction

- Removed the visible Android chat composer placeholder that had been reintroduced during no-device shell polish. This restores the user's requested quiet composer surface: no generic `Message`, `Ask anything`, or similar prompt text appears inside the input field.
- Kept accessibility semantics for the message field and send-button readiness, so the visual UI stays quiet without removing screen-reader affordances.
- Rechecked current Android source/resources for stale generic composer placeholder strings.
- The Android phone was disconnected during this pass, so verification did not include physical-device install, screenshots, or on-device visual inspection.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `rg -n "placeholderText|chat_input_placeholder|무엇이든|Ask anything" apps/android/app/src/main/java apps/android/app/src/main/res` returns no matches

## 2026-06-25 Android Runtime-Owned Chat Rehydration Guard

- Added regression coverage for the runtime-owned chat storage boundary on Android. A locally persisted runtime-owned session can keep metadata and message count while omitting message bodies from device storage.
- Verified that, after the client reconnects and receives `chat.sessions.list`, the active redacted runtime-owned session requests `chat.messages.list` and rehydrates the visible transcript from AetherLink Runtime.
- Kept the test relay-backed: the reconnect path uses the stored QR relay route and does not fall back to direct local transport.
- The Android phone was disconnected during this pass, so this remains source/unit-level evidence only. Physical app restart, trusted reconnect, and transcript reload still need a fresh device run after reconnection.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeRedactedRuntimeSessionRehydratesAfterReconnectSessionSync -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotDropsRuntimeOwnedMessageBodiesButKeepsLocalDrafts --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeRedactedRuntimeSessionRehydratesAfterReconnectSessionSync -Pkotlin.incremental=false`

## 2026-06-25 Android Pairing-First Settings Hierarchy

- Used a GPT-5.5 read-only subagent for a bounded Android UI hierarchy audit. No GPT-5.3-Codex-Spark agent was used, and the subagent was closed after completion.
- Adjusted the Android Settings screen so first launch and pending QR-route states start with the pairing hierarchy instead of showing the generic Settings header before pairing. Once a trusted runtime is saved and no QR route is pending, the normal Settings header returns.
- Added helper-level regression coverage for unpaired first launch, pending QR route, and trusted-runtime Settings hierarchy.
- The Android phone was disconnected during this pass, so this remains source/unit-level evidence only. Fresh on-device visual validation is still required after reconnecting the phone.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.unpairedSettingsScreenStartsWithPairingHierarchy --tests com.localagentbridge.android.AppNavigationTest.pendingQrRouteSettingsScreenKeepsPairingHierarchy --tests com.localagentbridge.android.AppNavigationTest.trustedSettingsScreenKeepsGenericSettingsHeader -Pkotlin.incremental=false`

## 2026-06-25 Android Adaptive Navigation Rail

- Added an expanded-width Android navigation rail so larger screens keep Chat and Settings visible on the left edge while the full chat-history drawer remains available from the top bar.
- The Settings item is anchored at the bottom of the rail, matching the requested ChatGPT-like sidebar placement on larger screens without changing the compact phone drawer behavior.
- Added a pure helper breakpoint test for the expanded-width rail threshold.
- The Android phone was disconnected during this pass, so this remains compile/unit-level evidence only. Fresh screenshots are still needed on a real phone or emulator after reconnection.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.permanentNavigationRailUsesExpandedWidthOnly -Pkotlin.incremental=false`

## 2026-06-25 macOS QR-First Companion Polish

- Used a GPT-5.5 read-only subagent for a bounded macOS companion UI/localization audit. No GPT-5.3-Codex-Spark agent was used, and the subagent was closed after completion.
- Hid the manual Route Diagnostics panel from normal Pairing and Status screens when automatic remote route preparation is available and no diagnostic route is already saved. This keeps the normal flow QR-first while preserving diagnostics for setups that cannot prepare routes automatically or already have a diagnostic route configured.
- Localized macOS model-residency event summaries so the Status card no longer shows raw English runtime event strings for model unload requested/succeeded/failed cases.
- Added English, Korean, Japanese, Simplified Chinese, and French strings for the new model-residency summaries.
- This is no-device/no-window validation only. A fresh macOS visual run is still needed before claiming current rendered layout quality.

Verified after this change:

- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-25 QR-First Route Diagnostics Guard

- Added a source-level guard to `script/check_copy_hygiene.py` so the macOS Route Diagnostics panel cannot be mounted directly in normal Pairing or Status surfaces without going through `shouldShowRouteDiagnosticsPanel(model:)`.
- The guard preserves the intended QR-first pairing path: route address, port, and route setup secret fields stay diagnostic-only unless automatic remote route preparation is unavailable or a diagnostic route already exists.
- The Android phone was disconnected during this pass, so this does not prove camera QR pairing or physical-device reconnect. It only prevents a known source regression while device validation is unavailable.

Verified after this change:

- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_macos_localization.py`
- `swift build --target LocalAgentBridge`

## 2026-06-25 QR Pairing Reliability Fixes

- Used two GPT-5.5 workers for bounded QR-pairing reliability fixes. No GPT-5.3-Codex-Spark agent was used, and both workers were closed after completion.
- Android optical QR scanning now treats ordinary ML Kit per-frame barcode processing failures as non-terminal, keeping the scanner open for the next frame instead of closing pairing on a transient analyzer failure. Camera permission/setup/bind failures remain fatal.
- Android QR acceptance remains limited to `aetherlink://pair` and legacy `lab://pair`; unrelated schemes/actions such as `https://...` or `aetherlink://settings` are still rejected.
- The development relay now sends an explicit `AETHERLINK_RELAY registered` acknowledgement after accepting a runtime registration. `RelayPeerClient` reports `waitingForPeer` only after that acknowledgement, so QR-ready gates no longer treat a raw TCP-ready connection as a usable relay route.
- Existing relay pairing and reconnect smoke behavior still passes: QR emission now occurs after accepted runtime registration, then moves to `ready` after the client peer is matched.
- The Android phone was disconnected during this pass, so this remains source/headless evidence only. Camera-based optical scan, real QR pairing completion, and different-network phone-to-relay reachability still need physical-device validation after reconnection.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest -Pkotlin.incremental=false`
- `swift test --filter RelayPeerClientTests`
- `swift test`
- `swift build --target RuntimeDevServer`
- `swift build --target LocalAgentBridge`
- `script/runtime_authenticated_mock_smoke.swift --relay`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only`
- `python3 script/check_copy_hygiene.py && python3 script/check_docs_hygiene.py && python3 script/check_protocol_schema.py`
- `python3 script/check_android_string_parity.py && python3 script/check_macos_localization.py`
- `git diff --check`

## 2026-06-25 Android QR Route Diagnostics Copy

- Clarified the Android pairing-copy path for identity-only QR scans. When a QR identifies the runtime but does not include remote connection details, the UI now says local discovery only works when the same local route is visible and asks the user to scan the latest QR with connection details for different networks.
- Updated English, Korean, Japanese, Simplified Chinese, and French Android string resources for the pending pairing route state, `pairing_endpoint_unavailable`, and remote-pending route diagnostic copy.
- This is no-device validation only. It improves the explanation shown after QR parsing/route planning states, but it does not prove optical QR scan completion or phone-to-relay reachability.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `git diff --check -- apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml`

## 2026-06-25 Android Structured Error Detail Visibility

- Updated the Android error surface so non-route error cards can show structured `RuntimeUiError.detail` text instead of limiting detail display to a small set of hard-coded error codes.
- This keeps QR scan, invalid pairing QR, pairing rejection, discovery failure, send failure, and runtime-returned error reasons visible when the ViewModel already has a useful detail string.
- Added a focused helper test so blank details stay hidden while meaningful details are preserved for rendering.
- This remains no-device evidence. It improves on-screen diagnostic quality, but it does not replace physical QR scan or real transport validation.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailKeepsStructuredErrorDetails -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`

## 2026-06-25 macOS Connection Route Status Detail

- Updated the macOS Status screen Connection Routes card so a saved remote route shows the current relay state instead of a generic route-protection message.
- The card now distinguishes connecting, waiting for a trusted device, matched/ready, reconnecting, failed, and stopped route states while still keeping normal model access mediated by AetherLink Runtime.
- This is no-device/no-window validation only. It does not prove physical-device pairing, different-network reachability, or rendered macOS layout quality.

Verified after this change:

- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift`

## 2026-06-25 Android Product Copy Polish

- Used two GPT-5.5 read-only audit agents, one for Android UI/copy and one for macOS UI/localization. GPT-5.3-Codex-Spark was not used, and both agents were closed after their audits.
- Refined Android chat-history copy in English, Korean, Japanese, Simplified Chinese, and French so archive/restore/permanent-delete semantics read as product actions instead of administrative warnings.
- Clarified that archived chats stay saved but leave the main list and stop contributing to Memory, matching the intended archive-vs-delete behavior.
- Softened Android troubleshooting route copy so hidden diagnostics surfaces say connection troubleshooting, local test route, and troubleshooting route instead of advanced/development diagnostics language.
- Renamed Android embedding-model settings copy to Memory indexing model across all five UI languages while still describing that AetherLink Runtime supplies the embedding model for memory/retrieval workflows.
- Kept the current reasoning UI behavior unchanged: Android already shows a dim three-line reasoning preview with expansion, which matches the requested Ollama-style reasoning treatment better than hiding reasoning by default.
- Recorded the macOS audit follow-up: Pairing/Status/Activity copy should continue moving from route-material/runtime-identity wording toward trust-and-connection wording in a later macOS copy pass.
- The Android phone was disconnected during this pass, so this remains source/resource validation only.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`

## 2026-06-25 macOS Product Copy Polish

- Continued the no-device product-polish pass on the macOS runtime UI after the GPT-5.5 audit identified route-material/runtime-identity wording in normal flows.
- Updated macOS Pairing copy so the visible flow talks about trusting AetherLink Runtime and connection details rather than runtime identity, route material, or local discovery paths.
- Renamed the visible remote-route fallback panel to Advanced Connection Setup and softened its status/actions to connection setup, connection details, and technical details. Internal `developmentRelay*` API names and relay log parsing remain unchanged.
- Updated macOS Status readiness copy so the runtime reads as ready for paired devices, model providers, and trusted chat instead of exposing listener/session terminology.
- Renamed the sidebar diagnostics destination to Activity and moved remaining low-level log content behind Technical Details in the existing disclosure pattern.
- Added matching English, Korean, Japanese, Simplified Chinese, and French localization entries for the new macOS product-facing strings.
- This is no-device/no-window validation only. A rendered macOS pass is still needed before claiming final layout quality.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `swift build --target LocalAgentBridge`
- `python3 script/check_copy_hygiene.py`

## 2026-06-25 macOS Stale Product Copy Guard

- Removed unused macOS localization keys that still carried older route-material, runtime-identity, listener, and diagnostics wording after the visible UI had moved to connection-details and Activity language.
- Tightened macOS visible copy in Status, Activity, and Advanced Connection Setup so normal surfaces say device connections, nearby/cross-network connectivity, saved connection details, and connection address instead of remote route or route address.
- Added a macOS product-copy guard to `script/check_copy_hygiene.py`. The guard scans `NSLocalizedString` keys and macOS `Localizable.strings` entries for stale visible wording such as Route Diagnostics, Runtime Diagnostics, route material, runtime identity, local discovery path, Runtime listener, and remote-route product copy.
- Internal relay/log parser tokens remain unchanged where they are needed to decode runtime event strings, but those tokens are kept out of user-facing summaries.
- The Android phone was disconnected during this pass, so this remains no-device/no-window validation only.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`

## 2026-06-25 Android Quiet Empty Chat Guard

- Removed the remaining ready-state empty-chat title/body resources (`empty_chat_title`, `empty_chat`) from all Android locale files so a connected, model-ready blank chat cannot show a static center prompt again.
- Kept blocker states visible: disconnected, QR-route-refresh-needed, streaming, and model-required states still show actionable empty-state copy.
- Preserved the requested behavior that next-question chips appear only after an assistant answer or while AetherLink is generating suggestions, not as static first-screen example prompts.
- The Android phone was disconnected during this pass, so this is source/unit-level evidence only. Fresh screenshots and touch validation are still needed after reconnecting the phone.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.emptyChatHidesStaticPromptWhenReadyToType --tests com.localagentbridge.android.AppNavigationTest.emptyChatUsesTopModelPickerWhenConnectedWithoutUsableModel -Pkotlin.incremental=false`
- `rg -n 'empty_chat_title|name="empty_chat"|Start a conversation|새 대화 시작|新しい会話を開始|开始新对话|Démarrer une conversation' apps/android/app/src/main apps/android/app/src/test || true`

## 2026-06-25 Android Runtime Trust Copy Guard

- Refined Android QR/trust error copy across English, Korean, Japanese, Simplified Chinese, and French so visible errors say the scanned QR does not match the trusted AetherLink Runtime instead of exposing `runtime identity` terminology.
- Updated the runtime-authentication failure message to say AetherLink Runtime could not verify saved trust and to ask for the latest trusted QR.
- Strengthened `script/check_android_string_parity.py` so ready-state static empty-chat resources (`empty_chat_title`, `empty_chat`) and visible `runtime identity` product copy cannot be reintroduced.
- This is source/resource validation only while the Android phone is disconnected; QR scan and error rendering still need a physical-device pass.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `rg -n "runtime identity|empty_chat_title|name=\"empty_chat\"|Start a conversation|새 대화 시작|新しい会話を開始|开始新对话|Démarrer une conversation" apps/android/app/src/main/res apps/android/app/src/main/java apps/android/app/src/test script/check_android_string_parity.py`

## 2026-06-25 Android Multilingual Trust Copy Guard

- Removed the remaining user-facing trust/QR wording that exposed localized identity terminology in Android resources, including Korean `런타임 신원`, Japanese `ランタイム ID` / `識別情報`, Simplified Chinese `运行时身份` / `可信身份`, and French runtime-identity phrasing.
- Updated pairing, QR scanner, pending-route, discovery-status, endpoint-unavailable, and device-key failure copy to use QR-verified AetherLink Runtime, trust details, and trust keys across English, Korean, Japanese, Simplified Chinese, and French.
- Expanded `script/check_android_string_parity.py` to catch the multilingual identity wording patterns alongside the existing English runtime-identity guard.
- This is still source/resource validation only while the Android phone is disconnected. Optical QR scan, on-device language switching, and rendered copy still need a physical-device pass.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `rg -n "runtime identit|trusted identity|런타임 신원|신원 정보|신원 확인|ランタイム ID|信頼済み ID|識別情報|运行时身份|可信身份|身份未知|identit[ée]s? de runtime|identit[ée] approuv[ée]e|identit[ée] inconnue|empty_chat_title|name=\"empty_chat\"" apps/android/app/src/main/res/values* apps/android/app/src/main/java apps/android/app/src/test script/check_android_string_parity.py`

## 2026-06-25 macOS Technical Details Copy Guard

- Replaced the visible macOS provider toggle label `Provider Diagnostics` with `Technical Details`, matching the Activity screen's existing disclosure language.
- Updated remaining visible fallback copy in Pairing and Advanced Connection Setup from `configured route` / `route port` to `saved connection` / `connection port`.
- Removed unused macOS localization keys that still mentioned Logs, Diagnostics, Connection Routes, route QR, route settings, route port, and QR route protection.
- Strengthened `script/check_copy_hygiene.py` so those stale macOS localization keys and visible `NSLocalizedString` labels cannot be reintroduced.
- This is no-device/no-window validation only. A rendered macOS pass is still needed before claiming current layout quality.

Verified after this change:

- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`
- `rg -n '"(Provider Diagnostics|No diagnostics yet|No runtime logs|Connection Routes|configured route|Save Route|.*route QR.*|.*QR route.*|.*route settings.*|.*route port.*|.*Relay route.*|Current QR route protection)' apps/macos/LocalAgentBridgeApp/Sources/Resources apps/macos/LocalAgentBridgeApp/Sources || true`

## 2026-06-25 QR Pairing Reachability Checkpoint

- Rechecked the QR pairing path while the Android phone was disconnected. This checkpoint is source/script evidence only; optical QR scan and phone network reachability are not verified.
- Android QR scanner, deeplink, and manual pairing text all feed the same `trustRuntimeFromPairingQr` path.
- Android accepts the compact remote-route QR form emitted by AetherLink Runtime, strips direct `host`/`port` when relay route material is present, prepares a relay route without a manual endpoint, and sends `pairing.request` over the prepared relay route in unit coverage.
- Android intentionally rejects product QR payloads that contain only a direct local `host`/`port` route. Direct local endpoint QR payloads are debug/diagnostic-only and cannot solve different-network connectivity.
- AetherLink Runtime's normal macOS pairing UI calls `beginPairing(routePolicy: .remoteRequired)`, so product QR generation requires prepared connection details instead of silently falling back to a fixed local address.
- Different-network QR pairing is therefore not "same-network-only", but it is only functional when the QR includes a mutually reachable relay/overlay route. A QR that contains only identity material, a private IP, loopback, `.local`, or a local diagnostic route cannot cross unrelated networks.
- The current development relay path can generate a valid QR URI/PNG and encrypt relay frame bodies using `relay_secret` plus `relay_nonce`. It is still not the final production P2P/private-overlay/TURN layer.

Verified after this checkpoint:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest :app:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrScanPlansPendingRelayPairingWithoutManualEndpoint --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.identityOnlyQrPlanStartsDiscoveryAndWaitsForRoute --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest -Pkotlin.incremental=false`
- `./script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 43171 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-qr-check`
- Sanitized generated QR field check: `v`, `n`, `c`, `rid`, `rf`, `rk`, `rt`, `rh`, `rp`, `ri`, `rs`, `rx`, `rrn`, and `rsc` were present in `/tmp/aetherlink-no-adb-qr-check/pairing-uri.txt`; secrets were not copied into this document.

## 2026-06-25 Android Chat Data Safety Regression Guard

- Added no-device Android unit coverage for the archive/delete storage boundary requested for chat history.
- `permanentDeleteArchivedChatSessionsSuppressesOnlyRuntimeOwnedArchivedSessions` proves permanent deletion of archived chats keeps active previous chats, removes archived chats, and records deletion suppressions only for runtime-owned archived sessions so server sync cannot reintroduce them. Local-only archived chats are removed locally without polluting the runtime-deletion suppression list.
- `deviceStorageSnapshotRedactsArchivedRuntimeOwnedBodiesButKeepsLocalArchivedBodies` proves runtime-owned chat message bodies are redacted from device storage even when the session is archived, while local-only archived notes keep their local body content.
- This keeps AetherLink aligned with the product rule that chat processing/transcripts are runtime-host-owned, archived chats stay out of Memory/Research candidates, and local-only drafts are not accidentally discarded by the runtime redaction path.
- The Android phone was disconnected during this pass, so this is unit/source evidence only. It does not prove rendered Settings behavior, haptics, or physical archive/delete flows.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsSuppressesOnlyRuntimeOwnedArchivedSessions --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotRedactsArchivedRuntimeOwnedBodiesButKeepsLocalArchivedBodies -Pkotlin.incremental=false`

## 2026-06-25 macOS App Language Regression Guard

- Added a SwiftPM `LocalAgentBridgeTests` test target for the macOS runtime app module so product-facing app language behavior is covered by native tests, not only by localization scripts.
- Added `AetherLinkLocalizationTests` for the initial five app languages: English, Korean, Japanese, Simplified Chinese, and French.
- The tests pin the default macOS UI language to English, keep the language list limited to the current five-language launch set, verify Chinese alias normalization (`zh-CN`, `zh-Hans`, `zh-rCN`, `zh-Hans-CN`), and keep the persisted `aetherlink.appLanguageTag` key stable.
- This is no-window/no-device validation only. It proves the macOS language selector contract at source/test level, but rendered app-language switching still needs a macOS UI pass.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- Package.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`

## 2026-06-25 Android Release Troubleshooting Guard

- Added a small Android UI contract helper for the Settings troubleshooting section so the normal Settings hierarchy remains pairing/status/preferences/memory/history first, while manual route and discovery troubleshooting stay explicitly tied to the debug diagnostics flag.
- Added unit coverage proving the troubleshooting section is hidden when `showDeveloperDiagnostics` is false and visible only when the debug diagnostics path is enabled.
- Strengthened `script/check_copy_hygiene.py` so future Android UI changes must keep Settings troubleshooting visibility centralized behind `settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics)` instead of sprinkling raw debug-flag checks through the visible Settings body.
- The same guard now checks the app wiring in `MainActivity.kt`: `SettingsScreen` must receive the centralized `showDeveloperDiagnostics` state, and that state is enabled only when a debug build is launched with the explicit developer-diagnostics request. Release builds and ordinary debug launches do not expose manual route/discovery troubleshooting controls.
- This keeps QR-first pairing and trusted runtime reconnect as the product path; local discovery, manual route text, and support route controls remain development/troubleshooting helpers instead of release UX.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove rendered Settings behavior or physical QR pairing.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsTroubleshootingSectionStaysDebugOnly -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`
- `git diff --check -- script/check_copy_hygiene.py`
- `python3 -m py_compile script/check_copy_hygiene.py`

## 2026-06-25 Android Preferences Option Contract

- Extracted Android Settings language and appearance option lists into testable UI helpers so the rendered selectors and unit tests use the same source of truth.
- Superseded on 2026-06-26: the same unit coverage now pins the visible launch language selector order to English, Korean, Japanese, Simplified Chinese, and French only.
- Added unit coverage that pins the appearance selector order to system, light, and dark, matching the requirement that AetherLink follows the device appearance by default while allowing explicit overrides.
- This is source/unit evidence only while the Android phone is disconnected. It does not prove physical device language switching or rendered Settings layout.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsLanguageOptionsKeepCurrentLaunchLanguageSetAndOrder --tests com.localagentbridge.android.AppNavigationTest.settingsThemeOptionsKeepSystemLightDarkOrder -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`

## 2026-06-25 macOS Language Picker Option Contract

- Extracted the macOS runtime app language picker source into `AetherLinkAppLanguage.pickerOptions`, so the sidebar language menu and tests use the same ordered option list.
- Updated the language picker to render from `pickerOptions` instead of reading enum cases directly.
- Added Swift test coverage that keeps the picker aligned with the initial five-language launch set: English, Korean, Japanese, Simplified Chinese, and French.
- This is no-window/no-device validation only. It proves the Swift option contract and localization parity, but not rendered menu layout.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/AetherLinkLocalization.swift apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`

## 2026-06-25 macOS Appearance Preference

- Added a macOS runtime app appearance preference that matches the Android Settings contract: system, light, and dark.
- Added `AetherLinkAppAppearanceStorageKey` and `AetherLinkAppAppearance`, including normalization, picker options, and `preferredColorScheme` mapping.
- Wired the main SwiftUI window to apply the saved appearance through `.preferredColorScheme(...)`, while keeping system appearance as the default.
- Added a compact Appearance picker beside the existing Language picker in the sidebar footer.
- Localized Appearance, System, Light, and Dark across English, Korean, Japanese, Simplified Chinese, and French.
- Added Swift tests covering appearance picker options, default system behavior, normalization, color-scheme mapping, and the stable storage key.
- Strengthened `script/check_macos_localization.py` so it also verifies macOS appearance options, picker order, default system behavior, stable storage key, color-scheme mapping, required localized keys, and the app/sidebar wiring that applies the saved preference.
- This is no-window validation only. It proves the source/test/localization contract but not the rendered macOS layout.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`
- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/AetherLinkLocalization.swift apps/macos/LocalAgentBridgeApp/Sources/LocalAgentBridgeApp.swift apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ko.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ja.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/zh-Hans.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/fr.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`
- `git diff --check -- script/check_macos_localization.py`

## 2026-06-25 Android Appearance Regression Guard

- Strengthened `script/check_android_string_parity.py` so it now verifies Android appearance support in addition to language/string parity.
- The checker now fails if `RuntimeAppTheme` drifts away from System, Light, and Dark; if UI or persisted theme defaults stop following the system setting; if persisted theme values stop normalizing through `RuntimeAppTheme`; if appearance string keys are missing; or if Settings/theme wiring no longer applies `state.selectedTheme` through `AetherLinkTheme`.
- This complements the focused Android unit tests for Settings option order and keeps Android aligned with the macOS appearance contract.
- The Android phone is disconnected during this pass, so this is source/script evidence only. It does not prove physical device theme switching or rendered Settings layout.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsThemeOptionsKeepSystemLightDarkOrder -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 -m py_compile script/check_android_string_parity.py`

## 2026-06-25 Android Reasoning Display Contract

- Extracted the Android assistant reasoning display behavior into a small `reasoningDisplayPolicy` helper used by the Compose reasoning panel.
- Added unit coverage that keeps collapsed reasoning dimmed, limited to the three-line preview, and marked expandable only when the reasoning text is longer than the compact preview.
- Added unit coverage that expanded reasoning shows the full text with the expanded alpha only when the content is actually expandable; short reasoning remains quiet and non-expandable.
- This preserves the requested Ollama-style treatment: reasoning/think content is visible but subdued, short by default, and expandable on demand.
- The Android phone is disconnected during this pass, so this is source/unit evidence only. It does not prove physical tap behavior or rendered on-device layout.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.reasoningDisplayPolicyKeepsCollapsedPreviewDimAndThreeLines --tests com.localagentbridge.android.AppNavigationTest.reasoningDisplayPolicyExpandsOnlyWhenExpandable -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`

## 2026-06-25 Android Empty Chat And Suggestions Contract

- Used one GPT-5.5 read-only explorer to audit Android empty chat, suggestion chips, and composer placeholder behavior. No GPT-5.3-Codex-Spark subagent was used, and the explorer was closed after completion.
- Added `shouldShowAssistantSuggestionsForMessage(...)` so the Compose chat row and tests share the same state-based rule: suggestions show only for the latest assistant row, only after non-blank assistant answer text exists, and never while streaming.
- Added unit coverage proving older assistant rows, user rows, and reasoning-only assistant rows do not show suggested next questions.
- Added `chatEmptyStaticPromptRes()` and unit coverage proving the empty chat center keeps static example prompts out of the ready-to-type state. Runtime-generated next questions remain tied to completed assistant output instead.
- The Android phone is disconnected during this pass, so this is source/unit evidence only. It does not prove rendered device layout, tap behavior, or live runtime-generated suggestions.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.emptyChatKeepsStaticExamplePromptsOutOfCenterState --tests com.localagentbridge.android.AppNavigationTest.assistantSuggestionsUseOnlyLatestAssistantWithRealOutputFromState --tests com.localagentbridge.android.AppNavigationTest.assistantSuggestionsStayHiddenForReasoningOnlyAssistantRows -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`

## 2026-06-25 macOS Localization Lookup And Connection Disable Safety

- Added macOS runtime app localization tests proving the stored app language drives `NSLocalizedString` lookup from the SwiftPM resource bundle, including Korean lookup, unsupported-language fallback to English, and missing-key fallback to the key itself.
- Used one GPT-5.5 read-only explorer to audit macOS runtime UI language/appearance, QR-first pairing, platform-neutral copy, and destructive actions. No GPT-5.3-Codex-Spark subagent was used, and the explorer was closed after completion.
- Added a destructive confirmation dialog before Advanced Connection Setup clears saved cross-network connection details. The confirmation explains that devices on another network may need a fresh pairing QR before reconnecting.
- Localized the new confirmation title and message across English, Korean, Japanese, Simplified Chinese, and French.
- Strengthened `script/check_macos_localization.py` so it guards the disable-connection confirmation wiring and required localized safety copy.
- This is no-window/no-device validation only. It proves source, localization, and build behavior but not the rendered macOS confirmation dialog.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests`
- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`
- `python3 -m py_compile script/check_macos_localization.py`

## 2026-06-25 Android Chat History Danger Guard

- Strengthened `script/check_copy_hygiene.py` with an Android chat-history danger-action guard.
- The guard now fails if bulk chat-history actions stop being collapsed behind Manage all chats, if archive-all or permanent-delete flows stop opening the shared two-step confirmation dialog, if the first/second confirmation copy is removed, or if permanent delete stops being limited to archived chats.
- The guard also checks that the focused helper-level regression tests for archive-all, permanent bulk delete, single archived-chat delete, and bulk-action visibility remain present.
- No GPT-5.3-Codex-Spark subagent was used. A GPT-5.5 read-only explorer was opened only to look for additional no-device gaps while this guard was patched.
- The Android phone is disconnected during this pass, so this is source/script evidence only. It does not prove rendered Settings layout, physical haptics, or on-device two-step dialog behavior.

Verified after this change:

- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- script/check_copy_hygiene.py`

## 2026-06-25 Android Manual QR Payload Guard

- Reused the Android QR raw-value validation rule for manual QR payload paste/entry.
- `usableManualPairingPayload(...)` now accepts only trimmed `aetherlink://pair` or legacy-compatible `lab://pair` payloads, matching the camera scanner route contract.
- Added unit coverage proving generic HTTPS URLs and other AetherLink actions such as `aetherlink://settings` cannot be submitted through the manual QR payload dialog.
- This closes a no-device gap found by a GPT-5.5 read-only explorer; the explorer did not edit files and was closed afterward. No GPT-5.3-Codex-Spark subagent was used.
- The Android phone is disconnected during this pass, so this is source/unit evidence only. It does not prove physical camera QR scanning or on-device pairing completion.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.manualPairingPayloadTrimsCopiedQrText --tests com.localagentbridge.android.AppNavigationTest.manualPairingPayloadRejectsUnsupportedUrlsOrActions --tests com.localagentbridge.android.AppNavigationTest.manualPairingPayloadRejectsBlankText -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`

## 2026-06-25 Android Runtime Boundary And Error Detail Redaction

- Strengthened `script/check_copy_hygiene.py` with an Android runtime-boundary guard.
- The guard now scans Android main source/resources and fails if direct Ollama or LM Studio endpoint material is introduced, including backend URL variables, `/api/tags`, `/api/chat`, `/api/pull`, `/api/v1`, `/v1/models`, or local model-server endpoint strings. The existing `LOCAL_MODEL_BACKEND_PORTS = setOf(11434, 1234)` blocklist remains the explicit allowed use of those ports.
- Added a last-mile Android UI sanitizer for runtime error details. Safe structured details still render, but details containing localhost model-provider endpoints, direct backend API paths, or `Ollama URL`/`LM Studio URL` wording are suppressed before display.
- Added unit coverage for the redaction behavior, including `http://127.0.0.1:11434/api/tags`, `localhost:1234/v1`, `LM Studio URL`, and `/api/chat`.
- A GPT-5.5 read-only explorer identified the display-layer redaction gap and was closed afterward. No GPT-5.3-Codex-Spark subagent was used.
- The Android phone is disconnected during this pass, so this is source/script/unit evidence only. It does not prove rendered on-device error cards or live runtime error behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailKeepsStructuredErrorDetails --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailRedactsBackendEndpointDetails -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt script/check_copy_hygiene.py`

## 2026-06-25 macOS Activity Log Redaction

- Added a CompanionCore log sanitizer before entries are stored in `CompanionAppModel.logs`.
- The sanitizer redacts local model-provider endpoints, direct provider API paths, and route/relay secret query material before Activity can render them.
- Added a second last-mile sanitizer in macOS Activity `Technical Details`, so raw diagnostics that still contain provider endpoint material render as the localized `Provider endpoint redacted.` message instead of exposing backend URLs or API paths.
- Expanded macOS Activity `Technical Details` redaction so raw route or relay secret material such as `relay_secret`, `route_secret`, `route_token`, compact `rs`, or compact `rt` renders as the localized `Sensitive technical detail redacted.` message.
- Expanded Android and macOS endpoint redaction beyond localhost defaults. Provider details now redact arbitrary `http(s)` URLs and any host using the model-provider ports `11434` or `1234`, while preserving non-provider connection route details such as `relay.example.test:43171`.
- Localized the redaction phrase across English, Korean, Japanese, Simplified Chinese, and French.
- Added focused Swift tests for both layers: CompanionCore log sanitization and LocalAgentBridge Activity technical-detail redaction.
- Strengthened `script/check_macos_localization.py` so it guards the Activity redaction source wiring, CompanionCore log sanitizer wiring, and the required localization key.
- A GPT-5.5 read-only explorer identified the macOS Activity log leak risk and was closed afterward. No GPT-5.3-Codex-Spark subagent was used.
- This is no-window/no-device validation only. It proves source, tests, localization, and build behavior, but not rendered Activity disclosure behavior in a running macOS window.

Verified after this change:

- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactProviderEndpoints|AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactRouteSecrets'`
- `swift build --target LocalAgentBridge`
- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- apps/macos/CompanionCore/Sources/CompanionAppModel.swift apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift apps/macos/LocalAgentBridgeApp/Sources/LogsView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ko.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ja.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/zh-Hans.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/fr.lproj/Localizable.strings script/check_macos_localization.py`

## 2026-06-25 Cross-Platform Endpoint Redaction Breadth

- Broadened Android visible error detail redaction so non-localhost provider URLs and host:provider-port strings are hidden as well as localhost defaults.
- Added Android unit coverage for `http://192.168.1.23:11434/api/tags` and `model-provider.example.test:1234/v1/models`.
- Added a `check_copy_hygiene.py` self-test for the Android runtime-boundary matcher, covering unsafe direct-provider endpoint samples and safe AetherLink route samples such as `relay.example.test:43171`.
- Broadened macOS Activity and CompanionCore log sanitizer coverage to match: arbitrary provider URLs, host:provider-port strings, direct provider API paths, and route/relay secrets are hidden before Activity can expose them.
- Kept non-provider connection route details visible when useful for troubleshooting, such as `relay.example.test:43171`.
- This remains source/unit/script evidence only; no running app window or physical device was used in this pass.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailRedactsBackendEndpointDetails -Pkotlin.incremental=false`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactProviderEndpoints|AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactRouteSecrets'`
- `python3 -m py_compile script/check_copy_hygiene.py script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- script/check_copy_hygiene.py`

## 2026-06-25 Android Embedding Model Install-State Guard

- Tightened `RuntimeClientViewModel.selectEmbeddingModel(...)` so the ViewModel only persists installed embedding models.
- This closes the UI-bypass path where an uninstalled embedding model could be stored even though the Compose Settings list disables that row.
- Added a ViewModel regression test that connects through the relay-backed fake runtime, receives a mixed chat/embedding model list, attempts to select an uninstalled embedding model, and verifies the previous installed embedding selection remains in both UI state and local storage.
- Kept model access behind AetherLink Runtime; no direct Ollama, LM Studio, or provider URL path was added.
- Used one GPT-5.5 read-only explorer to identify bounded no-device Android product gaps. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone is disconnected during this pass, so this is source/unit evidence only. It does not prove rendered on-device Settings behavior or physical haptics.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectEmbeddingModelRejectsUninstalledRuntimeModelWithoutChangingSelection -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest -Pkotlin.incremental=false`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt`

## 2026-06-25 Android Pairing Navigation Contract Guard

- Moved the post-pairing return-to-chat decision out of inline `MainActivity` `LaunchedEffect` branches into pure `AppNavigation` helpers.
- Removed the unused `pairingOnboardingCompleted` parameter from `resolveAppDestination(...)`. The persisted flag still records pairing completion, but destination routing now has one clear responsibility: untrusted installs start in Settings for pairing; trusted runtimes keep the user's chosen surface.
- Added unit coverage for the Chat return path after pairing succeeds, the pending-QR-route case that must remain in Settings, and manual Settings management that must not unexpectedly jump to Chat.
- Used one GPT-5.5 read-only explorer to audit the Android pairing/onboarding navigation flow. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone is disconnected during this pass, so this is source/unit evidence only. It does not prove physical QR scan, on-device navigation transitions, or rendered drawer behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/AppNavigation.kt apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`

## 2026-06-25 macOS Provider Status Redaction Guard

- Reused the Activity technical-detail sanitizer for the macOS Status > Model Providers technical-details disclosure.
- Provider status messages that contain provider URLs, provider ports, backend API paths, or route/relay secrets now render as the localized redaction text instead of exposing raw backend or route material.
- Safe structured provider fields remain visible in technical details as `code=...` and `retryable=true/false`, while unsafe diagnostic codes are redacted.
- Strengthened `script/check_macos_localization.py` so it guards the Status provider redaction helper wiring in addition to Activity log redaction.
- Used one GPT-5.5 read-only explorer to audit macOS runtime UI/localization gaps. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone is disconnected during this pass, so this is macOS source/unit/script evidence only. It does not prove rendered macOS disclosure behavior in a running window.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests`
- `swift build --target LocalAgentBridge`
- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift script/check_macos_localization.py`

## 2026-06-25 macOS Trusted Device Fingerprint Display

- Added a short SHA-256 public-key fingerprint to each trusted device row so similarly named paired devices are easier to distinguish before removal.
- Updated the destructive trust-removal confirmation to include both the device name and key fingerprint. If key material is missing, the UI uses the localized `Unavailable` value instead of showing a misleading empty-key hash.
- Localized the new trusted-device copy across English, Korean, Japanese, Simplified Chinese, and French.
- Added Swift regression coverage for fingerprint formatting, removal confirmation copy, and the fallback selected-device message.
- Strengthened `script/check_macos_localization.py` so the trusted-device identity display and new localization keys cannot silently regress.
- Used one GPT-5.5 read-only explorer to audit macOS trusted-device removal risk. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone is disconnected during this pass, so this is macOS source/unit/script evidence only. It does not prove rendered macOS trusted-device rows in a running window or physical QR trust removal behavior.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests`
- `swift build --target LocalAgentBridge`
- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/TrustedDevicesView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ko.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ja.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/zh-Hans.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/fr.lproj/Localizable.strings script/check_macos_localization.py docs/progress.md docs/qa-evidence.md`

## 2026-06-25 Android Route-Refresh QR Persistence

- Fixed the already-trusted runtime QR refresh path. A scanned QR for the same pinned runtime now saves the fresh relay route before attempting to reconnect, so a temporarily warming or unreachable relay no longer causes the new QR connection details to be discarded after one failed attempt.
- Updated the empty-chat QR recovery policy so `pairing_required` and `authentication_required` from a previously trusted runtime lead the user back to scanning the latest QR instead of presenting a generic reconnect action.
- Kept first-time pairing behavior unchanged: untrusted devices still send `pairing.request`, and Android still never talks directly to Ollama, LM Studio, or backend provider ports.
- Added a ViewModel regression test where the first relay connection attempt fails and the automatic trusted reconnect succeeds on the second attempt using the refreshed relay route.
- Added a UI policy regression test for the re-pairing-required empty chat action.
- Used one GPT-5.5 read-only explorer to audit QR pairing failure paths. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- Remaining QR follow-up: macOS QR generation can still produce no QR when remote route lease material is not ready. The next bounded macOS fix should make the Pairing UI clearly surface route allocation/readiness failure or provide a deliberately scoped static relay QR mode with expiration and nonce material.
- The Android phone is disconnected during this pass, so this is source/unit/script evidence only. It does not prove physical camera QR scan, on-device installation, or a real different-network relay path.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrPersistsRelayRouteBeforeReconnectRetry -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrPersistsRelayRouteBeforeReconnectRetry --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAddsRelayRouteToExistingTrustedRuntime -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.emptyChatPrefersQrRefreshWhenRuntimeRequiresPairingAgain --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrPersistsRelayRouteBeforeReconnectRetry -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt docs/progress.md docs/qa-evidence.md`

## 2026-06-25 Shared Private Overlay QR Fixture

- Added a shared compact QR fixture for private overlay relay routing at `shared/protocol/fixtures/macos-compact-private-overlay-pairing-uri.txt`.
- The fixture uses `rsc=private_overlay` with a CGNAT-style relay address so Android, macOS, and schema tooling all exercise the same different-network private-overlay QR contract.
- Extended the protocol schema checker to validate both the ordinary external relay fixture and the private overlay relay fixture.
- Added Android parser coverage that accepts the shared private overlay QR fixture only because the QR carries the explicit `private_overlay` scope.
- Added macOS pairing coverage that generates a compact private overlay QR payload matching the shared fixture.
- No GPT-5.3-Codex-Spark subagent was used. No new subagent was needed for this bounded source/test pass.
- The Android phone was disconnected during this pass, so this is source/unit/script evidence only. It does not prove physical camera QR scan, on-device pairing, or a live different-network relay route.

Verified after this change:

- `python3 script/check_protocol_schema.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests 'com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest'`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/run_allocation_relay.sh`
- `git diff --check`

## 2026-06-26 macOS Private Overlay Opt-In Guard

- Tightened macOS Advanced Connection Setup so private, CGNAT, and ULA relay literals are no longer treated as QR-ready remote routes by default.
- Added an explicit `Use Private Overlay Route` opt-in for GUI-configured private relay addresses. This is only for user-controlled VPN, tunnel, or private overlay routes that both paired devices can actually reach.
- Added environment opt-in support with `AETHERLINK_RELAY_ALLOW_PRIVATE_OVERLAY=1`, `AETHERLINK_BOOTSTRAP_RELAY_ALLOW_PRIVATE_OVERLAY=1`, or `AETHERLINK_ALLOW_PRIVATE_OVERLAY_RELAY=1` for development/bootstrap automation.
- Persisted the private-overlay opt-in alongside saved relay settings so rotating the route secret or restarting the companion does not silently change route scope.
- Updated macOS tests so private relay allocation is rejected by default and allowed only with explicit opt-in.
- Used one GPT-5.5 read-only explorer to audit cross-network QR blockers. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/script evidence only. It does not prove physical camera QR scan, on-device pairing, or a live different-network relay route.

Verified after this change:

- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelBlocksPrivateRelayHostWithoutExplicitOverlayOptIn|LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsPrivateOverlayRemoteRouteAllocationWithoutExplicitOptIn|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsPrivateOverlayRemoteRouteAllocationWithExplicitEnvironmentOptIn|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease|LocalRuntimeMessageRouterTests/testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode'`
- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `swift test --filter AetherLinkLocalizationTests`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/run_allocation_relay.sh`
- `git diff --check`

## 2026-06-26 Android Private Overlay Route UI Guard

- Fixed the Android connection UI helper so a saved QR relay route passes `relayScope` into the remote relay host eligibility check.
- Private, CGNAT, and ULA relay literals now become usable in the connection UI only when the trusted route carries the explicit `private_overlay` scope from QR pairing.
- Scope-less private relay literals remain unusable, which keeps accidental same-network private IP exposure from being treated as a valid different-network route.
- Added unit coverage for the connection action label, complete private-overlay relay material, scope-less private relay rejection, and the missing-secret warning path.
- A GPT-5.5 read-only explorer audited the existing Android reasoning UI. It confirmed the collapsed 3-line dim reasoning display and tests already exist. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/script evidence only. It does not prove physical camera QR scan, on-device pairing, or a live different-network relay route.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `./script/check_no_device_quality.sh`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`

## 2026-06-26 Runtime-Mediated Route Refresh Protocol Slice

- Added active `route.refresh` protocol documentation and JSON schema coverage for authenticated relay lease renewal.
- Added Swift and Kotlin protocol constants/payload models so both runtime and client protocol layers recognize `route.refresh`.
- Added a macOS runtime route refresh provider abstraction and wired `LocalRuntimeMessageRouter` to answer authenticated `route.refresh` requests with fresh relay host/id/secret/expiry/nonce material.
- Wired the macOS companion app model into the route refresh provider path by reusing the existing remote relay preparation and lease refresh logic.
- Added macOS router tests for successful route material refresh, retryable `route_refresh_unavailable`, and the authentication gate.
- Used two GPT-5.5 read-only explorers: one audited QR/different-network blockers and one audited UI/localization readiness. GPT-5.3-Codex-Spark was not used, and both explorers were closed after completion.
- Remaining route-refresh follow-up: Android still needs the ViewModel transport call and persistence path for `route.refresh`, plus scheduling before lease expiry. Until that is implemented, QR scan remains the fallback for expired route material.
- The Android phone was disconnected during this pass, so this is source/unit/schema evidence only. It does not prove physical camera QR scan, on-device route refresh, or a live different-network relay route.

Verified after this change:

- `swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshReturnsRetryableErrorWhenRuntimeHasNoRefreshableRoute|LocalRuntimeMessageRouterTests/testRouteRefreshRequiresAuthenticatedConnectionByDefault'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`
- `python3 script/check_protocol_schema.py`

## 2026-06-26 Android Route Refresh Integration

- Android now advertises `route.refresh` in client capabilities.
- After an authenticated trusted runtime session is established, Android sends `route.refresh` over the existing runtime channel.
- Successful `route.refresh` responses are validated with the same relay-route eligibility rules used for QR relay material, then persisted through `PairingStore.trustRuntime`.
- Invalid, expired, incomplete, or failed route-refresh responses do not overwrite trusted runtime identity or route material; `route_refresh_unavailable` remains a silent fallback path so the user can still scan a fresh QR.
- Added Android tests for route-refresh payload validation and the authenticated ViewModel path that sends `route.refresh` and stores fresh relay host/id/secret/expiry/nonce material.
- Used one GPT-5.5 read-only explorer to audit Android route-refresh integration points. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- Remaining route-refresh follow-up: schedule proactive refresh before relay expiry and validate it on a physical phone against a reachable different-network relay or overlay.
- The Android phone was disconnected during this pass, so this is source/unit/schema evidence only. It does not prove physical camera QR scan, on-device route refresh, or a live different-network relay route.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRefreshesRelayRouteMaterial -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`

## 2026-06-26 Android Proactive Route Refresh Scheduling

- Android now schedules a follow-up `route.refresh` before the trusted relay lease expires instead of waiting for the route to become stale.
- The scheduler only runs when the runtime session is authenticated, the channel is connected, and the trusted runtime has complete relay host/id/secret/expiry/nonce material.
- Successful `route.refresh` responses cancel the previous lease timer, persist the new relay material, and schedule the next refresh from the new expiry.
- Connection close, reconnect setup, receive failure, and authentication rejection cancel the lease timer so stale background refreshes do not fire against a closed channel.
- `route_refresh_unavailable` and send failures still remain silent fallback paths; the user can scan a fresh QR when no refreshable route is available.
- `RuntimeClientViewModel` now uses the injected clock dependency for route expiry calculations, which keeps this path testable.
- Added unit coverage for the renewal delay calculation and the authenticated ViewModel path that sends a second `route.refresh` before lease expiry.
- Used one GPT-5.5 read-only explorer to audit the safest Android scheduling points. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/schema evidence only. It does not prove physical camera QR scan, on-device route refresh, or a live different-network relay route.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshLeaseDelayUsesRenewalWindow --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRefreshesRelayRouteMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshLeaseDelayUsesRenewalWindow --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-26 Android Chat History Search Polish

- Added a search field to the Android Settings chat-history management panel so active and archived saved chats can be filtered before restore/archive/permanent-delete actions.
- The filter matches localized fallback titles, saved/generated titles, model ids, and runtime processing metadata such as last event, finish reason, or error code.
- Search changes only the visible list; bulk archive and permanent-delete actions still operate on the full active/archived sets and remain hidden behind Manage all chats plus the existing two-step confirmation.
- Reused the existing five-language chat-search resources instead of adding new copy.
- Added helper-level unit coverage for title, model-id, runtime-error metadata, untitled fallback, and blank-query behavior.
- Used one GPT-5.5 read-only explorer to audit the next Android UI completeness slices. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove rendered Settings layout, text entry behavior, haptics, or physical archive/delete flows.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatHistorySearchMatchesTitleModelAndRuntimeMetadata -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`

## 2026-06-26 Android Chat History Runtime Status Labels

- Android Settings chat-history rows now surface a compact runtime processing status using existing session metadata from AetherLink Runtime.
- `last_error_code` maps to a localized `Needs attention` status, cancellation finish reasons map to `Cancelled`, other finish reasons map to `Completed`, and active stream/request events map to `In progress`.
- The status is display-only and does not change runtime-owned storage, protocol messages, archive/delete semantics, or the client/runtime source-of-truth boundary.
- Added English, Korean, Japanese, Simplified Chinese, French, and default Android resources for the status labels.
- Added helper-level unit coverage for error-over-finish precedence, cancellation, failed finish, completed finish, in-progress event, error event, and empty metadata.
- Used one GPT-5.5 read-only explorer to verify the metadata was not already surfaced in Android UI. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove rendered Settings layout, text fit, haptics, or physical chat-history management flows.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatHistorySessionStatusSummarizesRuntimeProcessingMetadata -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`

## 2026-06-26 Android Settings Density Collapse

- Moved lower-priority Android Settings areas into collapsed-by-default expandable sections: Memory indexing model, Memory, and Chat history.
- Kept Pairing/Connection and Preferences immediately visible so first-launch pairing, connection state, language, and appearance stay above the denser management surfaces.
- Reused existing localized section labels and avoided nested header duplication by rendering the moved sections with `showHeader=false`; no new localized strings were added.
- Added unit coverage that keeps the lower-priority Settings sections collapsed by default.
- Used one GPT-5.5 read-only explorer to identify documentation insertion points. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove rendered Settings density, tap expansion behavior, ADB output, or screenshot state on a physical device.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsLowerPrioritySectionsStartCollapsed -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`

## 2026-06-26 Runtime Chat Title Locale Handoff

- Android `chat.send` payloads can now carry the effective runtime request locale, using the same supported-language normalization already used for explicit runtime title and suggested-question requests.
- The macOS runtime now preserves the optional `chat.send.locale` value and passes it into the automatic first-response title generation prompt after `chat.done`.
- This keeps automatic runtime-owned chat titles aligned with the explicit app language setting instead of falling back to conversation-only language detection.
- The locale stays at the runtime router/title-prompt layer; it is not added to low-level model backend request types and does not create any direct client-to-provider path.
- Added Android protocol coverage for `chat.send.locale` serialization and extended macOS automatic title generation coverage to assert the generated title prompt receives the locale hint.
- Used one GPT-5.5 read-only explorer to audit the current chat-title ownership and title-display paths. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/schema evidence only. It does not prove physical-device title rendering, QR pairing, or live model title generation from a real backend.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSendPayloadCanCarryRuntimeLocaleHint -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `swift test --filter LocalRuntimeMessageRouterTests`

## 2026-06-26 Android Thinking Preview Polish

- Tightened the Android assistant thinking/reasoning preview so collapsed long single-paragraph thinking text is capped by character count before expansion, not only by Compose line overflow.
- The collapsed policy still keeps thinking dimmed, limited to three visual lines, and expandable to the full text when there is more content.
- Updated the Android visible label copy from the more technical `Reasoning` wording to softer `Thinking` wording across English, Korean, Japanese, Simplified Chinese, French, and default resources.
- Added helper-level unit coverage that long single-paragraph thinking previews end in `...`, stay under the preview character cap, and remain single-line text before expansion.
- Used one GPT-5.5 read-only explorer to audit the current Android thinking UI implementation. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/resource evidence only. It does not prove physical-device rendering, expansion taps, haptic feel, or screenshot appearance.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.reasoningPreviewCapsLongSingleParagraphBeforeExpansion --tests com.localagentbridge.android.AppNavigationTest.reasoningDisplayPolicyKeepsCollapsedPreviewDimAndThreeLines --tests com.localagentbridge.android.AppNavigationTest.reasoningDisplayPolicyExpandsOnlyWhenExpandable -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`

## 2026-06-26 macOS Pairing-First and Runtime Copy Polish

- The macOS companion now defaults from Status to Pairing on first launch when there are no trusted devices, while preserving a restored non-status section and leaving Status selected when trusted devices already exist.
- Visible model-provider status copy now uses AetherLink Runtime wording instead of the internal `runtime host` phrase.
- Removed unused stale localization keys for old pairing and route-registration copy, then added those strings to the macOS localization hygiene denylist so they are caught if reintroduced.
- No new locale set was added; the existing English, Korean, Japanese, Simplified Chinese, and French macOS localization files stay aligned.
- Used one GPT-5.5 read-only explorer to audit macOS visible copy and localization gaps. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is macOS source/unit/localization evidence only. It does not prove physical QR pairing, Android rendering, or device reconnect behavior.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests/testCompanionFirstLaunchStartsWithPairingWhenNoTrustedDevicesExist`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`

## 2026-06-26 QR Pairing Route Audit and Runtime Copy Cleanup

- Audited the current QR pairing path from Android deep links/camera scan through pending pairing route setup, relay route preparation, pairing request send, accepted pairing persistence, and route refresh persistence.
- Confirmed relay QR trust material is already persisted after accepted pairing and route-refresh QR updates; the client stores relay host/port/id/secret/lease/nonce with the pinned runtime identity and avoids direct Ollama/LM Studio access.
- Confirmed local direct host/port QR hints are intentionally not restored as durable trusted reconnect addresses. Reintroducing direct host persistence was rejected because it would preserve the fixed-IP product shape the connection overlay is moving away from.
- Tightened pairing rejection and backend/provider error copy so user-visible failure details say `AetherLink Runtime` instead of the internal `runtime host` phrasing.
- Updated Android provider-status fixtures and macOS router/backend tests to cover the revised messages.
- Used one GPT-5.5 read-only explorer to audit QR/deeplink/route persistence gaps. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/build evidence only. It does not prove optical QR scan, different-network relay reachability, physical reconnect, or rendered error-copy behavior on device.

Verified after this change:

- `swift test --filter 'LocalRuntimeMessageRouterTests/testRepeatedInvalidPairingAttemptsInvalidateActiveSession|LocalRuntimeMessageRouterTests/testExpiredAndNoActivePairingRequestsReturnStructuredRejections'`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testRuntimeHealthUnavailableReturnsProtocolErrorWithoutBackendURL|LocalRuntimeMessageRouterTests/testRuntimeHealthIncludesAggregateProviderStatuses|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesStructuredBackendProviderStatuses|LocalRuntimeMessageRouterTests/testRepeatedInvalidPairingAttemptsInvalidateActiveSession|LocalRuntimeMessageRouterTests/testExpiredAndNoActivePairingRequestsReturnStructuredRejections'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderStatusesPreserveBackendDetails -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`

## 2026-06-26 Android Five-Language Default Cleanup

- Android Settings now exposes exactly five app languages: English, Korean, Japanese, Simplified Chinese, and French.
- Removed the visible `Device language` app-language option and its translated string resources; theme selection still keeps its separate `System` option for light/dark mode.
- Legacy blank/system stored language values now normalize to English, so existing installs do not silently switch the runtime request language to the device locale.
- Chat send, automatic title generation, and suggested-question requests all use the explicit normalized app language instead of the device locale.
- Added focused unit coverage for the five-language option order and English fallback for legacy language values.
- Used one GPT-5.5 read-only explorer to audit Android/macOS localization defaults. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/localization evidence only. It does not prove physical Settings rendering, persisted preference behavior on-device, or screenshot state.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsLanguageOptionsKeepCurrentLaunchLanguageSetAndOrder --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.appLanguageTagHelperNormalizesSupportedAndInvalidTags --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeUiState.kt apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt script/check_android_string_parity.py`

## 2026-06-26 Language And Connection Copy Hardening

- Removed the internal Android `RuntimeAppLanguage.System` enum member so app language support now models only the five visible languages. Legacy blank stored values are still accepted by normalization and fall back to English.
- Updated Android tests and documentation commands from legacy system-language naming to legacy blank-language naming.
- Tightened `script/check_android_string_parity.py` so the expected app-language enum is exactly English, Korean, Japanese, Simplified Chinese, and French.
- Replaced remaining macOS runtime connection error/log copy that said `Route host` or `development transport` with AetherLink Runtime / connection-address wording.
- Added a macOS router assertion for the neutral unknown-message copy and expanded copy hygiene so route-host/development-transport wording is caught if it returns to user-facing surfaces.
- Used one GPT-5.5 read-only explorer to audit stale language/default and connection copy. GPT-5.3-Codex-Spark was not used, and the explorer was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/localization evidence only. It does not prove physical Settings rendering, language persistence on-device, QR pairing, or live different-network connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsLanguageOptionsKeepCurrentLaunchLanguageSetAndOrder --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.appLanguageTagHelperNormalizesSupportedAndInvalidTags --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank -Pkotlin.incremental=false`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelBlocksInvalidRelayHostFormatForRemoteQRCode'`
- `swift test --filter AetherLinkLocalizationTests/testRemoteRoutePreparationIssueCopyIsActionableForRejectedRoute`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testUnknownMessageTypeReturnsProtocolError'`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_macos_localization.py`
- `swift build --target LocalAgentBridge`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeUiState.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift apps/macos/CompanionCore/Sources/CompanionAppModel.swift apps/macos/CompanionCore/Sources/RemoteRelayAllocationClient.swift apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift apps/macos/LocalAgentBridgeApp/Sources/LogsView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift script/check_android_string_parity.py script/check_copy_hygiene.py script/check_docs_hygiene.py docs/progress.md docs/qa-evidence.md`

## 2026-06-26 Android Attachment-Only Prompt Localization

- Localized the Android attachment-only chat prompt used when a user sends files or images without typed text.
- The generated chat content now follows the selected app language for English, Korean, Japanese, Simplified Chinese, and French; unsupported or legacy blank stored values still fall back to English.
- This keeps the visible user message and the runtime-mediated `chat.send` message body aligned with the selected app language without changing the rule that clients never call model-serving backends directly.
- Preserved attachment bullet formatting so document/image names remain visible in the message body.
- Used one GPT-5.5 worker to make the bounded Android runtime/test patch. GPT-5.3-Codex-Spark was not used.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical attachment sending, camera QR pairing, device rendering, or live runtime chat behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt docs/progress.md docs/qa-evidence.md`

## 2026-06-26 Documentation Contract Guard

- Expanded `script/check_docs_hygiene.py` beyond stale-wording checks with positive documentation-contract checks.
- The guard now fails if the current documentation set loses the product boundary that clients never call Ollama or LM Studio directly, QR-first pairing/route refresh depends on overlay or relay material rather than fixed IP reconnect, runtime-owned chat history is read through `chat.sessions.list` / `chat.messages.list`, the five-language launch set and runtime locale handoff remain visible, memory and embedding selection stay runtime-mediated and separate from chat model selection, or attachments stop being described as runtime-mediated.
- Kept `docs/progress.md` out of the historical stale-wording scan because it intentionally records superseded phrases, but included it in the positive product-contract scan so current implementation evidence helps protect the roadmap.
- Updated `docs/architecture.md` and `docs/roadmap.md` so attachment support is described as a current runtime-mediated path with remaining physical QA and future ingestion/indexing hardening, not only as a future idea.
- Used one GPT-5.5 read-only documentation audit subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so this is documentation/script evidence only. It does not prove physical QR pairing, attachment sending, device rendering, or different-network runtime connectivity.

Verified after this change:

- `python3 -m py_compile script/check_docs_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_protocol_schema.py`
- `git diff --check -- script/check_docs_hygiene.py docs/architecture.md docs/roadmap.md`

## 2026-06-26 Android Attachment Send-Path Contract

- Added Android ViewModel unit coverage for the attachment send path rather than changing production code.
- The tests prove attachment-only sends use the selected app language in the actual runtime-mediated `chat.send` payload.
- The tests prove document/image attachment metadata is attached only to the final user message sent to the runtime and is not duplicated onto prior context messages.
- The tests prove image attachments are blocked for a selected non-vision chat model and the pending attachment/input state is retained on that blocked path.
- The tests prove valid attachment sends clear pending attachments while the visible user message keeps read-only attachment chips.
- Used one GPT-5.5 worker for the bounded Android test patch. GPT-5.3-Codex-Spark was not used, and the worker was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical attachment picking, device rendering, real runtime chat, or camera QR pairing.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlySendUsesSelectedLanguagePromptInChatSendPayload --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentSendAttachesMetadataOnlyToFinalUserPayloadMessage --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.imageAttachmentSendRequiresVisionModelAndKeepsPendingAttachmentsWhenBlocked --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.validAttachmentSendClearsPendingAttachmentsAndRetainsReadonlyMessageChips -Pkotlin.incremental=false`

## 2026-06-26 Android Settings Persistence Contract

- Added Android ViewModel unit coverage for settings and model-selection restoration across ViewModel recreation.
- The tests prove persisted app language, appearance, chat model, embedding model, and trusted-runtime auto-reconnect preference are restored into `RuntimeUiState` on initialization.
- The tests prove public settings/model setter paths persist app language, appearance, auto-reconnect, chat model, and embedding model separately, then restore those same values after recreation.
- The test connectors fail if invoked, so this persistence path remains local UI state restoration and does not contact AetherLink Runtime, Ollama, LM Studio, or a device transport.
- Used one GPT-5.5 read-only persistence audit subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical app relaunch, Settings rendering, runtime reconnect, or on-device model-picker behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelRestoresPersistedLanguageThemeAndModelSelectionsOnInit --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelPersistsLanguageThemeAndRestoresThemAfterRecreation --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelPublicSettingsSettersPersistAcrossRecreation -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt docs/progress.md docs/qa-evidence.md`

## 2026-06-26 Model Picker Install Flow And Locale Protocol Contract

- Updated the Android chat top-bar model picker so idle uninstalled chat models stay selectable. Selecting one now reaches the existing `RuntimeClientViewModel.selectModel(...)` path, which requests installation through `models.pull` on AetherLink Runtime instead of requiring a hidden or separate install path.
- Kept the menu item disabled only while that model is already installing, and kept non-chat/embedding models out of the chat model picker.
- Added Android unit coverage for the new picker enablement contract.
- Made `chat.send.locale` an explicit protocol contract in `packages/protocol-schema/protocol.schema.json` and `docs/protocol.md`. This aligns the schema/docs with the already implemented Android serialization and runtime title/suggestion locale handoff path.
- Added a protocol schema guard requiring `chat.send`, `chat.suggestions.request`, and `chat.title.request` payload schemas to allow optional string `locale`.
- Clarified the protocol future-extension section so `route.refresh` is recognized as the current active route message while other `route.*` names remain reserved.
- Used two GPT-5.5 read-only audit subagents for Android UI and protocol/docs review. GPT-5.3-Codex-Spark was not used, and both subagents were closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/schema evidence only. It does not prove physical model-picker tapping, model installation through a live runtime, device rendering, or on-device locale behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuEnablesIdleChatModelsSoUninstalledModelsCanRequestInstall -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_protocol_schema.py`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt packages/protocol-schema/protocol.schema.json script/check_protocol_schema.py docs/protocol.md docs/progress.md docs/qa-evidence.md`

## 2026-06-26 Model Install Selection State

- Updated Android model installation selection so choosing an uninstalled chat model persists that install target as the selected model before sending `models.pull` to AetherLink Runtime.
- This keeps the top picker, composer send state, local persisted selection, and runtime install request aligned on the same model id instead of visually falling back to the previously installed model while another model is installing.
- The selected uninstalled model remains send-blocked with `SelectedModelSendState.NotInstalled` until the runtime reports it as installed in a later model refresh.
- Model installation remains runtime-mediated; the Android client does not call Ollama or LM Studio directly.
- Used GPT-5.5 read-only audit findings from the previous pass. GPT-5.3-Codex-Spark was not used.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical model-picker tapping, installation through a live runtime, device rendering, QR pairing, or different-network reconnect behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectUninstalledChatModelPersistsInstallTargetAndRequestsRuntimePull -Pkotlin.incremental=false`

## 2026-06-26 Embedding Model Installed-State Reconciliation

- Tightened Android model reconciliation so a persisted embedding model is cleared when the refreshed runtime model list reports that embedding model as not installed.
- Kept the chat model behavior separate: uninstalled chat models can still be selected as install targets because that path sends `models.pull` through AetherLink Runtime, while embedding models currently have no chat-composer install flow.
- This prevents Settings from showing a stale embedding selection as usable after the serving runtime reports it is unavailable.
- The Android client still treats embedding selection as UI/runtime metadata only; it does not call Ollama or LM Studio directly.
- Used GPT-5.5-only delegation policy for this pass. GPT-5.3-Codex-Spark was not used.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical Settings rendering, live runtime model refresh, QR pairing, or different-network reconnect behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsEmbeddingSelectionWhenModelIsNotInstalled -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsMissingPersistedSelectionsTypedAcrossRefresh --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsPersistedSelectionsWhileModelListIsRestoring --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsSelectionsWhenRefreshedModelHasWrongKind --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsEmbeddingSelectionWhenModelIsNotInstalled --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationOnlyAutoSelectsChatWhenSelectionIsEmpty --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsExplicitEmbeddingSelection --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationSelectsInstalledChatTargetAfterRefresh -Pkotlin.incremental=false`

## 2026-06-26 Sticky Chat Auto-Scroll

- Replaced unconditional Android chat auto-scroll on every streamed content/reasoning delta with a bottom-stickiness policy.
- The chat now auto-scrolls on initial layout, when a new message is added, or when the user is already near the latest message. If the user has scrolled up to read earlier context or collapsed reasoning while streaming continues, token deltas no longer force the list back to the bottom.
- Added a pure `shouldAutoScrollChat(...)` helper and JVM tests for near-bottom following, scrolled-up streaming deltas, initial layout, new-message jumps, and empty-list behavior.
- This moves the Android chat surface closer to ChatGPT-like behavior without changing the runtime protocol or backend access boundary.
- Used one GPT-5.5 read-only Android UI audit subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical scrolling behavior, rendered chat polish, QR pairing, or live streaming on a device.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollFollowsStreamingWhenAlreadyNearLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForStreamingDeltas --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollKeepsInitialAndNewMessageJumpBehavior -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-26 Jump To Latest And Menu-Bar QR Routing

- Added an Android chat "jump to latest" affordance that appears only when the message list has visible content and the user is scrolled away from the latest message.
- The button uses a localized accessibility label in the initial five Android languages and returns to the newest message with haptic feedback.
- Kept the sticky-scroll behavior: streamed deltas do not drag the user down while they read earlier content, but users now have an explicit path back to the live answer.
- Fixed the macOS menu-bar `Generate Pairing QR` action so it opens the main AetherLink window, activates the app, and routes `ContentView` to the Pairing section after generating the QR.
- Added a pure companion-section routing helper and macOS test coverage so external pairing requests override the current sidebar section.
- Used one GPT-5.5 read-only macOS UI audit subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit/localization evidence only. It does not prove physical scrolling behavior, optical QR scanning, rendered macOS window focus, or live pairing.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.jumpToLatestChatButtonShowsOnlyWhenScrolledAwayFromLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollFollowsStreamingWhenAlreadyNearLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForStreamingDeltas --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollKeepsInitialAndNewMessageJumpBehavior -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `swift test --filter AetherLinkLocalizationTests/testExternalPairingRequestOverridesCurrentCompanionSection`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-26 Broader Android Document Picker Coverage

- Expanded the Android document picker MIME allowlist to match more of the runtime attachment classifier.
- Added Office macro/template variants, HWPX fallback MIME, iWork documents, WebArchive, and Markdown so users can choose more document-like files beyond PDF, DOCX, and HWPX.
- Kept image selection gated by the currently selected vision-capable chat model; non-vision chat models still receive document MIME types only.
- Added Android UI policy coverage proving the document picker exposes the broadened document set while adding `image/*` only for vision-capable models.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove the platform file picker rendering, actual file read permissions, runtime ingestion success, or live model response quality for those documents.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerUsesDocumentTypesWhenSelectedModelIsNotVisionCapable --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerIncludesImageTypesWhenSelectedModelIsVisionCapable -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`

## 2026-06-26 Structured Text Attachment Coverage

- Extended the Android document picker allowlist with structured text MIME aliases that the runtime already classifies as extractable plain text: JSONL/NDJSON, YAML, TOML, CSV, TSV, reStructuredText, AsciiDoc, and log-style text.
- Added macOS `DocumentIngestion` coverage proving JSONL, YAML, TOML, CSV, TSV, INI, and properties files extract through the runtime-side document ingestion path as normalized text.
- This keeps the client file picker and runtime ingestion boundary aligned for document-like inputs beyond PDF/DOCX/HWPX while preserving the rule that the device does not parse model-provider data directly.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical file picker rendering, SAF MIME filtering on-device, real file read permissions, or live runtime/model answer quality for those attachments.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerUsesDocumentTypesWhenSelectedModelIsNotVisionCapable --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerIncludesImageTypesWhenSelectedModelIsVisionCapable -Pkotlin.incremental=false`
- `swift test --filter DocumentTextExtractorTests/testExtractsStructuredPlainTextDocumentFamily`
- `python3 script/check_android_string_parity.py`

## 2026-06-26 MIME-Only Structured Text Attachment Ingestion

- Added runtime-side support for structured text MIME aliases that may arrive without reliable filename extensions from a mobile document picker: `application/jsonl`, `application/x-yaml`, `application/toml`, and `application/x-toml`.
- Added `DocumentIngestion` coverage proving extensionless JSONL/YAML/TOML attachments are treated as normalized text when the MIME type carries the document identity.
- Added `LocalRuntimeMessageRouter` coverage proving an extensionless TOML attachment named `config` is extracted, appended into the runtime-mediated `chat.send` prompt, and forwarded to the backend as a text document attachment.
- This closes the picker/runtime mismatch where the client could expose structured text files but the runtime could reject them if Android supplied a generic or extensionless display name.
- The model access boundary is unchanged: attachments are decoded and normalized by AetherLink Runtime, and the Android client still never calls Ollama, LM Studio, or future serving providers directly.
- The Android phone was disconnected during this pass, so this is source/unit/schema evidence only. It does not prove physical file-picker MIME behavior, real SAF display names, live attachment upload, QR pairing, different-network reconnect, or model answer quality.

Verified after this change:

- `swift test --filter DocumentTextExtractorTests/testExtractsStructuredPlainTextDocumentsFromMimeOnlyAttachments`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment`
- `swift test --filter DocumentTextExtractorTests`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-26 Android Route Refresh Retry

- Hardened the trusted-runtime reconnect path for QR-provisioned relay routes. When an authenticated `route.refresh` request fails with a retryable runtime error, the Android client now keeps the current route and schedules another refresh attempt while the existing relay lease is still active.
- Added a bounded retry delay helper so refresh retries stay inside the active lease window instead of firing after the QR-provisioned route has already expired.
- Preserved the stricter security behavior for authentication/pairing-required errors: those still clear the authenticated session path rather than silently retrying runtime commands.
- This makes app re-entry and longer-running different-network sessions less brittle without changing the model-access boundary. The client still talks only to AetherLink Runtime and never directly to Ollama, LM Studio, or future serving providers.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical app relaunch, camera QR pairing, real relay reachability, or different-network reconnect on a device.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshRetryDelayStaysInsideActiveLease --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRouteRefreshErrorBeforeLeaseExpiry -Pkotlin.incremental=false`

## 2026-06-26 Android QR-Only Default Settings Entry

- Changed the Android app entry path so developer route diagnostics are hidden by default even in debug APKs. The normal Settings UI now stays QR-first and does not expose manual host/port entry unless the app is launched with an explicit developer diagnostics extra.
- Kept the existing developer diagnostics panel available for scripted/local troubleshooting through an explicit debug-only launch request, but removed it from the default user-facing flow.
- Added a pure navigation test proving developer diagnostics require both a debug build and an explicit launch request.
- This better matches the product rule that users should pair or refresh routes by scanning QR, not by entering fixed endpoints or backend URLs.
- The Android phone was disconnected during this pass, so this is source/unit/build evidence only. It does not prove physical Settings rendering, real QR scan behavior, or on-device absence of the diagnostics section.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.developerDiagnosticsRequireDebugBuildAndExplicitLaunchRequest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_android_string_parity.py`

## 2026-06-26 macOS Pairing-First Runtime Onboarding

- Tightened the macOS runtime host onboarding section selection so an unpaired runtime opens on Pairing even if SceneStorage preserved a previous sidebar section such as Activity or Trusted Devices.
- Added section-change handling so when the last trusted device is removed, the runtime host returns to Pairing instead of leaving the user on an empty management surface.
- Kept explicit external section requests, such as the menu-bar "Generate Pairing QR" path, higher priority than automatic onboarding selection.
- This aligns the runtime host with the QR-first product flow: if no trusted client exists, the primary action is generating/scanning a pairing QR.
- The Android phone was disconnected during this pass, so this is macOS source/unit/localization evidence only. It does not prove rendered window navigation, optical QR pairing, or physical reconnect behavior.

Verified after this change:

- `swift test --filter 'AetherLinkLocalizationTests/testCompanionFirstLaunchStartsWithPairingWhenNoTrustedDevicesExist|AetherLinkLocalizationTests/testTrustedDeviceCountChangeReturnsUnpairedRuntimeToPairing|AetherLinkLocalizationTests/testExternalPairingRequestOverridesCurrentCompanionSection'`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-26 macOS QR Route Readiness and Diagnostic Redaction

- Hardened the macOS Advanced Connection technical-details disclosure so route secrets, route tokens, compact QR route aliases, and model-provider endpoints are redacted before display.
- Added coverage proving safe relay endpoints can still appear in diagnostics while `relay_secret`, `route_token`, compact `rs`/`rt`, and provider URLs are replaced with localized redaction text.
- Tightened Pairing screen behavior so the remote QR generation button is enabled only when AetherLink can automatically prepare connection details or a saved connection route is eligible for QR inclusion.
- Updated Pairing empty-state copy to say that different-network pairing needs connection details inside the QR instead of implying a QR can always be generated locally.
- Expanded macOS route-preparation localization tests and the localization parity guard so all major route-preparation failure states stay covered in the initial five languages.
- The Android phone was disconnected during this pass, so this is macOS source/unit/localization evidence only. It does not prove optical QR scanning, a rendered button state, live relay reachability, or physical different-network pairing.

Verified after this change:

- `swift test --filter 'AetherLinkLocalizationTests/testPairingQRGenerationRequiresAutomaticPreparationOrEligibleRoute|AetherLinkLocalizationTests/testRouteDiagnosticDisclosureRedactsSensitiveDetails|AetherLinkLocalizationTests/testRemoteRoutePreparationIssueCopyCoversRoutePreparationFailures'`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`

## 2026-06-26 No-Device Relay QR Evidence Split

- Re-ran the headless development relay smoke with `./script/runtime_authenticated_mock_smoke.swift --relay`. This proves RuntimeDevServer can allocate relay route material, emit a route-bearing pairing URI, pair and authenticate over the relay, answer `runtime.health`, list/pull mock models, stream chat, cancel generation, and reconnect through the saved trusted relay route.
- Re-ran the no-ADB QR artifact smoke in local relay emit-only mode. This proves QR URI generation, QR PNG rendering, QR decode, and route-material validation. Because the relay host was loopback and the phone was disconnected, it does not prove optical QR scan, physical-device pairing, or different-network reachability.
- Updated `script/no_adb_external_relay_pairing_smoke.sh` so local relay emit-only runs explicitly print that they are artifact/diagnostic proof only, not evidence of a real external relay route.
- Updated Android pending QR-route hero copy to use the longer route-detail text, so an identity-only or incomplete route state points the user back to the latest QR with connection details for different-network use.
- The Android phone was disconnected during this pass, so this is source/unit/script evidence only. It does not prove physical camera QR scan, on-device pairing completion, live different-network relay reachability, or rendered Android copy on the phone.

Verified after this change:

- `./script/runtime_authenticated_mock_smoke.swift --relay`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 43172 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-emit-check-2 --timeout 30`
- `bash -n script/no_adb_external_relay_pairing_smoke.sh`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pendingQrRouteHeroExplainsThatLatestQrNeedsConnectionDetails -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`

## 2026-06-26 Android Trusted-Route Re-Entry State

- Tightened Android trusted runtime restore so enabling or restoring a saved relay-backed trusted runtime starts the reconnect coroutine undispatched. This makes the UI move to `connecting` synchronously instead of briefly rendering as disconnected while relay dialing is still suspended.
- Added a no-device regression test with a suspended relay connector and direct TCP forbidden, proving the saved trusted runtime route takes the relay path and immediately exposes `connecting`.
- This improves app re-entry polish for previously paired devices without changing the product boundary: the device app still connects only to AetherLink Runtime and never directly to Ollama or LM Studio.
- This work used one GPT-5.5 Android worker subagent. GPT-5.3-Codex-Spark was not used.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical app relaunch, camera QR pairing, real relay reachability, or different-network reconnect on a device.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayRestoreMarksConnectingBeforeRelayDialCompletes`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest`

## 2026-06-26 Android Floating Chat Composer Polish

- Refined the Android chat composer container from a docked tray into a cleaner floating composer surface: all corners now use a 28dp radius, the top divider was removed, and the surface uses a slightly more opaque container with subtle elevation.
- Kept the requested no-placeholder behavior intact. The input still uses an accessibility label for screen readers, but the composer does not display generic prompt text such as "Ask anything" or "What can I help with?".
- Added no-device regression coverage for the composer visual policy constants alongside the existing accessibility/no-placeholder assertion.
- Used one GPT-5.5 read-only UI audit subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove rendered device screenshots, touch ergonomics, IME overlap, or physical haptics.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatComposerKeepsAccessibilityLabelWithoutVisualPlaceholder -Pkotlin.incremental=false`
- `./script/check_no_device_quality.sh`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt docs/progress.md docs/qa-evidence.md`

## 2026-06-26 Android Chat-History Stale Danger Copy Cleanup

- Removed unused Android string resources that could reintroduce the old one-step archive/delete/clear behavior: `archive_all_chats_confirm`, `delete_all_chats`, `delete_all_chats_confirm`, `delete_chat_confirm`, `clear_chat_history`, and `clear_chat_history_confirm`.
- Kept the current archive/permanent-delete language intact across English, Korean, Japanese, Simplified Chinese, and French: archive all remains a separate action, permanent deletion is labeled as permanent, and permanent deletion is described as available only for archived chats.
- Added those stale keys to `script/check_android_string_parity.py` as forbidden names so future UI or localization changes cannot silently bring back the old one-step archive/delete/clear copy.
- This supports the requested history model: archive and delete are distinct, dangerous bulk operations stay hidden and double-confirmed, archived chats stay excluded from Memory, and permanent delete is archive-only.
- Used one GPT-5.5 read-only verification subagent. GPT-5.3-Codex-Spark was not used.
- The Android phone was disconnected during this pass, so this is source/script evidence only. It does not prove rendered Settings behavior, tap flow, dialog copy on-device, or haptics.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `rg -n 'name="archive_all_chats_confirm"|name="delete_all_chats"|name="delete_all_chats_confirm"|name="delete_chat_confirm"|name="clear_chat_history"|name="clear_chat_history_confirm"' apps/android/app/src/main/res`
- `./script/check_no_device_quality.sh`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml script/check_android_string_parity.py docs/progress.md docs/qa-evidence.md`

## 2026-06-26 No-Device Quality Gate Script

- Added `script/check_no_device_quality.sh` as the default local QA entry point when no Android phone is connected.
- The script compiles the static guard scripts, validates Android/macOS localization, protocol schema, copy hygiene, docs hygiene, Apache 2.0 license wording, app icon assets, targeted Android navigation tests, the macOS app product, and focused macOS localization/document extraction tests.
- Included the Android trusted-route re-entry regression test so a saved relay-backed runtime restore must show `connecting` synchronously instead of briefly presenting a disconnected state while relay dialing is still suspended.
- Expanded the gate to include focused runtime-host tests for runtime-owned chat event storage, authenticated history readback, reasoning/think streaming separation, and inline `<think>` splitting. This keeps two user-facing requirements from drifting while physical Android validation is unavailable: chat processing state is stored on the runtime host, and reasoning is not mixed into the assistant answer body.
- Kept physical-device and live-network work out of the script: APK install, camera QR pairing, haptic feel, launcher/Dock screenshots, live streamed chat/cancel, and different-network runtime connectivity still need explicit device evidence.
- Updated README verification guidance so the no-device script is the first command to run before handoff, with deeper relay and full Swift smokes left as separate dependency-aware checks.

Verified after this change:

- `./script/check_no_device_quality.sh`

## 2026-06-26 Android Attachment Composer Guardrails

- Extracted the Android chat composer send policy into pure helper functions so no-device tests can verify the UI-facing rules without a physical device or rendered Compose tree.
- Added AppNavigation coverage proving attachment-only sends are enabled when the runtime is connected and the selected chat model is installed, image attachments block send until a vision-capable chat model is selected, and attachment sends still require an installed chat model plus actual sendable content.
- Added RuntimeClientViewModel coverage proving pending attachment removal drops only the selected chip and clears stale attachment errors, while blank input with no attachments does not send `chat.send`.
- Added the new ViewModel attachment removal and blank-send guards to `script/check_no_device_quality.sh`; the new AppNavigation helper tests are covered by the script's existing full `AppNavigationTest` selection.
- Left actual `OpenMultipleDocuments` URI loading, SAF picker rendering, file-read permissions, and max-selection UX for future physical/instrumented validation because the current JVM unit setup does not exercise Android's real content resolver.
- Used one GPT-5.5 read-only UI audit subagent. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical file picking, attachment chip rendering on-device, touch behavior, or live model answers with attached files.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatComposerAllowsAttachmentOnlySendWhenConnectedModelIsUsable --tests com.localagentbridge.android.AppNavigationTest.chatComposerBlocksImageAttachmentUntilSelectedModelSupportsVision --tests com.localagentbridge.android.AppNavigationTest.chatComposerRequiresInstalledChatModelForAttachmentSends --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.removePendingAttachmentDropsOnlySelectedAttachmentAndClearsError --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.blankMessageWithoutAttachmentsDoesNotSend -Pkotlin.incremental=false`

## 2026-06-26 Android Attachment Loading Test Seam

- Added a small `RuntimeAttachmentReader` seam behind Android `addAttachments`, keeping the public UI path unchanged while making metadata, byte loading, size checks, and Base64 conversion testable without Android's real `ContentResolver`.
- Switched attachment Base64 conversion from Android's framework `Base64` helper to `java.util.Base64`, avoiding JVM unit-test mock behavior while preserving normal no-wrap Base64 payloads on supported Android API levels.
- Added no-device ViewModel coverage proving document and image references become pending attachments with inferred document/image types and Base64 payloads, oversized metadata stops before file bytes are read, and a multi-select result loads at most four pending attachments.
- Improved the over-limit attachment flow so extra selected files are no longer silently ignored. The ViewModel now reads only the remaining available slots, keeps the successfully loaded attachments, and exposes a localized `attachment_limit_reached` error when the user selects more than the current 4-file limit allows.
- Added the attachment-limit message to Android English, Korean, Japanese, Simplified Chinese, and French resources.
- Added the new attachment-loading tests to `script/check_no_device_quality.sh`.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove platform SAF picker rendering, actual content URI permissions, physical file selection, or live model quality for attached files.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsStopsBeforeReadingReportedOversizeFile --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsKeepsAtMostFourPendingAttachments -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsStopsBeforeReadingReportedOversizeFile --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsKeepsAtMostFourPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsWithExistingPendingAttachmentsReadsOnlyRemainingSlotsAndShowsLimit -Pkotlin.incremental=false`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- script/check_no_device_quality.sh README.md docs/progress.md docs/qa-evidence.md`

## 2026-06-26 Android Empty Chat Model Selection State

- Updated the Android empty chat decision so a connected runtime with no usable selected chat model now shows the existing localized model-selection empty state instead of leaving the center surface visually blank.
- Kept the ready-to-type state unchanged: when the runtime is connected and an installed chat model is selected, the central empty-state prompt remains hidden so the composer stays the primary surface.
- Added AppNavigation coverage for connected/no selected model, selected model missing from the runtime list, selected model not installed, and an embedding model accidentally selected as the chat model.
- Used two GPT-5.5 read-only subagents for audits. GPT-5.3-Codex-Spark was not used, and both subagents were closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove rendered device layout, physical pairing, or touch behavior.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `./script/check_no_device_quality.sh`

## 2026-06-26 macOS Route Refresh Lease Guardrails

- Added CompanionAppModel regression coverage for runtime route refresh material used by paired clients when connection details need renewal.
- Proved `refreshRuntimeRoute()` returns no relay material when a saved relay endpoint has no fresh lease/nonce and lease refresh fails, instead of exposing incomplete connection details to the client.
- Proved `refreshRuntimeRoute()` can allocate a fresh relay lease from the configured route service and returns only complete relay material: host, port, relay id, relay secret, lease expiration, and nonce.
- Added these focused Swift tests to `script/check_no_device_quality.sh` so the no-device gate keeps QR/route-refresh readiness from drifting while physical QR scanning is unavailable.
- Used one GPT-5.5 read-only subagent for the macOS QR readiness audit. GPT-5.3-Codex-Spark was not used, and the subagent was closed after completion.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove optical QR scanning, physical reconnect, or real different-network relay reachability.

Verified after this change:

- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial'`
- `./script/check_no_device_quality.sh`

## 2026-06-26 macOS Connection Recovery Redaction

- Hardened macOS connection-recovery copy so a route issue endpoint is displayed only when it passes the same technical-diagnostic sanitizer used by logs and disclosure panels.
- Sensitive values accidentally passed as an endpoint, such as `relay_secret` or `route_token`, now fall back to the generic localized recovery message instead of appearing inside formatted user copy.
- Added Korean selected-language coverage proving the recovery message and route diagnostic redaction both use the selected app language while hiding sensitive route material.
- The Android phone was disconnected during this pass, so this is source/unit/localization evidence only. It does not prove rendered macOS window layout, physical QR scanning, or real relay reachability.

Verified after this change:

- `swift test --filter AetherLinkLocalizationTests/testRemoteRoutePreparationIssueCopyUsesSelectedLocalizationAndRedactsSensitiveEndpoint`
- `python3 script/check_macos_localization.py`
- `swift test --filter AetherLinkLocalizationTests`
- `./script/check_no_device_quality.sh`

## 2026-06-26 Android Model Picker Selection Pinning

- Improved the Android chat-bar model menu so the currently selected chat model stays visible at the top even while a search query matches a different model.
- Applied the same behavior to the embedded Memory indexing model picker, keeping the selected embedding model pinned while searching other embedding models.
- This keeps model selection visibly stable when the user returns to the picker after reconnect/model refresh flows, and avoids making the selection look lost just because the current search text filters it out.
- Restored the intended runtime-mediated install path for uninstalled local chat models. The chat model menu now shows runtime-local chat models even when they are not installed, keeps cloud/provider-managed entries hidden, and lets selection reach `RuntimeClientViewModel.selectModel(...)` so `models.pull` goes through AetherLink Runtime.
- Kept embedding model behavior stricter: uninstalled embedding models remain unavailable because the current embedding selection path has no install action.
- Updated the Android copy-hygiene guard so it protects the new menu contract and no longer assumes only already-installed chat models are searchable.
- Added Android navigation/helper coverage for selected chat-model and selected embedding-model pinning during search.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove rendered dropdown layout, touch behavior, haptic feel, or physical model switching on device.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuKeepsSelectedModelVisibleDuringSearch --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuKeepsSelectedModelVisibleDuringSearch -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuEnablesLocalChatModelsSoUninstalledModelsCanRequestInstall --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuShowsLocalChatModelsAndPrioritizesRunningThenInstalled --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuKeepsSelectedModelVisibleDuringSearch --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuKeepsSelectedModelVisibleDuringSearch -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `./script/check_no_device_quality.sh`

## 2026-06-26 README Connection Setup Copy

- Updated README different-network development setup text from stale `Remote Route Diagnostics` / route-host wording to the current `Advanced Connection Setup` / `Connection Setup` / connection-address terminology.
- Added docs-hygiene rules so those stale handoff terms fail current documentation checks if they return to release-facing docs.
- The Android phone was disconnected during this pass, so this is documentation/script evidence only. It does not prove rendered runtime window layout, physical QR scan, or real different-network relay reachability.

Verified after this change:

- `python3 -m py_compile script/check_docs_hygiene.py script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`

## 2026-06-26 Validation Script Usability

- Clarified the Android string parity success output so no-device logs now show the checked module resource set count, five locale count, and localized `strings.xml` file count instead of only `1 resource set(s)`.
- Verified the shebang-based guard scripts for docs hygiene, license declaration, and app icon assets can be run directly from the shell.
- Expanded docs hygiene beyond root docs to include Android, runtime-host, and examples READMEs so stale platform-specific wording such as `companion runtime` cannot survive in app-level documentation while the main docs pass.
- Added the Android core protocol unit tests to `script/check_no_device_quality.sh`, covering protocol payload contracts that sit below app-level ViewModel tests.
- Pinned Android `assistant_reasoning_label`, `assistant_reasoning_show`, and `assistant_reasoning_hide` release copy across English, Korean, Japanese, Simplified Chinese, and French in the string parity guard.
- Extended protocol schema validation so `packages/protocol-schema/protocol.schema.json` now guards the Android `MessageType` constants and Swift `MessageType` constants against missing or extra message names.
- Pinned the Gradle wrapper distribution with the official Gradle 9.4.1 SHA-256 checksum so local no-device validation does not depend only on wrapper URL validation.
- This makes multilingual/localization evidence easier to read in QA logs and keeps the local validation scripts usable outside the aggregate no-device wrapper.
- The Android phone was disconnected during this pass, so this is tooling/script evidence only. It does not prove rendered localized UI or on-device language switching.

Verified after this change:

- `./script/check_android_string_parity.py`
- `./script/check_docs_hygiene.py`
- `./script/check_license.py`
- `./script/check_app_icons.py`
- `python3 -m py_compile script/check_protocol_schema.py`
- `python3 script/check_protocol_schema.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest -Pkotlin.incremental=false`
- `swift test --filter ProtocolCodecTests`
- `curl -fsSL https://services.gradle.org/distributions/gradle-9.4.1-bin.zip.sha256`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --version --no-daemon`
- `bash -n script/check_no_device_quality.sh`
- `python3 -m py_compile script/check_android_string_parity.py script/check_docs_hygiene.py`
- `./script/check_no_device_quality.sh`

## 2026-06-26 No-Device Model Picker And QR Artifact Gate

- Tightened the Android chat top-bar closed model label so it uses the same runtime-host-local chat model policy as the dropdown list. If a provider-managed/non-local chat model appears in a refreshed model list with the saved selected id, the closed picker no longer displays that provider-managed model name as if it were selectable.
- Updated the Android drawer runtime summary to use the same local chat model policy, keeping sidebar model state aligned with the chat top-bar picker.
- Added a regression test for provider-managed chat models in the closed picker state and extended copy/UX hygiene so this policy cannot silently drift away from the visible model menu.
- Added the no-ADB pairing QR artifact smoke to `script/check_no_device_quality.sh`. The aggregate no-device gate now starts a local allocation relay on a temporary port, runs RuntimeDevServer in emit-only mode, generates a pairing QR PNG, decodes the QR image, and validates complete relay-route payload material with no direct endpoint fallback.
- The QR smoke uses local relay diagnostics only. It proves QR artifact generation and payload integrity, not optical camera scanning or true different-network reachability.
- The Android phone was disconnected during this pass, so this is source/unit/script evidence only. It does not prove rendered model picker layout, physical touch behavior, haptics, camera QR scan, physical pairing, or real external-network runtime connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelPickerClosedLabelIgnoresProviderManagedChatModel --tests com.localagentbridge.android.AppNavigationTest.chatModelPickerClosedLabelUsesRuntimeModelNameWhenAvailable --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuShowsLocalChatModelsAndPrioritizesRunningThenInstalled -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port <free-port> --start-local-relay --emit-only --timeout 30 --work-dir <tmp>`
- `script/verify_pairing_qr.swift --image <tmp>/pairing-qr.png --expected <tmp>/pairing-uri.txt --require-relay-route --expected-relay-host 127.0.0.1 --expected-relay-port <free-port> --forbid-direct-endpoint --allow-local-relay`
- `bash -n script/check_no_device_quality.sh`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt script/check_copy_hygiene.py script/check_no_device_quality.sh`
- `./script/check_no_device_quality.sh`

## 2026-06-26 No-Device macOS Render Smoke

- Added `AetherLinkRenderSmokeTests`, the first no-device UI render smoke for the macOS runtime app.
- The test renders the real `ContentView` shell through `NSHostingView` at the app minimum window size `860x560` across English, Korean, Japanese, Simplified Chinese, and French in light and dark appearances.
- The test also renders the primary companion detail surfaces at minimum detail size: Status, Pairing, Trusted Devices, and Activity. The smoke asserts non-empty bitmap output and sampled color diversity so blank or failed SwiftUI rendering is caught without a screenshot dependency.
- The render smoke uses isolated `UserDefaults`, an empty test environment, and a fixed route-host provider so external relay environment variables and user preferences do not affect the result.
- Added `swift test --filter AetherLinkRenderSmokeTests` to `script/check_no_device_quality.sh`, so macOS UI renderability is now part of the aggregate no-device gate.
- Android still does not have true no-device Compose render coverage; current Android confidence remains JVM helper/unit tests, resource parity, copy hygiene, and physical-device testing when a phone is connected.
- The Android phone was disconnected during this pass, so this is macOS no-device render evidence only. It does not prove Android rendered UI, physical QR scan, haptic feel, or real external-network runtime connectivity.

Verified after this change:

- `swift test --filter AetherLinkRenderSmokeTests`
- `python3 script/check_macos_localization.py`
- `bash -n script/check_no_device_quality.sh`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Tests/AetherLinkRenderSmokeTests.swift script/check_no_device_quality.sh`

## 2026-06-26 No-Device QR Pairing Gate Expansion

- Expanded `script/check_no_device_quality.sh` so it now runs the Android QR parser contract tests before app-level runtime tests.
- Added focused app-level QR relay regressions to the default no-device gate: compact relay QR pairing acceptance, shared macOS compact QR fixture parsing, relay-backed `pairing.request` routing, pending relay route persistence after the first connection failure, and pending relay route restoration after ViewModel recreation.
- Added a ViewModel scan-path regression for the macOS-generated private-overlay compact QR fixture, proving a `private_overlay` relay route such as CGNAT/private-overlay material reaches the relay connector and sends `pairing.request` without direct TCP fallback.
- Added the macOS compact QR fixture generation tests to the same no-device gate, so public relay and private-overlay QR fixtures are checked from Swift generation through shared fixture contracts and Android parsing/routing coverage.
- Added archive/permanent-delete regressions to the same no-device gate. Android now checks that active sessions cannot be permanently deleted, archive-all keeps sessions archived while excluding them from Memory/Reflection/Research candidates, permanent delete removes only archived sessions and suppresses runtime-owned deleted sessions, and archived runtime-owned message bodies stay redacted from device storage; macOS now checks runtime-store archive/restore/delete lifecycle and rejects active-session delete at the protocol router.
- Added runtime-owned memory regressions to the same no-device gate. Android now checks that only enabled runtime memory is injected into `chat.send` context, stale client memory cache is replaced/mutated from runtime `memory.*` results, and client capabilities advertise runtime-owned memory/history/attachments; macOS now checks authenticated `memory.upsert`, `memory.list`, and `memory.delete` against the runtime JSONL memory store.
- Added runtime-mediated attachment/document/image regressions to the same no-device gate. Android now checks attachment-only locale prompts, final-user-message-only attachment payload metadata, image-send blocking for non-vision models, valid attachment cleanup, stored attachment metadata rehydration, and read-only message chips; macOS now checks document text extraction into `chat.send`, MIME-only structured text attachments, image rejection for non-vision models, LM Studio vision-image forwarding, unsupported attachment structured errors, and qualified LM Studio chat routing.
- Added chat/embedding model separation regressions to the same no-device gate. Android now checks that embedding models cannot become chat send targets, selected chat and Memory indexing models persist separately across restoring/missing model-list states, wrong-kind or uninstalled refreshed models clear safely, and explicit embedding selections can be cleared; macOS now checks Ollama/LM Studio embedding classification plus aggregate/router rejection of embedding models as chat routes.
- Added runtime-generated chat-title regressions to the same no-device gate. Android now checks that title requests are first-completed-turn only, legacy first-prompt titles sanitize back to the neutral title, and manual/runtime-generated titles are preserved; macOS now checks automatic title generation after the first answer, inline `<think>` stripping, and deterministic fallback when backend title output is invalid.
- Added runtime-generated next-question regressions to the same no-device gate. Android now checks that suggestions attach only to the latest assistant answer, request candidates carry the normalized app language, existing suggestions are not regenerated unnecessarily, and blank assistant placeholders do not show suggestions; macOS now checks structured/fenced suggestion output, invalid-output empty results, and localized numbered-list fallback parsing.
- Added Android ViewModel reasoning-state regressions to the same no-device gate. The gate now checks `reasoning_delta`, `thinking_delta`, complete inline `<think>` tags, split opening/closing think tags across streamed deltas, and cleanup of incomplete think placeholders on `chat.done`, so reasoning cannot silently merge back into visible assistant answer text.
- This makes the local gate catch the class of failures where a valid QR/deeplink payload enters the device app but relay route material is stripped, not persisted, or not reused for a later pairing attempt.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It still does not prove optical QR scan, camera permission flow, real-device app lifecycle, or live different-network relay reachability.

Verified after this change:

- `./script/check_no_device_quality.sh`

## 2026-06-26 Android Pending Relay QR Retry Regression

- Added a focused Android ViewModel regression for the QR pairing path where the scanned relay route exists but the first relay dial fails because the route is still warming up.
- The test proves the client does not fall back to direct TCP, keeps the pending pairing route persisted, surfaces the retrying pairing state, waits for the scheduled retry, and then sends `pairing.request` through the same relay route when the relay becomes ready.
- Added the regression to `script/check_no_device_quality.sh`, so the aggregate no-device gate now tracks pending relay QR retry behavior alongside QR payload parsing, route preparation, route persistence, app-init auto reconnect, and Compose smoke coverage.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove optical QR scanning, camera permission flow, live relay reachability from a mobile carrier or different Wi-Fi, physical app lifecycle, IME behavior, or real haptic feel.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady`
- `./script/check_no_device_quality.sh`

## 2026-06-26 Android Relay-First Bonjour Fallback Regression

- Added a ViewModel regression for the mixed route case where a trusted runtime has a saved relay route and the client also discovers the same runtime on the local network.
- The test proves reconnect attempts the saved relay route first, then falls back to the matching Bonjour direct route only after the relay connector fails. This keeps different-network failures visible when no local route exists, while preserving fast recovery when the paired runtime is also reachable on the same network.
- Added the regression to `script/check_no_device_quality.sh`.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove live mDNS discovery on a handset, physical network switching, carrier NAT behavior, or real remote relay reachability.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayReconnectAttemptsRelayBeforeMatchingBonjourFallback`
- `./script/check_no_device_quality.sh`

## 2026-06-26 Android Compose Reasoning Toggle Smoke

- Added a no-device Compose UI regression for the chat reasoning surface.
- The test renders `ChatScreen` with an assistant message containing four reasoning lines and answer text, proves the collapsed UI shows the `Thinking` affordance plus only the first three reasoning lines, then clicks the show control and proves the full reasoning text and `Hide thinking` affordance render.
- The same no-device Compose coverage now injects a fake `LocalHapticFeedback` and proves both the chat send action and reasoning toggle dispatch the lightweight AetherLink haptic feedback path.
- This complements the existing state/policy tests for `chat.reasoning_delta`, `chat.thinking_delta`, inline `<think>` parsing, dim collapsed alpha, and three-line preview behavior with real Compose tree coverage.
- The Android phone was disconnected during this pass, so this is Robolectric/JVM Compose evidence only. It does not prove physical touch target feel, real haptic output, device font metrics, IME behavior, or rendered screenshots on the handset.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRendersReasoningCollapsedAndExpandable`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest`

## 2026-06-26 Android Trusted Relay Auto-Reconnect Regression

- Added a focused Android ViewModel regression for app-init auto reconnect with a previously trusted relay-backed runtime.
- The test recreates `RuntimeClientViewModel` with saved chat-model and Memory indexing model selections plus a trusted relay route, then proves the app starts the relay connection without a manual connect action.
- After authenticated reconnect, the test proves the client refreshes route lease material, runtime health, runtime-owned chat history, runtime-owned memory, and then requests the model list after health returns.
- Added the regression to `script/check_no_device_quality.sh` and updated the gate coverage output so trusted relay app-init auto-reconnect is tracked by the aggregate no-device check.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove physical app relaunch, camera QR scan, haptic feel, live streamed chat/cancel, or real different-network relay reachability.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelAutoReconnectsTrustedRelayOnInitAndRefreshesRuntimeState`
- `./script/check_no_device_quality.sh`

## 2026-06-26 Android No-Device Compose Screen Smoke

- Added the first Android no-device Compose UI smoke tests using Robolectric plus Compose UI test APIs.
- The smoke renders public `SettingsScreen` and `ChatScreen` composables without launching `MainActivity`, avoiding CameraX/ML Kit QR scanner coupling while still proving real Compose UI trees are built on the JVM.
- Settings coverage proves the pairing-first surface renders, the QR scan action invokes its callback, and the pending QR route state renders the scan-latest-QR recovery copy.
- Chat coverage proves the floating composer renders with its accessibility input label, accepts text input, enables the send action when a connected local chat model is ready, and invokes `onSend`.
- Expanded the same no-device Compose smoke to recompose `SettingsScreen` through localized test contexts for the launch language set: English, Korean, Japanese, Simplified Chinese, and French. This proves the visible pairing title is resolved from real Android localized resources in each language.
- Added the test class to `script/check_no_device_quality.sh`, so Android screen-level no-device smoke now runs with the aggregate gate alongside ViewModel/helper tests.
- The Android phone was disconnected during this pass, so this is JVM/Robolectric Compose evidence only. It does not prove physical screenshots, camera QR scan, real haptic feel, IME behavior on device, or real different-network runtime connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest`
- `bash -n script/check_no_device_quality.sh`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/build.gradle.kts gradle/libs.versions.toml apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt script/check_no_device_quality.sh docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`

## 2026-06-26 Android QR URI Policy Hardening

- Tightened Android external pairing deeplink handling to accept only the canonical host-form pairing URI, `aetherlink://pair?...`, matching the manifest route that external camera/scanner apps can deliver reliably.
- Kept the in-app camera QR scanner path flexible through `RuntimePairingPayloadParser`, so raw QR values still parse through the product QR payload validator rather than the Android intent resolver.
- Added no-device tests proving path-only custom-scheme pairing URIs such as `aetherlink:/pair?...` are not treated as external pairing deeplinks, and release-mode QR parsing rejects macOS local diagnostic direct-route payloads with `pairing_direct_route_rejected`.
- Added the release-mode local diagnostic QR rejection regression to `script/check_no_device_quality.sh` and documented `aetherlink://pair` as the canonical QR URI in `docs/protocol.md`.
- The Android phone was disconnected during this pass, so this is source/unit/documentation evidence only. It does not prove optical QR scanning, third-party camera app deeplink delivery, physical install, haptic feel, or real different-network relay reachability.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pairingDeepLinkRejectsPathOnlyPairingUris --tests com.localagentbridge.android.AppNavigationTest.pairingDeepLinkAcceptsAetherLinkPairUris --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.releasePairingParserRejectsMacosLocalDiagnosticQrRoute -Pkotlin.incremental=false`

## 2026-06-26 Cross-OS UI Copy Audit

- Audited Android string resources and macOS localized SwiftUI copy for visible platform-specific wording such as Android, Mac, macOS, iOS, iPhone, or phone.
- No replacement candidates were found in current user-facing UI copy. The remaining platform mentions are packaging/permission/developer-context details, such as camera permission, Local Network permission, Android manifest permissions, scripts, or internal compatibility log parsing.
- Confirmed `script/check_copy_hygiene.py` already guards user-facing source/resource files against reintroducing platform-specific product UI copy, while allowing developer scripts and compatibility-only log mappings.
- Re-ran Android and macOS localization parity checks to confirm the English, Korean, Japanese, Simplified Chinese, and French resource sets remain aligned.
- The Android phone was disconnected during this pass, so this is source/resource/script evidence only. It does not prove rendered screenshots, physical language switching, optical QR scan, or real different-network connectivity.

Verified after this change:

- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`

## 2026-06-26 Android Settings Preference and Embedding Compose Smoke

- Added no-device Compose UI coverage for `SettingsScreen` preference controls and Memory indexing model selection.
- The smoke proves the Settings surface renders the Preferences panel, dispatches the Appearance selection callback for Dark mode, dispatches the Language callback for Korean, expands the Memory indexing model section, and dispatches separate embedding-model selection and clearing callbacks for an installed embedding model.
- This specifically guards the current requirement that text-generation chat models and embedding models stay separated in the UI, and that language/theme choices are reachable from Settings rather than the chat surface.
- A GPT-5.5 read-only subagent audited the UI coverage gap and was closed after reporting; GPT-5.3-Codex-Spark was not used in this pass.
- The Android phone was disconnected during this pass, so this is JVM/Robolectric Compose evidence only. It does not prove physical tapping, real haptic output, camera QR scan, physical reconnect, or different-network runtime connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest'`
- `./script/check_no_device_quality.sh`
- `git diff --check -- apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt`

## 2026-06-26 Android Chat Top-Bar Model Picker Compose Smoke

- Added no-device Compose UI coverage for the actual chat top-bar model picker in the ChatGPT-like chat shell.
- Exposed `ChatTopAppBarTitle` as an `internal` test seam while keeping the implementation-local `ChatModelTopBarMenu` private.
- The smoke renders the top-bar picker with two installed runtime-host-local chat models and one installed runtime-host-local embedding model, proves the closed picker shows the selected chat model, opens the menu, and verifies the refresh action, chat rows, Memory indexing model section, no-selection copy, and embedding row are visible.
- The same smoke proves selecting `Nomic Embed Text` invokes only `onSelectEmbeddingModel("ollama:nomic-embed-text")`, then reopening and selecting `Llama 3.1 8B` invokes only `onSelectModel("ollama:llama3.1:8b")`.
- Updated `script/check_no_device_quality.sh` coverage output so the aggregate gate now explicitly names chat top-bar model/embedding picker separation.
- A GPT-5.5 worker implemented the focused UI smoke and was closed after verification; GPT-5.3-Codex-Spark was not used.
- The Android phone was disconnected during this pass, so this is JVM/Robolectric Compose evidence only. It does not prove physical dropdown tapping, real haptic output, optical QR scanning, physical reconnect, or different-network runtime connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerSeparatesChatAndEmbeddingModels'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest'`
- `./script/check_no_device_quality.sh`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt`

## 2026-06-26 Android Primary Screen Locale/Theme Matrix Smoke

- Added no-device Compose layout smoke coverage for the primary Android Chat and Settings surfaces across the full initial launch matrix: 5 languages x 2 appearances x 2 primary surfaces.
- The test recomposes Chat and Settings through localized contexts for English, Korean, Japanese, Simplified Chinese, and French with both Material light and dark color schemes for each surface.
- The smoke asserts the root lays out to a minimum mobile-sized viewport in each case and proves visible localized Chat/Settings anchors resolve for every matrix cell. Chat-specific composer, send, reasoning, fake haptic callback, and model-picker behavior remains covered by the focused Compose tests in the same class.
- Attempted full `captureToImage()` pixel smoke first, but Robolectric window capture timed out in this environment while forcing redraw. The final committed check intentionally uses stable layout/semantics assertions instead of overstating screenshot evidence.
- Updated `script/check_no_device_quality.sh` coverage output so the aggregate gate explicitly names the full five-language light/dark Chat/Settings matrix and fake haptic callback dispatch without claiming real haptic output.
- The Android phone was disconnected during this pass, so this is JVM/Robolectric Compose layout evidence only. It does not prove physical screenshots, real device font metrics, actual haptic output, optical QR scanning, physical reconnect, or different-network runtime connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.primaryScreensRenderAcrossLocaleThemeSurfaceMatrix'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest'`
- `./script/check_no_device_quality.sh`
- `git diff --check -- apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt`

## 2026-06-26 QR Scan Error Routing and Schema Scope Guard

- Changed the in-app QR camera path and manual QR text entry to accept AetherLink pairing QR candidates before full payload validation, then forward them to the runtime ViewModel for structured parser errors. This prevents a scanned AetherLink QR with stale, local-only, or unusable route material from being silently ignored by the scanner.
- Kept unsupported schemes/actions rejected at the scanner/manual-input edge, so random QR codes still do not trigger pairing flow.
- Aligned the Android core pairing parser with the external deeplink and documented QR contract by rejecting path-only forms such as `aetherlink:/pair?...`; product QR remains canonical `aetherlink://pair?...`.
- Added Android tests proving invalid AetherLink pair candidates reach the structured error path, while path-only URI forms remain outside the product QR contract.
- Tightened the pairing QR JSON schema so private IPv4, CGNAT, and ULA IPv6 relay hosts require explicit `private_overlay` scope via `relay_scope`, `remote_scope`, or compact `rsc`. Updated `script/check_protocol_schema.py` so this contract is checked with the rest of the protocol schema.
- A GPT-5.5 read-only subagent audited the QR/route path and was closed after reporting. GPT-5.3-Codex-Spark was not used.
- The Android phone was disconnected during this pass, so this is source/unit/schema evidence only. It does not prove optical camera scanning, real QR pairing completion, physical reconnect, or real different-network relay reachability.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`

## 2026-06-26 QR v1 Contract Alignment

- Aligned the Android QR payload parser with `packages/protocol-schema/pairing-qr.schema.json` by requiring `version=1` or compact `v=1` before accepting a QR as a valid pairing payload.
- Kept scanner/manual-input candidate routing intact: an unversioned `aetherlink://pair` candidate can still reach the ViewModel and produce a structured invalid-QR error instead of being silently ignored.
- Updated legacy-alias parser tests so compatibility aliases such as `nonce`, `code`, `device_id`, and `fingerprint` remain supported only inside a versioned v1 payload.
- Documented the v1 requirement in `docs/protocol.md`.
- The Android phone was disconnected during this pass, so this is source/unit/documentation evidence only. It does not prove optical QR scanning or completed device pairing.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`

## 2026-06-26 Expired Relay Lease Reconnect Guard

- Preserved complete-but-expired trusted relay material instead of silently dropping it from Android trusted runtime state. This keeps the app able to explain why a previously paired runtime cannot reconnect from another network.
- Added an Android reconnect guard that emits `remote_route_expired` with `route_diagnostic_remote_route_expired` when a trusted runtime has only expired relay route material and no currently connectable route.
- Kept already discovered same-network routes eligible: the expired-route warning is only emitted when no reconnect target is available.
- Marked `script/aetherlink_relay.py` as legacy-only and guarded it behind `--allow-legacy-no-allocation` because it cannot allocate the lease material now required by QR pairing. Current different-network QR development must use SwiftPM `AetherLinkRelay --require-allocation`.
- Added the legacy Python relay allocation guard to the no-device quality gate so future changes cannot silently re-enable the wrong relay for current QR pairing.
- The Android phone was disconnected during this pass, so this is source/unit/documentation evidence only. It does not prove physical QR scanning or real different-network connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.PairingStoreTest :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit -Pkotlin.incremental=false`
- `bash -n script/check_no_device_quality.sh && ./script/check_no_device_quality.sh`

## 2026-06-26 Android Relay Preparation Host Eligibility Guard

- Hardened the Android transport layer so relay routes are rechecked before they become prepared remote routes. A relay host that is loopback, localhost, unspecified, `.local`, link-local, multicast, or ordinary private-network-only material no longer reaches the relay connector just because malformed saved state or a future caller bypassed QR parser validation.
- Preserved intentional exceptions: `relay_scope=private_overlay` keeps private/CGNAT/ULA relay literals eligible only for a user-controlled VPN, tunnel, or private overlay, and `relay_scope=usb_reverse` keeps loopback relay routes available for explicit debug USB reverse diagnostics.
- Passed `relay_scope` from pending QR payloads and saved trusted-runtime records into `RuntimeRelayRoutePreparation`, so the lower transport guard makes the same remote-vs-private-overlay decision as the QR parser and trusted route planner.
- Added `RuntimeRelayRoutePreparationTest` coverage for rejected local-only hosts, allowed private-overlay hosts, rejected link-local hosts even with private-overlay scope, and debug USB reverse loopback preparation.
- Added the focused transport relay-preparation test to `script/check_no_device_quality.sh`, and updated the aggregate gate output to name the relay preparation host eligibility guard.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove optical QR scanning, physical pairing, real relay reachability, or different-network runtime connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:transport:testDebugUnitTest --tests com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparationTest -Pkotlin.incremental=false`

## 2026-06-26 Android Settings Diagnostic Endpoint Visibility Smoke

- Audited the Android Settings connection surface with a GPT-5.5 read-only subagent. The default Settings UI already hides manual connection address/port, USB connection, emulator connection, manual QR text, and route troubleshooting behind `showDeveloperDiagnostics`.
- Added no-device Compose regression coverage for the actual rendered `SettingsScreen`. With `showDeveloperDiagnostics=false`, the test proves QR pairing remains the visible flow and the troubleshooting/manual endpoint controls do not render.
- Added a second rendered regression for `showDeveloperDiagnostics=true` proving that even when the debug-only troubleshooting section is present, the manual endpoint controls remain behind the explicit "Connection troubleshooting" switch rather than appearing immediately.
- This keeps the normal Android product path aligned with QR-only pairing and prevents fixed-IP/manual endpoint controls from creeping back into the default UI.
- The Android phone was disconnected during this pass, so this is JVM/Robolectric Compose evidence only. It does not prove physical screenshots, actual touch behavior, QR camera scanning, or real different-network runtime connectivity.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenHidesDiagnosticEndpointControlsByDefault' --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch' -Pkotlin.incremental=false`

## 2026-06-26 Android Chat History Dangerous Action Compose Guard

- Audited Android chat history archive/delete behavior with a GPT-5.5 read-only subagent. The current implementation already separates active previous chats from archived chats, excludes archived chats from memory/research/reflection candidate helpers, and keeps permanent deletion available only for archived chats.
- Added no-device Compose regression coverage for the rendered Settings Chat history section. The test proves bulk actions are not visible on initial Settings render, remain hidden after opening Chat history, and only appear after the nested "Manage all chats" disclosure is opened.
- The same rendered test exercises the two-step dialog for "Archive all chats" and the two-step dialog for "Permanently delete archived chats", proving callbacks are not invoked until the second confirmation.
- Updated the aggregate no-device quality gate output to explicitly name chat history bulk action hiding and two-step confirmation coverage.
- The Android phone was disconnected during this pass, so this is JVM/Robolectric Compose evidence only. It does not prove physical scrolling/tapping, real haptic output, physical screenshots, or runtime-server chat history synchronization.

Verified after this change:

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed' -Pkotlin.incremental=false`

## 2026-06-26 macOS Public Relay QR Scope Contract

- Audited the macOS QR generation path with a GPT-5.5 read-only subagent and closed the agent after the audit. GPT-5.3-Codex-Spark was not used.
- Fixed a QR contract mismatch: shared protocol fixtures and Android parser tests expect public relay QR payloads to carry `remote` scope, but `CompanionAppModel` could omit `relay_scope`/`rsc` for public DNS relay hosts.
- Updated `CompanionAppModel` so public/DNS relay routes emit `remote`, while private-network relay literals still require explicit `private_overlay` and loopback debug routes remain `usb_reverse`.
- Added macOS regression assertions proving full QR payloads include `relay_scope=remote`, compact camera QR payloads include `rsc=remote`, and runtime route refresh results report `relayScope=remote`.
- Updated the aggregate no-device quality gate output to explicitly name public relay remote-scope QR contract coverage.
- The Android phone was disconnected during this pass, so this is source/unit evidence only. It does not prove optical QR scanning, completed physical pairing, or real different-network relay reachability.

Verified after this change:

- `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests 'com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest' -Pkotlin.incremental=false`

## 2026-06-26 Cross-Network QR Readiness Copy Tightening

- Audited QR-only connection readiness UX with a GPT-5.5 read-only subagent and closed the agent after the audit. GPT-5.3-Codex-Spark was not used.
- Updated Android pending-pairing copy in all five supported languages so an identity-only or route-incomplete QR no longer tells users that nearby discovery may finish automatically. It now tells them the QR identified the runtime, but cross-network reconnect needs protected connection details and the latest AetherLink Runtime QR.
- Strengthened the Android no-device Compose regression for `SettingsScreen` pending-pairing state so the full actionable detail copy is asserted, not just the title/status/action.
- Updated macOS `StatusView` to reuse `relayQRCodeReadinessText` for the "Connection details not ready for QR" overview. The companion status surface now reflects the same stopped, connecting, reconnecting, failed, and ready route-preparation details already covered by localization tests.
- The Android phone was disconnected during this pass, so this is source/unit/render-smoke evidence only. It does not prove optical QR scanning, completed physical pairing, or real different-network relay reachability.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenRendersPendingPairingRouteState' -Pkotlin.incremental=false`
- `swift build --package-path apps/macos --product AetherLink`
- `swift test --package-path apps/macos --filter 'AetherLinkLocalizationTests|AetherLinkRenderSmokeTests'`

## 2026-06-26 Diagnostic QR Text Fallback Clarification

- Renamed the Android manual QR text path to a diagnostic fallback in all five supported UI languages. Normal pairing copy remains camera QR scanning, and the text-entry path now explicitly says it exists only when camera scanning cannot be tested.
- Kept the diagnostic QR text, USB connection, emulator connection, connection address, and connection port controls hidden from the default Settings UI.
- Made the developer diagnostics row easier to operate by letting the whole row toggle the switch, then added stable no-device Compose coverage for the off-to-on diagnostics state without exposing those test tags to users.
- The Android phone was disconnected during this pass, so this is source/resource/Robolectric evidence only. It does not prove physical camera scanning, actual device haptic feel, or optical QR pairing.

Verified after this change:

- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenHidesDiagnosticEndpointControlsByDefault' --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch' -Pkotlin.incremental=false`

## 2026-06-26 macOS First-Launch Pairing Priority

- Used a GPT-5.5 worker subagent for the macOS status surface and closed it after completion. GPT-5.3-Codex-Spark was not used.
- Updated the companion Status overview so a first launch with no trusted devices prioritizes pairing readiness over model-provider repair, even when Ollama or LM Studio is unavailable.
- Aligned the Status quick action for generating a pairing QR with the same route-readiness rule used by the Pairing view, so the button is disabled when QR route material cannot be produced.
- Added focused macOS localization tests proving first-launch pairing priority and provider repair after a trusted device exists.
- The Android phone was disconnected during this pass, so this is macOS source/unit evidence only. It does not prove physical Android pairing or cross-network connectivity.

Verified after this change:

- `swift test --package-path apps/macos --filter AetherLinkLocalizationTests`
