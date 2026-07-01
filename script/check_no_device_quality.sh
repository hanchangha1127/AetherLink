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

check_physical_external_relay_summary_guard() {
  local work_dir
  local summary_path
  local log_path
  local output
  local status_code

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/aetherlink-physical-wrapper-summary.XXXXXX")"
  summary_path="$work_dir/summary.json"
  log_path="$work_dir/run.log"
  set +e
  output="$(
    ADB=/bin/true \
      script/check_physical_external_relay_pairing.sh \
        --relay-host 0.0.0.0 \
        --json "$summary_path" \
        --log "$log_path" \
        2>&1
  )"
  status_code=$?
  set -e
  if [[ "$status_code" -ne 2 ]]; then
    echo "Physical external-relay wrapper invalid-host guard should exit 2, got $status_code" >&2
    echo "$output" >&2
    rm -rf "$work_dir"
    exit 1
  fi
  python3 - "$summary_path" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
assert summary["success"] is False, summary
assert summary["exit_status"] == 2, summary
assert summary["coverage"]["external_relay_probe_from_device"] is False, summary
assert summary["coverage"]["external_relay_route_probe_from_device"] is False, summary
assert summary["coverage"]["external_relay_probe_reachable"] is False, summary
assert summary["coverage"]["external_relay_route_ready"] is False, summary
assert summary["probe_summaries"]["device_relay_endpoint"] is None, summary
assert summary["probe_summaries"]["device_relay_route"] is None, summary
assert "device_endpoint_probe_not_reachable_or_missing" in summary["caveats"], summary
assert "device_route_probe_not_ready_or_missing" in summary["caveats"], summary
assert "does_not_expose_ollama_or_lm_studio_to_android" in summary["caveats"], summary
assert "--allocation-token" not in summary["command"], summary
PY
  rm -rf "$work_dir"
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
run check_physical_external_relay_summary_guard
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
  --require-production-bootstrap \
  --expected-relay-host 127.0.0.1 \
  --expected-relay-port "$QR_SMOKE_RELAY_PORT" \
  --forbid-direct-endpoint \
  --allow-local-relay \
  >/dev/null
run ./script/runtime_authenticated_mock_smoke.swift --relay --expect-p2p-route-refresh

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
  --tests com.localagentbridge.android.core.transport.RuntimePeerToPeerRoutePreparationTest \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayRoutePreparationTest \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.defaultResolverIgnoresTrustedLastKnownEndpointHintForPairedTarget \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.preparedRelayRouteStillConnectsWhenTargetHasTrustedLastKnownEndpointHint \
  --tests com.localagentbridge.android.core.transport.RuntimeConnectionManagerTest.relayConnectorCanFallbackAfterPreparedPeerToPeerRouteFails \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayConnectFailsWhenReadyLineRejectsRoute \
  --tests com.localagentbridge.android.core.transport.RuntimeRelayTcpClientTest.relayChannelEncryptsSentFramesAndDecryptsRuntimeResponses \
  -Pkotlin.incremental=false

