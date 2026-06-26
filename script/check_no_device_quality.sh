#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEFAULT_JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export JAVA_HOME="${JAVA_HOME:-$DEFAULT_JAVA_HOME}"
TEMP_DIRS=()

cleanup_temp_dirs() {
  local temp_dir
  for temp_dir in "${TEMP_DIRS[@]}"; do
    if [[ -d "$temp_dir" && "$(basename "$temp_dir")" == aetherlink-no-device-qr.* ]]; then
      rm -rf "$temp_dir"
    fi
  done
}

trap cleanup_temp_dirs EXIT

run() {
  echo
  echo "==> $*"
  "$@"
}

check_legacy_relay_guard() {
  local output
  local status_code
  set +e
  output="$(python3 script/aetherlink_relay.py --host 127.0.0.1 --port 1 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Legacy Python relay guard should exit 2 without --allow-legacy-no-allocation, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"does not support allocation leases required by QR pairing"* ]]; then
    echo "Legacy Python relay guard did not explain the allocation-lease limitation." >&2
    echo "$output" >&2
    exit 1
  fi
}

free_tcp_port() {
  python3 - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
}

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "JAVA_HOME does not point to a runnable JDK: $JAVA_HOME" >&2
  echo "Set JAVA_HOME or install Android Studio's bundled JBR before running this check." >&2
  exit 1
fi

run python3 -m py_compile \
  script/check_android_string_parity.py \
  script/check_macos_localization.py \
  script/check_protocol_schema.py \
  script/check_copy_hygiene.py \
  script/check_docs_hygiene.py \
  script/check_license.py \
  script/check_app_icons.py \
  script/aetherlink_relay.py

