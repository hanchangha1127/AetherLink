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
    relay_integration_test_path = (
        ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/runtime/"
        "RuntimeClientViewModelRelayIntegrationTest.kt"
    )
    manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")
    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    main_activity_text = main_activity_path.read_text(encoding="utf-8", errors="replace")
    runtime_text = runtime_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    runtime_test_text = runtime_test_path.read_text(encoding="utf-8", errors="replace")
    relay_integration_test_text = relay_integration_test_path.read_text(encoding="utf-8", errors="replace")
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
    if "compactRelayQrPairingResultPersistsTrustedRelayAndClearsPendingRoute" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android relay QR completion test that "
            "persists trusted relay material and clears the pending route."
        )
    if (
        "compactRelayQrPairingUsesRealRelayTcpClientAndPersistsTrustedRelay"
        not in relay_integration_test_text or
        "RuntimeRelayTcpClient()" not in relay_integration_test_text or
        "AETHERLINK_RELAY ready" not in relay_integration_test_text
    ):
        failures.append(
            f"{relay_integration_test_path.relative_to(ROOT)}: Missing Android app integration test that "
            "drives compact relay QR pairing through the real RuntimeRelayTcpClient socket path."
        )
    if "freshCompactRelayQrRefreshesExpiredTrustedRelayRouteAndReconnectsViaRelay" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android fresh relay QR recovery test that "
            "replaces an expired trusted relay route and reconnects through relay."
        )
    if "routeRefreshPayloadRejectsMismatchedRuntimeIdentity" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android route.refresh identity-binding regression test."
        )
    if "streamingRuntimeOwnedChatRendersInMemoryButRedactsDeviceStorage" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android streaming runtime-owned chat "
            "redaction test that keeps visible stream content out of device storage."
        )
    if "invalidPairingQrDoesNotEnableTrustedRuntimeAutoReconnect" not in runtime_test_text:
        failures.append(
            f"{runtime_test_path.relative_to(ROOT)}: Missing Android invalid QR state-mutation regression test."
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
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    viewmodel_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/runtime/RuntimeClientViewModel.kt"
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    viewmodel_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt"
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"
    main_relative = main_activity_path.relative_to(ROOT)
    ui_relative = ui_path.relative_to(ROOT)
    viewmodel_relative = viewmodel_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    viewmodel_test_relative = viewmodel_test_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)
    main_text = main_activity_path.read_text(encoding="utf-8", errors="replace")
    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    viewmodel_text = viewmodel_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    viewmodel_test_text = viewmodel_test_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")

    required_main_snippets = (
        (
            "internal fun AetherLinkTopAppBar(",
            "App top-bar shell chrome must stay testable outside the full Activity stack.",
        ),
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
        (
            "chatModelPickerFallbackDisplayName(state)",
            "Closed chat model labels must hide provider-managed selections after the model list has loaded.",
        ),
        (
            "R.string.model_status_value",
            "Model menu status copy must be formatted through localized resources.",
        ),
    )
    for snippet, guidance in required_main_snippets:
        if snippet not in main_text:
            failures.append(f"{main_relative}: {guidance}")

    if "R.string.model_status_value" not in ui_text:
        failures.append(f"{ui_relative}: Embedding model row status copy must be formatted through localized resources.")

    required_viewmodel_snippets = (
        (
            "installed = it.installed == true",
            "Runtime model parsing must not treat missing installed metadata as installed.",
        ),
        (
            'return normalizedSource == "local"',
            "Runtime model filtering must not treat missing source metadata as local.",
        ),
        (
            "model != null && !model.isRuntimeHostLocalModel()",
            "Model selection must reject provider-managed or unknown-source chat models.",
        ),
        (
            "!model.installed || !model.isRuntimeHostLocalModel()",
            "Embedding model selection must reject provider-managed or unknown-source embedding models.",
        ),
    )
    for snippet, guidance in required_viewmodel_snippets:
        if snippet not in viewmodel_text:
            failures.append(f"{viewmodel_relative}: {guidance}")

    hardcoded_status_pattern = re.compile(r"runtimeProviderDisplayName\(model\.provider\).*-\s*\$", re.DOTALL)
    for relative, text in ((main_relative, main_text), (ui_relative, ui_text)):
        if hardcoded_status_pattern.search(text):
            failures.append(f"{relative}: Model provider/status rows must not hard-code a dash-formatted status string.")

    required_test_snippets = (
        "embeddingModelMenuShowsOnlyInstalledLocalEmbeddingModelsAndPinsSelection",
        "embeddingModelMenuSearchMatchesModelIdentityProviderAndSource",
        "modelMenuSearchStaysAvailableForEmbeddingOrInstallableChatModels",
        "embeddingModelMenuEmptyTextDistinguishesSearchFromUnavailableModels",
        "chatModelPickerClosedLabelIgnoresProviderManagedChatModel",
        "assertEquals(null, chatModelPickerFallbackDisplayName(state))",
        "chat-unknown-source",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(
                f"{test_relative}: Missing Android chat top-bar embedding model regression test {snippet}."
            )

    required_viewmodel_test_snippets = (
        "modelsResultMissingInstalledOrSourceDoesNotBecomeSelectableChatModel",
        "selectModelRejectsProviderManagedOrUnknownSourceChatModelWithoutPersisting",
        "Metadata Missing",
        "source = null",
    )
    for snippet in required_viewmodel_test_snippets:
        if snippet not in viewmodel_test_text:
            failures.append(
                f"{viewmodel_test_relative}: Missing Android runtime model metadata regression test {snippet}."
            )

    required_compose_test_snippets = (
        "appTopBarKeepsNavigationModelPickerAndNewChatChrome",
        "chatTopBarModelPickerStatusLineUsesLocalizedResources",
        "Ollama - Installé",
    )
    for snippet in required_compose_test_snippets:
        if snippet not in compose_test_text:
            failures.append(
                f"{compose_test_relative}: Missing Android localized model-status Compose regression {snippet}."
            )

    return failures


def android_suggested_question_guard_failures() -> list[str]:
    failures: list[str] = []
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"

    for path in (ui_path, test_path, compose_test_path):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android suggested-question guard file.")
            return failures

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")
    ui_relative = ui_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)

    required_ui_snippets = (
        "internal fun normalizedSuggestedQuestions(",
        "SUGGESTED_QUESTION_MAX_ITEMS",
        ".filter { seen.add(it.lowercase(Locale.ROOT)) }",
        "val visibleSuggestions = normalizedSuggestedQuestions(suggestions)",
        "normalizedSuggestedQuestions(suggestions).isNotEmpty() || isLoadingSuggestions",
    )
    for snippet in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: Missing suggested-question normalization policy {snippet}.")

    required_test_snippets = (
        "assistantSuggestionsNormalizeBlankDuplicatesAndMaximumRows",
        "assistantSuggestionsHideWhenRowsNormalizeToBlank",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing suggested-question helper regression {snippet}.")

    if "chatScreenNormalizesSuggestedQuestionChips" not in compose_test_text:
        failures.append(f"{compose_test_relative}: Missing suggested-question Compose rendering regression.")

    return failures


def android_chat_pairing_empty_state_guard_failures() -> list[str]:
    failures: list[str] = []
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"
    helper_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    strings_path = ROOT / "apps/android/app/src/main/res/values/strings.xml"

    for path in (ui_path, compose_test_path, helper_test_path, strings_path):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android chat pairing empty-state guard file.")
            return failures

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")
    helper_test_text = helper_test_path.read_text(encoding="utf-8", errors="replace")
    strings_text = strings_path.read_text(encoding="utf-8", errors="replace")
    ui_relative = ui_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)
    helper_test_relative = helper_test_path.relative_to(ROOT)
    strings_relative = strings_path.relative_to(ROOT)

    required_ui_snippets = (
        "state.trustedRuntime == null -> stringResource(R.string.chat_hint_pairing)",
        "state.trustedRuntime == null -> stringResource(R.string.empty_chat_pairing_title)",
        "state.trustedRuntime == null -> stringResource(R.string.empty_chat_pairing)",
        "val canEditComposer = chatComposerCanEdit(state)",
        "internal fun chatComposerCanEdit(state: RuntimeUiState): Boolean",
        "chatComposerShouldShowStatus(",
        "internal fun chatComposerShouldShowStatus(",
        "state.trustedRuntime != null",
        "internal fun chatEmptyScanActionLabelRes(state: RuntimeUiState): Int",
    )
    for snippet in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: Missing QR-first untrusted chat empty-state policy {snippet}.")

    required_string_keys = (
        'name="empty_chat_pairing_title"',
        'name="empty_chat_pairing"',
        'name="chat_hint_pairing"',
    )
    for snippet in required_string_keys:
        if snippet not in strings_text:
            failures.append(f"{strings_relative}: Missing QR-first untrusted chat empty-state string {snippet}.")

    required_compose_test_snippets = (
        "chatScreenUntrustedRuntimeShowsQrFirstPairingCallToAction",
        "chatScreenUntrustedRuntimeUsesLocalizedQrFirstCopy",
        "chatScreenShowsComposerReadinessHintWhenPreviousChatCannotSend",
        "assertIsNotEnabled",
    )
    for snippet in required_compose_test_snippets:
        if snippet not in compose_test_text:
            failures.append(
                f"{compose_test_relative}: Missing QR-first untrusted ChatScreen Compose regression {snippet}."
            )

    required_helper_test_snippets = (
        "chatComposerEditingRequiresTrustedConnectedUsableModel",
        "chatComposerStatusShowsReadinessHintsWhenInputIsLocked",
    )
    for snippet in required_helper_test_snippets:
        if snippet not in helper_test_text:
            failures.append(f"{helper_test_relative}: Missing trusted composer readiness helper regression {snippet}.")

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
            "                    onNewChat()",
            "Drawer new-chat action must keep a primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)\n"
            "                onSelectDestination(AppDestination.Chat)",
            "Permanent navigation rail chat selection must keep selection haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                                onRenameChatSession(session)",
            "Chat rename menu action must keep primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)\n"
            "                                onArchiveChatSession(session)",
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


