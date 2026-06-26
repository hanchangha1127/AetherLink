#!/usr/bin/env python3
"""Check user-facing copy for stale prototype wording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


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
        re.compile(
            r"\b(?:Ask anything|Anything(?:\s*\.\.\.|…)?|"
            r"Ask me anything|Message anything)\b|"
            r"무엇이든(?:\s*(?:부탁|물어보세요|입력하세요|말해보세요))?|"
            r"何でも(?:聞いて|入力|話して)?|"
            r"任何(?:内容|问题|事)?|"
            r"(?:Demandez|Posez)(?:-moi)? n[’']importe quoi",
            re.IGNORECASE,
        ),
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
        "script/android_relay_reachability_probe.sh",
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
        "model.bootstrapRelaySettings.isEnabled",
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

    localization_tests_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"
    localization_tests_text = localization_tests_path.read_text(encoding="utf-8", errors="replace")
    if "testRouteDiagnosticsPanelStaysHiddenOnCleanFirstRunUntilRouteStateExists" not in localization_tests_text:
        failures.append(
            f"{localization_tests_path.relative_to(ROOT)}: Missing regression test that keeps "
            "Connection Recovery hidden on clean first-run until saved route state or a route issue exists."
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


def android_client_ui_resource_copy_guard_failures() -> list[str]:
    failures: list[str] = []
    string_paths = sorted(ROOT.glob("apps/android/app/src/main/res/values*/strings.xml"))
    os_product_noun_re = re.compile(r"\b(?:Android|Mac|macOS|Windows|iPhone|iOS)\b")
    direct_provider_access_re = re.compile(
        r"\b(?:"
        r"(?:connect|connecting|pair|pairing|load|loading|chat|chatting|send|sending|call|calling|use|using|"
        r"reach|reaching|talk|talking)\s+(?:directly\s+)?(?:to|with|through|from)\s+(?:Ollama|LM Studio)|"
        r"(?:connect|connecting|load|loading|chat|chatting|send|sending|call|calling|use|using)\s+"
        r"(?:Ollama|LM Studio)|"
        r"(?:Ollama|LM Studio)\s+(?:URL|endpoint|address|host|port|server|connection)|"
        r"direct(?:ly)?\s+(?:from|to|with)\s+(?:Ollama|LM Studio)|"
        r"from\s+(?:Ollama|LM Studio)\s+directly"
        r")\b",
        re.IGNORECASE,
    )
    safe_provider_context_re = re.compile(
        r"\b(?:"
        r"through (?:the runtime|AetherLink Runtime)|"
        r"in AetherLink Runtime|"
        r"via (?:the runtime|AetherLink Runtime)"
        r")\b",
        re.IGNORECASE,
    )

    unsafe_samples = (
        "Open AetherLink on Android.",
        "Open AetherLink on this Mac.",
        "Enter the Ollama URL.",
        "Use Ollama.",
        "Connect directly to LM Studio.",
        "Load models from Ollama directly.",
    )
    safe_samples = (
        "Open AetherLink on this device.",
        "Connect to the trusted runtime.",
        "Ollama is not responding through the runtime.",
        "Check LM Studio in AetherLink Runtime.",
    )

    for sample in unsafe_samples:
        if not (os_product_noun_re.search(sample) or direct_provider_access_re.search(sample)):
            failures.append(
                "script/check_copy_hygiene.py: Android UI resource copy guard missed "
                f"unsafe sample {sample!r}"
            )
    for sample in safe_samples:
        if os_product_noun_re.search(sample):
            failures.append(
                "script/check_copy_hygiene.py: Android UI resource copy guard rejected "
                f"target-neutral sample {sample!r}"
            )
        provider_match = direct_provider_access_re.search(sample)
        if provider_match and not safe_provider_context_re.search(sample):
            failures.append(
                "script/check_copy_hygiene.py: Android UI resource copy guard rejected "
                f"runtime-mediated provider sample {sample!r}"
            )

    for path in string_paths:
        relative = path.relative_to(ROOT)
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        except ET.ParseError as error:
            failures.append(f"{relative}: Android strings XML could not be parsed: {error}")
            continue

        for string_element in root.findall("string"):
            name = string_element.attrib.get("name", "")
            value = "".join(string_element.itertext())
            if os_product_noun_re.search(value):
                failures.append(
                    f"{relative}: string {name!r} must use device, client, runtime, or runtime host wording "
                    "instead of OS-specific product nouns."
                )
            provider_match = direct_provider_access_re.search(value)
            if provider_match and not safe_provider_context_re.search(value):
                failures.append(
                    f"{relative}: string {name!r} must not imply direct Ollama or LM Studio access from "
                    "the Android client; route provider access through AetherLink Runtime."
                )

    return failures


def platform_specific_os_copy_guard_failures() -> list[str]:
    failures: list[str] = []
    rule = next((candidate for candidate in RULES if candidate.name == "platform-specific-os-copy"), None)
    if rule is None:
        return ["script/check_copy_hygiene.py: missing platform-specific-os-copy rule."]

    unsafe_samples = (
        "Scan this QR from Android.",
        "Open AetherLink on this Mac.",
        "Use the iPhone app to connect.",
        "Pair from iOS.",
        "Run the runtime on Windows.",
        "Check macOS Settings.",
    )
    safe_samples = (
        "Scan this QR from AetherLink.",
        "Open AetherLink on this device.",
        "Pair from a trusted device.",
        "Run the runtime on the runtime host.",
        "Use System appearance.",
    )
    app_copy_path = ROOT / "apps/android/app/src/main/res/values/strings.xml"
    script_path = ROOT / "script/android_usb_smoke.sh"

    for sample in unsafe_samples:
        if not rule.pattern.search(sample):
            failures.append(
                "script/check_copy_hygiene.py: platform-specific OS copy guard missed "
                f"unsafe sample {sample!r}"
            )
        if is_allowed_match(app_copy_path, sample, rule.name):
            failures.append(
                "script/check_copy_hygiene.py: platform-specific OS copy guard allowed "
                f"app-facing unsafe sample {sample!r}"
            )

    for sample in safe_samples:
        if rule.pattern.search(sample):
            failures.append(
                "script/check_copy_hygiene.py: platform-specific OS copy guard rejected "
                f"target-neutral sample {sample!r}"
            )

    if not is_allowed_match(script_path, "Android device command", rule.name):
        failures.append(
            "script/check_copy_hygiene.py: platform-specific OS copy guard should allow "
            "developer diagnostic scripts to name concrete platforms."
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
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"
    ui_relative = ui_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)
    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")

    required_ui_snippets = (
        (
            "archiveActionContentDescription = stringResource(R.string.archive_chat_named, title)",
            "Per-chat archive buttons must include the chat title in their accessibility label.",
        ),
        (
            "restoreActionContentDescription = stringResource(R.string.restore_chat_named, title)",
            "Per-chat restore buttons must include the chat title in their accessibility label.",
        ),
        (
            "permanentlyDeleteActionContentDescription =\n        stringResource(R.string.permanently_delete_chat_named, title)",
            "Per-chat permanent delete buttons must include the chat title in their accessibility label.",
        ),
        (
            "contentDescription = archiveActionContentDescription",
            "Archive button semantics must use the contextual chat-title label.",
        ),
        (
            "contentDescription = restoreActionContentDescription",
            "Restore button semantics must use the contextual chat-title label.",
        ),
        (
            "contentDescription = permanentlyDeleteActionContentDescription",
            "Permanent delete button semantics must use the contextual chat-title label.",
        ),
        (
            "var showBulkActions by rememberSaveable { mutableStateOf(false) }",
            "Bulk chat-history actions must stay collapsed until the user opens Manage all chats.",
        ),
        (
            "if (showBulkActions) {",
            "Bulk archive/delete controls must stay hidden behind the Manage all chats expander.",
        ),
        (
            "stateDescription = bulkActionsStateDescription",
            "Manage all chats must expose expanded/collapsed state to accessibility.",
        ),
        (
            "bulkArchiveConfirmStep.value = 1",
            "Archive-all must open the two-step confirmation dialog before acting.",
        ),
        (
            "onClick = {\n"
            "                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                            bulkArchiveConfirmStep.value = 1\n"
            "                        },",
            "Archive-all must open confirmation with lightweight haptic feedback.",
        ),
        (
            "bulkDeleteConfirmStep.value = 1",
            "Permanent bulk delete must open the two-step confirmation dialog before acting.",
        ),
        (
            "onClick = {\n"
            "                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                            bulkDeleteConfirmStep.value = 1\n"
            "                        },",
            "Permanent bulk delete must open confirmation with lightweight haptic feedback.",
        ),
        (
            "deleteConfirmStep.value = 1",
            "Single permanent delete must open the two-step confirmation dialog before acting.",
        ),
        (
            "onClick = {\n"
            "                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                            deleteConfirmStep.value = 1\n"
            "                        },",
            "Single permanent delete must open confirmation with lightweight haptic feedback.",
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

    required_compose_test_snippets = (
        'onNodeWithContentDescription("Archive chat Active project chat", useUnmergedTree = true)',
        'onNodeWithContentDescription("Restore chat Archived project chat", useUnmergedTree = true)',
        'onNodeWithContentDescription("Permanently delete chat Archived project chat", useUnmergedTree = true)',
        "settingsScreenPerChatHistoryActionsUseConfirmationHaptics",
        "assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)",
        "assertEquals(\n            listOf(HapticFeedbackType.TextHandleMove, HapticFeedbackType.LongPress),",
    )
    for snippet in required_compose_test_snippets:
        if snippet not in compose_test_text:
            failures.append(
                f"{compose_test_relative}: Missing per-chat contextual accessibility regression {snippet}."
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
            "Settings must stay wired to the persisted embedding-model selector.",
        ),
        (
            "modelMenuSearchAvailable(state.models)",
            "Chat model-menu search must stay available when searchable chat models are present.",
        ),
        (
            "chatModelMenuItemSemanticsModifier(",
            "Chat model rows must keep accessibility state semantics.",
        ),
        (
            "!model.installed && !installing -> R.string.install_model",
            "Uninstalled chat model rows must expose the install action as accessibility state.",
        ),
        (
            "text = stringResource(R.string.install_model)",
            "Uninstalled chat model rows must show a visible install action cue.",
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

    if main_text.count("onSelectEmbeddingModel = viewModel::selectEmbeddingModel") != 1:
        failures.append(
            f"{main_relative}: Embedding model selection must be reachable only through Settings, not the Chat top bar."
        )
    forbidden_top_bar_snippets = (
        "EmbeddingModelMenuItem(",
        "embeddingModelMenuModels(",
        "embeddingModelMenuEmptyTextRes(",
    )
    for snippet in forbidden_top_bar_snippets:
        if snippet in main_text:
            failures.append(
                f"{main_relative}: Chat top-bar model picker must not render or own embedding-model selection ({snippet})."
            )

    if "onSelectEmbeddingModel: (String?) -> Unit" not in ui_text:
        failures.append(f"{ui_relative}: Settings must keep an embedding-model selection callback.")
    if "R.string.model_status_value" not in ui_text:
        failures.append(f"{ui_relative}: Embedding model row status copy must be formatted through localized resources.")
    if "selectedEmbeddingModelRowModifier(selected)" not in ui_text:
        failures.append(f"{ui_relative}: Settings embedding model rows must keep selected-state accessibility semantics.")
    if "selectedPreferenceOptionState(selected, selectedStateDescription)" not in ui_text:
        failures.append(f"{ui_relative}: Settings language and appearance rows must keep selected-state accessibility semantics.")

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
        "chatModelMenuSearchAvailabilityUsesChatModelsOnly",
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
        "chatTopBarModelPickerExposesSelectedRowsToAccessibility",
        "chatTopBarModelPickerExposesInstallActionForUninstalledLocalChatModel",
        'hasStateDescription("Install model")',
        "settingsPreferenceRowsExposeSelectedStateToAccessibility",
        "settingsEmbeddingModelRowsExposeSelectedStateToAccessibility",
        "chatTopBarModelPickerStatusLineUsesLocalizedResources",
        'assertNoVisibleText("Memory indexing model")',
        'assertNoVisibleText("Nomic Embed Text")',
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
        "suggestionContentDescription = stringResource(R.string.content_desc_suggested_question, text)",
        "contentDescription = suggestionContentDescription",
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

    required_compose_snippets = (
        "chatScreenNormalizesSuggestedQuestionChips",
        "Suggested question: Summarize again?",
    )
    for snippet in required_compose_snippets:
        if snippet not in compose_test_text:
            failures.append(f"{compose_test_relative}: Missing suggested-question Compose rendering regression {snippet}.")

    if "CHAT_MESSAGE_LIST_TEST_TAG" not in ui_text:
        failures.append(f"{ui_relative}: Missing stable chat list test tag for jump-to-latest coverage.")

    required_jump_to_latest_snippets = (
        "chatScreenJumpToLatestAppearsAfterScrollingAwayAndReturnsToLatestMessage",
        "CHAT_MESSAGE_LIST_TEST_TAG",
        "performScrollToIndex(messages.lastIndex)",
        'onNodeWithContentDescription("Jump to latest message")',
    )
    for snippet in required_jump_to_latest_snippets:
        if snippet not in compose_test_text:
            failures.append(f"{compose_test_relative}: Missing chat jump-to-latest Compose regression {snippet}.")

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
        "state.trustedRuntime == null -> R.string.empty_chat_pairing",
        "val canEditComposer = chatComposerCanEdit(state)",
        "internal fun chatComposerCanEdit(state: RuntimeUiState): Boolean",
        "chatComposerShouldShowStatus(",
        "internal fun chatComposerShouldShowStatus(",
        "internal fun chatEmptyTextRes(state: RuntimeUiState, preferQrRouteRefresh: Boolean = false): Int",
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


def android_trusted_runtime_forget_guard_failures() -> list[str]:
    failures: list[str] = []
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"
    strings_path = ROOT / "apps/android/app/src/main/res/values/strings.xml"

    for path in (ui_path, compose_test_path, strings_path):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android trusted-runtime forget guard file.")
            return failures

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")
    strings_text = strings_path.read_text(encoding="utf-8", errors="replace")
    ui_relative = ui_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)
    strings_relative = strings_path.relative_to(ROOT)

    required_ui_snippets = (
        (
            "var showForgetConfirmation by rememberSaveable { mutableStateOf(false) }",
            "Trusted runtime forget must keep a transient confirmation state.",
        ),
        (
            "if (trustedRuntime != null && showForgetConfirmation) {",
            "Trusted runtime forget confirmation must only show for an existing trusted runtime.",
        ),
        (
            "title = { Text(stringResource(R.string.forget_trusted_runtime_confirm_title)) }",
            "Trusted runtime forget dialog title must use localized copy.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)\n"
            "                        showForgetConfirmation = false",
            "Trusted runtime forget cancel must use lightweight feedback without invoking the action.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)\n"
            "                        showForgetConfirmation = false\n"
            "                        onForgetTrustedRuntime()",
            "Trusted runtime forget must only invoke the action from the destructive confirmation.",
        ),
        (
            "onClick = {\n"
            "                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                        showForgetConfirmation = true\n"
            "                    },",
            "Trusted runtime forget button must open the confirmation with lightweight feedback instead of invoking directly.",
        ),
    )
    for snippet, guidance in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: {guidance}")

    required_test_snippets = (
        "settingsTrustedRuntimeForgetRequiresConfirmation",
        'compose.onNodeWithText("Forget trusted runtime?").assertIsDisplayed()',
        'compose.onNodeWithText("Cancel").performClick()',
        'compose.onNodeWithText("Forget runtime").performClick()',
        "assertEquals(0, forgetClicks)",
        "assertEquals(1, forgetClicks)",
        "assertEquals(listOf(HapticFeedbackType.TextHandleMove), hapticFeedback.events)",
        "assertEquals(listOf(HapticFeedbackType.LongPress), hapticFeedback.events)",
    )
    for snippet in required_test_snippets:
        if snippet not in compose_test_text:
            failures.append(f"{compose_test_relative}: Missing trusted-runtime forget regression {snippet}.")

    required_string_snippets = (
        "forget_trusted_runtime_confirm_title",
        "forget_trusted_runtime_confirm_message",
        "forget_trusted_runtime_confirm_action",
    )
    for snippet in required_string_snippets:
        if snippet not in strings_text:
            failures.append(f"{strings_relative}: Missing trusted-runtime forget confirmation string {snippet}.")

    return failures


def android_haptic_guard_failures() -> list[str]:
    failures: list[str] = []
    main_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/MainActivity.kt"
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/AppNavigationTest.kt"
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"
    scanner_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/PairingQrScannerChromeNoDeviceComposeTest.kt"
    strings_path = ROOT / "apps/android/app/src/main/res/values/strings.xml"

    for path in (main_path, ui_path, test_path, compose_test_path, scanner_test_path, strings_path):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android haptic contract file.")
            return failures

    main_text = main_path.read_text(encoding="utf-8")
    ui_text = ui_path.read_text(encoding="utf-8")
    test_text = test_path.read_text(encoding="utf-8")
    compose_test_text = compose_test_path.read_text(encoding="utf-8")
    scanner_test_text = scanner_test_path.read_text(encoding="utf-8")
    strings_text = strings_path.read_text(encoding="utf-8")
    main_relative = main_path.relative_to(ROOT)
    ui_relative = ui_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)
    scanner_test_relative = scanner_test_path.relative_to(ROOT)
    strings_relative = strings_path.relative_to(ROOT)

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
            "chatSessionOptionsContentDescription = stringResource(R.string.chat_session_more_named, title)",
            "Drawer chat-session overflow buttons must include the chat title in their accessibility label.",
        ),
        (
            "contentDescription = chatSessionOptionsContentDescription",
            "Drawer chat-session overflow buttons must use the contextual chat-title label.",
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
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                                onArchiveChatSession(session)",
            "Chat archive action must use lightweight feedback because archive is reversible.",
        ),
        (
            "internal fun PairingQrScannerChrome(",
            "QR scanner chrome must stay testable without opening CameraX.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)\n"
            "                                onTorchToggle()",
            "QR scanner flashlight toggle must keep toggle haptic.",
        ),
        (
            "PAIRING_QR_FLASHLIGHT_BUTTON_TEST_TAG",
            "QR scanner flashlight button must keep a stable no-device test tag.",
        ),
        (
            "stateDescription = torchStateDescription",
            "QR scanner flashlight button must expose on/off state to accessibility.",
        ),
        (
            "qr_scanner_flashlight_state_on",
            "QR scanner flashlight state must use localized on copy.",
        ),
        (
            "qr_scanner_flashlight_state_off",
            "QR scanner flashlight state must use localized off copy.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                        onRequestCameraPermission()",
            "QR scanner permission action must keep primary-action haptic.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)\n"
            "                            onCancel()",
            "QR scanner cancel actions must use lightweight feedback.",
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
            "attachFilesStateDescription",
            "Attachment button must keep an accessibility state description.",
        ),
        (
            "stateDescription = attachFilesStateDescription",
            "Attachment button must expose readiness or disabled reason to accessibility.",
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
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                        actionHandler()",
            "Connection route notice cards must keep primary-action haptic.",
        ),
        (
            "runtimeRouteNotice(state, state.trustedRuntime)?.action == RouteNoticePrimaryAction.ScanLatestQr",
            "Settings trusted-runtime primary action must follow route-refresh QR guidance before stale endpoints.",
        ),
        (
            "RouteNoticePrimaryAction.ScanLatestQr -> onScanLatestQr()",
            "Settings trusted-runtime primary action must open the latest-QR scanner when route refresh is required.",
        ),
        (
            "hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)\n"
            "                    onRemoveAttachment(attachment.id)",
            "Attachment removal must keep destructive haptic.",
        ),
        (
            "attachmentContentDescription = stringResource(",
            "Attachment chips must build contextual accessibility labels with file state.",
        ),
        (
            "contentDescription = attachmentContentDescription",
            "Attachment chips must expose file name and state to accessibility.",
        ),
        (
            "stateDescription = attachmentStateDescription",
            "Attachment chips must expose document or vision-required state to accessibility.",
        ),
        (
            "stateDescription = attachmentTypeDescription",
            "Read-only message attachment chips must expose document or image state to accessibility.",
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
            "stateDescription = toggleStateDescription",
            "Expandable Settings sections must expose expanded/collapsed state to accessibility.",
        ),
        (
            "val toggleContentDescription = stringResource(title)",
            "Endpoint diagnostics expander must expose the section title as its accessibility label.",
        ),
        (
            "modifier = Modifier.clearAndSetSemantics {}",
            "Endpoint diagnostics expander must hide the nested icon button from accessibility.",
        ),
        (
            "stateDescription = autoReconnectStateDescription",
            "Auto reconnect switch must expose localized on/off state to accessibility.",
        ),
        (
            "stateDescription = diagnosticsStateDescription",
            "Connection troubleshooting switch must expose localized on/off state to accessibility.",
        ),
        (
            "discoveredRuntimeActionContentDescription = stringResource(",
            "Discovered runtime actions must build contextual accessibility labels.",
        ),
        (
            "contentDescription = discoveredRuntimeActionContentDescription",
            "Discovered runtime action buttons must include the runtime name in their accessibility label.",
        ),
        (
            "settingsSectionExpandedStateDescriptionRes()",
            "Expandable Settings sections must use localized expanded state copy.",
        ),
        (
            "shouldPerformSelectionChangeHaptic(selected)",
            "Model/preference selection rows must avoid duplicate haptics for already selected items.",
        ),
        (
            "memoryToggleContentDescription = stringResource(",
            "Memory enable/pause switches must include the memory text in their accessibility label.",
        ),
        (
            "memoryRemoveContentDescription = stringResource(R.string.memory_remove_named, memoryActionLabel)",
            "Memory remove buttons must include the memory text in their accessibility label.",
        ),
        (
            "onClick = {\n"
            "                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)\n"
            "                    showDeleteConfirmation.value = true\n"
            "                },\n"
            "                enabled = actionsEnabled,",
            "Memory remove buttons must open confirmation with lightweight haptic feedback.",
        ),
        (
            "stateDescription = memoryStateDescription",
            "Memory enable/pause switches must expose enabled/paused state to accessibility.",
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

    required_compose_test_snippets = (
        "connectionStatusSavedRouteNoticeClickConnectsWithHaptic",
        "connectionStatusRefreshNeededRouteNoticeClickScansLatestQrWithHaptic",
        "settingsExpiredRelayRoutePrimaryActionScansLatestQrWithHaptic",
        "settingsConnectedTrustedRuntimeDoesNotExposePairingConnectButton",
        "connectionStatusRefreshHealthActionUsesActionCopyAndCallback",
        "Refresh health",
        "settingsExpandableSectionsExposeLocalizedExpandedState",
        "Chat options for Trip plan",
        "Chat Trip plan. 3 messages - Needs attention.",
        "Selected chat One note. 1 message.",
        "chatScreenAttachmentChipsExposeFileStateToAccessibility",
        "chatScreenAttachmentSizeUsesSelectedAppLanguageContext",
        "Formatter.formatFileSize(localizedContext, attachment.sizeBytes)",
        "chatScreenMessageAttachmentChipsExposeFileStateToAccessibility",
        "Attachment diagram.png, Vision model required",
        "Attachment diagram.png, Image",
        "settingsMemoryRowsExposeContextualActionAccessibility",
        "settingsAutoReconnectSwitchExposesAccessibilityState",
        "settingsDiscoveredRuntimeActionsUseContextualAccessibilityLabels",
        "settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed",
        "settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch",
        "chatScreenStreamingShowsCancelActionInsteadOfSend",
        "hasStateDescription(\"Ready to attach files.\")",
        "hasStateDescription(\"Select a model before sending.\")",
        "hasStateDescription(\"Wait for the current response or cancel it.\")",
        "onAllNodesWithContentDescription(\"Send message\").assertCountEquals(0)",
        "HapticFeedbackType.LongPress",
        "hasContentDescription(\"Connection troubleshooting\") and",
        "hasStateDescription(\"Collapsed\") and",
        "SemanticsProperties.Role, Role.Button",
        "hasText(\"Manage all chats\") and hasStateDescription(\"Collapsed\")",
        "hasText(\"Manage all chats\") and hasStateDescription(\"Expanded\")",
        "Pause memory Project Alpha prefers concise Korean summaries",
        "Enable memory Use metric units for travel planning",
        "Remove memory Project Alpha prefers concise Korean summaries",
        'compose.onNodeWithText("Cancel").performClick()',
        'compose.onNodeWithText("Delete").performClick()',
        "assertEquals(1, removeClicks)",
    )
    for snippet in required_compose_test_snippets:
        if snippet not in compose_test_text:
            failures.append(f"{compose_test_relative}: Missing Android haptic Compose regression test {snippet}.")

    required_string_snippets = (
        'name="attach_files_state_ready"',
        'name="attach_files_state_unavailable"',
        'name="chat_session_row_summary"',
        'name="chat_session_row_summary_selected"',
    )
    for snippet in required_string_snippets:
        if snippet not in strings_text:
            failures.append(f"{strings_relative}: Missing Android attachment action accessibility string {snippet}.")

    required_scanner_test_snippets = (
        "PairingQrScannerChromeNoDeviceComposeTest",
        "scannerChromeShowsPermissionStateWithoutCameraPreview",
        "scannerChromeShowsCameraStateWithTorchAndCancelActions",
        "HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove",
        "hasStateDescription(\"Flashlight off\")",
        "hasStateDescription(\"Flashlight on\")",
    )
    for snippet in required_scanner_test_snippets:
        if snippet not in scanner_test_text:
            failures.append(f"{scanner_test_relative}: Missing QR scanner chrome no-device regression {snippet}.")

    return failures


def android_physical_chat_smoke_guard_failures() -> list[str]:
    failures: list[str] = []
    path = ROOT / "script/android_pairing_deeplink_smoke.sh"
    relative = path.relative_to(ROOT)
    text = path.read_text(encoding="utf-8", errors="replace")
    required_snippets = (
        (
            "--expect-chat-cancel",
            "Physical pairing smoke must keep the optional chat/cancel UI path.",
        ),
        (
            "--live-backend",
            "Physical pairing smoke must keep the optional real Ollama/LM Studio runtime path.",
        ),
        (
            "LOCAL_AGENT_BRIDGE_MOCK_BACKEND=1",
            "Physical pairing smoke must keep mock backend opt-in rather than forcing Android toward model providers.",
        ),
        (
            "AETHERLINK_DEV_MOCK_CHUNK_DELAY_MS=5000",
            "Physical chat/cancel smoke must slow the dev mock stream enough for cancel.",
        ),
        (
            "--chat-delta-timeout",
            "Physical live-backend smoke must allow longer first-token waits.",
        ),
        (
            "--probe-external-relay-from-device",
            "Physical external-relay smoke must keep the Android-device route reachability probe.",
        ),
        (
            "script/android_relay_reachability_probe.sh",
            "Physical external-relay smoke must probe relay reachability from the Android device before QR injection when requested.",
        ),
        (
            'tap_content_description "Message"',
            "Physical chat/cancel smoke must tap the accessibility-labelled chat input.",
        ),
        (
            'tap_content_description "Send message"',
            "Physical chat/cancel smoke must tap the accessibility-labelled send control.",
        ),
        (
            'tap_content_description "Cancel generation"',
            "Physical chat/cancel smoke must tap the accessibility-labelled cancel control.",
        ),
        (
            'wait_for_log "$RUNTIME_LOG" "chat.cancel"',
            "Physical chat/cancel smoke must verify chat.cancel reaches the runtime.",
        ),
        (
            'wait_for_log "$RUNTIME_LOG" "chat.done"',
            "Physical chat/cancel smoke must verify the runtime closes the streamed chat lifecycle.",
        ),
    )
    for snippet, guidance in required_snippets:
        if snippet not in text:
            failures.append(f"{relative}: {guidance}")

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


def macos_pairing_qr_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    view_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/PairingView.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"

    if not view_path.exists() or not test_path.exists():
        failures.append("macOS Pairing QR accessibility guard files are missing.")
        return failures

    view_text = view_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    view_relative = view_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_view_snippets = (
        (
            ".accessibilityValue(Text(pairingQRCodeAccessibilityValue(isExpired: isExpired)))",
            "Pairing QR image must expose active vs expired state through accessibility value.",
        ),
        (
            ".accessibilityHint(Text(pairingQRCodeAccessibilityHint()))",
            "Pairing QR image must explain that the QR verifies AetherLink Runtime and carries connection details.",
        ),
        (
            "func pairingQRCodeAccessibilityValue(isExpired: Bool) -> String",
            "Pairing QR accessibility value must stay testable without rendering SwiftUI.",
        ),
        (
            "func pairingQRCodeAccessibilityHint() -> String",
            "Pairing QR accessibility hint must stay testable without rendering SwiftUI.",
        ),
    )
    for snippet, guidance in required_view_snippets:
        if snippet not in view_text:
            failures.append(f"{view_relative}: {guidance}")

    required_test_snippets = (
        "testToolbarAndMenuPairingQRGenerationUsesSharedAvailabilityContract",
        "pairingQRGenerationCommandAvailable(",
        "testCompanionDateFormattingUsesSelectedAppLanguage",
        "localizedCompanionDateString(from:",
        "testCompanionByteCountFormattingUsesSelectedAppLanguage",
        "localizedCompanionByteCountString(fromByteCount:",
        "testPairingQRCodeAccessibilityCopyUsesSelectedLanguageAndState",
        "Scan this QR from AetherLink.",
        "Pairing QR expired. Generate a new QR.",
        "This QR verifies AetherLink Runtime and includes connection details for pairing or refresh.",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS Pairing QR accessibility regression {snippet}.")

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
            "platform-neutral app copy guard",
            "Default no-device gate coverage summary must mention platform-neutral app copy coverage.",
        ),
        (
            "RuntimeClientViewModelTest.identityOnlyPairingQrTimesOutWhenNoDiscoveryRouteAppears",
            "Default no-device quality gate must run the identity-only QR discovery timeout regression.",
        ),
        (
            "identity-only QR discovery timeout",
            "Default no-device gate coverage summary must mention identity-only QR timeout coverage.",
        ),
        (
            "macOS raw SwiftUI visible-string localization guard",
            "Default no-device gate coverage summary must mention macOS raw visible-string localization coverage.",
        ),
        (
            "Android native language picker labels",
            "Default no-device gate coverage summary must mention Android native language-picker labels.",
        ),
        (
            "AetherLinkThemeNoDeviceComposeTest",
            "Default no-device gate must run the Android app theme-path regression.",
        ),
        (
            "PairingQrScannerChromeNoDeviceComposeTest",
            "Default no-device gate must run the Android QR scanner chrome regression.",
        ),
        (
            "Android QR scanner permission/torch/cancel chrome",
            "Default no-device gate coverage summary must mention Android QR scanner chrome coverage.",
        ),
        (
            "QR scanner torch state accessibility",
            "Default no-device gate coverage summary must mention QR scanner flashlight state accessibility.",
        ),
        (
            "Android app System/Light/Dark theme path",
            "Default no-device gate coverage summary must mention Android app theme-path coverage.",
        ),
        (
            "Android app top-bar shell chrome",
            "Default no-device gate coverage summary must mention Android app top-bar shell coverage.",
        ),
        (
            "Android chat top-bar install action cue",
            "Default no-device gate coverage summary must mention Android chat top-bar install action cue coverage.",
        ),
        (
            "Android drawer chat options contextual accessibility",
            "Default no-device gate coverage summary must mention drawer chat options contextual accessibility.",
        ),
        (
            "Android drawer chat row accessibility summaries",
            "Default no-device gate coverage summary must mention drawer chat row accessibility summaries.",
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
        (
            "Android composer attach action accessibility state",
            "Default no-device gate coverage summary must mention Android composer attach action accessibility coverage.",
        ),
        (
            "Android streaming cancel Compose action",
            "Default no-device gate coverage summary must mention Android streaming cancel Compose action coverage.",
        ),
        (
            "Android attachment chip accessibility state",
            "Default no-device gate coverage summary must mention Android attachment chip accessibility coverage.",
        ),
        (
            "Android message attachment accessibility state",
            "Default no-device gate coverage summary must mention Android message attachment accessibility coverage.",
        ),
        (
            "Android suggested-question accessibility labels",
            "Default no-device gate coverage summary must mention Android suggested-question accessibility labels.",
        ),
        (
            "Android jump-to-latest Compose interaction",
            "Default no-device gate coverage summary must mention Android jump-to-latest Compose interaction coverage.",
        ),
        (
            "Settings expandable section accessibility state",
            "Default no-device gate coverage summary must mention Settings expandable section accessibility coverage.",
        ),
        (
            "Settings diagnostic endpoint expander accessibility state",
            "Default no-device gate coverage summary must mention Settings diagnostic endpoint expander accessibility state.",
        ),
        (
            "Settings connection switch state accessibility",
            "Default no-device gate coverage summary must mention Settings connection switch accessibility coverage.",
        ),
        (
            "Settings discovered route contextual action accessibility",
            "Default no-device gate coverage summary must mention Settings discovered route contextual action accessibility.",
        ),
        (
            "Settings memory contextual action accessibility",
            "Default no-device gate coverage summary must mention Settings memory contextual action accessibility.",
        ),
        (
            "Settings memory destructive confirmation haptic timing",
            "Default no-device gate coverage summary must mention Settings memory destructive confirmation haptic timing.",
        ),
        (
            "chat history destructive confirmation haptic timing",
            "Default no-device gate coverage summary must mention chat-history destructive confirmation haptic timing.",
        ),
        (
            "confirmation-open lightweight haptic timing",
            "Default no-device gate coverage summary must mention confirmation-open lightweight haptic timing.",
        ),
        (
            "Settings expired-route primary QR action",
            "Default no-device gate coverage summary must mention Settings expired-route primary QR action coverage.",
        ),
        (
            "Android connected Settings redundant-connect guard",
            "Default no-device gate coverage summary must mention the connected Settings redundant-connect guard.",
        ),
        (
            "macOS global QR generation availability gate",
            "Default no-device gate coverage summary must mention macOS global QR command availability coverage.",
        ),
        (
            "macOS app-language date formatting",
            "Default no-device gate coverage summary must mention macOS app-language date formatting coverage.",
        ),
        (
            "macOS app-language byte-count formatting",
            "Default no-device gate coverage summary must mention macOS app-language byte-count formatting coverage.",
        ),
        (
            "Android attachment size locale formatting",
            "Default no-device gate coverage summary must mention Android attachment size locale formatting coverage.",
        ),
        (
            "Android trusted-runtime forget confirmation",
            "Default no-device gate coverage summary must mention trusted-runtime forget confirmation coverage.",
        ),
        (
            "chat history per-chat contextual action accessibility",
            "Default no-device gate coverage summary must mention chat-history contextual action accessibility.",
        ),
        (
            "chat history bulk expander accessibility state",
            "Default no-device gate coverage summary must mention chat-history bulk expander accessibility state.",
        ),
        (
            "macOS five-language system/light/dark detail render smoke",
            "Default no-device gate coverage summary must mention macOS five-language system/light/dark render-smoke coverage.",
        ),
        (
            "macOS first-run diagnostics hiding",
            "Default no-device gate coverage summary must mention macOS first-run diagnostics hiding.",
        ),
        (
            "macOS Pairing QR accessibility state",
            "Default no-device gate coverage summary must mention macOS Pairing QR accessibility state.",
        ),
        (
            "macOS trusted-device remove accessibility labels",
            "Default no-device gate coverage summary must mention macOS trusted-device remove accessibility labels.",
        ),
        (
            "macOS trusted-device row accessibility labels",
            "Default no-device gate coverage summary must mention macOS trusted-device row accessibility labels.",
        ),
        (
            "macOS trusted-device removal confirmation localization",
            "Default no-device gate coverage summary must mention macOS trusted-device removal confirmation localization.",
        ),
        (
            "macOS connection disable accessibility label",
            "Default no-device gate coverage summary must mention macOS connection disable accessibility label coverage.",
        ),
        (
            "macOS provider technical-details accessibility labels",
            "Default no-device gate coverage summary must mention macOS provider technical-details accessibility labels.",
        ),
        (
            "macOS provider status pill accessibility labels",
            "Default no-device gate coverage summary must mention macOS provider status pill accessibility labels.",
        ),
        (
            "macOS runtime overview accessibility labels",
            "Default no-device gate coverage summary must mention macOS runtime overview accessibility labels.",
        ),
        (
            "macOS status card accessibility labels",
            "Default no-device gate coverage summary must mention macOS status card accessibility labels.",
        ),
        (
            "macOS model row accessibility labels",
            "Default no-device gate coverage summary must mention macOS model row accessibility labels.",
        ),
        (
            "macOS relay status row accessibility labels",
            "Default no-device gate coverage summary must mention macOS relay status row accessibility labels.",
        ),
        (
            "macOS route diagnostic technical-details accessibility labels",
            "Default no-device gate coverage summary must mention macOS route diagnostic technical-details accessibility labels.",
        ),
        (
            "macOS readiness row accessibility labels",
            "Default no-device gate coverage summary must mention macOS readiness row accessibility labels.",
        ),
        (
            "Android refresh-health action copy",
            "Default no-device gate coverage summary must mention Android refresh-health action copy.",
        ),
        (
            "including Connection Recovery",
            "Default no-device gate coverage summary must mention macOS Connection Recovery render coverage.",
        ),
        (
            "macOS native language picker labels",
            "Default no-device gate coverage summary must mention macOS native language-picker labels.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testCompanionAppModelStartRenewsSavedBootstrapRelayRouteBeforeRelayStart",
            "Default no-device gate must run the bootstrap relay start-renewal regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testCompanionAppModelRenewsBootstrapRelayRouteAfterRelayFailure",
            "Default no-device gate must run the bootstrap relay failure-renewal regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode",
            "Default no-device gate must run the restored-QR bootstrap lease persistence regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testCompanionAppModelRegeneratesBootstrapQRCodeWithExpiredSavedLease",
            "Default no-device gate must run the expired bootstrap lease QR regeneration regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testCompanionAppModelRequiresRemoteQRCodeForLoopbackSavedRelayHost",
            "Default no-device gate must run the loopback saved relay QR rejection regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testCompanionAppModelAllowsEnvironmentPrivateOverlayRelayButWaitsForLease",
            "Default no-device gate must run the private-overlay lease-wait regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testCompanionAppModelWaitsForLeaseBeforeUsingCGNATPrivateOverlayRelayQRCode",
            "Default no-device gate must run the CGNAT private-overlay lease-wait regression.",
        ),
        (
            "remote relay lease renewal and QR eligibility",
            "Default no-device gate coverage summary must mention remote relay lease renewal and QR eligibility coverage.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testChatSendDoesNotCompactShortConversation",
            "Default no-device gate must run the short-chat runtime compaction regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge",
            "Default no-device gate must run the oversized-chat runtime compaction regression.",
        ),
        (
            "LocalRuntimeMessageRouterTests/testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate",
            "Default no-device gate must run the runtime context separation compaction regression.",
        ),
        (
            "heuristic runtime chat context compaction",
            "Default no-device gate coverage summary must mention runtime chat context compaction coverage.",
        ),
    )
    for snippet, guidance in required_snippets:
        if snippet not in gate_text:
            failures.append(f"{gate_path.relative_to(ROOT)}: {guidance}")

    return failures


def macos_runtime_compaction_guard_failures() -> list[str]:
    failures: list[str] = []
    router_path = ROOT / "apps/macos/CompanionCore/Sources/LocalRuntimeMessageRouter.swift"
    tests_path = ROOT / "apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift"

    if not router_path.exists() or not tests_path.exists():
        return ["macOS runtime compaction guard files are missing."]

    router_text = router_path.read_text(encoding="utf-8", errors="replace")
    tests_text = tests_path.read_text(encoding="utf-8", errors="replace")
    router_snippets = (
        (
            "chatRequestWithRuntimeConversationCompaction(request)",
            "chat.send must keep runtime-side conversation compaction before backend.chat.",
        ),
        (
            "runtimeConversationCompactionPrefix = \"Runtime conversation summary:\"",
            "Runtime compaction must keep a recognizable backend-only summary prefix.",
        ),
        (
            "messages.filter { !$0.isRuntimeConversationCompactionContext }",
            "Runtime compaction must strip stale client-supplied compaction summaries before rebuilding context.",
        ),
        (
            "runtimeConversationCompactionRecentTurnCount",
            "Runtime compaction must preserve recent conversation turns verbatim.",
        ),
    )
    for snippet, guidance in router_snippets:
        if snippet not in router_text:
            failures.append(f"{router_path.relative_to(ROOT)}: {guidance}")

    test_snippets = (
        "testChatSendDoesNotCompactShortConversation",
        "testChatSendCompactsOlderTurnsBeforeBackendRequestWhenContextIsLarge",
        "testChatSendCompactionKeepsRuntimeMemoryAndCapabilityGuardSeparate",
    )
    for snippet in test_snippets:
        if snippet not in tests_text:
            failures.append(
                f"{tests_path.relative_to(ROOT)}: missing runtime compaction regression {snippet}."
            )

    return failures


def macos_render_smoke_guard_failures() -> list[str]:
    failures: list[str] = []
    render_test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkRenderSmokeTests.swift"

    if not render_test_path.exists():
        failures.append("apps/macos/LocalAgentBridgeApp/Tests/AetherLinkRenderSmokeTests.swift is missing.")
        return failures

    render_test_text = render_test_path.read_text(encoding="utf-8")
    required_snippets = (
        (
            "testPrimaryCompanionSurfacesRenderAtMinimumDetailSizeAcrossLanguagesAndAppearances",
            "macOS primary surface render smoke must run across all supported languages and appearances.",
        ),
        (
            "for language in AetherLinkAppLanguage.allCases",
            "macOS render smoke must iterate every supported launch language.",
        ),
        (
            "for appearance in AetherLinkAppAppearance.pickerOptions",
            "macOS render smoke must iterate System, Light, and Dark appearances from the app picker options.",
        ),
        (
            "withStoredPreferences(language: language, appearance: appearance)",
            "macOS render smoke must apply the language and appearance preference before rendering detail surfaces.",
        ),
        (
            ".environment(\\.locale, Locale(identifier: language.localeIdentifier))",
            "macOS render smoke must render detail surfaces with the selected locale.",
        ),
        (
            'label: "\\(name) \\(language.rawValue) \\(appearance.rawValue)"',
            "macOS render smoke failures must identify surface, language, and appearance.",
        ),
        (
            '("StatusView", AnyView(StatusView(model: model)))',
            "macOS render smoke must include StatusView.",
        ),
        (
            '("PairingView", AnyView(PairingView(model: model)))',
            "macOS render smoke must include PairingView.",
        ),
        (
            '("RemoteRelayRoutePanel", AnyView(RemoteRelayRoutePanel(model: model)))',
            "macOS render smoke must include Advanced Connection Setup / Connection Recovery.",
        ),
        (
            '("TrustedDevicesView", AnyView(TrustedDevicesView(model: model)))',
            "macOS render smoke must include TrustedDevicesView.",
        ),
        (
            '("LogsView", AnyView(LogsView(model: model)))',
            "macOS render smoke must include LogsView.",
        ),
    )
    for snippet, guidance in required_snippets:
        if snippet not in render_test_text:
            failures.append(f"{render_test_path.relative_to(ROOT)}: {guidance}")

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
            "for match in RAW_COMPOSE_VISIBLE_LITERAL_RE.finditer(text)",
            "Android raw Compose visible-string guard must scan multiline Kotlin source text.",
        ),
        (
            'text.count("\\n", 0, match.start()) + 1',
            "Android raw Compose visible-string guard must report line numbers from multiline matches.",
        ),
        (
            "check_no_raw_compose_visible_literals",
            "Android string parity must scan Kotlin UI sources for raw visible/accessibility strings.",
        ),
        (
            "raw_compose_visible_literal_matcher_self_test_failures",
            "Android raw Compose visible-string guard must keep inline matcher self-tests.",
        ),
        (
            "multiline Text named argument",
            "Android raw Compose visible-string matcher self-test must cover multiline named Text arguments.",
        ),
        (
            "multiline Button positional text",
            "Android raw Compose visible-string matcher self-test must cover multiline Button text.",
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


def macos_localization_script_guard_failures() -> list[str]:
    failures: list[str] = []
    localization_path = ROOT / "script/check_macos_localization.py"

    if not localization_path.exists():
        failures.append("script/check_macos_localization.py is missing.")
        return failures

    localization_text = localization_path.read_text(encoding="utf-8", errors="replace")
    required_snippets = (
        (
            "RAW_SWIFTUI_VISIBLE_LITERAL_RE",
            "macOS localization must keep the raw SwiftUI visible-string regex guard.",
        ),
        (
            "for match in RAW_SWIFTUI_VISIBLE_LITERAL_RE.finditer(text)",
            "macOS raw SwiftUI visible-string guard must scan multiline Swift source text.",
        ),
        (
            'text.count("\\n", 0, match.start()) + 1',
            "macOS raw SwiftUI visible-string guard must report line numbers from multiline matches.",
        ),
        (
            "check_no_raw_swiftui_visible_literals",
            "macOS localization must scan SwiftUI sources for raw visible strings.",
        ),
        (
            "raw_swiftui_visible_literal_matcher_self_test_failures",
            "macOS raw SwiftUI visible-string guard must keep inline matcher self-tests.",
        ),
        (
            "trustedDeviceRowAccessibilityLabel(",
            "macOS localization guard must require contextual trusted-device row accessibility labels.",
        ),
        (
            "Trusted device %@. %@. Key fingerprint %@",
            "macOS localization guard must require the trusted-device row accessibility localization key.",
        ),
        (
            "trustedDeviceRemoveAccessibilityLabel(name: name, keyFingerprint: keyFingerprint)",
            "macOS localization guard must require contextual trusted-device remove button accessibility labels.",
        ),
        (
            "Remove trust for %@. Key fingerprint %@",
            "macOS localization guard must require the trusted-device remove accessibility localization key.",
        ),
        (
            "logTechnicalDetailsAccessibilityLabel(summary: display.summary)",
            "macOS localization guard must require contextual Activity technical-details accessibility labels.",
        ),
        (
            "Technical details for %@",
            "macOS localization guard must require the Activity technical-details accessibility localization key.",
        ),
        (
            "providerStatusTechnicalDetailsAccessibilityLabel(providerName: status.name)",
            "macOS localization guard must require contextual provider technical-details accessibility labels.",
        ),
        (
            "routeDiagnosticDisclosureAccessibilityLabel(context: accessibilityContext)",
            "macOS localization guard must require contextual route diagnostic technical-details accessibility labels.",
        ),
        (
            "Connection diagnostics",
            "macOS localization guard must require the route diagnostic technical-details fallback key.",
        ),
        (
            "relayStatusRowAccessibilityLabel(title: title, value: value, detail: detail)",
            "macOS localization guard must require grouped connection status row accessibility labels.",
        ),
        (
            "Connection setting %@. Status %@. %@",
            "macOS localization guard must require the connection status row accessibility localization key.",
        ),
        (
            "readinessRowAccessibilityLabel(",
            "macOS localization guard must require contextual readiness row accessibility labels.",
        ),
        (
            "Readiness %@. Status %@. %@",
            "macOS localization guard must require the readiness row accessibility localization key.",
        ),
        (
            "runtimeOverviewAccessibilityLabel(",
            "macOS localization guard must require contextual runtime overview accessibility labels.",
        ),
        (
            "Runtime overview %@. Status %@. %@ %@",
            "macOS localization guard must require the runtime overview accessibility localization key.",
        ),
        (
            "statusCardAccessibilityLabel(",
            "macOS localization guard must require contextual Status card accessibility labels.",
        ),
        (
            "Status %@. Current state %@. %@",
            "macOS localization guard must require the Status card accessibility localization key.",
        ),
        (
            "modelRowAccessibilityLabel(",
            "macOS localization guard must require contextual model row accessibility labels.",
        ),
        (
            "Model %@. ID %@. Type %@. Provider %@. Source %@. State %@. Size %@",
            "macOS localization guard must require the model row accessibility localization key.",
        ),
        (
            "Model provider",
            "macOS localization guard must require the provider technical-details accessibility fallback key.",
        ),
        (
            "multiline Text",
            "macOS raw SwiftUI visible-string matcher self-test must cover multiline Text.",
        ),
        (
            "multiline alert",
            "macOS raw SwiftUI visible-string matcher self-test must cover multiline alert text.",
        ),
    )
    for snippet, guidance in required_snippets:
        if snippet not in localization_text:
            failures.append(f"{localization_path.relative_to(ROOT)}: {guidance}")

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

    macos_render_smoke_failures = macos_render_smoke_guard_failures()
    if macos_render_smoke_failures:
        print("macOS render smoke guard failed:", file=sys.stderr)
        for failure in macos_render_smoke_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_string_parity_failures = android_string_parity_guard_failures()
    if android_string_parity_failures:
        print("Android string parity guard failed:", file=sys.stderr)
        for failure in android_string_parity_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_localization_script_failures = macos_localization_script_guard_failures()
    if macos_localization_script_failures:
        print("macOS localization script guard failed:", file=sys.stderr)
        for failure in macos_localization_script_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    platform_os_copy_failures = platform_specific_os_copy_guard_failures()
    if platform_os_copy_failures:
        print("Platform-specific OS copy guard failed:", file=sys.stderr)
        for failure in platform_os_copy_failures:
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

    macos_pairing_qr_accessibility_failures = macos_pairing_qr_accessibility_guard_failures()
    if macos_pairing_qr_accessibility_failures:
        print("macOS Pairing QR accessibility guard failed:", file=sys.stderr)
        for failure in macos_pairing_qr_accessibility_failures:
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

    macos_runtime_compaction_failures = macos_runtime_compaction_guard_failures()
    if macos_runtime_compaction_failures:
        print("macOS runtime compaction guard failed:", file=sys.stderr)
        for failure in macos_runtime_compaction_failures:
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

    android_client_ui_copy_failures = android_client_ui_resource_copy_guard_failures()
    if android_client_ui_copy_failures:
        print("Android client UI resource copy guard failed:", file=sys.stderr)
        for failure in android_client_ui_copy_failures:
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

    android_trusted_runtime_forget_failures = android_trusted_runtime_forget_guard_failures()
    if android_trusted_runtime_forget_failures:
        print("Android trusted-runtime forget guard failed:", file=sys.stderr)
        for failure in android_trusted_runtime_forget_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_haptic_failures = android_haptic_guard_failures()
    if android_haptic_failures:
        print("Android haptic guard failed:", file=sys.stderr)
        for failure in android_haptic_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_physical_chat_smoke_failures = android_physical_chat_smoke_guard_failures()
    if android_physical_chat_smoke_failures:
        print("Android physical chat/cancel smoke guard failed:", file=sys.stderr)
        for failure in android_physical_chat_smoke_failures:
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