run ./gradlew --no-daemon \
	  :app:compileDebugKotlin \
		  :app:testDebugUnitTest \
		  --tests com.localagentbridge.android.AppNavigationTest \
		  --tests com.localagentbridge.android.AppNavigationTest.settingsSystemLanguageOptionIsSeparateFromFixedLaunchLanguages \
			  --tests com.localagentbridge.android.AppNavigationTest.routeNoticeActionIgnoresTrustedLastKnownEndpointForNormalQrFirstRecovery \
			  --tests com.localagentbridge.android.AetherLinkThemeNoDeviceComposeTest \
			  --tests com.localagentbridge.android.PairingQrScannerChromeNoDeviceComposeTest \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusProviderRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusPanelStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsLanguagePickerStaysInPreferencesAfterPairingFirstAcrossLaunchLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsExpandableSectionHeadersStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsTrustedRuntimePanelStaysBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsQrPairingPanelStaysBoundedAtLargeFontAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerSearchMatchesModelAndRuntimeMetadata \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerGroupsPreviousChatsByLocalDateAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerDisabledItemsExplainStreamingLockoutAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatDrawerRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryStaysBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.navigationDrawerRuntimeSummaryShowsSavedMissingModelRecovery \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerShowsSavedMissingChatModelRecovery \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerKeepsLongModelNamesCompact \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarModelPickerVisionRecoveryRowsStayBoundedAtLargeFontOnNarrowSurface \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatTopBarShowsNamedActiveChatTitleAndHidesDefaultNewChatFallback \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeLocalizedModelMetadata \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowsExposeLocalizedAccessibilitySummaries \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistorySummaryLocalizesSavedActiveAndArchivedCounts \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryActiveRowCanOpenChatWithHapticFeedback \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRefreshUsesCurrentSearchQuery \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryShowsRuntimeSearchSnippetForQueryResults \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRuntimeSearchMetadataStaysBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistorySearchResultActionsKeepFilteredContext \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryRowActionsStayInsideNarrowLargeFontRowsAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsChatHistoryBulkActionsStayBoundedAtLargeFontAcrossSupportedLanguages \
							  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsDiscoveredRuntimeRowsStayInsideNarrowLargeFontRowsAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsHistoryAndMemoryRenderRepresentativeNarrowPhoneAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsCoreControlsRemainReachableAtLargeFontScaleAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsAutoReconnectRowStaysBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsEmbeddingModelRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsPreferenceRowsExposeSelectedStateToAccessibility \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsAppearanceAndLanguagePreferenceRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsLanguagePreferenceRowsDispatchSystemAndFixedSelectionCallbacks \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsKeepActionsBelowLongContentOnCompactWidth \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryRowsShowApprovedSourceMetadataWithoutFullTranscript \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryApprovedSourceMetadataLocalizesAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemorySummaryLocalizesSavedAndPausedCountsAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelShowsSummaryDraftApprovalAction \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelDisablesPendingSummaryDraftApproval \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelShowsSummaryDraftDismissAction \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemoryPanelDisablesPendingSummaryDraftDismissal \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsMemorySummaryDraftRowsStayBoundedAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatSurfaceRendersRepresentativeNarrowPhoneWithoutComposerOverlap \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenCoreControlsRemainReachableAtLargeFontScaleAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.parseMessageContentPreservesCodeBlocksAndNormalizesMarkdownTextBlocks \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRendersMarkdownListsAndInlineCode \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMarkdownTablesExposeLocalizedAccessibilitySummaryAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenCodeBlocksExposeLocalizedAccessibilitySummaryAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenMarkdownTablesAndCodeBlocksStayBoundedAtLargeFontAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsRegenerateActionOnlyForLatestAssistantAndHidesWhileStreaming \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsReuseDraftActionOnlyForLatestEligibleUserMessage \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenLatestMessageActionsExposeLocalizedStateAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenLatestMessageActionsStayInsideNarrowLargeFontRowsAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTranscriptUsesCompactSameRoleSpacingAndWiderRoleChanges \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenJumpToLatestButtonStaysAboveComposerAtLargeFontAcrossSupportedLanguages \
				  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenAttachmentOnlyMessageRowsExposeLocalizedRoleAccessibilitySummaries \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenReadOnlyAttachmentChipsWrapOnCompactWidthAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenPendingAttachmentChipsWrapOnCompactWidthAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenClearDraftActionClearsComposerAndHidesWhileStreaming \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTextOnlyDraftControlsStayBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingCancelControlsStayBoundedAtLargeFontAcrossSupportedLanguages \
					  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenStreamingProgressIndicatorStaysDecorativeAndBoundedAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenComposerReadinessStatusStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenRouteAvailabilityNoticeStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenBackendUnavailableBannerStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenGenericErrorBannerStaysBoundedAtLargeFontAcrossSupportedLanguages \
						  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenShowsLocalizedLoadingStateWhileRuntimeTranscriptLoads \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.settingsCompanionOnlyPanelAnnouncesLocalizedPrivateModelAccessAcrossSupportedLanguages \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatScreenTrustedRuntimeWithoutConnectableRouteShowsLatestQrEmptyState \
		  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatEmptyNoModelGuidesUsersToHeaderModelPickerAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.chatEmptyUninstalledModelGuidesUsersToInstallOrChooseAcrossSupportedLanguages \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusScreenKeepsDiagnosticRoutesStatusOnly \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusTrustedLastKnownOnlyRouteScansLatestQrWithHaptic \
			  --tests com.localagentbridge.android.ui.ClientScreensNoDeviceComposeTest.connectionStatusConnectedActionsDisableWhileConnectingAcrossSupportedLanguages \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayRestoreMarksConnectingBeforeRelayDialCompletes \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelAutoReconnectsTrustedRelayOnInitAndRefreshesRuntimeState \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeRestoreDoesNotStartDiscoveryWhenRelayRouteIsAvailable \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrAcceptedPairingRestoresRelayReconnectWithoutManualEndpoint \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayReconnectAttemptsRelayBeforeMatchingBonjourFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.macosCompactRelayQrFixtureParsesAndPreparesRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrWithCompactRelayUriConnectsRelayAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayQrPairingFailsBeforeConnectWhenDeviceCannotReachRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayProbeResponseParserRequiresKnownRouteAndWaitingRuntime \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.rejectedCompactRelayQrPairingResultClearsPendingRouteAndSecret \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultRejectsIncompleteRelayRouteInsteadOfDirectFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultDropsQrDirectEndpointFromTrustedRuntimeStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeConnectionTargetDropsTrustedLastKnownEndpoint \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRouteCandidatesUseDiscoveredEndpointInsteadOfTrustedLastKnownFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.autoReconnectTrustedRuntimeTargetWaitsForFreshRouteWhenOnlyTrustedLastKnownEndpointExists \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.autoReconnectRouteCandidatesDoNotUseTrustedLastKnownEndpointAsFallback \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.compactRelayQrPairingUsesRealRelayTcpClientAndPersistsTrustedRelay \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.privateOverlayRelayQrPairingUsesRealRelayTcpClientAndPersistsOverlayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelRelayIntegrationTest.trustedPrivateOverlayRelayReconnectUsesRealRelayTcpClientAndAuthenticatedSession \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.freshCompactRelayQrRefreshesExpiredTrustedRelayRouteAndReconnectsViaRelay \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.invalidPairingQrDoesNotEnableTrustedRuntimeAutoReconnect \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromPairingQrRejectsIdentityOnlyQrInNormalScanPath \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.diagnosticIdentityOnlyPairingQrCanUseUsbReverseFallbackWhenRemoteRouteIsNotRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustRuntimeFromMacosPrivateOverlayQrConnectsRelayAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresPendingPairingRouteUntilShorterRelayExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataStoresPendingP2pRendezvousRouteUntilShorterRecordExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerPlansPendingP2pRendezvousBeforeRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForPendingP2pRendezvousRecord \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRuntimeP2pReconnectUsesStoredQrRendezvousMetadata \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedPeerToPeerRouteFallsBackToRelayAtViewModelConnectionLayer \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeRemoteRoutePlannerUsesInjectedClockForSavedP2pRendezvousRecord \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.autoReconnectTrustedRuntimeTargetUsesSavedP2pRouteWithoutManualEndpoint \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.productPairingQrParserRequiresRuntimePublicKeyAndRouteTokenWhenRemoteRouteIsRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.productPairingQrParserAcceptsP2pRendezvousQrWhenRemoteRouteIsRequired \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.acceptedPairingResultPreservesP2pRendezvousForTrustedRuntimeRestore \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrAddsP2pRendezvousRouteToExistingTrustedRuntime \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeSchedulesRouteRefreshBeforeRecordExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeRetriesRouteRefreshErrorBeforeRecordExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeMarksRouteExpiredWhenRefreshCannotRetryBeforeRecordExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataDropsDirectEndpointFromPendingPairingRouteStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRemovesPendingPairingRelaySecretWhenRouteClearsOrReplaces \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayPairingQrRetriesAndSendsPairingRequestAfterRelayBecomesReady \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.releasePairingParserRejectsMacosLocalDiagnosticQrRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectedModelSendStateRejectsEmbeddingModelAsChatModel \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.requestModelInstallRejectsUnknownModelWithoutPersistingOrPulling \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.selectModelRejectsUnknownModelWithoutPersistingOrPulling \
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
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedComposerDraftRestoresOnViewModelCreationAndUpdatesWithTyping \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openPreviousChatRestoresSessionScopedComposerDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.clearChatDraftClearsActiveSessionTextAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.startNewChatClearsNoActiveDraftButKeepsSessionDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveActiveChatClearsNoActiveDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.archiveAllChatsClearsNoActiveDraftAndPendingAttachments \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.openingRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.sendChatMessageClearsOnlyActiveSessionComposerDraft \
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
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummariesReplaceRuntimeOwnedCacheAndPreserveLocalSessions \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeSessionSummariesClampNegativeMessageCounts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.streamingRuntimeOwnedChatRendersInMemoryButRedactsDeviceStorage \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryListRendersInMemoryButRedactsDeviceStorage \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemorySummaryDraftsListRendersReviewStateWithoutDeviceStorage \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftSendsExpectedApprovalAndRendersRuntimeMemoryOnly \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.approveMemorySummaryDraftErrorClearsPendingAndAllowsRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.dismissMemorySummaryDraftSendsExpectedDecisionAndRemovesDraft \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.dismissMemorySummaryDraftErrorClearsPendingAndAllowsRetry \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeMemoryEntriesReplaceAndMutateCachedMemory \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryRequestsFreshListAfterPendingListCompletes \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryRequestsFreshListAfterPendingListCompletes \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryCanSendTrimmedQuery \
	  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeChatMessagesListErrorClearsLoadingAndShowsChatHistoryLoadFailed \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeChatHistoryErrorShowsLoadFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemoryErrorShowsFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.refreshRuntimeMemorySummaryDraftsErrorShowsFailureAndAllowsRetry \
  --tests com.localagentbridge.android.runtime.RuntimeClientChatSessionMutationFailureTest \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.deviceStorageSnapshotDropsRuntimeOwnedDataButKeepsLocalDrafts \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.runtimeLifecycleAckDoesNotMutateLocalOnlySessionWithSameId \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsMismatchedRuntimeIdentity \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsUnknownRelayScope \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAllowsStableRelayIdAndSecretWithFreshNonceAndExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsReusedRelayNonce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonAdvancingRelayExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadAddsFreshP2pRendezvousRouteToCurrentTrustedRuntime \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsExpiredOrIncompleteP2pMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonCanonicalP2pMaterial \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsReusedP2pRendezvousRecordOrNonce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshPayloadRejectsNonAdvancingP2pExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeRetriesRouteRefreshWhenRuntimeReturnsReusedP2pRecord \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedP2pRuntimeRetriesRouteRefreshWhenRuntimeReturnsNonAdvancingP2pExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.persistedRuntimeDataRejectsIncompletePendingPairingRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrWithoutPublicKeyCanRefreshPinnedRuntimeRelayRoute \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshQrKeepsUnreachableRelayRouteForRetryOrFreshQrRecovery \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.relayReceiveAuthenticationFailureClearsStoredRelayAndStopsAutoReconnect \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayConnectionFailureKeepsStoredRelayAndStopsAutoReconnectUntilUserRetries \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.trustedRelayHandshakeRejectionKeepsStoredRelayAndStopsAutoReconnectUntilUserRetries \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeMarksRouteExpiredWhenRefreshErrorCannotRetryBeforeLeaseExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.routeRefreshAuthenticationRequiredDoesNotRetainRouteMaterialTechnicalDetail \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRuntimeRetriesRejectedRouteRefreshPayloadBeforeLeaseExpiry \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRelayRuntimeRetriesRouteRefreshWhenRuntimeReturnsReusedRelayNonce \
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.authenticatedTrustedRelayRuntimeRetriesRouteRefreshWhenRuntimeReturnsNonAdvancingRelayExpiry \
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
  --tests com.localagentbridge.android.runtime.RuntimeClientViewModelTest.chatSendMessagesSerializesOnlyClientVisibleConversationAndFinalAttachments \
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
run swift test --filter 'OllamaBackendTests/testListModelsUsesShowCapabilitiesToSeparateEmbeddingModels|OllamaBackendTests/testUnloadModelPostsEmptyChatWithKeepAliveZero|LMStudioBackendTests/testListModelsParsesNativeLocalLLMAndEmbeddingModelsSeparately|LMStudioBackendTests/testListModelsFallsBackToOpenAICompatibleModels|LMStudioBackendTests/testUnloadModelPostsLoadedInstanceID|AggregatingLlmBackendResidencyTests/testSwitchingModelsUnloadsPreviousInactiveModel|AggregatingLlmBackendResidencyTests/testRepeatedSameModelDoesNotUnloadBetweenChats|AggregatingLlmBackendResidencyTests/testIdlePolicyUnloadsActiveModelAfterDelay|AggregatingLlmBackendResidencyTests/testUnloadFailureEmitsProviderSpecificFailureEventWithoutBreakingNextChat|AggregatingLlmBackendResidencyTests/testInstalledEmbeddingModelIsNotRoutedAsChat|AggregatingLlmBackendResidencyTests/testInstalledCloudChatModelIsNotRoutedAsChat|AggregatingLlmBackendResidencyTests/testDuplicateProviderBackendsKeepFirstProviderInsteadOfCrashing'
run swift test --filter 'RuntimeIdentityKeyStoreTests/testFileStoreLoadOrCreatePersistsRuntimeIdentity|RuntimeIdentityKeyStoreTests/testFileStoreCorrectsBroadPermissionsWithoutRotatingIdentity'
run swift test --filter TrustedDeviceStoreTests
run swift test --filter 'LocalRuntimeMessageRouterTests/testTrustedHelloAndAuthResponseAuthenticatesConnection|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsRawNonceSignature|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsReplayedNonceAfterAuthentication|LocalRuntimeMessageRouterTests/testTrustedAuthResponseRejectsSupersededChallengeNonce|LocalRuntimeMessageRouterTests/testUnauthenticatedRuntimeCommandsRejectBeforeProtocolPayloadHandling|LocalRuntimeMessageRouterTests/testPairingRequestStoresTrustedDeviceAndReturnsAccepted|LocalRuntimeMessageRouterTests/testPairingRequestRejectsWhitespaceMutatedDeviceIdentityBeforeTrusting|LocalRuntimeMessageRouterTests/testConnectionDidCloseClearsAuthenticatedSession|LocalRuntimeMessageRouterTests/testRemovedTrustedDeviceCannotContinueUsingAuthenticatedConnection|LocalRuntimeMessageRouterTests/testChatSendAppendsDocumentAttachmentTextAndPreservesImageAttachment|LocalRuntimeMessageRouterTests/testChatSendExtractsMimeOnlyStructuredTextDocumentAttachment|LocalRuntimeMessageRouterTests/testChatSendImageAttachmentRequiresVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendAllowsLMStudioImageAttachmentsForVisionCapableModel|LocalRuntimeMessageRouterTests/testChatSendUnsupportedDocumentAttachmentReturnsStructuredError|LocalRuntimeMessageRouterTests/testChatSendRoutesQualifiedLMStudioModelThroughAggregateBackend'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionLogSanitizerRedactsProviderEndpointsAndSecrets|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedPrivateOverlayRelayFixture|LocalRuntimeMessageRouterTests/testCompactPairingQRCodePayloadMatchesSharedP2PRendezvousFixture|LocalRuntimeMessageRouterTests/testEnvironmentRemoteRelayRouteAllocatorUsesStoredBootstrapSettingsWhenEnvironmentIsEmpty|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingFallsBackAcrossBootstrapRelayEndpointsBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingUsesSavedBootstrapRelayEndpointBeforeQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelStartRenewsSavedBootstrapRelayRouteBeforeRelayStart|LocalRuntimeMessageRouterTests/testCompanionAppModelRenewsBootstrapRelayRouteAfterRelayFailure|LocalRuntimeMessageRouterTests/testCompanionAppModelSavesBootstrapRelaySettingsAndAllocatesRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelDoesNotReuseSavedLeaseForDifferentRelayRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesBootstrapQRCodeWithExpiredSavedLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRequiresRemoteQRCodeForLoopbackSavedRelayHost|LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease|LocalRuntimeMessageRouterTests/testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteReturnsNilWithoutFreshRelayLease|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeRouteAllocatesFreshRelayMaterial|LocalRuntimeMessageRouterTests/testCompanionAppModelKeepsLeasePreparationIssueWhenRelayIsReadyWithoutLease|LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsUnknownRelayScopeFromRuntimeProvider|LocalRuntimeMessageRouterTests/testChatSendStoresRuntimeSideProcessingEvents|LocalRuntimeMessageRouterTests/testChatSendIntoArchivedRuntimeSessionReturnsStructuredErrorWithoutMutatingStore|LocalRuntimeMessageRouterTests/testChatCancelAcknowledgementPersistsRuntimeOwnedCancelledEvent|LocalRuntimeMessageRouterTests/testConnectionCloseCancelsActiveChatGenerationAndPersistsCancelledEvent|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryMessagesAreAuthenticatedAndReturnedFromStore|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryHandlersReturnEmptyForNonPositiveLimitsWithoutReadingStore|LocalRuntimeMessageRouterTests/testRuntimeChatStoreAppliesArchiveRestoreAndDeleteLifecycle|LocalRuntimeMessageRouterTests/testRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeChatStoreSearchesSessionSummariesAndTranscriptWithinOwnerScope|LocalRuntimeMessageRouterTests/testRuntimeChatStoreTreatsNonPositiveLimitsAsEmptyHistoryWindows|LocalRuntimeMessageRouterTests/testRuntimeChatStoreZeroLimitsReturnEmptyWithoutReadingLog|LocalRuntimeMessageRouterTests/testRuntimeChatStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeChatEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeChatHistorySemanticallyInvalidEventReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatHistoryCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testRuntimeChatSessionLifecycleMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testChatSessionsListQueryFiltersRuntimeOwnedSummaries|LocalRuntimeMessageRouterTests/testChatSessionsListQueryMatchesReasoningWhileMessagesKeepAnswerSeparate|LocalRuntimeMessageRouterTests/testRuntimeMemoryMessagesMutateRuntimeStore|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsCorruptJSONLLineInsteadOfDroppingIt|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreReportsSemanticallyInvalidUpsertLine|LocalRuntimeMessageRouterTests/testRuntimeMemoryStoreScopesEntriesByOwnerDevice|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogIsCreatedWithOwnerOnlyPermissions|LocalRuntimeMessageRouterTests/testRuntimeMemoryEventLogPermissionsAreCorrectedOnAppend|LocalRuntimeMessageRouterTests/testRuntimeMemoryListCorruptStoreReturnsStructuredError|LocalRuntimeMessageRouterTests/testAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory|LocalRuntimeMessageRouterTests/testChatSendInjectsEnabledRuntimeMemoryFromRuntimeStore|LocalRuntimeMessageRouterTests/testChatSendRuntimeMemoryOverridesClientSuppliedMemory|LocalRuntimeMessageRouterTests/testChatSendStoresOnlyClientVisibleMessagesWhileBackendReceivesRuntimeContext|LocalRuntimeMessageRouterTests/testChatSendDoesNotCompactShortConversation|LocalRuntimeMessageRouterTests/testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge|LocalRuntimeMessageRouterTests/testChatSendUsesModelContextWindowMetadataForCompactionBudget|LocalRuntimeMessageRouterTests/testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate|LocalRuntimeMessageRouterTests/testChatSendReturnsStructuredErrorWhenRuntimeMemoryCannotLoad|LocalRuntimeMessageRouterTests/testChatSendStreamsReasoningDeltaSeparatelyFromAnswerDelta|LocalRuntimeMessageRouterTests/testChatSendSplitsInlineThinkTagsBeforeStreamingAnswer|LocalRuntimeMessageRouterTests/testChatSendInstalledEmbeddingModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendInstalledCloudModelReturnsModelNotInstalled|LocalRuntimeMessageRouterTests/testChatSendGeneratesRuntimeTitleAfterFirstAssistantResponse|LocalRuntimeMessageRouterTests/testChatSendGeneratedRuntimeTitleStripsInlineThinking|LocalRuntimeMessageRouterTests/testChatSendTitleGenerationUsesDeterministicFallbackWhenBackendTitleIsInvalid'
run swift test --filter LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesGUIAllocatedQRCodeWithNearExpiredLease
run swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshRejectsMalformedRelayMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshAllowsPrivateOverlayAndUsbReverseScopedRelayMaterial'
run swift test --filter 'LocalRuntimeMessageRouterTests/testRouteRefreshReturnsFreshP2PRendezvousMaterialFromRuntimeProvider|LocalRuntimeMessageRouterTests/testRouteRefreshRejectsMalformedP2PRendezvousMaterialFromRuntimeProvider'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeDataSummaryFromInjectedStores|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRuntimeHistoryTranscriptPreviewAcrossOwners|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsClearsRecoveredSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeMemoryEntriesPreservesChatSummaryError|LocalRuntimeMessageRouterTests/testCompanionAppModelRefreshRuntimeChatSessionsPreservesMemorySummaryError'
run swift test --filter 'LocalRuntimeMessageRouterTests/testCompanionAppModelDefaultPairingRequiresRemoteQRCodeRoute|LocalRuntimeMessageRouterTests/testCompanionAppModelPublishesRemoteRoutePreparationIssueWhenBootstrapAllocationThrows'
run swift test --filter 'LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftsListReturnsOwnerScopedActiveVisibleDraftsOnly|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftApproveWritesIdempotentOwnerScopedMemoryAndHidesApprovedDraft|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissRequiresAuthentication|LocalRuntimeMessageRouterTests/testMemorySummaryDraftDismissHidesOwnerScopedDraftWithoutWritingMemory'
run swift test --filter SQLiteRuntimeChatEventStoreTests
run swift test --filter RuntimeLongInactivityMemorySummarizationPolicyTests