def macos_model_visibility_guard_failures() -> list[str]:
    failures: list[str] = []
    status_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"

    if not status_path.exists() or not test_path.exists():
        failures.append("macOS model visibility guard files are missing.")
        return failures

    status_text = status_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    status_relative = status_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_status_snippets = (
        (
            "visibleModelGroups(for: model.models)",
            "Status Models panel must use the shared visible-model policy.",
        ),
        (
            "model.installed &&",
            "Status Models panel must hide uninstalled models.",
        ),
        (
            "model.source == .local",
            "Status Models panel must hide provider-managed/cloud models.",
        ),
        (
            "visibleModelCount",
            "Readiness model count must reflect visible installed local models.",
        ),
    )
    for snippet, guidance in required_status_snippets:
        if snippet not in status_text:
            failures.append(f"{status_relative}: {guidance}")

    required_test_snippets = (
        "testVisibleModelGroupsShowOnlyInstalledLocalModels",
        "provider-managed-chat",
        "uninstalled-embedding",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS model visibility regression {snippet}.")

    return failures


def macos_runtime_local_chat_routing_guard_failures() -> list[str]:
    failures: list[str] = []
    aggregate_path = ROOT / "apps/macos/CompanionCore/Sources/AggregatingLlmBackend.swift"
    router_path = ROOT / "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift"
    aggregate_test_path = ROOT / "apps/macos/CompanionCore/Tests/AggregatingLlmBackendResidencyTests.swift"
    router_test_path = ROOT / "apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift"

    required_paths = (aggregate_path, router_path, aggregate_test_path, router_test_path)
    if any(not path.exists() for path in required_paths):
        failures.append("macOS runtime-local chat routing guard files are missing.")
        return failures

    aggregate_text = aggregate_path.read_text(encoding="utf-8", errors="replace")
    router_text = router_path.read_text(encoding="utf-8", errors="replace")
    aggregate_test_text = aggregate_test_path.read_text(encoding="utf-8", errors="replace")
    router_test_text = router_test_path.read_text(encoding="utf-8", errors="replace")

    aggregate_relative = aggregate_path.relative_to(ROOT)
    router_relative = router_path.relative_to(ROOT)
    aggregate_test_relative = aggregate_test_path.relative_to(ROOT)
    router_test_relative = router_test_path.relative_to(ROOT)

    required_aggregate_snippets = (
        (
            "guard candidate.source == .local else { return false }",
            "Aggregating backend chat routing must reject provider-managed/cloud models.",
        ),
    )
    for snippet, guidance in required_aggregate_snippets:
        if snippet not in aggregate_text:
            failures.append(f"{aggregate_relative}: {guidance}")

    required_router_snippets = (
        (
            "model.installed\n                    && model.source == .local",
            "Runtime router qualified model lookup must require runtime-host-local models.",
        ),
        (
            "model.installed && model.source == .local &&",
            "Runtime router unqualified model lookup must require runtime-host-local models.",
        ),
    )
    for snippet, guidance in required_router_snippets:
        if snippet not in router_text:
            failures.append(f"{router_relative}: {guidance}")

    required_aggregate_test_snippets = (
        "testInstalledCloudChatModelIsNotRoutedAsChat",
        "source: .cloud",
        "XCTAssertTrue(ollama.routedModels.isEmpty)",
    )
    for snippet in required_aggregate_test_snippets:
        if snippet not in aggregate_test_text:
            failures.append(
                f"{aggregate_test_relative}: Missing aggregate runtime-local routing regression {snippet}."
            )

    required_router_test_snippets = (
        "testChatSendInstalledCloudModelReturnsModelNotInstalled",
        "\"model_not_installed\"",
        ".bool(false)",
    )
    for snippet in required_router_test_snippets:
        if snippet not in router_test_text:
            failures.append(f"{router_test_relative}: Missing runtime router cloud-model rejection regression {snippet}.")

    if "testChatSendInstalledCloudModelIsSelectable" in router_test_text:
        failures.append(
            f"{router_test_relative}: Installed provider-managed/cloud chat models must not remain selectable."
        )

    return failures


def macos_remote_qr_lease_guard_failures() -> list[str]:
    failures: list[str] = []
    model_path = ROOT / "apps/macos/CompanionCore/Sources/CompanionAppModel.swift"
    test_path = ROOT / "apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift"

    if not model_path.exists() or not test_path.exists():
        failures.append("macOS remote QR lease guard files are missing.")
        return failures

    model_text = model_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    model_relative = model_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_model_snippets = (
        (
            "if let issue = remoteRoutePreparationIssue",
            "Remote QR generation must surface the concrete route-preparation issue.",
        ),
        (
            "shouldGenerateRemotePairingQRCodeWhenRelayReady = false",
            "Remote QR generation must not wait on relay readiness after lease preparation has already failed.",
        ),
        (
            "log(\"Remote pairing QR not generated: \\(issue.message)\")",
            "Remote QR logs must include the concrete route-preparation failure message.",
        ),
        (
            "clearRelayConnectionIssueIfRouteIsUsable()",
            "Relay ready/waiting status must not blindly clear lease-preparation failures.",
        ),
        (
            "if isDevelopmentRelayRoutePreparedForQRCode",
            "Route-preparation issues should clear only after QR lease material is actually usable.",
        ),
    )
    for snippet, guidance in required_model_snippets:
        if snippet not in model_text:
            failures.append(f"{model_relative}: {guidance}")

    required_test_snippets = (
        "testCompanionAppModelKeepsLeasePreparationIssueWhenRelayIsReadyWithoutLease",
        ".routeLeaseRefreshFailed",
        "Remote pairing QR not generated: Remote route allocation response was invalid.",
        "Remote route ready: relay.example.test:43171",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS remote QR lease regression {snippet}.")

    return failures


def macos_suggested_question_guard_failures() -> list[str]:
    failures: list[str] = []
    router_path = ROOT / "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift"
    test_path = ROOT / "apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift"

    if not router_path.exists() or not test_path.exists():
        failures.append("macOS suggested-question guard files are missing.")
        return failures

    router_text = router_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    router_relative = router_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_router_snippets = (
        (
            "private static let maxChatSuggestionCount = 4",
            "Runtime suggested-question responses must stay capped to the compact chip row.",
        ),
        (
            "let key = cleaned.suggestionDedupeKey",
            "Runtime suggested-question dedupe must use the normalized key.",
        ),
        (
            ".folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive]",
            "Runtime suggested-question dedupe must be case/diacritic/width insensitive.",
        ),
        (
            "func collapsedSuggestionWhitespace() -> String",
            "Runtime suggested-question text must collapse multiline or repeated whitespace.",
        ),
    )
    for snippet, guidance in required_router_snippets:
        if snippet not in router_text:
            failures.append(f"{router_relative}: {guidance}")

    required_test_snippets = (
        "testChatSuggestionsRequestNormalizesBlankDuplicateAndExcessSuggestions",
        "Résumé details?",
        "Should not appear?",
        "\"max_suggestions\": .number(5)",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS suggested-question regression {snippet}.")

    return failures


def macos_chat_store_corruption_guard_failures() -> list[str]:
    failures: list[str] = []
    store_path = ROOT / "apps/macos/CompanionCore/Sources/RuntimeChatEventStore.swift"
    router_path = ROOT / "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift"
    test_path = ROOT / "apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift"

    if not store_path.exists() or not router_path.exists() or not test_path.exists():
        failures.append("macOS chat-store corruption guard files are missing.")
        return failures

    store_text = store_path.read_text(encoding="utf-8", errors="replace")
    router_text = router_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    store_relative = store_path.relative_to(ROOT)
    router_relative = router_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_store_snippets = (
        (
            "case corruptEventLog(line: Int, reason: String)",
            "Runtime chat store must expose corrupt JSONL logs as structured errors.",
        ),
        (
            "throw RuntimeChatEventStoreError.corruptEventLog(",
            "Runtime chat store must throw on corrupt JSONL lines instead of skipping them.",
        ),
        (
            "components(separatedBy: .newlines)",
            "Runtime chat store must preserve line numbers while decoding JSONL.",
        ),
    )
    for snippet, guidance in required_store_snippets:
        if snippet not in store_text:
            failures.append(f"{store_relative}: {guidance}")

    forbidden_store_snippets = (
        "try? decoder.decode(RuntimeChatStoredEvent.self",
        ".compactMap { line in",
    )
    for snippet in forbidden_store_snippets:
        if snippet in store_text:
            failures.append(f"{store_relative}: Runtime chat store must not silently drop corrupt JSONL lines.")

    required_router_snippets = (
        "if let error = error as? RuntimeChatEventStoreError",
        ".chatStoreUnavailable(error.localizedDescription)",
        "The runtime could not access chat history on this host:",
    )
    for snippet in required_router_snippets:
        if snippet not in router_text:
            failures.append(f"{router_relative}: Missing chat-store corruption protocol-error mapping {snippet}.")

    required_test_snippets = (
        "testRuntimeChatStoreReportsCorruptJSONLLineInsteadOfDroppingIt",
        "testRuntimeChatHistoryCorruptStoreReturnsStructuredError",
        "should-not-leak",
        "chat_store_unavailable",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing chat-store corruption regression {snippet}.")

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


def no_device_quality_gate_guard_failures() -> list[str]:
    failures: list[str] = []
    gate_path = ROOT / "script/check_no_device_quality.sh"

    if not gate_path.exists():
        failures.append("script/check_no_device_quality.sh is missing.")
        return failures

    gate_text = gate_path.read_text(encoding="utf-8", errors="replace")
    required_snippets = (
        (
            "./script/runtime_authenticated_mock_smoke.swift --relay",
            "Default no-device quality gate must run the authenticated relay E2E smoke.",
        ),
        (
            "authenticated mock relay E2E",
            "Default no-device gate coverage summary must mention authenticated relay E2E coverage.",
        ),
        (
            "RuntimeClientViewModelRelayIntegrationTest.compactRelayQrPairingUsesRealRelayTcpClientAndPersistsTrustedRelay",
            "Default no-device quality gate must run the Android app real RuntimeRelayTcpClient pairing regression.",
        ),
        (
            "real RuntimeRelayTcpClient app pairing path",
            "Default no-device gate coverage summary must mention the Android app real relay-client pairing path.",
        ),
        (
            "Android raw Compose visible-string localization guard",
            "Default no-device gate coverage summary must mention Android raw visible-string localization coverage.",
        ),
        (
            "Android app top-bar shell chrome",
            "Default no-device gate coverage summary must mention Android app top-bar shell coverage.",
        ),
        (
            "Android QR-first chat empty state",
            "Default no-device gate coverage summary must mention Android QR-first chat empty-state coverage.",
        ),
        (
            "Android trusted composer readiness lock",
            "Default no-device gate coverage summary must mention Android trusted composer readiness coverage.",
        ),
        (
            "Android composer readiness hint",
            "Default no-device gate coverage summary must mention Android composer readiness hint coverage.",
        ),
    )
    for snippet, guidance in required_snippets:
        if snippet not in gate_text:
            failures.append(f"{gate_path.relative_to(ROOT)}: {guidance}")

    return failures


def android_string_parity_guard_failures() -> list[str]:
    failures: list[str] = []
    parity_path = ROOT / "script/check_android_string_parity.py"

    if not parity_path.exists():
        failures.append("script/check_android_string_parity.py is missing.")
        return failures

    parity_text = parity_path.read_text(encoding="utf-8", errors="replace")
    required_snippets = (
        (
            "RAW_COMPOSE_VISIBLE_LITERAL_RE",
            "Android string parity must keep the raw Compose visible-string regex guard.",
        ),
        (
            "check_no_raw_compose_visible_literals",
            "Android string parity must scan Kotlin UI sources for raw visible/accessibility strings.",
        ),
        (
            "raw Compose visible-string guards",
            "Android string parity success output must mention the raw visible-string guard.",
        ),
    )
    for snippet, guidance in required_snippets:
        if snippet not in parity_text:
            failures.append(f"{parity_path.relative_to(ROOT)}: {guidance}")

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

    no_device_gate_failures = no_device_quality_gate_guard_failures()
    if no_device_gate_failures:
        print("No-device quality gate guard failed:", file=sys.stderr)
        for failure in no_device_gate_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_string_parity_failures = android_string_parity_guard_failures()
    if android_string_parity_failures:
        print("Android string parity guard failed:", file=sys.stderr)
        for failure in android_string_parity_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_product_copy_failures = macos_product_copy_guard_failures()
    if macos_product_copy_failures:
        print("macOS product copy guard failed:", file=sys.stderr)
        for failure in macos_product_copy_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_model_visibility_failures = macos_model_visibility_guard_failures()
    if macos_model_visibility_failures:
        print("macOS model visibility guard failed:", file=sys.stderr)
        for failure in macos_model_visibility_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_runtime_local_chat_routing_failures = macos_runtime_local_chat_routing_guard_failures()
    if macos_runtime_local_chat_routing_failures:
        print("macOS runtime-local chat routing guard failed:", file=sys.stderr)
        for failure in macos_runtime_local_chat_routing_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_remote_qr_lease_failures = macos_remote_qr_lease_guard_failures()
    if macos_remote_qr_lease_failures:
        print("macOS remote QR lease guard failed:", file=sys.stderr)
        for failure in macos_remote_qr_lease_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_suggested_question_failures = macos_suggested_question_guard_failures()
    if macos_suggested_question_failures:
        print("macOS suggested-question guard failed:", file=sys.stderr)
        for failure in macos_suggested_question_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_chat_store_corruption_failures = macos_chat_store_corruption_guard_failures()
    if macos_chat_store_corruption_failures:
        print("macOS chat-store corruption guard failed:", file=sys.stderr)
        for failure in macos_chat_store_corruption_failures:
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

    android_suggested_question_failures = android_suggested_question_guard_failures()
    if android_suggested_question_failures:
        print("Android suggested-question guard failed:", file=sys.stderr)
        for failure in android_suggested_question_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_chat_pairing_empty_state_failures = android_chat_pairing_empty_state_guard_failures()
    if android_chat_pairing_empty_state_failures:
        print("Android chat pairing empty-state guard failed:", file=sys.stderr)
        for failure in android_chat_pairing_empty_state_failures:
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
