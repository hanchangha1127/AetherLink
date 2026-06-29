# QA Evidence

This document separates current verification evidence from historical captures.

## Current Rule

- Source code, tests, smoke commands, and explicitly referenced current artifacts are authoritative.
- Files under `artifacts/` are generated QA captures. Treat them as historical unless the latest relevant `docs/progress.md` entry names the file and explains the device/runtime state that produced it.
- Do not use an old screenshot or XML dump as proof that the current UI copy, route behavior, QR pairing, or localization is still correct.
- New `artifacts/*.png` and `artifacts/*.xml` files are ignored by default so stale generated captures are not accidentally committed.

## 2026-06-29 macOS Connection Recovery Source Copy

The latest evidence is focused macOS source/localization evidence:

- The macOS runtime app now uses `Connection Recovery` as the source/product label for the different-network recovery surface instead of the stale `Advanced Connection Setup` wording.
- Existing Korean, Japanese, Simplified Chinese, and French translations were preserved under the renamed source keys.
- The host-warning accessibility label now exposes a localized `Connection Recovery warning`, `Needs attention` status, and fallback `No details available` text.
- Copy hygiene now treats `Advanced Connection Setup` as stale visible macOS copy rather than an allowed old localization value.
- Latest macOS localization evidence: `python3 script/check_macos_localization.py` passed.
- Latest stale-source search evidence: `rg -n "Advanced Connection Setup|Advanced connection setup" apps/macos/LocalAgentBridgeApp/Sources apps/macos/LocalAgentBridgeApp/Tests script/check_macos_localization.py` returned no matches.
- Latest focused XCTest evidence: `swift test --filter LocalAgentBridgeTests.AetherLinkLocalizationTests` passed.
- Latest copy-hygiene evidence: `python3 script/check_copy_hygiene.py` passed after the stale-copy guard update.
- Caveat: this is source/localization/test evidence only. It does not prove live VoiceOver output, a rendered macOS screenshot, optical QR scanning, physical Android pairing, production private overlay routing, or live provider-backed chat/cancel.

## 2026-06-29 French Model And Runtime Copy Consistency

The latest evidence is focused French localization evidence:

- Mobile French runtime/model copy now uses `État`, `Runtime de confiance requis`, `Via AetherLink Runtime`, and `Localement installé` for the affected status and model-source surfaces.
- Mobile and runtime-host French embedding model copy now consistently uses memory-indexing terminology rather than mixing `embedding` with translated memory-indexing labels.
- Android focused Compose expectations cover the updated French embedding-model empty state and disconnected model-picker empty-state summary.
- macOS localization XCTest expectations cover the updated French model-row accessibility summary and model-section accessibility label.
- Latest string/localization evidence: `python3 script/check_android_string_parity.py` and `python3 script/check_macos_localization.py` passed.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelEmptyStatesAnnounceLocalizedLiveRegion --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerEmptyStatesShowLocalizedTitleAndLiveRegion -Pkotlin.incremental=false --console=plain` passed.
- Latest focused macOS evidence: `swift test --package-path apps/macos --filter LocalAgentBridgeTests.AetherLinkLocalizationTests` passed.
- Caveat: this is resource/test evidence only. It does not prove physical TalkBack or VoiceOver pronunciation, physical rendered screenshots, optical QR scanning, production private overlay routing, or live provider-backed chat/cancel.

## 2026-06-29 Memory-Indexing Model Term Consistency

The latest evidence is focused multilingual resource and localization-test evidence:

- Android Japanese and Simplified Chinese embedding-model guidance now uses memory-indexing model terminology consistently with their section titles and row summaries.
- macOS Japanese and Simplified Chinese model group labels, model-row accessibility summaries, and status guidance now use memory-indexing terminology instead of generic embedding wording.
- The remaining French macOS status sentence now uses `modèles de chat et d’indexation de la mémoire`.
- Copy hygiene now rejects `embedding` loanwords in French macOS localized values while still allowing English source keys.
- Latest Android resource evidence: `python3 script/check_android_string_parity.py` passed.
- Latest macOS localization evidence: `python3 script/check_macos_localization.py` and `swift test --package-path apps/macos --filter LocalAgentBridgeTests.AetherLinkLocalizationTests` passed.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelEmptyStatesAnnounceLocalizedLiveRegion -Pkotlin.incremental=false --console=plain` passed.
- Latest hygiene evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed.
- Caveat: this is resource/test/script evidence only. It does not prove physical TalkBack or VoiceOver pronunciation, physical rendered screenshots, optical QR scanning, production private overlay routing, or live provider-backed chat/cancel.

## 2026-06-29 Android Provider Label Normalization

The latest evidence is focused no-device Android provider-health UI evidence:

- Runtime-reported provider id/name variants such as `lm-studio` and `lm_studio` now render through the localized provider label path as `LM Studio`.
- Provider row visible names, accessibility summaries, unavailable/ready details, and diagnostics show/hide labels use the normalized localized provider label.
- Custom provider display names remain preserved from runtime-provided names when their ids are not known AetherLink provider ids.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusProviderRowsExposeLocalizedAccessibilitySummariesAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusProviderDiagnosticsToggleExposesExpandedState --console=plain` passed.
- Latest copy/string/script evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_android_string_parity.py`, and `bash -n script/check_no_device_quality.sh` passed.
- Caveat: this is Android no-device UI/source evidence only. It does not prove physical TalkBack pronunciation, physical Android rendering, live provider failure payload variety, optical QR scanning, live provider-backed chat/cancel, or true different-network runtime connectivity.

## 2026-06-29 Android Drawer Chat Date Groups

The latest evidence is localized no-device Android drawer evidence plus connected physical Android install/launch/drawer capture evidence:

- Android drawer previous chats are grouped by local calendar buckets: `Today`, `Yesterday`, `Previous 7 days`, and `Older`.
- Grouping is applied after the existing drawer chat search filter, and the bucket order remains stable while preserving row order inside each bucket.
- The group labels are localized across English, Korean, Japanese, Simplified Chinese, and French and expose heading semantics.
- Drawer archive now uses lighter selection-change haptic feedback because archive is reversible, while rename keeps primary-action feedback.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatSessionDrawerGroupLabelUsesLocalCalendarDays --tests com.localagentbridge.android.AppNavigationTest.chatSessionDrawerGroupsUseStableBucketOrderAndPreserveOrderInsideBuckets --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerGroupsPreviousChatsByLocalDateAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerChatSearchFiltersClearsAndUsesHapticFeedback --console=plain` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed and included `Android drawer chat date grouping`.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Physical build/install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:assembleDebug --console=plain` passed and `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`.
- Physical launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM shell am start -W -n com.localagentbridge.android/.MainActivity` started the app, `pidof` returned a live process, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Screenshot evidence: `/tmp/aetherlink-phone-drawer-date-groups.png` and `/tmp/aetherlink-phone-drawer-date-groups-ui.xml` captured the installed app after launch; `/tmp/aetherlink-phone-drawer-open-date-groups.png` and `/tmp/aetherlink-phone-drawer-open-date-groups-ui.xml` captured the opened drawer with the `Today` group visible above a previous chat.
- Caveat: this proves implementation, focused no-device UI behavior, aggregate gates, physical install/launch, and physical drawer rendering. It does not prove physical TalkBack announcement timing, real haptic feel, optical QR scanning, live provider-backed chat/cancel, or true different-network runtime connectivity.

## 2026-06-29 Android Streaming Thinking Collapsed By Default

The latest evidence is focused no-device Android reasoning UI evidence:

- Assistant reasoning/think output now stays muted and collapsed by default even while a reasoning stream is actively open.
- The collapsed preview keeps the existing short thinking surface and expands to the full thinking text only after user action.
- Open reasoning streams still expose a polite live region and suppress the generic assistant typing placeholder, so thinking updates remain separate from final answer text.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRendersReasoningCollapsedAndExpandable --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenKeepsOpenStreamingReasoningCollapsedUntilExpanded --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenReasoningSummaryLocalizesAcrossSupportedLanguages --tests com.localagentbridge.android.AppNavigationTest.reasoningDisplayPolicyKeepsCollapsedPreviewDimAndThreeLines --tests com.localagentbridge.android.AppNavigationTest.reasoningPreviewStaysShortAndDimUntilExpanded --console=plain` passed.
- Latest copy/docs evidence: `python3 script/check_copy_hygiene.py` and `python3 script/check_docs_hygiene.py` passed.
- Latest Android string and script evidence: `python3 script/check_android_string_parity.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Physical build/install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:assembleDebug --console=plain` passed and `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`.
- Physical launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM shell am start -W -n com.localagentbridge.android/.MainActivity` started the app, `pidof` returned a live process, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Screenshot evidence: `/tmp/aetherlink-phone-thinking-collapsed-policy.png` and `/tmp/aetherlink-phone-thinking-collapsed-policy-ui.xml` captured the installed app after launch in the latest-QR recovery state.
- Caveat: this proves the no-device Compose policy and accessibility semantics. It does not prove physical TalkBack announcement timing, real model reasoning output quality, physical haptic feel, optical QR scanning, live provider streaming/cancel, or true different-network runtime connectivity.

## 2026-06-29 Android Settings Chat History Rename Action

The latest evidence is focused no-device Android UI/store evidence plus connected physical Android install/launch evidence:

- Settings > Chat history active and archived rows now expose a localized `Rename chat` action.
- Active and archived row rename actions use the same rename dialog entry point and haptic feedback path.
- Archived chat rename preserves archive state instead of restoring the chat or reintroducing it into active memory/history flows.
- Streaming state disables the rename action with localized accessibility state copy across English, Korean, Japanese, Simplified Chinese, and French.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeRenameActionForActiveAndArchivedChats --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPerChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.renamedArchivedChatSessionKeepsArchiveState --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed for English, Korean, Japanese, Simplified Chinese, and French.
- Latest copy/docs/diff evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Physical build/install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:assembleDebug --console=plain` passed and `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`.
- Physical launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM shell am start -W -n com.localagentbridge.android/.MainActivity` started the app, `pidof` returned a live process, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Screenshot evidence: `/tmp/aetherlink-phone-chat-history-rename-action.png` and `/tmp/aetherlink-phone-chat-history-rename-action-ui.xml` captured the installed app after launch in the latest-QR recovery state.
- Caveat: this evidence proves implementation, focused UI/store behavior, build, install, and launch. It does not prove a manual physical tap on the Settings rename action, physical TalkBack traversal, optical QR scanning, production relay allocation, true QR-only different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 Android Relay QR Device-Reachability Preflight

The latest evidence combines focused Android ViewModel/UI/resource evidence, macOS localization/copy hygiene, and connected physical Android install/launch evidence:

- Android now checks whether the scanning device can open the QR-provisioned relay host and port before the relay connector starts.
- Unreachable relay routes fail as `remote_route_unreachable_from_device` with diagnostic `route_diagnostic_relay_unreachable_from_device`.
- The failure clears pending QR pairing state and keeps the user on the fresh-QR recovery path instead of repeatedly retrying an unreachable relay route.
- Route notices and empty-chat recovery copy distinguish device-network relay reachability failures from generic saved-route failures.
- macOS QR-ready copy now states that pairing or refresh still requires the scanning device to reach the advertised route.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayQrPairingFailsBeforeConnectWhenDeviceCannotReachRelayRoute --tests com.localagentbridge.android.AppNavigationTest.routeAvailabilityNoticeUsesDeviceReachabilityDiagnosticForRelayQrPreflightFailure --tests com.localagentbridge.android.AppNavigationTest.emptyChatPrefersQrRefreshWhenDeviceCannotReachRelayQrRoute --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` and `python3 script/check_macos_localization.py` passed.
- Latest copy evidence: `python3 script/check_copy_hygiene.py` passed.
- Latest macOS localization test evidence: `swift test --filter AetherLinkLocalizationTests/testPairingRouteNoticeAccessibilityUsesSelectedLanguage` passed.
- Latest docs and diff hygiene evidence: `python3 script/check_docs_hygiene.py` and `git diff --check` passed.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Physical build/install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:assembleDebug -Pkotlin.incremental=false --console=plain` passed and `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`.
- Physical launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM shell am start -S -n com.localagentbridge.android/.MainActivity` started the app, `pidof` returned a live process, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Screenshot evidence: `/tmp/aetherlink-phone-relay-preflight.png` and `/tmp/aetherlink-phone-relay-preflight-ui.xml` captured the installed app after launch.
- Caveat: this evidence proves preflight branching, copy, build, install, and launch. It does not prove optical QR camera capture, production public relay allocation, direct P2P NAT traversal, or a no-ADB real different-network route.

## 2026-06-29 Android QR Scanner Invalid-Code Recovery

The latest evidence is no-device Android scanner UI, resource, and unit evidence:

- Optical scanner raw values are now classified before being consumed: valid AetherLink pairing QR, invalid or expired AetherLink QR, or unsupported QR.
- Invalid/expired AetherLink QR values keep the scanner open and render a localized inline recovery message instead of closing the camera and dumping the user back to Settings.
- Unsupported QR values also keep the scanner open and render a localized inline message that the code is not an AetherLink Runtime QR.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pairingQrScannerClassifiesRawValuesBeforeConsumingCameraResult --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest.scannerChromeShowsInvalidQrFeedbackWithoutClosingScanner -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed for English, Korean, Japanese, Simplified Chinese, and French.
- Latest docs, copy, shell, and diff hygiene evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-android-qr-scanner-invalid-code-recovery.log 2>&1` passed with `No-device quality checks passed.` and included `Android QR scanner invalid-code recovery`.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Physical build/install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:assembleDebug -Pkotlin.incremental=false --console=plain` passed and `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`.
- Physical launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM shell am start -S -n com.localagentbridge.android/.MainActivity` started the app, `pidof` returned a live process, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Screenshot evidence: `/tmp/aetherlink-phone-qr-scanner-invalid-code-recovery.png` and `/tmp/aetherlink-phone-qr-scanner-invalid-code-recovery-ui.xml` captured the installed app after launch.
- Caveat: this combines no-device scanner UI/resource evidence with connected physical install/launch evidence. It does not prove a physical camera scan, production relay allocation, true QR-only different-network routing, physical TalkBack traversal, physical haptic feel, or live provider-backed chat/cancel.

## 2026-06-29 Android Settings Chat History Open Action

The latest evidence is no-device Android Compose, resource, and script evidence:

- Settings > Chat history active rows now show a localized `Open chat` action next to `Archive`.
- The action selects the existing runtime-owned session and returns the app to Chat through the app-level callback.
- Archived rows intentionally do not expose `Open chat`; they remain restore/delete only until restored.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPerChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryActiveRowCanOpenChatWithHapticFeedback -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed for English, Korean, Japanese, Simplified Chinese, and French.
- Latest docs, copy, shell, and diff hygiene evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-android-settings-chat-history-open-action.log 2>&1` passed with `No-device quality checks passed.` and included `Android Settings chat history open-chat action`.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Physical build/install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:assembleDebug -Pkotlin.incremental=false --console=plain` passed and `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`.
- Physical launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM shell am start -S -n com.localagentbridge.android/.MainActivity` started the app, `pidof` returned a live process, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Screenshot evidence: `/tmp/aetherlink-phone-chat-history-open-action.png` and `/tmp/aetherlink-phone-chat-history-open-action-ui.xml` captured the installed app after launch.
- Caveat: this combines no-device UI/resource evidence with connected physical install/launch evidence. It does not prove a manual physical tap on the Settings open-chat action, physical TalkBack traversal, optical QR scanning, production relay allocation, true QR-only different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 macOS Runtime History Transcript Preview

The latest evidence is no-device macOS store, model, render, localization, and script evidence:

- `RuntimeChatEventStore.listAllMessages(sessionID:limit:)` now provides a runtime-host inspection path for transcript previews across stored trusted-device owners, while existing owner-scoped client reads remain scoped.
- `CompanionAppModel` now publishes per-session `runtimeChatTranscriptMessages` and `runtimeChatTranscriptErrors`.
- `RuntimeHistoryInspectorSheet` now renders runtime-owned chat sessions and a read-only transcript preview side by side, including muted three-line reasoning snippets when stored assistant reasoning exists.
- Latest transcript model evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryTranscriptPreviewAcrossOwners` passed and verifies owner-scoped stored messages plus assistant reasoning are visible through the host-inspection path.
- Latest transcript error evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryInspectorError` passed and verifies per-session transcript preview failures surface without fabricating transcript messages.
- Latest render evidence: `swift test --filter AetherLinkRenderSmokeTests/testRuntimeHistoryInspectorRendersAcrossLanguagesAndAppearances` passed with transcript preview content across supported macOS languages and appearance modes.
- Latest localization evidence: `python3 script/check_macos_localization.py` and `swift test --filter AetherLinkLocalizationTests/testRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages` passed.
- Latest docs, copy, shell, and diff hygiene evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-macos-runtime-history-transcript-preview.log 2>&1` passed with `No-device quality checks passed.` and included `macOS runtime history transcript preview`.
- Caveat: this is no-device host UI/model evidence only. It does not prove transcript editing, physical Android interaction, optical QR scanning, production different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 Android Physical Device Relay Smoke Refresh

The latest physical evidence is connected-device Android build, install, launch, and development relay smoke evidence:

- Device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Build evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :app:assembleDebug --no-daemon` passed.
- Install evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`.
- Launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb -s R3CXC0M76VM shell am start -S -n com.localagentbridge.android/.MainActivity` started the app and `pidof` returned a live app process.
- First-screen evidence: `/tmp/aetherlink-phone-connected-current.png` and `/tmp/aetherlink-phone-connected-ui.xml` captured the installed app in the latest-QR route-recovery state.
- Physical relay smoke evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel` passed with workdir `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.faBpvK`.
- Runtime evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.faBpvK/runtime.log` observed reconnect plus `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done`.
- Relay evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.faBpvK/relay.log` was produced by the same smoke.
- Screenshot evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.faBpvK/aetherlink-pairing-smoke.png` and `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.faBpvK/aetherlink-chat-cancel-smoke.png`.
- Caveat: this smoke injects the QR result through Android's `VIEW` intent and uses development relay plumbing with `adb reverse`. It does not prove optical QR camera capture, production public relay allocation, direct P2P NAT traversal, or a true QR-only different-network route without USB/debug tooling.

## 2026-06-29 macOS Runtime History Inspector

The latest evidence is no-device macOS model, render, localization, and script evidence:

- `CompanionAppModel` now publishes read-only runtime chat sessions from `RuntimeChatEventStore.listAllSessions(limit:includeArchived:)` and exposes `runtimeChatSessionsError` for inspector read failures.
- Status > Quick Actions now includes `Inspect Runtime History`, which opens a read-only `RuntimeHistoryInspectorSheet` showing active/archived runtime-owned sessions, model id, message count, last event, last error, updated time, empty state, warning state, and accessibility summaries.
- Latest model evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores` passed and verifies owner-scoped runtime chat rows are visible to the host inspector and sorted by latest activity.
- Latest error evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryInspectorError` passed and verifies chat-store read failures surface through the inspector error state without fabricating sessions.
- Latest render evidence: `swift test --filter AetherLinkRenderSmokeTests/testRuntimeHistoryInspectorRendersAcrossLanguagesAndAppearances` passed across supported macOS languages and appearance modes.
- Latest localization evidence: `python3 script/check_macos_localization.py` and `swift test --filter AetherLinkLocalizationTests/testRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages` passed.
- Latest copy evidence: `python3 script/check_copy_hygiene.py` passed.
- Latest docs, shell, and diff hygiene evidence: `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-macos-runtime-history-inspector.log 2>&1` passed with `No-device quality checks passed.` and included `macOS runtime history inspector`.
- Caveat: this is no-device host UI/model evidence only. It does not prove transcript preview, physical Android interaction, optical QR scanning, production different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 macOS Runtime Memory Inspector

The latest evidence is no-device macOS model, render, localization, and script evidence:

- `CompanionAppModel` now publishes read-only runtime memory entries from `RuntimeMemoryStore.listAll()` and exposes `runtimeMemoryEntriesError` for inspector read failures.
- Status > Quick Actions now includes `Inspect Runtime Memory`, which opens a read-only `RuntimeMemoryInspectorSheet` showing enabled/paused memory notes, created/updated timestamps, empty state, warning state, and accessibility summaries.
- Latest model evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores` passed and verifies owner-scoped runtime memory rows are visible to the host inspector and sorted by update time.
- Latest error evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeMemoryInspectorError` passed and verifies memory-store read failures surface through the inspector error state without fabricating entries.
- Latest render evidence: `swift test --filter AetherLinkRenderSmokeTests/testRuntimeMemoryInspectorRendersAcrossLanguagesAndAppearances` passed across supported macOS languages and appearance modes.
- Latest localization evidence: `python3 script/check_macos_localization.py` and `swift test --filter AetherLinkLocalizationTests/testRuntimeMemoryInspectorCopyLocalizesAcrossSupportedLanguages` passed.
- Latest docs, copy, and diff hygiene evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-macos-runtime-memory-inspector.log 2>&1` passed with `No-device quality checks passed.` and included `macOS runtime memory inspector`.
- Caveat: this is no-device host UI/model evidence only. It does not prove physical Android interaction, optical QR scanning, production different-network routing, live provider-backed chat/cancel, or runtime-memory editing from the macOS app.

## 2026-06-29 Android Chat History Manual Runtime Refresh

The latest evidence is no-device Android ViewModel, Compose, resource, script, and physical install evidence:

- Settings > Chat history now has a localized refresh icon action that explicitly re-requests `chat.sessions.list` from the authenticated runtime host.
- The action follows the runtime-owned chat-history boundary: connected trusted runtime required, disabled while streaming, and duplicate manual refreshes are suppressed while a `chat.sessions.list` request is already pending.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryRequestsFreshListAfterPendingListCompletes --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRefreshActionFollowsConnectionStateAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed for English, Korean, Japanese, Simplified Chinese, and French.
- Latest docs, copy, and diff hygiene evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-android-chat-history-manual-refresh.log 2>&1` passed with `No-device quality checks passed.` and included `Android chat history manual runtime refresh`.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`; `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the debug APK on `SM-S936N - 16`.
- Launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb shell am start -n com.localagentbridge.android/.MainActivity` focused `com.localagentbridge.android/.MainActivity`; `dumpsys window` reported `mCurrentFocus=Window{... com.localagentbridge.android/com.localagentbridge.android.MainActivity}` and `mFocusedApp=ActivityRecord{... com.localagentbridge.android/.MainActivity ...}`.
- Screenshot evidence: `/tmp/aetherlink-phone-chat-history-refresh.png` captured the installed app running in the latest-QR route-recovery state.
- Caveat: this does not prove physical Android tap feel, physical TalkBack traversal, optical camera QR scanning, production relay allocation, production different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 Android Runtime Chat Mutation Error Resync

The latest evidence is no-device Android ViewModel/protocol evidence:

- Runtime-owned chat rename, archive, and delete failures now request a fresh `chat.sessions.list` instead of leaving rejected optimistic UI state as authoritative.
- Failed rename clears the client-side manual title override before resync, so the runtime host title can replace the rejected local title.
- Failed delete clears the client-side runtime-session suppression tombstone before resync, so a runtime-owned archived session can reappear if the runtime rejected deletion.
- The relay integration test fake runtime now accepts either `runtime.health` or `route.refresh` first and waits for both before releasing the connection, matching the non-deterministic ordering of asynchronous client startup messages.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientChatSessionMutationFailureTest -Pkotlin.incremental=false --console=plain` passed.
- Latest relay integration evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest -Pkotlin.incremental=false --console=plain` passed.
- Latest copy, docs, and diff hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-android-runtime-chat-mutation-resync.log 2>&1` passed with `No-device quality checks passed.` and included `Android runtime chat mutation error resync`.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`; `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the debug APK on `SM-S936N - 16`.
- Launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb shell am start -n com.localagentbridge.android/.MainActivity` focused `com.localagentbridge.android/.MainActivity`.
- Screenshot evidence: `/tmp/aetherlink-phone-runtime-chat-mutation-resync.png` captured the installed app running in the latest-QR route-recovery state.
- Caveat: this does not prove live runtime-host mutation rejection, physical Android tap flow, optical QR scanning, production relay allocation, production different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 Android Memory Manual Runtime Refresh

The latest evidence is no-device Android ViewModel, Compose, resource, and script evidence:

- Settings > Memory now has a localized `Refresh memory` icon action that explicitly re-requests `memory.list` from the authenticated runtime host.
- The action follows the same boundary as other runtime-memory mutations: connected trusted runtime required, disabled while streaming, and duplicate manual refreshes are suppressed while a `memory.list` request is already pending.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryRequestsFreshListAfterPendingListCompletes --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRefreshActionFollowsConnectionStateAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed for English, Korean, Japanese, Simplified Chinese, and French.
- Latest copy and diff hygiene evidence: `python3 script/check_copy_hygiene.py` and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-android-memory-manual-refresh.log 2>&1` passed with `No-device quality checks passed.` and included `Android memory manual runtime refresh`.
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices` reported `R3CXC0M76VM` as `device`; `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the debug APK on `SM-S936N - 16`.
- Launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb shell am start -n com.localagentbridge.android/.MainActivity` focused `com.localagentbridge.android/.MainActivity`.
- Screenshot evidence: `/tmp/aetherlink-phone-memory-refresh.png` captured the installed app running in the latest-QR route-recovery state.
- Caveat: this does not prove physical Android tap feel, physical TalkBack traversal, optical camera QR scanning, production relay allocation, production different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 Android Memory Disconnected-Session Read-Only Copy

The latest evidence combines targeted no-device Android UI checks with physical Android install and launch confirmation:

- `memory_read_only_notice` now describes memory visible in the current UI session as read-only, and requires trusted-runtime reconnect to refresh or manage it.
- The wording intentionally avoids claiming that memory entries are persisted as a cold-start disk cache, because Android strips memory entries from the persisted runtime snapshot.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.memoryCopyDistinguishesDisconnectedCacheFromEmptyRuntimeMemory --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryDisconnectedSessionEntriesExplainReadOnlyStateAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed for English, Korean, Japanese, Simplified Chinese, and French.
- Latest copy and diff hygiene evidence: `python3 script/check_copy_hygiene.py` and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-memory-disconnected-session-copy.log 2>&1` passed with `No-device quality checks passed.`
- Physical device evidence: `$HOME/Library/Android/sdk/platform-tools/adb devices` reported `R3CXC0M76VM` as `device`; `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the debug APK on `SM-S936N - 16`.
- Launch evidence: `$HOME/Library/Android/sdk/platform-tools/adb shell am start -n com.localagentbridge.android/.MainActivity` focused `com.localagentbridge.android/.MainActivity`.
- Screenshot evidence: `/tmp/aetherlink-phone-current.png` captured the installed app running in the latest-QR route-recovery state.
- Caveat: this does not prove optical camera QR scanning, production public relay allocation, direct P2P NAT traversal, a production different-network route, or live provider-backed chat/cancel.

## 2026-06-29 macOS Runtime Data All-Owner Summary

The latest evidence is no-device macOS Swift/store/source/script evidence:

- `CompanionAppModel.refreshRuntimeDataSummary()` now reads `runtimeChatEventStore.listAllSessions(limit:includeArchived:)` and `runtimeMemoryStore.listAll()` so the status cards count all runtime-owned rows, including rows scoped to trusted device ids.
- Authenticated protocol history and memory routes still use owner-scoped store queries; the new all-owner APIs are for the app shell summary only.
- Latest focused Swift evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores` passed.
- Latest runtime-router evidence: `swift test --filter LocalRuntimeMessageRouterTests` passed with 142 tests.
- Latest copy evidence: `python3 script/check_copy_hygiene.py` passed and now requires the all-owner runtime data summary API path.
- Latest documentation and diff hygiene evidence: `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-macos-runtime-data-all-owner-summary.log 2>&1` passed with `No-device quality checks passed.` and included `macOS runtime data all-owner summary`.
- Caveat: this is no-device store/source evidence only. It does not prove live production client sync, optical QR scanning, physical Android haptics, production different-network routing, or live provider-backed chat/cancel.

## 2026-06-29 Android Suggested Questions Loading With Existing Chips

The latest evidence is no-device Android Compose/resource/source/script evidence:

- `SuggestedQuestions` now renders the localized generating-progress live region whenever `isLoadingSuggestions` is true, including when existing suggestion chips are still visible.
- Existing suggestion chips remain visible while the runtime is generating a refreshed set of next-question suggestions.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenGeneratingSuggestionsRowAnnouncesAcrossSupportedLanguages' -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest copy evidence: `python3 script/check_copy_hygiene.py` passed and now guards against the old suggestion-loading-only-when-empty condition.
- Latest shell and diff hygiene evidence: `bash -n script/check_no_device_quality.sh && git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-suggested-questions-existing-chips.log 2>&1` passed with `No-device quality checks passed.` and included `Android generating suggestions with existing chips accessibility`.
- Caveat: this is no-device UI evidence only. It does not prove physical Android install, physical TalkBack traversal, real device haptics, camera QR scanning, physical/live-backend streamed chat/cancel, or production different-network connectivity.

## 2026-06-28 Android Physical QR Relay Pairing, Reconnect, Chat Cancel Verification

The latest physical-device evidence was captured after the connected phone returned as an authorized ADB target:

- Device evidence: `adb devices -l` reported `R3CXC0M76VM` as `device`, model `SM_S936N`.
- Install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew :app:installDebug` passed and installed the debug APK on `SM-S936N - 16`.
- Launch evidence: `adb shell monkey -p com.localagentbridge.android -c android.intent.category.LAUNCHER 1` launched the app, and `adb shell pidof com.localagentbridge.android` returned a running process id.
- Screenshot evidence: `/tmp/aetherlink-phone-screen.png` shows the installed app in the latest-QR route-recovery state.
- Pairing smoke evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install` passed in relay mode.
- Strong physical smoke evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel` passed in relay mode with workdir `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.GK46yg`.
- Runtime result: the strong smoke reported observed `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the physical Android UI, then observed a second `runtime.health` after app relaunch without clearing app data.
- Runtime log: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.GK46yg/runtime.log` was produced by the same run.
- Relay log: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.GK46yg/relay.log` was produced by the same run.
- Screenshot evidence from the strong smoke: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.GK46yg/aetherlink-pairing-smoke.png` and `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.GK46yg/aetherlink-chat-cancel-smoke.png`.
- Caveat: this is physical Android UI evidence for the debug relay path, but it still injects QR delivery through Android's VIEW intent and uses ADB reverse. It does not prove optical camera QR capture, production public relay allocation, direct P2P NAT traversal, or a production different-network route without debug tooling.

## 2026-06-28 macOS Runtime Data Status Cards

The latest evidence is no-device macOS model/store, localization, render, source, and script evidence:

- `CompanionAppModel` now shares explicit runtime chat and memory stores with `LocalRuntimeMessageRouter`, then publishes a runtime data summary for the app shell.
- Status now shows `Runtime History` and `Runtime Memory` cards with active chat, archived chat, enabled memory note, and paused memory note counts.
- Quick Actions includes `Refresh Runtime Data` to refresh runtime-owned chat and memory counts from the runtime host app.
- Latest focused store evidence: `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores` passed.
- Latest runtime-router evidence: `swift test --filter LocalRuntimeMessageRouterTests` passed.
- Latest localization evidence: `swift test --filter AetherLinkLocalizationTests/testLocalizedCountHelpersUseNaturalSingularAndPluralCopy` and `python3 script/check_macos_localization.py` passed.
- Latest localization suite evidence: `swift test --filter AetherLinkLocalizationTests` passed.
- Latest render evidence: `swift test --filter AetherLinkRenderSmokeTests/testPrimaryCompanionSurfacesRenderAtMinimumDetailSizeAcrossLanguagesAndAppearances` passed.
- Latest copy evidence: `python3 script/check_copy_hygiene.py` passed and requires the no-device coverage phrase `macOS runtime data status cards`.
- Latest documentation and shell hygiene evidence: `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-macos-runtime-data-status-cards.log 2>&1` passed with `No-device quality checks passed.` and included `macOS runtime data status cards`.
- Caveat: this does not prove live production client sync, optical QR scanning, physical Android haptics, production different-network routing, or live provider-backed chat/cancel.

## 2026-06-28 Android Settings QR Refresh Navigation And Device Relay Reconnect Smoke

The latest evidence includes focused Android no-device navigation tests plus physical Android install and development-relay reconnect smoke:

- Settings QR refresh for an already trusted runtime now stays in Settings instead of reusing the first-pairing onboarding return-to-chat behavior.
- First pairing, Chat-origin QR scanning, and pending-route QR recovery still use onboarding semantics through `shouldTreatPairingQrAsOnboarding`.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-settings-qr-refresh-navigation.log 2>&1` passed with `No-device quality checks passed.`
- Latest physical install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" script/android_usb_install.sh` passed on device `R3CXC0M76VM` / `SM_S936N`; it installed the debug APK and launched `com.localagentbridge.android/.MainActivity`.
- Latest physical relay evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect` passed with workdir `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.ImTVsA`.
- Runtime evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.ImTVsA/runtime.log` was produced by the same smoke and the script reported a second `runtime.health` after app relaunch.
- Relay evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.ImTVsA/relay.log` was produced by the same smoke.
- Screenshot evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.ImTVsA/aetherlink-pairing-smoke.png` shows the connected dark chat surface with `Dev Mock Streaming ...` and the bottom composer.
- Caveat: this smoke still injects the QR result through Android's VIEW intent and uses development relay plumbing with a connected debug device. It does not prove optical QR camera capture, production relay allocation, direct P2P NAT traversal, or a real different-network route without USB/debug tooling.

## 2026-06-28 Android QR Scanner Compact Pairing-State Render Smoke

The latest evidence is no-device Android Compose/resource/source/script evidence:

- `PairingQrScannerChromeNoDeviceComposeTest` now renders the QR scanner chrome at `320.dp` by `520.dp` across English, Korean, Japanese, Simplified Chinese, and French.
- The compact render smoke covers the active camera, permission-request, and settings-recovery states and asserts that the title, scan target, camera preview, flashlight action, guidance copy, permission/settings actions, and cancel action remain displayed where applicable.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest.scannerChromeRendersCompactPairingStatesAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Latest scanner matrix evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest -Pkotlin.incremental=false --console=plain` passed.
- Latest localization and guard evidence: `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-android-qr-scanner-compact-render.log 2>&1` passed with `No-device quality checks passed.` and included `Android QR scanner compact pairing-state render smoke`.
- Caveat: this does not prove optical camera QR capture, camera permission behavior on a physical device, TalkBack traversal, real device haptics, production different-network connectivity, or live provider-backed chat/cancel.

## 2026-06-28 macOS Active Pairing QR Compact Render Smoke

The latest evidence is no-device macOS AppKit/SwiftUI render, localization, source, and script evidence:

- `AetherLinkRenderSmokeTests` now renders an active `PairingView` QR card after creating a real active pairing session with `beginPairing(routePolicy: .allowLocalDiagnostic)`.
- The active QR card is rendered at compact detail size across English, Korean, Japanese, Simplified Chinese, and French in System, Light, and Dark appearances.
- Latest focused render evidence: `swift test --filter AetherLinkRenderSmokeTests/testActivePairingQRCodeRendersAtCompactDetailSizeAcrossLanguagesAndAppearances` passed.
- Latest render matrix evidence: `swift test --filter AetherLinkRenderSmokeTests` passed.
- Latest localization evidence: `swift test --filter AetherLinkLocalizationTests` and `python3 script/check_macos_localization.py` passed.
- Latest guard evidence: `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-active-pairing-qr-render.log 2>&1` passed with `No-device quality checks passed.` and included `macOS active Pairing QR compact render smoke`.
- Caveat: this does not prove live VoiceOver traversal, optical Android camera QR scanning, physical Android install, real device haptics, production different-network connectivity, or live provider-backed chat/cancel.

## 2026-06-28 Android Vision Model Picker Recovery And Device Relay Smoke

The latest evidence includes focused no-device Android Compose/resource checks plus a physical Android development-relay smoke:

- The chat model picker now exposes a localized vision-recovery state when an image is pending and the selected local runtime chat model is not vision-capable.
- Non-vision chat models are disabled in that recovery state and expose localized not-recommended-for-images copy; installed vision-capable local runtime chat models remain selectable.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerGuidesImageAttachmentVisionRecoveryAcrossSupportedLanguages' -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest hygiene evidence: `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-vision-model-picker-recovery.log 2>&1` passed with `No-device quality checks passed.`
- Latest physical-device relay evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect --expect-chat-cancel` passed with device `R3CXC0M76VM` / `SM_S936N` and workdir `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.G57EeC`.
- Runtime evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.G57EeC/runtime.log` observed a second `runtime.health` after relaunch plus `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done`.
- Relay evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.G57EeC/relay.log` was produced by the same smoke run.
- Screenshot evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.G57EeC/aetherlink-pairing-smoke.png` was captured after relaunch and reconnect.
- Caveat: this physical smoke still injects pairing through Android's VIEW intent and uses the development relay with a connected debug device. It does not prove optical QR capture, production relay allocation, direct P2P NAT traversal, or a production different-network route without USB/debug tooling.

## 2026-06-28 Physical Relay Reconnect Stability

The latest evidence includes a physical Android relay smoke plus targeted log/XML/screenshot checks:

- `RuntimeDevServer` keeps route-refresh relay clients alive until disconnect instead of stopping the previously active refreshed client during `route.refresh`.
- Latest build evidence: `swift build --product RuntimeDevServer` passed.
- Latest shell guard: `bash -n script/android_pairing_deeplink_smoke.sh` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed.
- Latest aggregate no-device evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-relay-reconnect-stability.log 2>&1` passed with `No-device quality checks passed.`
- Latest physical-device relay evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect --expect-chat-cancel` passed with workdir `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.l1w5SG`.
- Runtime evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.l1w5SG/runtime.log` shows the first `route.refresh`, first `runtime.health`, `models.list`, `chat.cancel`, `chat.done`, second `route.refresh`, second `runtime.health`, post-relaunch `models.list`, and `chat.suggestions.request`.
- Negative runtime evidence: targeted search for `relay status=stopped` in that runtime log returned no matches.
- UI evidence: targeted search for latest-QR recovery copy in `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.l1w5SG/*.xml` returned no matches, while connected-chat copy such as `Dev Mock Streaming`, `AetherLink_physical_cancel_smoke`, and `Generating next questions` was present.
- Screenshot evidence: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.l1w5SG/aetherlink-pairing-smoke.png` shows the connected chat surface rather than the latest-QR route recovery screen.
- Caveat: this smoke still injects the QR result through Android's VIEW intent and uses development relay plumbing with a connected debug device. It does not prove optical QR capture, production relay allocation, direct P2P NAT traversal, or a real different-network route without USB/debug tooling.

## 2026-06-28 Android Empty-State Latest-QR Composer Alignment

The latest evidence includes focused Android no-device tests plus physical install/foreground-launch/screenshot evidence:

- A disconnected trusted runtime with no connectable route now shows the latest-QR recovery empty state instead of the generic Connect empty state.
- The bottom composer hint remains aligned with the center call to action: both ask for the latest AetherLink Runtime QR before sending.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatComposerHintRequestsLatestQrWhenTrustedRuntimeNeedsRouteRefresh --tests com.localagentbridge.android.AppNavigationTest.emptyChatPrefersLatestQrWhenTrustedRuntimeHasNoConnectableRoute --tests com.localagentbridge.android.AppNavigationTest.emptyChatKeepsConnectActionWhenTrustedRuntimeHasConnectableRoute --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTrustedRuntimeWithoutConnectableRouteShowsLatestQrEmptyState -Pkotlin.incremental=false --console=plain` passed.
- Latest hygiene evidence: `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest physical-device evidence: `adb devices -l` reported `R3CXC0M76VM device ... model:SM_S936N`; `adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`; `adb shell monkey -p com.localagentbridge.android -c android.intent.category.LAUNCHER 1` injected the launch event; `adb shell dumpsys window` reported `mCurrentFocus` and `mFocusedApp` for `com.localagentbridge.android/.MainActivity`; `/tmp/aetherlink-device-latest-qr-aligned.png` shows the aligned latest-QR empty state and composer hint.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-empty-state-latest-qr-alignment.log 2>&1` passed and included `Android empty-state latest-QR composer alignment`.
- Caveat: this does not prove physical QR camera pairing, actual different-network runtime connectivity, physical TalkBack traversal, real device haptic feel, or physical/live-backend streamed chat/cancel.

## 2026-06-28 Android Trusted Runtime Forget Confirmation Named Message And Device Install

The latest evidence includes focused Android no-device tests plus physical install/foreground-launch evidence:

- The trusted-runtime forget confirmation body now names the runtime being removed and exposes the same localized message as accessibility description.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetRequiresConfirmation --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetActionNamesRuntimeAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest physical-device evidence: `adb devices -l` reported `R3CXC0M76VM device ... model:SM_S936N`; `adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk` returned `Success`; `adb shell pm path com.localagentbridge.android` returned a `/data/app/.../base.apk` path; `adb shell monkey -p com.localagentbridge.android -c android.intent.category.LAUNCHER 1` injected the launch event; `adb shell dumpsys window` reported `mCurrentFocus` and `mFocusedApp` for `com.localagentbridge.android/.MainActivity`.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-trusted-runtime-forget-named-message.log 2>&1` passed and included `Android trusted-runtime forget confirmation named message`.
- Caveat: this does not prove physical QR camera pairing, physical TalkBack traversal, real device haptic feel, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Share Import Haptics And Memory Delete Confirmation Context

The latest evidence is no-device Android JVM/Compose/resource/source/script evidence only:

- Android share-sheet imports now dispatch a lightweight primary-action haptic when shared text/files are staged into the chat draft.
- Memory deletion confirmation now names the exact memory content in the visible dialog body before removing it from the trusted runtime.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.sharedChatDraftConfirmationFeedbackUsesLightweightHaptic --tests com.localagentbridge.android.AppNavigationTest.sharedChatDraftConfirmationMessageMatchesImportedContentType --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsExposeContextualActionAccessibility -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-share-haptic-memory-message.log 2>&1` passed and included `Android share-sheet import haptic feedback` plus `Android memory delete confirmation named message`.
- Caveat: this does not prove physical share-sheet entry from real apps, real device haptics, physical Android install, camera QR scanning, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Diagnostic QR Text Open Action Labels

The latest evidence is no-device Android Compose/resource/source/script evidence only:

- The developer diagnostics QR text opener now exposes localized content-description and click-action semantics before opening the manual QR text dialog.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.diagnosticQrTextDialogExplainsEmptyInvalidAndReadyStates --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.diagnosticQrTextAccessibilityLabelsLocalizeAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-diagnostic-qr-open-labels.log 2>&1` passed and included `Android diagnostic QR text open action labels`.
- Caveat: this does not prove physical TalkBack traversal, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Share-Sheet Import Confirmation

The latest evidence is no-device Android JVM/resource/source/script evidence only:

- Android share-sheet imports now show localized confirmation snackbars after shared text/files are staged into the chat draft.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false --console=plain` passed.
- Latest compile evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `python3 script/check_macos_localization.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-share-confirmation.log 2>&1` passed and included `Android share-sheet import confirmation`.
- Caveat: this does not prove physical share-sheet entry from real apps, physical Android install, physical snackbar timing, physical haptics, camera QR scanning, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Menu-Bar Status Accessibility Labels

The latest evidence is no-device macOS SwiftUI/source/XCTest/script evidence only:

- Menu-bar runtime and model-service status lines now expose localized accessibility labels with explicit status context while preserving their compact visible text.
- Latest focused evidence: `swift test --filter AetherLinkLocalizationTests/testMenuBarStatusAndCommandTitlesUseSelectedLanguage` passed.
- Latest localization evidence: `python3 script/check_macos_localization.py` passed.
- Latest copy hygiene evidence: `python3 script/check_copy_hygiene.py` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-menu-status-accessibility.log 2>&1` passed and included `macOS menu-bar status accessibility labels`.
- Caveat: this does not prove live VoiceOver traversal, rendered menu-bar screenshots, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android QR Scanner Scan-Target Accessibility Label

The latest evidence is no-device Android Compose/resource/script evidence only:

- The active camera QR scanner frame now exposes a localized scan-target accessibility description and stable test tag.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest -Pkotlin.incremental=false --console=plain` passed.
- Latest localization evidence: `python3 script/check_android_string_parity.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_macos_localization.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-qr-scan-target-command-menu.log 2>&1` passed and included `Android QR scanner scan-target accessibility label`.
- Caveat: this does not prove physical TalkBack traversal, optical QR capture, physical Android install, camera permission behavior on device, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Command Menu Model-Provider Accessibility Parity

The latest evidence is no-device macOS SwiftUI/source/script evidence only:

- The command-menu `Check Model Providers` action now shares the localized accessibility value and hint used by the Status, toolbar, and menu-bar quick actions.
- Latest focused evidence: `swift test --filter AetherLinkLocalizationTests/testQuickActionAccessibilityUsesSelectedLanguage` passed.
- Latest localization evidence: `python3 script/check_macos_localization.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-qr-scan-target-command-menu.log 2>&1` passed and included `testQuickActionAccessibilityUsesSelectedLanguage`.
- Caveat: this does not prove rendered command-menu traversal, live VoiceOver output, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Connection Recovery Host Warning Accessibility Status

The latest evidence is no-device macOS SwiftPM and script evidence only:

- Connection Recovery saved-host warnings now expose a localized accessibility label with warning context, `Needs attention` status, and the warning message.
- Latest focused evidence: `swift test --filter AetherLinkLocalizationTests/testConnectionRecoveryHostWarningAccessibilityLabelUsesSelectedLanguageAndTone` passed.
- Latest localization evidence: `python3 script/check_macos_localization.py` passed.
- Latest copy hygiene evidence: `python3 script/check_copy_hygiene.py` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-connection-recovery-host-warning.log 2>&1` passed and included `macOS Connection Recovery host warning accessibility status`.
- Caveat: this does not prove live VoiceOver traversal, rendered warning screenshots, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Menu-Bar Window And Quit Accessibility Hints

The latest evidence is no-device macOS SwiftPM and script evidence only:

- Menu-bar `Open AetherLink` and `Quit` actions now expose localized help/accessibility hints.
- Latest focused evidence: `swift test --filter AetherLinkLocalizationTests/testMenuBarWindowAndQuitAccessibilityHintsUseSelectedLanguage` passed.
- Latest localization evidence: `python3 script/check_macos_localization.py` passed.
- Latest hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `python3 script/check_android_string_parity.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-menu-bar-window-quit-hints.log 2>&1` passed and included `macOS menu-bar window and quit accessibility hints`.
- Caveat: this does not prove live VoiceOver traversal, rendered menu-bar screenshots, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Activity Disclosure Focus And Android Settings State

The latest evidence is no-device macOS SwiftPM, Android Robolectric/Compose, and script evidence only:

- macOS Activity diagnostic rows keep the summary label on the summary text and leave the `Technical Details` disclosure as a separate accessibility control.
- Android permanent navigation rail and drawer footer `Settings` controls now expose a localized ready state in addition to localized click action labels.
- Latest focused macOS evidence: `swift test --filter 'AetherLinkLocalizationTests/testActivityTechnicalDetailsAccessibilityLabelUsesEventContext|AetherLinkLocalizationTests/testActivityTechnicalDetailsAccessibilityStateUsesSelectedLanguage|AetherLinkLocalizationTests/testActivityLogRowAccessibilityLabelIncludesLocalizedTone'` passed.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerSettingsFooterLocalizesActionSemanticsAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.permanentNavigationRailSettingsItemLocalizesActionSemantics -Pkotlin.incremental=false --console=plain` passed.
- Latest hygiene evidence: `python3 script/check_macos_localization.py`, `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-activity-disclosure-rail-settings.log 2>&1` passed and included `macOS Activity diagnostic disclosure separate focus`, `Android drawer Settings footer readiness state`, and `Android permanent rail Settings readiness state`.
- Note: one earlier full no-device run hit a transient timeout in `RuntimeClientViewModelRelayIntegrationTest.trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession`; the test passed when run alone, and the subsequent full no-device run passed with the log above.
- Caveat: this does not prove rendered VoiceOver or TalkBack traversal, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Activity List And Android Trusted Runtime Action Labels

The latest evidence is no-device macOS SwiftPM, Android Robolectric/Compose, and script evidence only:

- The macOS Activity list now exposes a localized list-level accessibility label and item-count value in addition to existing row-level labels.
- The Android first-step `Forget` trusted-runtime action now exposes a localized runtime-specific click action label, matching the existing confirm/cancel dialog action-label coverage.
- Latest focused macOS evidence: `swift test --filter AetherLinkLocalizationTests/testActivityLogListAccessibilitySummaryUsesSelectedLanguage` passed.
- Latest focused Android evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetActionNamesRuntimeAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Latest hygiene evidence: `python3 script/check_macos_localization.py`, `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Latest docs evidence: `python3 script/check_docs_hygiene.py` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-activity-list-forget-click.log 2>&1` passed and included `macOS Activity log list accessibility summary` plus `Android trusted-runtime forget named click label`.
- Caveat: this does not prove rendered VoiceOver or TalkBack traversal, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Provider Details Accessibility Localization

The latest evidence is no-device macOS SwiftPM and localization-script evidence only:

- Provider technical-details expanded/collapsed values and expand/collapse hints now come from the macOS localization bundles, not a hardcoded language switch.
- The strings are present for English, Korean, Japanese, Simplified Chinese, and French.
- Latest focused evidence: `swift test --filter AetherLinkLocalizationTests/testProviderStatusTechnicalDetailsAccessibilityStateUsesSelectedLanguage` passed.
- Latest localization evidence: `python3 script/check_macos_localization.py` passed.
- Latest hygiene evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-provider-details-localization.log 2>&1` passed and included `macOS provider technical-details accessibility state`.
- Caveat: this does not prove rendered VoiceOver traversal, physical Android install, camera QR scanning, physical haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 macOS Runtime Owner-Device History And Memory Scoping

The latest evidence is no-device macOS SwiftPM, documentation, and script evidence only:

- Runtime chat and memory JSONL events now persist optional `owner_device_id`, derived by the runtime from the authenticated trusted-device connection rather than from client payloads.
- Authenticated clients cannot list each other's runtime-owned chat sessions/messages or memory, cannot rename/archive/delete another trusted device's session, and `chat.send` injects only the memory scoped to the authenticated device owner.
- Legacy nil-owner store calls remain compatible for no-auth/development store reads, but authenticated device views do not mix in legacy unscoped events.
- `LocalRuntimeMessageRouterTests.testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory` verifies cross-device chat/memory isolation through the authenticated router path.
- `LocalRuntimeMessageRouterTests.testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice` verifies session/message listing and archive mutation scoping at the chat JSONL store.
- `LocalRuntimeMessageRouterTests.testRuntimeMemoryStoreScopesEntriesByOwnerDevice` verifies independent memory entries with the same id per trusted-device owner.
- Latest focused evidence: `swift test --filter 'LocalRuntimeMessageRouterTests/testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory|LocalRuntimeMessageRouterTests/testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreScopesEntriesByOwnerDevice'` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after the owner-device scoping guard was added.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Roadmap Tooling Boundary Docs Guard

The latest evidence is no-device documentation and script evidence only:

- `script/check_docs_hygiene.py` now has a `future-tools-runtime-only` contract.
- The contract requires docs to keep MCP and web search as roadmap/future features, not v0.1 client capabilities.
- The contract also requires docs to keep future MCP and web search execution on AetherLink Runtime or the runtime host, with the client remaining a controller UI instead of directly performing those tool actions.
- Latest focused evidence: `python3 script/check_docs_hygiene.py`, `python3 script/check_protocol_schema.py`, and `python3 script/check_copy_hygiene.py` passed after the guard was added.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change.
- Caveat: this does not implement MCP, web search, production tool permissions, physical Android install, camera QR scanning, real device haptics, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Runtime Identity Fallback File Permission Hardening

The latest evidence is no-device macOS SwiftPM and script evidence only:

- `FileRuntimeIdentityKeyStore` now treats the persisted runtime identity fallback as sensitive trust material. It creates or corrects the containing directory to `0700` and the identity JSON file to `0600`.
- Existing broad-permission fallback identity files are repaired before loading, so a valid existing identity is not rotated only because permissions were too broad.
- `RuntimeIdentityKeyStoreTests.testFileStoreLoadOrCreatePersistsRuntimeIdentity` verifies new fallback identity persistence plus owner-only file and directory permissions.
- `RuntimeIdentityKeyStoreTests.testFileStoreCorrectsBroadPermissionsWithoutRotatingIdentity` verifies `0644` file and `0755` directory permissions are corrected to `0600`/`0700` without changing the identity key.
- `script/check_copy_hygiene.py` and `script/check_no_device_quality.sh` now require this focused Swift coverage and the no-device summary label.
- Latest focused evidence: `swift test --filter 'RuntimeIdentityKeyStoreTests/testFileStoreLoadOrCreatePersistsRuntimeIdentity|RuntimeIdentityKeyStoreTests/testFileStoreCorrectsBroadPermissionsWithoutRotatingIdentity'` passed: 2 tests, 0 failures.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change.
- Caveat: this does not prove Keychain behavior, physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Runtime Event-Log File Permission Hardening

The latest evidence is no-device macOS SwiftPM and script evidence only because the Android phone was disconnected during this pass:

- `RuntimeEventLogFileProtection` now owns macOS runtime event-log file hardening. It creates or corrects the support directory to `0700`, creates JSONL event logs with `0600`, and reasserts `0600` on append to repair older broad-permission files.
- `JSONLRuntimeChatEventStore` and `JSONLRuntimeMemoryStore` both write through that helper, keeping runtime-owned chat processing logs and memory notes owner-readable only.
- `LocalRuntimeMessageRouterTests.testRuntimeChatEventLogIsCreatedWithOwnerOnlyPermissions`, `testRuntimeChatEventLogPermissionsAreCorrectedOnAppend`, `testRuntimeMemoryEventLogIsCreatedWithOwnerOnlyPermissions`, and `testRuntimeMemoryEventLogPermissionsAreCorrectedOnAppend` verify new-file and migration-style permission behavior.
- `script/check_copy_hygiene.py` now requires the shared helper, `0600`/`0700` constants, store routing through the helper, the focused Swift regressions, and the no-device coverage label.
- Latest focused evidence: `swift test --filter 'LocalRuntimeMessageRouterTests/testRuntimeChatEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogPermissionsAreCorrectedOnAppend'` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Share Intake and Relay Framing Hardening

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android now accepts shared text, image, and application document payloads through the platform share sheet. Shared text is merged into the chat composer, shared URI streams are routed through the existing attachment ingestion path, and the Android client still does not call model-provider endpoints directly.
- `AppNavigationTest.shareIntentTextBecomesChatDraftWithoutBackendAccess`, `shareIntentStreamsBecomeDistinctChatAttachments`, `shareIntentParserRejectsNonShareAndEmptyShareIntents`, and `sharedChatDraftComposerTextAppendsWithoutDroppingExistingDraft` verify the pure share-draft parser and composer merge behavior without requiring a physical phone.
- Android `route.refresh` authentication and pairing-required handling now replaces runtime-supplied detail with a fixed safe diagnostic string before it reaches `RuntimeUiState.error.technicalDetail`.
- `RuntimeClientViewModelTest.routeRefreshAuthenticationRequiredDoesNotRetainRouteMaterialTechnicalDetail` verifies route tokens, relay secrets, relay ids, and nonces are not retained after a route-refresh auth failure.
- The Swift development relay server now rejects relay handshakes and allocation requests that reach EOF without a trailing newline, and `RelayServerCoreTests` covers the fail-closed line-framing behavior.
- `script/check_copy_hygiene.py` and the aggregate no-device gate now require these contracts.
- Latest focused evidence: the Android share-sheet and route-refresh detail regression tests passed, and `swift test --filter RelayServerCoreTests` passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change.
- Caveat: this does not prove Android share-sheet integration from real apps, physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Streaming Route Lockout And Runtime Chat Semantic Validation

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android route/trust/connection controls now reject user-triggered mutations while a response is streaming and surface `generation_in_progress`.
- `RuntimeClientViewModelTest.streamingBlocksRuntimeRouteTrustAndConnectionMutations` verifies endpoint, pairing code, discovery, trust, connection, persisted reconnect, pending pairing route, and envelope state are preserved during streaming.
- macOS runtime chat history replay now rejects semantically invalid decoded JSONL events instead of returning partial history from a corrupt store.
- `LocalRuntimeMessageRouterTests.testRuntimeChatHistorySemanticallyInvalidEventReturnsStructuredError` verifies invalid chat request message roles return structured `chat_store_unavailable` errors for session and message history requests without leaking prior transcript text.
- `script/check_copy_hygiene.py` and the aggregate no-device gate now require these contracts.
- Latest focused evidence: the Android full `RuntimeClientViewModelTest` suite passed with Android Studio JBR, and the macOS semantic chat corruption, runtime chat history, and runtime chat store Swift filters passed.
- Latest static evidence: copy hygiene, docs hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-route-chat-semantic-final.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Stream Termination Reasoning Closure and Runtime Memory Semantic Validation

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android stream termination now closes the trailing active assistant reasoning state and clears any pending inline reasoning tag on `chat.done`, `chat.cancel`, active runtime error, and receive failure.
- `RuntimeClientViewModelTest.activeStreamTerminationClosesTrailingAssistantReasoningState` verifies the active assistant message keeps its answer and reasoning text, older assistant messages remain unchanged, and only the active trailing reasoning state closes.
- macOS runtime memory replay now validates decoded JSONL event semantics, so blank ids and blank upsert content are treated as corrupt log lines instead of being silently dropped.
- `LocalRuntimeMessageRouterTests.testRuntimeMemoryStoreReportsSemanticallyInvalidUpsertLine` verifies a decodable but blank-content upsert line returns `RuntimeMemoryStoreError.corruptEventLog(line:reason:)`.
- `script/check_copy_hygiene.py` and the aggregate no-device gate now require these contracts.
- Latest focused evidence: the Android stream-termination reasoning test passed, and the macOS runtime memory semantic corruption Swift test passed.
- Latest static evidence: copy hygiene and shell syntax checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-reasoning-memory-semantic-final.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Streaming Memory Mutation Guard and Runtime Memory Corrupt-Log Visibility

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android runtime memory add, remove, and enable/disable commands now reject while a response is streaming, preserve the current memory list, and surface `generation_in_progress` without sending `memory.upsert` or `memory.delete`.
- `RuntimeClientViewModelTest.streamingBlocksMemoryMutations` verifies active-generation memory mutations do not change local memory state or send runtime memory envelopes.
- macOS runtime memory JSONL storage now throws `RuntimeMemoryStoreError.corruptEventLog(line:reason:)` for corrupt non-empty lines instead of silently dropping them.
- `LocalRuntimeMessageRouterTests.testRuntimeMemoryStoreReportsCorruptJSONLLineInsteadOfDroppingIt` verifies the store reports the corrupt line and sanitizes the decode failure message.
- `LocalRuntimeMessageRouterTests.testRuntimeMemoryListCorruptStoreReturnsStructuredError` verifies `memory.list` returns `memory_store_unavailable` without leaking raw corrupt-line contents.
- `script/check_copy_hygiene.py` and the aggregate no-device gate now require these contracts.
- Latest focused evidence: the Android streaming memory mutation ViewModel test passed, and the two macOS runtime memory corruption Swift tests passed.
- Latest static evidence: copy hygiene and shell syntax checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-memory-guards-final.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Streaming Composer Input Guard and Runtime History Handler Empty Windows

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android `RuntimeClientViewModel.updateChatInput(...)` now rejects stale composer input callbacks while streaming, preserving the current draft and surfacing `generation_in_progress`.
- `RuntimeClientViewModelTest.updateChatInputRejectsWhileStreamingAndPreservesDraft` verifies a stale IME-style input change cannot mutate the draft during an active response.
- macOS runtime history protocol handlers now preserve `limit: 0` and negative limits as empty windows for `chat.sessions.list` and `chat.messages.list`, instead of coercing them to one item.
- `LocalRuntimeMessageRouterTests.testRuntimeChatHistoryHandlersReturnEmptyForNonPositiveLimitsWithoutReadingStore` verifies the router returns empty session/message payloads for nonpositive limits without reading a corrupt JSONL store.
- `script/check_copy_hygiene.py` and the aggregate no-device gate now require these contracts.
- Latest focused evidence: the Android streaming input/suggested-question ViewModel tests passed, and the macOS runtime history handler/store/corrupt-store Swift tests passed.
- Latest static evidence: copy hygiene and shell syntax checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-input-router-limit-20260628092723.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Suggested Question Streaming Lockout and Runtime History Zero-Limit Bypass

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android suggested-question chips now stay visible but disabled while a response is streaming. They expose a localized wait-for-stream state description, use muted visual treatment, and do not dispatch haptics or fill the composer.
- `RuntimeClientViewModelTest.useSuggestedQuestionRejectsWhileStreamingAndPreservesDraft` verifies a stale suggested-question callback during streaming returns `generation_in_progress` and preserves the current composer draft.
- `ClientScreensNoDeviceComposeTest.chatScreenStreamingSuggestedQuestionChipsAreDisabledAcrossSupportedLanguages` verifies the disabled chip semantics and localized state across English, Korean, Japanese, Simplified Chinese, and French.
- macOS runtime chat history zero and negative limits now return empty results before reading the JSONL log, so defensive empty-window requests do not surface corrupt-log errors.
- `LocalRuntimeMessageRouterTests.testRuntimeChatStoreZeroLimitsReturnEmptyWithoutReadingLog` verifies zero and negative session/message limits skip a corrupt JSONL file, while a positive limit still surfaces the corrupt-log error.
- `script/check_copy_hygiene.py` and the aggregate no-device gate now require these contracts.
- Latest focused evidence: the Android suggested-question ViewModel/Compose tests passed, and the macOS zero-limit/nonpositive-limit Swift tests passed.
- Latest static evidence: Android string parity, copy hygiene, shell syntax, and the no-device success-marker log check passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-suggestion-zero-limit-20260628091750.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Runtime History Limits and Route Cleanup Guards

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android runtime lifecycle acknowledgements now ignore Android-local chat sessions with colliding ids, so runtime `archive`, `restore`, or `delete` acknowledgements cannot mutate local-only history.
- `RuntimeClientViewModelTest.runtimeLifecycleAckDoesNotMutateLocalOnlySessionWithSameId` verifies delete, archive, and restore acknowledgements do not change a local-only session with the same id.
- Android trusted runtime restore no longer starts local discovery when a trusted relay route is already available; the stored relay route remains the reconnect target.
- `RuntimeClientViewModelTest.trustedRuntimeRestoreDoesNotStartDiscoveryWhenRelayRouteIsAvailable` verifies relay reconnect suppresses unnecessary discovery.
- Android route-refresh QR handling now verifies the unreachable-relay cleanup path. The failed relay route is removed from trusted runtime state, no pending pairing route remains, and the UI exposes `remote_route_unreachable` / `route_diagnostic_relay_failed` so the user can scan a fresh QR.
- `RuntimeClientViewModelTest.routeRefreshQrDropsUnreachableRelayRouteAndRequiresFreshQrRecovery` verifies the cleanup and error path.
- macOS runtime chat history limits now treat nonpositive `listSessions` and `listMessages` limits as empty windows instead of returning all stored history.
- `LocalRuntimeMessageRouterTests.testRuntimeChatStoreTreatsNonPositiveLimitsAsEmptyHistoryWindows` verifies `limit: 0` and `limit: -1` return no sessions/messages.
- `script/check_copy_hygiene.py` and the aggregate no-device gate now require these contracts.
- Latest focused evidence: the Android four-test runtime-history/route cleanup set passed, and the macOS attachment/history two-test set passed.
- Latest static evidence: Android string parity, macOS localization parity, docs hygiene, copy hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-runtime-history-limits-20260628090413.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Runtime-Owned History Cache and Attachment Storage Separation

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android runtime-owned chat message sync now only updates a session that still exists in the latest runtime-owned cache. A late `chat.messages.list` response for a session removed by `chat.sessions.list` no longer recreates the stale session or active message list.
- `RuntimeClientViewModelTest.runtimeMessagesDoNotResurrectSessionMissingFromLatestRuntimeSummary` verifies the stale runtime-owned session stays absent after a late message sync.
- macOS runtime chat routing now separates backend-visible augmented prompts from storage-visible history messages. Extracted document text is still sent to the backend, while stored runtime history keeps the original client-visible body and strips inline image/binary data from stored attachment metadata.
- `LocalRuntimeMessageRouterTests.testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment` verifies backend prompt augmentation and stored-history redaction in the same chat-send flow.
- `script/check_copy_hygiene.py` now requires the Android stale-message regression, the runtime-cache source guard, the macOS backend/storage split, and stored-message redaction assertions.
- Latest focused evidence: the Android stale runtime-owned message sync regression and macOS attachment/history routing regression passed.
- Latest static evidence: Android string parity, macOS localization parity, docs hygiene, copy hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-runtime-history-storage-20260628085202.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 QR Route Refresh and Saved Relay Lease Binding

The latest evidence is no-device Android JVM, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android route-refresh QR handling now accepts a valid latest QR for an already pinned runtime even when the QR omits `runtime_public_key` / `rk`. Device id and fingerprint still have to match, and the previously pinned public key is retained.
- `RuntimeClientViewModelTest.routeRefreshQrWithoutPublicKeyCanRefreshPinnedRuntimeRelayRoute` verifies the optional-public-key route-refresh path updates relay host/port/id/secret/lease/nonce while preserving the pinned runtime public key.
- macOS remote QR generation no longer restores a saved relay lease unless the lease was allocated for the current relay host, port, and route id.
- `LocalRuntimeMessageRouterTests.testCompanionAppModelDoesNotReuseSavedLeaseForDifferentRelayRoute` verifies stale saved lease metadata does not produce a QR and forces fresh route material before pairing.
- `script/check_copy_hygiene.py` now requires both route-refresh and saved-lease route-binding regressions.
- Latest focused evidence: the Android QR route-refresh test and macOS stale-lease regression passed.
- Latest static evidence: Android string parity, macOS localization parity, docs hygiene, copy hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after this change with log `/tmp/aetherlink-no-device-qr-route-refresh-lease-binding-20260628084120.log`.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Drawer Disabled Visual State And Connection Recovery Result Tone

The latest evidence is no-device Android Compose, macOS SwiftPM, and script evidence only because the Android phone was disconnected during this pass:

- Android previous-chat drawer rows that are locked during streaming now expose a visibly disabled alpha state while keeping the existing disabled semantics and localized wait-for-stream reason.
- The drawer disabled-row regression verifies five localized states and confirms a disabled row click does not select a chat or emit haptic feedback.
- macOS Connection Recovery result messages now expose localized ready/warning/pending tone in the accessibility label, rather than relying only on color and SF Symbol tone.
- `AetherLinkLocalizationTests.testConnectionRecoveryResultAccessibilityLabelUsesSelectedLanguageAndTone` verifies ready, warning, and fallback result labels across English, Korean, Japanese, Simplified Chinese, and French.
- Latest focused evidence: the Android drawer disabled-row Compose test and macOS Connection Recovery result accessibility XCTest passed.
- Latest static evidence: macOS localization parity, copy hygiene, shell syntax, and scoped diff whitespace checks passed after the guard updates.
- Caveat: this does not prove physical TalkBack or VoiceOver traversal, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 macOS Pairing QR Unavailable Accessibility Value

The latest evidence is macOS source/SwiftPM/script evidence only because the Android phone was disconnected during this pass:

- Pairing QR accessibility now uses the same QR generation result as rendering, so a failed QR image generation reports `Pairing QR code unavailable` instead of the scan-ready value.
- `pairingQRCodeAccessibilityValue(isExpired:isAvailable:)` verifies active, expired, and unavailable states without rendering SwiftUI.
- `AetherLinkLocalizationTests.testPairingQRCodeAccessibilityCopyUsesSelectedLanguageAndState` verifies the unavailable QR state across English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_macos_localization.py` and `script/check_copy_hygiene.py` now require the availability-aware QR accessibility wiring and focused localization regression.
- Latest focused evidence: `swift build --product AetherLink` and the focused Pairing QR localization test passed.
- Latest static evidence: macOS localization parity, copy hygiene, docs hygiene, shell syntax, scoped diff whitespace, and full diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove live VoiceOver traversal, rendered macOS screen capture, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer And Rename Dialog Action Labels

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Chat history row overflow buttons now expose contextual `Chat options for <title>` click action labels, including when disabled by an active stream.
- The rename chat dialog now exposes contextual `Confirm: Rename chat` and `Cancel: Rename chat` accessibility labels while keeping the visible button text compact.
- `ClientScreensNoDeviceComposeTest.chatDrawerDisabledItemsExplainStreamingLockoutAcrossSupportedLanguages` verifies the disabled overflow button action label and streaming lockout reason across English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.chatDrawerOverflowMenuActionsKeepChatContextAcrossSupportedLanguages` verifies the active overflow button action label and menu item labels across the same five languages.
- `ClientScreensNoDeviceComposeTest.renameChatSessionDialogExposesTitleReadinessAndHaptics` verifies rename title readiness plus contextual Save/Cancel labels.
- `script/check_copy_hygiene.py` now requires the source semantics wiring, focused Compose regressions, and no-device coverage labels for these actions.
- Latest focused evidence: the drawer disabled-overflow, drawer active-overflow, and rename-dialog regressions passed together.
- Latest static evidence: Android string parity, copy hygiene, docs hygiene, shell syntax, scoped diff whitespace, and full diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack action announcements, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android QR Scanner And Chat Action Labels

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- QR scanner top-bar close now exposes a contextual localized `Close QR scanner` accessibility label instead of sharing the generic bottom `Cancel` label.
- Chat jump-to-latest now exposes its localized `Jump to latest message` copy as an explicit accessibility click action label.
- Provider diagnostics toggles now expose contextual `Show details for <provider>` and `Hide details for <provider>` click action labels.
- `PairingQrScannerChromeNoDeviceComposeTest` verifies the scanner close label across English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.chatScreenJumpToLatestActionExplainsStateAcrossSupportedLanguages` verifies the jump-to-latest action label across supported app languages.
- `ClientScreensNoDeviceComposeTest.connectionStatusProviderDiagnosticsToggleExposesExpandedState` verifies provider diagnostics show/hide action labels for Ollama and LM Studio rows.
- `script/check_copy_hygiene.py` now requires the source semantics wiring, focused Compose regressions, and no-device coverage labels for these actions.
- Latest focused evidence: the QR scanner chrome, chat jump-to-latest, and provider diagnostics regressions passed together.
- Latest static evidence: Android string parity, copy hygiene, shell syntax, scoped diff whitespace, docs hygiene, and full diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack action announcements, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Settings Repeated Action Labels

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Settings route discovery controls now expose explicit localized click action labels for find/running/stop states while preserving their localized state descriptions.
- Settings Memory indexing model refresh now exposes the localized visible label as the accessibility action label across ready, loading, and disconnected states.
- Settings Memory `Add Memory` now exposes a localized action label across locked, empty, and ready states while keeping the existing readiness state description.
- Chat history bulk `Archive all chats` and `Permanently delete archived chats` controls now expose localized action labels, including when disabled by an active stream.
- `ClientScreensNoDeviceComposeTest.settingsDiscoveryActionsExplainIdleAndRunningStatesAcrossSupportedLanguages`, `settingsModelRefreshActionLocalizesReadinessStates`, `settingsMemoryAddControlsLocalizeReadinessStateAcrossSupportedLanguages`, and `settingsBulkChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages` verify the action-label behavior across English, Korean, Japanese, Simplified Chinese, and French where those tests already cover localization.
- `script/check_copy_hygiene.py` now requires the source semantics wiring, focused Compose regressions, and no-device coverage labels for these repeated Settings actions.
- Latest focused evidence: the four Android Settings action-label regressions passed together.
- Latest static evidence: Android string parity, copy hygiene, docs hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android no-device Compose tests, macOS localization/build tests, QR/relay smoke, model routing checks, document ingestion tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack action announcements, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Primary Action And Preference Action Labels

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Settings QR pairing `Scan QR`, Settings trusted-runtime `Connect`, Chat empty-state `Connect`/`Scan QR`, and backend-unavailable `Refresh health` now expose explicit localized click action labels instead of relying on generic click actions.
- Settings Appearance and Language radio rows now expose localized `Select ...` action labels while preserving their localized selected-state descriptions.
- `ClientScreensNoDeviceComposeTest.settingsPairingScanQrActionExplainsDisabledConnectingState`, `settingsPairingConnectActionExplainsDisabledConnectingState`, and `settingsPreferenceRowsExposeSelectedStateToAccessibility` verify Settings action labels and selected preference row semantics.
- `ClientScreensNoDeviceComposeTest.chatScreenBackendUnavailableBannerExposesAccessibilitySummaryAndRefreshCallback`, `chatScreenBackendUnavailableRefreshActionExplainsStateAcrossSupportedLanguages`, `chatScreenUntrustedRuntimeShowsQrFirstPairingCallToAction`, and `chatScreenConnectActionExplainsDisabledConnectingState` verify Chat/backend action labels and state descriptions.
- `script/check_copy_hygiene.py` now requires the source semantics wiring, new preference action string key, focused Compose regressions, and no-device coverage labels.
- Latest focused evidence: Settings and Chat/backend action-label regressions passed.
- Latest static evidence: copy hygiene, shell syntax, and scoped diff whitespace checks passed before the aggregate run.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack action announcements, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer Footer And Connected Action Labels

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android navigation drawer destination rows now expose explicit localized click action labels, including the footer Settings action.
- Android connected status actions now expose explicit localized click action labels for Refresh health and Disconnect, while preserving their localized readiness state descriptions.
- `ClientScreensNoDeviceComposeTest.navigationDrawerSettingsFooterLocalizesActionSemanticsAcrossSupportedLanguages` verifies the drawer Settings footer action label in English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.connectionStatusConnectedActionsExplainStateAcrossSupportedLanguages` verifies the connected Refresh/Disconnect action labels and state descriptions across English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_copy_hygiene.py` now requires the drawer destination action wiring, connected action-label wiring, focused Compose regressions, and no-device coverage labels.
- Latest focused evidence: both Android action-label regressions passed. The initial parallel Gradle run hit a test-results file `NoSuchFileException`, and the same drawer footer test passed when rerun by itself.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack action announcements, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer Empty History And Rail Settings Accessibility

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android navigation drawer empty-history copy now exposes the localized `No previous chats yet.` state as a polite live region.
- Android permanent navigation rail Settings item now exposes an explicit localized click action label across the five supported app languages.
- `ClientScreensNoDeviceComposeTest.navigationDrawerEmptyHistoryAnnouncesLocalizedLiveRegionAcrossSupportedLanguages` verifies the drawer empty-history state in English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.permanentNavigationRailSettingsItemLocalizesActionSemantics` verifies the large-screen Settings rail action label in English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_copy_hygiene.py` now requires the drawer empty-history source pattern, permanent rail Settings action wiring, focused Compose regressions, and no-device coverage labels.
- Latest focused evidence: both Android navigation accessibility regressions passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack announcement timing, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 macOS Provider Status Decorative Icon Accessibility

The latest evidence is macOS SwiftUI source/script evidence only because the Android phone was disconnected during this pass:

- macOS Model Providers status rows now hide their decorative status icon from assistive technologies.
- The provider row summary and provider status pill remain the accessible sources for provider name, status, and detail.
- `script/check_macos_localization.py` now requires the provider status icon source pattern and `.accessibilityHidden(true)` wiring.
- `script/check_copy_hygiene.py` now requires the macOS localization guard snippet and no-device coverage label.
- Latest focused evidence: macOS localization parity, copy hygiene, no-device shell syntax validation, and scoped diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove live VoiceOver traversal, rendered macOS screen capture, physical Android install, camera QR scanning, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Memory Empty-State Live Region

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android Settings Memory empty states now expose their localized disconnected and connected-empty copy as polite live regions.
- `ClientScreensNoDeviceComposeTest.settingsMemoryEmptyStatesAnnounceLocalizedLiveRegion` verifies `memory_empty_disconnected` and `memory_empty` across English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_copy_hygiene.py` now requires the Memory empty-state source pattern, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android Settings Memory empty-state live-region regression passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack announcement timing, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer Section Heading Accessibility

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android navigation drawer now exposes the visible `Previous chats` section label as a TalkBack heading.
- `ClientScreensNoDeviceComposeTest.navigationDrawerPreviousChatsLabelIsAHeadingAcrossSupportedLanguages` verifies the localized drawer section heading across English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_copy_hygiene.py` now requires the drawer section heading source pattern, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android drawer section heading accessibility regression passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack traversal order, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Critical QR Copy And Activity Label Polish

The latest evidence is Android/macOS source/JVM/Robolectric/XCTest/script evidence only because the Android phone was disconnected during this pass:

- Android Settings pairing copy now keeps the critical QR route detail and security note fully visible instead of truncating them with ellipsis.
- `ClientScreensNoDeviceComposeTest.settingsScreenRendersPairingCopyAcrossLaunchLanguages` verifies the QR detail and security note display across English, Korean, Japanese, Simplified Chinese, and French on a narrow settings surface.
- macOS Activity technical-details labels now strip terminal punctuation from event summaries before localized formatting, avoiding awkward punctuation before language particles.
- `AetherLinkLocalizationTests.testActivityTechnicalDetailsAccessibilityLabelUsesEventContext` verifies normal, punctuated, and fallback Activity detail labels across all five supported app languages.
- `script/check_copy_hygiene.py` now rejects ellipsis on critical Android QR route/security copy and requires the macOS Activity normalization wiring.
- `script/check_macos_localization.py` now requires the shared Activity summary normalization and terminal punctuation trimming set.
- Latest focused evidence: Android QR copy visibility regression and macOS Activity detail-label grammar regression passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical Android rendering, physical TalkBack or VoiceOver output, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Attachment-Only Composer Readiness

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android Chat composer attachment-only sends now expose a readiness state that includes the localized attachment count.
- The readiness state reuses the same localized plural count as the attachment button and appends it to the localized `Ready to send` state.
- `ClientScreensNoDeviceComposeTest.chatScreenSendButtonLocalizesReadinessStateAcrossSupportedLanguages` verifies the empty-message attachment-only path across English, Korean, Japanese, Simplified Chinese, and French for both the message field and send button.
- `script/check_copy_hygiene.py` now requires the source readiness wiring, localized resource, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android attachment-only composer readiness regression passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack announcement timing, physical Android install, physical file picker behavior, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Open Reasoning Collapsed Live Region

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android Chat keeps actively streaming assistant reasoning collapsed by default, matching the muted short thinking-preview policy.
- Actively open reasoning streams still expose a polite live region so assistive technology can receive streamed thinking updates separately from final answer content.
- Reasoning remains muted, compact, and collapsed by default unless the user expands it, whether the stream is still open or already complete.
- Manual user expansion remains local UI state and reveals the full thinking text on demand.
- `ClientScreensNoDeviceComposeTest.chatScreenKeepsOpenStreamingReasoningCollapsedUntilExpanded` verifies the open-streaming path shows the three-line preview, exposes `Collapsed`, `Show thinking`, and `LiveRegionMode.Polite`, suppresses the generic assistant typing placeholder while reasoning is open, then expands to the full reasoning text after user action.
- `script/check_copy_hygiene.py` now requires the collapsed-default source state, live-region wiring, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android open reasoning collapsed live-region regression passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, document ingestion tests, model routing tests, and runtime router tests.
- Caveat: this does not prove physical TalkBack announcement timing, physical Android install, camera QR scanning, real model reasoning streams, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Embedding Model Empty-State Live Region

The latest evidence is Android source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android Settings Memory indexing model empty states now expose their localized text as a polite live region.
- The disconnected state says the user must connect to the trusted runtime before choosing an embedding model.
- The connected-empty state says no memory indexing models are available from AetherLink Runtime.
- `ClientScreensNoDeviceComposeTest.settingsEmbeddingModelEmptyStatesAnnounceLocalizedLiveRegion` verifies both empty states across English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_copy_hygiene.py` now requires the source live-region wiring, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android embedding-model empty-state live-region regression passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including Android string parity, copy hygiene, docs hygiene, QR/relay smoke, Android no-device tests, macOS localization/render smoke, and runtime router tests.
- Caveat: this does not prove physical TalkBack announcement timing, physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 macOS Model Provider Empty-State Accessibility

The latest evidence is macOS source/XCTest/script evidence only because the Android phone was disconnected during this pass:

- macOS Status now renders a localized empty state when the model-provider list is empty instead of leaving the `Model Providers` panel blank.
- The empty state is localized across English, Korean, Japanese, Simplified Chinese, and French.
- The empty state exposes a merged VoiceOver label through `companionEmptyStateAccessibilityLabel`, matching the existing Models, Pairing, Trusted Devices, and Activity empty-state pattern.
- `AetherLinkLocalizationTests.testModelProviderEmptyStateAccessibilityLabelUsesSelectedLanguage` verifies the localized title/body accessibility summary across all five supported app languages.
- `script/check_macos_localization.py` now requires the provider empty-state title, description, `ContentUnavailableView`, and accessibility-label wiring in `StatusView`.
- Latest focused evidence: macOS model-provider empty-state accessibility regression passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after this change, including copy hygiene, docs hygiene, macOS localization parity, macOS render smoke, Android no-device checks, QR/relay smoke, and runtime router tests.
- Caveat: this does not prove physical Android install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Model Picker Empty-State Live Region

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android chat top-bar model picker empty states now render localized title plus detail instead of a single body line.
- `model_picker_empty_state_summary` is localized across English, Korean, Japanese, Simplified Chinese, and French, preserving locale-specific punctuation for the accessibility summary.
- The model picker empty-state container exposes the localized title/body summary as a merged polite live region.
- `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerEmptyStatesShowLocalizedTitleAndLiveRegion` verifies exact title/detail/summary resources for connected and disconnected empty states across all five supported app languages, and verifies rendered connected empty-state title/detail/live-region behavior.
- `script/check_copy_hygiene.py` now requires the model picker empty-state source pattern, focused Compose regression, summary resource, and no-device coverage label.
- Latest focused evidence: Android model picker empty-state live-region regression passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack announcement timing, physical install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Streaming Assistant Content Live Region

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android Chat now exposes the latest non-empty assistant reply as a polite live region while that reply is still actively streaming.
- The existing blank `Generating...` streaming placeholder remains covered separately; this pass covers the later state where actual assistant text has started arriving.
- The live region uses the localized `chat_message_accessibility_summary`, so TalkBack can announce the assistant role plus current streamed content instead of only the initial placeholder.
- `ClientScreensNoDeviceComposeTest.chatScreenStreamingAssistantContentAnnouncesLatestReplyAcrossSupportedLanguages` verifies the live-region behavior across English, Korean, Japanese, Simplified Chinese, and French and confirms the message copy long-click action remains present.
- `script/check_copy_hygiene.py` now requires the streaming assistant content source pattern, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android streaming assistant content live-region regression passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack announcement timing, physical install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Model Search No-Results Live Region

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android chat top-bar model picker search now exposes the localized model no-results state as a polite live region.
- Visible copy is unchanged; the dynamic `Try another model name, provider, service, or source.` state is now easier for TalkBack users to notice after a model search query changes.
- `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerSearchClearsWithContextAndHapticFeedback` verifies the English no-results live-region node and existing haptic/search clear interaction.
- `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerSearchLocalizesClearAndNoResultsAcrossSupportedLanguages` verifies localized model no-results resource copy and clear-action localization across English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_copy_hygiene.py` now requires the model-picker source pattern, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android model search no-results live-region regressions passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack announcement timing, physical install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Chat Search No-Results Live Region

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android navigation drawer previous-chat search and Settings Chat History search now expose the localized no-results state as a polite live region.
- Visible copy is unchanged; the dynamic `No matching chats.` state is now easier for TalkBack users to notice after a search query changes.
- `ClientScreensNoDeviceComposeTest.navigationDrawerChatSearchLocalizesClearAndNoResultsAcrossSupportedLanguages` verifies drawer no-results live-region behavior across English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.settingsChatHistorySearchLocalizesClearAndNoResultsAcrossSupportedLanguages` verifies Settings chat-history no-results live-region behavior across the same five languages.
- `script/check_copy_hygiene.py` now requires the drawer and Settings source patterns, focused Compose regressions, and no-device coverage label.
- Latest focused evidence: Android chat search no-results live-region regressions passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack announcement timing, physical install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Preference Group Heading Accessibility

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android Settings Preferences now exposes the visible `Appearance` and `Language` group labels as TalkBack headings.
- `ClientScreensNoDeviceComposeTest.settingsPreferenceGroupLabelsExposeHeadingSemanticsAcrossSupportedLanguages` verifies those localized headings across English, Korean, Japanese, Simplified Chinese, and French.
- `script/check_copy_hygiene.py` now requires the heading semantics source pattern, focused Compose regression, and no-device coverage label.
- Latest focused evidence: Android preference group heading accessibility regression passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack traversal order, physical install, camera QR scanning, real device haptics, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 macOS Destructive Confirmation Cancel Accessibility

The latest evidence is source/XCTest/script evidence only because the Android phone was disconnected during this pass:

- macOS Trusted Devices remove-trust confirmation now gives the visible `Cancel` action a contextual accessibility label containing the selected device and key fingerprint.
- macOS Connection Recovery saved-connection removal confirmation now gives both destructive confirm and cancel actions contextual accessibility labels tied to the saved endpoint or localized fallback.
- `Cancel removing trust for %@. Key fingerprint %@` and `Cancel removing saved connection details for %@` are localized across English, Korean, Japanese, Simplified Chinese, and French.
- `AetherLinkLocalizationTests.testTrustedDeviceCancelRemoveActionAccessibilityLabelUsesDeviceContext` verifies trusted-device cancel labels and fallbacks across all five supported app languages.
- `AetherLinkLocalizationTests.testCancelRemoveSavedConnectionDetailsAccessibilityLabelUsesRouteContext` verifies saved-connection cancel labels and fallbacks across all five supported app languages.
- `script/check_macos_localization.py` and `script/check_copy_hygiene.py` now require the new dialog helpers, localization keys, focused tests, and no-device coverage labels.
- Latest focused evidence: macOS destructive confirmation cancel regressions passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove live VoiceOver output, physical rendered screenshots, physical Android install, camera QR scanning, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 macOS Model Provider Row And Model Group Heading Accessibility

The latest evidence is source/XCTest/script evidence only because the Android phone was disconnected during this pass:

- macOS Model Providers rows now expose a localized provider-row accessibility summary containing provider name, status, and detail.
- `Provider %@. Status %@. %@` and `No provider details` are localized across English, Korean, Japanese, Simplified Chinese, and French.
- macOS model group headers now keep the existing localized `Model section ...` label and add the VoiceOver heading trait.
- `AetherLinkLocalizationTests.testProviderStatusRowAccessibilityLabelUsesProviderContext` verifies provider-row labels and fallbacks across all five supported app languages.
- `script/check_macos_localization.py` requires the provider-row helper, provider-row format, focused XCTest, and model-group heading trait.
- Copy hygiene now requires no-device coverage labels `macOS provider row accessibility summaries` and `macOS model group header heading trait`.
- Latest focused evidence: macOS provider-row accessibility regression passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove live VoiceOver output, physical rendered screenshots, physical Android install, camera QR scanning, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Suggested Questions And Memory Confirmation Accessibility

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android suggested next-question groups now expose a localized count summary as a polite live region, while individual chips keep contextual suggested-question labels and insert-action labels.
- `suggested_questions_state_count` plural copy is localized across English, Korean, Japanese, Simplified Chinese, and French.
- Android memory deletion confirmation now gives the visible cancel button a contextual accessibility label and click label tied to the memory being removed.
- `ClientScreensNoDeviceComposeTest.chatScreenSuggestedQuestionsAnnounceLocalizedCountAcrossSupportedLanguages` verifies the suggested-question count summary and chip action labels across all five supported app languages.
- `ClientScreensNoDeviceComposeTest.settingsMemoryRowsExposeContextualActionAccessibility` verifies the memory remove confirmation confirm/cancel labels and haptic sequence.
- Copy hygiene now requires the suggested-question count resource/source/test contract, the no-device coverage label `Android suggested-question count live-region accessibility`, and the contextual memory delete cancel contract.
- Latest focused evidence: Android suggested-question count and memory contextual action regressions passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack traversal order, physical install, camera QR scanning, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Composer Attachment Count Limit Accessibility

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android chat composer attachment action now announces the current pending attachment count and the maximum attachment limit through its accessibility state.
- The pending attachment limit is now a shared runtime constant, so ViewModel enforcement and composer accessibility copy use the same `MAX_PENDING_ATTACHMENTS` value.
- `attach_files_state_count` plural copy and `attach_files_state_limit_reached` are localized across English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.chatScreenAttachButtonAnnouncesAttachmentCountAndLimitAcrossSupportedLanguages` verifies the count state, limit-reached disabled state, and localized attach click label across all five supported app languages.
- Copy hygiene now requires the shared limit, plural resource usage, limit-reached resource usage, focused Compose regression, and no-device coverage summary label `Android composer attachment count limit accessibility`.
- Latest focused evidence: Android composer attachment count/limit accessibility regression passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack traversal order, physical install, camera QR scanning, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Message Role Accessibility Summaries

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android chat transcript rows now expose localized role-plus-message accessibility summaries for user and assistant messages.
- The same message semantic targets keep the localized long-click copy action, so the speaker summary does not remove message-copy accessibility.
- `chat_message_accessibility_summary` is localized across English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.chatScreenMessageRowsExposeLocalizedRoleAccessibilitySummaries` verifies user and assistant summaries plus copy long-click labels across all five supported app languages.
- Copy hygiene now requires the summary resource, source wiring, focused Compose regression, and the no-device coverage summary label `Android message role accessibility summaries`.
- Latest focused evidence: Android message role accessibility summary regression passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack traversal order, physical install, camera QR scanning, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Heading Accessibility Semantics

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android app, Settings, and QR scanner landmarks now expose heading semantics for the top app bar title, active chat title, QR scanner title, QR scanner permission title, reusable screen headers, Settings expandable section rows, Preferences title, and QR pairing panel title.
- `ClientScreensNoDeviceComposeTest.settingsScreenHeadersExposeHeadingSemanticsAcrossSupportedLanguages` verifies Settings headings across English, Korean, Japanese, Simplified Chinese, and French.
- Existing top-bar and QR scanner no-device regressions now assert heading semantics on their visible titles.
- Copy hygiene now requires heading imports/wiring, the focused Compose regressions, and the no-device coverage summary labels `Android screen heading semantics` plus `Android QR scanner heading semantics`.
- Latest focused evidence: Android heading semantics regressions passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack traversal order, physical install, camera QR scanning, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 macOS Header Heading Accessibility

The latest evidence is source/XCTest/script evidence only because the Android phone was disconnected during this pass:

- Shared macOS page headers now keep their localized title-plus-subtitle accessibility label and add the VoiceOver heading trait.
- Shared macOS panel headers now expose one localized heading label for repeated cards such as Readiness, Quick Actions, Model Providers, Models, Pairing QR, Allowed Devices, Advanced Connection Setup, and Activity.
- `AetherLinkLocalizationTests/testCompanionPanelHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks` verifies panel header label fallback and English, Korean, Japanese, Simplified Chinese, and French `Readiness` labels.
- `script/check_macos_localization.py` and `script/check_copy_hygiene.py` now require the page-header and panel-header heading traits, and the no-device quality summary names `macOS page header heading trait` plus `macOS panel header heading trait`.
- Latest focused evidence: `swift test --filter 'AetherLinkLocalizationTests/testCompanionPageHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks|AetherLinkLocalizationTests/testCompanionPanelHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks'` passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical VoiceOver navigation order, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer Runtime Summary Accessibility

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- The drawer runtime summary now exposes one localized accessibility summary for runtime name, connection status, selected model, and the missing-model recovery detail.
- `ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryShowsSavedMissingModelRecovery` verifies the summary content description across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene now requires the localized summary resources, `clearAndSetSemantics`, the focused Compose assertion, and the no-device coverage summary label `Android drawer runtime summary accessibility`.
- Latest focused evidence: Android `ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryShowsSavedMissingModelRecovery` passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack announcement order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer Chat Model Metadata

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android previous-chat drawer rows now show saved chat model metadata when available, matching the Settings history model display behavior.
- The selected drawer row accessibility summary now includes both selected-chat context and model metadata.
- `ClientScreensNoDeviceComposeTest.chatDrawerSearchMatchesModelAndRuntimeMetadata` verifies that searching by model id shows the matching row, displays `Model: Qwen3 8B`, and exposes the selected row summary with that model text.
- Copy hygiene now requires drawer model metadata wiring, the selected-with-model string resource, the focused Compose evidence, and the no-device coverage summary label `Android drawer chat model metadata`.
- Caveat: this does not prove physical TalkBack announcement order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Chat-History Confirmation Cancel Accessibility

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android two-step chat-history confirmations now give the visible `Cancel` button contextual accessibility labels for the exact pending action.
- `confirmation_cancel_action_named` is localized across English, Korean, Japanese, Simplified Chinese, and French, matching the existing contextual continue/final-confirm resources.
- `ClientScreensNoDeviceComposeTest.chatHistoryConfirmationActionLabelsLocalizeSubjectsAcrossSupportedLanguages` verifies the five-language cancel strings for bulk archive, bulk permanent delete, and single archived-chat permanent delete.
- `ClientScreensNoDeviceComposeTest.settingsScreenPerChatHistoryActionsUseConfirmationHaptics` verifies the actual dialog exposes `Cancel: Permanently delete chat Archived project chat` as both content description and click-action label at both confirmation steps.
- Copy hygiene now requires the cancel resource, semantic wiring, focused Compose evidence, and the no-device coverage summary label `chat history destructive confirmation and cancel action labels`.
- Caveat: this does not prove physical TalkBack announcement order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Settings Chat History Model Metadata

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android Settings chat-history rows now show localized model metadata when a saved session carries `modelId`.
- Row accessibility summaries include the same localized model phrase, so assistive tech can identify which model was used without reopening the chat.
- `ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeLocalizedModelMetadata` covers active and archived chats across English, Korean, Japanese, Simplified Chinese, and French, including fallback from `ollama:qwen2.5:7b` to `qwen2.5:7b`.
- Copy hygiene now requires the focused Compose test and the no-device coverage summary label `Settings chat history model metadata`.
- Latest focused evidence: Android `ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeLocalizedModelMetadata` passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer Saved Missing Model Recovery

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- The drawer runtime summary now shows a saved missing chat model name and the localized recovery message instead of falling back to `No model selected`.
- `ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryShowsSavedMissingModelRecovery` covers the connected-runtime missing-model state across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene now requires the focused Compose test and the no-device coverage summary label `Android drawer saved missing model recovery`.
- Latest focused evidence: Android `ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryShowsSavedMissingModelRecovery` passed.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Chat Top-Bar Saved Missing Model Recovery

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- The chat top-bar model picker keeps the closed button conservative when a saved chat model is missing, but the expanded menu now shows the saved missing model name and the recovery copy.
- `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerShowsSavedMissingChatModelRecovery` covers a connected runtime returning a different chat model list, refresh action availability, missing saved-model visibility, recovery copy, and replacing the saved model with an available chat model.
- Copy hygiene now requires the focused Compose test and the no-device coverage summary label `Android chat top-bar saved missing model recovery`.
- Latest focused evidence: Android `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerShowsSavedMissingChatModelRecovery` and `appTopBarKeepsNavigationModelPickerAndNewChatChrome` passed together.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android App Top-Bar Active Chat Shell Coverage

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- The full `AetherLinkTopAppBar` regression now verifies that the active chat title appears beside the model picker with the localized accessibility summary.
- The same shell test still preserves the ChatGPT-like chrome contract: navigation button, model picker near the sidebar action, New Chat action, chat-model-only picker content, and no visible generic composer placeholder copy.
- Latest focused evidence: Android `ClientScreensNoDeviceComposeTest.appTopBarKeepsNavigationModelPickerAndNewChatChrome` passed, and was re-run with the saved missing model recovery regression after the menu change.
- Latest aggregate evidence: the full `script/check_no_device_quality.sh` gate passed after this change.
- Caveat: this does not prove physical TalkBack order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Drawer Rich Chat Search

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android drawer chat search now reuses `filterChatHistorySessions`, matching the richer Settings history search behavior.
- Drawer search now matches model ids, runtime event names, finish reasons, error codes, and localized untitled-chat fallback text instead of only visible titles.
- `ClientScreensNoDeviceComposeTest.chatDrawerSearchMatchesModelAndRuntimeMetadata` covers model-id search, runtime error metadata search, and untitled fallback search from the drawer.
- Copy hygiene now requires the focused Compose test and the no-device coverage summary label `Android drawer rich chat search`.
- Latest focused evidence: the drawer rich-search Compose regression passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed.
- Caveat: this does not prove physical TalkBack order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Chat Top-Bar Active Chat Title

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- Android now shows the active chat title in the chat top bar beside the model picker, with a compact ellipsized label.
- `chat_top_bar_active_title_summary` localizes the title accessibility summary across English, Korean, Japanese, Simplified Chinese, and French.
- `ClientScreensNoDeviceComposeTest.chatTopBarShowsActiveChatTitleAndLocalizedFallback` covers a real active title, preserves model-picker interaction, and verifies the legacy `New chat` title falls back to each locale's untitled-chat label instead of showing raw placeholder text.
- Copy hygiene now requires `ClientScreensNoDeviceComposeTest.chatTopBarShowsActiveChatTitleAndLocalizedFallback`.
- The no-device quality gate now includes the focused active-title Compose regression in the Android test selection.
- Copy hygiene also requires the no-device coverage summary label `Android chat top-bar active chat title`.
- Latest focused evidence: the active-title Compose regression passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed.
- Caveat: this does not prove physical TalkBack order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Chat Model Refresh Menu Accessibility

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- The chat top-bar model menu `Refresh models` row now exposes localized ready, loading, and disconnected/connect-first state descriptions.
- `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerRefreshRowLocalizesReadinessStates` covers English, Korean, Japanese, Simplified Chinese, and French refresh-row labels, state descriptions, enabled state, and click action labels.
- Copy hygiene now requires the refresh-row regression and the no-device coverage summary names `Android chat top-bar model refresh action accessibility state`.
- The full no-device quality gate passed after adding the chat top-bar model refresh row state regression to the default `ClientScreensNoDeviceComposeTest` run and coverage summary.
- Caveat: this does not prove physical TalkBack order, physical haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Chat Top-Bar And Route Notice Polish

The latest evidence is source/JVM/Robolectric/script evidence only because the Android phone was disconnected during this pass:

- The chat top-bar model picker no longer renders a stale saved model id such as `dev-mock` as the visible active model when the app is disconnected and no model list is being restored.
- `AppNavigationTest.chatModelPickerClosedLabelHidesSavedModelWhenDisconnectedAndNotRestoring` covers the helper-level fallback to `Choose model`.
- `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerDoesNotShowStaleSavedModelWhenDisconnected` covers the rendered top-bar chip content description, disconnected state, action label, and absence of stale saved-model text.
- `ClientScreensNoDeviceComposeTest.chatScreenRouteAvailabilityNoticeExposesStateAndAction` covers the compact chat route-recovery notice merged content description, `Refresh needed` state, `Scan latest QR` action label, polite live region, click behavior, and haptic dispatch.
- Copy hygiene now requires these regressions and the no-device coverage summary names `Android chat top-bar stale saved model suppression`.
- The full no-device quality gate passed after adding the stale saved-model suppression and compact route-notice accessibility regressions to the default coverage summary.
- Caveat: this does not prove physical rendering, real haptic feel, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-27 Android Attachment-Only Prompt Resource Localization

The latest evidence is source/unit/script evidence plus physical-device install/launch:

- Android now resolves the attachment-only prompt header from `R.string.attachment_only_prompt_header` using the selected app language.
- English, Korean, Japanese, Simplified Chinese, and French resource files all carry the prompt header key.
- `RuntimeAttachmentPromptResourceTest.attachmentOnlyPromptHeaderUsesLocalizedAndroidResources` covers resource-backed headers.
- `RuntimeClientViewModelTest.attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback` covers prompt formatting and fallback behavior.
- `RuntimeClientViewModelTest.attachmentOnlySendUsesSelectedLanguagePromptInChatSendPayload` covers the actual Korean `chat.send` payload for a blank message with an attachment.
- Copy hygiene now requires the resource helper, the string key, and the default no-device summary label `Android attachment-only prompt resource localization`.
- The default no-device quality gate passed after adding the prompt resource regression to the test selection.
- A fresh debug APK was built, installed on connected device `R3CXC0M76VM`, and launched as `com.localagentbridge.android/.MainActivity`; adb reported the package process alive and `MainActivity` as top resumed.
- Caveat: this does not prove a physical optical QR scan, real different-network runtime connectivity, live model streaming/cancel, or real haptic feel on the device.

## 2026-06-27 macOS First-Run Pairing QR Primary Action Ordering

The latest evidence is source/SwiftPM/script evidence only:

- macOS now uses a shared `CompanionPrimaryAction` order for toolbar and menu-bar primary actions.
- When there are no trusted devices, the order is `Generate Pairing QR`, provider refresh, then model loading.
- When trusted devices exist, the order remains provider refresh, model loading, then Pairing QR.
- Focused Swift coverage verifies the first-run and trusted-device action orders.
- macOS localization parity, copy hygiene, and the no-device coverage summary now require `macOS first-run Pairing QR primary action ordering`.
- Latest focused evidence: the primary action-order regression passed, macOS localization parity passed, copy hygiene passed, and no-device shell syntax validation passed.
- Not covered: rendered toolbar/menu screenshots, physical VoiceOver ordering, optical camera QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android First-Run Language Picker Before Pairing

The latest evidence includes source/Robolectric/script evidence plus physical install/launch evidence on `SM_S936N`:

- Android Settings now renders the language selector before pairing/status content when no trusted runtime exists.
- The regular Preferences card still contains appearance settings, but does not duplicate the language selector during the first-run pairing state.
- Focused Compose coverage verifies that `Language`, `English`, and `한국어` are visible before `Pair AetherLink` in a clean first-run `RuntimeUiState`.
- The same test keeps the five native language labels visible across supported launch languages and verifies that selecting Korean dispatches `onSetLanguageTag("ko")`.
- Copy hygiene and the no-device coverage summary now require `Android first-run language picker before pairing`.
- Latest focused evidence: the Android first-run language picker regression passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed.
- Physical device evidence: the latest debug APK installed on `SM_S936N`, `pidof` returned `28552`, Android app-locales reported `[en]`, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Not covered: destructive fresh-install verification on the physical phone, physical TalkBack announcement order, optical camera QR scanning, physical haptic feel, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Permanent Rail Chat Pairing Gate And Physical Launch Check

The latest evidence includes source/Robolectric/resource/script evidence plus physical install/launch evidence on `SM_S936N`:

- Android wide-layout permanent rail now keeps `Chat` disabled before a trusted runtime exists and exposes the localized pairing-required state.
- The same rail destination exposes a localized ready state and becomes clickable after trust exists.
- Focused Compose coverage verifies both pre-trust disabled semantics and post-trust click behavior.
- English, Korean, Japanese, Simplified Chinese, and French resources include the new ready-state string.
- Copy hygiene and the no-device coverage summary now require `Android permanent rail Chat pairing gate`.
- Physical device evidence: `SM_S936N` was detected by ADB, the latest debug APK installed successfully, `pidof` returned `27906`, Android app-locales reported `[en]`, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- The latest physical launch screenshot is `.codex-artifacts/android-language-sync-launch.png`; it shows a saved `dev-mock` trusted runtime state, so it proves latest launch/language/connection-gate state, not a clean first-run pairing screen.
- Not covered: optical camera QR scanning, first-install onboarding, real TalkBack announcement order, physical haptic feel, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android OS App-Language Sync From In-App Preferences

The latest evidence is source/unit/script evidence only:

- Android app-language startup now performs OS app-language reconciliation first, then synchronizes the selected AetherLink language back to Android 13+ `LocaleManager.applicationLocales`.
- The sync policy normalizes supported aliases and region-qualified tags before comparing the current OS app-language value with the selected in-app language.
- Focused unit coverage verifies that `null`, unsupported, matching, and mismatched language tags produce the expected synchronization decisions.
- Android string parity now requires the synchronization helper, `LocaleList.forLanguageTags(...)` assignment path, startup ordering guard, and focused shell regression test.
- Latest focused evidence: the new `AppNavigationTest.androidSystemAppLanguageSyncNormalizesCurrentAndSelectedTags` passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed.
- Not covered: physical Android Settings app-language UI state, real Activity recreation behavior after changing the OS app-language value, physical TalkBack output, camera QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Relay Route Failure Cleanup And QR Relay Smoke

The latest evidence includes focused no-device unit coverage, physical install/launch evidence on `SM_S936N`, and a USB-reversed development relay smoke:

- Android trusted-runtime reconnect now strips failed saved relay route material after `remote_route_unreachable` / `route_diagnostic_relay_failed`, while preserving the trusted runtime identity.
- Android no longer starts local discovery when a valid relay route is already present, preventing discovery state updates from clearing the structured relay failure recovery message.
- Focused ViewModel coverage verifies persisted relay cleanup and no retry after a saved relay route fails from the current network.
- The updated debug APK installed and launched on `SM_S936N`; `pidof` returned `24585`, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- `script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect` passed. The development smoke injected the QR URI, paired through the relay route, observed `runtime.health`, force-stopped and relaunched the app, then observed a second `runtime.health` from the saved trusted relay route.
- Physical screen capture after the fix was saved outside committed artifacts at `.codex-artifacts/android-after-relay-route-fix.png`; the device/runtime state was an installed debug app on `SM_S936N` after force-stop/relaunch with no public external relay configured.
- Not covered: optical camera QR scanning, production relay allocation, public internet reachability, live provider streaming/cancel in this run, and true real different-network runtime connectivity. Real different-network use still needs a relay, tunnel, VPN, or future private overlay endpoint reachable from both devices.

## 2026-06-27 Android Chat Model Picker Closed-State Accessibility

The latest evidence is source/Robolectric/resource/script evidence only:

- Android Chat top-bar model picker pills now expose a localized content description plus click action label while preserving the existing visible compact pill.
- Selected-model accessibility copy avoids duplicate model-name announcements, while streaming-disabled copy continues to explain that the current response must finish or be canceled before changing models.
- English, Korean, Japanese, Simplified Chinese, and French resources all include the new closed-picker summary strings.
- Focused Compose coverage verifies selected-model summaries, disabled streaming summaries, state descriptions, click labels, and five-language localization.
- Copy hygiene and the no-device coverage summary now require `Android chat top-bar model picker closed-button accessibility summary`.
- Latest focused evidence: Android model-picker regressions passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed.
- Not covered: physical TalkBack announcement order, physical haptic feel, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Trusted Device Confirm-Remove Accessibility

The latest evidence is source/SwiftPM/localization/script evidence only:

- macOS Trusted Devices confirmation dialogs now keep the visible final action short, while exposing a contextual accessibility label for the destructive confirm-remove action.
- The label includes the selected trusted device name and key fingerprint, with localized fallback copy when the pending device is absent.
- English, Korean, Japanese, Simplified Chinese, and French resources all include the new confirm-remove action accessibility string.
- Focused localization coverage verifies the final confirm-remove action label across all five supported macOS languages.
- Copy hygiene, macOS localization parity, and the no-device summary now require `macOS trusted-device confirm-remove action accessibility labels`.
- Latest focused evidence: `AetherLinkLocalizationTests/testTrustedDeviceConfirmRemoveActionAccessibilityLabelUsesDeviceContext` passed, macOS localization parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, shell syntax validation for the no-device quality gate passed, and the full no-device quality gate passed.
- Not covered: physical VoiceOver navigation order, real trusted-device removal in a running window, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Route Notice Accessibility Summaries

The latest evidence includes source/Robolectric/resource/script evidence plus physical install/launch evidence on `SM_S936N`:

- Android connection route notice cards now expose one merged accessibility summary containing the localized title, current route state, and visible route guidance.
- The same cards still expose localized click-action labels for `Connect trusted route` and `Scan latest QR`, and the focused tests verify callback routing plus haptic dispatch.
- English, Korean, Japanese, Simplified Chinese, and French resources all include the new route notice accessibility summary format.
- Copy hygiene and the no-device coverage summary now require `Android route notice accessibility summaries`.
- Latest focused evidence: Android route notice regressions passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, `:app:assembleDebug` passed, the full no-device quality gate passed, and the latest APK installed and launched on `SM_S936N`.
- Physical device evidence: `SM_S936N` was detected by ADB, `adb install -r` returned `Success`, `pidof` returned `22583`, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Not covered: real TalkBack announcement order, physical haptic feel, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Diagnostic QR Text Accessibility Labels

The latest evidence is source/Robolectric/resource/script evidence only:

- Android Settings still keeps diagnostic QR text behind Developer routes, while the dialog now exposes contextual accessibility labels for the input, submit, and cancel controls.
- The submit button keeps the visible text `Use QR text`, but assistive tech receives `Use diagnostic QR text`; the cancel action receives `Close diagnostic QR text`.
- Focused Compose coverage verifies the input label, submit click label, cancel click label, and empty/invalid/ready state descriptions.
- Resource coverage verifies the new accessibility-only labels across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene and the no-device coverage summary now require `Android diagnostic QR text contextual action labels`.
- Latest focused evidence: Android diagnostic QR text regressions passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed.
- Not covered: physical TalkBack output, real device haptics, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Connection Recovery Diagnostic Accessibility

The latest evidence is source/SwiftPM/script evidence only:

- macOS Connection Recovery diagnostic disclosures now use the localized accessibility context `Connection Recovery result` instead of the stale `Connection setup result`.
- English, Korean, Japanese, Simplified Chinese, and French resources all include the new localized context.
- Focused localization coverage verifies the route diagnostic disclosure label for the new Connection Recovery result context across all five supported languages.
- The macOS localization guard now requires the new context key and source snippet.
- Latest focused evidence: `AetherLinkLocalizationTests/testRouteDiagnosticDisclosureAccessibilityLabelUsesConnectionContext` passed, macOS localization parity passed, copy hygiene passed, docs hygiene passed, the full `AetherLinkLocalizationTests` filter passed, and whitespace diff checks passed.
- Not covered: physical VoiceOver navigation order, optical QR scanning, physical Android pairing, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Physical QR/Relay Smoke

The latest physical Android smoke includes QR-result/deeplink pairing, chat streaming, cancel, and saved-route reconnect evidence on `SM_S936N`:

- `script/android_pairing_deeplink_smoke.sh --relay --expect-chat-cancel --expect-reconnect` passed.
- Runtime logs observed successful pairing, `runtime.health`, `chat.send`, streamed `chat.delta`, `chat.cancel`, `chat.done`, app relaunch, and a second `runtime.health` from the saved trusted relay route.
- The Android UI was driven physically through ADB input for message entry, send, and cancel generation.
- Latest screenshots were copied to `artifacts/aetherlink-physical-pairing-smoke.png` and `artifacts/aetherlink-physical-chat-cancel-smoke.png`.
- Current app evidence after the smoke: `pidof` returned `21163`, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused.
- Not covered: optical camera QR scanning, real TalkBack announcement order, physical haptic feel, live provider streaming/cancel, and real different-network runtime connectivity. This smoke used `adb reverse`; a real different-network run still needs a relay, tunnel, VPN, or future private-overlay endpoint reachable from both devices.

## 2026-06-27 Android Memory Delete Confirmation Accessibility

The latest evidence includes source/Robolectric/script evidence plus physical install/launch evidence on `SM_S936N`:

- Android Memory entry delete confirmation now gives the final `Delete` button a contextual accessibility label matching the memory item being removed.
- Focused no-device Compose coverage verifies the contextual content description and click-action label on the delete confirmation button while preserving the existing haptic flow assertions.
- Copy hygiene and the no-device coverage summary now require `Settings memory delete confirmation action labels`.
- Latest focused evidence: Android Memory confirmation regression passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, `:app:assembleDebug` passed, and the full no-device quality gate passed.
- Physical device evidence: `SM_S936N` was detected by ADB, the debug APK installed successfully with `adb install -r`, `pidof` returned `19882`, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused after launch.
- Not covered: real TalkBack announcement order, physical haptic feel, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Reasoning And Chat-History Confirmation Accessibility

The latest evidence includes source/Robolectric/script evidence plus physical install/launch evidence on `SM_S936N`:

- Android assistant reasoning rows now merge the label, toggle, preview, and decorative children into one accessibility element while preserving the short dim collapsed preview and expandable full thinking text.
- Android chat-history two-step confirmation buttons keep compact visible labels, but expose contextual accessibility action labels for bulk archive, bulk permanent delete, and single archived-chat permanent delete flows.
- Focused no-device Compose/resource coverage verifies the destructive confirmation labels and five-language string formatting across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene and the no-device coverage summary now require `chat history destructive confirmation and cancel action labels`.
- Latest focused evidence: Android reasoning regressions passed, Android chat-history confirmation regressions passed, Android string parity passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed.
- Physical device evidence: `SM_S936N` was detected by ADB, `:app:assembleDebug` passed, the debug APK installed successfully with `adb install -r`, `pidof` returned `19015`, and `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused after launch.
- Not covered: real TalkBack announcement order, physical haptic feel, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Route-Recovery Empty-State Live Region

The Android phone was connected during this pass. The latest evidence includes source/Robolectric/script evidence plus physical install/launch evidence on `SM_S936N`:

- Android Chat now exposes the QR route-recovery empty-state title and body as one accessibility summary when the saved route is unreachable and the user must scan the latest QR.
- The route-recovery summary uses `LiveRegionMode.Polite`, while the `Scan latest QR` button remains a separate action.
- Focused no-device Compose coverage verifies the localized summary across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene and the no-device coverage summary now require `Android route-recovery empty-state live-region accessibility`.
- Physical device evidence: `SM_S936N` was detected by ADB, `:app:assembleDebug` passed, the debug APK installed successfully with `adb install -r`, `monkey` launched `com.localagentbridge.android`, `pidof` returned `18023`, `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused, UIAutomator pulled `artifacts/aetherlink-window-route-recovery-live-region.xml`, and the latest screenshot is `artifacts/aetherlink-route-recovery-live-region.png`.
- The UI dump includes the merged route-recovery content description `Scan latest QR. This network cannot reach the saved route. Prepare a reachable connection route in AetherLink Runtime, then scan the latest QR.`
- Not covered: real TalkBack announcement timing, physical haptic feel, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Composer Readiness Live Region

The Android phone was connected during this pass. The latest evidence includes source/Robolectric/script evidence plus physical install/launch evidence on `SM_S936N`:

- Android Chat now exposes the visible composer readiness/status row as one polite live region. The row merges the decorative dot and text into one accessibility element and uses the same localized status text as its content description.
- Focused no-device Compose coverage verifies the selected-model readiness status across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene and the no-device coverage summary now require `Android composer readiness live-region accessibility`.
- Physical device evidence: `SM_S936N` was detected by ADB, `:app:assembleDebug` passed, the debug APK installed successfully with `adb install -r`, `monkey` launched `com.localagentbridge.android`, `pidof` returned a running app process, `dumpsys window` reported `com.localagentbridge.android/.MainActivity` as focused, and UIAutomator pulled `artifacts/aetherlink-window-connected.xml`.
- The UI dump includes the current QR-recovery/chat surface, including `Scan latest QR`, `dev-mock`, `New Chat`, and the composer status content description `Scan the latest AetherLink Runtime QR before sending.`
- Not covered: real TalkBack announcement timing, physical haptic feel, optical QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Pairing QR Image Accessibility Element

The Android phone was disconnected during this pass. The latest evidence is source/SwiftPM/script evidence only:

- macOS active pairing QR now collapses its generated child QR image into one stable accessibility element.
- The QR element keeps image semantics and exposes the localized pairing QR label, active/expired value, and pairing/route-expiry hint from testable helper functions.
- Focused localization coverage verifies the QR label, value, hint, and route-expiry hint across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene and the no-device coverage summary now require `macOS Pairing QR image accessibility element`.
- Latest focused evidence: macOS `AetherLinkLocalizationTests/testPairingQRCodeAccessibilityCopyUsesSelectedLanguageAndState` passed, along with copy hygiene, macOS localization, docs hygiene, no-device shell syntax validation, scoped whitespace diff checks, and the full no-device quality gate.
- Not covered: physical VoiceOver navigation order, optical QR scanning, physical Android pairing, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Generating Suggestions Live Region

The Android phone was disconnected during this pass. The latest evidence is source/Robolectric/script evidence only:

- Android Chat now exposes the visible generating-suggestions row as a polite live region when AetherLink is generating suggested next questions and no suggestion chips have arrived yet.
- The live-region content description uses the localized `generating_suggestions` string across English, Korean, Japanese, Simplified Chinese, and French.
- Focused no-device Compose coverage verifies the visible generating-suggestions row and `LiveRegionMode.Polite` semantics across all five supported Android locales.
- Copy hygiene and the no-device coverage summary now require `Android generating suggestions live-region accessibility`.
- Latest focused evidence: Android `ClientScreensNoDeviceComposeTest.chatScreenGeneratingSuggestionsRowAnnouncesAcrossSupportedLanguages` passed, along with copy hygiene, Python compile, no-device shell syntax validation, docs hygiene, scoped whitespace diff checks, and the full no-device quality gate.
- Not covered: physical Android install, real TalkBack announcement timing, physical haptics, camera QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Streaming Assistant Live Region

The Android phone was disconnected during this pass. The latest evidence is source/Robolectric/script evidence only:

- Android Chat now exposes the visible assistant streaming placeholder as a polite live region while a blank assistant response is actively streaming.
- The live-region content description uses the localized `assistant_typing` string instead of hard-coded English.
- Focused no-device Compose coverage verifies the visible placeholder and `LiveRegionMode.Polite` semantics across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene and the no-device coverage summary now require `Android streaming assistant live-region accessibility`.
- Latest focused evidence: the focused Android Compose streaming-placeholder accessibility regression passed, along with copy hygiene, Android string parity, docs hygiene, whitespace diff checks, and the full no-device quality gate.
- Not covered: physical Android install, real TalkBack announcement timing, physical haptics, camera QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Relay Secret Store Boundary

The Android phone was disconnected during this pass. The latest evidence is source/SwiftPM/script evidence only:

- macOS runtime relay secrets now persist through `CompanionRelaySecretStoring` and the default `KeychainCompanionRelaySecretStore`.
- Relay settings store `aetherlink.relay.secret_ref` in `UserDefaults` and remove the legacy raw `aetherlink.relay.secret` key after save or migration.
- Bootstrap relay settings store `aetherlink.bootstrap_relay.allocation_token_ref` in `UserDefaults` and remove the legacy raw bootstrap allocation-token key after save or migration.
- Existing valid legacy relay secrets and bootstrap allocation tokens migrate into the injected secret store on first load, then are removed from raw defaults.
- Focused macOS regressions cover saved relay settings, regenerated relay secrets, bootstrap settings, restored QR leases, and expired-lease renewal with secret-ref storage.
- Copy hygiene and the no-device coverage summary now require `macOS relay secret store boundary`.
- Latest focused evidence: macOS `LocalRuntimeMessageRouterTests` focused relay/bootstrap secret-store regressions passed, copy hygiene passed, docs hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed after this update.
- Not covered: physical Android install, optical QR scanning, physical Keychain behavior in a signed app bundle, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Relay Secret Store Boundary

The Android phone was disconnected during this pass. The latest evidence is source/JVM/SwiftPM/script evidence only:

- Android trusted-runtime DataStore now stores `runtime_relay_secret_ref` for valid relay routes instead of writing the raw relay secret back into `runtime_relay_secret`.
- `AndroidKeystoreRelaySecretStore` is the default relay secret store and encrypts secret blobs with AES-GCM under an Android Keystore key.
- Existing valid legacy `runtime_relay_secret` values migrate into the secret store on first read and are removed from DataStore.
- Expired, incomplete, or unresolved secret-ref relay routes are sanitized and physically removed from trusted runtime storage.
- Focused regressions cover handle-backed persistence, legacy raw-secret migration, unresolved secret-ref cleanup, expired route cleanup, and trusted-runtime forget cleanup.
- Copy hygiene and the no-device coverage summary now require `Android relay secret store boundary`.
- Latest focused evidence: PairingStore unit tests passed, copy hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed after this update.
- Not covered: physical Android install, optical QR scanning, Android Keystore behavior on physical hardware, physical haptics, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Expired Relay Secret Store Cleanup

The Android phone was disconnected during this pass. The latest evidence is source/JVM/SwiftPM/script evidence only:

- `PairingStore` now loads and persists trusted-runtime relay routes only while the relay lease is currently valid.
- Expired relay routes are sanitized out of trusted runtime state and their persisted relay host/id/secret/expiry/nonce/scope keys are physically removed from DataStore.
- Focused regressions now cover both writing an expired trusted relay route and reading an expired legacy stored relay route.
- Copy hygiene now requires the valid-route-only persistence policy and expired/incomplete relay physical-cleanup regressions.
- Latest focused evidence: PairingStore unit tests passed, copy hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed after this update.
- Not covered: physical Android install, optical QR scanning, physical haptics, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Composer QR Hint And Expired Relay Purge

The Android phone was disconnected during this pass. The latest evidence is source/JVM/SwiftPM/script evidence only:

- Android chat composer readiness now has a testable `chatInputHintRes(...)` path.
- When a trusted runtime needs a fresh route, the disabled composer asks for the latest AetherLink Runtime QR instead of showing generic connect-first copy.
- The new latest-QR composer hint is localized in English, Korean, Japanese, Simplified Chinese, and French.
- Expired trusted relay leases now clear stale relay host/secret route material from ViewModel state and the trusted-runtime store instead of leaving expired secrets in durable trust state.
- Fresh QR route refresh still replaces the cleared route and reconnects through relay in focused regression coverage.
- Copy hygiene and the no-device coverage summary now require `Android composer latest QR readiness hint` and `Android expired relay route purge`.
- Latest focused evidence: Android string parity passed, copy hygiene passed, focused `AppNavigationTest` composer-hint regressions passed, focused `RuntimeClientViewModelTest` expired-relay purge/fresh-QR regressions passed, whitespace diff checks passed, and the full no-device quality gate passed after this update.
- Not covered: physical Android install, optical QR scanning, physical haptics, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Manual Diagnostic Host QR-First Guard

The Android phone was disconnected during this pass. The latest evidence is source/JVM/script evidence only:

- Android route notices now distinguish product route candidates from manual diagnostic host leftovers.
- A trusted runtime with no relay route, no trusted endpoint hint, and only a manual diagnostic `runtimeHost` keeps the normal recovery action on `Scan latest QR`.
- Non-manual trusted route sources, such as QR/discovery route hints, still offer a connect action.
- Copy hygiene and the no-device coverage summary now require the `Android manual diagnostic host QR-first guard` label.
- Latest focused evidence: the two focused `AppNavigationTest` route-action regressions passed, copy hygiene passed, whitespace diff checks passed, and the full no-device quality gate passed after this update.
- Not covered: physical Android install, optical QR scanning, physical haptics, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Language Polish And Region Tag Parity

The Android phone was disconnected during this pass. The latest evidence is source/JVM/Robolectric/XCTest/script evidence only:

- Android Korean, Japanese, Simplified Chinese, and French resources now translate the Memory feature noun in Memory indexing model UI, selection errors, archive confirmation copy, and embedding-model accessibility summaries instead of mixing raw English `Memory` into localized copy.
- Android string parity now rejects raw English `Memory` in non-English resources.
- macOS app-language normalization now accepts region-qualified tags such as `ko-KR`, `ja-JP`, `fr-FR`, and `en-US` before falling back to English.
- macOS localization guard now requires the region-tag normalization path.
- Latest focused evidence: Android string parity passed, macOS localization parity passed, copy hygiene passed, focused Android Compose Memory indexing regressions passed, focused macOS app-language normalization XCTest passed, and the full no-device quality gate passed after this update.
- Not covered: physical Android install, Android system Settings app-language UI behavior on a real device, physical macOS language switching, physical TalkBack or VoiceOver output, camera QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android OS App-Language Handoff

The Android phone was disconnected during this pass. The latest evidence is source/JVM/script evidence only:

- Android 13+ per-app language selection now flows from `LocaleManager.applicationLocales` into app state on launch.
- The handoff applies only until the user chooses a language inside AetherLink; persisted in-app language choices continue to win after app recreation.
- Persisted language records now distinguish default, OS app-language, and in-app language sources.
- Region-qualified language tags normalize into the supported five-language set without expanding the v0.1 language list.
- String parity and copy hygiene now require OS app-language handoff wiring, persistence source tracking, focused ViewModel regressions, and no-device coverage summary text.
- Latest focused evidence: Android string parity passed, copy hygiene passed, whitespace diff checks passed, focused `RuntimeClientViewModelTest` app-language handoff regressions passed, and the full no-device quality gate passed after this update.
- Not covered: physical Android install, Android system Settings app-language UI behavior on a real device, physical TalkBack output, camera QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Active Pairing QR Route Notice Reuse

The Android phone was disconnected during this pass. The latest evidence is source/XCTest/script evidence only:

- The active macOS Pairing QR card now uses the same `PairingRouteNoticeLabel` as the pre-QR setup notice.
- This keeps the localized `Pairing QR status` accessibility label and current route notice value consistent when a QR is visible and when the runtime is still preparing QR connection details.
- Copy hygiene now requires both active and setup Pairing QR surfaces to use the shared route-notice accessibility view.
- Latest focused evidence: macOS `testPairingRouteNoticeAccessibilityUsesSelectedLanguage` passed, along with copy hygiene, docs hygiene, and whitespace diff checks.
- Not covered: physical VoiceOver output, physical QR scanning, physical Android install, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Documentation Progress Evidence Guard

The Android phone was disconnected during this pass. The latest evidence is documentation/script evidence only:

- `script/check_docs_hygiene.py` now validates the latest `docs/progress.md` implementation entry without scanning all historical progress notes for stale product wording.
- The latest progress entry must include a dated heading, no-device scope, an explicit caveat, physical or real-network coverage limits, and concrete verification commands.
- This protects the `docs/qa-evidence.md` current-rule boundary where generated artifacts remain historical unless the latest relevant progress entry explains the artifact and device/runtime state.
- Latest focused evidence: `python3 script/check_docs_hygiene.py` passed, along with copy hygiene and whitespace diff checks. The full no-device quality gate also passed after this update.
- Not covered: physical Android install, physical QR scanning, physical TalkBack or VoiceOver output, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Pairing QR Route Notice Accessibility

The Android phone was disconnected during this pass. The latest evidence is source/XCTest/script evidence only:

- The macOS Pairing screen route setup notice now exposes the localized accessibility label `Pairing QR status`.
- The route setup notice exposes its current route message as an accessibility value, so waiting/ready/recovery QR status is not conveyed only by icon, color, or visual card text.
- English, Korean, Japanese, Simplified Chinese, and French resources now include the route-notice status label.
- Copy hygiene now requires the route notice accessibility label/value source wiring, focused localization regression, and no-device coverage label `macOS Pairing QR route notice accessibility status`.
- Latest focused evidence: macOS `testPairingRouteNoticeAccessibilityUsesSelectedLanguage` passed, along with macOS localization parity, copy hygiene, and docs hygiene. The full no-device quality gate also passed after this update.
- Not covered: physical VoiceOver output, physical QR scanning, physical Android install, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Trusted-Route Connect Label

The Android phone was disconnected during this pass. The latest evidence is source/Robolectric/script evidence only:

- The remote/trusted-route connect action now uses route-specific copy instead of the same generic `Connect` label.
- English, Korean, Japanese, Simplified Chinese, and French resources now distinguish generic connect from trusted-route connect.
- Copy hygiene now requires the no-device coverage label `Android trusted-route connect label`.
- Latest focused evidence: Android `trustedRouteConnectLabelDiffersFromGenericConnectAcrossSupportedLanguages` passed, along with Android string parity, copy hygiene, and docs hygiene.
- Not covered: physical TalkBack output, physical Android install, camera QR scanning, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Connection Recovery Fallback Contract Guard

The Android phone was disconnected during this pass. The latest evidence is source/XCTest/script evidence only:

- macOS Connection Recovery fallback private-overlay accessibility now uses a fallback-named helper contract instead of retaining an outdated manual-route helper name.
- Copy hygiene now requires the aggregate no-device summary label for `macOS Connection Recovery fallback-action accessibility hints`.
- Latest focused evidence: macOS `testConnectionRecoveryPrivateOverlayToggleAccessibilityDistinguishesRouteContext` passed, along with macOS localization parity, copy hygiene, and docs hygiene.
- Not covered: physical VoiceOver output, physical QR scanning, live relay route behavior, live provider streaming/cancel, and real different-network runtime connectivity.

## 2026-06-27 macOS Pairing QR Route-Expiry Accessibility

The Android phone was disconnected during this pass. The latest evidence is source/SwiftPM/script evidence only:

- macOS Pairing QR accessibility hints now append the localized route-expiration warning when the QR contains expiring connection details.
- The visible route-expiration instruction and the accessibility hint share the same helper, keeping app-language date formatting aligned across the five supported languages.
- Focused Swift localization coverage passed for active QR value, expired QR value, base hint, route-expiration helper, and route-expiration hint composition.
- Not covered: physical VoiceOver output, physical QR scanning, live relay route expiry behavior, and real different-network runtime connectivity.

## 2026-06-27 Route Recovery Copy And QR Readiness Polish

The Android phone was disconnected during this pass. The latest evidence is source/JVM/SwiftPM/script evidence only:

- Android Chat empty-state copy now surfaces nearby-only QR rejection and expired remote-route states with their specific localized route diagnostics instead of generic latest-QR recovery copy.
- Android backend-unavailable and generic error banners expose polite accessibility live regions in addition to safe accessibility summaries.
- macOS Connection Recovery now gates `Generate Latest QR` on full QR readiness, not only route eligibility.
- Focused Android Compose/JVM tests and a focused macOS localization test passed for the changed behavior.
- The full no-device quality gate passed after this update and includes the `Android route rejection empty-chat copy` and `Android expired route empty-chat copy` coverage labels.
- Not covered: physical QR scanning, real device haptics, physical VoiceOver output, live relay authentication failures, real relay allocation behavior, and real different-network runtime connectivity.

## 2026-06-27 Android Relay Auth Failure Empty-Chat Copy

The Android phone was disconnected during this pass. The latest evidence is source/JVM/script evidence only:

- Chat empty-state copy now surfaces relay authentication failure explicitly: saved connection details could not be authenticated, and the user should scan a fresh QR from the trusted runtime.
- Focused JVM/Compose coverage verifies both the resource mapping and the visible post-clear recovery action.
- The full no-device quality gate passed after this update and includes the `Android relay auth failure empty-chat copy` coverage label.
- Copy hygiene and the no-device gate coverage summary now require the `Android relay auth failure empty-chat copy` label.
- Not covered: physical QR scanning, real device haptics, live relay authentication failures, real relay allocation behavior, and real different-network runtime connectivity.

## 2026-06-27 Android Relay Auth Failure Post-Clear QR Action

The Android phone was disconnected during this pass. The latest evidence is source/JVM/script evidence only:

- Chat now has no-device Compose coverage for the state after failed relay material has been removed from the trusted runtime.
- With trusted runtime identity still present, no relay host/secret, and `remote_route_auth_failed`, the rendered Chat surface keeps `Scan latest QR` as the primary action and does not invoke the stale reconnect callback.
- Copy hygiene and the no-device gate coverage summary now require the `Android relay auth failure post-clear QR action` label.
- Not covered: physical QR scanning, real device haptics, live relay authentication failures, real relay allocation behavior, and real different-network runtime connectivity.

## 2026-06-27 Android Relay Auth Failure Auto-Retry Stop

The Android phone was disconnected during this pass. The latest evidence is source/JVM/script evidence only:

- Android relay frame authentication failure now clears stale trusted relay route material while keeping the trusted runtime identity.
- The auto-reconnect path no longer retries the same stored relay route after a `route_diagnostic_relay_auth_failed` state; the user must scan the latest QR with fresh route material.
- Focused ViewModel coverage verifies `relayHost`/`relaySecret` removal in state and store, plus no additional relay connection attempts after the retry delay.
- Copy hygiene and the no-device gate coverage summary now require the `Android relay auth failure auto-retry stop` label.
- Not covered: physical QR scanning, live relay authentication failures, real relay allocation behavior, real device haptics, and real different-network runtime connectivity.

## 2026-06-27 Android Relay Auth Failure QR Recovery Notice

The Android phone was disconnected during this pass. The latest evidence is source/JVM/script evidence only:

- Android route notices now render relay authentication failures as a `Refresh needed` QR-recovery state instead of a neutral saved-connection state.
- The notice reuses the structured `route_diagnostic_relay_auth_failed` guidance and exposes `Scan latest QR` as the primary action.
- Focused no-device UI coverage verifies the route notice state, action, and diagnostic resource mapping.
- Copy hygiene and the no-device gate coverage summary now require the `Android relay auth failure QR recovery notice` label.
- Not covered: physical QR scanning, real device haptics, live relay authentication failures, real relay allocation behavior, and real different-network runtime connectivity.

## 2026-06-27 Connection Recovery Save State And PairingStore Cleanup

The Android phone was disconnected during this pass. The latest evidence is source/JVM/SwiftPM/script evidence only:

- macOS Connection Recovery `Save Connection` accessibility values now distinguish missing address, address-with-port, invalid port, and ready states across all five supported languages.
- Android PairingStore now removes incomplete stored relay route keys from DataStore after read-time sanitization, including stale relay secret and route metadata keys.
- Focused Swift and Android pairing-store tests cover the new behavior, and hygiene/localization guards were updated.
- The full no-device quality gate passed after this update, including the `macOS Connection Recovery Save Connection input state` and `Android PairingStore incomplete relay cleanup` coverage labels.
- Not covered: physical VoiceOver output, physical QR scanning, real relay allocation behavior, and real different-network runtime connectivity.

## 2026-06-27 QR Runtime Name And Provider Details State

The Android phone was disconnected during this pass. The latest evidence is source/JVM/SwiftPM/script evidence only:

- Android pairing QR parsing now normalizes runtime names before pairing UI or trusted-runtime storage sees them: blank names fall back to `AetherLink Runtime`, repeated whitespace collapses, and oversized names are capped.
- macOS model-provider technical-details disclosures expose localized expanded/collapsed accessibility values and hints in all five supported languages.
- Focused Android parser tests and macOS localization tests cover the new behavior, and copy/localization/no-device guards were updated.
- The full no-device quality gate passed after this update, including the `Android QR runtime-name normalization` and `macOS provider technical-details accessibility state` coverage labels.
- Not covered: physical QR scanning, real-device rendering, physical VoiceOver output, and real different-network runtime connectivity.

## 2026-06-27 Route Refresh And Route Token Hardening

The Android phone was disconnected during this pass. The latest evidence is source/JVM/SwiftPM/script evidence only:

- Android pairing QR parsing rejects identity-only `route_token` values containing whitespace before they can participate in trusted runtime discovery or persistence.
- macOS route-refresh failures now return a fixed retryable `route_refresh_unavailable` error instead of exposing thrown error text that may contain route secrets, provider URLs, or backend endpoint details.
- Focused Android parser tests and Swift runtime-router tests cover the new behavior.
- Not covered: physical QR scanning, real relay allocation failure payloads, production relay/signaling security review, and real different-network runtime connectivity.

## 2026-06-27 Android Route Material Redaction Aliases

The Android phone was disconnected during this pass. The latest evidence is source/JVM/script evidence only:

- Android visible runtime error details and provider diagnostics now redact additional QR route material aliases before surfacing details to the user.
- Focused JVM tests cover canonical and compact route secret/id/nonce fields for `runtimeVisibleErrorDetail`, `providerDiagnosticMessage`, and `providerDiagnosticCode`.
- Copy hygiene now requires the expanded route-material redaction samples to stay covered by tests.
- Not covered: physical device display, live backend/provider failure payloads, production relay/signaling security review, and real different-network runtime connectivity.

## 2026-06-27 Android Chat History Contextual Action Labels

The Android phone was disconnected during this pass. The latest evidence is source/JVM/Robolectric/script evidence only:

- Settings chat-history per-chat archive, restore, and permanent-delete controls now expose chat-title-specific click-action labels aligned with their accessibility labels.
- Focused no-device Compose coverage verifies the contextual action labels and streaming-disabled state descriptions across English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene now guards the per-chat contextual click-action label contract so future UI refactors cannot silently fall back to generic action names.
- Not covered: physical install, camera QR scan, real-device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.

## 2026-06-27 Android Chat Composer Action Labels

The Android phone was disconnected during this pass. The latest evidence is source/JVM/Robolectric/script evidence only:

- Android chat composer controls now have localized click-action labels for attach files, send message, cancel generation, and remove pending attachment.
- Focused no-device Compose coverage verifies the ready, disabled, streaming, localized send/cancel, and pending attachment-chip paths.
- The full no-device quality gate passed with the `Android composer primary action click labels` contract included in its coverage summary.
- Not covered: physical install, camera QR scan, real-device haptics, launcher or Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.

## 2026-06-26 No-Device Android UI Matrix Check

The Android phone is currently disconnected. The latest no-device UI evidence is source/JVM/Robolectric evidence only:

- Android top-bar model picker rows now have no-device accessibility evidence: the selected chat model and selected Memory indexing model expose a localized selected-state description in the actual rendered dropdown menu.
- Android top-bar model picker install cues now have no-device accessibility evidence: an uninstalled runtime-host-local chat model row shows `Install model`, exposes that install action as row state, remains clickable, and dispatches the existing model-selection path instead of calling a provider directly.
- Android top-bar chat model picker rows now have no-device row-summary accessibility evidence: selected, running, and uninstalled chat-model rows expose model role, name, provider/status, and selected/install state through contextual accessibility summaries while keeping embedding models out of the chat picker.
- Android top-bar chat model picker now has no-device streaming-disabled evidence: while a response is streaming, the selected-model control is disabled and exposes localized guidance to wait for or cancel the current response before changing models across English, Korean, Japanese, Simplified Chinese, and French.
- Android Settings Memory indexing model rows now have matching no-device accessibility evidence: the actual rendered `SettingsScreen` exposes a localized selected-state description on the selected embedding model row after the section is expanded.
- Android Settings preference rows now have matching no-device accessibility evidence: the actual rendered `SettingsScreen` exposes localized selected-state descriptions and group-plus-option summaries on the selected Appearance and Language rows.
- Android Settings expandable sections now have no-device accessibility evidence that each section exposes one row-level collapsed/expanded control, while the trailing icon button no longer creates a duplicate screen-reader target.
- Android Settings expandable sections now have no-device action-label evidence: section headers expose localized `Expand section` / `Collapse section` click-action labels across English, Korean, Japanese, Simplified Chinese, and French, and the diagnostic endpoint expander exposes `Show troubleshooting` / `Hide troubleshooting`.
- Android Settings connection switch rows now have matching no-device accessibility evidence: the actual rendered `SettingsScreen` exposes localized on/off state descriptions for Auto reconnect and Connection troubleshooting.
- Android Settings connection switch rows now have no-device action-label evidence: Auto reconnect and Connection troubleshooting expose localized enable/disable click-action labels while preserving their existing on/off state descriptions.
- Android Settings chat-history bulk expander now has no-device action-label evidence: `Manage all chats` exposes localized `Expand section` while collapsed and `Collapse section` while expanded before any archive-all or permanent-delete controls are shown.
- Android Settings diagnostic endpoint expander now has no-device accessibility evidence: developer-only `Connection troubleshooting` exposes localized collapsed/expanded state plus a button role, hides the nested icon semantics, and keeps endpoint inputs hidden until the expander opens.
- Android QR scanner permission and settings-recovery states now have no-device cancel-action evidence: when camera permission is missing or blocked, the scanner shows a visible localized `Cancel` text action and dispatches the same lightweight cancel haptic path as the active scanner surface.
- Android connection notices now have no-device interaction evidence for the actual `ConnectionStatusScreen`: tapping a saved-connection notice dispatches reconnect plus lightweight AetherLink haptic feedback, while tapping a refresh-needed notice dispatches the latest-QR scan action plus the same haptic policy path.
- Android connection route notices now have no-device accessibility evidence: the saved-connection and refresh-needed clickable notice cards expose localized click-action labels matching their visible `Connect` or `Scan latest QR` recovery action.
- Android Settings route-recovery primary action now has no-device interaction evidence: when a trusted runtime's relay route is expired, even with an older saved endpoint hint, the Settings primary action shows `Scan latest QR`, dispatches QR scan, and uses lightweight haptic feedback instead of reconnecting the stale route.
- Android chat route-recovery empty state now has no-device layout evidence: at a narrow 260 dp width, the full saved-route recovery guidance remains visible and the `Scan latest QR` action remains reachable.
- Android expired remote-route Chat recovery now has no-device interaction evidence: when `remote_route_expired` is paired with expired relay route metadata, Chat shows the latest-QR recovery action, explains that fresh connection details are required, dispatches QR scanning with lightweight haptic feedback, and does not call the stale reconnect path.
- Android expired remote-route Chat recovery now has no-device localization evidence across English, Korean, Japanese, Simplified Chinese, and French for the latest-QR action label, detail copy, ready-state description, and haptic callback path.
- Android terminal route-refresh expiry now has no-device ViewModel evidence that `route_refresh_unavailable` near relay lease expiry clears connected/connecting state, sets runtime status to failed, clears the active route kind, and surfaces `remote_route_expired`.
- Android New Chat actions now have no-device pairing-state evidence: before QR pairing/trust, the top-bar, drawer, and permanent rail New Chat affordances share a state policy that keeps New Chat disabled and exposes localized pairing-required guidance across English, Korean, Japanese, Simplified Chinese, and French.
- Android permanent navigation rail New Chat now has direct no-device evidence: the large-screen rail disables New Chat before pairing, exposes the pairing-required state, enables the ready state after trust, and dispatches the same lightweight haptic callback as the rest of the shell chrome.
- Android chat route-availability notices now have no-device accessibility-state evidence: the compact clickable saved-route notice exposes its visible guidance as a state description while dispatching the expected latest-QR scan action with lightweight haptic feedback.
- Android Settings connected-state actions now have no-device interaction evidence: when a trusted runtime is already connected, Settings exposes `Refresh health` and `Disconnect` without a redundant enabled `Connect` button.
- Android connected connection actions now have no-device copy/action evidence: the runtime health refresh button uses the explicit localized `Refresh health` action label and invokes the refresh callback.
- Android connected connection actions now have no-device accessibility-state evidence: the shared connected action block exposes localized ready-state descriptions for `Refresh health` and `Disconnect` across English, Korean, Japanese, Simplified Chinese, and French.
- Android backend readiness banner now has no-device accessibility evidence: the Chat screen backend-unavailable banner exposes title plus safe provider detail as one localized accessibility summary, keeps unsafe raw provider details hidden, and preserves the `Refresh health` action callback.
- Android backend readiness banner refresh action now has no-device accessibility-state evidence: its `Refresh health` action exposes the same localized ready-to-refresh runtime state across English, Korean, Japanese, Simplified Chinese, and French.
- Android generic error banners now have no-device accessibility evidence: shared non-route errors expose localized title plus safe error label, safe detail, and diagnostic text as one assistive-tech summary, while endpoint, provider URL, route-token, or secret-like detail remains redacted from visible and accessibility output.
- Android reasoning sections now have no-device accessibility evidence: the Chat screen exposes assistant thinking as a dim collapsed/expandable UI, and the reasoning row now includes a localized summary with label, collapsed/expanded state, and the same preview/full reasoning text used visually.
- Android chat composer attach action now has no-device accessibility evidence: the actual rendered `ChatScreen` exposes the attach-files action with a ready state when the trusted connected composer can accept files, and with the same disabled reason as the composer hint when the composer is locked.
- Android chat composer input now has no-device readiness-state accessibility evidence: the actual message field exposes localized state descriptions for locked, empty, ready-to-send, and streaming states without adding a visible generic placeholder.
- Android chat send action now has no-device readiness-state accessibility evidence: the actual rendered `ChatScreen` exposes localized send-button state descriptions for empty-input and ready-to-send states across English, Korean, Japanese, Simplified Chinese, and French.
- Android chat composer primary actions now have no-device action-label evidence: attach files, send message, cancel generation, and contextual pending attachment remove buttons expose localized semantics click-action labels while keeping existing content descriptions and state descriptions intact.
- Android streaming cancel action now has no-device interaction evidence: the actual rendered `ChatScreen` hides `Send message` during streaming, exposes `Cancel generation`, dispatches the cancel callback, and uses the destructive haptic policy path.
- Android streaming cancel action now has no-device accessibility-state evidence: the actual rendered `ChatScreen` exposes a localized ready-to-stop state for `Cancel generation` across English, Korean, Japanese, Simplified Chinese, and French.
- Android jump-to-latest action now has no-device accessibility-state evidence: the actual rendered `ChatScreen` exposes a localized ready-to-return state for `Jump to latest message` across English, Korean, Japanese, Simplified Chinese, and French.
- Android chat pending attachment chips now have no-device accessibility evidence: the actual rendered `ChatScreen` exposes each pending attachment's file name and state, including the unsupported-image `Vision model required` state, while remove buttons stay separately reachable.
- Android pending attachment remove buttons now have no-device accessibility evidence: when the composer is disabled, the remove button exposes the same localized disabled reason as the composer controls instead of only appearing disabled.
- Android pending attachment size labels now have no-device locale evidence: the actual rendered `ChatScreen` uses the selected app-language context when formatting file-size metadata.
- Android chat message attachment chips now have no-device accessibility evidence: saved user/assistant message attachments expose each file name and type as a stable accessibility label plus state description.
- Android chat message copy actions now have no-device localization/accessibility evidence: user and assistant message long-press copy actions expose the localized action label such as `Copy message`, while the result toast copy such as `Copied` stays separate from the action label.
- Android code-block copy actions now have no-device localization/accessibility evidence: rendered fenced-code blocks expose a localized `Copy code block` action across English, Korean, Japanese, Simplified Chinese, and French, and they no longer reuse the generic message-copy action label.
- Android provider diagnostics toggles now have no-device accessibility evidence: model-provider `Show details`/`Hide details` controls expose localized collapsed/expanded state while still revealing diagnostic message and reference code content after expansion.
- Android provider diagnostics toggles now have no-device named-label accessibility evidence: repeated provider rows keep compact visible labels while assistive technologies can distinguish provider-specific actions such as `Show details for Ollama` and `Hide details for LM Studio`.
- Android suggested-question chips now have no-device accessibility evidence: the actual rendered `ChatScreen` exposes compact generated next-question chips with localized contextual labels such as `Suggested question: ...` while keeping the visible chip text short.
- Android suggested-question chips now have no-device action-label evidence: the compact chip still only shows the generated next question, but its click action exposes `Insert suggested question`, dispatches the lightweight haptic path, fills the composer, and leaves sending explicit.
- Android Settings discovered-runtime actions now have no-device contextual accessibility evidence: trusted route action buttons include the discovered runtime service name, so repeated connection candidates are distinguishable by assistive tech.
- Android Settings discovered-runtime unavailable rows now have no-device contextual accessibility evidence: QR-required and not-trusted discovered routes expose runtime name plus trust status plus unavailable reason as one accessibility summary instead of only short visible status copy.
- Android Settings discovery actions now have no-device accessibility-state evidence: `Find trusted routes` and `Stop` expose localized ready/running/idle state descriptions across English, Korean, Japanese, Simplified Chinese, and French.
- Android drawer chat history rows now have no-device contextual accessibility evidence: each overflow options button includes the chat title, so repeated previous-chat actions are distinguishable by assistive tech.
- Android drawer chat history rows now have no-device row-summary accessibility evidence: each previous-chat row exposes the chat title, message-count/runtime-processing status, and selected-state context through a localized row summary, with focused coverage across English, Korean, Japanese, Simplified Chinese, and French.
- Android rename-chat dialog now has no-device accessibility evidence: the actual dialog exposes localized empty-title and ready-to-save state descriptions on the title field and `Save` action, and the final save path dispatches the existing lightweight AetherLink haptic callback.
- Android chat top-bar model search now has no-device localization/accessibility evidence: the model picker search clear action includes the current query, dispatches lightweight haptic feedback when clearing, restores model rows after clearing, and has localized clear/no-results resources across English, Korean, Japanese, Simplified Chinese, and French.
- Android Settings chat-history search now has no-device localization/accessibility evidence: the Settings chat-history search clear action includes the current query, dispatches lightweight haptic feedback when clearing, restores active and archived saved chat rows after clearing, and has localized clear/no-results resources across English, Korean, Japanese, Simplified Chinese, and French.
- Android QR scanner chrome now has focused no-device evidence: `PairingQrScannerChromeNoDeviceComposeTest` renders the normal permission state without launching a camera preview, renders the blocked-permission app-settings recovery state, renders the camera-ready scanner guidance, verifies torch label/state toggling, checks localized flashlight state semantics, and checks fake haptic callbacks for permission, settings recovery, torch, and lightweight cancel actions.
- Android Settings QR-first pairing action now has no-device accessibility evidence: when a connection attempt is already running, the rendered `Scan QR` action is disabled and exposes the localized disabled reason instead of only appearing unavailable.
- Android diagnostic QR text fallback now has no-device accessibility evidence: the Settings troubleshooting dialog exposes localized empty, invalid, and ready state descriptions on the QR text field and submit action, marks invalid text as an error, and only submits valid `aetherlink://pair` payloads.
- Android connect actions now have no-device accessibility evidence: when a saved runtime connection attempt is already running, both Settings and Chat render the disabled `Connecting` action with a localized state description explaining that the connection attempt is in progress.
- Android model refresh actions now have no-device accessibility evidence: the Memory indexing model `Refresh models` action exposes localized ready, loading, and disconnected state descriptions across English, Korean, Japanese, Simplified Chinese, and French.
- Android New Chat actions now have no-device accessibility evidence: during streaming, the top-bar and drawer `New Chat` actions are disabled and expose a localized reason telling the user to wait for or cancel the current response before starting another chat.
- Android client UI copy boundary now has no-device source/script evidence: all five localized string resources avoid OS-specific product nouns, keep model-provider names behind runtime-mediated wording, and are protected by a parsed string-resource assertion in `script/check_copy_hygiene.py`.
- Android Settings Memory rows now have no-device contextual accessibility evidence: enable/pause switches include the memory text and expose enabled/paused state, while remove buttons include the memory text before the destructive confirmation opens.
- Android Settings Memory row actions now have no-device action-label evidence: enable/pause switches and remove buttons expose localized click-action labels aligned with their contextual content descriptions.
- Android Settings Memory rows now have no-device capped-label accessibility evidence: long saved memory text stays visible in the row, but switch/delete action labels are capped through a stable helper so assistive tech does not read entire long notes for every action.
- Android Settings Memory deletion now has no-device fake-haptic timing evidence: opening the delete confirmation emits lightweight feedback instead of destructive feedback, cancel stays on the lighter feedback path, and the final `Delete` confirmation emits the destructive haptic path while invoking removal exactly once.
- Android Settings trusted-runtime forget now has no-device accessibility evidence: the compact visible `Forget` action exposes a localized content description that includes the saved runtime name before the confirmation dialog opens.
- Android Settings chat history rows now have no-device accessibility evidence: per-chat archive, restore, and permanent-delete buttons expose contextual labels that include the chat title, while bulk archive/delete controls remain hidden behind Manage all chats and two-step confirmations.
- Android Settings chat history destructive actions now have no-device fake-haptic timing evidence: bulk archive/delete and per-chat permanent delete open confirmation with lightweight feedback instead of destructive feedback, first `Continue` stays lightweight, final confirmation emits destructive feedback, and reversible archive uses the lightweight path.
- Android Settings chat history bulk controls now have no-device accessibility evidence: the `Manage all chats` expander exposes localized collapsed/expanded state before revealing archive-all and permanent-delete-archived actions.
- Android Settings chat history bulk actions now have no-device disabled-state accessibility evidence: `Archive all chats` and `Permanently delete archived chats` expose localized ready, no matching chat type, and current-response-in-progress state descriptions across English, Korean, Japanese, Simplified Chinese, and French.
- Android Settings chat history per-chat actions now have no-device disabled-state accessibility evidence: archive, restore, and permanent-delete buttons expose a localized current-response-in-progress reason while streaming across English, Korean, Japanese, Simplified Chinese, and French.
- Android connection guidance now has no-device platform-neutral copy evidence: saved-runtime recovery and paused auto-reconnect guidance use `Use Connect` wording instead of touch-specific `Tap Connect` or localized equivalents, and Android string parity rejects those stale action phrases.
- macOS first-run Connection Recovery visibility now has no-device policy evidence: a clean first-run model hides the recovery panel, while saved route state or a concrete route-preparation issue shows it.
- macOS Pairing QR now has no-device localization/accessibility evidence: QR accessibility value copy distinguishes active scan-ready and expired states, and the QR hint explains runtime verification plus pairing/refresh connection details across all five supported languages.
- macOS Pairing QR time remaining now has no-device localization/accessibility evidence: the custom expiry progress bar exposes a stable `Pairing QR time remaining` label and the localized countdown or expired text as its accessibility value across all five supported languages.
- macOS Pairing QR generation actions now have no-device localization/accessibility evidence: Pairing, Status quick actions, toolbar, and menu bar QR generation affordances share localized ready/unavailable values plus disabled/unavailable reasons so QR-first setup does not rely only on hover help.
- macOS active Pairing QR renewal now has no-device localization/accessibility evidence: the in-card `Generate New QR` action exposes localized hover help, a ready accessibility value, and the localized action hint across English, Korean, Japanese, Simplified Chinese, and French.
- macOS global QR generation now has no-device command-policy evidence: toolbar and menu-bar `Generate Pairing QR` availability uses the same route-readiness contract as the Status and Pairing surfaces.
- macOS app-language date formatting now has no-device localization evidence: trusted-device pairing summaries and pairing QR route-expiration copy use AetherLink's selected app language for date strings instead of the system locale.
- macOS app-language byte-count formatting now has no-device localization evidence: model size labels and model-row accessibility summaries use AetherLink's selected app language for byte-count strings instead of the system locale.
- macOS Trusted Devices now has no-device localization/accessibility evidence: repeated remove-trust row buttons expose the device name and key fingerprint to assistive tech, while the visible button label stays compact.
- macOS Trusted Devices rows now have no-device localization/accessibility evidence: each trusted-device row exposes device name, pairing summary, and key fingerprint as one localized assistive-tech summary while keeping the destructive remove button separately reachable.
- macOS Trusted Devices removal confirmation now has no-device localization evidence: the confirmation message includes device name plus key fingerprint across English, Korean, Japanese, Simplified Chinese, and French, and Korean fallback wording avoids duplicated device nouns.
- macOS Activity now has no-device localization/accessibility evidence: repeated technical-details disclosures expose the localized log summary plus localized expanded/collapsed value and state-specific hint to assistive tech, while the visible disclosure label stays compact.
- macOS Activity row tone icons now have no-device source/accessibility evidence: the decorative status glyph is hidden from assistive tech so VoiceOver reaches the localized event summary and contextual technical-details disclosure instead.
- macOS Model Providers now has no-device localization/accessibility evidence: repeated provider technical-details disclosures expose the provider name or a localized provider fallback to assistive tech, while the visible disclosure label stays compact.
- macOS Model Providers status pills now have no-device localization/accessibility evidence: provider status pills expose provider name plus current status across English, Korean, Japanese, Simplified Chinese, and French while keeping compact visible pill text.
- macOS Runtime Overview now has no-device localization/accessibility evidence: the top status panel exposes title, current state, detail, and footnote as one localized assistive-tech summary across English, Korean, Japanese, Simplified Chinese, and French.
- macOS Status cards now have no-device localization/accessibility evidence: compact overview cards expose title, current state, and detail as one localized assistive-tech summary across English, Korean, Japanese, Simplified Chinese, and French.
- macOS sidebar brand header now has no-device localization/accessibility evidence: the decorative runtime icon is hidden from assistive tech, and the split visible brand text is exposed as one localized `AetherLink Runtime` label across English, Korean, Japanese, Simplified Chinese, and French.
- macOS reusable page headers now have no-device localization/accessibility evidence: the decorative header icon, title, and subtitle are grouped into one localized assistive-tech label, with title/subtitle separator localization across English, Korean, Japanese, Simplified Chinese, and French.
- macOS empty states now have no-device localization/accessibility evidence: Models, Pairing QR, Trusted Devices, and Activity empty states expose one localized assistive-tech label built from title plus description across English, Korean, Japanese, Simplified Chinese, and French.
- macOS sidebar preference pickers now have no-device localization/accessibility evidence: the Appearance and Language pickers expose localized selected values across English, Korean, Japanese, Simplified Chinese, and French.
- macOS menu-bar status and command localization now has no-device evidence: runtime status, model-service status, Open AetherLink, Refresh, Load Models, and Quit are generated through helper functions with focused five-language XCTest coverage.
- macOS Models rows now have no-device localization/accessibility evidence: each model row exposes model name, ID, type, provider, source, running state, and size as one localized assistive-tech summary across English, Korean, Japanese, Simplified Chinese, and French.
- macOS Models group headers now have no-device localization/accessibility evidence: `Chat Models` and `Embedding Models` headers expose the localized section title plus localized model count as one assistive-tech label across English, Korean, Japanese, Simplified Chinese, and French.
- macOS Connection Recovery status rows now have no-device localization/accessibility evidence: saved connection details, connection route scope, and connection health rows expose row title, status, and detail as one localized assistive-tech summary across English, Korean, Japanese, Simplified Chinese, and French.
- macOS Connection Recovery form fields now have no-device localization/accessibility evidence: bootstrap relay endpoints, bootstrap allocation token, connection address, port, and protected connection key expose explicit labels and localized accessibility values, while secure token/key fields announce state instead of reading secret contents.
- macOS Connection Recovery QR actions now have no-device localization/accessibility evidence: `Generate Latest QR` exposes localized ready/unavailable values plus concrete ready, not-ready, or unavailable reasons across English, Korean, Japanese, Simplified Chinese, and French.
- macOS no-device XCTest runs now have runtime-identity stabilization evidence: tests can inject `AETHERLINK_RUNTIME_IDENTITY_FILE`, and automatic `xctest` runs use a per-process temporary file-backed identity so UI/localization tests do not block on Keychain access. Production runtime identity still prefers Keychain first.
- Android drawer chat search now has no-device localization/accessibility evidence: the previous-chat search field renders across English, Korean, Japanese, Simplified Chinese, and French, the no-results state is localized, and the clear action exposes the current query in its accessibility label while dispatching the lightweight clear-action haptic.
- Android OS app-language metadata now has no-device source/script evidence: the manifest declares `android:localeConfig="@xml/locales_config"`, and the locale config lists English, Korean, Japanese, Simplified Chinese, and French in sync with the in-app language enum.
- Android Settings Memory indexing model rows now have no-device localization/accessibility evidence: the no-model option, selected installed embedding model row, uninstalled embedding model row, and saved-but-missing embedding model row expose contextual assistive-tech summaries across English, Korean, Japanese, Simplified Chinese, and French.
- Android Settings Memory add action now has no-device localization/accessibility evidence: the Add Memory button exposes localized state descriptions for trusted-runtime locked, empty-input, and ready-to-add states across English, Korean, Japanese, Simplified Chinese, and French.
- macOS Connection Recovery route diagnostics now have no-device localization/accessibility evidence: repeated technical-details disclosures expose connection setup result, connection health, or connection preparation context to assistive tech, while the visible disclosure label stays compact.
- macOS Connection Recovery saved-connection removal now has no-device localization/accessibility evidence: the destructive `Remove Saved Connection Details` button clearly names the data being removed and exposes the saved endpoint or saved-connection fallback across English, Korean, Japanese, Simplified Chinese, and French.
- macOS Status Readiness now has no-device localization/accessibility evidence: each readiness row exposes title, status, and detail in one localized assistive-tech summary across all five supported languages.
- macOS quick actions now have no-device localization/accessibility evidence: `Check Model Providers` and `Load Models` share localized readiness values and action hints across Status, toolbar, command/menu-bar surfaces in English, Korean, Japanese, Simplified Chinese, and French.
- macOS menu-bar Pairing QR command now has no-device localization evidence: it uses the same active-session title contract as the toolbar and Status quick action, showing `Generate Pairing QR` before a QR exists and `Generate New QR` while a pairing session is active across all five supported languages.
- `ClientScreensNoDeviceComposeTest.primaryScreensRenderAcrossLocaleThemeSurfaceMatrix` now renders Chat, Settings, and Connection screens across English, Korean, Japanese, Simplified Chinese, and French in both light and dark themes.
- The Connection screen matrix anchor is the saved-connection status pill in each supported language, so connection notice status copy is checked in the same matrix as the primary Chat and Settings surfaces.
- The default no-device quality gate includes the QR scanner chrome and full client-screen Compose regressions, and copy hygiene requires the gate summary to name Android chat top-bar install action cue, Android chat top-bar model search interaction, Android chat top-bar model row accessibility summaries, Android drawer chat options contextual accessibility, Android drawer chat row accessibility summaries, Android drawer chat search interaction, Settings chat history search interaction, Android QR scanner permission/settings/torch/cancel chrome, QR scanner torch state accessibility, Android Settings QR scan disabled reason, Android diagnostic QR text state accessibility, Android connect action disabled reason, Android model refresh action accessibility state, Android New Chat disabled reason, Android New Chat pairing-required disabled reason, Android permanent rail New Chat pairing gate, Android route notice accessibility state, Android chat empty route guidance full-wrap layout, Android composer input readiness accessibility state, Android send button readiness accessibility state, Android composer attach action accessibility state, Android streaming cancel Compose action, Android attachment chip accessibility state, Android attachment remove disabled reason, Android attachment size locale formatting, Android message attachment accessibility state, Android message copy accessibility labels, Android code block copy accessibility labels, Android backend readiness banner accessibility summary, Android generic error banner accessibility summary, Android provider diagnostics expanded state, Android provider diagnostics named accessibility labels, Android suggested-question accessibility labels, Android suggested-question action accessibility labels, Android reasoning accessibility summary, Android refresh-health action copy, Settings expandable section duplicate icon semantics guard, Settings preference option accessibility summaries, Settings diagnostic endpoint expander accessibility state, Settings connection switch state accessibility, Settings discovered route contextual action accessibility, Settings discovered route unavailable accessibility summaries, Android embedding model row accessibility summaries, Settings Memory contextual action accessibility, Settings memory capped action accessibility labels, Settings memory add readiness accessibility state, Settings memory destructive confirmation haptic timing, chat history destructive confirmation haptic timing, confirmation-open lightweight haptic timing, Settings expired-route primary QR action, Android connected Settings redundant-connect guard, chat-history contextual action accessibility, Android rename chat readiness accessibility state, chat-history bulk expander accessibility state, macOS first-run diagnostics hiding, macOS Pairing QR accessibility state, macOS Pairing QR time remaining accessibility value, macOS Pairing QR generation action accessibility reason, macOS active Pairing QR renewal accessibility hint, macOS sidebar brand accessibility label, macOS page header accessibility labels, macOS empty-state accessibility labels, macOS sidebar preference picker accessibility values, macOS global QR generation availability gate, macOS app-language date formatting, macOS app-language byte-count formatting, macOS connection recovery form field accessibility, macOS connection recovery QR action accessibility reason, macOS trusted-device remove accessibility labels, macOS trusted-device row accessibility labels, macOS trusted-device removal confirmation localization, macOS Activity technical-details accessibility labels, macOS provider technical-details accessibility labels, macOS provider status pill accessibility labels, macOS runtime overview accessibility labels, macOS status card accessibility labels, macOS model row accessibility labels, macOS model group header accessibility labels, macOS relay status row accessibility labels, macOS route diagnostic technical-details accessibility labels, and macOS readiness row accessibility labels coverage.
- The same no-device gate now also names Android platform-neutral connect guidance copy, chat history bulk action disabled accessibility state, chat history per-chat disabled accessibility state, macOS model group header accessibility labels, and Android generic error banner accessibility summary coverage.
- The same no-device gate now also names Android OS app-language localeConfig metadata and macOS menu-bar status and command localization coverage.
- The same no-device gate now also names macOS quick action accessibility hint coverage and chat history bulk expander action-label coverage.
- The same no-device gate now also names macOS menu-bar Pairing QR active-session title, Android chat top-bar model picker streaming-disabled state, and Settings memory action accessibility label coverage.
- The same no-device gate now also names Android trusted-runtime forget named accessibility label coverage.
- The same no-device gate now also names Settings discovery action accessibility state coverage.
- The same no-device gate now also names Android streaming cancel accessibility state coverage.
- The same no-device gate now also names Android jump-to-latest accessibility state coverage.
- The same no-device gate now also names Android connected action accessibility state coverage.
- The same no-device gate now also names Android backend readiness refresh accessibility state coverage.
- The same no-device gate now also names Android route notice action accessibility label coverage.
- The same no-device gate now also names Android expired remote-route QR recovery action coverage.
- The same no-device gate now also names Android expired remote-route QR recovery localization coverage.
- The same no-device gate now also names Android route.refresh terminal expiry state guard coverage.
- The same no-device gate now also names Settings expandable section action accessibility label coverage.
- The same no-device gate now also names Settings switch action accessibility label coverage.
- Latest focused Android Settings switch and QR scanner cancel evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsAutoReconnectSwitchExposesAccessibilityState --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest.scannerChromeShowsPermissionStateWithoutCameraPreview --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest.scannerChromeShowsSettingsRecoveryWhenCameraPermissionIsBlocked -Pkotlin.incremental=false` passed after the Settings switch action-label and QR permission cancel pass.
- Latest focused Android Settings section action-label evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsExpandableSectionsExposeLocalizedExpandedState --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDiscoveryActionsExplainIdleAndRunningStatesAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the Settings section action-label pass.
- Latest focused macOS quick-action accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testQuickActionAccessibilityUsesSelectedLanguage` passed after adding shared quick-action readiness and hint helpers.
- Latest focused Android chat-history bulk expander action-label evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed -Pkotlin.incremental=false` passed after adding `Manage all chats` expand/collapse action labels.
- Latest focused Android streaming model picker and Memory action-label evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerExplainsDisabledStreamingStateAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsExposeContextualActionAccessibility -Pkotlin.incremental=false` passed after the streaming model-picker and Memory action-label pass.
- Latest focused macOS menu-bar Pairing QR title evidence: `swift test --filter AetherLinkLocalizationTests/testMenuBarPairingQRCommandTitleTracksActiveSessionAndLanguage` passed after the menu-bar QR command adopted the active-session title helper.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android streaming model-picker, Settings Memory action-label, and macOS menu-bar Pairing QR active-session title pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the macOS quick-action accessibility and Android bulk chat expander action-label pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused macOS Activity decorative-icon evidence: `swift test --filter AetherLinkLocalizationTests/testActivityTechnicalDetailsAccessibilityLabelUsesEventContext` passed after hiding Activity row tone icons from assistive tech.
- Latest focused macOS Activity disclosure-state evidence: `swift test --filter AetherLinkLocalizationTests/testActivityTechnicalDetailsAccessibilityStateUsesSelectedLanguage` passed after adding localized expanded/collapsed accessibility values and state-specific hints to Activity `Technical Details`.
- Latest focused Android route notice action-label evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusSavedRouteNoticeClickConnectsWithHaptic --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusRefreshNeededRouteNoticeClickScansLatestQrWithHaptic -Pkotlin.incremental=false` passed after the route notice action-label pass.
- Latest focused Android expired remote-route QR recovery evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenExpiredRemoteRouteShowsLatestQrRecoveryAction -Pkotlin.incremental=false` passed after the expired remote-route Chat recovery pass.
- Latest focused Android expired remote-route localization evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenExpiredRemoteRouteRecoveryLocalizesAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the expired remote-route localization pass.
- Latest focused Android terminal route-refresh expiry state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeMarksRouteExpiredWhenRefreshErrorCannotRetryBeforeLeaseExpiry -Pkotlin.incremental=false` passed after clearing connected route state when refresh cannot retry before lease expiry.
- Latest focused Android backend readiness refresh accessibility-state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenBackendUnavailableRefreshActionExplainsStateAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the backend readiness refresh accessibility-state pass.
- Latest focused Android connected action accessibility-state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusConnectedActionsExplainStateAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the connected action accessibility-state pass.
- Latest focused Android jump-to-latest accessibility-state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenJumpToLatestActionExplainsStateAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the jump-to-latest accessibility-state pass.
- Latest focused Android streaming cancel accessibility-state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingCancelActionExplainsStateAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the streaming cancel accessibility-state pass.
- Latest focused Android Settings discovery action state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDiscoveryActionsExplainIdleAndRunningStatesAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the discovery action accessibility-state pass.
- Latest focused Android trusted-runtime forget named accessibility evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetActionNamesRuntimeAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the named forget-action accessibility pass.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android backend readiness refresh accessibility-state pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused Android OS app-language metadata evidence: `python3 script/check_android_string_parity.py` passed after adding `res/xml/locales_config.xml` and manifest `android:localeConfig` alignment checks.
- Latest focused macOS menu-bar localization evidence: `swift test --filter AetherLinkLocalizationTests/testMenuBarStatusAndCommandTitlesUseSelectedLanguage` passed after moving menu-bar status and command titles behind localized helpers.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android OS app-language metadata and macOS menu-bar localization pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused Android chat-history per-chat disabled-state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPerChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the per-chat history disabled-state pass.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android per-chat history disabled-state pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused Android generic error banner accessibility evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenGenericErrorBannerExposesAccessibilitySummaryAndRedactsUnsafeDetail --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenGenericErrorAccessibilitySummaryLocalizesAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the generic error banner accessibility-summary pass.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android generic error banner accessibility-summary pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused macOS model group header accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testModelGroupHeaderAccessibilityLabelUsesSelectedLanguage` passed after the model group header accessibility pass.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the macOS model group header accessibility pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused macOS empty-state accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testCompanionEmptyStateAccessibilityLabelUsesSelectedLanguageAndFallbacks` passed after the empty-state accessibility pass.
- Latest focused Android Settings QR disabled evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPairingScanQrActionExplainsDisabledConnectingState -Pkotlin.incremental=false` passed after the QR disabled-reason pass.
- Latest focused Android diagnostic QR text evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.diagnosticQrTextDialogExplainsEmptyInvalidAndReadyStates -Pkotlin.incremental=false` passed after the diagnostic QR text state-accessibility pass.
- Latest focused Android connect-action disabled evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPairingConnectActionExplainsDisabledConnectingState --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenConnectActionExplainsDisabledConnectingState -Pkotlin.incremental=false` passed after the connect-action disabled-reason pass.
- Latest focused Android chat-history bulk action state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsBulkChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsBulkChatHistoryActionsExplainMissingChatDisabledStates -Pkotlin.incremental=false` passed after the bulk action disabled-state pass.
- Latest focused Android platform-neutral connect guidance evidence: `python3 script/check_android_string_parity.py` passed after replacing touch-specific saved-runtime recovery and paused auto-reconnect copy.
- Latest focused Android platform-neutral connect guidance render evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusScreenShowsPlatformNeutralConnectGuidanceAcrossSupportedLanguages -Pkotlin.incremental=false` passed after proving `ConnectionStatusScreen` renders the neutral saved-route and paused-auto-reconnect guidance across English, Korean, Japanese, Simplified Chinese, and French.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android chat-history bulk action disabled-state and platform-neutral connect guidance render pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused Android model-refresh and New Chat accessibility evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsModelRefreshActionLocalizesReadinessStates --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.appTopBarKeepsNavigationModelPickerAndNewChatChrome --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.newChatActionsExplainDisabledStreamingStateAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the model-refresh and New Chat disabled-reason pass.
- Latest focused macOS sidebar preference accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testSidebarPreferencePickerAccessibilityValuesUseSelectedLanguage` passed after the sidebar preference accessibility-value pass.
- Latest focused macOS page-header accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testCompanionPageHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks` passed after the page-header accessibility pass.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android diagnostic QR text state-accessibility pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused Android rename-chat dialog evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.renameChatSessionDialogExposesTitleReadinessAndHaptics -Pkotlin.incremental=false` passed after the rename readiness accessibility pass.
- Latest full no-device gate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the rename readiness accessibility pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused Android suggested-question action evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenNormalizesSuggestedQuestionChips -Pkotlin.incremental=false` passed after the suggested-question action-label pass.
- Latest focused macOS Pairing QR generation accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testPairingQRGenerationActionAccessibilityUsesSelectedLanguage` passed after the QR generation action accessibility pass.
- Latest focused macOS active Pairing QR renewal evidence: `swift test --filter AetherLinkLocalizationTests/testPairingQRGenerationActionAccessibilityUsesSelectedLanguage` passed after the active QR renewal accessibility-hint pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the active Pairing QR renewal accessibility-hint pass; it still explicitly excludes physical install, camera QR scan, real device haptics, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest focused macOS Connection Recovery QR action evidence: `swift test --filter AetherLinkLocalizationTests/testConnectionRecoveryGenerateLatestQRActionAccessibilityUsesSelectedLanguage` passed after the Connection Recovery QR action accessibility pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Connection Recovery QR action accessibility pass.
- Latest focused Android composer input readiness evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsComposerReadinessHintWhenPreviousChatCannotSend --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenSendButtonLocalizesReadinessStateAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingShowsCancelActionInsteadOfSend -Pkotlin.incremental=false` passed after the composer input readiness accessibility pass.
- Latest focused Android reasoning accessibility evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRendersReasoningCollapsedAndExpandable --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenReasoningSummaryLocalizesAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the reasoning accessibility-summary pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android composer input readiness accessibility pass.
- Latest focused Android backend readiness banner evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenBackendUnavailableBannerExposesAccessibilitySummaryAndRefreshCallback --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenBackendUnavailableSummaryResourceFormatsAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the backend readiness banner accessibility-summary pass.
- Latest focused Android chat model-picker row-summary evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerRowsExposeAccessibilitySummaries --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages -Pkotlin.incremental=false` passed after the chat model picker row-summary accessibility pass.
- Latest focused Android provider diagnostics named-label evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusProviderDiagnosticsToggleExposesExpandedState -Pkotlin.incremental=false` passed after the provider-specific diagnostic toggle accessibility-label pass.
- Latest focused Android provider diagnostics and attachment disabled-state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusProviderDiagnosticsToggleExposesExpandedState --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsComposerReadinessHintWhenPreviousChatCannotSend` passed after the provider diagnostics and attachment disabled-state accessibility pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the provider diagnostics and attachment disabled-state accessibility pass.
- Latest focused Android message-copy evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMessageCopyActionsExposeLocalizedActionLabels` passed after the message-copy accessibility-label pass.
- Latest focused Android code-block copy evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenCodeBlockCopyUsesLocalizedCodeActionLabels` passed after the code-block copy accessibility-label pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android code-block copy accessibility-label pass.
- Latest focused Android send/discovery accessibility evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenSendButtonLocalizesReadinessStateAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDiscoveredRuntimeUnavailableRowsExposeContextualAccessibilityLabels` passed after the send readiness and discovered-runtime unavailable summary pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android send readiness and discovered-runtime unavailable summary pass.
- Latest focused Android Memory capped-label evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsCapLongActionAccessibilityLabels` passed after the Memory action-label cap pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android Memory action-label cap pass.
- Latest focused Android Memory add-state evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryAddButtonLocalizesReadinessStateAcrossSupportedLanguages` passed after the Memory add readiness-state pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android Memory add readiness-state pass.
- Latest focused macOS Pairing QR time-remaining evidence: `swift test --filter AetherLinkLocalizationTests/testPairingQRExpirationProgressAccessibilityUsesSelectedLanguage` passed after the Pairing QR time-remaining accessibility pass.
- Latest focused macOS sidebar brand evidence: `swift test --filter AetherLinkLocalizationTests/testSidebarBrandAccessibilityLabelUsesSelectedLanguage` passed after the sidebar brand accessibility-label pass.
- Latest focused Android Settings preference evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPreferenceRowsExposeSelectedStateToAccessibility` passed after the Settings preference option accessibility-summary pass.
- Latest focused Android Settings expandable-section evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsExpandableSectionsExposeLocalizedExpandedState` passed after the duplicate icon semantics pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android Settings expandable-section duplicate icon semantics pass.
- Latest focused Android chat empty route-guidance evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRouteRecoveryEmptyStateShowsFullGuidanceOnNarrowWidth` passed after the route guidance full-wrap pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android chat empty route-guidance full-wrap pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the macOS sidebar brand and Android Settings preference accessibility passes.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the macOS Pairing QR time-remaining accessibility pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android message-copy accessibility-label pass.
- Latest focused Android Settings chat-history search evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistorySearchClearsWithContextAndHapticFeedback --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistorySearchLocalizesClearAndNoResultsAcrossSupportedLanguages` passed after the Settings chat-history search accessibility pass.
- Latest no-device gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android Settings chat-history search accessibility pass.
- Latest focused Android chat top-bar model-search evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerSearchClearsWithContextAndHapticFeedback --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerSearchLocalizesClearAndNoResultsAcrossSupportedLanguages` passed after the model-search accessibility pass.
- Latest focused Android QR scanner evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest -Pkotlin.incremental=false` passed after the blocked camera-permission settings recovery pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android QR scanner blocked-permission recovery pass.
- Latest focused Android embedding-model row evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelRowsExposeSelectedStateToAccessibility --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsSavedEmbeddingModelRowLocalizesAccessibilitySummaryAcrossSupportedLanguages` passed after the embedding-model row accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android embedding-model row accessibility pass.
- Latest focused Android drawer-search evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerChatSearchFiltersClearsAndUsesHapticFeedback --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerChatSearchLocalizesClearAndNoResultsAcrossSupportedLanguages` passed after the drawer search accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android drawer chat-search accessibility pass.
- Latest focused macOS Connection Recovery form evidence: `swift test --filter AetherLinkLocalizationTests/testConnectionRecoveryFormFieldAccessibilityValuesUseSelectedLanguageAndHideSecrets` passed after the form-field accessibility pass.
- Latest focused macOS no-device identity evidence: `swift test --filter AetherLinkLocalizationTests`, `swift test --filter AetherLinkRenderSmokeTests`, and `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease` passed after the XCTest runtime-identity fallback pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS Connection Recovery form-field accessibility and XCTest runtime-identity stabilization pass.
- Latest focused Android drawer-row localization evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerItemsLocalizeAccessibilitySummariesAcrossSupportedLanguages` passed after the five-language drawer row summary pass.
- Latest focused Android drawer-row accessibility evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerItemsShowRuntimeProcessingStatus` passed after the Android chat drawer row accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android chat drawer row accessibility pass.
- Latest focused locale-format evidence: `swift test --filter AetherLinkLocalizationTests/testCompanionByteCountFormattingUsesSelectedAppLanguage` and `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenAttachmentSizeUsesSelectedAppLanguageContext` passed after the app-language file size formatting pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the app-language file size formatting pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS first-run Connection Recovery visibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android chat attachment accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android Settings connection accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android message attachment accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android suggested-question and macOS Pairing QR accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS trusted-device remove accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS Activity technical-details accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS provider details and Android bulk chat expander accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS Readiness row and Android refresh-health copy accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS route diagnostic details accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android diagnostic endpoint expander accessibility pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android model picker install action cue pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS trusted-device removal confirmation localization pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS connection-disable accessibility polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS provider-status pill accessibility polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS runtime status summary accessibility polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS model row accessibility polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android composer action accessibility polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS relay status row accessibility polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS trusted-device row accessibility polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android Memory delete haptic timing polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android chat-history haptic timing polish pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android confirmation cancel haptic consistency pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android confirmation-open haptic consistency pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android Settings expired-route primary QR action pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS global QR generation availability and Android connected Settings redundant-connect guard pass.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the macOS app-language date formatting pass.
- Latest focused macOS date-format evidence: `swift test --filter AetherLinkLocalizationTests/testCompanionDateFormattingUsesSelectedAppLanguage` passed after the macOS app-language date formatting pass.
- Latest focused macOS QR command evidence: `swift test --filter AetherLinkLocalizationTests/testToolbarAndMenuPairingQRGenerationUsesSharedAvailabilityContract` passed after the macOS global QR generation availability pass.
- Latest focused Android connected Settings evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsConnectedTrustedRuntimeDoesNotExposePairingConnectButton -Pkotlin.incremental=false` and `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsExpiredRelayRoutePrimaryActionScansLatestQrWithHaptic -Pkotlin.incremental=false` passed after the connected Settings redundant-connect guard.
- Latest focused Android Settings route-recovery evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsExpiredRelayRoutePrimaryActionScansLatestQrWithHaptic -Pkotlin.incremental=false`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after the Android Settings expired-route primary QR action pass.
- Latest focused Android haptic evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetRequiresConfirmation --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenPerChatHistoryActionsUseConfirmationHaptics --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsExposeContextualActionAccessibility -Pkotlin.incremental=false`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after the Android confirmation-open haptic consistency pass.
- Latest focused Android haptic evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetRequiresConfirmation -Pkotlin.incremental=false`, `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest -Pkotlin.incremental=false`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after the Android confirmation cancel haptic consistency pass.
- Latest focused Android haptic evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenPerChatHistoryActionsUseConfirmationHaptics -Pkotlin.incremental=false`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after the Android chat-history haptic timing polish pass.
- Latest focused Android haptic evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsExposeContextualActionAccessibility -Pkotlin.incremental=false`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after the Android Memory delete haptic timing polish pass.
- Latest focused macOS accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testTrustedDeviceRowAccessibilityLabelUsesDeviceContext`, `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after the macOS trusted-device row accessibility polish pass.
- Latest focused macOS accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testRelayStatusRowAccessibilityLabelUsesTitleStatusAndDetail`, `python3 script/check_macos_localization.py`, and `python3 script/check_copy_hygiene.py` passed after the macOS relay status row accessibility polish pass.
- Latest focused Android accessibility evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenAcceptsInputAndSendWhenConnectedModelIsReady --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsComposerReadinessHintWhenPreviousChatCannotSend --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingShowsCancelActionInsteadOfSend -Pkotlin.incremental=false`, `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after the Android composer action accessibility polish pass.
- Latest focused macOS accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testModelRowAccessibilityLabelUsesModelContext`, `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed after the macOS model row accessibility polish pass.
- Latest focused macOS accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testRuntimeOverviewAccessibilityLabelUsesTitleStatusDetailAndFootnote`, `swift test --filter AetherLinkLocalizationTests/testStatusCardAccessibilityLabelUsesTitleStatusAndDetail`, `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed after the macOS runtime status summary accessibility polish pass.
- Latest focused macOS accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testProviderStatusPillAccessibilityLabelUsesProviderContext`, `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed after the macOS provider-status pill accessibility polish pass.
- Latest focused macOS accessibility evidence: `swift test --filter AetherLinkLocalizationTests/testRemoveSavedConnectionDetailsAccessibilityLabelUsesRouteContext`, `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed after the macOS saved-connection removal accessibility polish pass.
- Latest focused macOS localization evidence: `swift test --filter AetherLinkLocalizationTests/testTrustedDeviceRemovalMessageUsesSelectedLanguageAndKeyFingerprint --filter AetherLinkLocalizationTests/testTrustedDeviceRemoveButtonAccessibilityLabelUsesDeviceContext`, `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, and `python3 script/check_docs_hygiene.py` passed after the macOS trusted-device removal localization polish pass.
- Latest focused copy evidence: `python3 script/check_android_string_parity.py` and `python3 script/check_copy_hygiene.py` passed after the Android client UI copy boundary guard pass.
- This does not prove physical install, camera QR scan, real device haptics, launcher screenshots, live-backend chat/cancel, or real different-network runtime connectivity.
- No GPT-5.3-Codex-Spark subagent was used for this pass.

## 2026-06-26 Runtime-Side Context Compaction

The Android phone is currently disconnected. The current context-compaction evidence is runtime unit/source evidence only:

- The first runtime-side compaction slice is documented as a `chat.send` backend-call shaping path: if active history is too large for the heuristic character budget, AetherLink Runtime preserves recent client-visible messages verbatim and injects a backend-only system summary of older active turns.
- `LocalRuntimeMessageRouter` now applies that compaction after runtime capability guard and runtime-owned memory injection, but before calling Ollama or LM Studio through the mediated backend.
- The documented contract keeps compaction out of client-visible chat history, `chat.messages.list`, `chat.sessions.list`, archive state, and delete state.
- Archived and deleted chats remain excluded from compaction inputs unless a future permissioned workflow explicitly restores or selects eligible sources.
- Capability guard context, runtime-owned memory context, and compaction summaries remain separate runtime-only system context before the backend call.
- Focused Swift coverage proves short chats are not compacted, large active histories are compacted before backend dispatch while stored request events keep the original visible messages, and capability guard/runtime memory/compaction summaries remain separate system contexts.
- The default no-device gate now includes the focused compaction regressions and names heuristic runtime chat context compaction in its coverage summary.
- Tokenizer-aware budgets, LLM-generated summaries, durable source pointers, reasoning summaries, and longer-inactivity memory summaries remain future work.
- This does not prove physical install, camera QR scan, live provider output quality, or real different-network runtime connectivity.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendDoesNotCompactShortConversation`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate`
- `python3 script/check_copy_hygiene.py && python3 script/check_android_string_parity.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift docs/architecture.md docs/protocol.md docs/roadmap.md docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`

Broader follow-up: `swift test --filter LocalRuntimeMessageRouterTests` initially exposed unrelated environment-driven remote relay tests, but the later remote relay QR allocation stabilization fixed that suite. The new context-compaction tests now pass individually, in the broader suite, and through the project no-device gate.

## 2026-06-26 Remote Relay QR Allocation Stabilization

The Android phone is currently disconnected. The latest remote-relay QR allocation evidence is macOS runtime unit/source evidence only:

- A `CompanionAppModel` route-preparation bug was fixed so automatic remote route allocation covers allocator capability, dynamic bootstrap environment, and saved bootstrap relay settings.
- Bootstrap restore, QR regeneration with expired saved leases, relay-failure renewal, private-overlay lease waiting, loopback rejection, and CGNAT/private-overlay readiness paths are covered by `LocalRuntimeMessageRouterTests`.
- QR route policy remains conservative: ordinary loopback, private LAN, link-local, and CGNAT-style routes are not treated as normal unrelated-network QR-ready routes. Private-overlay routes require explicit private-overlay policy and lease material.
- The earlier full-suite failure is no longer current: `swift test --filter LocalRuntimeMessageRouterTests` now passes with 120 tests and 0 failures.
- The default no-device quality gate now directly includes the formerly failing remote relay lease-renewal and QR eligibility regressions, and copy hygiene requires those test names plus the gate coverage phrase to remain present.
- This does not prove physical install, camera QR scan, physical haptics, live backend chat/cancel, or real different-network runtime connectivity.

Verified after this change:

- `swift test --filter LocalRuntimeMessageRouterTests`
- `python3 script/check_docs_hygiene.py && python3 script/check_copy_hygiene.py`
- `./script/check_no_device_quality.sh`

## 2026-06-26 Physical Different-Network Check

The connected Android phone was on cellular/different-network routing while USB was available only for automation and logs. A USB-assisted external-relay smoke intentionally avoided `adb reverse` for the relay and advertised the Mac private address `192.168.0.102:<ephemeral>` in the QR route.

- Expected result: failure, because a cellular phone cannot reach the Mac private LAN address without a public relay, tunnel, VPN, private overlay, port-forwarded route, or future decentralized bootstrap layer.
- Observed result: Android accepted the pairing URI, attempted the relay route, and logged `remote_route_unreachable` with `route_diagnostic_relay_failed`. The runtime reached `relay status=waiting_for_peer`; the relay accepted the runtime side but not the phone side.
- Evidence value: this proves current failure is route reachability, not QR parsing, app launch, model provider access, or chat pipeline behavior.
- Product status: arbitrary different-network QR pairing is not successful yet in the current local-only environment. It requires a reachable relay/P2P route before QR-only pairing can work across unrelated networks.
- Latest rerun: the phone again reported cellular as the active default network and no active Wi-Fi network. A local allocation relay on the Mac accepted the runtime peer only; the Android peer never reached the relay, then logged `remote_route_unreachable` with `route_diagnostic_relay_failed` from a cellular source address to the Mac private LAN route.
- Preserved latest artifacts: `build/qa/aetherlink-cellular-private-relay-runtime-20260626-1531.log`, `build/qa/aetherlink-cellular-private-relay-logcat-initial-20260626-1531.txt`, `build/qa/aetherlink-cellular-private-relay-logcat-final-20260626-1531.txt`, and `build/qa/aetherlink-cellular-private-relay-20260626-1531.png`.
- Guardrail added: `script/no_adb_external_relay_pairing_smoke.sh` now writes a run `summary.json` and can require explicit `DIFFERENT_NETWORK` or `CELLULAR` confirmation before waiting, so local artifact runs cannot be confused with cross-network proof.
- Follow-up guardrail: the default no-device gate now rejects link-local relay hosts even when `--allow-private-relay` is passed, keeping script preflight aligned with Android QR parser and schema policy. Private overlay means a user-controlled VPN/tunnel/overlay route, not `169.254.x.x`, `fe80::`, multicast, loopback, or local-only names.
- Follow-up guardrail: macOS runtime tests now prove bootstrap relay endpoint failover before QR generation. If the first bootstrap relay allocation fails and a later endpoint succeeds, only the successful relay endpoint, id, secret, lease, and nonce are written into the pairing QR.
- Current implementation update: macOS can now persist Bootstrap Relay settings in the Companion UI and use them to allocate QR route lease material before generating the pairing QR. This removes the env-var-only setup path, but it does not create a public relay by itself; the configured bootstrap relay still must be reachable from both the runtime host and the phone's different network.
- Current implementation update: relay allocation preflights now send `preflight=1`, allowing scripts to validate bootstrap reachability and token authorization without persisting throwaway leases in the relay allocation store.
- Current implementation update: runtime bootstrap preflight can now emit `--summary-json` with endpoint, success/failure, allocation-field, and caveat data. The default no-device gate checks both a successful local-relay summary and a rejected link-local summary.
- Current implementation update: Android Chat route-failure UX now distinguishes saved route unreachable, relay QR route unreachable, and identity-only QR with no reachable route in English, Korean, Japanese, Simplified Chinese, and French. The copy points the user back to preparing a reachable AetherLink Runtime route and scanning the latest QR.
- Latest route probe: with the physical device `R3CXC0M76VM` on active default `MOBILE[LTE]`, a temporary relay bound on the runtime host and advertised as `192.168.0.102:<ephemeral>` failed from the device network with `nc: Timeout`. Preserved artifacts: `build/qa/aetherlink-different-network-relay-probe-20260626-163341.json`, `build/qa/aetherlink-different-network-relay-20260626-163341.log`, and `build/qa/aetherlink-different-network-integrated-relay-20260626-163405.log`.
- Latest integrated smoke: `script/android_pairing_deeplink_smoke.sh --relay --external-relay-host 192.168.0.102 --external-relay-port <ephemeral> --allow-private-relay --skip-install --probe-external-relay-from-device` exited 21 before QR injection. This is the desired diagnostic behavior for an unreachable advertised route; it is not successful arbitrary-network pairing.
- Route-refresh update: `RuntimeDevServer` now wires `route.refresh` to fresh relay allocation, and the headless relay smoke now validates the refreshed route response and reconnects with the refreshed route material.
- Current headless route-refresh evidence: `./script/runtime_authenticated_mock_smoke.swift --relay` passed after checking relay QR material, pairing, auth, `route.refresh`, runtime health, model list, model pull, streaming chat, cancel, and saved trusted relay reconnect.
- Current physical route probe: with the physical device `R3CXC0M76VM` still on active default `MOBILE[LTE]`, a temporary local relay bound on the runtime host and advertised as `192.168.0.102:43171` failed from the device network with `nc: Timeout`. Preserved artifact: `build/qa/aetherlink-different-network-relay-probe-20260626-lte-private-ip.json`.
- Current physical app smoke: `script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect --expect-chat-cancel` passed on `R3CXC0M76VM`, installing the current debug APK, injecting a pairing URI, pairing over development relay mode, relaunching the app, reconnecting from saved trusted route state, and observing `chat.send`, `chat.delta`, `chat.cancel`, and `chat.done` through the physical Android UI. Preserved artifacts: `build/qa/aetherlink-runtime-relay-chat-smoke-20260626-1653.log`, `build/qa/aetherlink-relay-chat-smoke-20260626-1653.log`, `build/qa/aetherlink-pairing-chat-smoke-20260626-1653.png`, and `build/qa/aetherlink-chat-cancel-smoke-20260626-1653.png`.
- Current conclusion: QR pairing and the app/runtime relay pipeline are now working in local development and USB-assisted physical smoke paths. True unrelated-network pairing is still blocked until the QR carries a relay/P2P route that the phone and runtime host can both reach, such as a public, VPN, tunnel, or private-overlay relay endpoint. Mac private LAN addresses remain expected failures from LTE.
- Latest no-device UI evidence: the macOS Advanced Connection Setup / Connection Recovery surface now shows a connection-scope status row that distinguishes reachable connection details, automatic QR connection preparation, local diagnostic loopback, local-network-only `.local` or private addresses, explicit private-overlay addresses, and missing route details. This is localization/render/source evidence only, not proof of physical different-network reachability.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the connection-scope UI update. The gate still explicitly excludes physical install, camera QR scan, real device haptics, launcher/Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.

## 2026-06-25 No-Device Checkpoint

The Android phone is currently disconnected. The following evidence is valid for source-level, unit-level, and no-device runtime behavior only:

- Android connection notices now have no-device source/unit evidence that a compact status pill distinguishes connected, diagnostics, refresh-needed, saved-connection, nearby, and scan-QR states across the supported five UI languages. This is not physical-device visual evidence.
- Android connection notices now also have no-device Compose evidence that the actual `ConnectionStatusScreen` renders the saved-connection status pill and exposes the same value through `stateDescription` semantics for accessibility. This is not physical TalkBack evidence.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android connection notice accessibility pass. The gate still explicitly excludes physical install, camera QR scan, real device haptics, launcher/Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Latest no-device gate: `./script/check_no_device_quality.sh` passed after the Android connection status pill update. The gate still explicitly excludes physical install, camera QR scan, real device haptics, launcher/Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity.
- Android language and appearance support is guarded by `script/check_android_string_parity.py`. The checker now verifies string parity, placeholder parity, the supported language set, the English first-run default, the system/light/dark appearance contract, and the app theme wiring that applies the saved preference.
- Android Settings language and appearance option order is guarded by focused unit tests. The visible language selector is pinned to English, Korean, Japanese, Simplified Chinese, and French only; the appearance selector is pinned to system, light, and dark.
- macOS runtime localization is guarded by `script/check_macos_localization.py`. The checker now verifies string parity, format placeholders, source `NSLocalizedString` coverage, the supported language set, the English default, the stable language storage key, the system/light/dark appearance contract, and the app/sidebar wiring that applies the saved appearance preference.
- macOS runtime language picker options are guarded by `AetherLinkLocalizationTests`, keeping the sidebar picker aligned with the initial English, Korean, Japanese, Simplified Chinese, and French launch set.
- macOS runtime localized string lookup is guarded by `AetherLinkLocalizationTests`, proving the stored app language drives module string lookup and unsupported stored languages fall back to English.
- macOS runtime appearance preferences are guarded by `AetherLinkLocalizationTests`, keeping the sidebar appearance picker aligned with system, light, and dark while defaulting to system appearance.
- macOS SwiftUI visible text localization is guarded by `script/check_macos_localization.py`; visible `Text`, `Button`, `Label`, `Picker`, `Toggle`, text-field, alert, and confirmation-dialog literals must use `NSLocalizedString` so the app language setting applies.
- Android compile and selected ViewModel tests have been run without a connected phone.
- macOS runtime build and localization checks have been run without a connected phone.
- Runtime model routing has test coverage that blocks unknown or non-installed model names instead of falling back to a backend.
- Headless QR pairing over direct local diagnostics has been verified with `./script/runtime_authenticated_mock_smoke.swift`.
- Headless QR pairing over the development relay path has been verified with `./script/runtime_authenticated_mock_smoke.swift --relay`; this covers no-device relay allocation, QR route parsing, pairing, authenticated runtime traffic, streaming chat, cancellation, and trusted relay reconnect.
- No-ADB QR artifact generation, QR PNG render, and QR decode round trip have been verified with `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only`. In local relay emit-only mode this is artifact/contract evidence only, not proof of optical QR scan or external-network relay reachability.
- Development relay allocation-token gating has unit/build/smoke evidence: relay allocation parsing accepts `allocation_token=<token>`, the runtime bootstrap allocator passes `AETHERLINK_BOOTSTRAP_RELAY_ALLOCATION_TOKEN`, and the no-ADB QR emit-only smoke can allocate route material from a token-required local diagnostic relay.
- Cross-platform compact relay QR contract is guarded in the default no-device gate from Swift generation through `shared/protocol/fixtures/macos-compact-relay-pairing-uri.txt` and `shared/protocol/fixtures/macos-compact-private-overlay-pairing-uri.txt` to Android core parsing and Android relay reconnect planning.
- Pairing QR schema checks now verify complete compact relay fixture material, forbid local direct fields in the shared remote fixture, and accept the digit-string representation produced by URL query decoding.
- Runtime-owned chat storage is guarded by macOS tests that reconstruct transcripts from runtime JSONL events and expose latest processing state in session summaries.
- Android device storage is guarded so runtime-owned sessions keep metadata but do not persist message bodies as the durable mobile transcript; transcripts should be fetched from AetherLink Runtime when needed.
- Android runtime-owned transcript rehydration is guarded so an active redacted session requests `chat.messages.list` after reconnecting and syncing `chat.sessions.list`.
- Android QR/deeplink route handling has unit coverage for compact relay QR parsing, relay-first pairing request routing, trusted relay reconnect planning, and unreachable relay QR error classification.
- Android QR/deeplink route handling now also has no-device regression coverage that route-bearing relay QR payloads remain persisted after an initial relay connection failure and are restored after ViewModel recreation to send `pairing.request` without direct TCP fallback.
- The default no-device quality gate now runs the Android QR parser contract plus focused compact-relay QR regressions, so QR route material stripping, pending route loss, and ViewModel recreation regressions are checked before handoff even when the phone is disconnected.
- The Android ViewModel scan path also consumes the macOS private-overlay compact relay fixture, proving scoped private-overlay relay material reaches the relay connector and sends `pairing.request` without falling back to direct TCP in no-device tests.
- Archive/permanent-delete behavior is now part of the default no-device quality gate: Android guards active-session delete rejection, archive-all retention with Memory/Reflection/Research exclusion, archived-only permanent delete, runtime-owned deletion suppressions, and archived runtime-owned body redaction; macOS guards runtime-store archive/restore/delete lifecycle and protocol-router rejection of active-session delete.
- Runtime-owned memory is now part of the default no-device quality gate: Android guards enabled-memory-only chat context injection, runtime-result replacement/mutation of cached memory, and memory/history/attachment capability advertisement; macOS guards `memory.upsert`, `memory.list`, and `memory.delete` against the runtime JSONL memory store.
- Runtime-mediated attachments are now part of the default no-device quality gate: Android guards attachment-only locale prompts, final-user-message-only attachment payloads, attachment metadata/byte loading through the ViewModel seam, Base64 payload creation, max attachment count, localized over-limit feedback, oversized-file short-circuiting, composer send enablement, non-vision image blocking, pending attachment removal, blank-send suppression, valid attachment cleanup, stored attachment metadata rehydration, and read-only message chips; macOS guards document extraction into `chat.send`, MIME-only structured text attachments, vision-image gating, LM Studio image forwarding, unsupported attachment structured errors, and qualified LM Studio chat routing.
- Chat and Memory indexing model separation is now part of the default no-device quality gate: Android guards embedding-model rejection as a chat target, persisted chat/embedding selections across restoring and missing model-list states, wrong-kind/uninstalled model reconciliation, and explicit embedding clear behavior; macOS guards Ollama/LM Studio embedding classification plus aggregate/router rejection of embedding models as chat routes.
- Runtime-generated chat titles are now part of the default no-device quality gate: Android guards first-completed-turn title request eligibility, first-prompt title sanitization, and manual/runtime title preservation, while macOS guards automatic title generation after the first response, inline think stripping, and deterministic fallback when backend title output is invalid.
- Runtime-generated next questions are now part of the default no-device quality gate: Android guards latest-assistant-only attachment, candidate locale handoff, duplicate regeneration suppression, and blank assistant placeholder rejection, while macOS guards structured/fenced suggestion parsing, invalid-output empty results, and localized numbered-list fallback parsing.
- Android scanner QR acceptance now shares the runtime pairing parser policy, so incomplete legacy pair links do not close the camera scanner before they can be rejected by the real pairing parser.
- Android exported pairing deep links are scoped to `aetherlink://pair` and legacy `lab://pair`; unrelated custom-scheme actions are not accepted by the manifest-level browsable filter.
- Android runtime-boundary route generation now blocks selected Bonjour and discovered direct routes on model-provider ports `11434` and `1234`, preserving the client-to-runtime boundary even when discovery metadata matches a trusted runtime.
- Android QR/deeplink/runtime-boundary policy is now pinned by `script/check_copy_hygiene.py`: the manifest must stay pair-host scoped, scanner raw-value acceptance must use the runtime pairing parser, DirectTcp candidates must block `11434` and `1234`, and the matching Android regression tests must remain present.
- Android optical QR scanning now keeps scanning after ordinary ML Kit per-frame barcode processing failures; only camera permission/setup/bind failures should terminate the scanner. URI acceptance remains limited to `aetherlink://pair` and legacy `lab://pair`.
- Android manual QR payload entry now reuses the same QR raw-value validation contract as camera scanning, so pasted values must be `aetherlink://pair` or legacy-compatible `lab://pair`; generic URLs and other AetherLink actions are rejected by unit coverage.
- Android QR route diagnostics copy now distinguishes identity-only QR scans from QR scans that include remote connection details. The pending route and endpoint-unavailable messages explain that nearby discovery only works when the same local route is visible, while different-network use requires a latest QR with connection details.
- Android non-route error cards now preserve structured `RuntimeUiError.detail` strings when present, so invalid QR, pairing rejection, discovery, send, and runtime-returned details are not silently hidden.
- Android visible error details now include a last-mile redaction guard: safe structured details render, but model-provider URLs, host:provider-port strings for `11434` or `1234`, direct backend API paths, and Ollama/LM Studio URL wording are suppressed before display.
- Android chat-shell polish has unit coverage for compact suggested-question chips, route-auth QR refresh handling, no static center prompt in empty chats, and state-based suggestion visibility after real assistant output. It still needs fresh physical-device screenshots and touch validation.
- Android reasoning display policy has unit coverage so collapsed reasoning stays dimmed, capped to three lines, and expandable to the full text only when the reasoning content needs it.
- Android thinking preview polish has unit coverage that long single-paragraph thinking previews are capped before expansion, while the five-language visible copy now uses softer Thinking wording instead of technical Reasoning wording.
- Android thinking preview now has helper-level unit evidence that reasoning stays short and dim by default, expands only on request, and suppresses the generic typing placeholder while a reasoning stream is still open.
- The default no-device gate now also runs Android ViewModel reasoning-state regressions for `reasoning_delta`, `thinking_delta`, inline `<think>` splitting across streamed deltas, and incomplete think cleanup on `chat.done`, so state-level reasoning cannot regress into the assistant answer body while physical-device testing is unavailable.
- Android chat message rendering now has parser unit evidence for closed fenced code blocks, unclosed fenced code blocks, and malformed fences without a newline.
- Android chat-composer quietness has unit coverage that preserves the accessibility input label while requiring no visible generic placeholder resource.
- Android quiet empty-chat guard removes ready-state static center prompt resources and keeps unit coverage proving connected/model-ready empty chats stay visually blank until the user types or assistant-generated next questions arrive after a response.
- Android runtime trust copy guard now blocks reintroducing ready-state empty-chat resources and visible `runtime identity` wording in Android string resources.
- Android multilingual trust-copy guard removes localized identity wording from QR/pairing/discovery errors and blocks those terms in English, Korean, Japanese, Simplified Chinese, and French string resources.
- Android pairing-first Settings hierarchy has helper-level unit coverage so first launch and pending QR-route states start with pairing instead of the generic Settings header.
- Android release UX has helper-level unit coverage and copy-hygiene script coverage that keeps manual route/discovery troubleshooting hidden unless the centralized developer-diagnostics state is enabled; app wiring is guarded so Settings receives `showDeveloperDiagnostics`, and ordinary debug launches still keep manual route/discovery troubleshooting hidden unless explicitly requested.
- Android adaptive navigation has compile/unit evidence for an expanded-width left rail with Settings anchored below the primary chat navigation while compact screens keep the modal drawer.
- Android product-copy polish has resource/compile evidence that chat history archive/delete semantics, hidden troubleshooting routes, and the separate Memory indexing model wording are aligned across English, Korean, Japanese, Simplified Chinese, and French.
- Android product-copy polish now has resource and unit-test evidence that QR text fallback, USB/emulator connection labels, and provider detail/reference-code labels use release-facing wording across English, Korean, Japanese, Simplified Chinese, and French.
- Android release-copy values are now pinned by `script/check_android_string_parity.py`, so QR fallback labels, USB/emulator connection labels, provider status detail, provider reference code, and details show/hide labels cannot silently regress while locale parity still passes.
- Android chat-history danger actions are guarded by `script/check_copy_hygiene.py`; bulk archive/delete controls must stay hidden behind Manage all chats, destructive flows must use two-step confirmation copy, and permanent delete must remain limited to archived chats.
- Android Settings chat-history search has helper-level unit coverage for filtering active/archived saved chats by title, model id, runtime event, finish reason, error code, and untitled fallback while leaving bulk danger actions scoped to the full chat sets.
- Android Settings chat-history runtime status labels have helper-level unit coverage for displaying localized completed, cancelled, needs-attention, and in-progress states from runtime-owned session metadata without changing archive/delete or storage semantics.
- Android Settings density has helper-level unit coverage that keeps Memory indexing model, Memory, and Chat history as lower-priority collapsed-by-default expandable sections while Pairing/Connection and Preferences remain immediately visible; the implementation reuses existing localized labels and suppresses duplicated nested headers with `showHeader=false`.
- Android chat top-bar model menu now has helper-level unit evidence for a separate Memory indexing model section. Installed runtime-host-local embedding models can be selected from the chat model menu without being mixed into the normal chat model list, and the selected embedding model is pinned in that section.
- Android model-menu search now has helper-level unit evidence that search stays available when only embedding models are present and that embedding empty states distinguish search misses from unavailable runtime models.
- Android Memory indexing model error copy is now release-value guarded across English, Korean, Japanese, Simplified Chinese, and French so it no longer points only to Settings after chat top-bar embedding selection was added.
- Android copy hygiene now guards the chat top-bar Memory indexing model wiring itself: `MainActivity` must keep `selectEmbeddingModel`, embedding-menu rows, separate embedding filtering, search availability, empty-state helpers, and the focused helper tests.
- Android haptic feedback now has source/test guard coverage: `script/check_copy_hygiene.py` pins the central AetherLink haptic helper and core QR, navigation, chat, composer, suggestion, attachment, copy, settings, and selection de-duplication wiring, while `AppNavigationTest` covers the haptic policy mapping.
- AetherLink icon assets now have source-level QA coverage through `script/check_app_icons.py`, which verifies the user-provided source image, Android launcher/adaptive icon assets, and macOS `AppIcon.icns` chunk coverage. Android resource processing and `swift build --product AetherLink` also passed with the current icons.
- Apache 2.0 licensing now has source-level QA coverage through `script/check_license.py`, which verifies the root `LICENSE`, root README license section, nested README license sections, and stale/conflicting license wording.
- macOS saved connection details copy is guarded across English, Korean, Japanese, Simplified Chinese, and French by `script/check_macos_localization.py`, `script/check_copy_hygiene.py`, and `AetherLinkLocalizationTests`; the stale "saved connection settings" wording is forbidden.
- Attachment ingestion now has no-device source/test evidence for broad document intake: Android explicitly offers runtime-supported document MIME types including HWPML/HTML/RTF text variants, image selection remains vision-model gated, macOS extracts HWPML XML text, and `script/check_copy_hygiene.py` guards these contracts.
- Runtime-generated chat-title locale handoff has Android protocol coverage for `chat.send.locale`, macOS router coverage that automatic title prompts receive the locale hint after `chat.done`, and schema evidence that the field remains part of the Android-runtime JSON protocol.
- Android runtime-boundary hygiene is guarded by `script/check_copy_hygiene.py`; Android main source/resources must not introduce direct Ollama or LM Studio endpoint material, backend URL variables, or model-provider API paths.
- macOS companion QR-first polish has compile/localization evidence that Route Diagnostics stays hidden from the normal automatic-route pairing flow unless diagnostics are needed or already configured.
- macOS Route Diagnostics visibility is guarded by `script/check_copy_hygiene.py`; Pairing and Status surfaces must mount it through `shouldShowRouteDiagnosticsPanel(model:)`, keeping route address/port/secret fields out of the normal QR-first path.
- macOS QR route-readiness failures are now source/test guarded: `CompanionAppModel.remoteRoutePreparationIssue` exposes automatic route allocation failures, unreachable connection addresses, lease refresh failures, missing route secrets, and relay connection failures to Pairing, Status, and Advanced Connection Setup instead of leaving them only in logs.
- macOS Advanced Connection Setup now requires a destructive confirmation before saved cross-network connection details can be disabled; `script/check_macos_localization.py` guards the confirmation wiring and localized copy.
- macOS Connection Routes status now reflects the current remote route state, including connecting, waiting for a trusted device, matched/ready, reconnecting, failed, and stopped states.
- macOS Advanced Connection QR readiness copy now has source/localization evidence that prepared-but-not-ready relay routes show state-specific stopped, connecting, reconnecting, failed, and ready messages instead of one generic start/wait message.
- macOS product-copy polish has compile/localization evidence that Pairing, Status, Advanced Connection Setup, and Activity use trust-and-connection wording across English, Korean, Japanese, Simplified Chinese, and French.
- macOS product-copy polish now has localization and test evidence that visible Activity/provider redaction and connection-recovery surfaces use softer release-facing wording such as Details, provider address hidden, Connection Recovery, and protected connection key across English, Korean, Japanese, Simplified Chinese, and French.
- macOS release-copy values are now pinned by `script/check_macos_localization.py`, and `AetherLinkLocalizationTests` resolves the English connection/details strings directly to guard release-facing copy separately from localization key presence.
- macOS stale product-copy cleanup removed unused route-material/runtime-identity/listener/diagnostics localization keys and added a regression guard so visible macOS `NSLocalizedString` keys and `Localizable.strings` entries cannot reintroduce those prototype terms.
- macOS technical-details copy guard removes stale Logs/Diagnostics/route localization leftovers and keeps provider low-level detail behind `Technical Details` instead of visible diagnostics wording.
- macOS Activity now has two endpoint/secret-redaction layers: CompanionCore sanitizes stored log entries before inserting them into `CompanionAppModel.logs`, and Activity `Technical Details` redacts any remaining provider endpoint/API or route-secret material before display. `script/check_macos_localization.py` guards both wiring points and the localized redaction copy.
- Development relay QR readiness now requires an accepted runtime registration acknowledgement before the runtime reports `waitingForPeer`; a raw TCP-ready connection is no longer enough to make a relay route QR-ready.
- Android route-refresh cleanup now has unit evidence that manual disconnect and forget-trusted-runtime cancel scheduled refresh retry work, clear the pending refresh request id, and prevent later `route.refresh` sends after cleanup.
- Android connection cleanup now has unit evidence that disconnect clears pending runtime-owned chat rename requests, preventing stale rename state from surviving after the runtime channel is closed.
- Android provider status details now have ViewModel and UI-helper unit evidence that backend URLs, local model ports, and provider API paths are redacted before they become visible client diagnostics.
- Android provider status details now also have ViewModel and UI-helper unit evidence that route/relay/pairing secrets, including `route_token`, `routeToken`, `relay_secret`, `relaySecret`, `pairing_secret`, `rt`, and `rs`, are redacted before visible diagnostics.
- Android provider diagnostics visibility now has helper-level unit evidence that a fully redacted provider message/code does not leave behind an empty expandable diagnostics panel.
- Android runtime-boundary hygiene now requires the provider endpoint and route-secret redaction guards, plus the matching Android tests, before `script/check_copy_hygiene.py` passes.
- Android/macOS model-source copy hygiene now rejects user-facing `Cloud` labels and cloud-default/recommended wording while leaving protocol/schema/docs references, implementation enum values, and provider names out of scope. Current Android/macOS app resources use provider-managed wording instead of Cloud labels.
- Android haptic feedback policy now has helper-level unit evidence that ordinary actions, selection changes, and toggles stay on the lighter feedback path while destructive and clipboard actions stay distinct.
- Android main UI files now avoid direct `LongPress` or `TextHandleMove` haptic calls outside the shared policy helper for the current `MainActivity` and `ClientScreens` surfaces.
- Android route-safety notices now have helper-level unit evidence that no trusted runtime, missing route details, expired relay details, and remote route failures resolve to scanning the latest QR, while usable saved relay routes resolve to Connect and already-connected routes stay informational.
- Android chat auto-scroll now has helper-level unit evidence that assistant-only appended messages do not pull the user away from older messages, while local user-send bursts and near-bottom streaming still follow the latest row.
- Android thinking preview and code-block parsing have helper-level unit evidence from `AppNavigationTest`, including short dim reasoning previews, typing-placeholder suppression during open reasoning, and fenced code parsing cases.
- Android/macOS release-copy polish has current no-device evidence from Android app unit tests, macOS localization tests, localization parity checks, copy hygiene, and docs hygiene; this covers resource and copy contracts only, not physical-device feel.
- macOS model residency summaries have localization evidence for English, Korean, Japanese, Simplified Chinese, and French instead of raw English runtime event strings in the Status card.
- Platform-neutral product copy is guarded by `script/check_copy_hygiene.py`, including Android UI, macOS UI, runtime/provider-facing copy, and macOS pairing protocol messages.
- No GPT-5.3-Codex-Spark subagent was used for this workstream; GPT-5.5 workers used earlier were closed after their bounded tasks.

This checkpoint does not prove physical-device UX. Do not claim these behaviors are verified on a real phone until a fresh device run is recorded:

- APK install on the physical Android phone,
- camera-based QR scan,
- QR pairing completion,
- trusted runtime reconnect after app restart,
- physical haptic feel,
- device-level language switching,
- real streamed chat and cancel from the app, and
- different-network runtime connectivity through a reachable relay/P2P route.

## Current No-Device Evidence

The latest no-device checks prove only local/runtime/script behavior, not physical-device UX:

- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:compileDebugKotlin --no-daemon -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`
- `./script/runtime_authenticated_mock_smoke.swift`
- `script/runtime_authenticated_mock_smoke.swift --relay`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only`
- `swift test --filter RelayPeerClientTests`
- `swift test`
- `swift test --filter AetherLinkLocalizationTests`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pairingQrRawValueAcceptsCompactRelayPayloadsFromScanner -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailKeepsStructuredErrorDetails -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests.testCompactPairingQRCodePayloadMatchesSharedRelayFixture`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testRuntimeChatStoreSessionSummaryExposesCancelledAndErrorProcessingState|LocalRuntimeMessageRouterTests/testRuntimeChatStoreListsSessionsAndMessages|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotDropsRuntimeOwnedMessageBodiesButKeepsLocalDrafts --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummarySyncReplacesStaleRuntimeOwnedSessions -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotDropsRuntimeOwnedMessageBodiesButKeepsLocalDrafts --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeRedactedRuntimeSessionRehydratesAfterReconnectSessionSync -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.unpairedSettingsScreenStartsWithPairingHierarchy --tests com.localagentbridge.android.AppNavigationTest.pendingQrRouteSettingsScreenKeepsPairingHierarchy --tests com.localagentbridge.android.AppNavigationTest.trustedSettingsScreenKeepsGenericSettingsHeader -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.permanentNavigationRailUsesExpandedWidthOnly -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.emptyChatHidesStaticPromptWhenReadyToType --tests com.localagentbridge.android.AppNavigationTest.emptyChatUsesTopModelPickerWhenConnectedWithoutUsableModel -Pkotlin.incremental=false`
- `rg -n 'empty_chat_title|name="empty_chat"|Start a conversation|새 대화 시작|新しい会話を開始|开始新对话|Démarrer une conversation' apps/android/app/src/main apps/android/app/src/test || true`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `rg -n "runtime identity|empty_chat_title|name=\"empty_chat\"|Start a conversation|새 대화 시작|新しい会話を開始|开始新对话|Démarrer une conversation" apps/android/app/src/main/res apps/android/app/src/main/java apps/android/app/src/test script/check_android_string_parity.py`
- `rg -n "runtime identit|trusted identity|런타임 신원|신원 정보|신원 확인|ランタイム ID|信頼済み ID|識別情報|运行时身份|可信身份|身份未知|identit[ée]s? de runtime|identit[ée] approuv[ée]e|identit[ée] inconnue|empty_chat_title|name=\"empty_chat\"" apps/android/app/src/main/res/values* apps/android/app/src/main/java apps/android/app/src/test script/check_android_string_parity.py`
- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.manualPairingPayloadTrimsCopiedQrText --tests com.localagentbridge.android.AppNavigationTest.manualPairingPayloadRejectsUnsupportedUrlsOrActions --tests com.localagentbridge.android.AppNavigationTest.manualPairingPayloadRejectsBlankText -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailKeepsStructuredErrorDetails --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailRedactsBackendEndpointDetails -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt script/check_copy_hygiene.py`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactProviderEndpoints'`
- `swift build --target LocalAgentBridge`
- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- apps/macos/CompanionCore/Sources/CompanionAppModel.swift apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift apps/macos/LocalAgentBridgeApp/Sources/LogsView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ko.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ja.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/zh-Hans.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/fr.lproj/Localizable.strings script/check_macos_localization.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.runtimeVisibleErrorDetailRedactsBackendEndpointDetails -Pkotlin.incremental=false`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactProviderEndpoints|AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactRouteSecrets'`
- `python3 -m py_compile script/check_copy_hygiene.py script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectEmbeddingModelRejectsUninstalledRuntimeModelWithoutChangingSelection -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest -Pkotlin.incremental=false`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/AppNavigation.kt apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`
- `swift test --filter AetherLinkLocalizationTests`
- `swift build --target LocalAgentBridge`
- `python3 -m py_compile script/check_macos_localization.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift script/check_macos_localization.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest :app:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrScanPlansPendingRelayPairingWithoutManualEndpoint --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.identityOnlyQrPlanStartsDiscoveryAndWaitsForRoute --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest -Pkotlin.incremental=false`
- `./script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 43171 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-qr-check`
- Sanitized inspection of `/tmp/aetherlink-no-adb-qr-check/pairing-uri.txt` confirmed relay QR fields were emitted: `v`, `n`, `c`, `rid`, `rf`, `rk`, `rt`, `rh`, `rp`, `ri`, `rs`, `rx`, `rrn`, and `rsc`. Secret values were not copied into the repo docs.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsSuppressesOnlyRuntimeOwnedArchivedSessions --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotRedactsArchivedRuntimeOwnedBodiesButKeepsLocalArchivedBodies -Pkotlin.incremental=false`
- `swift test --filter AetherLinkLocalizationTests`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/AetherLinkLocalization.swift apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/AetherLinkLocalization.swift apps/macos/LocalAgentBridgeApp/Sources/LocalAgentBridgeApp.swift apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ko.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ja.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/zh-Hans.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/fr.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`
- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- Package.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsTroubleshootingSectionStaysDebugOnly -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsLanguageOptionsKeepCurrentLaunchLanguageSetAndOrder --tests com.localagentbridge.android.AppNavigationTest.settingsThemeOptionsKeepSystemLightDarkOrder -Pkotlin.incremental=false`
- `git diff --check -- script/check_copy_hygiene.py`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `swift build --target LocalAgentBridge`
- `swift build --target LocalAgentBridge`
- `rg -n '"(Provider Diagnostics|No diagnostics yet|No runtime logs|Connection Routes|configured route|Save Route|.*route QR.*|.*QR route.*|.*route settings.*|.*route port.*|.*Relay route.*|Current QR route protection)' apps/macos/LocalAgentBridgeApp/Sources/Resources apps/macos/LocalAgentBridgeApp/Sources || true`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift`
- `python3 script/check_docs_hygiene.py`
- `bash -n script/*.sh`
- `swift build --target RuntimeDevServer`
- `git diff --check`
- `swift test --filter AetherLinkLocalizationTests`
- `swift build --target LocalAgentBridge`
- `python3 -m py_compile script/check_macos_localization.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/TrustedDevicesView.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ko.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/ja.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/zh-Hans.lproj/Localizable.strings apps/macos/LocalAgentBridgeApp/Sources/Resources/fr.lproj/Localizable.strings script/check_macos_localization.py docs/progress.md docs/qa-evidence.md`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrPersistsRelayRouteBeforeReconnectRetry -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrPersistsRelayRouteBeforeReconnectRetry --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAddsRelayRouteToExistingTrustedRuntime -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.emptyChatPrefersQrRefreshWhenRuntimeRequiresPairingAgain --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrPersistsRelayRouteBeforeReconnectRetry -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt docs/progress.md docs/qa-evidence.md`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRemoteRoutePreparationIssueWhenBootstrapAllocationThrows`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRelayConnectionStatus`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsPrivateRemoteRouteAllocationWithoutDirectFallback`
- `swift test --filter AetherLinkLocalizationTests`
- `swift build --target LocalAgentBridge`
- `python3 -m py_compile script/check_macos_localization.py script/check_copy_hygiene.py`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check`
- `swift test --filter RelayAllocationTests`
- `swift test --filter LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorPassesBootstrapAllocationToken`
- `swift build --target RuntimeDevServer`
- `bash -n script/run_allocation_relay.sh script/run_different_network_dev_runtime.sh script/no_adb_external_relay_pairing_smoke.sh`
- `script/run_allocation_relay.sh --dry-run --allocation-token allocation-token-1`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 43171 --start-local-relay --emit-only --allocation-token allocation-token-1 --work-dir /tmp/aetherlink-token-relay-qr-check`
- No-device private overlay QR scope pass on 2026-06-25 KST. The Android phone was disconnected, so this is source/unit/script evidence only, not optical QR/device pairing evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests 'com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest' --tests 'com.localagentbridge.android.core.pairing.PairingStoreTest'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectAllowsPrivateOverlayRelayRoute' --tests 'com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRelayReconnectRejectsScopeLessPrivateRelayRoute'`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsPrivateOverlayRemoteRouteAllocationWithoutDirectFallback`
- `swift build --target RuntimeDevServer`
- `swift build --target LocalAgentBridge`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/run_allocation_relay.sh`
- `script/android_pairing_deeplink_smoke.sh --help`
- `script/no_adb_external_relay_pairing_smoke.sh --help`
- `swiftc -parse script/verify_pairing_qr.swift`
- Shared private overlay QR fixture pass on 2026-06-25 KST. The Android phone was disconnected, so this is source/unit/script evidence only, not optical QR/device pairing evidence.
- `python3 script/check_protocol_schema.py`
- No-device Android route-refresh cleanup pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical-device reconnect evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.disconnectCancelsScheduledRouteRefreshRetry --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.forgetTrustedRuntimeClosesConnectionAndClearsPendingRouteRefresh -Pkotlin.incremental=false`
- No-device Android runtime cleanup/provider redaction pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical-device UI evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderStatusesPreserveSafeBackendDetails --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderStatusesRedactBackendEndpointDetails --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.disconnectClearsPendingChatSessionRenameRequests --tests com.localagentbridge.android.AppNavigationTest.providerDiagnosticMessageRedactsBackendEndpointDetails -Pkotlin.incremental=false`
- No-device Android chat auto-scroll pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical scroll/touch evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollFollowsStreamingWhenAlreadyNearLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForStreamingDeltas --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollKeepsInitialAndNewMessageJumpBehavior --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForAssistantOnlyAppends --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDetectsUserSendBurstOnlyWhileStreaming --tests com.localagentbridge.android.AppNavigationTest.jumpToLatestChatButtonShowsOnlyWhenScrolledAwayFromLatestMessage -Pkotlin.incremental=false`
- No-device macOS Advanced Connection QR readiness copy pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/localization evidence only, not physical QR/device pairing evidence.
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_docs_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :core:pairing:testDebugUnitTest --tests 'com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest'`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/run_allocation_relay.sh`
- `git diff --check`
- macOS private overlay opt-in guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/script evidence only, not optical QR/device pairing evidence.
- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelBlocksPrivateRelayHostWithoutExplicitOverlayOptIn|LocalRuntimeMessageRouterTests/testCompanionAppModelRejectsPrivateOverlayRemoteRouteAllocationWithoutExplicitOptIn|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsPrivateOverlayRemoteRouteAllocationWithExplicitEnvironmentOptIn|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease|LocalRuntimeMessageRouterTests/testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode'`
- `swift build --target LocalAgentBridge`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `swift test --filter AetherLinkLocalizationTests`
- `bash -n script/android_pairing_deeplink_smoke.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/run_allocation_relay.sh`
- `git diff --check`
- Android private overlay route UI guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/script evidence only, not optical QR/device pairing evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- Runtime-mediated route refresh protocol slice on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/schema evidence only, not optical QR/device route-refresh evidence.
- `swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshReturnsRetryableErrorWhenRuntimeHasNoRefreshableRoute|LocalRuntimeMessageRouterTests/testRouteRefreshRequiresAuthenticatedConnectionByDefault'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`
- `python3 script/check_protocol_schema.py`
- Android route refresh integration pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/schema evidence only, not optical QR/device route-refresh evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRefreshesRelayRouteMaterial -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- Android proactive route refresh scheduling pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/schema evidence only, not optical QR/device route-refresh evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshLeaseDelayUsesRenewalWindow --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRefreshesRelayRouteMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshLeaseDelayUsesRenewalWindow --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- Android chat-history search polish pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not rendered Settings or physical archive/delete evidence.
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatHistorySearchMatchesTitleModelAndRuntimeMetadata -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`
- Android chat-history runtime status label pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not rendered Settings or physical chat-history evidence.
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatHistorySessionStatusSummarizesRuntimeProcessingMetadata -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt`
- Android Settings density collapse pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not ADB, screenshot, rendered Settings, or physical expansion/collapse evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsLowerPrioritySectionsStartCollapsed -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt docs/progress.md docs/qa-evidence.md`
- Runtime chat-title locale handoff pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/schema evidence only, not physical title rendering or live backend title-generation evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest --tests com.localagentbridge.android.core.protocol.ProtocolCodecTest.chatSendPayloadCanCarryRuntimeLocaleHint -Pkotlin.incremental=false`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- `swift test --filter LocalRuntimeMessageRouterTests`
- Android thinking preview polish pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/resource evidence only, not physical rendering, expansion tap, haptic, or screenshot evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.reasoningPreviewCapsLongSingleParagraphBeforeExpansion --tests com.localagentbridge.android.AppNavigationTest.reasoningDisplayPolicyKeepsCollapsedPreviewDimAndThreeLines --tests com.localagentbridge.android.AppNavigationTest.reasoningDisplayPolicyExpandsOnlyWhenExpandable -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- macOS pairing-first and runtime-copy polish pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS source/unit/localization evidence only, not physical QR pairing, Android rendering, or device reconnect evidence.
- `swift test --filter AetherLinkLocalizationTests/testCompanionFirstLaunchStartsWithPairingWhenNoTrustedDevicesExist`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`
- QR pairing route audit and runtime-copy cleanup pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/build evidence only, not optical QR scan, different-network relay reachability, physical reconnect, or rendered error-copy evidence.
- `swift test --filter 'LocalRuntimeMessageRouterTests/testRepeatedInvalidPairingAttemptsInvalidateActiveSession|LocalRuntimeMessageRouterTests/testExpiredAndNoActivePairingRequestsReturnStructuredRejections'`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testRuntimeHealthUnavailableReturnsProtocolErrorWithoutBackendURL|LocalRuntimeMessageRouterTests/testRuntimeHealthIncludesAggregateProviderStatuses|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesStructuredBackendProviderStatuses|LocalRuntimeMessageRouterTests/testRepeatedInvalidPairingAttemptsInvalidateActiveSession|LocalRuntimeMessageRouterTests/testExpiredAndNoActivePairingRequestsReturnStructuredRejections'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeProviderStatusesPreserveBackendDetails -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `swift build --target LocalAgentBridge`
- Android five-language default cleanup pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/localization evidence only, not physical Settings rendering, persisted preference behavior on-device, or screenshot evidence.
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.settingsLanguageOptionsKeepCurrentLaunchLanguageSetAndOrder --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.appLanguageTagHelperNormalizesSupportedAndInvalidTags --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank -Pkotlin.incremental=false`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_macos_localization.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeUiState.kt apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt script/check_android_string_parity.py docs/progress.md docs/qa-evidence.md`
- Language and connection-copy hardening pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/localization evidence only, not physical Settings rendering, language persistence on-device, QR pairing, or live different-network connectivity evidence.
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
- Android attachment-only prompt localization pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical attachment sending, camera QR pairing, device rendering, or live runtime chat evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt docs/progress.md docs/qa-evidence.md`
- Documentation contract guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is documentation/script evidence only, not physical QR pairing, attachment sending, device rendering, or different-network runtime connectivity evidence.
- `python3 -m py_compile script/check_docs_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_protocol_schema.py`
- `git diff --check -- script/check_docs_hygiene.py docs/architecture.md docs/roadmap.md`
- Android attachment send-path contract pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical attachment picking, device rendering, real runtime chat, or camera QR pairing evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlySendUsesSelectedLanguagePromptInChatSendPayload --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentSendAttachesMetadataOnlyToFinalUserPayloadMessage --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.imageAttachmentSendRequiresVisionModelAndKeepsPendingAttachmentsWhenBlocked --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.validAttachmentSendClearsPendingAttachmentsAndRetainsReadonlyMessageChips -Pkotlin.incremental=false`
- Android Settings persistence contract pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical app relaunch, Settings rendering, runtime reconnect, or on-device model-picker behavior evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelRestoresPersistedLanguageThemeAndModelSelectionsOnInit --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelPersistsLanguageThemeAndRestoresThemAfterRecreation --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelPublicSettingsSettersPersistAcrossRecreation -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt docs/progress.md docs/qa-evidence.md`
- Model picker install-flow and locale protocol contract pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/schema evidence only, not physical model-picker tapping, model installation through a live runtime, device rendering, or on-device locale behavior evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuEnablesIdleChatModelsSoUninstalledModelsCanRequestInstall -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_protocol_schema.py`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt packages/protocol-schema/protocol.schema.json script/check_protocol_schema.py docs/protocol.md docs/progress.md docs/qa-evidence.md`
- Android model install selection-state pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical model-picker tapping, live runtime model installation, device rendering, QR pairing, or different-network reconnect evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectUninstalledChatModelPersistsInstallTargetAndRequestsRuntimePull -Pkotlin.incremental=false`
- Android embedding model installed-state reconciliation pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical Settings rendering, live runtime model refresh, QR pairing, or different-network reconnect evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsEmbeddingSelectionWhenModelIsNotInstalled -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsMissingPersistedSelectionsTypedAcrossRefresh --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsPersistedSelectionsWhileModelListIsRestoring --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsSelectionsWhenRefreshedModelHasWrongKind --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsEmbeddingSelectionWhenModelIsNotInstalled --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationOnlyAutoSelectsChatWhenSelectionIsEmpty --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsExplicitEmbeddingSelection --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationSelectsInstalledChatTargetAfterRefresh -Pkotlin.incremental=false`
- Android sticky chat auto-scroll pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical scrolling behavior, rendered chat polish, QR pairing, or live streaming evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollFollowsStreamingWhenAlreadyNearLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForStreamingDeltas --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollKeepsInitialAndNewMessageJumpBehavior -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- Android jump-to-latest and macOS menu-bar QR routing pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/localization evidence only, not physical scrolling behavior, optical QR scanning, rendered macOS window focus, or live pairing evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.jumpToLatestChatButtonShowsOnlyWhenScrolledAwayFromLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollFollowsStreamingWhenAlreadyNearLatestMessage --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollDoesNotPullUserFromEarlierMessagesForStreamingDeltas --tests com.localagentbridge.android.AppNavigationTest.chatAutoScrollKeepsInitialAndNewMessageJumpBehavior -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- `swift test --filter AetherLinkLocalizationTests/testExternalPairingRequestOverridesCurrentCompanionSection`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- Android broader document picker coverage pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not platform picker rendering, actual file read permissions, runtime ingestion success, or live model response evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerUsesDocumentTypesWhenSelectedModelIsNotVisionCapable --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerIncludesImageTypesWhenSelectedModelIsVisionCapable -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- Structured text attachment coverage pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical file picker rendering, SAF MIME filtering on-device, real file read permissions, or live runtime/model answer quality evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerUsesDocumentTypesWhenSelectedModelIsNotVisionCapable --tests com.localagentbridge.android.AppNavigationTest.attachmentPickerIncludesImageTypesWhenSelectedModelIsVisionCapable -Pkotlin.incremental=false`
- `swift test --filter DocumentTextExtractorTests/testExtractsStructuredPlainTextDocumentFamily`
- `python3 script/check_android_string_parity.py`
- MIME-only structured text attachment ingestion pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/schema evidence only, not physical file-picker MIME behavior, SAF display-name behavior, live attachment upload, QR pairing, different-network reconnect, or model answer quality evidence.
- `swift test --filter DocumentTextExtractorTests/testExtractsStructuredPlainTextDocumentsFromMimeOnlyAttachments`
- `swift test --filter LocalRuntimeMessageRouterTests/testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment`
- `swift test --filter DocumentTextExtractorTests`
- `python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- Android route-refresh retry pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical app relaunch, camera QR pairing, real relay reachability, or different-network reconnect evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteRefreshRetryDelayStaysInsideActiveLease --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRouteRefreshErrorBeforeLeaseExpiry -Pkotlin.incremental=false`
- Android QR-only default Settings entry pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/build evidence only, not physical Settings rendering, real QR scan behavior, or on-device absence of the diagnostics section evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.developerDiagnosticsRequireDebugBuildAndExplicitLaunchRequest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:compileDebugKotlin -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_android_string_parity.py`
- macOS pairing-first runtime onboarding pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS source/unit/localization evidence only, not rendered window navigation, optical QR pairing, or physical reconnect evidence.
- `swift test --filter 'AetherLinkLocalizationTests/testCompanionFirstLaunchStartsWithPairingWhenNoTrustedDevicesExist|AetherLinkLocalizationTests/testTrustedDeviceCountChangeReturnsUnpairedRuntimeToPairing|AetherLinkLocalizationTests/testExternalPairingRequestOverridesCurrentCompanionSection'`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- macOS QR route readiness and diagnostic-redaction pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS source/unit/localization evidence only, not optical QR scanning, rendered button state, live relay reachability, or physical different-network pairing evidence.
- `swift test --filter 'AetherLinkLocalizationTests/testPairingQRGenerationRequiresAutomaticPreparationOrEligibleRoute|AetherLinkLocalizationTests/testRouteDiagnosticDisclosureRedactsSensitiveDetails|AetherLinkLocalizationTests/testRemoteRoutePreparationIssueCopyCoversRoutePreparationFailures'`
- `python3 script/check_macos_localization.py`
- `python3 script/check_copy_hygiene.py`
- No-device relay QR evidence split pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/script evidence only, not optical QR scanning, physical pairing, rendered Android copy, or real different-network reachability evidence.
- `./script/runtime_authenticated_mock_smoke.swift --relay`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port 43172 --start-local-relay --emit-only --work-dir /tmp/aetherlink-no-adb-emit-check-2 --timeout 30`
- `bash -n script/no_adb_external_relay_pairing_smoke.sh`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pendingQrRouteHeroExplainsThatLatestQrNeedsConnectionDetails -Pkotlin.incremental=false`
- `python3 script/check_android_string_parity.py`
- No-device quality gate pass on 2026-06-26 KST after adding Android Compose screen smoke and trusted relay app-init auto-reconnect. The Android phone was disconnected, so this is source/unit/build/script/JVM-render evidence only, not APK install, optical QR scan, physical file picking, haptic feel, launcher/Dock screenshot, live streamed chat/cancel, or real different-network runtime connectivity evidence.
- `./script/check_no_device_quality.sh`
- Android pending relay QR retry pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not optical QR scanning, camera permission flow, physical app lifecycle, or live different-network relay reachability. This pass proves a scanned relay QR route remains persisted after the first relay dial fails, the UI enters the retrying pairing state, direct TCP is not attempted, and the next scheduled retry sends `pairing.request` through the same relay route when the relay becomes ready.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady`
- Android relay-first Bonjour fallback pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not live handset mDNS discovery, physical network switching, carrier NAT behavior, or real remote relay reachability. This pass proves a trusted saved relay route is attempted before a matching Bonjour direct route and that the client falls back to direct only after the relay connector fails.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayReconnectAttemptsRelayBeforeMatchingBonjourFallback`
- Android Compose reasoning toggle and haptic smoke pass on 2026-06-26 KST. The Android phone was disconnected, so this is Robolectric/JVM Compose evidence only, not physical touch target feel, real haptic motor output, device font metrics, IME behavior, or rendered handset screenshots. This pass proves the chat screen renders assistant thinking as a dim collapsed three-line preview, expands it to the full text through the visible thinking toggle, and dispatches lightweight AetherLink haptic feedback for both chat send and reasoning toggle interactions.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRendersReasoningCollapsedAndExpandable`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest`
- Android no-device Compose screen smoke pass on 2026-06-26 KST. The Android phone was disconnected, so this is JVM/Robolectric Compose evidence only, not physical screenshot, camera QR scan, haptic feel, IME behavior, or real different-network runtime evidence. This pass renders `SettingsScreen` and `ChatScreen`, proves the pairing-first QR action callback, pending route recovery copy, composer text entry, enabled send action, `onSend` callback, and localized pairing-title rendering across English, Korean, Japanese, Simplified Chinese, and French.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest`
- Android trusted relay app-init auto-reconnect pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical app relaunch, camera QR pairing, real relay reachability, haptic feel, or different-network reconnect evidence. This pass proves a recreated ViewModel with saved model selections and trusted relay route starts the relay connection without a manual connect action, then requests route refresh, health, runtime chat history, runtime memory, and model list after authentication.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelAutoReconnectsTrustedRelayOnInitAndRefreshesRuntimeState`
- Android trusted-route re-entry state pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical app relaunch, camera QR pairing, real relay reachability, or different-network reconnect evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayRestoreMarksConnectingBeforeRelayDialCompletes`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest`
- Android floating chat composer polish pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not rendered device screenshot, touch ergonomics, IME overlap, or physical haptic evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatComposerKeepsAccessibilityLabelWithoutVisualPlaceholder -Pkotlin.incremental=false`
- `./script/check_no_device_quality.sh`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt docs/progress.md docs/qa-evidence.md`
- Android chat-history stale danger copy cleanup pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/script evidence only, not rendered Settings behavior, tap flow, dialog copy on-device, or haptic evidence.
- `python3 script/check_android_string_parity.py`
- `python3 script/check_copy_hygiene.py`
- `rg -n 'name="archive_all_chats_confirm"|name="delete_all_chats"|name="delete_all_chats_confirm"|name="delete_chat_confirm"|name="clear_chat_history"|name="clear_chat_history_confirm"' apps/android/app/src/main/res`
- `./script/check_no_device_quality.sh`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml script/check_android_string_parity.py docs/progress.md docs/qa-evidence.md`
- Android attachment composer guardrail pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical file picking, attachment chip rendering on-device, touch behavior, or live model answers with attached files.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatComposerAllowsAttachmentOnlySendWhenConnectedModelIsUsable --tests com.localagentbridge.android.AppNavigationTest.chatComposerBlocksImageAttachmentUntilSelectedModelSupportsVision --tests com.localagentbridge.android.AppNavigationTest.chatComposerRequiresInstalledChatModelForAttachmentSends --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.removePendingAttachmentDropsOnlySelectedAttachmentAndClearsError --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.blankMessageWithoutAttachmentsDoesNotSend -Pkotlin.incremental=false`
- Android attachment loading seam pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not platform SAF picker rendering, actual content URI permission behavior, physical file selection, or live model quality for attached files.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsStopsBeforeReadingReportedOversizeFile --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsKeepsAtMostFourPendingAttachments -Pkotlin.incremental=false`
- Android attachment over-limit feedback pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/resource evidence only, not physical file picker behavior or rendered on-device error display.
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsStopsBeforeReadingReportedOversizeFile --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsKeepsAtMostFourPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsWithExistingPendingAttachmentsReadsOnlyRemainingSlotsAndShowsLimit -Pkotlin.incremental=false`
- Cloud model-source copy hygiene pass on 2026-06-26 KST. This is source/script evidence only; the Android phone was disconnected, so app rendering was not physically validated.
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- No-device quality gate pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/build/script evidence only. It now covers trusted-route re-entry state, runtime-owned chat event storage, authenticated history readback, archive/permanent-delete guardrails, runtime-owned memory guardrails, runtime-mediated attachment/document/image guardrails, Android attachment loading, localized over-limit feedback, and composer send-policy guardrails, vision-model attachment gating, chat/embedding model separation and persisted selection guardrails, runtime-generated chat title and next-question guardrails, reasoning/think streaming separation, and inline `<think>` splitting, but it is still not APK install, optical QR scan, physical file picking, haptic feel, launcher/Dock screenshot, live streamed chat/cancel, or different-network runtime connectivity evidence.
- `./script/check_no_device_quality.sh`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- script/check_no_device_quality.sh README.md docs/progress.md docs/qa-evidence.md`
- No-device validation usability hardening pass on 2026-06-26 KST. The Android phone was disconnected, so this is script/build/unit evidence only, not rendered UI, physical QR, or on-device reconnect evidence. This pass adds Android/Swift protocol message constant drift detection to the schema check, pins the Gradle 9.4.1 wrapper checksum, expands app-level README docs hygiene, makes direct validation scripts executable, keeps Android protocol tests in the aggregate no-device gate, and makes Android string-parity logs report module, locale, and localized resource counts.
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
- `./script/check_no_device_quality.sh`
- Android model-picker local-source policy and QR artifact gate pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/script evidence only. It proves the closed chat model picker and drawer summary follow the runtime-host-local chat-model policy, and that the aggregate no-device gate now includes local emit-only QR PNG generation/decode plus relay-route payload validation. It is not evidence of physical model-menu touch behavior, optical QR scanning, completed app pairing, haptic feel, or real different-network reachability.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelPickerClosedLabelIgnoresProviderManagedChatModel --tests com.localagentbridge.android.AppNavigationTest.chatModelPickerClosedLabelUsesRuntimeModelNameWhenAvailable --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuShowsLocalChatModelsAndPrioritizesRunningThenInstalled -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --relay-port <free-port> --start-local-relay --emit-only --timeout 30 --work-dir <tmp>`
- `script/verify_pairing_qr.swift --image <tmp>/pairing-qr.png --expected <tmp>/pairing-uri.txt --require-relay-route --expected-relay-host 127.0.0.1 --expected-relay-port <free-port> --forbid-direct-endpoint --allow-local-relay`
- `./script/check_no_device_quality.sh`
- macOS no-device render smoke pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS AppKit/SwiftUI render evidence only. It proves the real companion shell renders at `860x560` across English, Korean, Japanese, Simplified Chinese, and French in system/light/dark appearances, and that Status, Pairing, Trusted Devices, and Activity detail surfaces also render non-empty bitmaps at minimum detail size across the same five-language system/light/dark matrix. It is not Android Compose render evidence, physical-device screenshot evidence, optical QR evidence, haptic evidence, or real different-network reachability evidence.
- `swift test --filter AetherLinkRenderSmokeTests`
- `python3 script/check_macos_localization.py`
- `bash -n script/check_no_device_quality.sh`
- Android empty chat model-selection state pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not rendered device layout or physical touch evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `./script/check_no_device_quality.sh`
- macOS route-refresh lease guardrail pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not optical QR scanning, physical reconnect, or real different-network relay reachability evidence.
- `swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial'`
- `./script/check_no_device_quality.sh`
- macOS connection-recovery redaction pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/localization evidence only, not rendered macOS window layout, optical QR scanning, or real relay reachability evidence.
- `swift test --filter AetherLinkLocalizationTests/testRemoteRoutePreparationIssueCopyUsesSelectedLocalizationAndRedactsSensitiveEndpoint`
- `python3 script/check_macos_localization.py`
- `swift test --filter AetherLinkLocalizationTests`
- `./script/check_no_device_quality.sh`
- Android model-picker selection pinning pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not rendered dropdown layout, physical touch behavior, haptic feel, or live model switching evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuKeepsSelectedModelVisibleDuringSearch --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuKeepsSelectedModelVisibleDuringSearch -Pkotlin.incremental=false`
- Android model-picker install-target recovery pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only, not physical model-picker tapping, live model pull, or rendered dropdown evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuEnablesLocalChatModelsSoUninstalledModelsCanRequestInstall --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuShowsLocalChatModelsAndPrioritizesRunningThenInstalled --tests com.localagentbridge.android.AppNavigationTest.chatModelMenuKeepsSelectedModelVisibleDuringSearch --tests com.localagentbridge.android.AppNavigationTest.embeddingModelMenuKeepsSelectedModelVisibleDuringSearch -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- README connection setup copy pass on 2026-06-26 KST. This is documentation/script evidence only, not rendered runtime-window or live different-network relay evidence.
- `python3 -m py_compile script/check_docs_hygiene.py script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- Validation script usability pass on 2026-06-26 KST. This is tooling/script evidence only, not rendered localized UI or on-device language-switching evidence.
- `./script/check_android_string_parity.py`
- `./script/check_docs_hygiene.py`
- `./script/check_license.py`
- `./script/check_app_icons.py`
- Android core protocol no-device gate pass on 2026-06-26 KST. This is unit evidence for protocol model/codec contracts, not physical client-runtime transport evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:protocol:testDebugUnitTest -Pkotlin.incremental=false`
- Validation script syntax pass on 2026-06-26 KST.
- `bash -n script/check_no_device_quality.sh`
- `python3 -m py_compile script/check_android_string_parity.py script/check_docs_hygiene.py`
- `./script/check_no_device_quality.sh`
- Android QR URI policy hardening pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/documentation evidence only, not optical QR scan or external camera deeplink evidence. It proves external pairing deeplink handling is limited to canonical `aetherlink://pair?...` host-form URIs and release-mode QR parsing rejects local diagnostic direct-route payloads instead of treating them as product pairing routes.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.pairingDeepLinkRejectsPathOnlyPairingUris --tests com.localagentbridge.android.AppNavigationTest.pairingDeepLinkAcceptsAetherLinkPairUris --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.releasePairingParserRejectsMacosLocalDiagnosticQrRoute -Pkotlin.incremental=false`
- Cross-OS UI copy audit pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/resource/script evidence only. Android and macOS visible UI copy was checked for platform-specific product wording and current resources are guarded by copy hygiene plus five-language parity checks; packaging permissions, camera/Local Network permission copy, developer scripts, and compatibility-only log parsing remain allowed.
- `python3 script/check_copy_hygiene.py`
- `python3 script/check_android_string_parity.py`
- `python3 script/check_macos_localization.py`
- Android Settings preference and embedding-model Compose smoke pass on 2026-06-26 KST. The Android phone was disconnected, so this is JVM/Robolectric Compose evidence only. It proves Settings renders the preference controls, dispatches Dark appearance and Korean language callbacks, expands the Memory indexing model section, and keeps embedding-model selection/clearing separate from chat-model selection. It is not evidence of physical tapping, real haptic output, optical QR scanning, physical reconnect, or different-network runtime connectivity.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest'`
- `./script/check_no_device_quality.sh`
- `git diff --check -- apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt`
- Android chat top-bar model picker Compose smoke pass on 2026-06-26 KST. The Android phone was disconnected, so this is JVM/Robolectric Compose evidence only. It proves the actual chat top-bar picker renders the selected chat model, exposes chat-model rows separately from the Memory indexing model section, and dispatches embedding-model selection separately from chat-model selection. It is not evidence of physical dropdown tapping, real haptic output, optical QR scanning, physical reconnect, or different-network runtime connectivity.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerSeparatesChatAndEmbeddingModels'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest'`
- `./script/check_no_device_quality.sh`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt`
- Android primary screen locale/theme matrix smoke pass on 2026-06-26 KST. The Android phone was disconnected, so this is JVM/Robolectric Compose layout evidence only. It proves primary Chat and Settings surfaces lay out across all five launch languages and both light/dark Material color schemes, with visible localized Chat/Settings anchors in every matrix cell. It is not screenshot/pixel evidence, physical-device layout evidence, real haptic output, optical QR scanning, physical reconnect, or different-network runtime connectivity.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.primaryScreensRenderAcrossLocaleThemeSurfaceMatrix'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest'`
- `./script/check_no_device_quality.sh`
- `git diff --check -- apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt`
- Android QR candidate error-routing and schema scope guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/schema evidence only. It proves AetherLink pair QR candidates no longer get silently ignored by the camera/manual-input prefilter when full payload validation will produce a structured error, path-only `aetherlink:/pair` URI forms are rejected by the core parser, and private/CGNAT/ULA relay hosts require explicit private-overlay scope in the pairing QR schema. It is not optical QR scan evidence, completed pairing evidence, physical reconnect evidence, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- `python3 script/check_protocol_schema.py`
- Android QR v1 contract alignment pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/documentation evidence only. It proves the Android pairing parser now requires `version=1` or `v=1`, while candidate routing still lets unversioned AetherLink pair QR text reach structured invalid-QR handling instead of being silently ignored. It is not optical QR scan evidence or completed pairing evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false`
- Android expired relay lease reconnect guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/documentation evidence only. It proves a trusted runtime with complete but expired relay lease material now surfaces `remote_route_expired` instead of silently losing the reconnect path, and the no-device gate now verifies `script/aetherlink_relay.py` remains guarded as legacy-only because it cannot allocate QR route leases. It is not optical QR scan evidence, completed pairing evidence, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.PairingStoreTest :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit -Pkotlin.incremental=false`
- `bash -n script/check_no_device_quality.sh && ./script/check_no_device_quality.sh`
- Android relay preparation host eligibility guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only. It proves malformed or stale relay route material is rechecked at the transport preparation layer before the relay connector is reached: normal remote routes reject loopback, localhost, unspecified, `.local`, link-local, multicast, and private-network-only relay hosts, while explicit `private_overlay` and debug `usb_reverse` scopes keep their intended diagnostic/overlay exceptions. It is not optical QR scan evidence, completed pairing evidence, physical reconnect evidence, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:transport:testDebugUnitTest --tests com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparationTest -Pkotlin.incremental=false`
- Android Settings diagnostic endpoint visibility smoke pass on 2026-06-26 KST. The Android phone was disconnected, so this is JVM/Robolectric Compose evidence only. It proves the rendered default Settings screen keeps QR pairing visible while hiding Troubleshooting, manual QR text, USB connection, emulator connection, connection address, and connection port; with developer diagnostics enabled, manual endpoint controls still stay behind the explicit Connection troubleshooting switch. It is not physical screenshot evidence, actual touch evidence, optical QR scan evidence, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenHidesDiagnosticEndpointControlsByDefault' --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch' -Pkotlin.incremental=false`
- Android chat history dangerous action Compose guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is JVM/Robolectric Compose evidence only. It proves rendered Settings keeps bulk chat history actions hidden until Chat history and then Manage all chats are opened, and proves both Archive all chats and Permanently delete archived chats require two dialog confirmations before their callbacks fire. It is not physical scrolling/tapping evidence, real haptic output evidence, physical screenshot evidence, or runtime-server synchronization evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed' -Pkotlin.incremental=false`
- macOS public relay QR scope contract pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit evidence only. It proves macOS public/DNS relay QR generation now emits explicit `relay_scope=remote` in full payloads and `rsc=remote` in compact camera payloads, matching the shared fixtures and Android parser expectations. It is not optical QR scan evidence, completed physical pairing evidence, or real different-network relay reachability evidence.
- `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelReplacesReadyStaleRelayBeforeGeneratingAllocatedRouteQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture'`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests 'com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest' -Pkotlin.incremental=false`
- Cross-network QR readiness copy pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/render-smoke evidence only. It proves Android pending-pairing copy in all five supported languages no longer suggests same-network discovery as the next step when protected route material is missing, and macOS Status overview now uses the tested route-readiness copy for stopped, connecting, reconnecting, failed, and ready connection-detail states. It is not optical QR scan evidence, completed physical pairing evidence, or real different-network relay reachability evidence.
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenRendersPendingPairingRouteState' -Pkotlin.incremental=false`
- `swift build --package-path apps/macos --product AetherLink`
- `swift test --package-path apps/macos --filter 'AetherLinkLocalizationTests|AetherLinkRenderSmokeTests'`
- Android diagnostic QR text fallback clarification pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/resource/Robolectric evidence only. It proves manual QR text is labeled as a diagnostic fallback in all five supported UI languages, the default Settings UI keeps QR pairing visible while hiding diagnostic endpoint controls, and the developer diagnostics row can be toggled before those controls appear. It is not physical camera QR evidence, actual device haptic evidence, or completed pairing evidence.
- `python3 script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenHidesDiagnosticEndpointControlsByDefault' --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch' -Pkotlin.incremental=false`
- macOS first-launch pairing priority pass on 2026-06-26 KST. A GPT-5.5 worker subagent implemented the narrow Status surface change and was closed after completion; GPT-5.3-Codex-Spark was not used. This proves first launch with no trusted devices prioritizes pairing over provider repair, and the Status QR quick action follows the same route-readiness rule as the Pairing view. It is not Android physical pairing or different-network connectivity evidence.
- `swift test --package-path apps/macos --filter AetherLinkLocalizationTests`
- Android drawer status, Settings reopen, and language alias guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/JVM/Robolectric Compose evidence only. It proves previous-chat drawer rows expose runtime-owned processing state, Settings reopens the primary pairing/connection section when pairing becomes required again, and persisted language aliases such as `zh-Hans` and `zh_rCN` still select Simplified Chinese. It is not physical drawer tapping, physical Settings behavior, optical QR scan, haptic, or different-network connectivity evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.AppNavigationTest.settingsLanguageSelectionNormalizesStoredAliases' --tests 'com.localagentbridge.android.AppNavigationTest.settingsLanguageOptionsKeepCurrentLaunchLanguageSetAndOrder' --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerItemsShowRuntimeProcessingStatus' --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPrimaryConnectionSectionReopensWhenPairingBecomesRequired' -Pkotlin.incremental=false`
- No-device quality gate pass after Android drawer status, Settings reopen, and language alias guard updates on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/build/script evidence only; it explicitly includes Android drawer runtime session status, Settings pairing section resync, and language alias selection normalization. It is still not physical install, optical QR scanning, physical reconnect, real haptic output, live streamed chat/cancel, or different-network runtime connectivity evidence.
- `./script/check_no_device_quality.sh`
- macOS natural count and plural copy pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS source/resource/unit/script evidence only. It proves Status, Trusted Devices, menu-bar status, and Activity log summaries no longer use parenthetical plural UI copy, and the macOS localization gate now rejects `(s)` in localized resources. It is not physical Android pairing, optical QR scan, haptic, live chat/cancel, or different-network connectivity evidence.
- `python3 script/check_macos_localization.py`
- `python3 -m py_compile script/check_macos_localization.py`
- `swift test --package-path apps/macos --filter AetherLinkLocalizationTests/testLocalizedCountHelpersUseNaturalSingularAndPluralCopy`
- `swift test --package-path apps/macos --filter AetherLinkLocalizationTests`
- No-device quality gate pass after macOS natural count/plural copy updates on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/build/script evidence only; it explicitly includes the macOS natural count/plural copy guard. It is still not physical install, optical QR scanning, physical reconnect, real haptic output, live streamed chat/cancel, or different-network runtime connectivity evidence.
- `./script/check_no_device_quality.sh`
- Android natural message-count plural resource pass on 2026-06-26 KST. The Android phone was disconnected, so this is Android source/resource/JVM/Robolectric evidence only. It proves `chat_message_count` is a localized plural resource across the five launch languages, the parity script now checks plural resources, and drawer plus Settings chat-history paths can render `1 message` instead of `1 messages` in English. It is not physical scrolling, real device font metric, haptic, optical QR scan, or different-network connectivity evidence.
- `python3 script/check_android_string_parity.py`
- `python3 -m py_compile script/check_android_string_parity.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerItemsShowRuntimeProcessingStatus' --tests 'com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed' -Pkotlin.incremental=false`
- No-device quality gate pass after Android natural message-count plural updates on 2026-06-26 KST. The Android phone was disconnected, so this is source/unit/build/script evidence only; it explicitly includes Android natural message-count plural resources. It is still not physical install, optical QR scanning, physical reconnect, real haptic output, live streamed chat/cancel, or different-network runtime connectivity evidence.
- `./script/check_no_device_quality.sh`
- Android localized model-status resource pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/resource/JVM evidence only. It proves model row provider/status formatting is backed by `model_status_value`, French status text formats as `Ollama - Installé`, and copy hygiene blocks hard-coded provider/status interpolation in the chat top-bar and Memory indexing model rows. It is not physical dropdown/touch, font metric, haptic, optical QR scan, or reconnect evidence.
- `python3 script/check_android_string_parity.py`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerStatusLineUsesLocalizedResources -Pkotlin.incremental=false`
- macOS visible localization anchor and `zh-Hans` bundle fallback pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS source/resource/unit evidence only. It proves selected Simplified Chinese no longer falls back to the system locale when SwiftPM emits `zh-hans.lproj`, and visible sidebar/settings anchor strings resolve in English, Korean, Japanese, Simplified Chinese, and French.
- `python3 script/check_macos_localization.py`
- `swift test --package-path apps/macos --filter AetherLinkLocalizationTests/testLocalizedVisibleAnchorsAcrossInitialLanguages`
- `swift test --package-path apps/macos --filter AetherLinkLocalizationTests`
- Provider-managed model visibility guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is source/JVM/macOS unit/script evidence only. It proves Android closed model labels and drawer summaries stop displaying provider-managed/cloud selections after the runtime model list has loaded, while macOS Status normal Models sections count and show installed local chat/embedding models only. It is not physical dropdown, drawer, haptic, optical QR, live chat, or different-network connectivity evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatModelPickerClosedLabelIgnoresProviderManagedChatModel -Pkotlin.incremental=false`
- `swift test --package-path apps/macos --filter AetherLinkLocalizationTests/testVisibleModelGroupsShowOnlyInstalledLocalModels`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- Android strict local model metadata guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is Android source/JVM/script evidence only. It proves `models.result` entries with missing `installed` or `source` metadata are not treated as selectable local chat models, stale provider-managed or unknown-source model IDs are rejected by ViewModel selection paths, and menu-level visibility also hides unknown-source chat models. It is not physical dropdown, touch, haptic, optical QR, live chat, or different-network connectivity evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- macOS runtime chat-store corruption guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS source/unit/script evidence only. It proves corrupt JSONL chat-history lines are surfaced as `RuntimeChatEventStoreError.corruptEventLog`, raw prompt/log text is not copied into the error message, and runtime protocol reads return structured `chat_store_unavailable` instead of silently hiding partial history. It is not physical Android history UI, optical QR, live chat, or different-network connectivity evidence.
- `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testRuntimeChatStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryCorruptStoreReturnsStructuredError'`
- `swift test --package-path apps/macos --filter LocalRuntimeMessageRouterTests`
- macOS runtime-local chat routing guard pass on 2026-06-26 KST. A GPT-5.5 worker subagent implemented the narrow macOS code/test patch and was closed; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is macOS source/unit/script evidence only. It proves installed cloud/provider-managed model metadata is rejected as `model_not_installed` and is not routed to the backend as a normal chat target. It is not physical QR scan, physical reconnect, live streamed chat/cancel, or different-network runtime connectivity evidence.
- `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testChatSendInstalledCloudModelReturnsModelNotInstalled|AggregatingLlmBackendResidencyTests/testInstalledCloudChatModelIsNotRoutedAsChat'`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `./script/check_no_device_quality.sh`
- Android invalid QR auto-reconnect guard pass on 2026-06-26 KST. The Android phone was disconnected, so this is Android JVM/source/script evidence only. It proves invalid or incomplete pair QR payloads no longer enable trusted-runtime auto-reconnect before the payload parses successfully, while valid compact relay QR pairing still enables reconnect and sends `pairing.request` over the relay path. It is not optical QR scan, completed pairing, physical reconnect, real haptics, live chat/cancel, or different-network runtime connectivity evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.invalidPairingQrDoesNotEnableTrustedRuntimeAutoReconnect --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `./script/check_no_device_quality.sh`
- Android suggested-question polish pass on 2026-06-26 KST. The Android phone was disconnected, so this is Android helper/Robolectric/source/script evidence only. It proves generated next-question chips drop blank suggestions, collapse whitespace/newlines, remove case-insensitive duplicates, cap the row at four suggestions, and send the normalized visible chip text when tapped. It is not physical touch, physical font metrics, haptics, optical QR, live chat/cancel, or different-network runtime connectivity evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.assistantSuggestionsNormalizeBlankDuplicatesAndMaximumRows --tests com.localagentbridge.android.AppNavigationTest.assistantSuggestionsHideWhenRowsNormalizeToBlank --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenNormalizesSuggestedQuestionChips -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `./script/check_no_device_quality.sh`
- macOS runtime suggested-question normalization pass on 2026-06-26 KST. The Android phone was disconnected, so this is macOS source/unit/script evidence only. It proves runtime-generated `chat.suggestions.result` rows drop blanks, collapse whitespace/newlines, remove case/diacritic/width-insensitive duplicates, and cap to four suggestions before any client renders them. It is not physical touch, physical font metrics, haptics, optical QR, live chat/cancel, or different-network runtime connectivity evidence.
- `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testChatSuggestionsRequestNormalizesBlankDuplicateAndExcessSuggestions|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsStructuredSuggestions|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestFallsBackToNumberedLocalizedList'`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `./script/check_no_device_quality.sh`
- macOS remote QR lease failure visibility pass on 2026-06-26 KST. A GPT-5.5 read-only subagent identified the QR-ready gap and was closed afterward; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is macOS source/unit/script evidence only. It proves a relay that is connected but lacks current route lease material does not silently clear the preparation issue or wait forever for relay readiness, and logs the concrete route allocation failure instead. It is not optical QR scan evidence, completed pairing evidence, physical reconnect evidence, or real different-network relay reachability evidence.
- `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelKeepsLeasePreparationIssueWhenRelayIsReadyWithoutLease|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesRemoteRouteAllocator|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRelayConnectionStatus'`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- Android relay QR completion persistence pass on 2026-06-26 KST. The Android phone was disconnected, so this is Android JVM/source/script evidence only. It proves compact relay QR pairing proceeds through `pairing.result`, stores trusted relay route material, clears the pending pairing route, marks onboarding complete, keeps reconnect enabled, and starts runtime refresh requests. It is not optical QR scan evidence, completed physical pairing evidence, physical reconnect evidence, live chat/cancel evidence, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute -Pkotlin.incremental=false`
- Android runtime-owned streaming storage boundary pass on 2026-06-26 KST. The Android phone was disconnected, so this is Android JVM/source/script evidence only. It proves live `chat.send` UI state can show the user prompt, assistant delta, and reasoning delta while the saved device snapshot keeps only runtime-owned session metadata/message count and redacts message bodies after send, delta, and done. It is not physical install, optical QR scan, physical reconnect, live runtime streaming, real haptics, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingRuntimeOwnedChatRendersInMemoryButRedactsDeviceStorage -Pkotlin.incremental=false`
- QR relay recovery and route-refresh identity binding pass on 2026-06-26 KST. Two GPT-5.5 subagents were used and closed; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is Android JVM/macOS unit/source/schema/script evidence only. It proves a fresh compact relay QR can replace an expired trusted relay lease and reconnect through relay without direct TCP, and proves `route.refresh` success payloads are bound to `runtime_device_id` plus `runtime_key_fingerprint` before Android saves refreshed relay material. It is not physical install, optical QR scan, physical reconnect, live runtime streaming/cancel, real haptics, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.freshCompactRelayQrRefreshesExpiredTrustedRelayRouteAndReconnectsViaRelay -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRefreshesRelayRouteMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsMismatchedRuntimeIdentity --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.freshCompactRelayQrRefreshesExpiredTrustedRelayRouteAndReconnectsViaRelay -Pkotlin.incremental=false`
- `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshRequiresAuthenticatedConnectionByDefault'`
- `python3 -m py_compile script/check_copy_hygiene.py script/check_protocol_schema.py && python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `./script/check_no_device_quality.sh`
- Default no-device relay E2E gate pass on 2026-06-26 KST. The Android phone was disconnected, so this is headless macOS/script evidence only. It proves the default gate now includes `./script/runtime_authenticated_mock_smoke.swift --relay`, covering relay allocation, QR route material parsing, encrypted relay frames, pairing, P-256 challenge-response authentication, `runtime.health`, `models.list`, `models.pull`, streaming `chat.send`, `chat.cancel`, and trusted relay reconnect. It is not physical install, optical QR scan, physical reconnect, real device haptics, live provider-backed chat/cancel, or real different-network relay reachability evidence.
- `./script/runtime_authenticated_mock_smoke.swift --relay`
- `python3 -m py_compile script/check_copy_hygiene.py script/check_protocol_schema.py && python3 script/check_copy_hygiene.py`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Route refresh retry and QR alias contract pass on 2026-06-26 KST. Two GPT-5.5 read-only subagents audited Android UI and QR/relay gaps; GPT-5.3-Codex-Spark was not used, and both subagents were closed. The Android phone was disconnected, so this is Android JVM/source/schema/script evidence only. It proves rejected authenticated `route.refresh` payloads preserve the existing trusted relay lease and schedule a bounded retry, and proves the shared QR schema plus Android parser now cover complete `remote_*`, `route_*`, and `rendezvous_*` relay alias families. It is not physical install, optical QR scan, camera permission, physical reconnect, real haptic, live provider-backed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRejectedRouteRefreshPayloadBeforeLeaseExpiry -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.parsesRendezvousRouteAliasesFromQrPayload --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest.rejectsIncompleteRelayAliasFamiliesFromQrPayload -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_protocol_schema.py && python3 script/check_protocol_schema.py`
- `python3 -m json.tool packages/protocol-schema/pairing-qr.schema.json >/dev/null`
- `python3 -m py_compile script/check_protocol_schema.py script/check_copy_hygiene.py && python3 script/check_protocol_schema.py`
- `python3 script/check_docs_hygiene.py`
- `python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/RuntimePairingPayload.kt apps/android/core/pairing/src/test/java/com/localagentbridge/android/core/pairing/RuntimePairingPayloadParserTest.kt packages/protocol-schema/pairing-qr.schema.json script/check_protocol_schema.py script/check_no_device_quality.sh docs/protocol.md docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- PairingStore persistence and suggested-question handoff coverage pass on 2026-06-26 KST. The Android phone was disconnected, so this is Android JVM/Robolectric/source/script evidence only. It proves complete relay routes survive the real PairingStore DataStore path, incomplete stored relay routes are stripped on read, `forgetRuntime()` removes relay trust, suggested-question taps fill the composer without sending or opening transport, and Compose chip taps hand the suggestion into chat input while leaving send explicit. It is not physical tapping, IME behavior, real haptic output, physical QR scanning, physical reconnect, live provider-backed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.PairingStoreTest -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.useSuggestedQuestionFillsComposerWithoutSending -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenSuggestionClickFillsComposerWithoutSending -Pkotlin.incremental=false`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `python3 -m py_compile script/check_protocol_schema.py script/check_copy_hygiene.py && python3 script/check_protocol_schema.py && python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/core/pairing/build.gradle.kts apps/android/core/pairing/src/test/java/com/localagentbridge/android/core/pairing/PairingStoreTest.kt apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt script/check_no_device_quality.sh docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android navigation drawer shell coverage pass on 2026-06-26 KST. One GPT-5.5 read-only subagent audited real relay connector integration-test feasibility; GPT-5.3-Codex-Spark was not used, and the subagent was closed. The Android phone was disconnected, so this is Android JVM/Robolectric/source evidence only. It proves the actual drawer content can be rendered without the full Activity stack, Settings stays below chat history as the drawer footer, and the footer still invokes settings selection. It also records that a real `RuntimeRelayTcpClient` ViewModel integration test is feasible but still needs a test-local relay-frame decrypt helper or intentional test visibility change. It is not physical drawer gesture, real device font metric, haptic, optical QR scan, physical reconnect, live provider-backed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerKeepsSettingsAsFooterBelowChatHistory -Pkotlin.incremental=false`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `python3 -m py_compile script/check_protocol_schema.py script/check_copy_hygiene.py && python3 script/check_protocol_schema.py && python3 script/check_copy_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android real relay client pairing regression pass on 2026-06-26 KST. A GPT-5.5 worker was spawned and then closed after it left an environment-dependent draft; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is Android JVM/source/script evidence only. It proves compact relay QR pairing uses the actual `RuntimeRelayTcpClient` socket transport, performs the `AETHERLINK_RELAY` handshake, decrypts/encrypts relay frames through the AES-GCM relay-frame contract, sends `pairing.request`, accepts encrypted `pairing.result`, persists the trusted relay route, clears pending pairing, keeps auto reconnect enabled, and marks the active route as relay. It is not optical QR scan, physical reconnect, real haptic output, live provider-backed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.compactRelayQrPairingUsesRealRelayTcpClientAndPersistsTrustedRelay -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_protocol_schema.py script/check_copy_hygiene.py && python3 script/check_protocol_schema.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelRelayIntegrationTest.kt script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android raw visible string localization guard pass on 2026-06-26 KST. A GPT-5.5 read-only explorer recommended this no-device improvement and was closed; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is source/script evidence only. It proves Android string parity now scans Kotlin UI sources for raw visible Compose/accessibility literals such as `Text("...")`, raw `contentDescription`, raw `placeholder`, raw `label`, raw `Toast.makeText`, and raw `showSnackbar` text, forcing new UI copy through localized resources across English, Korean, Japanese, Simplified Chinese, and French. It is not physical rendering, physical language switching, IME behavior, haptic feel, optical QR scan, or real different-network connectivity evidence.
- `python3 -m py_compile script/check_android_string_parity.py script/check_copy_hygiene.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh`
- `python3 script/check_docs_hygiene.py`
- `git diff --check -- script/check_android_string_parity.py script/check_copy_hygiene.py script/check_no_device_quality.sh docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android app top-bar shell chrome pass on 2026-06-26 KST. The prior GPT-5.5 read-only app-shell audit was closed; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is JVM/Robolectric/source/script evidence only. It proves the extracted `AetherLinkTopAppBar` renders the real shell navigation action, chat-model picker, new-chat action, and Memory indexing model selection without launching the full Activity stack, and keeps generic chat placeholders absent from the app chrome. It is not physical tapping, camera QR pairing, real haptic output, physical reconnect, live streamed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.appTopBarKeepsNavigationModelPickerAndNewChatChrome -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_android_string_parity.py script/check_copy_hygiene.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android QR-first chat empty state pass on 2026-06-26 KST. A GPT-5.5 read-only explorer audited the untrusted ChatScreen path and was closed; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is JVM/Robolectric/source/resource/script evidence only. It proves a fresh untrusted ChatScreen now renders QR-first copy, calls `onScanPairingQr` from the primary action, does not call `onConnect`, renders the QR-first title/action in English, Korean, Japanese, Simplified Chinese, and French, and keeps old connection-first/manual-route wording out of the empty chat surface. It is not optical QR scanning evidence, camera permission evidence, physical haptic output, physical reconnect evidence, live streamed chat/cancel evidence, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenUntrustedRuntimeShowsQrFirstPairingCallToAction -Pkotlin.incremental=false`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenUntrustedRuntimeUsesLocalizedQrFirstCopy -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_android_string_parity.py script/check_copy_hygiene.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android trusted composer readiness lock pass on 2026-06-26 KST. GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is Android JVM/Robolectric/source/script evidence only. It proves the chat input and attachment button are disabled until a trusted runtime is connected and a usable chat model is selected, while the QR-first Scan QR call to action remains available on a fresh untrusted ChatScreen. It also proves `chatComposerCanEdit` rejects untrusted, disconnected, streaming, and no-model states before `chatComposerCanSend` can become true. It is not physical keyboard behavior, real touch feel, IME behavior, actual haptic output, optical QR scanning, live streamed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenUntrustedRuntimeShowsQrFirstPairingCallToAction --tests com.localagentbridge.android.AppNavigationTest.chatComposerEditingRequiresTrustedConnectedUsableModel --tests com.localagentbridge.android.AppNavigationTest.chatComposerAllowsAttachmentOnlySendWhenConnectedModelIsUsable -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_android_string_parity.py script/check_copy_hygiene.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android composer readiness hint pass on 2026-06-26 KST. GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is Android JVM/Robolectric/source/script evidence only. It proves disabled non-streaming composer states show their readiness hint, active image/vision mismatches still show warning hints, normal ready states do not add extra status text, streaming suppresses extra readiness text, and previous-chat screens with no selected model render `Select a model before sending.` beside the disabled composer. It is not physical keyboard behavior, IME layout, real touch feel, actual haptic output, optical QR scanning, live streamed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsComposerReadinessHintWhenPreviousChatCannotSend --tests com.localagentbridge.android.AppNavigationTest.chatComposerStatusShowsReadinessHintsWhenInputIsLocked -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_android_string_parity.py script/check_copy_hygiene.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- macOS five-language detail render smoke pass on 2026-06-26 KST. A GPT-5.5 read-only explorer audited the macOS no-device UI test gap and was closed; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is macOS AppKit/SwiftUI/source/script evidence only. It proves Status, Pairing, Trusted Devices, and Activity detail surfaces render non-empty bitmaps at minimum detail size across English, Korean, Japanese, Simplified Chinese, and French in system/light/dark appearances, with failure labels that include surface, language, and appearance. It is not Android rendering, physical install, optical QR scanning, real haptic output, physical reconnect, live streamed chat/cancel, or real different-network relay reachability evidence.
- `swift test --filter AetherLinkRenderSmokeTests`
- `python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Tests/AetherLinkRenderSmokeTests.swift script/check_no_device_quality.sh script/check_copy_hygiene.py docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`
- Android native language picker label pass on 2026-06-26 KST. A GPT-5.5 read-only explorer audited the Android no-device UX/i18n surface and was closed; GPT-5.3-Codex-Spark was not used. The Android phone was disconnected, so this is Android resource/JVM/Robolectric/script evidence only. It proves the Settings language picker uses stable native option labels, `English`, `한국어`, `日本語`, `简体中文`, and `Français`, across English, Korean, Japanese, Simplified Chinese, and French launch contexts, and still dispatches `ko` when selecting `한국어`. It is not physical Settings rendering, physical touch, haptic feel, optical QR scanning, physical reconnect, live streamed chat/cancel, or real different-network relay reachability evidence.
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsLanguagePickerUsesNativeLabelsAcrossLaunchLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenPreferenceAndEmbeddingControlsInvokeCallbacks -Pkotlin.incremental=false`
- `python3 -m py_compile script/check_android_string_parity.py script/check_copy_hygiene.py && python3 script/check_android_string_parity.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/android/app/src/main/res/values/strings.xml apps/android/app/src/main/res/values-en/strings.xml apps/android/app/src/main/res/values-ko/strings.xml apps/android/app/src/main/res/values-ja/strings.xml apps/android/app/src/main/res/values-zh-rCN/strings.xml apps/android/app/src/main/res/values-fr/strings.xml apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt script/check_android_string_parity.py script/check_copy_hygiene.py script/check_no_device_quality.sh docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`

- Physical Android relay pairing smoke pass on 2026-06-26 KST. The latest debug APK built, installed, and launched on physical device `SM_S936N` without a captured fatal crash. `script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect` passed against the device; runtime logs show `pairing.request`, `pairing.result`, first `runtime.health`, app force-stop/relaunch, authenticated reconnect, and second `runtime.health`. Evidence artifacts were preserved at `build/qa/aetherlink-pairing-smoke-20260626-1443.png`, `build/qa/aetherlink-runtime-smoke-20260626-1443.log`, and `build/qa/aetherlink-relay-smoke-20260626-1443.log`. This is not optical camera QR scanning, real public different-network relay reachability, live provider-backed chat/cancel, or real haptic-feel evidence.
- macOS native language picker label pass on 2026-06-26 KST. The macOS picker now uses self-identifying native labels, `English`, `한국어`, `日本語`, `简体中文`, and `Français`, across all selected app languages. `AetherLinkLocalizationTests`, `script/check_macos_localization.py`, copy hygiene, and the no-device coverage summary guard the contract. This is source/unit/script evidence, not a physical macOS UI screenshot pass.

Verified after these changes:

- `~/Library/Android/sdk/platform-tools/adb devices -l`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew --no-daemon :app:assembleDebug -Pkotlin.incremental=false`
- `~/Library/Android/sdk/platform-tools/adb install -r apps/android/app/build/outputs/apk/debug/app-debug.apk`
- `adb logcat -c && adb shell am start -n com.localagentbridge.android/.MainActivity && sleep 3 && adb logcat -d -t 300 | rg -i 'FATAL EXCEPTION|AndroidRuntime|com.localagentbridge|AetherLink|Exception|ANR'`
- `script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect`
- `swift test --filter AetherLinkLocalizationTests`
- `python3 -m py_compile script/check_macos_localization.py script/check_copy_hygiene.py && python3 script/check_macos_localization.py && python3 script/check_copy_hygiene.py`
- `bash -n script/check_no_device_quality.sh && python3 script/check_docs_hygiene.py`
- `git diff --check -- apps/macos/LocalAgentBridgeApp/Sources/AetherLinkLocalization.swift apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift script/check_macos_localization.py script/check_copy_hygiene.py script/check_no_device_quality.sh docs/progress.md docs/qa-evidence.md`
- `./script/check_no_device_quality.sh`

- Physical Android chat/cancel smoke pass on 2026-06-26 KST. The physical device `SM_S936N` ran `script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel`. The script injected the QR URI, paired through the relay route, then used Android UI automation against accessibility nodes to tap `Message`, type `AetherLink_physical_cancel_smoke`, tap `Send message`, wait for streaming `chat.delta`, tap `Cancel generation`, and verify `chat.cancel` plus `chat.done`. Runtime log evidence shows `pairing.request`, `pairing.result`, first `runtime.health`, `models.list`, `chat.send`, one `chat.delta`, `chat.cancel`, `chat.done`, app force-stop/relaunch, second `runtime.health`, and a follow-up `models.list`. Evidence artifacts were preserved at `build/qa/aetherlink-chat-cancel-smoke-20260626-1505.png`, `build/qa/aetherlink-pairing-chat-smoke-20260626-1505.png`, `build/qa/aetherlink-runtime-chat-smoke-20260626-1505.log`, and `build/qa/aetherlink-relay-chat-smoke-20260626-1505.log`. This is physical-device post-QR/deeplink UI evidence, not optical camera QR scanning, real public different-network relay reachability, live Ollama/LM Studio-backed chat quality, physical haptic-feel evidence, or physical file-picker evidence.
- Physical Android live backend chat/cancel smoke pass on 2026-06-26 KST. The physical device `SM_S936N` ran `script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel --live-backend --chat-delta-timeout 180 --chat-text "Answer in one short sentence."`. Runtime log evidence begins with `Backend: Ollama + LM Studio` and then shows `pairing.request`, `pairing.result`, first `runtime.health`, `models.list`, `chat.send`, many streamed `chat.delta` events, `chat.cancel`, `chat.done`, app force-stop/relaunch, second `runtime.health`, and a follow-up `models.list`. The physical screenshot shows selected live model `qwen3.6:35b-mlx` and the compact dim Thinking preview during a live model response. Evidence artifacts were preserved at `build/qa/aetherlink-live-chat-cancel-smoke-20260626-1512.png`, `build/qa/aetherlink-live-pairing-chat-smoke-20260626-1512.png`, `build/qa/aetherlink-live-runtime-chat-smoke-20260626-1512.log`, and `build/qa/aetherlink-live-relay-chat-smoke-20260626-1512.log`. This is physical-device post-QR/deeplink UI evidence for runtime-mediated real-provider streaming and cancel, not optical camera QR scanning, real public different-network relay reachability, physical haptic-feel evidence, physical file-picker evidence, or model-quality evaluation.
- Android-device relay reachability probe added on 2026-06-26 KST. `script/android_relay_reachability_probe.sh` checks whether the connected physical device can open TCP to a relay endpoint without adb reverse and writes JSON evidence with endpoint class, probe result, and optional connectivity summary. `script/android_pairing_deeplink_smoke.sh --external-relay-host ... --probe-external-relay-from-device` now runs that probe before injecting the pairing URI. The current physical run used `SM_S936N` on `MOBILE[LTE]` against a temporary runtime-host relay advertised as `192.168.0.102:<ephemeral>`; the probe exited 1 with `nc: Timeout`, and the integrated smoke exited 21 before QR injection. This improves diagnosis for different-network QR failures by separating unreachable relay routes from QR parsing, pairing, authentication, and model-provider behavior. It is not pairing evidence, optical QR evidence, chat evidence, or proof that a relay endpoint is production-safe.

Verified after this change:

- `bash -n script/android_pairing_deeplink_smoke.sh && python3 -m py_compile script/check_copy_hygiene.py && python3 script/check_copy_hygiene.py`
- `swift build --product RuntimeDevServer`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel`
- `rg -n "pairing.request|pairing.result|runtime.health|models.list|chat.send|chat.delta|chat.cancel|chat.done" build/qa/aetherlink-runtime-chat-smoke-20260626-1505.log`
- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel --live-backend --chat-delta-timeout 180 --chat-text "Answer in one short sentence."`
- `rg -n "Backend:|pairing.request|pairing.result|runtime.health|models.list|chat.send|chat.delta|chat.cancel|chat.done" build/qa/aetherlink-live-runtime-chat-smoke-20260626-1512.log`

## Remaining Physical Device Evidence Needed

The latest APK install, app launch, QR payload/deeplink pairing, and trusted relay reconnect have current physical-device evidence. Remaining physical evidence before claiming the full device experience:

- scan a live QR optically with the camera,
- verify different-network relay or future overlay routing with a reachable route,
- verify real haptic feel and physical file picking, and
- reference the fresh artifact paths in `docs/progress.md`.

## Known Stale Capture Risk

Some existing historical XML dumps and screenshots may still show older copy such as direct provider names, fixed-route diagnostics, or development runtime names. Those files should not be read as current UI state unless they are regenerated after the latest source changes.

## 2026-06-26 Android App Theme Path

- Scope: no-device Robolectric/Compose verification of the actual `AetherLinkTheme` function used by the app shell.
- Result: explicit Light uses the AetherLink light palette, explicit Dark uses the AetherLink dark palette, and System follows Robolectric `notnight`/`night` qualifiers.
- Adjacent stabilization: the real relay-client integration test now keeps its fake relay socket open until the active relay route assertion has a stable state to observe, avoiding a larger-suite-only disconnect race.
- Caveat: the Android phone was disconnected, so this does not prove a physical device screenshot, real device dark-mode toggle, launcher icon appearance, optical QR scanning, physical haptics, live provider chat/cancel, or real different-network runtime connectivity.

## 2026-06-26 Reasoning Accessibility And Connection Copy Polish

- Scope: no-device Android Compose accessibility semantics plus macOS Connection Recovery localization copy.
- Result: Android assistant thinking/reasoning now exposes localized `Collapsed` and `Expanded` state descriptions while preserving the dim three-line preview and explicit expanded view. The focused Compose test verifies collapsed state, tap-to-expand, expanded state, and fake haptic callback dispatch.
- Result: macOS Connection Recovery invalid-address detail no longer tells users to use a host name or IP address. It reuses the localized connection-address-only guidance, and the stale fixed-IP localization key was removed from all five current languages.
- Latest focused evidence: Android reasoning Compose regression, macOS localization parity, copy hygiene, macOS localization tests, and a fixed-IP phrase search all passed after the change.
- Latest gate: `./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack output, physical haptic feel, optical QR scanning, real-device reconnect, or real different-network runtime connectivity.

## 2026-06-26 Chat Model Picker Separation

- Scope: no-device Android Compose and helper coverage for separating active chat-model selection from Settings/Memory embedding-model selection.
- Result: the Chat top-bar dropdown now renders only chat model refresh/search/selection. Memory indexing model selection remains in Settings and is no longer mixed into the active chat model menu.
- Result: copy hygiene now fails if the Chat top bar reintroduces embedding-model menu ownership, while still requiring the Settings embedding-model selector callback and selected-state accessibility semantics.
- Latest focused evidence: the Chat top-bar no-device Compose test proves Memory indexing rows are hidden from the chat picker, the selected chat row remains accessible, AppNavigation helper tests confirm search availability is chat-model-only, and Android string parity plus copy hygiene passed.
- Latest gate: `./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical touch behavior, real haptic feel, or physical model switching.

## 2026-06-26 macOS Connection Recovery Render Coverage

- Scope: no-device AppKit/SwiftUI bitmap smoke coverage for `RemoteRelayRoutePanel`.
- Result: Connection Recovery / Advanced Connection Setup now participates in the five-language System/Light/Dark render matrix alongside Status, Pairing, Trusted Devices, and Activity.
- Caveat: this is visual render evidence only. It does not prove physical QR scanning, physical Android pairing, reachable public relay behavior, or real different-network runtime connectivity.

## 2026-06-26 Expired Relay Metadata Persistence

- Scope: no-device Android PairingStore/DataStore persistence coverage for QR-provisioned relay route metadata.
- Result: expired but complete relay lease metadata now survives `PairingStore.trustRuntime(...)` and `trustedRuntime` restore. The restored runtime still rejects the route as connectable, reports it as expired, and keeps stale direct endpoint fallback suppressed so the UI can show the latest-QR recovery path instead of a generic no-route state.
- Latest focused evidence: PairingStore Robolectric coverage and the ViewModel expired-route initialization regression both passed.
- Latest gate: `./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical QR scanning, real-device reconnect, reachable public relay behavior, or real different-network runtime connectivity.

## 2026-06-26 Android Jump to Latest Compose Interaction

- Scope: no-device Robolectric/Compose interaction coverage for the Chat screen's `Jump to latest message` control.
- Result: the test scrolls the chat list away from the newest message, verifies the jump control appears, taps it, verifies the latest message is visible again, and checks the fake haptic callback dispatch.
- Guardrail: copy hygiene now requires the stable chat list test tag and the focused Compose regression, and the no-device quality gate summary explicitly names Android jump-to-latest Compose interaction coverage.
- Latest gate: `./script/check_no_device_quality.sh` passed after adding this coverage.
- Caveat: the Android phone was disconnected, so this does not prove physical touch behavior, real device haptic feel, optical QR scanning, physical reconnect, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-26 Settings Section Accessibility and Multiline Localization Guards

- Scope: no-device Android Settings accessibility semantics plus Android/macOS localization guard hardening.
- Result: Settings expandable sections expose localized `Expanded` or `Collapsed` state descriptions, and the focused Compose test proves the state changes after tapping a section.
- Result: Android raw Compose visible-string and macOS raw SwiftUI visible-string guards now scan multiline source text instead of only one source line at a time.
- Result: the Android/macOS raw visible-string guards now include inline self-tests for multiline unsafe samples and localized safe samples, so the regex behavior itself is checked before scanning app sources.
- Result: the real relay-client Android integration test cleanup now waits briefly for IO relay coroutine cancellation before resetting `Dispatchers.Main`, preventing aggregate-test contamination.
- Guardrail: copy hygiene requires the Settings section state semantics, the focused Compose regression, and multiline raw visible-string scanners for Android and macOS. The no-device quality gate summary names Settings expandable section accessibility state and macOS raw SwiftUI visible-string localization coverage.
- Latest gate: `./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this is source/Robolectric/script evidence only. It does not prove physical TalkBack output, physical touch behavior, real haptic feel, optical QR scanning, physical reconnect, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-26 Runtime-Owned Memory Injection

- Scope: no-device SwiftPM and Android JVM/Robolectric evidence for runtime-host-owned memory context at the Mac chat boundary.
- Result: `LocalRuntimeMessageRouter` now injects enabled memory from the runtime store into `chat.send` backend requests, skips disabled entries, removes stale client-supplied `Runtime user memory:` context, and returns `memory_store_unavailable` if the runtime cannot load memory before calling the backend.
- Result: Android's existing enabled-memory-only payload tests still pass, but the protocol boundary is now stricter: the client payload is compatibility input and the runtime host is authoritative.
- Documentation evidence: `docs/protocol.md`, `docs/security.md`, and `docs/architecture.md` now describe runtime-side memory replacement and the continued rule that clients never call Ollama, LM Studio, or future serving backends directly.
- Latest focused evidence: new Swift memory-injection regressions, existing Swift capability-guard regressions, Android memory payload regressions, docs hygiene, copy hygiene, script syntax, and diff whitespace checks passed.
- Latest gate: `./script/check_no_device_quality.sh` passed after adding the new Swift regressions to the aggregate gate.
- Caveat: the Android phone was disconnected, so this does not prove physical QR scan, physical reconnect, physical haptic feel, live provider streaming/cancel, or real different-network runtime connectivity.

## 2026-06-26 Runtime-Only Context History Filtering

- Scope: no-device SwiftPM evidence for separating backend-only system prompt context from runtime-owned user-visible history.
- Result: `LocalRuntimeMessageRouter` now stores only client-visible request messages in runtime chat events while still sending the capability guard and runtime-owned memory context to the backend request.
- Result: `JSONLRuntimeChatEventStore` now filters old or accidental `Runtime user memory:` system messages from reconstructed transcripts, so `chat.messages.list` does not expose runtime memory prompt context as a chat turn.
- Result: the new focused regression proves a backend request contains runtime context, while the recorded `.request` event contains only the original user-visible message.
- Documentation evidence: protocol, architecture, and security docs now state that runtime-only context is model-call input and not user-visible chat history.
- Latest focused evidence: focused Swift runtime-history tests, docs hygiene, copy hygiene, script syntax, and diff whitespace checks passed.
- Latest gate: `./script/check_no_device_quality.sh` passed after adding the runtime-only context history-filtering regression.
- Caveat: the Android phone was disconnected, so this does not prove physical QR scan, physical reconnect, physical haptic feel, live provider streaming/cancel, or real different-network runtime connectivity.

## 2026-06-26 Platform-Neutral App Copy Guard

- Scope: no-device source/script evidence that product UI copy stays target-neutral as more client and runtime OSes are added later.
- Result: `script/check_copy_hygiene.py` now self-tests the `platform-specific-os-copy` rule, proving app-facing copy rejects concrete OS names such as Android, Mac, macOS, iOS, iPhone, and Windows while allowing neutral device/runtime wording.
- Result: the aggregate no-device gate summary now names platform-neutral app copy guard coverage, and `check_copy_hygiene.py` fails if that coverage label is removed.
- Latest focused evidence: `python3 script/check_copy_hygiene.py` passed after the self-test and no-device summary guard update.
- Caveat: this does not prove physical screenshots, launcher/Dock labels, app-store metadata, or installed-app UI on a connected device.

## 2026-06-27 macOS Trusted Device Row Accessibility Summary Separation

- Scope: no-device macOS XCTest/source/script evidence for the Trusted Devices list accessibility label.
- Result: `TrustedDeviceRow` still displays the compact visual row summary, but its VoiceOver label now uses `trustedDevicePairingAccessibilitySummary(...)` instead of reusing the visual `Paired ... · ID ending ...` string.
- Result: the focused localization regression covers English, Korean, Japanese, Simplified Chinese, and French, rejects the visual `·` separator in accessibility output, and verifies non-English labels no longer retain the English `Paired` / `ID ending` fragment.
- Guardrail: macOS localization and copy hygiene scripts now require the accessibility-only pairing summary helper, `Paired %@. Device ID ending %@`, and the aggregate no-device summary phrase `macOS trusted-device row accessibility visual-summary separation`.
- Latest focused evidence: `swift test --filter AetherLinkLocalizationTests/testTrustedDeviceRowAccessibilityLabelUsesDeviceContext` passed.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the trusted-device accessibility separation update.
- Caveat: this does not prove a live VoiceOver session, physical pairing scan, physical device reconnect, live provider streaming/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Nearby-Only Connection Guidance Copy

- Scope: no-device macOS XCTest/source/script evidence for Status `Device Connections` copy when no cross-network connection details are saved.
- Result: nearby-only status guidance now says nearby pairing still works and another network requires a reachable relay, VPN, or tunnel before generating the latest QR. It no longer uses vague "prepared later" wording.
- Result: the focused localization regression covers English, Korean, Japanese, Simplified Chinese, and French for the new guidance and rejects the old English `prepared later` fragment.
- Guardrail: macOS localization and copy hygiene scripts now require the new source string and the aggregate no-device summary phrase `macOS nearby-only connection guidance copy`.
- Latest focused evidence: `swift test --filter AetherLinkLocalizationTests/testStatusNearbyOnlyConnectionGuidanceUsesActionableCopyAcrossLanguages` passed.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the nearby-only connection guidance copy update.
- Caveat: this does not prove physical QR scanning, physical device reconnect, live provider streaming/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Composer IME and Reasoning Action Labels

- Scope: no-device Android Robolectric/Compose and source/script evidence for chat composer keyboard send behavior and reasoning toggle accessibility.
- Result: the composer now exposes `ImeAction.Send`; pressing the soft keyboard Send action triggers the same guarded send path and lightweight haptic policy as the visible send button.
- Result: the reasoning block still renders dimmed, collapsed to about three lines, and expandable; regression coverage now also asserts the localized `Show thinking` and `Hide thinking` click-action labels.
- Guardrail: copy hygiene now requires `KeyboardActions`, `ImeAction.Send`, `performImeAction()`, and reasoning toggle action-label assertions. The aggregate no-device summary names Android composer keyboard Send action and Android reasoning toggle action labels.
- Latest focused evidence: `ClientScreensNoDeviceComposeTest.chatScreenAcceptsInputAndSendWhenConnectedModelIsReady`, `chatScreenRendersReasoningCollapsedAndExpandable`, and `chatScreenReasoningSummaryLocalizesAcrossSupportedLanguages` passed.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the Android composer and reasoning action-label update.
- Caveat: the Android phone was disconnected, so this does not prove physical keyboard/IME behavior, real TalkBack output, physical haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Connection Recovery Fallback Action Hints

- Scope: no-device macOS XCTest/source/script evidence for fallback Connection Recovery action accessibility.
- Result: `Save Bootstrap Relay`, `Save Connection`, and `Rotate Secret` now expose localized help and VoiceOver hints that describe how they affect future pairing QR connection details.
- Result: the focused localization regression covers English, Korean, Japanese, Simplified Chinese, and French for all three fallback action hints.
- Guardrail: macOS localization and copy hygiene scripts now require the helper functions, the button hint wiring, the source strings, and the aggregate no-device summary phrase `macOS Connection Recovery fallback-action accessibility hints`.
- Latest focused evidence: `swift test --filter 'AetherLinkLocalizationTests/testConnectionRecoveryFallbackActionAccessibilityHintsUseSelectedLanguage|AetherLinkLocalizationTests/testConnectionRecoveryGenerateLatestQRActionAccessibilityUsesSelectedLanguage|AetherLinkLocalizationTests/testConnectionRecoveryFormFieldAccessibilityValuesUseSelectedLanguageAndHideSecrets'` passed.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the macOS Connection Recovery fallback action hint update.
- Caveat: this does not prove a live VoiceOver session, physical QR scanning, physical device reconnect, live provider streaming/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Action Labels and macOS CJK Accessibility Spacing

- Scope: no-device Android Compose/Robolectric, macOS XCTest, and source/script evidence for action-label and localization polish.
- Result: Android top-bar, drawer, and permanent-rail `New Chat` controls now expose localized click-action labels while retaining their existing readiness and disabled-state descriptions.
- Result: Android chat model picker rows now expose `Choose model` for installed/running rows and `Install model` for uninstalled local rows, so assistive activation text matches the actual action.
- Result: macOS Japanese and Simplified Chinese page-header and empty-state accessibility labels no longer insert a Western-style space after `。`.
- Guardrail: copy hygiene now requires the New Chat action-label wiring, model row select/install click labels, CJK page-header expectations, and CJK empty-state expectations. The aggregate no-device summary names Android New Chat action labels, Android model row action labels, and macOS CJK page-header accessibility spacing.
- Latest focused evidence: Android `appTopBarKeepsNavigationModelPickerAndNewChatChrome`, `permanentNavigationRailUsesNewChatPairingGateAndHaptics`, and `chatTopBarModelPickerRowsExposeAccessibilitySummaries` passed. macOS `testCompanionPageHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks` and `testCompanionEmptyStateAccessibilityLabelUsesSelectedLanguageAndFallbacks` passed.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after the action-label and CJK accessibility spacing update.
- Caveat: the Android phone was disconnected, so this does not prove physical install, real TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Search and Memory Accessibility, macOS Trusted Device Refresh Hint

- Scope: no-device Android Compose/Robolectric, macOS XCTest, and source/script evidence for focused accessibility polish.
- Result: Android search clear controls now expose localized click-action labels for drawer chat search, Settings chat history search, and chat top-bar model search, while keeping their existing haptic behavior and visual layout.
- Result: Android Memory's input field now exposes the localized `Add memory` accessibility label and the same locked, empty, or ready state description as the Add Memory button.
- Result: macOS Trusted Devices `Refresh Devices` now has localized help, accessibility value, and accessibility hint text explaining that it refreshes trusted devices from AetherLink Runtime.
- Guardrail: copy hygiene now requires Android search clear action labels, Android memory input readiness semantics, macOS Trusted Devices refresh hint helpers, and the updated no-device summary phrases. macOS localization parity requires the new refresh hint key across the five supported languages.
- Latest focused evidence: Android `navigationDrawerChatSearchFiltersClearsAndUsesHapticFeedback`, `settingsChatHistorySearchClearsWithContextAndHapticFeedback`, `settingsChatHistorySearchLocalizesClearAndNoResultsAcrossSupportedLanguages`, `chatTopBarModelPickerSearchClearsWithContextAndHapticFeedback`, `chatTopBarModelPickerSearchLocalizesClearAndNoResultsAcrossSupportedLanguages`, and `settingsMemoryAddControlsLocalizeReadinessStateAcrossSupportedLanguages` passed. macOS `testTrustedDeviceRefreshActionAccessibilityUsesSelectedLanguage` passed.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical install, real TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-26 Off-Network QR Pairing Diagnostics

- Scope: no-device Android ViewModel coverage plus local relay QR artifact generation for the off-network pairing path.
- Result: identity-only pairing QR now times out instead of waiting indefinitely for local discovery. The client surfaces `pairing_endpoint_unavailable` with `route_diagnostic_remote_pending`, making it clear that a fresh QR with reachable connection details is required.
- Result: local relay emit-only smoke generated a pairing URI and QR PNG at `/tmp/aetherlink-no-adb-relay-smoke`, verified QR decode round-trip, and confirmed the runtime registered with the relay and waited for a peer.
- Observed local smoke caveats: artifact-only emit mode, local relay only unless advertised through a public/VPN/tunnel/overlay route, and no trusted device joined because the phone was disconnected.
- Latest focused evidence: `RuntimeClientViewModelTest.identityOnlyPairingQrTimesOutWhenNoDiscoveryRouteAppears` passed, and `script/no_adb_external_relay_pairing_smoke.sh --relay-host 127.0.0.1 --start-local-relay --emit-only` completed successfully.
- Caveat: this is not proof of real different-network connectivity. A physical trusted device and a relay/bootstrap route reachable from both networks are still required for the actual QR pairing acceptance and reconnect proof.

## 2026-06-26 Attachment and Document Ingestion Verification

- Scope: no-device SwiftPM/source/script evidence for file and image attachments through the runtime-mediated chat boundary.
- Result: `DocumentIngestion` is included in the root Swift package, `CompanionCore` depends on it, and `LocalRuntimeMessageRouter` uses it to turn supported document attachments into prompt text while preserving image attachments for vision-capable backend requests.
- Result: the supported document set currently includes PDF, OpenXML office formats, HWPX/HWPML, best-effort legacy HWP, OpenDocument, iWork XML archives, EPUB, RTF, HTML/XHTML, WebArchive through `textutil`, XML, Markdown/reStructuredText/AsciiDoc/logs, JSON/JSONL, YAML, TOML, CSV/TSV, INI/properties/env, and plain text.
- Result: Android's file picker MIME list includes the document families above and adds `image/*` only when the selected chat model reports image/vision/multimodal support.
- Latest focused evidence: `swift test --filter DocumentTextExtractorTests` passed 20 tests, `python3 script/check_copy_hygiene.py` passed, `python3 script/check_android_string_parity.py` passed, and `./script/check_no_device_quality.sh` passed.
- Caveat: the Android phone was disconnected, so this does not prove physical file picker behavior, real-device upload latency, OCR for scanned PDFs, password-protected files, provider-specific vision quality, or large-document summarization quality.

## 2026-06-26 Android Trusted Runtime Forget Confirmation

- Scope: no-device Robolectric/Compose coverage for the Android Settings trusted-runtime removal path.
- Result: Settings now requires confirmation before forgetting the saved trusted runtime. Cancel leaves the callback untouched; confirm invokes it exactly once.
- Result: destructive haptic feedback is asserted on final confirmation only, with no destructive feedback when the dialog opens.
- Latest focused evidence: `ClientScreensNoDeviceComposeTest.settingsTrustedRuntimeForgetRequiresConfirmation` passed, along with Android string parity, copy hygiene, docs hygiene, and whitespace diff checks for the touched files.
- Caveat: this does not prove physical haptic feel or real-device Settings rendering.

## 2026-06-27 Android Multi-Code Copy Labels and macOS Activity Trust Audit Copy

- Scope: no-device Android Compose/Robolectric, macOS XCTest, and source/script evidence for accessibility copy precision.
- Result: Android assistant messages now distinguish multiple fenced code-block copy actions by language and order, while preserving the generic localized label for a single code block.
- Result: macOS Activity trusted-device audit summaries now say that a device was trusted or trust was removed, with localized fallback copy when the device name is blank.
- Guardrail: copy hygiene requires the Android named/numbered code-block label resources, action-label test coverage, and macOS Activity trusted-device audit helpers. macOS localization parity requires the new trust-audit strings across the five supported languages.
- Latest focused evidence: Android `chatScreenCodeBlockCopyUsesLocalizedCodeActionLabels` and `chatScreenMultipleCodeBlockCopyActionsLocalizeDistinctContextAcrossSupportedLanguages` passed. macOS `testActivityTrustedDeviceLogSummariesUseDeviceContextAcrossLanguages` passed.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scan, real device haptics, physical TalkBack or VoiceOver output, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Drawer Chat Menu Contextual Action Labels

- Scope: no-device Android Compose/Robolectric and source/script evidence for drawer chat-history menu accessibility.
- Result: Android drawer chat overflow menu items now keep the target chat title in their accessibility label and click-action label after the menu opens. The visible labels remain compact.
- Result: the coverage spans English, Korean, Japanese, Simplified Chinese, and French for rename, archive, restore, and delete menu actions.
- Guardrail: copy hygiene now requires the contextual drawer menu semantics, the new `rename_chat_named` and `delete_chat_named` resources, the five-language menu regression, and the aggregate no-device summary phrase `Android drawer chat menu contextual action labels`.
- Latest focused evidence: Android `chatDrawerOverflowMenuActionsKeepChatContextAcrossSupportedLanguages` passed, along with Android string parity and copy hygiene.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical install, real drawer/menu TalkBack output, physical haptic feel, camera QR scan, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Menu-Bar Quick Action Accessibility Parity

- Scope: no-device macOS SwiftUI source, XCTest, and script evidence for menu-bar quick actions.
- Result: MenuBarExtra `Refresh` and `Load Models` now expose the same localized accessibility value and hint helpers as the toolbar and Status quick actions.
- Guardrail: macOS localization and copy hygiene scripts now require the actual menu-bar button chains to include `help`, `accessibilityValue`, and `accessibilityHint`, and the no-device summary names `macOS menu-bar quick action accessibility parity`.
- Latest focused evidence: macOS `testQuickActionAccessibilityUsesSelectedLanguage` passed, along with macOS localization parity and copy hygiene.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: this does not prove a live VoiceOver session, rendered menu-bar screenshots, physical Android reconnect, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Connection Recovery Private Overlay Toggle Accessibility

- Scope: no-device macOS SwiftUI source, XCTest, localization, and script evidence for Connection Recovery private-overlay controls.
- Result: the two visible `Use Private Overlay Route` toggles now keep compact copy but expose different accessibility labels for Bootstrap Relay and manual Connection route scopes.
- Result: the private-overlay toggle accessibility values are localized as enabled/disabled across English, Korean, Japanese, Simplified Chinese, and French, and the route-specific hints remain localized.
- Guardrail: macOS localization and copy hygiene scripts now require the helper functions, button wiring, localization keys, five-language XCTest, and aggregate no-device summary phrase `macOS Connection Recovery private-overlay toggle accessibility labels`.
- Latest focused evidence: macOS `testConnectionRecoveryPrivateOverlayToggleAccessibilityDistinguishesRouteContext` passed, along with macOS localization parity and copy hygiene.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical install, live VoiceOver output, camera QR scan, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Copy Success Live-Region Accessibility

- Scope: no-device Android Compose/source/script evidence for chat copy success feedback.
- Result: message long-press copy and code-block copy now announce the localized `Copied` result through a `LiveRegionMode.Polite` semantics node, while preserving the existing Toast and haptic feedback.
- Result: the copy success announcement uses the current app language across English, Korean, Japanese, Simplified Chinese, and French.
- Guardrail: copy hygiene now requires the copy-success announcement channel, the polite live-region node, focused Compose assertions, and the aggregate no-device summary phrase `Android copy success live-region accessibility`.
- Latest focused evidence: Android `chatScreenMessageCopyActionsExposeLocalizedActionLabels` and `chatScreenCodeBlockCopyUsesLocalizedCodeActionLabels` passed after executing the actual copy actions and asserting live-region output.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack announcement timing, physical clipboard behavior, camera QR scan, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Pairing QR Cross-Network Route Help

- Scope: macOS Pairing QR generation help text and five-language localization expectations.
- Result: the disabled Pairing QR generation hint now names the required cross-network route classes: relay, VPN, tunnel, or private overlay.
- Result: the localization test expectations were updated for English, Korean, Japanese, Simplified Chinese, and French.
- Guardrail: copy hygiene now requires the five localized route-specific disabled Pairing QR generation hints.
- Caveat: this is source/localization evidence only. It does not prove rendered macOS screenshots or real different-network connectivity.

## 2026-06-27 Android Cross-Network QR Recovery Guidance

- Scope: Android pairing-card copy, route-warning card recovery steps, five-language resources, Compose assertions, and script guardrails.
- Result: the primary Android pairing card now explains that different-network QR pairing requires a relay, VPN, tunnel, or private-overlay route reachable from both devices.
- Result: warning-state route notices now render a short recovery sequence: open AetherLink Runtime, generate the latest QR, then scan it on the client.
- Result: the route-warning card accessibility summary includes the same recovery steps when the primary action is `Scan latest QR`.
- Guardrail: copy hygiene now requires `route_notice_accessibility_summary_with_steps`, `routeNoticeRecoverySteps(notice)`, `route_notice_recovery_steps`, and the primary cross-network pairing copy.
- Latest focused evidence: Android `settingsScreenRendersPairingCopyAcrossLaunchLanguages` and `connectionStatusRefreshNeededRouteNoticeClickScansLatestQrWithHaptic` passed with Kotlin incremental compilation disabled.
- Caveat: this is no-device Android UI evidence. It does not prove production NAT traversal, optical QR camera scanning, or a public/VPN/tunnel relay from unrelated networks.

## 2026-06-27 Android Physical Device Relay Pairing Smoke

- Scope: physical Android device install, pairing-result deeplink, trusted-route persistence, runtime reconnect, and chat/cancel smoke.
- Device: `SM_S936N` / `R3CXC0M76VM`, authorized through ADB.
- Result: `script/android_usb_install.sh` built, installed, and launched the current debug APK successfully.
- Result: `script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect` passed. The app handled the `aetherlink://pair` URI, completed development pairing, and reconnected after force-stop/relaunch with app data preserved.
- Result: `script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect --expect-chat-cancel` passed. The runtime observed `chat.send`, `chat.delta`, `chat.cancel`, and `chat.done` from the physical Android UI.
- Artifact: latest chat/cancel screenshot captured at `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.GTfBbf/aetherlink-chat-cancel-smoke.png`.
- Caveat: this is a USB-assisted development relay proof using ADB reverse and deeplink injection. It does not prove optical camera QR scanning or public/VPN/tunnel relay reachability from two unrelated networks.

## 2026-06-27 Android QR Pairing Live-Region Accessibility

- Scope: no-device Android Compose/source/script evidence for QR pairing and route-refresh accessibility.
- Result: the route-refresh confirmation and pending QR-route warning cards now expose polite live regions so QR recovery state changes are available to assistive navigation.
- Guardrail: copy hygiene now requires the QR route-refresh/pending-route live-region source snippets, focused Compose assertions, and the aggregate no-device summary phrase `Android QR pairing live-region accessibility`.
- Latest focused evidence: Android `settingsScreenRendersPendingPairingRouteState` and `settingsScreenAnnouncesRouteRefreshSavedNotice` passed after asserting localized content descriptions with `LiveRegionMode.Polite`.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical camera QR scan, physical TalkBack announcement timing, real haptic output, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Connection Recovery Fallback Copy

- Scope: no-device macOS SwiftUI source, localization, XCTest expectation, and script-guard evidence for Connection Recovery copy.
- Result: user-facing accessibility copy now describes advanced route entry as fallback connection details for future pairing QR routes instead of manual connection details.
- Result: the private-overlay route label now reads as a fallback connection route across English, Korean, Japanese, Simplified Chinese, and French.
- Guardrail: macOS localization and copy hygiene scripts now require the fallback route label and fallback save-connection hint.
- Latest focused evidence: macOS `testConnectionRecoveryFallbackActionAccessibilityHintsUseSelectedLanguage` and `testConnectionRecoveryPrivateOverlayToggleAccessibilityDistinguishesRouteContext` passed, along with macOS localization parity and copy hygiene.
- Caveat: this does not prove live VoiceOver output, rendered macOS screen capture, physical Android reconnect, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Activity Row Tone Accessibility Labels

- Scope: no-device macOS SwiftUI source, XCTest, localization, and script evidence for Activity row severity accessibility.
- Result: Activity rows now expose a localized accessibility label that combines the event summary with the row tone status, so the hidden severity icon/color has an equivalent spoken status.
- Result: the tone mapping uses the existing localized status vocabulary: `Ready`, `Needs attention`, `Not ready`, and `Pending`.
- Guardrail: macOS localization and copy hygiene scripts now require the Activity row helper, the localized row label key, and the aggregate no-device summary phrase `macOS Activity row tone accessibility labels`.
- Latest focused evidence: macOS `testActivityLogRowAccessibilityLabelIncludesLocalizedTone` passed across English, Korean, Japanese, Simplified Chinese, and French warning/fallback labels. `AetherLinkRenderSmokeTests` also passed.
- Caveat: this does not prove a live VoiceOver session, rendered macOS screen capture, physical Android reconnect, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Settings Status and Chat History Accessibility Summaries

- Scope: no-device Android Compose/source/script evidence for Settings and connection-state accessibility polish.
- Result: the connection status hero now exposes one localized card-level accessibility summary composed from the current state title and detail. Covered states include pairing required, latest-QR route refresh, saved relay reconnect, and connected trusted runtime across English, Korean, Japanese, Simplified Chinese, and French.
- Result: Settings chat-history rows now expose localized row summaries that combine the chat title and current state/count, while preserving separate action buttons for archive, restore, and permanent delete.
- Guardrail: copy hygiene now requires the status hero summary resource, merged hero semantics, the chat-history row summary wiring, focused Compose regressions, and the aggregate no-device summary phrases `Android connection status hero accessibility summary` and `chat history row accessibility summaries`.
- Latest focused evidence: Android `settingsConnectionStatusHeroExposesLocalizedAccessibilitySummaries` and `settingsChatHistoryRowsExposeLocalizedAccessibilitySummaries` passed, along with Android string parity, copy hygiene, and no-device shell syntax validation.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack output, physical install, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Provider Row Accessibility Summaries

- Scope: no-device Android Compose/source/script evidence for model-provider status row accessibility.
- Result: provider rows now expose one localized summary for provider name, status, detail, and retry guidance when retryable, while the diagnostics Show/Hide control remains a separate focusable action.
- Result: the row summary is covered across available, unavailable retryable, and unavailable non-retryable providers in English, Korean, Japanese, Simplified Chinese, and French.
- Guardrail: copy hygiene now requires the provider-row summary resources, merged information-block semantics, the five-language Compose regression, and the aggregate no-device summary phrase `Android provider row accessibility summaries`.
- Latest focused evidence: Android `connectionStatusProviderRowsExposeLocalizedAccessibilitySummariesAcrossSupportedLanguages` and `connectionStatusProviderDiagnosticsToggleExposesExpandedState` passed, along with Android string parity and copy hygiene.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack output, physical install, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Documentation Stable Contract Guardrails

- Scope: no-device documentation/script evidence for stable product-contract hygiene.
- Result: documentation contracts now use current handoff docs only, so `docs/progress.md` can no longer satisfy required product contracts by itself.
- Result: `docs/protocol.md` must directly define `chat.send.locale` and the five-language launch set, while `README.md` must keep Android and macOS app-language verification plus runtime locale handoff visible.
- Guardrail: `script/check_docs_hygiene.py` now has file-specific contracts for the protocol locale contract and README cross-platform language verification.
- Latest focused evidence: `python3 script/check_docs_hygiene.py` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical install, QR camera pairing, physical TalkBack or VoiceOver output, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Trusted Runtime Forget Confirmation Action Labels

- Scope: no-device Android Compose/source/script evidence for the Settings trusted-runtime forget confirmation dialog.
- Result: the confirmation dialog keeps compact visible copy, while the destructive confirm action and cancel action now expose localized runtime-specific accessibility labels and click action labels.
- Result: the same saved runtime name is carried from the initial `Forget` launcher into the final confirmation semantics, reducing ambiguity before a trust-removal action.
- Guardrail: copy hygiene now requires the named confirmation/cancel resources, their semantic wiring, the five-language Compose regression, and the aggregate no-device summary phrase `Android trusted-runtime forget confirmation action labels`.
- Latest focused evidence: Android `settingsTrustedRuntimeForgetActionNamesRuntimeAcrossSupportedLanguages` passed across English, Korean, Japanese, Simplified Chinese, and French, along with Android string parity, copy hygiene, docs hygiene, diff whitespace, and the aggregate no-device quality gate.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack output, physical install, real haptic output, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Drawer Streaming Lockout Accessibility State

- Scope: no-device Android Compose/source/script evidence for previous-chat drawer rows while streaming is active.
- Result: disabled previous-chat drawer rows now expose an explicit disabled semantic state and the localized wait-for-stream reason as a state description.
- Result: the drawer overflow button for each locked chat row exposes the same localized state description, so the disabled action is not silent for accessibility users.
- Guardrail: copy hygiene now requires the disabled semantic-state wiring, the disabled state-description wiring, the focused five-language Compose regression, and the aggregate no-device summary phrase `Android drawer streaming lockout accessibility state`.
- Latest focused evidence: Android `chatDrawerDisabledItemsExplainStreamingLockoutAcrossSupportedLanguages` passed across English, Korean, Japanese, Simplified Chinese, and French, along with Android string parity, copy hygiene, docs hygiene, diff whitespace, and the aggregate no-device quality gate.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack output, physical install, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Connection Recovery Disclosure Accessibility State

- Scope: no-device macOS SwiftUI source, XCTest, localization, and script evidence for disclosure expanded/collapsed state.
- Result: Connection Recovery advanced settings and connection diagnostics disclosures now expose localized labels, expanded/collapsed values, and hints instead of relying only on visible disclosure text.
- Result: the five-language coverage includes English, Korean, Japanese, Simplified Chinese, and French for both Connection Recovery and diagnostics disclosure states.
- Guardrail: macOS localization and copy hygiene scripts now require the helper functions, localized state keys, focused XCTest, and aggregate no-device summary phrase `macOS Connection Recovery and diagnostics disclosure accessibility state`.
- Latest focused evidence: macOS `testConnectionRecoveryAndRouteDiagnosticDisclosuresExposeLocalizedExpandedState` passed, along with macOS localization parity and copy hygiene.
- Caveat: this does not prove live VoiceOver output, rendered macOS screen capture, physical Android reconnect, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android QR Scanner Five-Language Chrome Accessibility

- Scope: no-device Android Compose/source/script evidence for first-run QR scanner chrome localization and accessibility.
- Result: `PairingQrScannerChromeNoDeviceComposeTest` now renders the scanner with localized `LocalContext` values across English, Korean, Japanese, Simplified Chinese, and French.
- Result: the no-device test covers localized scanner title/detail, camera permission request, blocked-permission settings recovery, cancel actions, flashlight labels, and flashlight on/off state descriptions while preserving haptic callback assertions.
- Guardrail: copy hygiene now requires the locale matrix, localized scanner expectation helper, QR scanner resource usage, and aggregate no-device summary phrase `Android QR scanner five-language chrome accessibility`.
- Latest focused evidence: Android `PairingQrScannerChromeNoDeviceComposeTest` passed, along with Android string parity and copy hygiene.
- Caveat: the Android phone was disconnected, so this does not prove physical camera QR scanning, physical TalkBack output, physical install, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 Android Attachment Picker Single-Dispatch Guard

- Scope: no-device Android source/JVM/script evidence for chat composer file attachment intake.
- Result: the ActivityResult document picker path now goes through `handlePickedAttachments(...)`, which ignores empty picker results and dispatches a non-empty URI batch exactly once to the ViewModel.
- Guardrail: copy hygiene now requires the callback helper, the one-dispatch helper body, the focused JVM regression, and the aggregate no-device summary phrase `Android attachment picker single-dispatch guard`.
- Latest focused evidence: Android `AppNavigationTest.attachmentPickerCallbackAddsPickedUrisOnceAndIgnoresEmptySelections` passed, along with copy hygiene.
- Latest gate: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/check_no_device_quality.sh` passed after this update.
- Caveat: the Android phone was disconnected, so this does not prove physical file picker behavior, real document provider URI permissions, real haptic output, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-27 macOS Provider Technical Details Accessibility State

- Scope: no-device macOS SwiftUI source, XCTest, localization, and shell-script syntax evidence for Model Providers disclosure accessibility.
- Result: provider technical-details disclosures now expose localized expanded/collapsed accessibility values and state-specific hints, while keeping the provider-specific label.
- Result: the helper coverage includes English, Korean, Japanese, Simplified Chinese, and French.
- Guardrail: macOS localization now requires the provider disclosure state wiring and helper snippets, and the aggregate no-device summary includes `macOS provider technical-details accessibility state`.
- Latest focused evidence: macOS `testProviderStatusTechnicalDetailsAccessibilityStateUsesSelectedLanguage` passed, along with macOS localization parity, no-device shell syntax validation, and scoped `git diff --check`.
- Caveat: this does not prove live VoiceOver output, rendered macOS screen capture, physical Android reconnect, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Memory Streaming Lockout and macOS Bootstrap Save State

- Scope: no-device Android Compose/source/string evidence plus macOS SwiftUI source/XCTest/localization evidence.
- Result: Android Settings Memory add, toggle, and remove actions are disabled during active response streaming and expose the localized wait-for-stream state in all five supported app languages.
- Result: macOS Connection Recovery Save Bootstrap Relay now exposes an input-sensitive accessibility value, distinguishing ready-to-save endpoints from blank input that clears the saved bootstrap relay.
- Guardrail: copy hygiene now requires the Android streaming-aware memory gate, the five-language Compose regression, the macOS Save Bootstrap Relay value helper, its five-language XCTest, and aggregate no-device coverage labels.
- Latest focused evidence: Android `memoryActionsRequireConnectedTrustedRuntime`, `settingsMemoryEmptyStatesAnnounceLocalizedLiveRegion`, and `settingsMemoryActionsWaitForStreamAcrossSupportedLanguages` passed, macOS `testConnectionRecoverySaveBootstrapRelayAccessibilityValueUsesSelectedLanguage` passed, and Android string parity, macOS localization, and copy hygiene passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix, including QR/relay smoke, Android no-device tests, macOS localization/render smoke, model routing tests, document ingestion tests, and runtime router tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, physical TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Model Picker Streaming Transition Lockout and macOS Activity Ready Tone

- Scope: no-device Android Compose/ViewModel evidence plus macOS SwiftUI source/XCTest/localization evidence.
- Result: Android closes an already-open Chat top-bar model picker when streaming starts, disables refresh/model rows during the transition, and rejects ViewModel model selection or pull requests with `generation_in_progress` while a response is active.
- Result: macOS Activity now announces successful Connection Recovery route events as Ready instead of Pending, matching the saved/ready route state that users inspect after pairing recovery actions.
- Guardrail: copy hygiene now requires the Android source guards, focused Compose regression, ViewModel regression, macOS activity tone helper, route-success XCTest, and no-device summary labels.
- Latest focused evidence: Android `chatTopBarModelPickerClosesOpenMenuWhenStreamingStarts` and `streamingBlocksModelSelectionAndInstallRequests` passed, macOS `testActivityRouteSuccessLogRowsUseReadyTone` passed, and macOS localization plus copy hygiene passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix, including Android no-device UI/ViewModel tests, macOS localization/render checks, runtime routing, model routing, relay route, chat-store, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, physical TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Streaming Send Guard and macOS Local Model Readiness

- Scope: no-device Android ViewModel evidence plus macOS SwiftUI source/XCTest evidence.
- Result: Android now blocks `sendChatMessage()` while `isStreaming` is true, preserving the active request id, current input, current messages, and existing stream state instead of dispatching a second `chat.send`.
- Result: macOS Status overview now uses the same installed-local visibility policy as the Models panel when deciding whether model loading is complete. Hidden provider-managed/cloud and uninstalled models do not count as ready.
- Guardrail: copy hygiene now requires the Android source guard, the focused ViewModel regression, the macOS installed-local readiness source contract, the focused XCTest, and the no-device summary labels.
- Latest focused evidence: Android `streamingBlocksReentrantChatSendRequests` passed, macOS `testRuntimeOverviewTreatsHiddenModelsAsNotLoaded` passed, and copy hygiene, macOS localization, docs hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix, including Android ViewModel tests, macOS localization/render checks, QR/relay smoke, runtime routing, model routing, chat-store, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, physical TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Streaming Attachment Lockout and macOS Readiness Fallbacks

- Scope: no-device Android ViewModel evidence plus macOS SwiftUI source/XCTest/localization evidence.
- Result: Android now blocks `addAttachmentReferences(...)` and `removePendingAttachment(...)` while `isStreaming` is true. The focused regression proves no attachment metadata or bytes are read, the existing pending attachment list is preserved, and `generation_in_progress` is surfaced.
- Result: macOS readiness row accessibility labels now fall back to localized `Readiness item`, `Unknown status`, and `No readiness details` values when defensive empty strings reach the helper.
- Guardrail: copy hygiene now requires the Android streaming attachment source/test contract, macOS localization now requires the readiness fallback resources and XCTest, and the no-device gate names both contracts in its readiness addendum.
- Latest focused evidence: Android `streamingBlocksPendingAttachmentMutation` passed, macOS `testReadinessRowAccessibilityLabelUsesTitleStatusDetailAndFallbacks` passed, and macOS localization plus copy hygiene passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix, including Android attachment/ViewModel tests, macOS localization/render checks, QR/relay smoke, runtime routing, model routing, chat-store, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, physical TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Streaming Embedding Guard and macOS Trusted Device Context

- Scope: no-device Android ViewModel/string evidence plus macOS SwiftUI source/XCTest/localization evidence.
- Result: Android now blocks chat embedding model selection and clearing while `isStreaming` is true. The focused regression proves the selected embedding model remains persisted, no pull envelope is sent for model install paths, and `generation_in_progress` is surfaced.
- Result: the localized `generation_in_progress` copy now says to wait before making changes instead of only before switching chats.
- Result: macOS trusted-device row accessibility now preserves the device ID suffix when paired date metadata is missing but device ID remains available. The focused XCTest covers all five supported app languages and the final row label.
- Guardrail: copy hygiene now requires the Android embedding streaming guard and focused regression snippets. macOS localization and copy hygiene require the missing-date trusted-device ID fallback, and the no-device gate names both contracts in its readiness addendum.
- Latest focused evidence: Android `streamingBlocksModelSelectionAndInstallRequests` passed, macOS `testTrustedDeviceRowAccessibilityLabelUsesDeviceContext` passed, Android string parity, macOS localization, copy hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix (`/tmp/aetherlink-no-device-embedding-trusted-20260628080918.log`), including Android ViewModel tests, macOS localization/render checks, QR/relay smoke, runtime routing, model routing, chat-store, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, physical TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Settings Embedding Streaming Lockout and macOS Remove Trust Hint

- Scope: no-device Android Settings Compose evidence plus macOS SwiftUI source/XCTest/localization evidence.
- Result: Android Settings disables memory indexing model refresh/select controls while `isStreaming` is true. The focused Compose regression proves selected/alternate embedding rows and Refresh models are disabled, expose the wait-for-stream state description, and do not call selection or refresh callbacks.
- Result: macOS Trusted Devices destructive `Remove Trust` row buttons now expose a localized VoiceOver hint explaining that the device must pair again before it can use AetherLink Runtime after removal.
- Guardrail: copy hygiene now requires the Android Settings embedding streaming source/test contract and the macOS trusted-device remove hint source/test/localization contract. The no-device gate names `Settings embedding model streaming lockout accessibility state` and `macOS trusted-device remove accessibility hints`.
- Latest focused evidence: Android `settingsEmbeddingModelControlsAreDisabledWhileStreaming` passed, macOS `testTrustedDeviceRemoveButtonAccessibilityHintUsesSelectedLanguage` passed, Android string parity, macOS localization, copy hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix (`/tmp/aetherlink-no-device-settings-embedding-trusted-hint-20260628081942.log`), including Android Compose/ViewModel tests, macOS localization/render checks, QR/relay smoke, runtime routing, model routing, chat-store, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, physical TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Chat History Display-Model Search and macOS Preference Hints

- Scope: no-device Android helper/JVM evidence plus macOS SwiftUI source/XCTest/localization evidence.
- Result: Android chat history search now matches resolved model display names. The focused JVM regression proves searching `qwen` finds a session whose stored `modelId` is opaque but resolves through the current model list to `Qwen3 8B`.
- Result: macOS sidebar Appearance and Language pickers now expose localized VoiceOver hints that the chosen preference is saved for future launches.
- Guardrail: copy hygiene now requires the Android display-model search regression and the macOS sidebar preference hint source/test/localization contract. The no-device gate names `Android chat history display-model search` and `macOS sidebar preference picker accessibility hints`.
- Latest focused evidence: Android `chatHistorySearchMatchesResolvedModelDisplayName` passed, macOS `testSidebarPreferencePickerAccessibilityHintsUseSelectedLanguage` passed, Android string parity, macOS localization, copy hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix (`/tmp/aetherlink-no-device-chat-history-sidebar-hints-20260628082854.log`), including Android Compose/ViewModel/JVM tests, macOS localization/render checks, QR/relay smoke, runtime routing, model routing, chat-store, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, physical TalkBack or VoiceOver output, real haptic feel, camera QR scanning, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Runtime-Owned Memory Storage Redaction

- Scope: no-device Android source/JVM/script evidence for keeping runtime-owned memory and processing data authoritative on the runtime host.
- Result: Android `RuntimeLocalStore` now writes through `withoutRuntimeOwnedLocalData()`, clearing runtime-owned chat message bodies and runtime memory entries before they reach device-local storage.
- Result: `runtimeMemoryListRendersInMemoryButRedactsDeviceStorage` proves runtime memory still appears in the connected UI state while the saved device snapshot remains empty.
- Guardrail: copy hygiene now requires the redaction helper, memory-entry clearing, and the focused storage redaction regressions. The aggregate no-device gate now includes both focused Android tests and names `Android runtime-owned local memory storage redaction`.
- Latest focused evidence: Android `runtimeMemoryListRendersInMemoryButRedactsDeviceStorage` and `deviceStorageSnapshotDropsRuntimeOwnedDataButKeepsLocalDrafts` passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix, including Android source/JVM storage redaction tests, script hygiene, docs hygiene, Android string parity, macOS localization, Swift build/tests, QR/relay smoke, runtime routing, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptics, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Android Chat Send Runtime-Memory Boundary

- Scope: no-device Android source/JVM/script evidence for keeping memory prompt injection runtime-owned.
- Result: Android `chatSendMessages(...)` no longer turns UI memory entries into a client-supplied `Runtime user memory:` system prompt. The payload keeps the capability guard, client-visible conversation, and final user attachments.
- Result: `chatSendMessagesPrependsCapabilityGuardWithoutClientSuppliedMemoryContext` proves enabled and disabled memory entries are ignored by chat payload assembly, so the runtime host remains responsible for memory injection from its own store.
- Guardrail: copy hygiene now fails if Android payload assembly reintroduces `Runtime user memory:`, and the aggregate no-device gate now runs the updated focused regression.
- Latest focused evidence: Android `chatSendMessagesPrependsCapabilityGuardWithoutClientSuppliedMemoryContext` passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the fix, including Android chat payload memory suppression, storage redaction, script hygiene, docs hygiene, Android string parity, macOS localization, Swift build/tests, QR/relay smoke, runtime routing, memory, compaction, reasoning, and suggestion tests.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptics, live streamed chat/cancel, or real different-network runtime connectivity.

## 2026-06-28 Runtime Memory Client Boundary Follow-up

- Scope: documentation-only current-session record for the runtime-memory client boundary; GPT-5.3-Codex-Spark was not used.
- Result: current clients must not prepend cached memory context into `chat.send` / `messages`; memory prompt injection is runtime-owned.
- Result: stale `Runtime user memory:` client input is compatibility-only and is stripped/rebuilt by the runtime from the runtime memory store.
- Guardrail: docs hygiene now requires `docs/protocol.md` to keep current-client memory prompt suppression, compatibility-client stale-memory stripping, and runtime-owned memory storage visible together.
- Latest focused evidence: docs hygiene, copy hygiene, shell syntax, and whitespace checks passed after the documentation contract update.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the documentation contract update.
- Caveat: the Android phone was disconnected, so QR pairing, real different-network routing, live streamed chat/cancel, physical install, and live device validation remain pending.

## 2026-06-28 Android Private-Overlay Real Relay TCP Pairing Path

- Scope: no-device Android app integration evidence for private-overlay QR relay pairing; GPT-5.3-Codex-Spark was not used.
- Result: `RuntimeRelayTcpClient` now has a socket-factory seam that leaves production dialing unchanged while allowing tests to preserve non-loopback QR route material and dial a local fake relay.
- Result: `privateOverlayRelayQrPairingUsesRealRelayTcpClientAndPersistsOverlayRoute` proves a `relay_scope=private_overlay` QR with `100.64.1.10`, relay secret, lease expiration, and relay nonce goes through the real Android relay TCP client, handshake, AES-GCM relay frame encryption, pairing request/response, trusted-route persistence, and active relay route state.
- Guardrail: copy hygiene now requires the private-overlay real relay TCP regression and the aggregate no-device summary label `Android private-overlay real relay TCP pairing path`.
- Latest focused evidence: Android `RuntimeClientViewModelRelayIntegrationTest` passed, core transport `RuntimeRelayRoutePreparationTest` passed, copy hygiene passed, docs hygiene passed, shell syntax passed, and whitespace checks passed after the patch.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after adding the private-overlay real relay TCP pairing path to the default gate.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, real device haptics, live provider-backed streamed chat/cancel, or actual different-network reachability through a public relay/VPN/tunnel/private overlay.

## 2026-06-28 Android Private-Overlay Real Relay TCP Reconnect Path

- Scope: no-device Android app integration evidence for saved trusted private-overlay relay reconnect; GPT-5.3-Codex-Spark was not used.
- Result: `trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession` is now in the default no-device gate. It starts from a persisted trusted runtime with private-overlay relay material and proves app-init restore uses the real Android relay TCP client, sends `hello`, verifies a signed `auth.challenge`, sends `auth.response`, handles accepted authentication, refreshes route material, and reaches `runtime.health` without direct TCP.
- Result: the regression covers the current read-loop auth challenge path, where the client sends the challenge response before waiting on the next runtime frame.
- Result: `DeviceIdentity` uses JVM/Android-compatible `java.util.Base64` for signing and generated public-key material, keeping the identity protocol path covered in local no-device tests.
- Guardrail: copy hygiene now requires the private-overlay real relay TCP reconnect regression and the aggregate no-device summary label `Android private-overlay real relay TCP reconnect path`.
- Latest focused evidence: Android `trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession`, Android `RuntimeClientViewModelRelayIntegrationTest`, core pairing tests, copy hygiene, docs hygiene, shell syntax, and whitespace checks passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after adding the private-overlay real relay TCP reconnect path to the default gate.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, real device haptics, live provider-backed streamed chat/cancel, or actual different-network reachability through a public relay/VPN/tunnel/private overlay.

## 2026-06-28 Android Device Identity Base64 Signature Guard

- Scope: no-device Android core pairing evidence for the trusted-device identity/signature boundary; GPT-5.3-Codex-Spark was not used.
- Result: `DeviceIdentityStore` now uses `java.util.Base64` for generated public-key material, matching `DeviceIdentity.sign(...)` and avoiding Android framework Base64 behavior in JVM tests.
- Result: `RuntimeIdentityProofVerifierTest.deviceIdentitySignaturesUseJvmCompatibleBase64AndVerifyWithStoredPublicKey` proves generated identity signatures are nonblank, JVM-decodable, and verify against the generated public key for raw auth nonce signatures.
- Guardrail: copy hygiene now requires the identity signature regression and the aggregate no-device summary label `Android device identity Base64 signature guard`.
- Latest focused evidence: Android `RuntimeIdentityProofVerifierTest` passed.
- Caveat: the Android phone was disconnected, so this does not prove Android Keystore behavior on a physical device, physical install, camera QR scanning, or actual different-network reachability.

## 2026-06-28 Android Device Identity Persistence Guard

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.DeviceIdentityStoreTest -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered recreated `DeviceIdentityStore` instances reusing the same persisted client id/name/public key, client-auth signature verification against that key, local DataStore containing only `android_device_id` and `android_device_name`, and keypair-store failure preserving the existing stored identity.
- Guardrail: the default no-device gate now runs `DeviceIdentityStoreTest`, `script/check_copy_hygiene.py` verifies the source/test/no-device contract, and the no-device summary includes `Android device identity persistence guard`.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-device-identity-persistence.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android device identity persistence guard`.
- Caveat: the Android phone was disconnected, so this does not prove physical Android Keystore behavior, physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Android Relay Secret Base64 Boundary

- Scope: no-device Android core pairing evidence for QR relay secret persistence; GPT-5.3-Codex-Spark was not used.
- Result: `AndroidKeystoreRelaySecretStore` now uses `java.util.Base64` to encode and decode encrypted relay secret blobs, preserving the existing no-wrap serialized format without relying on Android framework Base64 in JVM-friendly code paths.
- Result: the focused core pairing suite still passes after the relay secret storage boundary change.
- Latest focused evidence: Android `:core:pairing:testDebugUnitTest` passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after the relay secret Base64 boundary change, including pairing QR artifact generation, authenticated mock relay E2E, Android private-overlay relay pairing/reconnect tests, app ViewModel/Compose regressions, macOS build/tests, localization, docs, copy, icon, and license hygiene.
- Caveat: the Android phone was disconnected, so this does not prove physical Android Keystore behavior, physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Client Auth Domain Separation

- Scope: no-device Android core/app evidence plus macOS runtime router XCTest evidence for trusted-device challenge-response authentication; GPT-5.3-Codex-Spark was not used.
- Result: Android `DeviceIdentity.signAuthenticationResponse(...)` signs the domain-separated message `AetherLink client auth response v1\n<device_id>\n<nonce>` instead of the raw nonce.
- Result: macOS `LocalRuntimeMessageRouter` verifies that same domain-separated client-auth message before authenticating a trusted device connection.
- Result: `testTrustedAuthResponseRejectsRawNonceSignature` proves a raw nonce signature returns `authentication_failed` and does not unlock runtime commands.
- Guardrail: copy hygiene now requires the Android signer, macOS verifier, macOS raw-nonce rejection regression, protocol/security documentation, and the aggregate no-device label `Android/macOS client auth domain separation`.
- Latest focused evidence: Android `RuntimeIdentityProofVerifierTest`, Android trusted private-overlay relay reconnect, and macOS trusted auth success/raw-nonce rejection tests passed.
- Latest aggregate evidence: `script/check_no_device_quality.sh` passed after adding client-auth domain separation, including the authenticated relay smoke updated to sign the domain-separated client-auth message.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Attachment Read Bound and Auth Session Cleanup

- Scope: no-device Android app attachment ingestion evidence plus macOS runtime transport/auth cleanup evidence; GPT-5.3-Codex-Spark was not used.
- Result: Android attachment reads are bounded to `MAX_ATTACHMENT_BYTES + 1`, so unknown-size or incorrectly reported content providers cannot force an unbounded `readBytes()` allocation before the app rejects oversize input.
- Result: `addAttachmentsBoundsReadWhenReportedSizeIsUnknown` proves unknown-size oversize content is rejected as `attachment_too_large` without adding a pending attachment.
- Result: macOS local and relay transports now notify `LocalRuntimeMessageRouter.connectionDidClose(...)`, and `testConnectionDidCloseClearsAuthenticatedSession` proves authenticated session state is cleared after disconnect.
- Guardrail: copy hygiene now requires the bounded Android attachment-read path, the macOS transport disconnect hooks, the router cleanup hook, the focused tests, and no-device coverage labels `Android bounded attachment read guard` and `macOS auth session disconnect cleanup`.
- Latest focused evidence: Android bounded attachment read test, macOS auth success/raw nonce/disconnect cleanup tests, Swift build, copy hygiene, docs hygiene, shell syntax, and diff whitespace checks passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after the bounded attachment-read and auth-session cleanup changes, including QR artifact generation, authenticated relay smoke, Android no-device tests, macOS localization/render/document/model/router tests, and hygiene checks.
- Caveat: the Android phone was disconnected, so this does not prove physical file picker behavior, physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Transport Disconnect Idempotency

- Scope: no-device macOS Transport SwiftPM evidence for keeping auth-session cleanup callbacks stable at the transport boundary; GPT-5.3-Codex-Spark was not used.
- Result: relay disconnect cleanup is now idempotent for a connection id. `stop()` consumes the current relay connection id before cancelling, and later failed/cancelled state callbacks only notify when they still own the current connection id.
- Result: `RelayPeerClientTests.testRelayPeerClientReportsDisconnectOnceWhenStoppedConnectionCancels` proves relay stop/cancel emits one disconnect callback.
- Result: `LocalPeerServerTests.testLocalPeerServerReportsDisconnectOnceWhenPeerClosesBeforeFrame` proves EOF before a frame on the local peer server emits one disconnect callback.
- Guardrail: the aggregate no-device gate now runs `swift test --filter TransportTests` and copy hygiene requires both direct transport disconnect regressions plus summary labels `macOS relay disconnect callback idempotency` and `macOS local peer disconnect callback idempotency`.
- Latest focused evidence: `swift test --filter TransportTests`, copy hygiene, and shell syntax checks passed after the transport idempotency patch.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after adding the transport idempotency regressions, including `TransportTests`, QR artifact generation, authenticated relay smoke, Android no-device tests, macOS localization/render/document/model/router tests, and hygiene checks.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Android Error Detail Boundary

- Scope: no-device Android JVM/Compose/script evidence for keeping normal user-facing error banners localized while preserving raw diagnostics separately; GPT-5.3-Codex-Spark was not used.
- Result: `RuntimeUiError` now has a separate `technicalDetail` field. Raw transport/runtime/parser/protocol messages are stored there instead of in the user-visible `detail` field.
- Result: the generic Chat error banner no longer renders raw safe-looking technical strings such as `relay timed out`; it keeps the localized error summary and still redacts endpoint/secret material.
- Result: attachment file names remain allowlisted user-visible detail for attachment size/read errors.
- Guardrail: copy hygiene now requires the `technicalDetail` field, `runtimeUiError(...)` factory, the allowlist, technical-detail assertions, and the no-device coverage label `Android runtime technical error detail storage boundary`.
- Latest focused evidence: Android ViewModel, AppNavigation, and Compose focused tests passed after the split, along with copy hygiene and shell syntax checks.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after the error-detail boundary update, including QR artifact generation, authenticated relay smoke, Android no-device ViewModel/Compose/JVM tests, macOS localization/render/document/model/router/transport tests, and hygiene checks.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack output, physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 macOS Pairing Connection Recovery Entry Point

- Scope: no-device macOS SwiftUI/source/XCTest/script evidence for preventing Pairing from dead-ending when QR generation requires remote route setup; GPT-5.3-Codex-Spark was not used.
- Result: Pairing now uses `shouldShowPairingRouteSetupPanel(model:)`, so a clean no-route Pairing view exposes Connection Recovery while Status still keeps route diagnostics hidden on a clean first run.
- Result: the Android empty-chat starter-prompt suggestion was deliberately not implemented because static examples were previously removed in favor of runtime-generated next-question suggestions after assistant output.
- Guardrail: copy hygiene now requires the Pairing-specific setup helper, the narrower Status diagnostics helper, and the regression `testRouteDiagnosticsPanelStaysHiddenOnCleanFirstRunButPairingExposesSetup`.
- Latest focused evidence: macOS Pairing/Status visibility regression, macOS five-language localization parity, Pairing/RemoteRelay render smoke across supported languages and appearances, and copy hygiene passed.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after the Pairing Connection Recovery entry point update, including Android no-device tests, macOS localization/render/document/model/router/transport tests, QR artifact generation, authenticated relay smoke, and hygiene checks.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Android Latest QR Empty-State Callback Routing

- Scope: no-device Android Compose evidence for the trusted-runtime QR refresh action in the empty chat recovery state; GPT-5.3-Codex-Spark was not used.
- Result: `ChatEmptyState` dispatches trusted-runtime route-refresh recovery clicks to `onScanLatestQr()` and keeps first-pairing QR clicks on `onScanPairingQr()`.
- Result: the route-unreachable, relay-auth-failed, and expired-route empty chat tests now assert that `Scan latest QR` triggers the latest-QR callback while the pairing callback stays idle.
- Guardrail: copy hygiene now requires the latest-QR empty-state callback split, the callback threading, and the callback-specific Compose assertions.
- Latest focused evidence: Android focused Compose tests for route recovery, relay auth failure, expired route, and expired-route five-language localization passed, followed by copy hygiene, docs hygiene, shell syntax, and whitespace checks.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after the latest-QR empty-state callback routing update, including QR artifact generation, authenticated relay smoke, Android no-device tests, macOS localization/render/document/model/router/transport tests, and hygiene checks.
- Caveat: the Android phone was disconnected, so this does not prove optical camera QR scanning, physical install, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Android Safe Runtime Technical Diagnostics Surface

- Scope: no-device Android Compose/script evidence for showing runtime/provider troubleshooting details without leaking backend endpoints or route secrets into normal chat error copy; GPT-5.3-Codex-Spark was not used.
- Result: generic runtime errors now keep the main error banner localized and safe, while a collapsed `Technical details` control exposes a redacted diagnostic report only when the user opens it.
- Result: `runtimeTechnicalDiagnosticsReport(...)` preserves valid `code` and `diagnostic_code` values, redacts backend endpoints, local backend API paths, route tokens, relay ids, and related route material from `technicalDetail`, then formats the report for display and copying.
- Result: `chatScreenTechnicalDiagnosticsAreCollapsedAndRedactUnsafeRuntimeDetails` proves the diagnostics surface starts collapsed, exposes expanded/collapsed accessibility state and click labels, copies through the localized diagnostics action, and never renders the raw unsafe technical detail.
- Guardrail: copy hygiene now requires the technical diagnostics surface, the redaction helper, the localized copy action, the focused Compose regression, and the no-device coverage label `Android safe runtime technical diagnostics surface`.
- Latest focused evidence: Android generic error accessibility/redaction and collapsed technical diagnostics Compose tests passed, followed by Android string parity, copy hygiene, docs hygiene, shell syntax, and whitespace checks.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after the diagnostics surface update, including QR artifact generation, authenticated mock relay E2E, Android no-device tests, macOS localization/render/document/model/router/transport tests, and hygiene checks.
- Caveat: the Android phone was disconnected, so this does not prove physical TalkBack output, clipboard behavior, physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Share Intake and Relay Framing Hardening

- Scope: no-device Android JVM evidence for share-sheet intake and route.refresh state hardening plus SwiftPM relay-server evidence for strict bootstrap line framing; GPT-5.3-Codex-Spark was not used.
- Result: Android share intents can stage text into the current chat draft and URI streams into pending attachments through the same attachment ingestion path used by the in-app picker. This keeps model access mediated by the runtime.
- Result: `routeRefreshAuthenticationRequiredDoesNotRetainRouteMaterialTechnicalDetail` proves secret-bearing route.refresh auth errors are reduced to a fixed safe technical detail and do not retain route token, relay id, relay secret, or nonce material in UI state.
- Result: `RelayServerLineFraming.decode(...)` rejects relay handshake/allocation lines that do not end with `\n`, while valid newline-terminated runtime and allocation lines still pass.
- Guardrail: copy hygiene now requires the Android share-sheet helper/tests, route.refresh sensitive-detail minimization, RelayServerCore newline framing coverage, and no-device coverage labels for all three.
- Latest focused evidence: Android share-intake and route.refresh sensitive-detail tests passed, and `swift test --filter RelayServerCoreTests` passed.
- Caveat: the Android phone was disconnected, so this does not prove physical share-sheet entry from real apps, physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Android Chat Surface Narrow-Phone Layout Regression

- Scope: no-device Android Compose evidence for screenshot-based client UI polish on the chat surface; GPT-5.3-Codex-Spark was not used.
- Result: `chatSurfaceRendersRepresentativeNarrowPhoneWithoutComposerOverlap` renders a 320dp-wide, 470dp-tall phone surface with the active chat title/model top bar, user message, assistant answer, collapsed reasoning preview, message attachment chip, suggested next-question chips, and bottom attach/message/send composer controls.
- Result: the regression uses visibility and bounds assertions to prove the suggested-question and message-attachment rows stay above the docked composer controls instead of adding pixel-perfect screenshot comparisons.
- Guardrail: `script/check_no_device_quality.sh` now runs the focused Compose regression, and `script/check_copy_hygiene.py` requires both the test and no-device coverage label.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after the narrow-phone layout regression update, including QR artifact generation, authenticated mock relay E2E, Android no-device tests, macOS localization/render/document/model/router/transport tests, and hygiene checks.
- Caveat: this is no-device Compose evidence only. It does not prove physical install, camera QR scanning, physical keyboard/IME behavior, physical haptics, pixel-perfect screenshots, live streamed chat/cancel, or actual different-network reachability.
## 2026-06-28 macOS Runtime Owner-Device History And Memory Scoping

- `swift test --filter 'LocalRuntimeMessageRouterTests/testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory|LocalRuntimeMessageRouterTests/testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreScopesEntriesByOwnerDevice'`
- Result: passed. Covered authenticated device isolation for runtime-owned memory list/injection, chat sessions/messages, rename/archive/delete denial across owners, legacy nil-owner compatibility, and same memory id per owner.
- Caveat: no-device SwiftPM evidence only. Not covered: physical Android install, optical QR scan, live local-model streaming/cancel behavior, or real different-network runtime connectivity.

## 2026-06-28 Android Archived Chat Composer Cleanup

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.startNewChatClearsNoActiveDraftButKeepsSessionDrafts --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveActiveChatClearsNoActiveDraftAndPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveAllChatsClearsNoActiveDraftAndPendingAttachments --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedDropsArchivedSessionComposerDrafts -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered the difference between starting a fresh chat, which keeps existing session-scoped drafts, and archiving chats, which clears no-active composer text, transient pending attachments, and archived session-scoped drafts.
- `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after this update.
- Latest aggregate evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh` passed after adding the archived-chat composer cleanup regressions. The gate summary includes `Android transient attachment cleanup on chat lifecycle exits`.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Android Runtime Transcript Loading State

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatComposerEditingRequiresTrustedConnectedUsableModel --tests com.localagentbridge.android.AppNavigationTest.chatComposerHintExplainsActiveTranscriptLoadingLockout --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openingRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsLocalizedLoadingStateWhileRuntimeTranscriptLoads -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered runtime-owned previous-chat opening, `chat.messages.list` loading state, composer/send lockout until transcript arrival, localized loading copy across English, Korean, Japanese, Simplified Chinese, and French, and polite live-region accessibility.
- `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, and `git diff --check` passed after this update.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-runtime-transcript-loading.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android runtime transcript loading state`.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 Android Runtime Transcript Lifecycle Mutation Lockout

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openingRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered runtime-owned previous-chat loading, composer/send lockout, and rename/archive/archive-all lifecycle mutation lockout until `chat.messages.list` returns.
- Guardrail: `script/check_no_device_quality.sh` summary now includes `Android runtime transcript lifecycle mutation lockout`, and `script/check_copy_hygiene.py` requires the source/test/no-device contract.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-lifecycle-redaction.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android runtime transcript lifecycle mutation lockout`.
- Caveat: the Android phone was disconnected, so this does not prove physical install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network reachability.

## 2026-06-28 macOS Route Material Diagnostic Redaction

- `swift test --filter AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactRouteSecrets`
- `swift test --filter AetherLinkLocalizationTests/testRouteDiagnosticDisclosureRedactsSensitiveDetails`
- `swift test --filter LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets`
- Result: passed. Covered Activity technical details, Connection Recovery route diagnostic disclosures, and companion log storage for `relay_secret`, `relaySecret`, `route_token`, `routeToken`, `relay_id`, `relayId`, `relay_nonce`, `relayNonce`, `allocation_token`, `allocationToken`, `rs`, `rt`, `ri`, and `rrn`.
- Guardrail: `script/check_no_device_quality.sh` now runs the focused redaction tests and includes `macOS route material diagnostic redaction`; `script/check_copy_hygiene.py` verifies the source/test/no-device contract.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-lifecycle-redaction.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `macOS route material diagnostic redaction`.
- Caveat: no-device SwiftPM evidence only. Not covered: live VoiceOver traversal, rendered macOS screenshots, optical QR scan, live different-network runtime connectivity, or physical model streaming/cancel.

## 2026-06-28 Android Pending Relay QR Secret-Store Boundary

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresPendingPairingRouteUntilShorterRelayExpiry --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRejectsIncompletePendingPairingRoute -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered retryable pending QR relay pairing, process-recreation restore, incomplete pending route rejection, and raw `relay_secret` removal from persisted runtime UI JSON in favor of a `relaySecretRef`.
- `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Guardrail: the default no-device gate now runs `RuntimeClientViewModelTest.persistedRuntimeDataStoresPendingPairingRouteUntilShorterRelayExpiry` and the summary includes `Android pending relay QR secret-store boundary`.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-pending-secret-boundary.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android pending relay QR secret-store boundary`.
- Caveat: the client device was disconnected, so this does not prove physical install, optical camera QR scanning, physical haptic feel, physical/live-backend streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 route.refresh Relay-Scope Enum Validation

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshRelayRouteToCurrentTrustedRuntime --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsUnknownRelayScope --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteRelayMaterial -Pkotlin.incremental=false --console=plain`
- `swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownRelayScopeFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshReturnsRetryableErrorWhenRuntimeHasNoRefreshableRoute'`
- Result: passed. Covered valid `remote` route-refresh material, macOS invalid-scope `route_refresh_unavailable`, Android rejection of unknown and whitespace-mutated `relay_scope`, and continued rejection of expired/incomplete relay material.
- Guardrail: the default no-device gate now runs `RuntimeClientViewModelTest.routeRefreshPayloadRejectsUnknownRelayScope` and `LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownRelayScopeFromRuntimeProvider`, and the summary includes `route.refresh relay-scope enum validation`.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-route-scope.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `route.refresh relay-scope enum validation`.
- Caveat: the client device was disconnected, so this does not prove physical install, optical camera QR scanning, physical haptic feel, physical/live-backend streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android Pending Relay QR Secret Cleanup

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRemovesPendingPairingRelaySecretWhenRouteClearsOrReplaces -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered pending relay QR secret-store cleanup when a pending route is cleared and when it is replaced by a new pending route.
- Guardrail: the default no-device gate now runs `RuntimeClientViewModelTest.persistedRuntimeDataRemovesPendingPairingRelaySecretWhenRouteClearsOrReplaces`, `script/check_copy_hygiene.py` verifies the source/test/no-device contract, and the no-device summary includes `Android pending relay QR secret cleanup`.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-pending-secret-cleanup.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android pending relay QR secret cleanup`.
- Caveat: the client device was disconnected, so this does not prove physical install, optical camera QR scanning, physical haptic feel, physical/live-backend streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android QR Trust Value Whitespace Guard

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :core:pairing:testDebugUnitTest --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest --tests com.localagentbridge.android.core.pairing.RuntimeIdentityProofVerifierTest --tests com.localagentbridge.android.core.pairing.DeviceIdentityStoreTest --tests com.localagentbridge.android.core.pairing.PairingStoreTest -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered QR parsing for trusted runtime identity, route material, device identity proof verification, device identity persistence, and trusted pairing-store cleanup regressions.
- New focused regression: `RuntimePairingPayloadParserTest.rejectsWhitespaceMutatedTrustAndRouteIdentityQrValues` proves whitespace-mutated `pairing_nonce`, `runtime_device_id`, `runtime_key_fingerprint`, `runtime_public_key`, `route_token`, `relay_id`, `relay_nonce`, and `relay_scope` fail before trust or route persistence.
- `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-qr-trust-value-whitespace.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android QR trust value whitespace guard`.
- Caveat: the client device was disconnected, so this does not prove physical install, optical camera QR scanning, physical haptic feel, physical/live-backend streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 macOS Trusted-Device Store File Permission Hardening

- `swift test --filter TrustedDeviceStoreTests`
- Result: passed. Covered `TrustedDeviceStore.trust(_:)` creating `trusted-devices.json` as `0600` in a `0700` directory, `load()` correcting broad legacy permissions without dropping trusted devices, and `remove(deviceID:)` preserving owner-only file permissions.
- `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-trusted-device-store-permissions.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `TrustedDeviceStoreTests` plus `macOS trusted-device store file permission hardening`.
- Caveat: no-device SwiftPM/source/script evidence only. Not covered: encrypted-at-rest trusted-device storage, tamper detection, rendered macOS trusted-device UI behavior, optical QR scanning, live device removal/reconnect, physical Android install, or actual different-network runtime connectivity.

## 2026-06-28 macOS Trusted-Device Removal Live-Session Revocation

- `swift test --filter LocalRuntimeMessageRouterTests/testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection`
- Result: passed. Covered a trusted device authenticating, successfully calling `models.list`, being removed from `TrustedDeviceStore`, then receiving `pairing_required` for the next command on the same still-open connection.
- `swift test --filter 'LocalRuntimeMessageRouterTests/testTrustedHelloAndAuthResponseAuthenticatesConnection|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsRawNonceSignature|LocalRuntimeMessageRouterTests/testConnectionDidCloseClearsAuthenticatedSession|LocalRuntimeMessageRouterTests/testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection'` passed after changing the runtime command gate to re-check stored trust.
- Guardrail: `script/check_no_device_quality.sh` now runs the live-session revocation regression and reports `macOS trusted-device removal live-session revocation`; `script/check_copy_hygiene.py` checks the source/test/no-device contract.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-trusted-device-revocation.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection` plus `macOS trusted-device removal live-session revocation`.
- Caveat: no-device SwiftPM/source/script evidence only. Not covered: rendered macOS trusted-device removal UI, live Android reconnect behavior after removal, optical QR scanning, physical Android install, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 macOS Pairing Trusted-Device Identity Validation

- `swift test --filter 'LocalRuntimeMessageRouterTests/testPairingRequestStoresTrustedDeviceAndReturnsAccepted|LocalRuntimeMessageRouterTests/testPairingRequestRejectsWhitespaceMutatedDeviceIdentityBeforeTrusting'`
- Result: passed. Covered accepted pairing with a real P-256 DER public-key fixture, rejection of whitespace-mutated device ids, whitespace-mutated public keys, non-Base64 public keys, and Base64 material that is not a P-256 DER key.
- Result: malformed identity returned `pairing_invalid_device_identity`, did not write a trusted-device record, and a later valid identity in the same active pairing session stored a normalized display name and the submitted public key.
- Guardrail: `script/check_no_device_quality.sh` now runs the pairing identity regression and reports `macOS pairing trusted-device identity validation`; `script/check_copy_hygiene.py` verifies the source/test/no-device contract.
- `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-pairing-identity-validation.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `testPairingRequestRejectsWhitespaceMutatedDeviceIdentityBeforeTrusting`, `testPairingRequestStoresTrustedDeviceAndReturnsAccepted`, and `macOS pairing trusted-device identity validation`.
- Caveat: no-device SwiftPM/source/script evidence only. Not covered: optical QR scanning, physical install, live client pairing, physical reconnect after pairing, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 macOS Connection Recovery Bootstrap Relay Removal

- `swift test --filter AetherLinkLocalizationTests/testConnectionRecoveryBootstrapRelayRemovalAccessibilityUsesSelectedLanguage`
- Result: passed. Covered the explicit bootstrap relay removal action, confirmation title/body, removal result, endpoint-specific accessibility label, fallback accessibility label, cancel label, and action hint across English, Korean, Japanese, Simplified Chinese, and French.
- Guardrail: `script/check_no_device_quality.sh` now reports `macOS Connection Recovery bootstrap relay removal accessibility labels`; `script/check_copy_hygiene.py` verifies the source/test/no-device contract.
- `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-bootstrap-relay-removal.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `testConnectionRecoveryBootstrapRelayRemovalAccessibilityUsesSelectedLanguage` plus `macOS Connection Recovery bootstrap relay removal accessibility labels`.
- Caveat: no-device SwiftUI/source/XCTest/script evidence only. Not covered: rendered click behavior, live VoiceOver traversal, optical QR scanning, physical install, live different-network routing, physical reconnect after pairing, or live streamed chat/cancel.

## 2026-06-28 macOS Connection Recovery Destructive Removal Hints

- `swift test --filter 'AetherLinkLocalizationTests/testRemoveSavedConnectionDetailsAccessibilityUsesSelectedLanguage|AetherLinkLocalizationTests/testConnectionRecoveryBootstrapRelayRemovalAccessibilityUsesSelectedLanguage'`
- Result: passed. Covered localized destructive removal hints for saved fallback connection details and saved bootstrap relay settings across English, Korean, Japanese, Simplified Chinese, and French.
- Result: the visible destructive buttons and the confirmation destructive actions now share the same hint helpers, and removing saved fallback connection details clears stale route diagnostics.
- Guardrail: `script/check_no_device_quality.sh` now reports `macOS Connection Recovery destructive removal action hints`; `script/check_macos_localization.py` and `script/check_copy_hygiene.py` verify the source/test/no-device contract.
- `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- `python3 script/check_docs_hygiene.py` passed after the QA/progress record update.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-destructive-removal-hints.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `macOS Connection Recovery destructive removal action hints`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device SwiftUI/source/XCTest/script evidence only. It does not prove rendered click behavior, live VoiceOver traversal, optical QR scanning, physical install, live different-network routing, physical reconnect after pairing, or live streamed chat/cancel.

## 2026-06-28 Android Connection Status Incomplete Relay Route Live Region

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusRouteNoticeForMissingRelaySecretIsLiveRegionAndScansLatestQr -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered the Connection Status route notice for a trusted runtime with relay host, port, id, expiry, and nonce but a missing relay secret.
- Result: the notice exposes `Refresh needed`, the localized `Scan latest QR` action, polite live-region semantics, the remote-route recovery copy, latest-QR callback routing, and primary-action haptic feedback.
- Guardrail: `script/check_no_device_quality.sh` now reports `Android connection status incomplete relay route live-region recovery`; `script/check_copy_hygiene.py` verifies the source/test/no-device contract.
- `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- `python3 script/check_docs_hygiene.py` passed after the QA/progress record update.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-incomplete-relay-live-region.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android connection status incomplete relay route live-region recovery`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device Compose/source/script evidence only. It does not prove physical TalkBack output, camera QR scanning, physical haptics, physical install, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 macOS Connection Recovery Bootstrap Allocation Token Warning

- `swift test --filter 'AetherLinkLocalizationTests/testConnectionRecoveryBootstrapAllocationTokenWarningUsesSelectedLanguage|AetherLinkLocalizationTests/testBootstrapRelayAllocationTokenWarningClassifiesNonLocalEndpoints|AetherLinkLocalizationTests/testConnectionRecoverySaveBootstrapRelayAccessibilityValueUsesSelectedLanguage'`
- Result: passed. Covered the non-local bootstrap relay allocation-token warning, missing-token accessibility value, Save Bootstrap Relay token-aware accessibility value, and local diagnostic endpoint exemptions.
- Result: the warning is localized across English, Korean, Japanese, Simplified Chinese, and French, and endpoint classification distinguishes remote hostnames/private remote addresses/public IPv6 candidates from loopback, `.local`, and link-local diagnostics.
- Guardrail: `script/check_no_device_quality.sh` now reports `macOS Connection Recovery bootstrap allocation token warning`; `script/check_macos_localization.py` and `script/check_copy_hygiene.py` verify the source/test/no-device contract.
- `python3 script/check_macos_localization.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-bootstrap-token-warning.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `testConnectionRecoveryBootstrapAllocationTokenWarningUsesSelectedLanguage`, `testBootstrapRelayAllocationTokenWarningClassifiesNonLocalEndpoints`, and `macOS Connection Recovery bootstrap allocation token warning`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device SwiftUI/source/XCTest/script evidence only. It does not prove rendered click behavior, live VoiceOver traversal, optical QR scanning, physical install, live different-network routing, physical reconnect after pairing, or live streamed chat/cancel.

## 2026-06-28 Android Composer Clear-Draft Localized State

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenClearDraftActionStateUsesSelectedLanguage -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered the chat composer clear-draft action across English, Korean, Japanese, Simplified Chinese, and French.
- Result: the button now exposes the localized `clear_draft_state_ready` state description together with the localized clear-draft label and click action label.
- Guardrail: `script/check_no_device_quality.sh` now reports `Android composer clear-draft localized state`; `script/check_copy_hygiene.py` verifies the source/test/no-device contract.
- `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-clear-draft-localized-state.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android composer clear-draft localized state`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device Compose/resource/script evidence only. It does not prove physical TalkBack output, physical haptic feel, physical Android install, camera QR scanning, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android Settings Panel Heading Semantics

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsScreenHeadersExposeHeadingSemanticsAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered the Settings heading surface across English, Korean, Japanese, Simplified Chinese, and French.
- Result: the expanded `Memory indexing model` and `Memory` in-panel titles now expose heading semantics, matching the existing Settings and Preferences panel heading behavior.
- Guardrail: `script/check_no_device_quality.sh` now reports `Android Settings panel heading semantics`; `script/check_copy_hygiene.py` verifies the source/test/no-device contract.
- `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-settings-panel-heading.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android Settings panel heading semantics`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device Compose/source/script evidence only. It does not prove physical TalkBack traversal, physical Android install, real device haptics, camera QR scanning, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android Explicit Share-Sheet MIME Scope

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered the attachment picker policy and share-intent draft parsing regressions.
- Result: the Android manifest now removes broad `application/*` share intake and lists the explicit supported application document MIME types instead, while keeping `text/*` and `image/*` entry points.
- Guardrail: `script/check_copy_hygiene.py` now blocks broad `application/*` manifest intake and requires representative explicit document MIME types. `script/check_no_device_quality.sh` now reports `Android explicit share-sheet MIME scope`.
- `python3 script/check_copy_hygiene.py`, `python3 script/check_android_string_parity.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-explicit-share-mime.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android explicit share-sheet MIME scope`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device manifest/JVM/source/script evidence only. It does not prove physical share-sheet integration from real apps, physical Android install, camera QR scanning, physical haptic feel, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android Message Follow-Up Action Localized States

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenFollowupMessageActionsExposeLocalizedStateAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered the latest assistant regenerate action and latest user-message draft reuse action across English, Korean, Japanese, Simplified Chinese, and French.
- Result: both compact message follow-up actions now expose localized state descriptions alongside localized content descriptions and click-action labels.
- Guardrail: `script/check_copy_hygiene.py` now requires the state-description resources, UI semantics, and Compose regression. `script/check_no_device_quality.sh` now reports `Android message follow-up action localized states`.
- `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-message-followup-states.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android message follow-up action localized states`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device Compose/resource/script evidence only. It does not prove physical TalkBack output, physical haptic feel, physical Android install, camera QR scanning, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android Localized Clipboard Payload Labels

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMessageCopyActionsExposeLocalizedActionLabels --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenCodeBlockCopyUsesLocalizedCodeActionLabels -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered message-copy and code-block copy actions after each click by checking the system clipboard description label.
- Result: message copy uses the localized `copy_message` label as the clipboard payload label, and code-block copy uses the localized code-block action label instead of a hardcoded app name.
- Guardrail: `script/check_copy_hygiene.py` blocks hardcoded `ClipData.newPlainText("AetherLink", ...)` and requires clipboard-label assertions. `script/check_no_device_quality.sh` now reports `Android localized clipboard payload labels`.
- `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-localized-clipboard-labels.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android localized clipboard payload labels`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device Compose/Robolectric/source/script evidence only. It does not prove physical Android clipboard UI, physical TalkBack output, physical haptic feel, physical Android install, camera QR scanning, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android Long-Press Clipboard Payload Coverage

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMessageCopyActionsExposeLocalizedActionLabels --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenCodeBlockCopyUsesLocalizedCodeActionLabels -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered both chat message copy entry points by invoking the long-press semantics action for the user message and the visible copy button for the assistant message.
- Result: the tests now wait for both clipboard payload label and copied text, so the long-press path cannot silently regress while visible copy buttons remain green.
- Guardrail: `script/check_copy_hygiene.py` now requires the long-press semantics invocation and clipboard label/text helper.
- Caveat: the Android phone was disconnected for this pass, so this is no-device Compose/Robolectric/source/script evidence only. It does not prove physical long-press behavior, physical Android clipboard UI, physical TalkBack output, physical haptic feel, physical Android install, camera QR scanning, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-28 Android Connected Action Reconnect Lockout

- `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusConnectedActionsDisableWhileConnectingAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain`
- Result: passed. Covered connected `Refresh health` and `Disconnect` actions while `isConnected=true` and `isConnecting=true`.
- Result: the actions remain visible but disabled, expose localized click-action labels, and reuse `connect_runtime_state_connecting` as the disabled state description across English, Korean, Japanese, Simplified Chinese, and French.
- Guardrail: `script/check_copy_hygiene.py` verifies the source/test/no-device contract. `script/check_no_device_quality.sh` now reports `Android connected action reconnect lockout`.
- `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed after adding the guardrails.
- Full no-device aggregate passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/check_no_device_quality.sh > /tmp/aetherlink-no-device-connected-action-lockout.log 2>&1`; the log ends with `No-device quality checks passed.` and includes `Android connected action reconnect lockout`.
- Caveat: the Android phone was disconnected for this pass, so this is no-device Compose/source/script evidence only. It does not prove physical TalkBack output, physical haptic feel, physical Android install, camera QR scanning, live streamed chat/cancel, or actual different-network runtime connectivity.

## 2026-06-29 Physical Android Relay QR Pairing, Chat, Cancel, Reconnect

- Device: `R3CXC0M76VM` / `SM-S936N`, connected over USB debugging and reported by adb as `device`.
- Installed current debug APK with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug --console=plain`.
- Physical relay smoke passed with `AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.iam7g8/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.iam7g8/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.iam7g8/aetherlink-chat-cancel-smoke.png`.
- Result: the smoke observed QR/deeplink pairing acceptance, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, `chat.done`, app force-stop/relaunch, a second `runtime.health`, and a refreshed model list after reconnect.
- Regression tests passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests 'com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAfterAcceptedRelayPairingDoesNotOpenDuplicateRelayConnection' --tests 'com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute' --tests 'com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeSchedulesRouteRefreshBeforeLeaseExpiry' --console=plain`.
- macOS runtime/relay build passed with `swift build --package-path apps/macos --product RuntimeDevServer --product AetherLinkRelay`.
- `git diff --check` passed.
- Caveat: this physical evidence uses a development relay exposed to the phone through `adb reverse`. It does not prove arbitrary non-USB, public internet, VPN, tunnel, or private-overlay reachability yet. Android still talks only to AetherLink Runtime/relay, never directly to Ollama or LM Studio.

## 2026-06-29 Physical Android Relay QR Duplicate Pairing Request Recovery

- Device: `R3CXC0M76VM` / `SM-S936N`, connected over USB debugging and reported by adb as `device`.
- Installed the current debug APK after the QR duplicate-request fix with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug --console=plain`.
- Physical relay smoke passed with `AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.YHHgr2/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.YHHgr2/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.YHHgr2/aetherlink-chat-cancel-smoke.png`.
- Result: the smoke observed QR/deeplink pairing acceptance, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done`.
- Result: Android logcat showed one duplicate QR path being skipped with `Skipping duplicate pairing.request for runtime=aetherlink-dev-runtime`; the runtime log received exactly one `pairing.request` before `runtime.health`.
- Regression tests passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.duplicateCompactRelayQrScanSendsSinglePairingRequestOnActiveRelayConnection --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAfterAcceptedRelayPairingDoesNotOpenDuplicateRelayConnection --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarShowsActiveChatTitleAndLocalizedFallback -Pkotlin.incremental=false --console=plain`.
- Caveat: this physical evidence uses a development relay exposed to the phone through `adb reverse`. It proves the Android app can pair and chat through the mediated AetherLink Runtime/relay path, but it does not prove arbitrary non-USB, public internet, VPN, tunnel, or production private-overlay reachability yet.

## 2026-06-29 Relay Allocation Fail-Closed Default And Short Lease

- Relay core tests passed with `swift test --filter RelayAllocationTests`.
- Relay executable build passed with `swift build --product AetherLinkRelay`.
- Result: `RelayServerConfiguration()` now defaults to `requiresAllocation = true` and a 15-minute allocation TTL.
- Result: `AetherLinkRelay` now rejects unknown or expired relay ids by default. Explicit `--allow-legacy` is required for old local diagnostics that intentionally accept arbitrary relay ids.
- Result: `AetherLinkRelay --allocation-ttl-seconds <seconds>` and `AETHERLINK_RELAY_ALLOCATION_TTL_SECONDS` provide explicit development TTL overrides.
- Script evidence: `script/run_allocation_relay.sh --dry-run` reported `Allocation required: yes`, while `script/run_allocation_relay.sh --allow-legacy --allocation-ttl-seconds 120 --dry-run` reported `Allocation required: no (--allow-legacy)` and `Allocation TTL: 120s`.
- CLI evidence: `swift run AetherLinkRelay --help` showed `--allow-legacy`, `--allocation-ttl-seconds`, allocation-required default wording, and the short-lived allocation-ticket warning.
- Hygiene evidence: `bash -n script/run_allocation_relay.sh script/no_adb_external_relay_pairing_smoke.sh script/run_different_network_dev_runtime.sh script/android_pairing_deeplink_smoke.sh`, `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed.
- Caveat: this is relay foundation hardening, not a full production private overlay. It does not prove public internet reachability, P2P NAT traversal, production TURN fallback, abuse controls, or production end-to-end session encryption.

## 2026-06-29 Reconnected Physical Android Relay QR Smoke

- Device: `R3CXC0M76VM` / `SM-S936N`, connected over USB debugging and reported by `/Users/hanchangha/Library/Android/sdk/platform-tools/adb devices -l` as `device`.
- Installed the current debug APK with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew :app:installDebug`.
- Physical relay smoke passed with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.5FvILY/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.5FvILY/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.5FvILY/aetherlink-chat-cancel-smoke.png`.
- Result: the smoke observed QR/deeplink pairing acceptance, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the physical Android UI.
- Caveat: this verification still uses local Mac processes and `adb reverse` for the development relay path. It confirms the mediated AetherLink Runtime/relay path on the attached phone, but it is not proof of arbitrary same-QR connectivity across public networks without USB, VPN, tunnel, or a production private overlay.

## 2026-06-29 macOS Runtime Data Summary Error Recovery

- Focused CompanionCore tests passed with `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesPreservesChatSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsPreservesMemorySummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryInspectorError|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeMemoryInspectorError'`.
- Result: a successful Runtime Memory inspector refresh now clears the memory-specific summary error instead of leaving the Status dashboard in a stale warning state.
- Result: a successful Runtime Chat History inspector refresh now clears the chat-specific summary error instead of leaving the Status dashboard in a stale warning state.
- Result: if the other runtime data domain is still failing, the summary warning remains attached to that remaining failure instead of being cleared too aggressively.
- Hygiene evidence: `python3 script/check_macos_localization.py`, `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed.

## 2026-06-29 Android Populated Settings Narrow-Phone Render

- Focused Compose test passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsHistoryAndMemoryRenderRepresentativeNarrowPhoneAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain`.
- Result: Android Settings now has a no-device regression that renders representative populated Chat history and Memory data on a 260dp-wide phone surface across English, Korean, Japanese, Simplified Chinese, and French.
- Result: the test expands Memory and Chat history in product order, proving active and paused memory rows plus active and archived chat rows remain reachable and visible with localized section titles.
- Guardrail: `script/check_no_device_quality.sh` now runs the focused render regression, and `script/check_copy_hygiene.py` requires both the test and the no-device coverage summary phrase.
- Hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_android_string_parity.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Caveat: this is no-device Compose/Robolectric render evidence. It does not prove physical TalkBack output, real device haptics, optical QR scanning, live backend chat/cancel, or production different-network runtime connectivity.

## 2026-06-29 no-device Gate Runtime Recovery Wiring

- Android runtime-owned chat mutation recovery test passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientChatSessionMutationFailureTest -Pkotlin.incremental=false --console=plain`.
- macOS Runtime Data recovery tests passed with `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesPreservesChatSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsPreservesMemorySummaryError'`.
- Result: the default no-device gate now directly runs the macOS Runtime Data summary error recovery regressions instead of relying only on focused evidence.
- Result: `script/check_copy_hygiene.py` now requires the no-device gate to keep both macOS recovery test filters and the `macOS runtime data summary error recovery` coverage summary.
- Hygiene evidence: `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Caveat: `RuntimeClientChatSessionMutationFailureTest.kt` is still an untracked file in Git status until it is staged by the user. The file exists and passes locally, but omitting it from the eventual commit would break the documented no-device gate.

## 2026-06-29 Android Runtime Data Load Error Surfacing

- Focused Android ViewModel tests passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeChatMessagesListErrorClearsLoadingAndShowsChatHistoryLoadFailed --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryErrorShowsLoadFailureAndAllowsRetry --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryErrorShowsFailureAndAllowsRetry -Pkotlin.incremental=false --console=plain`.
- Result: `chat.messages.list` error handling clears the active runtime-owned chat loading state and shows `chat_history_load_failed` while retaining the technical runtime detail outside the user-visible detail field.
- Result: `chat.sessions.list` and `memory.list` error handling now allow a later manual refresh to issue a fresh request after an error.
- Result: `memory_load_failed` is localized across the default Android resources plus English, Korean, Japanese, Simplified Chinese, and French.
- Hygiene evidence: `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Device evidence: `R3CXC0M76VM` / `SM-S936N` was connected as `device`; `./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the current debug APK successfully.
- Physical relay smoke passed with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.SHGluR/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.SHGluR/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.SHGluR/aetherlink-chat-cancel-smoke.png`.
- Result: the physical smoke observed QR/deeplink pairing, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the Android UI.
- Caveat: this remains a development relay proof through local Mac processes and `adb reverse`; it is not production arbitrary-network reachability.

## 2026-06-29 Android French Chat Accessibility Copy Polish

- French chat input accessibility now uses `Votre message` for the composer input.
- French attachment type copy now uses `Image jointe` and `Document joint` for attachment chip metadata and state descriptions.
- French assistant role copy now uses `Assistant IA` for message-row accessibility summaries.
- Guard evidence: `script/check_copy_hygiene.py` now rejects regressions for these French chat accessibility values in `values-fr/strings.xml`.
- No-device gate evidence: `script/check_no_device_quality.sh` now reports `Android French chat accessibility copy`, and copy hygiene requires that coverage phrase.
- Verification scope: no-device Android resource, Compose accessibility, copy hygiene, docs hygiene, and whitespace checks.
- Verified commands:
  - `python3 -m py_compile script/check_copy_hygiene.py`
  - `bash -n script/check_no_device_quality.sh`
  - `python3 script/check_copy_hygiene.py`
  - `python3 script/check_android_string_parity.py`
  - `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenSendButtonLocalizesReadinessStateAcrossSupportedLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenAttachmentSizeUsesSelectedAppLanguageContext --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMessageRowsExposeLocalizedRoleAccessibilitySummaries -Pkotlin.incremental=false --console=plain`
  - `python3 script/check_docs_hygiene.py`
  - `git diff --check`
- Caveat: this is no-device localized resource and Compose semantics evidence. It does not prove physical TalkBack pronunciation, physical rendered screenshots, optical QR scanning, live provider-backed chat, or production arbitrary-network connectivity.

## 2026-06-29 Memory-Indexing Locale Guard Expansion

- Guard evidence: `script/check_copy_hygiene.py` now rejects stale Android localized string values for memory-indexing model copy in Japanese (`埋め込み`), Simplified Chinese (`嵌入`), and French (`embedding`) without flagging `embedding_model_*` resource keys.
- Guard evidence: macOS localized values now reject Japanese `埋め込み` and Simplified Chinese `嵌入` in addition to the existing French `embedding` loanword check.
- Verification scope: no-device script, docs, and localization hygiene only.
- Verified commands:
  - `python3 -m py_compile script/check_copy_hygiene.py`
  - `python3 script/check_copy_hygiene.py`
  - `python3 script/check_docs_hygiene.py`
  - `python3 script/check_android_string_parity.py`
  - `python3 script/check_macos_localization.py`
  - `git diff --check`
- Caveat: this is localized resource guard evidence. It does not prove physical rendered UI, TalkBack or VoiceOver pronunciation, optical QR scanning, live provider-backed chat, or production arbitrary-network connectivity.

## 2026-06-29 Attached Phone Relay Smoke Refresh

- Device evidence: `/Users/hanchangha/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` / `SM-S936N` as `device`.
- Build evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:assembleDebug -Pkotlin.incremental=false --console=plain` passed.
- Install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the current debug APK on the attached phone.
- Physical relay smoke passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel --chat-delta-timeout 20`.
- Result: the physical UI smoke observed QR/deeplink pairing, `runtime.health`, persisted route reconnect after app relaunch, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.KSxghk/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.KSxghk/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.KSxghk/aetherlink-chat-cancel-smoke.png`.
- Caveat: no `AETHERLINK_BOOTSTRAP_RELAY_HOST` or related external relay environment was configured in this shell. This proof still uses local development relay processes plus `adb reverse`; it is not proof of arbitrary-network QR-only production reachability.

## 2026-06-29 Android Language And Model Guard, macOS Runtime QA Hardening

- Focused Android tests passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.requestModelInstallRejectsUnknownModelWithoutPersistingOrPulling -Pkotlin.incremental=false --console=plain`.
- Result: `shouldSynchronizeAndroidSystemAppLanguage(null, "en")` and blank current-language values now return false, so a first launch with no Android app-specific locale does not pin the app to English.
- Result: unknown model install requests reject with `select_chat_model` and do not persist the model id, set `installingModelId`, or send `models.pull`.
- Focused macOS Runtime Data filter passed with `swift test --package-path apps/macos --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryTranscriptPreviewAcrossOwners|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesPreservesChatSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsPreservesMemorySummaryError'`.
- Result: no-device coverage now runs the macOS all-owner runtime data summary and transcript preview tests that the coverage text reports.
- Result: `RuntimeDevServer` startup relay logging no longer prints the relay id; it logs host, port, and scope only.
- Hygiene evidence: `python3 script/check_android_string_parity.py`, `python3 script/check_macos_localization.py`, `python3 script/check_protocol_schema.py`, `python3 script/check_docs_hygiene.py`, `python3 script/check_copy_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Device evidence: `R3CXC0M76VM` / `SM-S936N` was connected as `device`; `./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the current debug APK successfully.
- Physical relay smoke passed with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.bLcEcx/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.bLcEcx/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.bLcEcx/aetherlink-chat-cancel-smoke.png`.
- Result: the physical smoke observed QR/deeplink pairing, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the Android UI.
- Caveat: this remains a local development relay proof through `adb reverse`, not arbitrary public-network production connectivity.

## 2026-06-29 Android Unknown Chat Model Selection Guard

- Focused Android tests passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectModelRejectsUnknownModelWithoutPersistingOrPulling --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.requestModelInstallRejectsUnknownModelWithoutPersistingOrPulling --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectModelRejectsProviderManagedOrUnknownSourceChatModelWithoutPersisting -Pkotlin.incremental=false --console=plain`.
- Result: selecting an absent chat model id now rejects with `select_chat_model`, keeps the previous selected model in UI state and local storage, keeps `installingModelId` null, and sends no `models.pull`.
- Guardrail evidence: `script/check_no_device_quality.sh` now includes `RuntimeClientViewModelTest.selectModelRejectsUnknownModelWithoutPersistingOrPulling`, and `script/check_copy_hygiene.py` requires the model-selection and model-install unknown-id regressions.
- Hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_android_string_parity.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Device evidence: `R3CXC0M76VM` / `SM-S936N` was connected as `device`; `./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the current debug APK successfully.
- Physical relay smoke passed with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.l4fPZm/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.l4fPZm/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.l4fPZm/aetherlink-chat-cancel-smoke.png`.
- Result: the physical smoke observed QR/deeplink pairing, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the Android UI.
- Caveat: this remains a local development relay proof through `adb reverse`, not arbitrary public-network production connectivity.

## 2026-06-29 Android Explicit In-App Language Sync Guard

- Focused Android tests passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.androidSystemAppLanguageSyncNormalizesCurrentAndSelectedTags --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelReconcilesSystemAppLanguageUntilInAppLanguageIsSelected --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.systemAppLanguageHelperDoesNotOverrideInAppLanguageSelection -Pkotlin.incremental=false --console=plain`.
- Result: `shouldSynchronizeAndroidSystemAppLanguage(null, "en")` and blank-current English remain false, preserving the fresh-install guard that avoids pinning default English into Android app-specific locales.
- Result: `shouldSynchronizeAndroidSystemAppLanguage(null, "ko")` and blank-current French now return true, so an explicit supported non-English in-app language selection can be written into Android 13+ `LocaleManager.applicationLocales`.
- Guardrail evidence: `script/check_copy_hygiene.py` now requires both the fresh-install English skip assertions and the explicit non-English sync assertions.
- Hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_android_string_parity.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Device evidence: `R3CXC0M76VM` / `SM-S936N` was connected as `device`; `./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the current debug APK successfully.
- Physical relay smoke passed with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.qbE1vf/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.qbE1vf/relay.log`.
- Screenshot from the passing pairing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.qbE1vf/aetherlink-pairing-smoke.png`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.qbE1vf/aetherlink-chat-cancel-smoke.png`.
- Result: the physical smoke observed QR/deeplink pairing, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the Android UI.
- Caveat: the JVM/helper evidence covers the language-sync decision. The physical smoke proves the mediated AetherLink Runtime/relay path on the attached phone, but it still uses local Mac processes plus `adb reverse`; it is not production arbitrary-network reachability and does not prove the Android Settings app language panel visually updated.

## 2026-06-29 Android Compact Chat Top-Bar Model Picker

- Focused Compose test passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerKeepsLongModelNamesCompact -Pkotlin.incremental=false --console=plain`.
- Result: the selected chat-model top-bar pill is capped at a compact width for long model names while retaining the full model name in the `Chat model picker` accessibility summary.
- Result: the compact pill leaves measurable width for the active chat title on a 320dp-wide surface.
- Guardrail evidence: `script/check_no_device_quality.sh` now includes `ClientScreensNoDeviceComposeTest.chatTopBarModelPickerKeepsLongModelNamesCompact`, and `script/check_copy_hygiene.py` requires both the test filter and the `Android chat top-bar compact long model name` coverage phrase.
- Hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Device evidence: `R3CXC0M76VM` / `SM-S936N` was connected as `device`; `./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the current debug APK successfully.
- Physical relay smoke passed with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.wmfgHp/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.wmfgHp/relay.log`.
- Screenshot from the passing pairing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.wmfgHp/aetherlink-pairing-smoke.png`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.wmfgHp/aetherlink-chat-cancel-smoke.png`.
- Result: the physical smoke observed QR/deeplink pairing, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the Android UI.
- Caveat: this visual proof still comes from a development relay smoke through local Mac processes and `adb reverse`; it is not production arbitrary-network reachability.

## 2026-06-29 Android Default Chat Title Top-Bar Suppression

- Focused Android tests passed with `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.AppNavigationTest.chatTopBarActiveTitleHidesOnlyUnprovenanceDefaultTitle --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarShowsNamedActiveChatTitleAndHidesDefaultNewChatFallback --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerKeepsLongModelNamesCompact --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedPreservesExplicitAndRuntimeGeneratedPromptTitles -Pkotlin.incremental=false --console=plain`.
- Result: the top bar hides only the unprovenance default active title, so a fresh/default chat no longer shows a redundant `New Chat` label next to the model picker.
- Result: manual and runtime-generated titles remain visible even if the title text is `New chat`; persisted title provenance is now mapped into `RuntimeChatSession`.
- Result: persisted session sanitization preserves manual/generated `New chat` titles instead of migrating them to the blank/default title.
- Guardrail evidence: `script/check_copy_hygiene.py` requires `chatTopBarActiveTitleHidesOnlyUnprovenanceDefaultTitle` and `chatTopBarShowsNamedActiveChatTitleAndHidesDefaultNewChatFallback`; `script/check_no_device_quality.sh` includes the renamed Compose top-bar title regression.
- Hygiene evidence: `python3 script/check_copy_hygiene.py`, `python3 script/check_docs_hygiene.py`, `bash -n script/check_no_device_quality.sh`, and `git diff --check` passed.
- Device evidence: `R3CXC0M76VM` / `SM-S936N` was connected as `device`; `./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the current debug APK successfully.
- Physical relay smoke passed with `PATH="/Users/hanchangha/Library/Android/sdk/platform-tools:$PATH" AETHERLINK_ANDROID_CHAT_DELTA_TIMEOUT_SECONDS=20 ./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.d6rp54/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.d6rp54/relay.log`.
- Screenshot from the passing pairing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.d6rp54/aetherlink-pairing-smoke.png`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.d6rp54/aetherlink-chat-cancel-smoke.png`.
- Result: the physical smoke observed QR/deeplink pairing, `runtime.health`, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the Android UI. The chat/cancel screenshot shows the default `New Chat` label removed from the top bar.
- Caveat: this visual proof still comes from a development relay smoke through local Mac processes and `adb reverse`; it is not production arbitrary-network reachability.

## 2026-06-29 Android Regenerate Error Localization And Physical Recheck

- Physical device evidence: `/Users/hanchangha/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` / `SM-S936N` as `device`.
- Build and install evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:assembleDebug :app:installDebug -Pkotlin.incremental=false --console=plain` passed and installed the debug APK on the attached phone.
- Physical relay smoke passed with `./script/android_pairing_deeplink_smoke.sh --relay --skip-install --expect-reconnect --expect-chat-cancel --chat-delta-timeout 20`.
- Runtime result: the physical smoke observed QR/deeplink pairing, `runtime.health`, persisted reconnect after relaunch, `models.list`, `chat.send`, streamed `chat.delta`, `chat.cancel`, and `chat.done` through the Android UI.
- Localization evidence: `python3 script/check_android_string_parity.py` passed after pinning `error_regenerate_unavailable` across default English, explicit English, Korean, Japanese, Simplified Chinese, and French.
- Copy hygiene evidence: `python3 script/check_copy_hygiene.py` passed after the regenerate-unavailable localization update.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.tHsj2s/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.tHsj2s/relay.log`.
- Screenshot from the passing chat/cancel run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.tHsj2s/aetherlink-chat-cancel-smoke.png`.
- Caveat: this remains a local development relay proof through local Mac processes and `adb reverse`; it is not production arbitrary-network QR-only reachability.

## 2026-06-29 macOS Runtime Inspector French Copy And Close Labels

- Localization evidence: `python3 script/check_macos_localization.py` passed after pinning French runtime inspector/model-list values and the new contextual close labels across all supported macOS app languages.
- XCTest evidence: `swift test --package-path apps/macos --filter 'AetherLinkLocalizationTests/testRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages|AetherLinkLocalizationTests/testRuntimeMemoryInspectorCopyLocalizesAcrossSupportedLanguages|AetherLinkLocalizationTests/testModelRowAccessibilityLabelUsesModelContext'` passed.
- Result: French model-row accessibility uses `Discussion` for chat model type, and French transcript preview uses `Assistant IA` for assistant role display.
- Result: Runtime History Inspector and Runtime Memory Inspector close buttons expose distinct accessibility labels while preserving the compact visible `Close` button text.
- Caveat: this is no-device macOS source/resource/XCTest/script evidence. It does not prove live VoiceOver pronunciation, rendered macOS UI capture, physical Android behavior, live provider-backed chat, or production arbitrary-network connectivity.

## 2026-06-29 Inspector Refresh Labels And Android Memory Refresh State

- macOS localization evidence: `python3 script/check_macos_localization.py` passed after adding contextual Runtime History Inspector and Runtime Memory Inspector refresh accessibility labels in all supported app languages.
- macOS XCTest evidence: `swift test --package-path apps/macos --filter 'AetherLinkLocalizationTests/testRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages|AetherLinkLocalizationTests/testRuntimeMemoryInspectorCopyLocalizesAcrossSupportedLanguages'` passed.
- macOS quick-action evidence: `swift test --package-path apps/macos --filter AetherLinkLocalizationTests/testQuickActionAccessibilityUsesSelectedLanguage` passed after adding a shared accessibility value and hint for `Refresh Runtime Data`.
- macOS history-inspector evidence: `swift test --package-path apps/macos --filter 'AetherLinkLocalizationTests/testRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages|AetherLinkLocalizationTests/testQuickActionAccessibilityUsesSelectedLanguage'` passed after adding title-specific transcript preview load labels and shared quick-action accessibility values for Runtime History and Runtime Memory inspection.
- Android localization evidence: `python3 script/check_android_string_parity.py` passed after pinning `memory_refresh_state_ready` across default English, explicit English, Korean, Japanese, Simplified Chinese, and French.
- Android Compose evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRefreshActionFollowsConnectionStateAcrossSupportedLanguages -Pkotlin.incremental=false --console=plain` passed.
- Result: macOS inspector refresh controls, macOS runtime quick actions, transcript preview load controls, and Android memory refresh controls now announce contextual action/state copy instead of relying on generic or repeated button names.
- Caveat: this is no-device source/resource/XCTest/Robolectric/script evidence. It does not prove live VoiceOver or TalkBack pronunciation, physical Android rendering, live provider-backed chat, or production arbitrary-network connectivity.

## 2026-06-29 Android Embedding Model Accessibility And macOS QR Recovery State

- Android string parity evidence: `python3 script/check_android_string_parity.py` passed after adding localized `embedding_model_state_install_before_selecting` across default English, explicit English, Korean, Japanese, Simplified Chinese, and French.
- Android Compose evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelRowsExposeSelectedStateToAccessibility -Pkotlin.incremental=false --console=plain` passed.
- Android physical evidence: `/Users/hanchangha/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` / `SM-S936N` as `device`; `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the debug APK successfully.
- Android relay smoke evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ADB="$HOME/Library/Android/sdk/platform-tools/adb" ./script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect` passed and observed a second `runtime.health` after app relaunch.
- Result: uninstalled memory-indexing models remain disabled, but TalkBack semantics now explain that the model must be installed in AetherLink Runtime before selection instead of using the generic streaming-disabled state.
- macOS localization evidence: `python3 -m py_compile script/check_macos_localization.py`, `python3 script/check_macos_localization.py`, and `git diff --check` passed after splitting the Generate Latest QR accessibility value into ready, missing-action, and route-not-ready states.
- macOS XCTest evidence: `swift test --package-path apps/macos --filter AetherLinkLocalizationTests/testConnectionRecoveryGenerateLatestQRActionAccessibilityUsesSelectedLanguage` passed.
- Result: the Connection Recovery `Generate Latest QR` button now reports `Connection details not ready` when route material is not QR-ready, while still reporting `Unavailable` only when QR generation is unavailable from that view.
- Caveat: the physical Android relay smoke still uses development relay processes plus `adb reverse`; it proves the mediated relay/deeplink/reconnect path on the attached phone, not production arbitrary-network QR-only reachability.

## 2026-06-29 Android Pairing-First Onboarding And Drawer Search Trimmed Accessibility

- Android focused evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:testDebugUnitTest --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsLanguagePickerStaysInPreferencesAfterPairingFirstAcrossLaunchLanguages --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerChatSearchFiltersClearsAndUsesHapticFeedback -Pkotlin.incremental=false --console=plain` passed.
- Android string/copy evidence: `python3 script/check_android_string_parity.py`, `python3 script/check_copy_hygiene.py`, and `git diff --check` passed after the onboarding/search patch.
- Android physical evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./gradlew --no-daemon :app:installDebug -Pkotlin.incremental=false --console=plain` installed the debug APK on `R3CXC0M76VM` / `SM-S936N`; after `pm clear`, the first screen showed `Pair AetherLink`, `Scan Pairing QR`, and `Scan QR` without the language selector above pairing.
- Screenshot evidence: `/tmp/aetherlink-pairing-first.png`.
- Result: first-run Settings now leads with QR pairing, while language selection remains available from Preferences instead of occupying the first viewport.
- Result: the navigation drawer chat-search clear action trims leading/trailing whitespace in its accessibility label, so a padded query such as `  missing  ` is announced as `Clear chat search for missing`.
- Caveat: the physical evidence covers first-run UI layout on the attached debug device. It does not prove production arbitrary-network QR-only connectivity or live provider-backed chat.

## 2026-06-29 Physical Android Recheck And macOS Trusted Devices List Accessibility

- Android device evidence: `/Users/hanchangha/Library/Android/sdk/platform-tools/adb devices -l` reported `R3CXC0M76VM` / `SM-S936N` as `device`.
- Android relay smoke evidence: `JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ANDROID_HOME="$HOME/Library/Android/sdk" ./script/android_pairing_deeplink_smoke.sh --relay --expect-reconnect` passed. The run installed the current debug APK, injected the pairing URI, relaunched the app, and observed a second `runtime.health`.
- Runtime log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.N1VME8/runtime.log`.
- Relay log from the passing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.N1VME8/relay.log`.
- Screenshot from the passing pairing run: `/var/folders/n2/vgx0vf052yl248_8cff1xt2r0000gn/T//aetherlink-android-pairing.N1VME8/aetherlink-pairing-smoke.png`.
- Android first-run evidence: after `pm clear`, `adb shell monkey -p com.localagentbridge.android -c android.intent.category.LAUNCHER 1` launched to the QR pairing-first screen. Screenshot: `/tmp/aetherlink-clean-first-run.png`.
- macOS XCTest evidence: `swift test --package-path apps/macos --filter AetherLinkLocalizationTests/testTrustedDeviceListAccessibilityUsesSelectedLanguage` passed.
- macOS localization evidence: `python3 script/check_macos_localization.py` passed.
- Android localization evidence: `python3 script/check_android_string_parity.py` passed.
- Result: the macOS Trusted Devices list now provides localized list-level accessibility context and count value when trusted devices are present.
- Caveat: this Android proof still uses development relay processes plus `adb reverse`; it is not production arbitrary-network QR-only reachability.
