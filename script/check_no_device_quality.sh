#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DEFAULT_JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export JAVA_HOME="${JAVA_HOME:-$DEFAULT_JAVA_HOME}"
TEMP_DIRS=()

cleanup_temp_dirs() {
  local temp_dir
  set +u
  for temp_dir in "${TEMP_DIRS[@]}"; do
    if [[ -d "$temp_dir" && "$(basename "$temp_dir")" == aetherlink-no-device-qr.* ]]; then
      rm -rf "$temp_dir"
    fi
  done
  set -u
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

check_link_local_relay_guard() {
  local output
  local summary_path
  local status_code

  summary_path="$(mktemp "${TMPDIR:-/tmp}/aetherlink-link-local-summary.XXXXXX")"
  set +e
  output="$(script/run_different_network_dev_runtime.sh --relay-host 169.254.10.20 --relay-port 43171 --allow-private-relay --preflight-only --summary-json "$summary_path" 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Different-network runtime preflight should reject link-local relay hosts even with --allow-private-relay, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"link-local and multicast addresses cannot be used as QR relay routes"* ]]; then
    echo "Different-network runtime preflight did not explain the link-local relay limitation." >&2
    echo "$output" >&2
    exit 1
  fi
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
assert summary["exit_status"] == 2, summary
assert summary["relay"]["endpoints"][0]["host"] == "169.254.10.20", summary
assert "relay_bootstrap_preflight_failed" in summary["caveats"], summary
assert "link-local" in summary["failure_detail"], summary
PY
  rm -f "$summary_path"

  set +e
  output="$(script/no_adb_external_relay_pairing_smoke.sh --relay-host 169.254.10.20 --relay-port 43171 --allow-private-relay --emit-only 2>&1 >/dev/null)"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "No-ADB QR smoke should reject link-local relay hosts even with --allow-private-relay, got $status_code" >&2
    echo "$output" >&2
    exit 1
  fi
  if [[ "$output" != *"private, link-local, CGNAT, loopback, and multicast IP literals are invalid"* ]]; then
    echo "No-ADB QR smoke did not explain the link-local relay limitation." >&2
    echo "$output" >&2
    exit 1
  fi
}

check_different_network_preflight_summary_guard() {
  local port
  local summary_path

  port="$(free_tcp_port)"
  summary_path="$(mktemp "${TMPDIR:-/tmp}/aetherlink-runtime-preflight-summary.XXXXXX")"
  script/run_different_network_dev_runtime.sh \
    --relay-host 127.0.0.1 \
    --relay-port "$port" \
    --start-local-relay \
    --preflight-only \
    --summary-json "$summary_path" \
    >/dev/null
  python3 - "$summary_path" "$port" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
port = int(sys.argv[2])
assert summary["exit_status"] == 0, summary
assert summary["mode"]["preflight_only"] is True, summary
assert summary["relay"]["success_endpoint"] == f"127.0.0.1:{port}", summary
assert summary["relay"]["start_local_relay"] is True, summary
assert summary["allocation"]["required_fields_present"] is True, summary
assert summary["allocation"]["preflight_non_persistent"] is True, summary
assert "runtime_host_preflight_only_not_phone_reachability_proof" in summary["caveats"], summary
assert "local_relay_only_unless_advertised_host_is_public_vpn_tunnel_or_overlay" in summary["caveats"], summary
PY
  rm -f "$summary_path"
}

check_relay_preflight_allocation_guard() {
  local relay_bin
  local port
  local work_dir
  local store
  local relay_pid

  swift build --product AetherLinkRelay >/dev/null
  relay_bin="$(swift build --show-bin-path)/AetherLinkRelay"
  port="$(free_tcp_port)"
  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-relay-preflight.XXXXXX")"
  store="$work_dir/allocations.json"
  relay_pid=""

  "$relay_bin" \
    --host 127.0.0.1 \
    --port "$port" \
    --require-allocation \
    --allocation-store "$store" \
    >"$work_dir/relay.log" 2>&1 &
  relay_pid="$!"

  set +e
  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token preflight-route \
    --quiet
  local preflight_status=$?
  sleep 0.2
  python3 - "$store" <<'PY'
import sys
from pathlib import Path

store = Path(sys.argv[1])
contents = store.read_text(encoding="utf-8") if store.exists() else ""
assert "preflight-route" not in contents, contents
PY
  local preflight_store_status=$?
  python3 script/relay_allocation_preflight.py \
    --host 127.0.0.1 \
    --port "$port" \
    --route-token normal-route \
    --persist \
    --quiet
  local normal_status=$?
  sleep 0.2
  python3 - "$store" <<'PY'
import sys
from pathlib import Path

contents = Path(sys.argv[1]).read_text(encoding="utf-8")
assert "normal-route" in contents, contents
assert "preflight-route" not in contents, contents
PY
  local normal_store_status=$?
  local status_code=$?
  set -e
  if [[ "$preflight_status" -ne 0 ]]; then
    status_code="$preflight_status"
  elif [[ "$preflight_store_status" -ne 0 ]]; then
    status_code="$preflight_store_status"
  elif [[ "$normal_status" -ne 0 ]]; then
    status_code="$normal_status"
  else
    status_code="$normal_store_status"
  fi

  if [[ -n "$relay_pid" ]]; then
    kill "$relay_pid" >/dev/null 2>&1 || true
    wait "$relay_pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$work_dir"
  return "$status_code"
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
  script/relay_allocation_preflight.py \
  script/aetherlink_relay.py

run bash -n script/*.sh
run check_legacy_relay_guard
run check_link_local_relay_guard
run check_different_network_preflight_summary_guard
run check_relay_preflight_allocation_guard
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
run ./script/runtime_authenticated_mock_smoke.swift --relay

run ./gradlew --no-daemon \
  :core:pairing:testDebugUnitTest \
  --tests com.localagentbridge.android.core.pairing.RuntimePairingPayloadParserTest \
  --tests com.localagentbridge.android.core.pairing.RuntimeIdentityProofVerifierTest \
  --tests com.localagentbridge.android.core.pairing.DeviceIdentityStoreTest \
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
	  --tests com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest \
	  --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerSearchMatchesModelAndRuntimeMetadata \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerDisabledItemsExplainStreamingLockoutAcrossSupportedLanguages \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryShowsSavedMissingModelRecovery \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerShowsSavedMissingChatModelRecovery \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarShowsActiveChatTitleAndLocalizedFallback \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeLocalizedModelMetadata \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatSurfaceRendersRepresentativeNarrowPhoneWithoutComposerOverlap \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.parseMessageContentPreservesCodeBlocksAndNormalizesMarkdownTextBlocks \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRendersMarkdownListsAndInlineCode \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingSuggestedQuestionChipsAreDisabledAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsRegenerateActionOnlyForLatestAssistantAndHidesWhileStreaming \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsReuseDraftActionOnlyForLatestEligibleUserMessage \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenFollowupMessageActionsExposeLocalizedStateAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenClearDraftActionClearsComposerAndHidesWhileStreaming \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsLocalizedLoadingStateWhileRuntimeTranscriptLoads \
	  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusConnectedActionsDisableWhileConnectingAcrossSupportedLanguages \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayRestoreMarksConnectingBeforeRelayDialCompletes \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelAutoReconnectsTrustedRelayOnInitAndRefreshesRuntimeState \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRestoreDoesNotStartDiscoveryWhenRelayRouteIsAvailable \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayReconnectAttemptsRelayBeforeMatchingBonjourFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.compactRelayQrPairingUsesRealRelayTcpClientAndPersistsTrustedRelay \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.privateOverlayRelayQrPairingUsesRealRelayTcpClientAndPersistsOverlayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.freshCompactRelayQrRefreshesExpiredTrustedRelayRouteAndReconnectsViaRelay \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.invalidPairingQrDoesNotEnableTrustedRuntimeAutoReconnect \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.identityOnlyPairingQrTimesOutWhenNoDiscoveryRouteAppears \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromMacosPrivateOverlayQrConnectsRelayAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresPendingPairingRouteUntilShorterRelayExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRemovesPendingPairingRelaySecretWhenRouteClearsOrReplaces \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.releasePairingParserRejectsMacosLocalDiagnosticQrRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectedModelSendStateRejectsEmbeddingModelAsChatModel \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.updateChatInputRejectsWhileStreamingAndPreservesDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksModelSelectionAndInstallRequests \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksReentrantChatSendRequests \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksMemoryMutations \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksRuntimeRouteTrustAndConnectionMutations \
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
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.useSuggestedQuestionFillsComposerWithoutSending \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.useSuggestedQuestionRejectsWhileStreamingAndPreservesDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedComposerDraftRestoresOnViewModelCreationAndUpdatesWithTyping \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openPreviousChatRestoresSessionScopedComposerDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.startNewChatClearsNoActiveDraftButKeepsSessionDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveActiveChatClearsNoActiveDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveAllChatsClearsNoActiveDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openingRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sendChatMessageClearsOnlyActiveSessionComposerDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.useSuggestedQuestionUpdatesActiveSessionComposerDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedCapsSessionScopedComposerDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sanitizedDropsArchivedSessionComposerDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sendChatMessageClearsPersistedComposerDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.regenerateLatestResponseExcludesOldAssistantFromPayloadAndHistory \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.regenerateLatestResponsePreservesComposerDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.regenerateLatestResponseBlocksAttachmentBackedPriorPrompt \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.reuseLatestUserMessageAsDraftCopiesLatestTextWithoutSendingOrMutatingHistory \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.reuseLatestUserMessageAsDraftRejectsAttachmentBackedPromptAndPreservesDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.reuseLatestUserMessageAsDraftRejectsWhileStreamingAndPreservesDraft \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotRedactsArchivedRuntimeOwnedBodiesButKeepsLocalArchivedBodies \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteRequiresArchivedChatSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveAllChatSessionsRetainsSessionsAsArchivedAndKeepsMemoryCandidatesEmpty \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsDoesNotDeleteActivePreviousChats \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.permanentDeleteArchivedChatSessionsSuppressesOnlyRuntimeOwnedArchivedSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMessagesReplaceSessionTranscriptAndPreserveReasoningWithStableIds \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMessagesDoNotResurrectSessionMissingFromLatestRuntimeSummary \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingRuntimeOwnedChatRendersInMemoryButRedactsDeviceStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryListRendersInMemoryButRedactsDeviceStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotDropsRuntimeOwnedDataButKeepsLocalDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeLifecycleAckDoesNotMutateLocalOnlySessionWithSameId \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsMismatchedRuntimeIdentity \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsUnknownRelayScope \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrWithoutPublicKeyCanRefreshPinnedRuntimeRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrDropsUnreachableRelayRouteAndRequiresFreshQrRecovery \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayReceiveAuthenticationFailureClearsStoredRelayAndStopsAutoReconnect \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeMarksRouteExpiredWhenRefreshErrorCannotRetryBeforeLeaseExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshAuthenticationRequiredDoesNotRetainRouteMaterialTechnicalDetail \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRejectedRouteRefreshPayloadBeforeLeaseExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeConnectionFailureMapsRouteMissingReasonsToFocusedUiErrors \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeCompletionCancellationAndErrorRemoveOnlyBlankAssistantPlaceholder \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeReceiveFailureClearsStreamingAndRemovesOnlyBlankAssistantPlaceholder \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeAuthenticationErrorTransitionsToPairingRequiredState \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelReconcilesSystemAppLanguageUntilInAppLanguageIsSelected \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.systemAppLanguageHelperDoesNotOverrideInAppLanguageSelection \
  --tests com.localagentbridge.android.runtime.RuntimeAttachmentPromptResourceTest.attachmentOnlyPromptHeaderUsesLocalizedAndroidResources \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentOnlySendUsesSelectedLanguagePromptInChatSendPayload \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.attachmentSendAttachesMetadataOnlyToFinalUserPayloadMessage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.imageAttachmentSendRequiresVisionModelAndKeepsPendingAttachmentsWhenBlocked \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.validAttachmentSendClearsPendingAttachmentsAndRetainsReadonlyMessageChips \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingBlocksPendingAttachmentMutation \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.removePendingAttachmentDropsOnlySelectedAttachmentAndClearsError \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.blankMessageWithoutAttachmentsDoesNotSend \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsLoadsDocumentAndImageUrisIntoPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsStopsBeforeReadingReportedOversizeFile \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsBoundsReadWhenReportedSizeIsUnknown \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsKeepsAtMostFourPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.addAttachmentsWithExistingPendingAttachmentsReadsOnlyRemainingSlotsAndShowsLimit \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSendMessagesPrependsCapabilityGuardWithoutClientSuppliedMemoryContext \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryEntriesReplaceAndMutateCachedMemory \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.clientCapabilitiesAdvertiseRuntimeOwnedHistoryMemoryAndAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatDeltaAppendsReasoningWithoutMixingIntoAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.thinkingDeltaAliasAppendsReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.inlineThinkTagsAreSeparatedFromAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkTagsKeepReasoningCollapsedOutOfAnswerContent \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.activeStreamTerminationClosesTrailingAssistantReasoningState \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkOpeningTagAcrossDeltasDoesNotLeakTagToAnswer \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.splitInlineThinkClosingTagAcrossDeltasDoesNotLeakTagToReasoning \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.incompleteInlineThinkTagPlaceholderIsClearedOnDone \
  -Pkotlin.incremental=false

run swift build --product AetherLink
run swift test --filter RelayServerCoreTests
run swift test --filter TransportTests
run swift test --filter AetherLinkLocalizationTests
run swift test --filter 'AetherLinkLocalizationTests/testActivityTechnicalDetailsRedactRouteSecrets|AetherLinkLocalizationTests/testRouteDiagnosticDisclosureRedactsSensitiveDetails'
run swift test --filter AetherLinkRenderSmokeTests
run swift test --filter DocumentTextExtractorTests
run swift test --filter 'OllamaBackendTests/testListModelsUsesShowCapabilitiesToSeparateEmbeddingModels|LMStudioBackendTests/testListModelsParsesNativeLocalLLMAndEmbeddingModelsSeparately|LMStudioBackendTests/testListModelsFallsBackToOpenAICompatibleModels|AggregatingLlmBackendResidencyTests/testInstalledEmbeddingModelIsNotRoutedAsChat|AggregatingLlmBackendResidencyTests/testInstalledCloudChatModelIsNotRoutedAsChat'
run swift test --filter 'RuntimeIdentityKeyStoreTests/testFileStoreLoadOrCreatePersistsRuntimeIdentity|RuntimeIdentityKeyStoreTests/testFileStoreCorrectsBroadPermissionsWithoutRotatingIdentity'
run swift test --filter TrustedDeviceStoreTests
run swift test --filter 'LocalRuntimeMessageRouterTests/testTrustedHelloAndAuthResponseAuthenticatesConnection|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsRawNonceSignature|LocalRuntimeMessageRouterTests/testPairingRequestStoresTrustedDeviceAndReturnsAccepted|LocalRuntimeMessageRouterTests/testPairingRequestRejectsWhitespaceMutatedDeviceIdentityBeforeTrusting|LocalRuntimeMessageRouterTests/testConnectionDidCloseClearsAuthenticatedSession|LocalRuntimeMessageRouterTests/testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection|LocalRuntimeMessageRouterTests/testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment|LocalRuntimeMessageRouterTests/testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment|LocalRuntimeMessageRouterTests/testChatSendImageAttachmentRequiresVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendAllowsLMStudioImageAttachmentsForVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendUnsupportedDocumentAttachmentReturnsStructuredError|LocalRuntimeMessageRouterTests/testChatSendRoutesQualifiedLMStudioModelThroughAggregateBackend'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture|LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorUsesStoredBootstrapSettingsWhenEnvironmentIsEmpty|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingFallsBackAcrossBootstrapRelayEndpointsBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesSavedBootstrapRelayEndpointBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelStartRenewsSavedBootstrapRelayRouteBeforeRelayStart|LocalRuntimeMessageRouterTests/testCompanionAppModelRenewsBootstrapRelayRouteAfterRelayFailure|LocalRuntimeMessageRouterTests/testCompanionAppModelSavesBootstrapRelaySettingsAndAllocatesRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotReuseSavedLeaseForDifferentRelayRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesBootstrapQRCodeWithExpiredSavedLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRequiresRemoteQRCodeForLoopbackSavedRelayHost|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease|LocalRuntimeMessageRouterTests/testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial|LocalRuntimeMessageRouterTests/testCompanionAppModelKeepsLeasePreparationIssueWhenRelayIsReadyWithoutLease|LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownRelayScopeFromRuntimeProvider|LocalRuntimeMessageRouterTests/testChatSendStoresRuntimeSideProcessingEvents|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryHandlersReturnEmptyForNonPositiveLimitsWithoutReadingStore|LocalRuntimeMessageRouterTests/testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle|LocalRuntimeMessageRouterTests/testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeChatStoreTreatsNonPositiveLimitsAsEmptyHistoryWindows|LocalRuntimeMessageRouterTests/testRuntimeChatStoreZeroLimitsReturnEmptyWithoutReadingLog|LocalRuntimeMessageRouterTests/testRuntimeChatStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeChatHistorySemanticallyInvalidEventReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testRuntimeMemoryMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsSemanticallyInvalidUpsertLine|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreScopesEntriesByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeMemoryListCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory|LocalRuntimeMessageRouterTests/testChatSendInjectsEnabledRuntimeMemoryFromRuntimeStore|LocalRuntimeMessageRouterTests/testChatSendRuntimeMemoryOverridesClientSuppliedMemory|LocalRuntimeMessageRouterTests/testChatSendStoresOnlyClientVisibleMessagesWhileBackendReceivesRuntimeContext|LocalRuntimeMessageRouterTests/testChatSendDoesNotCompactShortConversation|LocalRuntimeMessageRouterTests/testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge|LocalRuntimeMessageRouterTests/testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate|LocalRuntimeMessageRouterTests/testChatSendReturnsStructuredErrorWhenRuntimeMemoryCannotLoad|LocalRuntimeMessageRouterTests/testChatSendStreamsReasoningDeltaSeparatelyFromAnswerDelta|LocalRuntimeMessageRouterTests/testChatSendSplitsInlineThinkTagsBeforeStreamingAnswer|LocalRuntimeMessageRouterTests/testChatSendInstalledEmbeddingModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendInstalledCloudModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse|LocalRuntimeMessageRouterTests/testChatSendGeneratedRuntimeTitleStripsInlineThinking|LocalRuntimeMessageRouterTests/testChatSendTitleGenerationUsesDeterministicFallbackWhenBackendTitleIsInvalid|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsStructuredSuggestions|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestNormalizesBlankDuplicateAndExcessSuggestions|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestAcceptsFencedStructuredSuggestions|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestReturnsEmptySuggestionsForInvalidJSON|LocalRuntimeMessageRouterTests/testChatSuggestionsRequestFallsBackToNumberedLocalizedList'

echo
echo "No-device quality checks passed."
echo "Covered: local emit-only pairing QR artifact generation, QR PNG decode, canonical pairing URI policy, authenticated mock relay E2E, QR candidate structured-error routing, identity-only QR discovery timeout, public relay remote-scope QR contract, private-overlay relay scope schema guard, link-local relay preflight rejection, relay preflight allocation non-persistence, bootstrap relay endpoint failover before QR generation, saved bootstrap relay endpoint allocation, remote relay lease renewal and QR eligibility, QR relay alias-family completeness, release-mode diagnostic direct-route rejection, invalid QR auto-reconnect state guard, relay-route payload validation, PairingStore complete and expired relay-route persistence, relay preparation host eligibility guard, expired relay lease reconnect guard, fresh relay QR recovery, Android QR route refresh public-key optional binding, macOS remote QR lease route binding, route.refresh runtime-identity binding, route.refresh relay-scope enum validation, route.refresh rejected-payload retry, cross-network QR readiness copy, diagnostic QR text fallback copy, macOS remote QR lease failure visibility, macOS first-launch pairing priority, macOS first-run diagnostics hiding, macOS Pairing QR accessibility state, macOS Pairing QR image accessibility element, macOS Pairing QR unavailable accessibility value, macOS Pairing QR time remaining accessibility value, macOS Pairing QR remote-route expiry accessibility hint, macOS Pairing QR generation action accessibility reason, macOS active Pairing QR renewal accessibility hint, macOS sidebar brand accessibility label, macOS page header accessibility labels, macOS page header heading trait, macOS panel header heading trait, macOS empty-state accessibility labels, macOS sidebar preference picker accessibility values, macOS sidebar preference picker accessibility hints, macOS nearby-only connection guidance copy, macOS global QR generation availability gate, macOS app-language date formatting, macOS app-language byte-count formatting, macOS app-language region tag normalization, macOS connection recovery form field accessibility, macOS connection recovery QR action accessibility reason, macOS Connection Recovery result tone accessibility label, macOS trusted-device remove accessibility labels, macOS trusted-device remove accessibility hints, macOS trusted-device row accessibility labels, macOS trusted-device row accessibility visual-summary separation, macOS trusted-device removal confirmation localization, macOS trusted-device confirm-remove action accessibility labels, macOS Activity trusted-device audit copy, macOS Activity row tone accessibility labels, macOS Activity log list accessibility summary, macOS Activity diagnostic disclosure separate focus, macOS Activity route-success ready tone, macOS Activity technical-details accessibility state, macOS saved connection details removal accessibility label, macOS Activity technical-details accessibility labels, macOS provider technical-details accessibility labels, macOS provider technical-details accessibility state, macOS provider status pill accessibility labels, macOS provider row accessibility summaries, macOS runtime overview accessibility labels, macOS status card accessibility labels, macOS model row accessibility labels, macOS model group header accessibility labels, macOS model group header heading trait, macOS relay status row accessibility labels, macOS route diagnostic technical-details accessibility labels, macOS readiness row accessibility labels, macOS natural count/plural copy guard, macOS visible localization anchors with zh-Hans bundle fallback, macOS raw SwiftUI visible-string localization guard, macOS five-language system/light/dark detail render smoke including Connection Recovery, macOS native language picker labels, macOS installed-local model visibility, macOS runtime-local chat routing, macOS runtime suggested-question normalization, macOS corrupt chat-store visibility, macOS runtime-owned memory injection, stale-client-memory replacement, runtime-only context history filtering, and heuristic runtime chat context compaction, Android natural message-count plural resources, Android raw Compose visible-string localization guard, platform-neutral app copy guard, Android native language picker labels, Android first-run language picker before pairing, Android app System/Light/Dark theme path, Android refresh-health action copy, Android localized model-status resources, Android provider-managed model label suppression, Android strict local model metadata guard, Android drawer runtime session status, Android drawer runtime summary accessibility, Android drawer settings footer layout, Android app top-bar shell chrome, Android screen heading semantics, Android QR scanner heading semantics, Android chat top-bar install action cue, Android chat top-bar model search interaction, Android chat top-bar model row accessibility summaries, Android drawer chat options contextual accessibility, Android drawer chat options action labels, Android drawer chat menu contextual action labels, Android drawer chat row accessibility summaries, Android drawer chat search interaction, Android drawer streaming lockout visual-disabled state, Settings chat history search interaction, Android QR scanner permission/settings/torch/cancel chrome, Android QR scanner close action accessibility label, Android QR scanner five-language chrome accessibility, QR scanner torch state accessibility, Android QR-first chat empty state, Android QR pairing live-region accessibility, Android Settings QR scan disabled reason, Android diagnostic QR text state accessibility, Android diagnostic QR text contextual action labels, Android connect action disabled reason, Android platform-neutral connect guidance copy, Android connection status hero accessibility summary, Android model refresh action accessibility state, Android New Chat disabled reason, Android chat empty route guidance full-wrap layout, Android expired remote-route QR recovery action, Android trusted composer readiness lock, Android composer readiness hint, Android composer input readiness accessibility state, Android send button readiness accessibility state, Android composer primary action click labels, Android composer attach action accessibility state, Android composer attachment count limit accessibility, Android attachment-only prompt resource localization, Android attachment picker single-dispatch guard, Android bounded attachment read guard, Android streaming cancel Compose action, Android attachment chip accessibility state, Android attachment remove disabled reason, Android attachment size locale formatting, Android message attachment accessibility state, Android message role accessibility summaries, Android message copy accessibility labels, Android copy success live-region accessibility, Android code block copy accessibility labels, Android multi-code-block copy action labels, Android backend readiness banner accessibility summary, Android generic error banner accessibility summary, Android provider diagnostics expanded state, Android provider diagnostics named accessibility labels, Android provider diagnostics action labels, Android provider row accessibility summaries, Android suggested-question accessibility labels, Android suggested-question count live-region accessibility, Android suggested-question action accessibility labels, Android generating suggestions live-region accessibility, Android reasoning accessibility summary, Android jump-to-latest Compose interaction, Settings expandable section accessibility state, Settings expandable section duplicate icon semantics guard, Settings preference option accessibility summaries, Settings diagnostic endpoint expander accessibility state, Settings connection switch state accessibility, Settings discovered route contextual action accessibility, Settings discovered route unavailable accessibility summaries, Android embedding model row accessibility summaries, Settings embedding model streaming lockout accessibility state, Settings memory contextual action accessibility, Settings memory capped action accessibility labels, Settings memory add readiness accessibility state, Settings memory destructive confirmation haptic timing, chat history destructive confirmation haptic timing, confirmation-open lightweight haptic timing, Settings expired-route primary QR action, Android connected Settings redundant-connect guard, Android trusted-runtime forget confirmation, Settings pairing section resync, language alias selection normalization, legacy Python relay allocation-guard, Android no-device Compose screen smoke with five-language pairing copy, Settings diagnostic endpoint visibility guard, chat history bulk action hiding and two-step confirmation, chat history bulk expander accessibility state, chat history bulk action disabled accessibility state, chat history per-chat contextual action accessibility, chat history per-chat disabled accessibility state, chat history row accessibility summaries, Android rename chat readiness accessibility state, Android rename chat action labels, full five-language light/dark Chat/Settings/Connection layout matrix, reasoning toggle, suggested-question normalization, suggested-question composer handoff, chat top-bar model/embedding picker separation, selected model-picker plus Settings preference and embedding-model accessibility state, fake haptic callback dispatch, connection notice haptic callback dispatch, runtime-owned streaming storage redaction, pending relay QR retry, Android pending relay QR secret-store boundary, Android pending relay QR secret cleanup, relay QR completion persistence, real RuntimeRelayTcpClient app pairing path, relay-before-Bonjour fallback, and trusted relay app-init auto-reconnect."
echo "Covered addendum: Android OS app-language handoff, Android translated Memory noun, macOS menu-bar status and command localization, macOS quick action accessibility hints, macOS menu-bar quick action accessibility parity, macOS first-run Pairing QR primary action ordering, macOS Connection Recovery private-overlay toggle accessibility labels, macOS Connection Recovery and diagnostics disclosure accessibility state, macOS Connection Recovery Save Connection input state, macOS Connection Recovery Save Bootstrap Relay input state, macOS Connection Recovery bootstrap allocation token warning, macOS Connection Recovery bootstrap relay removal accessibility labels, macOS Connection Recovery destructive removal action hints, macOS menu-bar Pairing QR active-session title, macOS Pairing QR route notice accessibility status, macOS Connection Recovery fallback-action accessibility hints, macOS CJK page-header accessibility spacing, macOS trusted-device refresh accessibility hint, Android trusted-runtime forget named accessibility label, Android trusted-runtime forget named click label, Android trusted-runtime forget confirmation action labels, Settings discovery action accessibility states, Settings discovery action accessibility labels, Android streaming cancel accessibility state, Android jump-to-latest accessibility state, Android jump-to-latest action labels, Android connected action accessibility states, Android connected action accessibility labels, Android connected action reconnect lockout, Android backend readiness refresh accessibility state, Android backend readiness refresh action labels, Android model refresh action accessibility labels, Android route notice action accessibility labels, Android route notice accessibility summaries, Android route notice accessibility state, Android route notice QR recovery steps, Android connection status incomplete relay route live-region recovery, Android primary pairing cross-network route copy, Android pairing primary action accessibility labels, Android trusted-route connect label, Android manual diagnostic host QR-first guard, Android relay auth failure QR recovery notice, Android relay auth failure auto-retry stop, Android relay auth failure post-clear QR action, Android relay auth failure empty-chat copy, Android route rejection empty-chat copy, Android expired route empty-chat copy, Android expired remote-route QR recovery localization, Android expired relay route purge, Android relay secret store boundary, Android relay secret Base64 boundary, macOS relay secret store boundary, Android route.refresh terminal expiry state guard, Android QR runtime-name normalization, Android PairingStore incomplete relay cleanup, Android New Chat pairing-required disabled reason, Android New Chat action labels, Android permanent rail New Chat pairing gate, Android permanent rail Chat pairing gate, Android drawer rich chat search, Android drawer chat model metadata, Android chat history display-model search, Android drawer saved missing model recovery, Android drawer streaming lockout accessibility state, Android chat top-bar model picker streaming disabled state, Android chat top-bar model picker streaming transition lockout, Android chat top-bar stale saved model suppression, Android chat top-bar saved missing model recovery, Android chat top-bar model refresh action accessibility state, Android chat top-bar active chat title, Android chat top-bar model picker closed-button accessibility summary, Android chat top-bar model row action labels, Android search clear action labels, Android composer keyboard Send action, Android composer latest QR readiness hint, Android attachment-only composer readiness state, Android composer readiness live-region accessibility, Android route-recovery empty-state live-region accessibility, Android latest QR empty-state callback routing, Android chat empty-state primary action labels, Android reasoning toggle action labels, Android streaming assistant live-region accessibility, Settings expandable section action accessibility labels, Settings switch action accessibility labels, Settings memory action accessibility labels, Settings memory streaming lockout accessibility state, Settings memory add action accessibility labels, Settings memory empty-state live-region accessibility, Settings memory delete confirmation action labels, Settings chat history model metadata, Android memory input readiness accessibility state, chat history bulk expander action labels, chat history bulk action accessibility labels, chat history destructive confirmation and cancel action labels."
echo "Covered macOS dialog addendum: macOS trusted-device cancel-remove action accessibility labels, macOS saved connection details cancel accessibility label."
echo "Covered macOS status addendum: macOS model-provider empty-state accessibility labels, macOS provider status decorative icon hiding."
echo "Covered readiness addendum: macOS runtime overview installed-local model readiness, macOS readiness row fallback accessibility, macOS trusted-device missing-date ID accessibility, Android streaming chat input mutation guard, Android streaming send reentrancy guard, Android streaming attachment mutation guard, Android streaming embedding-model selection guard, Android streaming suggested-question lockout guard, Android streaming memory mutation guard, Android streaming route/trust mutation guard, Android stream termination reasoning closure, Android runtime-owned stale message resurrection guard, Android runtime-owned local memory storage redaction, Android runtime memory client-prompt suppression, Android runtime lifecycle local-session collision guard, Android unreachable route-refresh QR cleanup guard, Android route.refresh sensitive detail minimization, Android pending relay QR secret-store boundary, Android pending relay QR secret cleanup, Android runtime technical error detail storage boundary, Android safe runtime technical diagnostics surface, Android share-sheet intake, Android explicit share-sheet MIME scope, Android private-overlay real relay TCP pairing path, Android private-overlay real relay TCP reconnect path, Android device identity Base64 signature guard, Android device identity persistence guard, Android QR trust value whitespace guard, Android/macOS client auth domain separation, macOS pairing trusted-device identity validation, macOS auth session disconnect cleanup, macOS trusted-device removal live-session revocation, macOS relay line framing newline guard, macOS relay disconnect callback idempotency, macOS local peer disconnect callback idempotency, macOS route material diagnostic redaction, macOS attachment prompt storage separation, macOS trusted-device store file permission hardening, macOS runtime identity fallback file permission hardening, macOS runtime event-log file permission hardening, macOS runtime history router nonpositive-limit guard, macOS runtime history nonpositive limit guard, macOS runtime history zero-limit corrupt-log bypass, macOS runtime history semantic corruption visibility, macOS runtime memory corrupt-log visibility, macOS runtime memory semantic corruption visibility, macOS authenticated runtime history and memory owner-device scoping."
echo "Covered Android settings addendum: Android preference group heading semantics, Android Settings panel heading semantics, Settings preference option action labels, Android drawer section heading semantics, Android drawer empty-history live-region accessibility, Android drawer Settings footer action semantics, Android permanent rail Settings action semantics, Android permanent rail Settings readiness state, Android chat search no-results live-region accessibility, Android model search no-results live-region accessibility, Android streaming assistant content live-region accessibility, Android model picker empty-state live-region accessibility, Android embedding model empty-state live-region accessibility, Android open reasoning initial expansion, Android open reasoning live-region accessibility."
echo "Covered Android layout addendum: Android ChatGPT-like chat surface narrow-phone layout regression, Android markdown message rendering, Android assistant response regenerate action, Android latest user-message draft reuse action, Android message follow-up action localized states, Android localized clipboard payload labels, Android composer clear-draft action, Android composer clear-draft localized state, Android composer draft persistence, Android session-scoped composer draft switching, Android transient attachment cleanup on chat switching, Android transient attachment cleanup on chat lifecycle exits, Android runtime transcript loading state, Android runtime transcript lifecycle mutation lockout."
echo "Not covered: physical install, camera QR scan, real device haptics, launcher/Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity."