run bash -n script/*.sh
run check_legacy_relay_guard
run git diff --check

run python3 script/check_android_string_parity.py
run python3 script/check_macos_localization.py
run python3 script/check_protocol_schema.py
run python3 script/check_copy_hygiene.py
run python3 script/check_docs_hygiene.py
run python3 script/check_license.py
run python3 script/check_app_icons.py

QR_SMOKE_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-no-device-qr.XXXXXX")"
TEMP_DIRS+=("$QR_SMOKE_WORK_DIR")
QR_SMOKE_RELAY_PORT="$(free_tcp_port)"
run ./script/no_adb_external_relay_pairing_smoke.sh \
  --relay-host 127.0.0.1 \
  --relay-port "$QR_SMOKE_RELAY_PORT" \
  --start-local-relay \
  --emit-only \
  --timeout 30 \
  --work-dir "$QR_SMOKE_WORK_DIR"
run ./script/verify_pairing_qr.swift \
  --image "$QR_SMOKE_WORK_DIR/pairing-qr.png" \
  --expected "$QR_SMOKE_WORK_DIR/pairing-uri.txt" \
  --require-relay-route \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  >/dev/null

run ./gradlew --no-daemon \
  :core:pairing:testDebugUnitTest \
  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest \
  --tests com.localagentbridge.android.core.pairing.PairingStoreTest \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
  :core:protocol:testDebugUnitTest \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
  :core:transport:testDebugUnitTest \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparationTest \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
	  :app:compileDebugKotlin \
	  :app:testDebugUnitTest \
	  --tests com.localagentbridge.android.AppNavigationTest \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayRestoreMarksConnectingBeforeRelayDialCompletes \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelAutoReconnectsTrustedRelayOnInitAndRefreshesRuntimeState \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayReconnectAttemptsRelayBeforeMatchingBonjourFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromMacosPrivateOverlayQrConnectsRelayAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.releasePairingParserRejectsMacosLocalDiagnosticQrRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectedModelSendStateRejectsEmbeddingModelAsChatModel \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectEmbeddingModelRejectsUninstalledRuntimeModelWithoutChangingSelection \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsPersistedSelectionsWhileModelListIsRestoring \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsMissingPersistedSelectionsTypedAcrossRefresh \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsSelectionsWhenRefreshedModelHasWrongKind \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationClearsEmbeddingSelectionWhenModelIsNotInstalled \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelSelectionReconciliationKeepsExplicitEmbeddingSelection \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.modelKindNormalizationSeparatesChatAndEmbeddingModels \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.embeddingCapabilityPreventsModelFromBeingTreatedAsChat \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresSelectedChatAndEmbeddingModelsSeparately \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataCanClearSelectedEmbeddingModel \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateBuildsAfterFirstCompletedExchange \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatTitleRequestCandidateRejectsUnsafeOrAlreadyTitledSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.newPersistedMessagesDoNotUseFirstUserPromptAsTitle \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedMigratesLegacyPromptTitleToDefaultTitle \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedPreservesExplicitAndRuntimeGeneratedPromptTitles \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.generatedChatTitleAppliesOnlyUntilUserRenamesSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionsAttachToLatestAssistantMessage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateRefreshesRuntimeHistoryWhenLatestAssistantHasNoSuggestions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateUsesEnglishWhenLanguagePreferenceIsLegacyBlank \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateDoesNotRefreshRuntimeHistoryWhenSuggestionsAlreadyExist \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSuggestionCandidateSkipsBlankAssistantPlaceholder \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotRedactsArchivedRuntimeOwnedBodiesButKeepsLocalArchivedBodies \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteRequiresArchivedChatSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveAllChatSessionsRetainsSessionsAsArchivedAndKeepsMemoryCandidatesEmpty \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsDoesNotDeleteActivePreviousChats \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsSuppressesOnlyRuntimeOwnedArchivedSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMessagesReplaceSessionTranscriptAndPreserveReasoningWithStableIds \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlySendUsesSelectedLanguagePromptInChatSendPayload \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentSendAttachesMetadataOnlyToFinalUserPayloadMessage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.imageAttachmentSendRequiresVisionModelAndKeepsPendingAttachmentsWhenBlocked \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.validAttachmentSendClearsPendingAttachmentsAndRetainsReadonlyMessageChips \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.removePendingAttachmentDropsOnlySelectedAttachmentAndClearsError \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.blankMessageWithoutAttachmentsDoesNotSend \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsStopsBeforeReadingReportedOversizeFile \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsKeepsAtMostFourPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsWithExistingPendingAttachmentsReadsOnlyRemainingSlotsAndShowsLimit \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSendMessagesPrependsCapabilityGuardAndOnlyEnabledMemoryAsSystemContext \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryEntriesReplaceAndMutateCachedMemory \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.clientCapabilitiesAdvertiseRuntimeOwnedHistoryMemoryAndAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.thinkingDeltaAliasAppendsReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.inlineThinkTagsAreSeparatedFromAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkTagsKeepReasoningCollapsedOutOfAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkOpeningTagAcrossDeltasDoesNotLeakTagToAnswer \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkClosingTagAcrossDeltasDoesNotLeakTagToReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.incompleteInlineThinkTagPlaceholderIsClearedOnDone \
  -Pkotlin.incremental=false

run swift build --product AetherLink
run swift test --filter AetherLinkLocalizationTests
run swift test --filter AetherLinkRenderSmokeTests
run swift test --filter DocumentTextExtractorTests
run swift test --filter 'OllamaBackendTests/testListModelsUsesShowCapabilitiesToSeparateEmbeddingModels|LMStudioBackendTests/testListModelsParsesNativeLocalLLMAndEmbeddingModelsSeparately|LMStudioBackendTests/testListModelsFallsBackToOpenAICompatibleModels|AggregatingLlmBackendResidencyTests/testInstalledEmbeddingModelIsNotRoutedAsChat'
run swift test --filter 'LocalRuntimeMessageRouterTests/testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment|LocalRuntimeMessageRouterTests/testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment|LocalRuntimeMessageRouterTests/testChatSendImageAttachmentRequiresVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendAllowsLMStudioImageAttachmentsForVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendUnsupportedDocumentAttachmentReturnsStructuredError|LocalRuntimeMessageRouterTests/testChatSendRoutesQualifiedLMStudioModelThroughAggregateBackend'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial|LocalRuntimeMessageRouterTests/testChatSendStoresRuntimeSideProcessingEvents|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore|LocalRuntimeMessageRouterTests/testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle|LocalRuntimeMessageRouterTests/testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testRuntimeMemoryMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testChatSendStreamsReasoningDeltaSeparatelyFromAnswerDelta|LocalRuntimeMessageRouterTests/testChatSendSplitsInlineThinkTagsBeforeStreamingAnswer|LocalRuntimeMessageRouterTests/testChatSendInstalledEmbeddingModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse|LocalRuntimeMessageRouterTests/testChatSendGeneratedRuntimeTitleStripsInlineThinking|LocalRuntimeMessageRouterTests/testChatSendTitleGenerationUsesDeterministicFallbackWhenBackendTitleIsInvalid|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsStructuredSuggestions|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestAcceptsFencedStructuredSuggestions|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsEmptySuggestionsForInvalidJSON|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestFallsBackToNumberedLocalizedList'

echo
echo "No-device quality checks passed."
echo "Covered: local emit-only pairing QR artifact generation, QR PNG decode, canonical pairing URI policy, QR candidate structured-error routing, public relay remote-scope QR contract, private-overlay relay scope schema guard, release-mode diagnostic direct-route rejection, relay-route payload validation, relay preparation host eligibility guard, expired relay lease reconnect guard, cross-network QR readiness copy, diagnostic QR text fallback copy, macOS first-launch pairing priority, legacy Python relay allocation-guard, Android no-device Compose screen smoke with five-language pairing copy, Settings diagnostic endpoint visibility guard, chat history bulk action hiding and two-step confirmation, full five-language light/dark Chat/Settings layout matrix, reasoning toggle, chat top-bar model/embedding picker separation, and fake haptic callback dispatch, pending relay QR retry, relay-before-Bonjour fallback, and trusted relay app-init auto-reconnect."
echo "Not covered: physical install, camera QR scan, real device haptics, launcher/Dock screenshots, real streamed chat/cancel, and different-network runtime connectivity."
