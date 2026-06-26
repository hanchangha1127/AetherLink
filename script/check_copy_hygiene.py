#!/usr/bin/env python3
"""Check user-facing copy for stale prototype wording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CopyRule:
    name: str
    pattern: re.Pattern[str]
    guidance: str


RULES = (
    CopyRule(
        "companion-runtime",
        re.compile(r"\bcompanion runtime\b", re.IGNORECASE),
        "Use AetherLink Runtime or runtime host.",
    ),
    CopyRule(
        "legacy-companion-copy",
        re.compile(
            r'"(?:Open Companion|Companion Status|Recent companion activity from this runtime host session\.|Events will appear here after the companion starts receiving activity\.|Companion started|Companion stopped)"'
            r"|\bOpen Companion\b|\bCompanion Status\b",
            re.IGNORECASE,
        ),
        "Use AetherLink Runtime wording for visible copy and localization fallback keys.",
    ),
    CopyRule(
        "backend-status",
        re.compile(
            r"\b(Backend is reachable|Backend status|Backend needs attention|Refresh Backend Status|Backend:\s*%@)\b",
            re.IGNORECASE,
        ),
        "Use model provider or model service wording.",
    ),
    CopyRule(
        "local-model-backend",
        re.compile(r"\b(local model backend|local backend(?:\\(s\\))?|No local model backend|%d local backend)", re.IGNORECASE),
        "Use model provider or model service wording.",
    ),
    CopyRule(
        "legacy-local-backends-heading",
        re.compile(r'"Local Backends"'),
        "Use Model Providers for visible headings.",
    ),
    CopyRule(
        "mac-route-copy",
        re.compile(r"\b(this Mac to the relay|connect this Mac to the relay)\b", re.IGNORECASE),
        "Use runtime host or remote route wording.",
    ),
    CopyRule(
        "desktop-host-copy",
        re.compile(
            r"\b(this computer|this Mac|on this computer|from this computer|keep this computer)\b",
            re.IGNORECASE,
        ),
        "Use runtime host wording so copy is not tied to one desktop OS.",
    ),
    CopyRule(
        "platform-specific-os-copy",
        re.compile(r"\b(?:Mac|macOS|Android|Windows|iPhone|iOS)\b"),
        "Use client, device, runtime, runtime host, or target-neutral wording in product UI.",
    ),
    CopyRule(
        "client-device-copy",
        re.compile(r"\bclient device(?:s)?\b|\bclient app(?:s)?\b", re.IGNORECASE),
        "Use device, trusted device, or AetherLink wording.",
    ),
    CopyRule(
        "local-runtime-copy",
        re.compile(r"\bthis local runtime\b|\blocal runtime\b", re.IGNORECASE),
        "Use AetherLink Runtime or runtime host.",
    ),
    CopyRule(
        "paired-computer",
        re.compile(r"\bpaired computer\b", re.IGNORECASE),
        "Use trusted runtime or runtime host.",
    ),
    CopyRule(
        "generic-chat-placeholder",
        re.compile(r"\bAsk anything\b|무엇이든 부탁", re.IGNORECASE),
        "Keep the chat composer visually quiet unless a real warning is needed.",
    ),
    CopyRule(
        "chat-composer-placeholder-api",
        re.compile(r"\b(?:chat_input_placeholder|composer_placeholder|placeholderText)\b", re.IGNORECASE),
        "Do not add a visible chat composer placeholder; keep accessibility labels separate.",
    ),
    CopyRule(
        "direct-model-url-copy",
        re.compile(r"\b(enter .*Ollama|enter .*LM Studio|Ollama URL|LM Studio URL)\b", re.IGNORECASE),
        "Clients should pair/connect to AetherLink Runtime, not enter model-provider URLs.",
    ),
    CopyRule(
        "manual-route-copy",
        re.compile(r"\bmanual route\b|\bfixed IP\b|\bfixed address\b", re.IGNORECASE),
        "Use QR-first, remote route, or diagnostics route wording.",
    ),
)

MACOS_LOCALIZED_STRING_RE = re.compile(r'NSLocalizedString\("((?:\\.|[^"\\])*)"')
MACOS_STRINGS_ENTRY_RE = re.compile(
    r'^\s*"(?P<key>(?:\\.|[^"\\])*)"\s*=\s*"(?P<value>(?:\\.|[^"\\])*)"\s*;\s*$'
)
MACOS_STALE_VISIBLE_COPY_RE = re.compile(
    r"Runtime listener|authenticated runtime sessions|Route Diagnostics|Runtime Diagnostics|"
    r"route material|runtime identity|local discovery path|Remote Route|Remote route|"
    r"Advanced Route Setup|Route address|route address|route host|Route host|Route setup secret|Route secret|"
    r"Save Remote Route|Disable Remote Route|remote route|local route|"
    r"Provider Diagnostics|No diagnostics yet|No runtime logs|"
    r"Connection Routes|configured route|Save Route|route QR|route settings|"
    r"route port|Relay route|development transport|"
    r"Show diagnostics|Hide diagnostics|saved connection settings",
    re.IGNORECASE,
)
MACOS_STALE_LOCALIZATION_VALUE_RE = re.compile(
    r"^(?:Technical Details|Provider endpoint redacted\.|Advanced Connection Setup|"
    r"Connection Setup|Connection setup secret|Connection setup secret regenerated\.)$",
    re.IGNORECASE,
)
CLOUD_MODEL_SOURCE_LABEL_RE = re.compile(
    r'name="model_source_cloud"\b|'
    r'NSLocalizedString\("Cloud"\b|'
    r'^\s*"Cloud"\s*=|'
    r'>\s*(?:Cloud|클라우드|クラウド|云端)\s*<',
    re.IGNORECASE,
)
CLOUD_DEFAULT_RECOMMENDED_RE = re.compile(
    r"\b(?:"
    r"cloud[- ]?(?:default|recommended)|"
    r"(?:default|recommended)[- ]?cloud|"
    r"(?:default|recommend(?:ed)?|prefer(?:red)?)\s+(?:to\s+)?(?:a\s+)?cloud\s+model|"
    r"cloud\s+model\s+(?:is\s+)?(?:the\s+)?(?:default|recommended|preferred)"
    r")\b",
    re.IGNORECASE,
)
ANDROID_DIRECT_BACKEND_ENDPOINT_PATTERNS = (
    re.compile(r"https?://[A-Za-z0-9.-]+:(?:11434|1234)\b", re.IGNORECASE),
    re.compile(r"https?://\[[0-9A-Fa-f:]+]:(?:11434|1234)\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9.-]+:(?:11434|1234)\b", re.IGNORECASE),
    re.compile(r"\[[0-9A-Fa-f:]+]:(?:11434|1234)\b", re.IGNORECASE),
    re.compile(r"/(?:api/(?:tags|ps|pull|chat|show|v1)|v1/(?:models|chat|chat/completions))\b", re.IGNORECASE),
    re.compile(r"\bapi/v1/(?:models|chat|models/unload)\b", re.IGNORECASE),
    re.compile(r"\bbaseUrl\b|\bbackendUrl\b|\bproviderUrl\b", re.IGNORECASE),
)
ANDROID_DIRECT_BACKEND_ENDPOINT_ALLOWED_SNIPPETS = (
    "LOCAL_MODEL_BACKEND_PORTS = setOf(11434, 1234)",
    "if (hint.port in LOCAL_MODEL_BACKEND_PORTS)",
)


def target_files() -> list[Path]:
    targets: list[Path] = []
    target_globs = (
        "apps/android/app/src/main/res/values*/strings.xml",
        "apps/android/app/src/main/java/**/*.kt",
        "apps/macos/LocalAgentBridgeApp/Sources/**/*.swift",
        "apps/macos/LocalAgentBridgeApp/Sources/Resources/**/*.strings",
        "apps/macos/CompanionCore/Sources/**/*.swift",
        "apps/macos/Pairing/Sources/**/*.swift",
        "apps/macos/OllamaBackend/Sources/**/*.swift",
        "apps/macos/LMStudioBackend/Sources/**/*.swift",
        "apps/macos/RuntimeDevServer/Sources/**/*.swift",
        "script/android_usb_install.sh",
        "script/android_usb_smoke.sh",
        "script/run_runtime_dev_server.sh",
        "script/run_different_network_dev_runtime.sh",
        "script/android_pairing_deeplink_smoke.sh",
        "script/no_adb_external_relay_pairing_smoke.sh",
        "script/run_allocation_relay.sh",
    )
    for pattern in target_globs:
        targets.extend(ROOT.glob(pattern))
    return sorted(path for path in targets if path.is_file())


def route_diagnostics_guard_failures() -> list[str]:
    failures: list[str] = []
    helper_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/RemoteRelayRoutePanel.swift"
    helper_text = helper_path.read_text(encoding="utf-8", errors="replace")
    helper_signature = "@MainActor\nfunc shouldShowRouteDiagnosticsPanel(model: CompanionAppModel) -> Bool"
    helper_rule_snippets = (
        "model.hasDevelopmentRelayRoute",
        "!model.canPrepareRemoteRelayRouteAutomatically",
        "model.remoteRoutePreparationIssue != nil",
    )

    if helper_signature not in helper_text or any(snippet not in helper_text for snippet in helper_rule_snippets):
        failures.append(
            "apps/macos/LocalAgentBridgeApp/Sources/RemoteRelayRoutePanel.swift: "
            "Route Diagnostics visibility must stay centralized behind "
            "shouldShowRouteDiagnosticsPanel(model:)."
        )

    guarded_views = (
        ROOT / "apps/macos/LocalAgentBridgeApp/Sources/PairingView.swift",
        ROOT / "apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift",
    )
    guard_line = "if shouldShowRouteDiagnosticsPanel(model: model) {"
    for path in guarded_views:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"\bRemoteRelayRoutePanel\s*\(", text):
            preceding = text[max(0, match.start() - 160):match.start()]
            if guard_line not in preceding:
                relative = path.relative_to(ROOT)
                line_number = text.count("\n", 0, match.start()) + 1
                failures.append(
                    f"{relative}:{line_number}: Route Diagnostics must be hidden from normal QR pairing "
                    "unless automatic remote route preparation is unavailable or a diagnostic route exists."
                )

    return failures


def android_troubleshooting_guard_failures() -> list[str]:
    failures: list[str] = []
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    ui_relative = ui_path.relative_to(ROOT)
    text = ui_path.read_text(encoding="utf-8", errors="replace")

    helper_signature = "internal fun settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics: Boolean): Boolean"
    helper_rule = "return showDeveloperDiagnostics"
    if helper_signature not in text or helper_rule not in text:
        failures.append(
            f"{ui_relative}: Settings troubleshooting visibility must stay centralized behind "
            "settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics)."
        )

    settings_start = text.find("fun SettingsScreen(")
    settings_end = text.find("internal fun settingsScreenShowsGenericHeader", settings_start)
    if settings_start == -1 or settings_end == -1:
        failures.append(f"{ui_relative}: could not locate SettingsScreen visibility guard region.")
        return failures

    settings_body = text[settings_start:settings_end]
    guard_call = "settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics)"
    if guard_call not in settings_body:
        failures.append(
            f"{ui_relative}: SettingsScreen must gate troubleshooting UI through "
            "settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics)."
        )

    raw_flag_pattern = re.compile(r"\bif\s*\(\s*showDeveloperDiagnostics\s*\)")
    if raw_flag_pattern.search(settings_body):
        failures.append(
            f"{ui_relative}: SettingsScreen must not gate visible troubleshooting UI with a raw "
            "showDeveloperDiagnostics check."
        )

    app_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt"
    app_relative = app_path.relative_to(ROOT)
    app_text = app_path.read_text(encoding="utf-8", errors="replace")
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    test_relative = test_path.relative_to(ROOT)
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    settings_call_pattern = re.compile(r"SettingsScreen\s*\((?P<body>.*?)\n\s*\)", re.DOTALL)
    settings_call = settings_call_pattern.search(app_text)
    if settings_call is None:
        failures.append(f"{app_relative}: could not locate SettingsScreen app wiring.")
    else:
        call_body = settings_call.group("body")
        if "showDeveloperDiagnostics = showDeveloperDiagnostics" not in call_body:
            failures.append(
                f"{app_relative}: SettingsScreen must receive the launch-gated showDeveloperDiagnostics value "
                "so default app entry stays QR-only."
            )
    required_app_snippets = (
        "internal fun shouldEnableDeveloperDiagnostics(",
        "return isDebugBuild && requestedByLaunch",
        "intent.developerDiagnosticsRequested()",
        "DEVELOPER_DIAGNOSTICS_EXTRA",
    )
    for snippet in required_app_snippets:
        if snippet not in app_text:
            failures.append(
                f"{app_relative}: Android developer diagnostics must require both a debug build "
                "and an explicit launch request."
            )
    if "developerDiagnosticsRequireDebugBuildAndExplicitLaunchRequest" not in test_text:
        failures.append(
            f"{test_relative}: Missing regression test for launch-gated Android developer diagnostics."
        )

    return failures


def android_line_contains_direct_backend_endpoint(line: str) -> bool:
    if any(snippet in line for snippet in ANDROID_DIRECT_BACKEND_ENDPOINT_ALLOWED_SNIPPETS):
        return False
    return any(pattern.search(line) for pattern in ANDROID_DIRECT_BACKEND_ENDPOINT_PATTERNS)


def android_runtime_boundary_matcher_self_test_failures() -> list[str]:
    failures: list[str] = []
    unsafe_samples = (
        'val url = "http://192.168.1.23:11434/api/tags"',
        'val url = "http://[::1]:1234/v1/models"',
        'val endpoint = "GET /api/tags"',
        'val endpoint = "api/v1/models"',
        'val providerUrl = userInput',
        'val socket = "model-provider.example.test:1234"',
    )
    safe_samples = (
        'val route = "127.0.0.1:43170"',
        'val route = "relay.example.test:43171"',
        'private val LOCAL_MODEL_BACKEND_PORTS = setOf(11434, 1234)',
        'if (hint.port in LOCAL_MODEL_BACKEND_PORTS) return false',
        'Regex("https?://[^\\\\s,;)]+", RegexOption.IGNORE_CASE)',
    )

    for sample in unsafe_samples:
        if not android_line_contains_direct_backend_endpoint(sample):
            failures.append(
                "script/check_copy_hygiene.py: Android runtime-boundary matcher missed "
                f"unsafe sample {sample!r}"
            )

    for sample in safe_samples:
        if android_line_contains_direct_backend_endpoint(sample):
            failures.append(
                "script/check_copy_hygiene.py: Android runtime-boundary matcher rejected "
                f"safe sample {sample!r}"
            )

    return failures


def android_runtime_boundary_guard_failures() -> list[str]:
    failures: list[str] = []
    manifest_path = ROOT / "apps/android/app/src/main/AndroidManifest.xml"
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    runtime_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt"
    main_activity_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt"
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    runtime_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt"
    manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")
    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    main_activity_text = main_activity_path.read_text(encoding="utf-8", errors="replace")
    runtime_text = runtime_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    runtime_test_text = runtime_test_path.read_text(encoding="utf-8", errors="replace")
    source_patterns = (
        "apps/android/app/src/main/**/*.kt",
        "apps/android/core/*/src/main/**/*.kt",
        "apps/android/app/src/main/res/values*/strings.xml",
    )
    android_files: list[Path] = []
    for pattern in source_patterns:
        android_files.extend(ROOT.glob(pattern))

    for path in sorted({candidate for candidate in android_files if candidate.is_file()}):
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if android_line_contains_direct_backend_endpoint(line):
                failures.append(
                    f"{relative}:{line_number}: Android client code must not contain direct "
                    "Ollama or LM Studio endpoint material; route model access through AetherLink Runtime."
                )

    if 'android:scheme="aetherlink"' not in manifest_text or 'android:host="pair"' not in manifest_text:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: Android pairing deep links must remain scoped to "
            "aetherlink://pair and legacy lab://pair."
        )
    if re.search(r'<data\s+android:scheme="(?:aetherlink|lab)"\s*/>', manifest_text):
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: Android manifest must not accept broad custom-scheme "
            "links without android:host=\"pair\"."
        )
    if manifest_text.count('android:host="pair"') != 2:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: Android manifest should expose only the two pair-host "
            "schemes: aetherlink and legacy lab."
        )

    required_main_activity_snippets = (
        "RuntimePairingPayloadParser.parse(",
        "allowDebugLoopbackRelay = BuildConfig.DEBUG",
        "allowDiagnosticLocalDirectEndpoint = BuildConfig.DEBUG",
    )
    for snippet in required_main_activity_snippets:
        if snippet not in main_activity_text:
            failures.append(
                f"{main_activity_path.relative_to(ROOT)}: Android scanner raw-value acceptance must "
                "reuse the runtime pairing parser policy before closing the camera scanner."
            )

    required_route_boundary_snippets = (
        "endpoint.isAllowedDirectEndpoint() &&\n                state.isTrustedRouteEndpointAllowed",
        "endpoint.isAllowedDirectEndpoint() &&\n                discovered.matchesTrustedIdentity",
        "if (port in LOCAL_MODEL_BACKEND_PORTS) return false",
        "LOCAL_MODEL_BACKEND_PORTS = setOf(11434, 1234)",
    )
    for snippet in required_route_boundary_snippets:
        if snippet not in runtime_text:
            failures.append(
                f"{runtime_path.relative_to(ROOT)}: Android DirectTcp route candidates must keep "
                "model-provider ports 11434 and 1234 blocked for selected, discovered, and target endpoints."
            )

    required_ui_snippets = (
        "takeUnless { it.containsBackendEndpointMaterial() }",
        "private fun String.containsBackendEndpointMaterial(): Boolean",
        "BACKEND_ENDPOINT_DETAIL_PATTERNS",
        "https?://[^\\\\s,;)]+",
        "[A-Za-z0-9.-]+|\\\\[[0-9A-Fa-f:]+]",
        "api/(?:tags|ps|pull|chat|show|v1)",
        "v1/(?:models|chat|chat/completions)",
        "route[_-]?token",
        "relay[_-]?secret",
        "pairing[_-]?secret",
        "routeToken",
        "relaySecret",
        "|rt|rs",
        "providerDiagnosticCode",
        "providerDiagnosticsVisible",
    )
    for snippet in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(
                f"{ui_path.relative_to(ROOT)}: Android visible error details must keep "
                "a last-mile redaction guard for direct backend endpoint material."
            )

    required_runtime_snippets = (
        "runtimeProviderSafeCode",
        "PROVIDER_DIAGNOSTIC_CODE_PATTERN",
        "route[_-]?token",
        "relay[_-]?secret",
        "pairing[_-]?secret",
        "routeToken",
        "relaySecret",
        "|rt|rs",
    )
    for snippet in required_runtime_snippets:
        if snippet not in runtime_text:
            failures.append(
                f"{runtime_path.relative_to(ROOT)}: Android runtime health provider states must redact "
                "route, relay, and pairing secret material before storing provider diagnostics."
            )

    if "runtimeVisibleErrorDetailRedactsBackendEndpointDetails" not in test_text:
        failures.append(
            f"{test_path.relative_to(ROOT)}: Missing Android visible error-detail redaction regression test."
        )
    if "runtimeVisibleErrorDetailRedactsRouteSecretDetails" not in test_text:
        failures.append(
            f"{test_path.relative_to(ROOT)}: Missing Android visible route-secret redaction regression test."
        )
    if "providerDiagnosticMessageRedactsRouteSecretDetails" not in test_text:
        failures.append(
            f"{test_path.relative_to(ROOT)}: Missing Android provider route-secret message redaction test."
        )
    if "providerDiagnosticCodeRedactsUnsafeCodes" not in test_text:
        failures.append(
            f"{test_path.relative_to(ROOT)}: Missing Android provider diagnostic-code redaction test."
        )
    if "providerDiagnosticsHiddenWhenAllDetailsAreRedacted" not in test_text:
        failures.append(
            f"{test_path.relative_to(ROOT)}: Missing Android provider diagnostics visibility regression test."
        )
    if "runtimeProviderStatusesRedactRouteSecretDetails" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android runtime provider route-secret state redaction test."
        )
    if "runtimeProviderSafeCodePreservesStructuredCodesOnly" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android runtime provider diagnostic-code sanitizer test."
        )
    if "runtimeRouteCandidatesRejectDirectModelProviderPortsFromSelectedAndDiscoveredRoutes" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android route-candidate test that blocks "
            "direct Ollama and LM Studio ports from selected and discovered routes."
        )
    if "relayPairingQrPersistsPendingRouteAfterInitialConnectionFailure" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android pending relay QR persistence test "
            "after initial route failure."
        )
    if "recreatedViewModelRestoresPendingRelayPairingAndSendsPairingRequest" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android pending relay QR restore test "
            "after app/ViewModel recreation."
        )
    if '"lab://pair?pairing_code=123456".isAetherLinkPairingQrValue()' not in test_text:
        failures.append(
            f"{test_path.relative_to(ROOT)}: Missing Android scanner regression test for incomplete "
            "legacy pair QR values."
        )
    if "http://192.168.1.23:11434/api/tags" not in test_text or (
        "model-provider.example.test:1234/v1/models" not in test_text
    ):
        failures.append(
            f"{test_path.relative_to(ROOT)}: Android visible error-detail redaction tests must cover "
            "non-localhost provider endpoints."
        )
    required_secret_samples = (
        "route_token=route-secret-token",
        "relay_secret=relay-secret-value",
        "pairing_secret=pairing-secret-value",
        "rt=compact-route-token",
        "rs=compact-relay-secret",
        "routeToken",
        "relaySecret",
    )
    combined_test_text = test_text + "\n" + runtime_test_text
    for sample in required_secret_samples:
        if sample not in combined_test_text:
            failures.append(
                f"{test_path.relative_to(ROOT)} and {runtime_test_path.relative_to(ROOT)}: Android redaction tests "
                f"must cover route/relay secret sample {sample!r}."
            )

    return failures


def android_chat_history_danger_guard_failures() -> list[str]:
    failures: list[str] = []
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    ui_relative = ui_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")

    required_ui_snippets = (
        (
            "var showBulkActions by rememberSaveable { mutableStateOf(false) }",
            "Bulk chat-history actions must stay collapsed until the user opens Manage all chats.",
        ),
        (
            "if (showBulkActions) {",
            "Bulk archive/delete controls must stay hidden behind the Manage all chats expander.",
        ),
        (
            "bulkArchiveConfirmStep.value = 1",
            "Archive-all must open the two-step confirmation dialog before acting.",
        ),
        (
            "bulkDeleteConfirmStep.value = 1",
            "Permanent bulk delete must open the two-step confirmation dialog before acting.",
        ),
        (
            "deleteConfirmStep.value = 1",
            "Single permanent delete must open the two-step confirmation dialog before acting.",
        ),
        (
            "archive_all_chats_confirm_first",
            "Archive-all needs a first confirmation message.",
        ),
        (
            "archive_all_chats_confirm_second",
            "Archive-all needs a second confirmation message.",
        ),
        (
            "delete_archived_chats_confirm_first",
            "Bulk permanent delete needs a first confirmation message.",
        ),
        (
            "delete_archived_chats_confirm_second",
            "Bulk permanent delete needs a second confirmation message.",
        ),
        (
            "permanently_delete_chat_confirm_first",
            "Single permanent delete needs a first confirmation message.",
        ),
        (
            "permanently_delete_chat_confirm_second",
            "Single permanent delete needs a second confirmation message.",
        ),
        (
            "return isActionEnabled && isArchived",
            "Single permanent delete must remain limited to archived chats.",
        ),
        (
            "return isActionEnabled && archivedSessionCount > 0",
            "Bulk permanent delete must remain limited to archived chats.",
        ),
    )
    for snippet, guidance in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: {guidance}")

    required_confirmation_invocations = (
        (
            "onConfirm = onArchiveAllChatSessions,",
            "Archive-all must be invoked only from the two-step dialog confirmation.",
        ),
        (
            "onConfirm = onPermanentlyDeleteArchivedChatSessions,",
            "Bulk permanent delete must be invoked only from the two-step dialog confirmation.",
        ),
        (
            "onConfirm = { onPermanentlyDeleteChatSession(session.id) },",
            "Single permanent delete must be invoked only from the two-step dialog confirmation.",
        ),
    )
    for snippet, guidance in required_confirmation_invocations:
        if ui_text.count(snippet) != 1:
            failures.append(f"{ui_relative}: {guidance}")

    required_test_snippets = (
        "chatHistoryBulkArchiveRequiresEnabledActiveChats",
        "chatHistoryPermanentBulkDeleteRequiresEnabledArchivedChats",
        "chatHistoryPermanentDeleteRequiresEnabledArchivedChat",
        "chatHistoryBulkActionsOnlyAppearWhenChatsExist",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(
                f"{test_relative}: Missing Android chat-history danger-action regression test {snippet}."
            )

    return failures


def android_chat_model_menu_guard_failures() -> list[str]:
    failures: list[str] = []
    main_activity_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt"
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    main_relative = main_activity_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    main_text = main_activity_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")

    required_main_snippets = (
        (
            "onSelectEmbeddingModel = viewModel::selectEmbeddingModel",
            "Chat top-bar model menu must stay wired to the persisted embedding-model selector.",
        ),
        (
            "onSelectEmbeddingModel: (String?) -> Unit",
            "Chat top-bar model menu must accept embedding-model selection separately from chat model selection.",
        ),
        (
            "EmbeddingModelMenuItem(",
            "Chat top-bar model menu must keep a visible Memory indexing model section.",
        ),
        (
            "embeddingModelMenuModels(",
            "Embedding models must stay filtered separately from chat models.",
        ),
        (
            "modelMenuSearchAvailable(state.models)",
            "Model-menu search must stay available when embedding or installable chat models are present.",
        ),
        (
            "embeddingModelMenuEmptyTextRes(",
            "Embedding-model empty states must distinguish search misses from unavailable models.",
        ),
        (
            "val selectedModel = chatModelMenuModels(state.models)\n        .firstOrNull { it.id == state.selectedModelId }",
            "Closed chat model labels must use the same runtime-host-local model policy as the menu.",
        ),
    )
    for snippet, guidance in required_main_snippets:
        if snippet not in main_text:
            failures.append(f"{main_relative}: {guidance}")

    required_test_snippets = (
        "embeddingModelMenuShowsOnlyInstalledLocalEmbeddingModelsAndPinsSelection",
        "embeddingModelMenuSearchMatchesModelIdentityProviderAndSource",
        "modelMenuSearchStaysAvailableForEmbeddingOrInstallableChatModels",
        "embeddingModelMenuEmptyTextDistinguishesSearchFromUnavailableModels",
        "chatModelPickerClosedLabelIgnoresProviderManagedChatModel",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(
                f"{test_relative}: Missing Android chat top-bar embedding model regression test {snippet}."
            )

    return failures


def android_haptic_guard_failures() -> list[str]:
    failures: list[str] = []
    main_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt"
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"

    for path in (main_path, ui_path, test_path):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android haptic contract file.")
            return failures

    main_text = main_path.read_text(encoding="utf-8")
    ui_text = ui_path.read_text(encoding="utf-8")
    test_text = test_path.read_text(encoding="utf-8")
    main_relative = main_path.relative_to(ROOT)
    ui_relative = ui_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_main_snippets = (
        (
            "private fun HapticFeedback.performAetherLinkFeedback(feedback: AetherLinkInteractionFeedback)",
            "MainActivity must keep the centralized AetherLink haptic helper.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                        handlePairingQr(rawValue)",
            "QR scan success must keep a primary-action haptic before pairing begins.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                                    viewModel.startNewChat()",
            "Drawer new-chat action must keep a primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)\n"
            "                onSelectDestination(AppDestination.Chat)",
            "Permanent navigation rail chat selection must keep selection haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                                                renamingSessionId = session.id",
            "Chat rename menu action must keep primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)\n"
            "                                                val archivedSessionId = session.id",
            "Chat archive action must keep destructive haptic.",
        ),
    )
    for snippet, guidance in required_main_snippets:
        if snippet not in main_text:
            failures.append(f"{main_relative}: {guidance}")

    required_ui_snippets = (
        (
            "private fun HapticFeedback.performAetherLinkFeedback(feedback: AetherLinkInteractionFeedback)",
            "ClientScreens must keep the centralized AetherLink haptic helper.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                        onAttachFiles()",
            "Attachment button must keep a primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)\n"
            "                            onCancel()",
            "Cancel-generation button must keep destructive haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                            onSend()",
            "Send button must keep primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                            onSuggestionClick(suggestion)",
            "Suggested-question chips must keep primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)\n"
            "                    onRemoveAttachment(attachment.id)",
            "Attachment removal must keep destructive haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Clipboard)",
            "Copy/share-like assistant actions must keep clipboard haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)\n"
            "        isExpanded.value = !isExpanded.value",
            "Expandable Settings sections must keep toggle haptic.",
        ),
        (
            "shouldPerformSelectionChangeHaptic(selected)",
            "Model/preference selection rows must avoid duplicate haptics for already selected items.",
        ),
    )
    for snippet, guidance in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: {guidance}")

    required_test_snippets = (
        "aetherLinkHapticPolicyKeepsOrdinaryActionsLightweight",
        "aetherLinkHapticPolicyKeepsStrongActionsDistinct",
        "selectionChangeHapticOnlyRunsWhenSelectionChanges",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing Android haptic policy regression test {snippet}.")

    return failures


def attachment_ingestion_guard_failures() -> list[str]:
    failures: list[str] = []
    android_picker_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt"
    android_runtime_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt"
    android_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    macos_extractor_path = ROOT / "apps/macos/DocumentIngestion/Sources/DocumentTextExtractor.swift"
    macos_test_path = ROOT / "apps/macos/DocumentIngestion/Tests/DocumentTextExtractorTests.swift"

    files = (
        android_picker_path,
        android_runtime_path,
        android_test_path,
        macos_extractor_path,
        macos_test_path,
    )
    for path in files:
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing attachment ingestion contract file.")
            return failures

    android_picker_text = android_picker_path.read_text(encoding="utf-8")
    android_runtime_text = android_runtime_path.read_text(encoding="utf-8")
    android_test_text = android_test_path.read_text(encoding="utf-8")
    macos_extractor_text = macos_extractor_path.read_text(encoding="utf-8")
    macos_test_text = macos_test_path.read_text(encoding="utf-8")

    required_android_picker_mimes = (
        "application/x-hwpml",
        "application/vnd.hancom.hwpml",
        "text/html",
        "text/rtf",
        "application/xhtml+xml",
        "text/markdown",
        "text/x-rst",
        "text/asciidoc",
    )
    for mime_type in required_android_picker_mimes:
        if mime_type not in android_picker_text:
            failures.append(
                f"{android_picker_path.relative_to(ROOT)}: attachment picker must keep {mime_type}."
            )
        if mime_type not in android_test_text:
            failures.append(
                f"{android_test_path.relative_to(ROOT)}: attachment picker regression test must cover {mime_type}."
            )

    if '"hwpml" -> "application/x-hwpml"' not in android_runtime_text:
        failures.append(
            f"{android_runtime_path.relative_to(ROOT)}: Android attachment MIME fallback must map .hwpml."
        )

    for snippet in (
        "case hwpml",
        "application/x-hwpml",
        "application/vnd.hancom.hwpml",
        "testExtractsTextFromHWPMLXmlDocument",
        "testExtractsTextFromHWPMLHancomMimeAlias",
    ):
        target_text = macos_test_text if snippet.startswith("test") else macos_extractor_text
        target_path = macos_test_path if snippet.startswith("test") else macos_extractor_path
        if snippet not in target_text:
            failures.append(
                f"{target_path.relative_to(ROOT)}: document ingestion must keep HWPML support snippet {snippet!r}."
            )

    return failures


def macos_product_copy_guard_failures() -> list[str]:
    failures: list[str] = []
    source_root = ROOT / "apps/macos/LocalAgentBridgeApp/Sources"
    resources_root = source_root / "Resources"

    for path in sorted(source_root.glob("*.swift")):
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for match in MACOS_LOCALIZED_STRING_RE.finditer(line):
                localized_key = match.group(1)
                if MACOS_STALE_VISIBLE_COPY_RE.search(localized_key):
                    failures.append(
                        f"{relative}:{line_number}: replace stale macOS product copy "
                        "with connection details, Activity, or AetherLink Runtime wording."
                    )

    for path in sorted(resources_root.glob("*.lproj/Localizable.strings")):
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if MACOS_STALE_VISIBLE_COPY_RE.search(line):
                failures.append(
                    f"{relative}:{line_number}: remove unused stale macOS localization copy."
                )
            entry = MACOS_STRINGS_ENTRY_RE.match(line)
            if entry and MACOS_STALE_LOCALIZATION_VALUE_RE.search(entry.group("value")):
                failures.append(
                    f"{relative}:{line_number}: replace stale macOS localization value "
                    "with release-facing connection/details copy."
                )

    return failures


def cloud_model_source_copy_guard_failures() -> list[str]:
    failures: list[str] = []

    for path in target_files():
        relative = path.relative_to(ROOT)
        relative_text = relative.as_posix()

        # The guard is for app-facing Android/macOS copy. Protocol schemas,
        # docs, tests, implementation enums, and provider names may still use
        # cloud/source terminology where it is a data contract or provider fact.
        if (
            relative_text.startswith("script/")
            or "/Tests/" in relative_text
            or "/build/" in relative_text
            or "/.build/" in relative_text
        ):
            continue

        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if CLOUD_MODEL_SOURCE_LABEL_RE.search(line):
                failures.append(
                    f"{relative}:{line_number}: user-facing model source copy must not expose an explicit "
                    '"Cloud" label; use provider/service availability wording instead.'
                )
            if CLOUD_DEFAULT_RECOMMENDED_RE.search(line):
                failures.append(
                    f"{relative}:{line_number}: user-facing model copy must not imply cloud models are "
                    "the default, recommended, or preferred option."
                )

    return failures


def is_allowed_match(path: Path, line: str, rule_name: str) -> bool:
    relative = path.relative_to(ROOT).as_posix()

    if "/Tests/" in relative:
        return True
    if "build/" in relative or "/.build/" in relative:
        return True

    # Internal resource ids and protocol/error codes still use backend-oriented
    # identifiers for compatibility. This check is about visible text values and
    # localization fallback keys, not stable code identifiers.
    if relative.startswith("apps/android/") and re.search(r'name="[^"]*backend[^"]*"', line):
        return True

    # Shell scripts are developer diagnostics; they can name concrete platforms
    # where commands such as adb or local dev-server launch instructions require it.
    if rule_name == "platform-specific-os-copy" and relative.startswith("script/"):
        return True

    if rule_name == "direct-model-url-copy" and (
        "without entering backend URLs" in line or "without provider URLs" in line
    ):
        return True

    if rule_name == "legacy-companion-copy" and relative.endswith("LogsView.swift") and (
        'case "Companion started"' in line
        or 'case "Companion stopped"' in line
        or 'line == "Companion stopped"' in line
    ):
        return True

    return False


def main() -> int:
    failures: list[str] = []

    for path in target_files():
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for rule in RULES:
                if rule.pattern.search(line) and not is_allowed_match(path, line, rule.name):
                    failures.append(f"{relative}:{line_number}: {rule.name}: {rule.guidance}")

    if failures:
        print("Copy hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    cloud_model_source_failures = cloud_model_source_copy_guard_failures()
    if cloud_model_source_failures:
        print("Cloud model-source copy guard failed:", file=sys.stderr)
        for failure in cloud_model_source_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_product_copy_failures = macos_product_copy_guard_failures()
    if macos_product_copy_failures:
        print("macOS product copy guard failed:", file=sys.stderr)
        for failure in macos_product_copy_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    route_failures = route_diagnostics_guard_failures()
    if route_failures:
        print("Route Diagnostics guard check failed:", file=sys.stderr)
        for failure in route_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_troubleshooting_failures = android_troubleshooting_guard_failures()
    if android_troubleshooting_failures:
        print("Android troubleshooting guard check failed:", file=sys.stderr)
        for failure in android_troubleshooting_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_runtime_boundary_matcher_failures = android_runtime_boundary_matcher_self_test_failures()
    if android_runtime_boundary_matcher_failures:
        print("Android runtime boundary matcher self-test failed:", file=sys.stderr)
        for failure in android_runtime_boundary_matcher_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_runtime_boundary_failures = android_runtime_boundary_guard_failures()
    if android_runtime_boundary_failures:
        print("Android runtime boundary guard failed:", file=sys.stderr)
        for failure in android_runtime_boundary_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_chat_history_failures = android_chat_history_danger_guard_failures()
    if android_chat_history_failures:
        print("Android chat-history danger guard failed:", file=sys.stderr)
        for failure in android_chat_history_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_chat_model_menu_failures = android_chat_model_menu_guard_failures()
    if android_chat_model_menu_failures:
        print("Android chat model-menu guard failed:", file=sys.stderr)
        for failure in android_chat_model_menu_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_haptic_failures = android_haptic_guard_failures()
    if android_haptic_failures:
        print("Android haptic guard failed:", file=sys.stderr)
        for failure in android_haptic_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    attachment_ingestion_failures = attachment_ingestion_guard_failures()
    if attachment_ingestion_failures:
        print("Attachment ingestion guard failed:", file=sys.stderr)
        for failure in attachment_ingestion_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Copy hygiene OK across {len(target_files())} user-facing source/resource file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