echo
echo "No-device quality checks passed."
echo "Covered: local emit-only pairing QR artifact generation, QR PNG decode, canonical pairing URI policy, authenticated mock relay E2E, QR candidate structured-error routing, identity-only QR USB reverse fallback, public relay remote-scope QR contract, private-overlay relay scope schema guard, link-local relay preflight rejection, relay preflight allocation non-persistence, bootstrap relay endpoint failover before QR generation, saved bootstrap relay endpoint allocation, remote relay lease renewal and QR eligibility, QR relay alias-family completeness, release-mode diagnostic direct-route rejection, invalid QR auto-reconnect state guard, relay-route payload validation, PairingStore complete and expired relay-route persistence, relay preparation host eligibility guard, expired relay lease reconnect guard, fresh relay QR recovery, Android QR route refresh public-key optional binding, macOS remote QR lease route binding, route.refresh runtime-identity binding, route.refresh relay-scope enum validation, route.refresh rejected-payload retry, cross-network QR readiness copy, diagnostic QR text fallback copy, macOS remote QR lease failure visibility, macOS first-launch pairing priority, macOS first-run diagnostics hiding, macOS Pairing QR accessibility state, macOS Pairing QR image accessibility element, macOS Pairing QR unavailable accessibility value, macOS Pairing QR time remaining accessibility value, macOS Pairing QR remote-route expiry accessibility hint, macOS Pairing QR generation action accessibility reason, macOS active Pairing QR renewal accessibility hint, macOS sidebar brand accessibility label, macOS sidebar brand heading trait, macOS page header accessibility labels, macOS page header heading trait, macOS panel header heading trait, macOS empty-state accessibility labels, macOS sidebar preference picker accessibility values, macOS sidebar preference picker accessibility hints, macOS nearby-only connection guidance copy, macOS global QR generation availability gate, macOS app-language date formatting, macOS app-language byte-count formatting, macOS app-language region tag normalization, macOS connection recovery form field accessibility, macOS connection recovery QR action accessibility reason, macOS Connection Recovery result tone accessibility label, macOS trusted-device remove accessibility labels, macOS trusted-device remove accessibility hints, macOS trusted-device row accessibility labels, macOS trusted-device row accessibility visual-summary separation, macOS trusted-device removal confirmation localization, macOS trusted-device confirm-remove action accessibility labels, macOS Activity trusted-device audit copy, macOS Activity row tone accessibility labels, macOS Activity log list accessibility summary, macOS Activity diagnostic disclosure separate focus, macOS Activity route-success ready tone, macOS Activity technical-details accessibility state, macOS saved connection details removal accessibility label, macOS Activity technical-details accessibility labels, macOS provider technical-details accessibility labels, macOS provider technical-details accessibility state, macOS provider status pill accessibility labels, macOS provider row accessibility summaries, macOS runtime overview accessibility labels, macOS status card accessibility labels, macOS model row accessibility labels, macOS model group header accessibility labels, macOS model group header heading trait, macOS relay status row accessibility labels, macOS route diagnostic technical-details accessibility labels, macOS readiness row accessibility labels, macOS natural count/plural copy guard, macOS visible localization anchors with zh-Hans bundle fallback, macOS raw SwiftUI visible-string localization guard, macOS five-language system/light/dark detail render smoke including Connection Recovery, macOS active Pairing QR compact render smoke, macOS compact Quick Actions render smoke, macOS native language picker labels, macOS installed-local model visibility, macOS runtime-local chat routing, macOS corrupt chat-store visibility, macOS runtime-owned memory injection, stale-client-memory replacement, runtime-only context history filtering, and heuristic runtime chat context compaction, Android natural message-count plural resources, Android raw Compose visible-string localization guard, platform-neutral app copy guard, Android native language picker labels, Android first-run language picker before pairing, Android app System/Light/Dark theme path, Android refresh-health action copy, Android localized model-status resources, Android provider-managed model label suppression, Android strict local model metadata guard, Android drawer runtime session status, Android drawer runtime summary accessibility, Android drawer settings footer layout, Android app top-bar shell chrome, Android screen heading semantics, Android QR scanner heading semantics, Android chat top-bar install action cue, Android chat top-bar model search interaction, Android chat top-bar model row accessibility summaries, Android drawer chat options contextual accessibility, Android drawer chat options action labels, Android drawer chat menu contextual action labels, Android drawer chat row accessibility summaries, Android drawer chat search interaction, Android drawer streaming lockout visual-disabled state, Settings chat history search interaction, Android Settings chat-history runtime search metadata compact layout, Android QR scanner permission/settings/torch/cancel chrome, Android QR scanner close action accessibility label, Android QR scanner five-language chrome accessibility, QR scanner torch state accessibility, Android QR-first chat empty state, Android QR pairing live-region accessibility, Android Settings QR scan disabled reason, Android diagnostic QR text state accessibility, Android diagnostic QR text contextual action labels, Android connect action disabled reason, Android platform-neutral connect guidance copy, Android connection status hero accessibility summary, Android model refresh action accessibility state, Android New Chat disabled reason, Android chat empty route guidance full-wrap layout, Android expired remote-route QR recovery action, Android trusted composer readiness lock, Android composer readiness hint, Android composer input readiness accessibility state, Android send button readiness accessibility state, Android composer primary action click labels, Android composer attach action accessibility state, Android composer attachment count limit accessibility, Android attachment-only prompt resource localization, Android attachment picker single-dispatch guard, Android bounded attachment read guard, Android streaming cancel Compose action, Android attachment chip accessibility state, Android attachment remove disabled reason, Android attachment size locale formatting, Android message attachment accessibility state, Android message role accessibility summaries, Android assistant identity marker, Android message copy accessibility labels, Android copy success live-region accessibility, Android code block copy accessibility labels, Android multi-code-block copy action labels, Android backend readiness banner accessibility summary, Android generic error banner accessibility summary, Android provider diagnostics expanded state, Android provider diagnostics named accessibility labels, Android provider diagnostics action labels, Android provider row accessibility summaries, Android reasoning accessibility summary, Android jump-to-latest Compose interaction, Android jump-to-latest compact layout, Settings expandable section accessibility state, Settings expandable section duplicate icon semantics guard, Settings preference option accessibility summaries, Settings diagnostic endpoint expander accessibility state, Settings connection switch state accessibility, Settings discovered route contextual action accessibility, Settings discovered route unavailable accessibility summaries, Android discovered trusted-route row compact layout, Android embedding model row accessibility summaries, Settings embedding model streaming lockout accessibility state, Settings memory contextual action accessibility, Settings memory capped action accessibility labels, Settings memory add readiness accessibility state, Settings memory destructive confirmation haptic timing, chat history destructive confirmation haptic timing, confirmation-open lightweight haptic timing, Settings expired-route primary QR action, Android connected Settings redundant-connect guard, Android trusted-runtime forget confirmation, Settings pairing section resync, language alias selection normalization, legacy Python relay allocation-guard, Android no-device Compose screen smoke with five-language pairing copy, Settings diagnostic endpoint visibility guard, chat history bulk action hiding and two-step confirmation, chat history bulk expander accessibility state, chat history bulk action disabled accessibility state, chat history per-chat contextual action accessibility, chat history per-chat disabled accessibility state, chat history row accessibility summaries, Android rename chat readiness accessibility state, Android rename chat action labels, full five-language light/dark Chat/Settings/Connection layout matrix, reasoning toggle, chat top-bar model/embedding picker separation, selected model-picker plus Settings preference and embedding-model accessibility state, fake haptic callback dispatch, connection notice haptic callback dispatch, runtime-owned streaming storage redaction, pending relay QR retry, Android pending relay QR secret-store boundary, Android pending relay QR secret cleanup, relay QR completion persistence, real RuntimeRelayTcpClient app pairing path, relay-before-Bonjour fallback, and trusted relay app-init auto-reconnect."
echo "Covered addendum: Android OS app-language handoff, Android follow system language preference, Android translated Memory noun, macOS menu-bar status and command localization, macOS quick action accessibility hints, macOS menu-bar quick action accessibility parity, macOS menu-bar window and quit accessibility hints, macOS first-run Pairing QR primary action ordering, macOS Connection Recovery private-overlay toggle accessibility labels, macOS Connection Recovery and diagnostics disclosure accessibility state, macOS Connection Recovery Save Connection input state, macOS Connection Recovery Save Bootstrap Relay input state, macOS Connection Recovery bootstrap allocation token warning, macOS Connection Recovery host warning accessibility status, macOS Connection Recovery bootstrap relay removal accessibility labels, macOS Connection Recovery destructive removal action hints, macOS menu-bar Pairing QR active-session title, macOS Pairing QR route notice accessibility status, macOS Connection Recovery fallback-action accessibility hints, macOS CJK page-header accessibility spacing, macOS trusted-device refresh accessibility hint, Android trusted-runtime forget named accessibility label, Android trusted-runtime forget named click label, Android trusted-runtime forget confirmation action labels, Android trusted-runtime forget confirmation named message, Settings discovery action accessibility states, Settings discovery action accessibility labels, Android streaming cancel accessibility state, Android jump-to-latest accessibility state, Android jump-to-latest action labels, Android connected action accessibility states, Android connected action accessibility labels, Android connected action reconnect lockout, Android backend readiness refresh accessibility state, Android backend readiness refresh action labels, Android backend readiness banner bounded layout, Android generic runtime error banner bounded layout, Android model refresh action accessibility labels, Android route notice action accessibility labels, Android route notice accessibility summaries, Android route notice accessibility state, Android route notice QR recovery steps, Android connection status incomplete relay route live-region recovery, Android primary pairing cross-network route copy, Android pairing primary action accessibility labels, Android trusted-route connect label, Android manual diagnostic host QR-first guard, Android relay auth failure QR recovery notice, Android relay auth failure auto-retry stop, Android relay auth failure post-clear QR action, Android relay auth failure empty-chat copy, Android route rejection empty-chat copy, Android expired route empty-chat copy, Android expired remote-route QR recovery localization, Android expired relay route purge, Android relay secret store boundary, Android relay secret Base64 boundary, macOS relay secret store boundary, Android route.refresh terminal expiry state guard, Android QR runtime-name normalization, Android PairingStore incomplete relay cleanup, Android New Chat pairing-required disabled reason, Android New Chat action labels, Android permanent rail New Chat pairing gate, Android permanent rail Chat pairing gate, Android drawer rich chat search, Android drawer chat date grouping, Android drawer chat model metadata, Android chat history display-model search, Android drawer saved missing model recovery, Android drawer streaming lockout accessibility state, Android chat top-bar model picker streaming disabled state, Android chat top-bar model picker streaming transition lockout, Android chat top-bar stale saved model suppression, Android chat top-bar saved missing model recovery, Android chat top-bar compact long model name, Android chat top-bar model refresh action accessibility state, Android unknown model install guard, Android chat top-bar active chat title, Android chat top-bar model picker closed-button accessibility summary, Android chat top-bar model row action labels, Android search clear action labels, Android composer keyboard Send action, Android composer latest QR readiness hint, Android attachment-only composer readiness state, Android composer readiness live-region accessibility, Android route-recovery empty-state live-region accessibility, Android latest QR empty-state callback routing, Android chat empty-state primary action labels, Android reasoning toggle action labels, Android streaming assistant live-region accessibility, Settings expandable section action accessibility labels, Settings switch action accessibility labels, Settings memory action accessibility labels, Settings memory streaming lockout accessibility state, Settings memory add action accessibility labels, Settings memory add success live-region accessibility, Settings memory empty-state live-region accessibility, Settings memory delete confirmation action labels, Settings chat history model metadata, Android memory input readiness accessibility state, chat history bulk expander action labels, chat history bulk action accessibility labels, chat history destructive confirmation and cancel action labels."
echo "Covered Settings compact addendum: Android Settings trusted-runtime panel compact layout."
echo "Covered QR lease addendum: near-expiry remote relay lease QR renewal."
echo "Covered relay probe addendum: non-consuming relay readiness probe and Android route-level relay preflight."
echo "Covered QR production bootstrap addendum: QR production relay bootstrap verifier requires runtime public key, route token, and complete relay route material."
echo "Covered Android product QR bootstrap addendum: normal QR scans require runtime public key, route token, and complete remote route material; diagnostic identity-only fallback must opt out explicitly."
echo "Covered accepted pairing addendum: Android incomplete relay route material fails closed instead of falling back to direct endpoint."
echo "Covered rejected pairing addendum: Android rejected relay QR pairing clears pending route material, stale pairing code, and pending relay secret references."
echo "Covered accepted pairing direct-endpoint cleanup addendum: Android accepted pairing drops direct endpoint material before trusted runtime storage."
echo "Covered stale relay refresh addendum: Android authenticated route.refresh keeps the current relay route and schedules retry when refreshed relay material reuses the active nonce or lease."
echo "Covered Android authenticated route.refresh default-off addendum: production Android does not advertise or send authenticated route.refresh unless explicitly enabled for diagnostic coverage."
echo "Covered PairingStore direct endpoint cleanup addendum: Android trusted runtime persistence drops current and legacy direct host/port fields."
echo "Covered pending pairing direct-endpoint cleanup addendum: Android pending pairing route storage drops direct QR host/port fields."
echo "Covered trusted route fallback addendum: Android trusted reconnect drops trusted last-known direct endpoint fallback."
echo "Covered trusted route UI addendum: Android route UI treats trusted last-known direct endpoints as latest-QR recovery."
echo "Covered trusted route core addendum: Android core transport default resolver ignores trusted last-known direct endpoints."
echo "Covered P2P route prep addendum: Android p2p_rendezvous route preparation contract and relay fallback ordering."
echo "Covered P2P QR planning addendum: Android QR-carried opaque P2P rendezvous records persist as pending route material and plan before relay."
echo "Covered P2P trusted-runtime restore addendum: Android trusted P2P rendezvous material persists after accepted pairing and restores as a prepared remote route without direct endpoint fallback."
echo "Covered long-inactivity memory summary draft protocol listing addendum: authenticated memory.summary.drafts.list returns owner-scoped active visible-transcript drafts without writing runtime memory."
echo "Covered Android memory summary draft review addendum: Android requests memory.summary.drafts.list, renders suggested memories in Settings Memory, approves memory.summary.draft.approve, and keeps draft previews out of device storage."
echo "Covered long-inactivity memory summary draft approval addendum: authenticated memory.summary.draft.approve writes idempotent owner-scoped runtime memory and hides approved drafts from later review lists."
echo "Covered long-inactivity memory summary draft dismiss addendum: authenticated memory.summary.draft.dismiss stores owner-scoped dismiss decisions, hides dismissed drafts, and does not write runtime memory."
echo "Covered approved memory source metadata addendum: approved long-inactivity memory entries preserve bounded visible-transcript source metadata through runtime storage, memory.list, protocol DTOs, and Android in-memory state while device storage remains redacted."
echo "Covered approved memory source review UI addendum: Android Settings Memory shows approved-memory source metadata on demand without exposing the full transcript by default."
echo "Covered P2P canonical material addendum: Android pending, trusted, and route.refresh P2P rendezvous records reject whitespace-mutated opaque route values."
echo "Covered P2P app route addendum: Android ViewModel injects a P2P connector, attempts saved opaque P2P before relay, and falls back to relay without direct endpoint fallback."
echo "Covered P2P route-refresh lease addendum: Android P2P-only trusted routes schedule, retry, and expire route.refresh renewal from the P2P rendezvous record lease."
echo "Covered P2P route-refresh replay addendum: Android route.refresh rejects reused or non-advancing P2P rendezvous records before storage."
echo "Covered stale P2P refresh addendum: Android authenticated route.refresh keeps the current P2P rendezvous route and schedules retry when refreshed P2P material reuses the active record or lease."
echo "Covered macOS P2P QR generation addendum: macOS pairing QR generation emits the shared opaque P2P rendezvous record family."
echo "Covered runtime mock attachment addendum: authenticated relay chat.send document attachment and non-vision image rejection smoke."
echo "Covered relay ciphertext boundary addendum: authenticated relay smoke checks encrypted frame bodies for model, chat, attachment, cancel, history, and memory plaintext markers."
echo "Covered macOS RelayPeerClient ciphertext addendum: macOS RelayPeerClient sends nonce-bound encrypted runtime frame bodies after relay readiness."
echo "Covered Android relay TCP ciphertext addendum: Android RuntimeRelayTcpClient encrypts sent frame bodies and decrypts nonce-bound runtime responses on a real socket channel."
echo "Covered runtime pairing relay smoke addendum: RuntimeDevServer relay rejected pairing request leaves device untrusted before accepted pairing."
echo "Covered runtime auth relay smoke addendum: RuntimeDevServer relay unauthenticated runtime command and untrusted hello rejection."
echo "Covered RuntimeDevServer malformed pairing identity smoke addendum: RuntimeDevServer relay malformed pairing identity rejection keeps the device untrusted while preserving the active QR for a later valid pairing."
echo "Covered RuntimeDevServer consumed pairing QR reuse smoke addendum: RuntimeDevServer relay rejects consumed pairing QR reuse and keeps the second device untrusted."
echo "Covered RuntimeDevServer rejected pairing connection auth-boundary addendum: RuntimeDevServer relay keeps rejected and consumed pairing connections unauthenticated."
echo "Covered RuntimeDevServer raw nonce auth relay smoke addendum: RuntimeDevServer relay rejects raw nonce auth signatures and keeps the connection unauthenticated."
echo "Covered RuntimeDevServer auth replay relay smoke addendum: RuntimeDevServer relay rejects replayed auth responses and superseded challenge nonces while preserving valid auth paths."
echo "Covered runtime auth revocation smoke addendum: RuntimeDevServer relay trusted-device revocation clears authenticated sessions."
echo "Covered physical relay QA addendum: Android device relay-id readiness probe and external-relay summary artifacts."
echo "Covered Android QR policy addendum: Android product QR remote-route requirement and identity-only scanner rejection."
echo "Covered Android chat history addendum: Settings chat history selected active chat state."
echo "Covered Android chat empty-state addendum: Android no-model empty chat header picker guidance."
echo "Covered Android chat empty-state addendum: Android uninstalled selected model install-or-choose guidance."
echo "Covered provider addendum: Android provider label normalization."
echo "Covered runtime provider addendum: macOS duplicate provider registration guard."
echo "Covered model-residency smoke addendum: macOS model-switch unload, same-model unload suppression, idle-timeout unload, provider-specific unload-failure reporting, Ollama unload wire format, and LM Studio unload wire format."
echo "Covered runtime auth gate addendum: unauthenticated models.list, models.pull, chat.send, chat.cancel, route.refresh, chat history/title/session mutation, and memory list/upsert/delete command rejection."
echo "Covered route.refresh addendum: route.refresh malformed relay material validation, route.refresh private-overlay and usb-reverse scoped relay material validation."
echo "Covered route.refresh relay freshness addendum: Android route.refresh rejects reused relay nonces or non-advancing relay leases before storage while allowing stable relay id/secret reuse."
echo "Covered route.refresh P2P addendum: authenticated route.refresh can carry complete opaque P2P rendezvous material without claiming real P2P traversal."
echo "Covered RuntimeDevServer route.refresh P2P smoke addendum: authenticated relay smoke validates complete opaque P2P rendezvous material from RuntimeDevServer."
echo "Covered RuntimeDevServer history/title/session lifecycle/memory smoke addendum: authenticated relay smoke positively validates chat.sessions.list, chat.messages.list, chat.title.request, chat.session rename/archive/restore/delete, memory.upsert, memory.list, and memory.delete over RuntimeDevServer."
echo "Covered runtime session search addendum: chat.sessions.list query filters runtime-owned titles, model ids, and sanitized transcript text inside owner/archive/delete boundaries, with deterministic ranking, bounded snippets, Android query/search DTO serialization, trimmed request plumbing, Settings chat-history search refresh query forwarding, Settings chat-history runtime search match metadata, RuntimeDevServer chat.sessions.list query search metadata smoke, and SQLite/FTS event-store parity plus JSONL-to-SQLite backfill, SQLite default-store rollout, and SQLite deleted-session retention pruning for sessions, messages, owner/archive/delete lifecycle, inline-byte redaction, corrupt-log handling, idempotency, legacy-file freshness, tombstone-backed legacy resurrection prevention, and search metadata."
echo "Covered runtime reasoning search metadata addendum: chat.sessions.list can match stored assistant reasoning separately from visible answer text across JSONL router and SQLite/FTS paths, and Android Settings labels reasoning matched fields."
echo "Covered context-window compaction addendum: models.result carries optional context_window_tokens, Android preserves the metadata, Ollama/LM Studio parse context-window hints, and macOS chat.send uses resolved model context windows to choose runtime compaction budget."
echo "Covered long-inactivity memory summarization eligibility addendum: runtime-host policy selects only owner-scoped, active, sufficiently old, sufficiently long chat sessions as future memory-summary candidates, and builds deterministic long-inactivity memory summary drafts/source pointers from visible transcript text without writing runtime memory."
echo "Covered runtime archive polish addendum: chat.send into archived runtime sessions returns a restore-required structured error before backend dispatch or chat-event mutation."
echo "Covered RuntimeDevServer multi-device owner isolation smoke addendum: authenticated relay smoke validates memory, chat session, message, and session mutation owner-device boundaries across two trusted devices."
echo "Covered RuntimeDevServer model-residency smoke addendum: authenticated relay smoke validates aggregate mock model-switch unload, same-model unload suppression, and idle unload through RuntimeDevServer."
echo "Covered relay/auth hardening addendum: Android relay preparation explicit relay_id route material, macOS auth response replayed nonce rejection, macOS superseded challenge nonce rejection."
echo "Covered macOS menu-bar addendum: macOS menu-bar status accessibility labels."
echo "Covered macOS dialog addendum: macOS trusted-device cancel-remove action accessibility labels, macOS saved connection details cancel accessibility label."
echo "Covered macOS status addendum: macOS model-provider empty-state accessibility labels, macOS provider status decorative icon hiding, macOS runtime data status cards, macOS runtime history saved/archived status card summary, macOS runtime memory saved/paused status card summary, macOS runtime data all-owner summary, macOS runtime data summary error recovery, macOS runtime memory inspector, macOS runtime history inspector, macOS runtime history inspector saved/archived summary, macOS runtime history transcript preview."
echo "Covered macOS model layout addendum: macOS compact long model row render smoke."
echo "Covered macOS large-text addendum: macOS large accessibility text sidebar preference render."
echo "Covered macOS sidebar preference addendum: macOS sidebar App Preferences group label, macOS sidebar preference detail copy."
echo "Covered macOS route recovery addendum: macOS failed saved connection recovery requires a fresh QR."
echo "Covered macOS QR-only pairing addendum: clean first-run Pairing hides Connection Recovery unless saved route diagnostics or a route-preparation issue exists."
echo "Covered runtime history addendum: Android runtime history message-count clamp, macOS runtime history message-count clamp, macOS chat.cancel runtime-owned cancelled event, macOS connection-close generation cancellation."
echo "Covered macOS P2P route material redaction addendum: macOS Activity diagnostics, route diagnostics, and companion logs redact p2p_rendezvous record IDs, encrypted bodies, anti-replay nonces, expiries, protocol versions, and compact P2P aliases."
echo "Covered readiness addendum: macOS runtime overview installed-local model readiness, macOS readiness row fallback accessibility, macOS trusted-device missing-date ID accessibility, Android streaming chat input mutation guard, Android streaming send reentrancy guard, Android streaming attachment mutation guard, Android streaming embedding-model selection guard, Android streaming memory mutation guard, Android streaming route/trust mutation guard, Android stream termination reasoning closure, Android runtime-owned stale message resurrection guard, Android runtime-owned local memory storage redaction, Android runtime memory client-prompt suppression, Android runtime lifecycle local-session collision guard, Android unreachable route-refresh QR cleanup guard, Android route.refresh sensitive detail minimization, Android pending relay QR secret-store boundary, Android pending relay QR secret cleanup, Android runtime technical error detail storage boundary, Android safe runtime technical diagnostics surface, Android share-sheet intake, Android explicit share-sheet MIME scope, Android private-overlay real relay TCP pairing path, Android private-overlay real relay TCP reconnect path, Android device identity Base64 signature guard, Android device identity persistence guard, Android QR trust value whitespace guard, Android/macOS client auth domain separation, macOS pairing trusted-device identity validation, macOS auth session disconnect cleanup, macOS trusted-device removal live-session revocation, macOS relay line framing newline guard, macOS relay disconnect callback idempotency, macOS local peer disconnect callback idempotency, macOS route material diagnostic redaction, macOS attachment prompt storage separation, macOS trusted-device store file permission hardening, macOS runtime identity fallback file permission hardening, macOS runtime event-log file permission hardening, macOS runtime history router nonpositive-limit guard, macOS runtime history nonpositive limit guard, macOS runtime history zero-limit corrupt-log bypass, macOS runtime history semantic corruption visibility, macOS runtime memory corrupt-log visibility, macOS runtime memory semantic corruption visibility, macOS authenticated runtime history and memory owner-device scoping."
echo "Covered Android settings addendum: Android preference group heading semantics, Android Settings panel heading semantics, Settings preference option action labels, Android Settings private model access live-region summary, Android drawer section heading semantics, Android drawer empty-history live-region accessibility, Android drawer Settings footer action semantics, Android drawer Settings footer readiness state, Android permanent rail Settings action semantics, Android permanent rail Settings readiness state, Android chat search no-results live-region accessibility, Android model search no-results live-region accessibility, Android streaming assistant content live-region accessibility, Android model picker empty-state live-region accessibility, Android embedding model empty-state live-region accessibility, Android open reasoning collapsed live-region accessibility, Android open reasoning live-region accessibility, Android short reasoning static accessibility state, Android memory delete confirmation named message, Android memory manual runtime refresh, Android chat history manual runtime refresh, Android Settings chat history open-chat action, Android Settings chat-history search result action context, Android runtime chat mutation error resync, Android runtime data load error surfacing."
echo "Covered Android Settings embedding model compact row layout."
echo "Covered Android Settings auto-reconnect compact row layout."
echo "Covered Android Settings preference compact row layout."
echo "Covered Android Settings section header compact layout."
echo "Covered language/trust copy addendum: Android appearance system detail copy, Android follow-system language callback dispatch, Android follow-system selected preference state, and macOS Trusted Devices runtime requests empty-state copy."
echo "Covered Android localization addendum: Android French chat accessibility copy."
echo "Covered Android accessibility addendum: Android attachment-only message role accessibility."
echo "Covered suggested-question removal tombstone addendum: active code/protocol paths forbid chat.suggestions and suggested-question UI symbols."
echo "Covered Android layout addendum: Android ChatGPT-like chat surface narrow-phone layout regression, Android populated Settings history and Memory narrow-phone render, Android drawer chat row compact layout, Android drawer runtime summary compact layout, Android provider status compact diagnostic layout, Android connection status panel compact layout, Android Settings QR pairing panel compact first-run layout, Android Settings memory compact long-content actions layout, Android Settings chat-history compact row actions, Android Settings chat-history bulk action compact layout, Android memory summary draft compact review layout, Android read-only attachment chip wrapping, Android pending attachment chip wrapping, Android text-only draft composer controls compact layout, Android streaming cancel composer controls compact layout, Android streaming assistant progress decorative compact layout, Android composer readiness status compact layout, Android chat route availability notice compact layout, Android markdown table and code block compact layout, Android Settings memory saved/paused summary localization, Android markdown message rendering, Android assistant response regenerate action, Android latest user-message draft reuse action, Android latest message action localized states, Android latest message action wrapping, Android transcript role-change spacing rhythm, Android model picker vision recovery compact row layout, Android localized clipboard payload labels, Android composer clear-draft action, Android composer clear-draft localized state, Android clear-draft attachment cleanup, Android composer draft persistence, Android session-scoped composer draft switching, Android transient attachment cleanup on chat switching, Android transient attachment cleanup on chat lifecycle exits, Android runtime transcript loading state, Android runtime transcript lifecycle mutation lockout, Android empty-state latest-QR composer alignment."
echo "Covered Android large-font chat addendum: Android large-font multilingual Chat render."
echo "Covered Android large-font layout addendum: Android large-font multilingual Settings render."
echo "Covered Android layout detail addendum: Android Settings chat-history saved/archived summary localization, Android markdown heading accessibility, Android markdown table accessibility, Android code block accessibility summary."
echo "Covered Android share addendum: Android share-sheet import confirmation, Android share-sheet import haptic feedback, Android share-sheet content URI boundary."
echo "Covered Android scanner addendum: Android QR scanner compact pairing-state render smoke, Android QR scanner compact large-font bounds, Android QR scanner scan-target accessibility label, Android QR scanner invalid-code recovery."
echo "Covered Android diagnostics addendum: Android diagnostic QR text open action labels."
echo "Covered app icon addendum: no-device Android launcher and macOS Dock small-size readability plus asset-chain validation."
echo "Physical external-relay QA gate: script/check_physical_external_relay_pairing.sh --relay-host <public-or-vpn-host> writes build/qa/android-external-relay-pairing.json and must be run with a real attached phone on the target network."
echo "Not covered by this no-device gate: physical install, camera QR scan, real device haptics, physical TalkBack/VoiceOver traversal, Android system/per-app locale mutation on hardware, launcher/Dock screenshots, physical/live-backend streamed chat/cancel, and real different-network runtime connectivity."
