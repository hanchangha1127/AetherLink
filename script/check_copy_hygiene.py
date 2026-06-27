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
    latest_qr_ready_snippets = (
        "let canGenerateLatestQRCode = model.isDevelopmentRelayQRCodeReady &&",
        "isRouteReadyForQRCode: model.isDevelopmentRelayQRCodeReady",
        "func connectionRecoveryGenerateLatestQRActionAccessibilityValue(\n    isRouteReadyForQRCode: Bool",
        "func connectionRecoveryGenerateLatestQRActionAccessibilityHint(\n    isRouteReadyForQRCode: Bool",
    )
    for snippet in latest_qr_ready_snippets:
        if snippet not in helper_text:
            failures.append(
                "apps/macos/LocalAgentBridgeApp/Sources/RemoteRelayRoutePanel.swift: "
                "Generate Latest QR must depend on full QR readiness, not only route eligibility."
            )
            break

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
    client_screens_test_path = (
        ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/"
        "ClientScreensNoDeviceComposeTest.kt"
    )
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
    client_screens_test_text = client_screens_test_path.read_text(encoding="utf-8", errors="replace")
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

    pairing_parser_path = ROOT / (
        "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/"
        "RuntimePairingPayload.kt"
    )
    pairing_parser_test_path = ROOT / (
        "apps/android/core/pairing/src/test/java/com/localagentbridge/android/core/pairing/"
        "RuntimePairingPayloadParserTest.kt"
    )
    pairing_store_path = ROOT / (
        "apps/android/core/pairing/src/main/java/com/localagentbridge/android/core/pairing/"
        "PairingStore.kt"
    )
    pairing_store_test_path = ROOT / (
        "apps/android/core/pairing/src/test/java/com/localagentbridge/android/core/pairing/"
        "PairingStoreTest.kt"
    )
    pairing_parser_text = pairing_parser_path.read_text(encoding="utf-8", errors="replace")
    pairing_parser_test_text = pairing_parser_test_path.read_text(encoding="utf-8", errors="replace")
    pairing_store_text = pairing_store_path.read_text(encoding="utf-8", errors="replace")
    pairing_store_test_text = pairing_store_test_path.read_text(encoding="utf-8", errors="replace")
    if "require(it.none(Char::isWhitespace)) { \"Invalid route token\" }" not in pairing_parser_text:
        failures.append(
            f"{pairing_parser_path.relative_to(ROOT)}: Android pairing route tokens must reject "
            "whitespace before trust/discovery matching."
        )
    if "RUNTIME_NAME_MAX_CHARS = 80" not in pairing_parser_text or "normalizedRuntimeName()" not in pairing_parser_text:
        failures.append(
            f"{pairing_parser_path.relative_to(ROOT)}: Android pairing runtime names must be normalized "
            "and capped before UI/storage."
        )
    if "rejectsRouteTokenWithWhitespaceForIdentityOnlyQrPayload" not in pairing_parser_test_text:
        failures.append(
            f"{pairing_parser_test_path.relative_to(ROOT)}: Missing identity-only route-token whitespace "
            "rejection regression test."
        )
    for snippet in (
        "normalizesBlankRuntimeNameToDefaultRuntimeName",
        "capsOversizedRuntimeNameBeforeUiOrStorage",
    ):
        if snippet not in pairing_parser_test_text:
            failures.append(
                f"{pairing_parser_test_path.relative_to(ROOT)}: Missing Android QR runtime-name "
                f"normalization regression test {snippet}."
            )
    if "loaded.shouldRemoveStoredRelayRoute" not in pairing_store_text or "editPrefs.removeRelayRouteKeys()" not in pairing_store_text:
        failures.append(
            f"{pairing_store_path.relative_to(ROOT)}: PairingStore must physically remove incomplete "
            "stored relay route keys after sanitizing trusted runtime state."
        )
    if "trusted.hasValidRelayRoute()" not in pairing_store_text or "runtime.hasValidRelayRoute()" not in pairing_store_text:
        failures.append(
            f"{pairing_store_path.relative_to(ROOT)}: PairingStore must only load and persist "
            "currently valid relay routes so expired relay secrets are physically removed."
        )
    required_relay_secret_store_snippets = (
        "interface RelaySecretStore",
        "class AndroidKeystoreRelaySecretStore",
        "runtimeRelaySecretRef",
        "relaySecretStore.saveSecret",
        "prefs.remove(Keys.runtimeRelaySecret)",
        "relaySecretHandle(",
    )
    for snippet in required_relay_secret_store_snippets:
        if snippet not in pairing_store_text:
            failures.append(
                f"{pairing_store_path.relative_to(ROOT)}: PairingStore must keep relay secrets behind "
                f"a secret-store handle boundary; missing {snippet}."
            )
    if "prefs[Keys.runtimeRelaySecret] =" in pairing_store_text:
        failures.append(
            f"{pairing_store_path.relative_to(ROOT)}: PairingStore must not write raw relay secrets "
            "back into DataStore."
        )
    for snippet in (
        "pairingStoreDropsIncompleteRelayRouteOnRead",
        "pairingStoreDropsExpiredCompleteRelayRouteOnWrite",
        "pairingStoreDropsExpiredStoredRelayRouteOnRead",
        "pairingStoreMigratesLegacyRawRelaySecretToSecretStoreOnRead",
        "pairingStoreDropsRelayRouteWhenStoredSecretRefCannotBeResolved",
        'assertEquals("secret-1", secretStore.secrets[relaySecretRef])',
        'assertNull(prefs[stringPreferencesKey("runtime_relay_secret")])',
        'assertNull(prefs[stringPreferencesKey("runtime_relay_secret_ref")])',
        'assertNull(prefs[stringPreferencesKey("runtime_relay_host")])',
        'assertNull(prefs[stringPreferencesKey("runtime_relay_nonce")])',
    ):
        if snippet not in pairing_store_test_text:
            failures.append(
                f"{pairing_store_test_path.relative_to(ROOT)}: Missing PairingStore incomplete or expired relay "
                f"route physical-cleanup regression {snippet}."
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
        "R.string.provider_status_row_summary",
        "R.string.provider_status_row_summary_retryable",
        "val rowAccessibilitySummary",
        ".semantics(mergeDescendants = true) {\n"
        "                        contentDescription = rowAccessibilitySummary",
        "provider_show_diagnostics_for",
        "provider_hide_diagnostics_for",
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
    if (
        'hasContentDescription("Show details for Ollama")' not in client_screens_test_text or
        'hasContentDescription("Hide details for LM Studio")' not in client_screens_test_text
    ):
        failures.append(
            f"{client_screens_test_path.relative_to(ROOT)}: Missing Android provider diagnostic "
            "toggle accessibility coverage that names repeated provider rows."
        )
    if "connectionStatusProviderRowsExposeLocalizedAccessibilitySummariesAcrossSupportedLanguages" not in client_screens_test_text:
        failures.append(
            f"{client_screens_test_path.relative_to(ROOT)}: Missing Android provider row "
            "accessibility summary coverage across supported languages."
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
    required_relay_auth_terminal_snippets = (
        "requiresFreshRemoteRouteBeforeReconnect()",
        "trustedRuntimeWithoutFailedRelay",
        "current.trustedRuntime?.withoutRelayRoute()",
        "pairingStore.trustRuntime(trusted)",
        "relayReceiveAuthenticationFailureClearsStoredRelayAndStopsAutoReconnect",
        "assertEquals(1, relayConnectionAttempts)",
    )
    for snippet in required_relay_auth_terminal_snippets:
        if snippet not in runtime_text and snippet not in runtime_test_text:
            failures.append(
                f"{runtime_path.relative_to(ROOT)} / {runtime_test_path.relative_to(ROOT)}: "
                "Android relay authentication failures must clear stale relay material and stop "
                "auto-retry until the latest QR provides a fresh route."
            )
    required_route_refresh_terminal_snippets = (
        "authenticatedTrustedRuntimeMarksRouteExpiredWhenRefreshErrorCannotRetryBeforeLeaseExpiry",
        "assertFalse(viewModel.state.value.isConnected)",
        "assertFalse(viewModel.state.value.isConnecting)",
        'assertEquals("failed", viewModel.state.value.runtimeStatus)',
        "assertNull(viewModel.state.value.activeRouteKind)",
    )
    for snippet in required_route_refresh_terminal_snippets:
        if snippet not in runtime_test_text:
            failures.append(
                f"{runtime_test_path.relative_to(ROOT)}: Missing Android terminal route.refresh "
                "expiry state regression coverage."
            )
    if (
        'isConnected = false,\n'
        '                isConnecting = false,\n'
        '                runtimeStatus = "failed",\n'
        '                activeRouteKind = null,\n'
        '                routeRefreshNoticeRuntimeName = null,' not in runtime_text
    ):
        failures.append(
            f"{runtime_path.relative_to(ROOT)}: Terminal route.refresh expiry must clear connected "
            "route state before asking the user to scan the latest QR."
        )
    required_expired_relay_purge_snippets = (
        "trustedRuntimeWithoutExpiredRelay",
        "trustedRuntimeWithoutExpiredRelay?.toTrustedRuntimeOrNull()?.let",
        "viewModelShowsExpiredRemoteRouteWhenTrustedRelayLeaseExpiredOnInit",
        "assertNull(viewModel.state.value.trustedRuntime?.relayHost)",
        "assertNull(viewModel.state.value.trustedRuntime?.relaySecret)",
        "assertNull(trustedStore.trusted?.relayHost)",
        "assertNull(trustedStore.trusted?.relaySecret)",
    )
    for snippet in required_expired_relay_purge_snippets:
        if snippet not in runtime_text and snippet not in runtime_test_text:
            failures.append(
                f"{runtime_path.relative_to(ROOT)} / {runtime_test_path.relative_to(ROOT)}: "
                "Android expired relay leases must purge stale relay material from UI state and trusted store."
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
        "remote_secret=remote-secret-value",
        "route_secret=route-secret-value",
        "rendezvous_secret=rendezvous-secret-value",
        "relay_id=relay-room-secret",
        "route_id=route-room-secret",
        "network_id=private-network-secret",
        "relay_nonce=nonce-secret-value",
        "rt=compact-route-token",
        "rs=compact-relay-secret",
        "ri=compact-route-id",
        "rrn=compact-nonce",
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
            "onClick(label = archiveActionContentDescription, action = null)",
            "Archive button semantics must expose the contextual chat-title click action label.",
        ),
        (
            "contentDescription = restoreActionContentDescription",
            "Restore button semantics must use the contextual chat-title label.",
        ),
        (
            "onClick(label = restoreActionContentDescription, action = null)",
            "Restore button semantics must expose the contextual chat-title click action label.",
        ),
        (
            "contentDescription = permanentlyDeleteActionContentDescription",
            "Permanent delete button semantics must use the contextual chat-title label.",
        ),
        (
            "onClick(label = permanentlyDeleteActionContentDescription, action = null)",
            "Permanent delete button semantics must expose the contextual chat-title click action label.",
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
            "val bulkActionsClickLabel = stringResource(",
            "Manage all chats must expose the current expand/collapse click action label.",
        ),
        (
            "onClick(label = bulkActionsClickLabel, action = null)",
            "Manage all chats must wire the expand/collapse click action label into semantics.",
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
            "accessibilitySubject: String",
            "Two-step confirmations must receive a destructive-action accessibility subject.",
        ),
        (
            "R.string.confirmation_continue_action_named",
            "Two-step confirmations must expose a contextual first-step action label.",
        ),
        (
            "R.string.confirmation_final_action_named",
            "Two-step confirmations must expose a contextual final-step action label.",
        ),
        (
            "contentDescription = confirmActionContentDescription",
            "Two-step confirmation buttons must expose the contextual subject as content description.",
        ),
        (
            "onClick(label = confirmActionContentDescription, action = null)",
            "Two-step confirmation buttons must expose the contextual subject as click label.",
        ),
        (
            "val rowAccessibilitySummary = stringResource(R.string.chat_session_row_summary, title, statusText)",
            "Settings chat-history rows must expose a localized title and status accessibility summary.",
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
        'hasClickActionLabel(context.getString(R.string.archive_chat_named, activeTitle))',
        'hasClickActionLabel(context.getString(R.string.restore_chat_named, archivedTitle))',
        'hasClickActionLabel(context.getString(R.string.permanently_delete_chat_named, archivedTitle))',
        "settingsPerChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages",
        "R.string.chat_history_action_state_wait_for_stream",
        "hasText(\"Manage all chats\") and\n"
        "                hasStateDescription(\"Collapsed\") and\n"
        "                hasClickActionLabel(\"Expand section\")",
        "hasText(\"Manage all chats\") and\n"
        "                hasStateDescription(\"Expanded\") and\n"
        "                hasClickActionLabel(\"Collapse section\")",
        "settingsScreenPerChatHistoryActionsUseConfirmationHaptics",
        "chatHistoryConfirmationActionLabelsLocalizeSubjectsAcrossSupportedLanguages",
        'hasContentDescription("Continue: Archive all chats")',
        'hasClickActionLabel("Confirm: Permanently delete chat Archived project chat")',
        "R.string.confirmation_continue_action_named",
        "R.string.confirmation_final_action_named",
        "settingsChatHistoryRowsExposeLocalizedAccessibilitySummaries",
        "settingsConnectionStatusHeroExposesLocalizedAccessibilitySummaries",
        "R.string.chat_session_row_summary",
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
            "onClick(label = actionLabel, action = null)",
            "Chat model rows must expose select/install click action labels.",
        ),
        (
            "contentDescription = clearModelSearchContentDescription",
            "Model search clear button must expose its contextual accessibility label on the actionable button.",
        ),
        (
            "onClick(label = clearModelSearchContentDescription, action = null)",
            "Model search clear button must expose a contextual click action label.",
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
        (
            "chatModelMenuItemContentDescription(",
            "Chat model rows must keep localized row-summary accessibility labels.",
        ),
        (
            "R.string.chat_model_row_summary_selected",
            "Selected chat model rows must use a selected row-summary string.",
        ),
        (
            "state.isStreaming -> stringResource(R.string.model_picker_state_wait_for_stream)",
            "Disabled chat model picker must explain the streaming lock state.",
        ),
        (
            "R.string.chat_model_picker_summary",
            "Closed chat model picker must expose a localized accessibility summary.",
        ),
        (
            "contentDescription = modelPickerContentDescription",
            "Closed chat model picker must attach its accessibility summary to the button.",
        ),
        (
            "onClick(label = modelPickerActionLabel, action = null)",
            "Closed chat model picker must expose an accessibility action label.",
        ),
        (
            "this.contentDescription = contentDescription",
            "Chat model rows must expose model name and status as one accessibility summary.",
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
    embedding_semantics_snippets = (
        "contentDescription: String",
        "this.contentDescription = contentDescription",
        "stateDescription = selectedStateDescription",
    )
    if any(snippet not in ui_text for snippet in embedding_semantics_snippets):
        failures.append(
            f"{ui_relative}: Settings embedding model rows must keep selected-state and row-summary accessibility semantics."
        )
    preference_semantics_snippets = (
        "selectedPreferenceOptionState(",
        "selectedStateDescription = selectedStateDescription",
        "contentDescription = optionAccessibilitySummary",
    )
    if any(snippet not in ui_text for snippet in preference_semantics_snippets):
        failures.append(
            f"{ui_relative}: Settings language and appearance rows must keep selected-state and row-summary accessibility semantics."
        )

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
        "chatTopBarModelPickerClosedButtonLocalizesSelectedModelSummaryAcrossSupportedLanguages",
        "chatTopBarModelPickerExposesSelectedRowsToAccessibility",
        "chatTopBarModelPickerExplainsDisabledStreamingStateAcrossSupportedLanguages",
        "chatTopBarModelPickerExposesInstallActionForUninstalledLocalChatModel",
        "chatTopBarModelPickerRowsExposeAccessibilitySummaries",
        "chatTopBarModelPickerRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages",
        "Chat model picker. Selected chat model Qwen3 8B.",
        "채팅 모델 선택기. 선택된 채팅 모델 Qwen3 8B.",
        "チャットモデルピッカー。選択中のチャットモデル「Qwen3 8B」。",
        "聊天模型选择器。已选聊天模型 Qwen3 8B。",
        "Sélecteur de modèle de chat. Modèle de chat sélectionné Qwen3 8B.",
        "Chat model picker. Qwen3 8B. Wait for the current response or cancel it before changing models.",
        "채팅 모델 선택기. Qwen3 8B. 현재 응답을 기다리거나 취소한 뒤 모델을 변경하세요.",
        "Sélecteur de modèle de chat. Qwen3 8B. Attendez la réponse en cours ou annulez-la avant de changer de modèle.",
        "Wait for the current response or cancel it before changing models.",
        "현재 응답을 기다리거나 취소한 뒤 모델을 변경하세요.",
        "Attendez la réponse en cours ou annulez-la avant de changer de modèle.",
        "Selected chat model Qwen3 8B. Ollama - Installed.",
        "Chat model Llama 3.1 8B. Ollama - Running.",
        "Chat model Gemma 4 26B. Ollama - Not installed.",
        'hasClickActionLabel("Choose model")',
        'hasClickActionLabel("Install model")',
        "선택된 채팅 모델 Qwen3 8B. Ollama - 설치됨.",
        "選択中のチャットモデル「Qwen3 8B」。Ollama - インストール済み。",
        "已选择聊天模型“Qwen3 8B”。Ollama - 已安装。",
        "Modèle de chat sélectionné « Qwen3 8B ». Ollama - Installé.",
        "chatTopBarModelPickerSearchClearsWithContextAndHapticFeedback",
        "chatTopBarModelPickerSearchLocalizesClearAndNoResultsAcrossSupportedLanguages",
        "Clear model search for missing",
        'hasClickActionLabel("Clear model search for missing")',
        "missing 검색어로 된 모델 검색 지우기",
        "Effacer la recherche de modèles pour missing",
        'hasStateDescription("Install model")',
        "settingsPreferenceRowsExposeSelectedStateToAccessibility",
        "settingsEmbeddingModelRowsExposeSelectedStateToAccessibility",
        "settingsEmbeddingModelRowsLocalizeAccessibilitySummariesAcrossSupportedLanguages",
        "settingsSavedEmbeddingModelRowLocalizesAccessibilitySummaryAcrossSupportedLanguages",
        "Selected memory indexing model Nomic Embed Text. Ollama - Installed.",
        "Saved memory indexing model $savedModelName. Saved memory indexing model is missing from the runtime list. Refresh or choose another.",
        "선택된 메모리 색인 모델 Nomic Embed Text. Ollama - 설치됨.",
        "저장된 메모리 색인 모델 $savedModelName. 저장된 메모리 색인 모델이 런타임 목록에 없습니다. 새로고침하거나 다른 모델을 선택하세요.",
        "保存済みのメモリ インデックスモデル「$savedModelName」。保存済みのメモリ インデックスモデルはランタイム一覧にありません。更新するか別のモデルを選択してください。",
        "已保存的记忆索引模型“$savedModelName”。已保存的记忆索引模型不在运行时列表中。请刷新或选择其他模型。",
        "Modèle d’indexation de la mémoire sélectionné « Nomic Embed Text ». Ollama - Installé.",
        "Modèle d’indexation de la mémoire enregistré « $savedModelName ». Le modèle d’indexation de la mémoire enregistré manque dans la liste du runtime. Actualisez ou choisissez-en un autre.",
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
    strings_path = ROOT / "apps/android/app/src/main/res/values/strings.xml"

    for path in (ui_path, test_path, compose_test_path, strings_path):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android suggested-question guard file.")
            return failures

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")
    strings_text = strings_path.read_text(encoding="utf-8", errors="replace")
    ui_relative = ui_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)
    strings_relative = strings_path.relative_to(ROOT)

    required_ui_snippets = (
        "internal fun normalizedSuggestedQuestions(",
        "SUGGESTED_QUESTION_MAX_ITEMS",
        ".filter { seen.add(it.lowercase(Locale.ROOT)) }",
        "val visibleSuggestions = normalizedSuggestedQuestions(suggestions)",
        "normalizedSuggestedQuestions(suggestions).isNotEmpty() || isLoadingSuggestions",
        "val generatingSuggestionsText = stringResource(R.string.generating_suggestions)",
        "liveRegion = LiveRegionMode.Polite",
        "contentDescription = generatingSuggestionsText",
        "suggestionContentDescription = stringResource(R.string.content_desc_suggested_question, text)",
        "val suggestionClickLabel = stringResource(R.string.action_use_suggested_question)",
        "onClickLabel = suggestionClickLabel",
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
        "chatScreenGeneratingSuggestionsRowAnnouncesAcrossSupportedLanguages",
        "Suggested question: Summarize again?",
        ".getString(R.string.generating_suggestions)",
        ".assert(hasPoliteLiveRegion())",
        'hasClickActionLabel("Insert suggested question")',
        )
    for snippet in required_compose_snippets:
        if snippet not in compose_test_text:
            failures.append(f"{compose_test_relative}: Missing suggested-question Compose rendering regression {snippet}.")

    if "CHAT_MESSAGE_LIST_TEST_TAG" not in ui_text:
        failures.append(f"{ui_relative}: Missing stable chat list test tag for jump-to-latest coverage.")
    if "jumpToLatestStateDescription" not in ui_text or "stateDescription = jumpToLatestStateDescription" not in ui_text:
        failures.append(f"{ui_relative}: Jump-to-latest action must expose localized readiness state to accessibility.")
    if 'name="jump_to_latest_state_ready"' not in strings_text:
        failures.append(f"{strings_relative}: Missing jump-to-latest accessibility state string.")

    required_jump_to_latest_snippets = (
        "chatScreenJumpToLatestAppearsAfterScrollingAwayAndReturnsToLatestMessage",
        "chatScreenJumpToLatestActionExplainsStateAcrossSupportedLanguages",
        "CHAT_MESSAGE_LIST_TEST_TAG",
        "performScrollToIndex(messages.lastIndex)",
        'onNodeWithContentDescription("Jump to latest message")',
        'hasStateDescription("Ready to return to the latest message.")',
        "hasContentDescription(expected.jumpAction) and hasStateDescription(expected.jumpState)",
    )
    for snippet in required_jump_to_latest_snippets:
        if snippet not in compose_test_text:
            failures.append(f"{compose_test_relative}: Missing chat jump-to-latest Compose regression {snippet}.")

    return failures


def android_reasoning_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"
    string_paths = sorted(ROOT.glob("apps/android/app/src/main/res/values*/strings.xml"))

    for path in (ui_path, compose_test_path, *string_paths):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android reasoning accessibility guard file.")
            return failures

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")
    ui_relative = ui_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)

    required_ui_snippets = (
        "val reasoningLabel = stringResource(R.string.assistant_reasoning_label)",
        "R.string.assistant_reasoning_summary",
        "displayPolicy.text.replace(Regex(\"\\\\s+\"), \" \")",
        "contentDescription = accessibilitySummary",
    )
    for snippet in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: Missing Android reasoning accessibility summary policy {snippet}.")

    required_compose_snippets = (
        "chatScreenRendersReasoningCollapsedAndExpandable",
        "chatScreenReasoningSummaryLocalizesAcrossSupportedLanguages",
        "Thinking. Collapsed. first step second step third step",
        "Thinking. Expanded. first step second step third step fourth step",
        "hasContentDescription(expectedSummary)",
        'hasClickActionLabel("Show thinking")',
        'hasClickActionLabel("Hide thinking")',
    )
    for snippet in required_compose_snippets:
        if snippet not in compose_test_text:
            failures.append(
                f"{compose_test_relative}: Missing Android reasoning accessibility Compose regression {snippet}."
            )

    for path in string_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if 'name="assistant_reasoning_summary"' not in text:
            failures.append(
                f"{path.relative_to(ROOT)}: Missing localized assistant_reasoning_summary resource."
            )

    return failures


def android_streaming_assistant_live_region_guard_failures() -> list[str]:
    failures: list[str] = []
    ui_path = ROOT / "apps/android/app/src/main/java/com/localagentbridge/android/ui/ClientScreens.kt"
    compose_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/ui/ClientScreensNoDeviceComposeTest.kt"
    string_paths = sorted(ROOT.glob("apps/android/app/src/main/res/values*/strings.xml"))

    for path in (ui_path, compose_test_path, *string_paths):
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: missing Android streaming assistant live-region guard file.")
            return failures

    ui_text = ui_path.read_text(encoding="utf-8", errors="replace")
    compose_test_text = compose_test_path.read_text(encoding="utf-8", errors="replace")
    ui_relative = ui_path.relative_to(ROOT)
    compose_test_relative = compose_test_path.relative_to(ROOT)

    required_ui_snippets = (
        "val assistantTypingText = stringResource(R.string.assistant_typing)",
        "assistantShowsTypingPlaceholder(message, isStreaming)",
        "liveRegion = LiveRegionMode.Polite",
        "contentDescription = assistantTypingText",
    )
    for snippet in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: Missing Android streaming assistant live-region policy {snippet}.")

    required_compose_snippets = (
        "chatScreenStreamingAssistantPlaceholderAnnouncesLiveStatusAcrossSupportedLanguages",
        "compose.onNodeWithText(expectedTyping).assertIsDisplayed()",
        "hasContentDescription(expectedTyping) and hasPoliteLiveRegion()",
        "listOf(\"en\", \"ko\", \"ja\", \"zh-CN\", \"fr\")",
    )
    for snippet in required_compose_snippets:
        if snippet not in compose_test_text:
            failures.append(
                f"{compose_test_relative}: Missing Android streaming assistant live-region Compose regression {snippet}."
            )

    for path in string_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if 'name="assistant_typing"' not in text:
            failures.append(f"{path.relative_to(ROOT)}: Missing localized assistant_typing resource.")

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
        "internal fun chatInputHintRes(state: RuntimeUiState): Int?",
        "state.trustedRuntime == null -> R.string.chat_hint_pairing",
        "!state.isConnected && !hasConnectableTrustedRuntimeRoute(state) -> R.string.chat_hint_scan_latest_qr",
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
        'name="chat_hint_scan_latest_qr"',
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
        "chatComposerHintRequestsLatestQrWhenTrustedRuntimeNeedsRouteRefresh",
        "chatComposerHintStillRequestsConnectWhenTrustedRuntimeHasRouteCandidate",
        "emptyChatPrefersQrRefreshForRejectedDirectQrRoute",
        "emptyChatPrefersQrRefreshForExpiredRemoteRoute",
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
        (
            "stringResource(R.string.forget_trusted_runtime_named, runtime.name)",
            "Trusted runtime forget button must include the runtime name in its accessibility label.",
        ),
        (
            "contentDescription = it",
            "Trusted runtime forget button must attach its named accessibility label to semantics.",
        ),
    )
    for snippet, guidance in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: {guidance}")

    required_test_snippets = (
        "settingsTrustedRuntimeForgetRequiresConfirmation",
        "settingsTrustedRuntimeForgetActionNamesRuntimeAcrossSupportedLanguages",
        'compose.onNodeWithText("Forget trusted runtime?").assertIsDisplayed()',
        "R.string.forget_trusted_runtime_named",
        "onNodeWithContentDescription(expectedActionLabel)",
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
        "forget_trusted_runtime_named",
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
            "val newChatStateDescription = newChatActionStateDescription(state)",
            "New Chat actions must expose pairing-required, ready, or streaming-disabled state to accessibility.",
        ),
        (
            "stateDescription = newChatStateDescription",
            "New Chat actions must attach their readiness state to accessibility.",
        ),
        (
            "onClick(label = newChatActionLabel, action = null)",
            "New Chat actions must expose their localized click action label.",
        ),
        (
            "private fun newChatActionStateDescription(state: RuntimeUiState): String",
            "New Chat actions must use one localized helper for pairing-required, ready, and streaming-disabled states.",
        ),
        (
            "internal fun newChatActionEnabled(state: RuntimeUiState): Boolean",
            "New Chat actions must use one testable state policy.",
        ),
        (
            "state.trustedRuntime != null && !state.isStreaming",
            "New Chat actions must require a trusted runtime and an idle stream.",
        ),
        (
            "state.trustedRuntime == null -> stringResource(R.string.new_chat_state_pairing_required)",
            "New Chat actions must explain that pairing is required before first chat.",
        ),
        (
            "R.string.new_chat_state_ready",
            "New Chat actions must use localized ready-state accessibility copy.",
        ),
        (
            "R.string.new_chat_state_wait_for_stream",
            "New Chat actions must use localized streaming-disabled reason.",
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
            "renameActionContentDescription = stringResource(R.string.rename_chat_named, title)",
            "Drawer rename menu item must include the chat title in its accessibility label.",
        ),
        (
            "deleteActionContentDescription = stringResource(R.string.delete_chat_named, title)",
            "Drawer delete menu item must include the chat title in its accessibility label.",
        ),
        (
            "contentDescription = renameActionContentDescription",
            "Drawer rename menu item must expose its contextual chat-title label.",
        ),
        (
            "onClick(label = renameActionContentDescription, action = null)",
            "Drawer rename menu item must expose a contextual click action label.",
        ),
        (
            "contentDescription = archiveActionContentDescription",
            "Drawer archive menu item must expose its contextual chat-title label.",
        ),
        (
            "onClick(label = archiveActionContentDescription, action = null)",
            "Drawer archive menu item must expose a contextual click action label.",
        ),
        (
            "contentDescription = restoreActionContentDescription",
            "Drawer restore menu item must expose its contextual chat-title label.",
        ),
        (
            "onClick(label = restoreActionContentDescription, action = null)",
            "Drawer restore menu item must expose a contextual click action label.",
        ),
        (
            "contentDescription = deleteActionContentDescription",
            "Drawer delete menu item must expose its contextual chat-title label.",
        ),
        (
            "onClick(label = deleteActionContentDescription, action = null)",
            "Drawer delete menu item must expose a contextual click action label.",
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
            "internal fun RenameChatSessionDialog(",
            "Rename chat dialog must stay directly testable without launching the full app shell.",
        ),
        (
            "R.string.rename_chat_title_state_empty",
            "Rename chat title field must use localized empty-state accessibility copy.",
        ),
        (
            "R.string.rename_chat_title_state_ready",
            "Rename chat title field must use localized ready-state accessibility copy.",
        ),
        (
            "stateDescription = titleStateDescription",
            "Rename chat title field and Save action must expose readiness state to accessibility.",
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
            "                        if (cameraPermissionPermanentlyDenied)",
            "QR scanner permission and settings actions must keep primary-action haptic.",
        ),
        (
            "onOpenAppSettings()",
            "QR scanner permanently denied camera permission state must open app settings.",
        ),
        (
            "onRequestCameraPermission()",
            "QR scanner normal camera permission state must still request camera permission.",
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
            "val scanQrStateDescription = if (state.isConnecting)",
            "Settings QR-first scan action must expose why scanning is unavailable while connecting.",
        ),
        (
            "stateDescription = scanQrStateDescription",
            "Settings QR-first scan action must attach its readiness state to accessibility.",
        ),
        (
            "R.string.scan_qr_state_connecting",
            "Settings QR-first scan action must use localized connecting-state disabled reason.",
        ),
        (
            "R.string.scan_qr_state_ready",
            "Settings QR-first scan action must use localized ready-state accessibility copy.",
        ),
        (
            "manualPairingPayloadStateDescriptionRes(payload, sanitizedPayload)",
            "Diagnostic QR text dialog must derive empty, invalid, and ready accessibility states.",
        ),
        (
            "isError = payloadIsInvalid",
            "Diagnostic QR text field must expose invalid QR text as an error state.",
        ),
        (
            "stateDescription = payloadStateDescription",
            "Diagnostic QR text field and submit action must attach readiness state to accessibility.",
        ),
        (
            "contentDescription = payloadInputAccessibilityLabel",
            "Diagnostic QR text field must expose a contextual accessibility label.",
        ),
        (
            "contentDescription = payloadSubmitAccessibilityLabel",
            "Diagnostic QR text submit action must expose a contextual accessibility label.",
        ),
        (
            "onClick(label = payloadSubmitAccessibilityLabel, action = null)",
            "Diagnostic QR text submit action must expose a contextual click label.",
        ),
        (
            "contentDescription = payloadCancelAccessibilityLabel",
            "Diagnostic QR text cancel action must expose a contextual accessibility label.",
        ),
        (
            "onClick(label = payloadCancelAccessibilityLabel, action = null)",
            "Diagnostic QR text cancel action must expose a contextual click label.",
        ),
        (
            "R.string.manual_qr_payload_state_empty",
            "Diagnostic QR text dialog must use localized empty-state guidance.",
        ),
        (
            "R.string.manual_qr_payload_state_invalid",
            "Diagnostic QR text dialog must use localized invalid-state guidance.",
        ),
        (
            "R.string.manual_qr_payload_state_ready",
            "Diagnostic QR text dialog must use localized ready-state guidance.",
        ),
        (
            "val connectStateDescription = pairingConnectButtonStateDescription(state, action)",
            "Settings trusted-runtime connect action must expose readiness and connecting state.",
        ),
        (
            "stateDescription = connectStateDescription",
            "Settings trusted-runtime connect action must attach its accessibility state.",
        ),
        (
            "val modelRefreshStateDescription = modelRefreshButtonStateDescription(state)",
            "Model refresh actions must expose ready, loading, or disconnected state to accessibility.",
        ),
        (
            "stateDescription = modelRefreshStateDescription",
            "Model refresh actions must attach their readiness state to accessibility.",
        ),
        (
            "private fun modelRefreshButtonStateDescription(state: RuntimeUiState): String",
            "Model refresh actions must use one localized helper for ready/loading/disconnected states.",
        ),
        (
            "R.string.model_refresh_state_ready",
            "Model refresh actions must use localized ready-state accessibility copy.",
        ),
        (
            "R.string.model_refresh_state_loading",
            "Model refresh actions must use localized loading-state accessibility copy.",
        ),
        (
            "R.string.model_refresh_state_connect_first",
            "Model refresh actions must use localized disconnected disabled reason.",
        ),
        (
            "chatEmptyPrimaryActionStateDescription(state, primaryAction)",
            "Chat empty-state primary action must expose readiness and connecting state.",
        ),
        (
            "stateDescription = primaryActionStateDescription",
            "Chat empty-state primary action must attach its accessibility state.",
        ),
        (
            "R.string.connect_runtime_state_connecting",
            "Connect actions must use localized connecting disabled reason.",
        ),
        (
            "R.string.connect_runtime_state_ready",
            "Connect actions must use localized ready-state accessibility copy.",
        ),
        (
            "R.string.connect_remote_route",
            "Remote-route connect actions must use a distinct localized label.",
        ),
        (
            "refreshHealthStateDescription",
            "Connected refresh-health action must expose a localized accessibility state.",
        ),
        (
            "disconnectStateDescription",
            "Connected disconnect action must expose a localized accessibility state.",
        ),
        (
            "stateDescription = refreshHealthStateDescription",
            "Connected refresh-health action must attach its accessibility state.",
        ),
        (
            "stateDescription = disconnectStateDescription",
            "Connected disconnect action must attach its accessibility state.",
        ),
        (
            "R.string.refresh_health_state_ready",
            "Connected refresh-health action must use localized ready-state accessibility copy.",
        ),
        (
            "val refreshHealthStateDescription = stringResource(R.string.refresh_health_state_ready)",
            "Backend readiness refresh action must use localized ready-state accessibility copy.",
        ),
        (
            "R.string.disconnect_runtime_state_ready",
            "Connected disconnect action must use localized ready-state accessibility copy.",
        ),
        (
            "onClickLabel = toggleActionLabel",
            "Expandable settings and diagnostics sections must expose localized accessibility action labels.",
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
            "cancelGenerationStateDescription",
            "Cancel-generation button must keep an accessibility state description.",
        ),
        (
            "stateDescription = cancelGenerationStateDescription",
            "Cancel-generation button must expose readiness to accessibility.",
        ),
        (
            "R.string.cancel_generation_state_ready",
            "Cancel-generation button must use localized ready-state accessibility copy.",
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
            "onClickLabel = actionLabel",
            "Connection route notice cards must expose localized accessibility action labels.",
        ),
        (
            "R.string.route_notice_accessibility_summary",
            "Connection route notice cards must expose a merged accessibility summary.",
        ),
        (
            "R.string.route_notice_accessibility_summary_with_steps",
            "Connection route notice cards must include QR recovery steps in accessibility summaries.",
        ),
        (
            "routeNoticeRecoverySteps(notice)",
            "Connection route notice cards must render QR recovery steps for refresh-needed states.",
        ),
        (
            "R.string.route_notice_recovery_steps",
            "Connection route notice cards must use localized QR recovery-step copy.",
        ),
        (
            "contentDescription = accessibilitySummary",
            "Connection route notice cards must attach the merged accessibility summary to the actionable card.",
        ),
        (
            "stateDescription = body",
            "Connection route notice cards must expose their visible guidance as accessibility state.",
        ),
        (
            "it.requiresLatestQrRouteNotice()",
            "Connection route notices must turn stale relay failures into latest-QR recovery guidance.",
        ),
        (
            "detailRes = routeAvailabilityCompactLabelRes(routeError)",
            "Connection route notices must reuse the structured route diagnostic copy for latest-QR recovery.",
        ),
        (
            "error?.code == \"remote_route_auth_failed\"",
            "Chat empty-state copy must explain relay authentication failures before asking for a fresh QR.",
        ),
        (
            "error?.code == \"pairing_direct_route_rejected\"",
            "Chat empty-state copy must explain nearby-only QR rejection before asking for a fresh QR.",
        ),
        (
            "error?.code == \"remote_route_expired\"",
            "Chat empty-state copy must explain expired remote routes before asking for a fresh QR.",
        ),
        (
            "R.string.status_hero_accessibility_summary",
            "Connection status hero must build a localized card-level accessibility summary.",
        ),
        (
            ".semantics(mergeDescendants = true) {\n"
            "                contentDescription = accessibilitySummary",
            "Connection status hero must expose one merged accessibility summary.",
        ),
        (
            "R.string.chat_backend_unavailable_summary",
            "Backend readiness banner must build a localized accessibility summary.",
        ),
        (
            "R.string.error_accessibility_summary",
            "Generic error banner must build a localized accessibility summary.",
        ),
        (
            "contentDescription = accessibilitySummary",
            "Backend readiness and generic error banners must expose the combined safe summary to accessibility.",
        ),
        (
            "liveRegion = LiveRegionMode.Polite",
            "Backend readiness and generic error banners must announce new error states politely.",
        ),
        (
            ".clearAndSetSemantics {\n"
            "                contentDescription = accessibilitySummary",
            "Generic error banner must expose one grouped accessibility target.",
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
            "onClick(label = attachFilesActionLabel)",
            "Composer attach button must expose its localized click action label.",
        ),
        (
            "onClick(label = sendActionLabel)",
            "Composer send button must expose its localized click action label.",
        ),
        (
            "onClick(label = cancelGenerationActionLabel)",
            "Composer cancel button must expose its localized click action label.",
        ),
        (
            "onClick(label = removeAttachmentActionLabel)",
            "Attachment remove buttons must expose their contextual click action label.",
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
            "val copyCodeBlockLabel = when {",
            "Code-block copy buttons must derive a code-specific accessibility label.",
        ),
        (
            "R.string.copy_code_block_named",
            "Multiple code-block copy buttons must expose language and ordinal context.",
        ),
        (
            "R.string.copy_code_block_numbered",
            "Multiple unlabeled code-block copy buttons must expose ordinal context.",
        ),
        (
            "contentDescription = copyActionLabel",
            "Copy buttons must expose their localized label on the actionable button.",
        ),
        (
            "onClick(label = copyActionLabel, action = null)",
            "Copy buttons must expose localized click action labels.",
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
            "autoReconnectActionLabel",
            "Auto reconnect switch must expose localized enable/disable action labels.",
        ),
        (
            "stateDescription = diagnosticsStateDescription",
            "Connection troubleshooting switch must expose localized on/off state to accessibility.",
        ),
        (
            "diagnosticsActionLabel",
            "Connection troubleshooting switch must expose localized enable/disable action labels.",
        ),
        (
            "disabledActionStateDescription = attachFilesStateDescription.takeUnless { enabled }",
            "Attachment remove buttons must reuse the composer disabled reason.",
        ),
        (
            "stateDescription = disabledActionStateDescription",
            "Disabled attachment remove buttons must expose the disabled reason to accessibility.",
        ),
        (
            "text = emptyBody,\n"
            "                style = MaterialTheme.typography.bodyMedium,\n"
            "                color = MaterialTheme.colorScheme.secondary,\n"
            "                textAlign = TextAlign.Center,\n"
            "            )",
            "Chat empty-state detail copy must wrap fully instead of truncating route-recovery guidance.",
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
            "routeUnavailableSummary = stringResource(",
            "Unavailable discovered runtime rows must build contextual accessibility summaries.",
        ),
        (
            "contentDescription = routeUnavailableSummary",
            "Unavailable discovered runtime rows must include runtime name and reason in accessibility labels.",
        ),
        (
            "startDiscoveryStateDescription = stringResource(",
            "Start discovery action must expose localized readiness/running state to accessibility.",
        ),
        (
            "stopDiscoveryStateDescription = stringResource(",
            "Stop discovery action must expose localized ready/idle state to accessibility.",
        ),
        (
            "stateDescription = startDiscoveryStateDescription",
            "Start discovery action must attach its accessibility state.",
        ),
        (
            "stateDescription = stopDiscoveryStateDescription",
            "Stop discovery action must attach its accessibility state.",
        ),
        (
            "settingsSectionExpandedStateDescriptionRes()",
            "Expandable Settings sections must use localized expanded state copy.",
        ),
        (
            "FilledTonalIconButton(\n"
            "                onClick = { toggleExpanded() },\n"
            "                modifier = Modifier.clearAndSetSemantics {},",
            "Settings expandable section trailing icon must not create a duplicate accessibility target.",
        ),
        (
            "R.string.preference_option_accessibility_summary",
            "Settings preference option rows must expose group plus option summaries to accessibility.",
        ),
        (
            "contentDescription = optionAccessibilitySummary",
            "Settings preference option row semantics must include the localized group plus option summary.",
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
            "memoryAddStateDescription = when {",
            "Memory add button must expose why it is locked, empty, or ready through accessibility state.",
        ),
        (
            "stateDescription = memoryAddStateDescription",
            "Memory add controls must attach localized readiness state to semantics.",
        ),
        (
            "memoryAddContentDescription = stringResource(R.string.memory_add_label)",
            "Memory add input field must derive a stable accessibility label from localized resources.",
        ),
        (
            "contentDescription = memoryAddContentDescription",
            "Memory add input field must expose the stable accessibility label.",
        ),
        (
            "memoryAccessibilityActionLabel(",
            "Memory action labels must pass through the accessibility label cap helper.",
        ),
        (
            "MEMORY_ACTION_LABEL_MAX_CHARS = 80",
            "Memory action accessibility labels must keep a stable cap.",
        ),
        (
            "memoryRemoveContentDescription = stringResource(R.string.memory_remove_named, memoryActionLabel)",
            "Memory remove buttons must include the memory text in their accessibility label.",
        ),
        (
            "contentDescription = memoryRemoveContentDescription",
            "Memory delete confirmation must expose the memory text in its accessibility label.",
        ),
        (
            "onClick(label = memoryRemoveContentDescription, action = null)",
            "Memory delete confirmation must expose the memory text in its click action label.",
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
        (
            "onClick(label = memoryToggleContentDescription, action = null)",
            "Memory enable/pause switches must expose their localized action label.",
        ),
        (
            "onClick(label = memoryRemoveContentDescription, action = null)",
            "Memory remove buttons must expose their localized action label.",
        ),
        (
            "val composerStateDescription = when {",
            "Chat composer input must derive the same localized readiness state as send/attach controls.",
        ),
        (
            "stateDescription = composerStateDescription",
            "Chat composer input must expose its localized readiness state to accessibility.",
        ),
        (
            "private fun ComposerStatus(",
            "Chat composer visible readiness status must remain centralized for accessibility coverage.",
        ),
        (
            ".semantics(mergeDescendants = true)",
            "Chat composer visible readiness status must merge its decorative dot and text into one accessibility element.",
        ),
        (
            "liveRegion = LiveRegionMode.Polite",
            "Chat composer visible readiness status must announce readiness changes politely.",
        ),
        (
            "contentDescription = text",
            "Chat composer visible readiness status must expose the same localized status copy to accessibility.",
        ),
        (
            "KeyboardActions(",
            "Chat composer must wire the soft-keyboard send action.",
        ),
        (
            "ImeAction.Send",
            "Chat composer must expose a send IME action.",
        ),
        (
            "LocalCopySuccessAnnouncer",
            "Chat copy actions must route successful copies into an accessibility announcement channel.",
        ),
        (
            "CopySuccessLiveRegion(message = announcement.message)",
            "Chat copy success feedback must render a dedicated accessibility live-region node.",
        ),
        (
            "liveRegion = LiveRegionMode.Polite",
            "Chat copy success feedback must use a polite live region for screen readers.",
        ),
        (
            "val notice = stringResource(R.string.route_refresh_notice, runtimeName)",
            "Route-refresh QR confirmation must expose one localized accessibility announcement.",
        ),
        (
            "R.string.pending_pairing_route_accessibility_summary",
            "Pending QR-route state must expose a single localized accessibility summary resource.",
        ),
    )
    for snippet, guidance in required_ui_snippets:
        if snippet not in ui_text:
            failures.append(f"{ui_relative}: {guidance}")

    required_test_snippets = (
        "aetherLinkHapticPolicyKeepsOrdinaryActionsLightweight",
        "aetherLinkHapticPolicyKeepsStrongActionsDistinct",
        "selectionChangeHapticOnlyRunsWhenSelectionChanges",
        "newChatActionRequiresTrustedRuntimeAndIdleStream",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing Android haptic policy regression test {snippet}.")

    required_compose_test_snippets = (
        "connectionStatusSavedRouteNoticeClickConnectsWithHaptic",
        "connectionStatusRefreshNeededRouteNoticeClickScansLatestQrWithHaptic",
        "routeNoticeShowsQrRefreshForRelayAuthenticationFailure",
        "Open AetherLink Runtime, generate the latest QR, then scan it here.",
        "chatScreenRelayAuthFailureAfterRouteClearKeepsLatestQrRecoveryAction",
        "Saved connection details could not be authenticated. Scan a fresh QR from the trusted runtime.",
        "connectionStatusProviderDiagnosticsToggleExposesExpandedState",
        "chatScreenBackendUnavailableBannerExposesAccessibilitySummaryAndRefreshCallback",
        "chatScreenBackendUnavailableRefreshActionExplainsStateAcrossSupportedLanguages",
        "chatScreenBackendUnavailableSummaryResourceFormatsAcrossSupportedLanguages",
        "chatScreenGenericErrorBannerExposesAccessibilitySummaryAndRedactsUnsafeDetail",
        "chatScreenGenericErrorAccessibilitySummaryLocalizesAcrossSupportedLanguages",
        ".assert(hasPoliteLiveRegion())",
        "Error. Could not send the message to AetherLink Runtime. More information: relay timed out",
        "Model service needs attention. Check the model service in AetherLink Runtime, then refresh health.",
        "모델 서비스 확인 필요. AetherLink Runtime에서 모델 서비스 상태를 확인한 다음 상태를 새로고침하세요.",
        "settingsExpiredRelayRoutePrimaryActionScansLatestQrWithHaptic",
        "settingsConnectedTrustedRuntimeDoesNotExposePairingConnectButton",
        "connectionStatusRefreshHealthActionUsesActionCopyAndCallback",
        "connectionStatusConnectedActionsExplainStateAcrossSupportedLanguages",
        "Refresh health",
        "hasStateDescription(\"Ready to refresh runtime health.\") and hasClickAction()",
        "onNodeWithText(expected.refreshAction)",
        "hasStateDescription(expected.refreshState) and hasClickAction()",
        "onNodeWithText(expected.disconnectAction)",
        "hasStateDescription(expected.disconnectState) and hasClickAction()",
        "settingsExpandableSectionsExposeLocalizedExpandedState",
        "onAllNodesWithContentDescription(\n"
        "            \"Expand section\",\n"
        "            useUnmergedTree = true,\n"
        "        ).assertCountEquals(0)",
        "onAllNodesWithContentDescription(\n"
        "            \"Collapse section\",\n"
        "            useUnmergedTree = true,\n"
        "        ).assertCountEquals(0)",
        "Chat options for Trip plan",
        "Chat Trip plan. 3 messages - Needs attention.",
        "Selected chat One note. 1 message.",
        "chatDrawerOverflowMenuActionsKeepChatContextAcrossSupportedLanguages",
        "Rename chat Trip plan",
        "Archive chat Trip plan",
        "Restore chat Trip plan",
        "Delete chat Trip plan",
        "hasContentDescription(label) and hasClickActionLabel(label)",
        "chatScreenAttachmentChipsExposeFileStateToAccessibility",
        "chatScreenAttachmentSizeUsesSelectedAppLanguageContext",
        "Formatter.formatFileSize(localizedContext, attachment.sizeBytes)",
        "chatScreenMessageAttachmentChipsExposeFileStateToAccessibility",
        "chatScreenMessageCopyActionsExposeLocalizedActionLabels",
        "chatScreenCodeBlockCopyUsesLocalizedCodeActionLabels",
        "chatScreenMultipleCodeBlockCopyActionsLocalizeDistinctContextAcrossSupportedLanguages",
        "settingsScreenAnnouncesRouteRefreshSavedNotice",
        "hasContentDescription(\"QR scanned. $pendingDetail Waiting for AetherLink Runtime\")",
        "hasContentDescription(notice) and\n"
        "                hasPoliteLiveRegion()",
        "hasLongClickActionLabel(expected.copyAction)",
        "hasClickActionLabel(expected.codeCopyAction)",
        "hasClickActionLabel(expected.firstCodeCopyAction)",
        "hasClickActionLabel(expected.secondCodeCopyAction)",
        "Copy Kotlin code block 1",
        "Copy SQL code block 2",
        "Copy code block",
        "코드 블록 복사",
        "Copier le bloc de code",
        "Attachment diagram.png, Vision model required",
        "Attachment diagram.png, Image",
        "settingsMemoryRowsExposeContextualActionAccessibility",
        "settingsAutoReconnectSwitchExposesAccessibilityState",
        'hasClickActionLabel("Disable Auto reconnect")',
        'hasClickActionLabel("Enable Auto reconnect")',
        "settingsDiscoveredRuntimeActionsUseContextualAccessibilityLabels",
        "settingsDiscoveredRuntimeUnavailableRowsExposeContextualAccessibilityLabels",
        "settingsDiscoveryActionsExplainIdleAndRunningStatesAcrossSupportedLanguages",
        "hasText(expected.startLabel) and hasStateDescription(expected.startReadyState)",
        "hasText(expected.runningLabel) and hasStateDescription(expected.startRunningState)",
        "hasText(expected.stopLabel) and hasStateDescription(expected.stopIdleState)",
        "hasText(expected.stopLabel) and hasStateDescription(expected.stopReadyState)",
        "Studio Runtime. Trust details hidden. QR required.",
        "Desk Runtime. Different trusted runtime. Not trusted.",
        "chatScreenSendButtonLocalizesReadinessStateAcrossSupportedLanguages",
        "chatScreenRouteRecoveryEmptyStateShowsFullGuidanceOnNarrowWidth",
        "chatScreenRouteRecoveryEmptyStateAnnouncesLocalizedSummary",
        "chat_empty_state_accessibility_summary",
        "hasContentDescription(expectedSummary)",
        "This network cannot reach the saved route. Prepare a reachable connection route in AetherLink Runtime, then scan the latest QR.",
        "Modifier.width(260.dp).height(720.dp)",
        "chatScreenExpiredRemoteRouteShowsLatestQrRecoveryAction",
        "chatScreenExpiredRemoteRouteRecoveryLocalizesAcrossSupportedLanguages",
        "chatScreenRouteAvailabilityNoticeExposesStateAndAction",
        "route_diagnostic_remote_route_expired",
        "Ready to scan the latest QR.",
        "최신 QR 스캔",
        "最新 QR をスキャン",
        "扫描最新二维码",
        "Scanner dernier QR",
        "relayExpiresAtEpochMillis = 1L",
        "hasContentDescription(expected.messageField) and hasStateDescription(expected.emptyState)",
        "hasContentDescription(expected.messageField) and hasStateDescription(expected.readyState)",
        "Saisissez un message à envoyer.",
        "전송할 준비가 되었습니다.",
        "waitForCopiedAnnouncement(expected.copiedResult)",
        "hasPoliteLiveRegion()",
        "settingsScreenKeepsBulkChatHistoryActionsHiddenAndTwoStepConfirmed",
        "settingsBulkChatHistoryActionsExplainStreamingDisabledStateAcrossSupportedLanguages",
        "settingsBulkChatHistoryActionsExplainMissingChatDisabledStates",
        "Wait for the current response before archiving chats.",
        "No active chats to archive.",
        "No archived chats to permanently delete.",
        "settingsChatHistorySearchClearsWithContextAndHapticFeedback",
        "settingsChatHistorySearchLocalizesClearAndNoResultsAcrossSupportedLanguages",
        "SETTINGS_CHAT_HISTORY_SEARCH_TEST_TAG",
        "settingsScreenKeepsEndpointInputsBehindDeveloperDiagnosticsSwitch",
        "settingsPairingScanQrActionExplainsDisabledConnectingState",
        "hasStateDescription(\"Wait for the current connection attempt before scanning again.\")",
        "diagnosticQrTextDialogExplainsEmptyInvalidAndReadyStates",
        "Paste AetherLink Runtime QR text before continuing.",
        "Use AetherLink Runtime QR text that starts with aetherlink://pair.",
        "Ready to use QR text.",
        "settingsPairingConnectActionExplainsDisabledConnectingState",
        "chatScreenConnectActionExplainsDisabledConnectingState",
        "hasStateDescription(\"Connection attempt in progress.\")",
        "connectionStatusScreenShowsPlatformNeutralConnectGuidanceAcrossSupportedLanguages",
        "Use Connect to restore Desk Runtime.",
        "자동 재연결이 일시 중지되었습니다. 연결을 사용하면 신뢰된 런타임 복구가 다시 켜집니다.",
        "settingsModelRefreshActionLocalizesReadinessStates",
        "Ready to refresh models.",
        "Model refresh in progress.",
        "Connect to the trusted runtime before refreshing models.",
        "newChatActionsExplainDisabledStreamingStateAcrossSupportedLanguages",
        "newChatActionsExplainPairingRequiredStateAcrossSupportedLanguages",
        "permanentNavigationRailUsesNewChatPairingGateAndHaptics",
        "Wait for the current response or cancel it before starting a new chat.",
        "Pair with AetherLink Runtime before starting a new chat.",
        "chatScreenStreamingShowsCancelActionInsteadOfSend",
        "chatScreenStreamingCancelActionExplainsStateAcrossSupportedLanguages",
        "hasStateDescription(\"Ready to attach files.\")",
        "hasStateDescription(\"Select a model before sending.\")",
        "hasStateDescription(\"Wait for the current response or cancel it.\")",
        "hasStateDescription(\"Ready to stop the current response.\")",
        'hasClickActionLabel("Attach files")',
        'hasClickActionLabel("Send message")',
        'hasClickActionLabel("Cancel generation")',
        'hasClickActionLabel("Remove attachment brief.pdf")',
        "hasContentDescription(expected.cancelAction) and\n"
        "                    hasStateDescription(expected.cancelState) and\n"
        "                    hasClickActionLabel(expected.cancelAction)",
        "hasClickActionLabel(expected.sendAction)",
        "hasClickActionLabel(expected.cancelAction)",
        "chatScreenComposerReadinessStatusAnnouncesAcrossSupportedLanguages",
        ".getString(R.string.chat_hint_select_model)",
        "onNodeWithContentDescription(expectedStatus, useUnmergedTree = true)",
        ".assert(hasPoliteLiveRegion())",
        "Remove attachment brief.pdf",
        "onAllNodesWithContentDescription(\"Send message\").assertCountEquals(0)",
        "HapticFeedbackType.LongPress",
        "hasContentDescription(\"Connection troubleshooting\") and",
        "hasStateDescription(\"Collapsed\") and",
        'hasClickActionLabel("Enable Connection troubleshooting")',
        'hasClickActionLabel("Disable Connection troubleshooting")',
        "SemanticsProperties.Role, Role.Button",
        "hasText(\"Manage all chats\") and\n"
        "                hasStateDescription(\"Collapsed\") and\n"
        "                hasClickActionLabel(\"Expand section\")",
        "hasText(\"Manage all chats\") and\n"
        "                hasStateDescription(\"Expanded\") and\n"
        "                hasClickActionLabel(\"Collapse section\")",
        "chatDrawerItemsLocalizeAccessibilitySummariesAcrossSupportedLanguages",
        "navigationDrawerChatSearchFiltersClearsAndUsesHapticFeedback",
        "navigationDrawerChatSearchLocalizesClearAndNoResultsAcrossSupportedLanguages",
        "Clear chat search for missing",
        'hasClickActionLabel("Clear chat search for missing")',
        "missing 검색어로 된 채팅 검색 지우기",
        "Effacer la recherche de chats pour missing",
        "채팅 Trip plan. 메시지 3개 - 확인 필요.",
        "Chat sélectionné « One note ». 1 message.",
        "settingsPreferenceRowsExposeSelectedStateToAccessibility",
        "Appearance: Dark",
        "화면 모드: 다크",
        "Language: 日本語",
        "언어: 한국어",
        "Pause memory Project Alpha prefers concise Korean summaries",
        "Enable memory Use metric units for travel planning",
        "Remove memory Project Alpha prefers concise Korean summaries",
        'hasClickActionLabel("Pause memory Project Alpha prefers concise Korean summaries")',
        'hasClickActionLabel("Enable memory Use metric units for travel planning")',
        'hasClickActionLabel("Remove memory Project Alpha prefers concise Korean summaries")',
        "settingsMemoryRowsCapLongActionAccessibilityLabels",
        "MEMORY_ACTION_LABEL_MAX_CHARS",
        "Pause memory $cappedMemory",
        "Remove memory $cappedMemory",
        "settingsMemoryAddControlsLocalizeReadinessStateAcrossSupportedLanguages",
        "hasContentDescription(memoryAddLabel) and hasSetTextAction() and hasStateDescription(emptyState)",
        "hasContentDescription(memoryAddLabel) and hasSetTextAction() and hasStateDescription(readyState)",
        "renameChatSessionDialogExposesTitleReadinessAndHaptics",
        "hasStateDescription(\"Enter a title before saving.\")",
        "hasStateDescription(\"Ready to save.\")",
        "hasSetTextAction()",
        'hasClickActionLabel("Expand section")',
        'hasClickActionLabel("Collapse section")',
        'hasClickActionLabel("Show troubleshooting")',
        'hasClickActionLabel("Hide troubleshooting")',
        "R.string.memory_add_state_enter_memory",
        "R.string.memory_add_state_ready",
        'compose.onNodeWithText("Cancel").performClick()',
        'hasContentDescription("Remove memory Project Alpha prefers concise Korean summaries") and',
        'hasClickActionLabel("Remove memory Project Alpha prefers concise Korean summaries")',
        'compose.onNodeWithText("Delete").performClick()',
        "assertEquals(1, removeClicks)",
        'hasClickActionLabel("Connect trusted route")',
        'hasClickActionLabel("Scan latest QR")',
        "performImeAction()",
    )
    for snippet in required_compose_test_snippets:
        if snippet not in compose_test_text:
            failures.append(f"{compose_test_relative}: Missing Android haptic Compose regression test {snippet}.")
    if "trustedRouteConnectLabelDiffersFromGenericConnectAcrossSupportedLanguages" not in compose_test_text:
        failures.append(
            f"{compose_test_relative}: Missing Android trusted-route connect label localization regression."
        )

    required_scanner_test_snippets = (
        "scannerChromeShowsPermissionStateWithoutCameraPreview",
        "scannerChromeShowsSettingsRecoveryWhenCameraPermissionIsBlocked",
        "scannerLocaleExpectations().forEachIndexed",
        "LocalizedScannerContent(languageTag = currentExpectation.value.languageTag)",
        "compose.onNodeWithText(expected.cancel).assertIsDisplayed()",
        "compose.onNodeWithText(expected.cancel).performClick()",
    )
    for snippet in required_scanner_test_snippets:
        if snippet not in scanner_test_text:
            failures.append(f"{scanner_test_relative}: Missing Android QR scanner regression test {snippet}.")

    required_string_snippets = (
        'name="attach_files_state_ready"',
        'name="attach_files_state_unavailable"',
        'name="cancel_generation_state_ready"',
        'name="chat_session_row_summary"',
        'name="chat_session_row_summary_selected"',
        'name="status_hero_accessibility_summary"',
        'name="rename_chat_named"',
        'name="delete_chat_named"',
        'name="chat_history_action_state_wait_for_stream"',
        'name="chat_backend_unavailable_summary"',
        'name="provider_status_row_summary"',
        'name="provider_status_row_summary_retryable"',
        'name="error_accessibility_summary"',
        'name="copy_code_block"',
        'name="copy_code_block_named"',
        'name="copy_code_block_numbered"',
        'name="discovered_runtime_unavailable_summary"',
        'name="clear_chat_search_named"',
        'name="preference_option_accessibility_summary"',
        'name="memory_add_state_enter_memory"',
        'name="memory_add_state_ready"',
        'name="rename_chat_title_state_empty"',
        'name="rename_chat_title_state_ready"',
        'name="scan_qr_state_ready"',
        'name="scan_qr_state_connecting"',
        'name="scan_latest_qr_state_ready"',
        'name="qr_pairing_detail"',
        "To connect from another network, the QR must include a relay, VPN, tunnel, or private-overlay route both devices can reach.",
        'name="route_notice_accessibility_summary_with_steps"',
        'name="route_notice_recovery_steps"',
        'name="attachment_only_prompt_header"',
        'name="new_chat_state_pairing_required"',
        'name="setting_action_enable_named"',
        'name="setting_action_disable_named"',
        'name="connect_runtime_state_ready"',
        'name="connect_runtime_state_connecting"',
        'name="connect_remote_route"',
        'name="refresh_health_state_ready"',
        'name="disconnect_runtime_state_ready"',
        'name="discover_runtimes_state_ready"',
        'name="discover_runtimes_state_running"',
        'name="stop_discovery_state_ready"',
        'name="stop_discovery_state_idle"',
        'name="clear_model_search_named"',
        'name="embedding_model_none_row_summary"',
        'name="embedding_model_none_row_summary_selected"',
        'name="embedding_model_row_summary"',
        'name="embedding_model_row_summary_selected"',
        'name="saved_embedding_model_row_summary"',
    )
    for snippet in required_string_snippets:
        if snippet not in strings_text:
            failures.append(f"{strings_relative}: Missing Android attachment action accessibility string {snippet}.")

    required_saved_embedding_locale_paths = (
        strings_path,
        ROOT / "apps/android/app/src/main/res/values-en/strings.xml",
        ROOT / "apps/android/app/src/main/res/values-ko/strings.xml",
        ROOT / "apps/android/app/src/main/res/values-ja/strings.xml",
        ROOT / "apps/android/app/src/main/res/values-zh-rCN/strings.xml",
        ROOT / "apps/android/app/src/main/res/values-fr/strings.xml",
    )
    for locale_strings_path in required_saved_embedding_locale_paths:
        locale_relative = locale_strings_path.relative_to(ROOT)
        if not locale_strings_path.exists():
            failures.append(f"{locale_relative}: Missing Android localized strings file for embedding row summaries.")
            continue
        locale_strings_text = locale_strings_path.read_text(encoding="utf-8")
        if 'name="saved_embedding_model_row_summary"' not in locale_strings_text:
            failures.append(
                f"{locale_relative}: Missing saved embedding model accessibility summary string."
            )

    required_scanner_test_snippets = (
        "PairingQrScannerChromeNoDeviceComposeTest",
        "scannerChromeShowsPermissionStateWithoutCameraPreview",
        "scannerChromeShowsSettingsRecoveryWhenCameraPermissionIsBlocked",
        "scannerChromeShowsCameraStateWithTorchAndCancelActions",
        "listOf(\"en\", \"ko\", \"ja\", \"zh-CN\", \"fr\")",
        "ScannerLocaleExpectation(",
        "R.string.qr_scanner_permission_blocked_detail",
        "R.string.qr_scanner_permission_settings_action",
        "R.string.qr_scanner_flashlight_state_on",
        "R.string.qr_scanner_flashlight_state_off",
        "cameraPermissionPermanentlyDenied = true",
        "expected.blockedPermissionTitle",
        "expected.settingsAction",
        "HapticFeedbackType.TextHandleMove, HapticFeedbackType.TextHandleMove",
        "hasStateDescription(expected.flashlightStateOff)",
        "hasStateDescription(expected.flashlightStateOn)",
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
    android_runtime_test_path = ROOT / "apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeClientViewModelTest.kt"
    android_prompt_resource_test_path = ROOT / (
        "apps/android/app/src/test/java/com/localagentbridge/android/runtime/RuntimeAttachmentPromptResourceTest.kt"
    )
    macos_extractor_path = ROOT / "apps/macos/DocumentIngestion/Sources/DocumentTextExtractor.swift"
    macos_test_path = ROOT / "apps/macos/DocumentIngestion/Tests/DocumentTextExtractorTests.swift"

    files = (
        android_picker_path,
        android_runtime_path,
        android_test_path,
        android_runtime_test_path,
        android_prompt_resource_test_path,
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
    android_runtime_test_text = android_runtime_test_path.read_text(encoding="utf-8")
    android_prompt_resource_test_text = android_prompt_resource_test_path.read_text(encoding="utf-8")
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

    required_attachment_prompt_snippets = (
        (
            "attachmentOnlyPromptHeader(",
            "Android attachment-only prompt header must be resolved through a testable resource helper.",
        ),
        (
            "R.string.attachment_only_prompt_header",
            "Android attachment-only prompt header must come from localized string resources.",
        ),
        (
            "context = getApplication(),",
            "Android attachment-only send path fallback must use the ViewModel application context for localized prompt headers.",
        ),
        (
            "attachmentPromptHeaderProvider = { languageTag ->",
            "Production Android dependencies must install the localized attachment-only prompt header provider.",
        ),
    )
    for snippet, guidance in required_attachment_prompt_snippets:
        if snippet not in android_runtime_text:
            failures.append(f"{android_runtime_path.relative_to(ROOT)}: {guidance}")

    required_attachment_prompt_unit_test_snippets = (
        "attachmentOnlyPromptUsesSelectedAppLanguageAndEnglishFallback",
        "첨부한 입력을 분석하세요:\\n- pairing-notes.txt",
        "attachmentPromptHeaderProvider = ::testAttachmentOnlyPromptHeader",
    )
    for snippet in required_attachment_prompt_unit_test_snippets:
        if snippet not in android_runtime_test_text:
            failures.append(
                f"{android_runtime_test_path.relative_to(ROOT)}: Missing attachment-only prompt resource regression {snippet}."
            )

    required_attachment_prompt_resource_test_snippets = (
        "RuntimeAttachmentPromptResourceTest",
        "attachmentOnlyPromptHeaderUsesLocalizedAndroidResources",
        "context.getString(R.string.attachment_only_prompt_header)",
        "attachmentOnlyPromptHeader(context, RuntimeAppLanguage.Korean.languageTag)",
    )
    for snippet in required_attachment_prompt_resource_test_snippets:
        if snippet not in android_prompt_resource_test_text:
            failures.append(
                f"{android_prompt_resource_test_path.relative_to(ROOT)}: Missing attachment-only prompt resource regression {snippet}."
            )

    required_picker_callback_snippets = (
        (
            "handlePickedAttachments(uris, viewModel::addAttachments)",
            "attachment picker callback must route selected URIs through the single-dispatch helper.",
        ),
        (
            "internal fun handlePickedAttachments(",
            "attachment picker callback must keep a testable single-dispatch helper.",
        ),
        (
            "if (uris.isNotEmpty()) {\n        addAttachments(uris)\n    }",
            "attachment picker callback helper must ignore empty selections and dispatch non-empty selections once.",
        ),
    )
    for snippet, guidance in required_picker_callback_snippets:
        if snippet not in android_picker_text:
            failures.append(f"{android_picker_path.relative_to(ROOT)}: {guidance}")

    if "attachmentPickerCallbackAddsPickedUrisOnceAndIgnoresEmptySelections" not in android_test_text:
        failures.append(
            f"{android_test_path.relative_to(ROOT)}: Missing attachment picker single-dispatch regression test."
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
        (
            "modelGroupHeaderAccessibilityLabel(title: group.title, count: group.countText)",
            "Status Models group headers must expose title plus count as one accessibility label.",
        ),
        (
            "func modelGroupHeaderAccessibilityLabel(title: String, count: String) -> String",
            "Status Models group header accessibility helper must stay testable.",
        ),
    )
    for snippet, guidance in required_status_snippets:
        if snippet not in status_text:
            failures.append(f"{status_relative}: {guidance}")

    required_test_snippets = (
        "testVisibleModelGroupsShowOnlyInstalledLocalModels",
        "testModelGroupHeaderAccessibilityLabelUsesSelectedLanguage",
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


def macos_relay_secret_store_guard_failures() -> list[str]:
    failures: list[str] = []
    model_path = ROOT / "apps/macos/CompanionCore/Sources/CompanionAppModel.swift"
    test_path = ROOT / "apps/macos/CompanionCore/Tests/LocalRuntimeMessageRouterTests.swift"

    if not model_path.exists() or not test_path.exists():
        failures.append("macOS relay secret-store guard files are missing.")
        return failures

    model_text = model_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    model_relative = model_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_model_snippets = (
        "public protocol CompanionRelaySecretStoring",
        "public final class KeychainCompanionRelaySecretStore",
        "private let relaySecretStore",
        "RelayDefaults.secretRef",
        "BootstrapRelayDefaults.allocationTokenRef",
        "loadSavedRelaySecret(",
        "loadSavedBootstrapAllocationToken(",
        "relaySecretStore.saveSecret",
        "defaults.removeObject(forKey: RelayDefaults.secret)",
        "defaults.removeObject(forKey: BootstrapRelayDefaults.allocationToken)",
        "SecItemAdd",
        "SecItemCopyMatching",
        "SecItemDelete",
    )
    for snippet in required_model_snippets:
        if snippet not in model_text:
            failures.append(
                f"{model_relative}: macOS relay/bootstrap secrets must stay behind the secret-store "
                f"boundary; missing {snippet}."
            )

    forbidden_model_patterns = (
        (
            r"defaults\.set\([^,\n]*relaySecret[^,\n]*,\s*forKey:\s*RelayDefaults\.secret\)",
            "must not write relay secrets directly to UserDefaults.",
        ),
        (
            r"defaults\.set\([^,\n]*allocationToken[^,\n]*,\s*forKey:\s*BootstrapRelayDefaults\.allocationToken\)",
            "must not write bootstrap allocation tokens directly to UserDefaults.",
        ),
    )
    for pattern, guidance in forbidden_model_patterns:
        if re.search(pattern, model_text):
            failures.append(f"{model_relative}: macOS relay secret-store boundary {guidance}")

    required_test_snippets = (
        "FakeCompanionRelaySecretStore",
        "assertStoredRelaySecret(",
        "assertNoStoredRelaySecret(",
        "assertStoredBootstrapAllocationToken(",
        "testCompanionAppModelPersistsRelaySettingsAndIncludesRelayInQRCodeAfterRelayReady",
        "testCompanionAppModelSavesBootstrapRelaySettingsAndAllocatesRoute",
        "testCompanionAppModelPersistsBootstrapAllocationLeaseForRestoredQRCode",
        "testCompanionAppModelRegeneratesBootstrapQRCodeWithExpiredSavedLease",
        "relaySecretStore: relaySecretStore",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(
                f"{test_relative}: Missing macOS relay secret-store regression coverage {snippet}."
            )

    forbidden_test_snippets = (
        'XCTAssertEqual(defaults.string(forKey: "aetherlink.relay.secret")',
        'XCTAssertEqual(defaults.string(forKey: "aetherlink.bootstrap_relay.allocation_token")',
    )
    for snippet in forbidden_test_snippets:
        if snippet in test_text:
            failures.append(
                f"{test_relative}: macOS relay secret-store tests must assert secret refs, not raw defaults."
            )

    return failures


def macos_pairing_qr_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    view_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/PairingView.swift"
    content_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift"
    status_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift"
    app_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/LocalAgentBridgeApp.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"

    if not all(path.exists() for path in (view_path, content_path, status_path, app_path, test_path)):
        failures.append("macOS Pairing QR accessibility guard files are missing.")
        return failures

    view_text = view_path.read_text(encoding="utf-8", errors="replace")
    content_text = content_path.read_text(encoding="utf-8", errors="replace")
    status_text = status_path.read_text(encoding="utf-8", errors="replace")
    app_text = app_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    view_relative = view_path.relative_to(ROOT)
    content_relative = content_path.relative_to(ROOT)
    status_relative = status_path.relative_to(ROOT)
    app_relative = app_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_view_snippets = (
        (
            ".accessibilityElement(children: .ignore)",
            "Pairing QR image must collapse the generated QR child image into one stable accessibility element.",
        ),
        (
            ".accessibilityAddTraits(.isImage)",
            "Pairing QR accessibility element must preserve image semantics after child elements are ignored.",
        ),
        (
            ".accessibilityLabel(Text(pairingQRCodeAccessibilityLabel()))",
            "Pairing QR image must use the testable localized accessibility label helper.",
        ),
        (
            ".accessibilityValue(Text(pairingQRCodeAccessibilityValue(isExpired: isExpired)))",
            "Pairing QR image must expose active vs expired state through accessibility value.",
        ),
        (
            ".accessibilityHint(Text(pairingQRCodeAccessibilityHint(remoteRouteExpiresAt: remoteRouteExpiresAt)))",
            "Pairing QR image must explain runtime verification, connection details, and route expiry when present.",
        ),
        (
            '.accessibilityLabel(Text(NSLocalizedString("Pairing QR time remaining"',
            "Pairing QR expiration progress must expose a stable accessibility label.",
        ),
        (
            ".accessibilityValue(Text(expirationText(at: date)))",
            "Pairing QR expiration progress must expose the countdown through accessibility value.",
        ),
        (
            "func pairingQRCodeAccessibilityLabel() -> String",
            "Pairing QR accessibility label must stay testable without rendering SwiftUI.",
        ),
        (
            "func pairingQRCodeAccessibilityValue(isExpired: Bool) -> String",
            "Pairing QR accessibility value must stay testable without rendering SwiftUI.",
        ),
        (
            "func pairingQRCodeAccessibilityHint(remoteRouteExpiresAt: Date? = nil) -> String",
            "Pairing QR accessibility hint must stay testable without rendering SwiftUI.",
        ),
        (
            "func pairingQRRemoteRouteExpirationText(_ date: Date) -> String",
            "Pairing QR remote-route expiry accessibility hint must stay testable without rendering SwiftUI.",
        ),
        (
            "func pairingQRExpirationText(expiresAt: Date, at date: Date) -> String",
            "Pairing QR expiration accessibility value must stay testable without rendering SwiftUI.",
        ),
        (
            "private struct PairingRouteNoticeLabel: View",
            "Pairing QR route notice accessibility must live in a reusable view shared by setup and active QR cards.",
        ),
        (
            ".accessibilityLabel(Text(pairingRouteNoticeAccessibilityLabel()))",
            "Pairing QR route notice label view must expose a stable accessibility label.",
        ),
        (
            ".accessibilityValue(Text(routeNotice.text))",
            "Pairing QR route notice label view must expose its current route status through accessibility value.",
        ),
        (
            "func pairingRouteNoticeAccessibilityLabel() -> String",
            "Pairing QR route notice accessibility label must stay testable without rendering SwiftUI.",
        ),
        (
            ".accessibilityValue(Text(pairingQRGenerationActionAccessibilityValue(isAvailable: canGeneratePairingQR)))",
            "Pairing QR generation action must expose ready/unavailable state through accessibility value.",
        ),
        (
            ".accessibilityHint(Text(pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR)))",
            "Pairing QR generation action must expose disabled reason through accessibility hint.",
        ),
        (
            ".help(activePairingQRRenewalActionAccessibilityHint())",
            "Active Pairing QR renewal button must expose the same localized action hint as hover help.",
        ),
        (
            ".accessibilityValue(Text(pairingQRGenerationActionAccessibilityValue(isAvailable: true)))",
            "Active Pairing QR renewal button must expose ready state through accessibility value.",
        ),
        (
            ".accessibilityHint(Text(activePairingQRRenewalActionAccessibilityHint()))",
            "Active Pairing QR renewal button must expose its localized action hint to accessibility.",
        ),
    )
    for snippet, guidance in required_view_snippets:
        if snippet not in view_text:
            failures.append(f"{view_relative}: {guidance}")
    if view_text.count("PairingRouteNoticeLabel(routeNotice: routeNotice)") < 2:
        failures.append(
            f"{view_relative}: Pairing QR setup and active QR card must both use PairingRouteNoticeLabel."
        )

    required_content_snippets = (
        "func pairingQRGenerationActionAccessibilityValue(",
        "func pairingQRGenerationActionAccessibilityHint(",
        "func activePairingQRRenewalActionAccessibilityHint() -> String",
        ".accessibilityValue(Text(pairingQRGenerationActionAccessibilityValue(isAvailable: canGeneratePairingQR)))",
        ".accessibilityHint(Text(pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR)))",
    )
    for snippet in required_content_snippets:
        if snippet not in content_text:
            failures.append(f"{content_relative}: Missing Pairing QR generation action accessibility contract {snippet}.")

    required_status_snippets = (
        "let pairingQRActionHint = pairingQRGenerationActionAccessibilityHint(",
        "hasAction: onGenerateRelayQRCode != nil",
        ".accessibilityHint(Text(pairingQRActionHint))",
    )
    for snippet in required_status_snippets:
        if snippet not in status_text:
            failures.append(f"{status_relative}: Missing Pairing QR quick-action accessibility contract {snippet}.")

    required_app_snippets = (
        ".help(pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR))",
        ".accessibilityValue(Text(pairingQRGenerationActionAccessibilityValue(isAvailable: canGeneratePairingQR)))",
        ".accessibilityHint(Text(pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR)))",
    )
    for snippet in required_app_snippets:
        if snippet not in app_text:
            failures.append(f"{app_relative}: Missing Pairing QR menu-bar accessibility contract {snippet}.")

    required_test_snippets = (
        "testToolbarAndMenuPairingQRGenerationUsesSharedAvailabilityContract",
        "testPairingQRGenerationActionAccessibilityUsesSelectedLanguage",
        "testPairingRouteNoticeAccessibilityUsesSelectedLanguage",
        "Pairing QR status",
        "페어링 QR 상태",
        "ペアリング QR の状態",
        "配对 QR 状态",
        "État du QR de jumelage",
        "activePairingQRRenewalActionAccessibilityHint()",
        "Generate New QR",
        "새 QR 생성",
        "新しい QR を生成",
        "生成新二维码",
        "Générer un nouveau QR",
        "pairingQRGenerationCommandAvailable(",
        "testCompanionDateFormattingUsesSelectedAppLanguage",
        "localizedCompanionDateString(from:",
        "testCompanionByteCountFormattingUsesSelectedAppLanguage",
        "localizedCompanionByteCountString(fromByteCount:",
        "testPairingQRCodeAccessibilityCopyUsesSelectedLanguageAndState",
        "pairingQRCodeAccessibilityLabel()",
        "Pairing QR code",
        "페어링 QR 코드",
        "ペアリング QR コード",
        "配对 QR 码",
        "QR code de jumelage",
        "testPairingQRExpirationProgressAccessibilityUsesSelectedLanguage",
        "Pairing QR time remaining",
        "페어링 QR 남은 시간",
        "Temps restant du QR de jumelage",
        "pairingQRExpirationText(expiresAt: activeExpiration, at: now)",
        "Scan this QR from AetherLink.",
        "Pairing QR expired. Generate a new QR.",
        "This QR verifies AetherLink Runtime and includes connection details for pairing or refresh.",
        "Pairing QR generation is unavailable from this view.",
        "Pairing from another network needs a relay, VPN, tunnel, or private-overlay route inside the pairing QR.",
        "다른 네트워크에서 페어링하려면 페어링 QR 안에 릴레이, VPN, 터널 또는 프라이빗 오버레이 경로가 필요합니다.",
        "別ネットワークからペアリングするには、ペアリング QR 内にリレー、VPN、トンネル、またはプライベートオーバーレイ経路が必要です。",
        "从另一个网络配对时，配对二维码内需要包含中继、VPN、隧道或私有覆盖网络路径。",
        "Le jumelage depuis un autre réseau nécessite une route relais, VPN, tunnel ou overlay privé dans le QR de jumelage.",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS Pairing QR accessibility regression {snippet}.")

    return failures


def macos_quick_action_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    chrome_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/CompanionChrome.swift"
    status_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift"
    content_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift"
    app_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/LocalAgentBridgeApp.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"

    paths = (chrome_path, status_path, content_path, app_path, test_path)
    if any(not path.exists() for path in paths):
        failures.append("macOS quick action accessibility guard files are missing.")
        return failures

    chrome_text = chrome_path.read_text(encoding="utf-8", errors="replace")
    status_text = status_path.read_text(encoding="utf-8", errors="replace")
    content_text = content_path.read_text(encoding="utf-8", errors="replace")
    app_text = app_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")

    required_chrome_snippets = (
        "func modelProviderCheckActionAccessibilityValue() -> String",
        "func modelProviderCheckActionAccessibilityHint() -> String",
        "func modelListLoadActionAccessibilityValue() -> String",
        "func modelListLoadActionAccessibilityHint() -> String",
        "func pairingQRGenerationCommandTitle(hasActiveSession: Bool) -> String",
        "enum CompanionPrimaryAction: String, CaseIterable, Identifiable",
        "func companionPrimaryActionOrder(trustedDeviceCount: Int) -> [CompanionPrimaryAction]",
        "return [.pairingQR, .refreshProviders, .loadModels]",
        "return [.refreshProviders, .loadModels, .pairingQR]",
        "Check model provider availability through AetherLink Runtime.",
        "Load the installed local model list through AetherLink Runtime.",
    )
    for snippet in required_chrome_snippets:
        if snippet not in chrome_text:
            failures.append(
                f"{chrome_path.relative_to(ROOT)}: Missing macOS quick action accessibility helper {snippet}."
            )

    required_action_snippets = (
        ".help(modelProviderCheckActionAccessibilityHint())",
        ".accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))",
        ".accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))",
        ".help(modelListLoadActionAccessibilityHint())",
        ".accessibilityValue(Text(modelListLoadActionAccessibilityValue()))",
        ".accessibilityHint(Text(modelListLoadActionAccessibilityHint()))",
    )
    for path, text in ((status_path, status_text), (content_path, content_text)):
        for snippet in required_action_snippets:
            if snippet not in text:
                failures.append(
                    f"{path.relative_to(ROOT)}: Missing macOS quick action accessibility wiring {snippet}."
                )

    for snippet in (
        "ForEach(companionPrimaryActionOrder(trustedDeviceCount: model.trustedDevices.count))",
        "menuBarPrimaryAction(action, commandTitles: commandTitles)",
        "case .refreshProviders:",
        "case .loadModels:",
        "case .pairingQR:",
        "Button(pairingQRGenerationCommandTitle(hasActiveSession: model.pairingSession != nil))",
    ):
        if snippet not in app_text:
            failures.append(
                f"{app_path.relative_to(ROOT)}: Missing macOS command/menu quick action hint {snippet}."
            )

    required_test_snippets = (
        "testQuickActionAccessibilityUsesSelectedLanguage",
        "testMenuBarPairingQRCommandTitleTracksActiveSessionAndLanguage",
        "testPrimaryActionsPrioritizePairingQRWhenNoTrustedDevicesExist",
        "companionPrimaryActionOrder(trustedDeviceCount: 0)",
        "modelProviderCheckActionAccessibilityValue()",
        "modelProviderCheckActionAccessibilityHint()",
        "modelListLoadActionAccessibilityValue()",
        "modelListLoadActionAccessibilityHint()",
        "pairingQRGenerationCommandTitle(hasActiveSession: true)",
        "AetherLink Runtime을 통해 모델 제공자 사용 가능 여부를 확인합니다.",
        "AetherLink Runtime 経由でインストール済みローカルモデルの一覧を読み込みます。",
        "通过 AetherLink Runtime 检查模型提供方可用性。",
        "Charge la liste des modèles locaux installés via AetherLink Runtime.",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_path.relative_to(ROOT)}: Missing macOS quick action accessibility test {snippet}.")

    return failures


def macos_sidebar_brand_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    view_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"

    if not view_path.exists() or not test_path.exists():
        failures.append("macOS sidebar brand accessibility guard files are missing.")
        return failures

    view_text = view_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    view_relative = view_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_view_snippets = (
        (
            ".accessibilityHidden(true)",
            "Sidebar brand icon must be hidden from assistive tech as decorative chrome.",
        ),
        (
            ".accessibilityElement(children: .ignore)",
            "Sidebar brand header must read as one stable runtime label.",
        ),
        (
            ".accessibilityLabel(Text(sidebarBrandAccessibilityLabel()))",
            "Sidebar brand header must use the testable localized accessibility helper.",
        ),
        (
            "func sidebarBrandAccessibilityLabel() -> String",
            "Sidebar brand accessibility label must stay testable without rendering SwiftUI.",
        ),
    )
    for snippet, guidance in required_view_snippets:
        if snippet not in view_text:
            failures.append(f"{view_relative}: {guidance}")

    required_test_snippets = (
        "testSidebarBrandAccessibilityLabelUsesSelectedLanguage",
        "AetherLink 런타임",
        "AetherLink ランタイム",
        "AetherLink 运行时",
        "Runtime AetherLink",
        "sidebarBrandAccessibilityLabel()",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS sidebar brand accessibility regression {snippet}.")

    return failures


def macos_page_header_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    view_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/CompanionChrome.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"
    strings_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/Resources/en.lproj/Localizable.strings"

    if not view_path.exists() or not test_path.exists() or not strings_path.exists():
        failures.append("macOS page header accessibility guard files are missing.")
        return failures

    view_text = view_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    strings_text = strings_path.read_text(encoding="utf-8", errors="replace")
    view_relative = view_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)
    strings_relative = strings_path.relative_to(ROOT)

    required_view_snippets = (
        (
            ".accessibilityElement(children: .ignore)",
            "Companion page headers must group decorative icon, title, and subtitle into one accessibility element.",
        ),
        (
            ".accessibilityLabel(Text(companionPageHeaderAccessibilityLabel(title: title, subtitle: subtitle)))",
            "Companion page headers must use the localized helper for their accessibility label.",
        ),
        (
            "func companionPageHeaderAccessibilityLabel(title: String, subtitle: String) -> String",
            "Companion page header accessibility label must stay testable without rendering SwiftUI.",
        ),
        (
            "NSLocalizedString(\"%@. %@\"",
            "Companion page header title/subtitle separator must stay localized.",
        ),
    )
    for snippet, guidance in required_view_snippets:
        if snippet not in view_text:
            failures.append(f"{view_relative}: {guidance}")

    required_test_snippets = (
        "testCompanionPageHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks",
        "companionPageHeaderAccessibilityLabel(",
        "AetherLink ランタイム。信頼済みデバイスを AetherLink Runtime 経由でローカルモデルに接続します。",
        "AetherLink 运行时。通过 AetherLink Runtime 将受信任设备连接到本地模型。",
        "Runtime AetherLink. Relie les appareils approuvés aux modèles locaux via AetherLink Runtime.",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS page header accessibility regression {snippet}.")

    if '"%@. %@"' not in strings_text:
        failures.append(f"{strings_relative}: Missing macOS page header accessibility separator localization.")

    return failures


def macos_empty_state_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    chrome_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/CompanionChrome.swift"
    status_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/StatusView.swift"
    pairing_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/PairingView.swift"
    trusted_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/TrustedDevicesView.swift"
    logs_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/LogsView.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"

    paths = (chrome_path, status_path, pairing_path, trusted_path, logs_path, test_path)
    if any(not path.exists() for path in paths):
        failures.append("macOS empty state accessibility guard files are missing.")
        return failures

    chrome_text = chrome_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    required_chrome_snippets = (
        "func companionEmptyStateAccessibilityLabel(title: String, description: String) -> String",
        "companionPageHeaderAccessibilityLabel(title: title, subtitle: description)",
    )
    for snippet in required_chrome_snippets:
        if snippet not in chrome_text:
            failures.append(
                f"{chrome_path.relative_to(ROOT)}: Missing macOS empty-state accessibility helper {snippet}."
            )

    required_screen_snippets = (
        (status_path, "emptyModelsTitle", "emptyModelsDescription"),
        (pairing_path, "emptyPairingTitle", "emptyPairingDescription"),
        (trusted_path, "emptyTrustedDevicesTitle", "emptyTrustedDevicesDescription"),
        (logs_path, "emptyActivityTitle", "emptyActivityDescription"),
    )
    for path, title_snippet, description_snippet in required_screen_snippets:
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        for snippet in (
            title_snippet,
            description_snippet,
            "companionEmptyStateAccessibilityLabel(",
            ".accessibilityElement(children: .ignore)",
        ):
            if snippet not in text:
                failures.append(f"{relative}: Missing macOS empty-state accessibility wiring {snippet}.")

    required_test_snippets = (
        "testCompanionEmptyStateAccessibilityLabelUsesSelectedLanguageAndFallbacks",
        "companionEmptyStateAccessibilityLabel(",
        "불러온 모델 없음. AetherLink Runtime에서 사용할 수 있는 모델을 불러오세요.",
        "読み込まれたモデルはありません。AetherLink Runtime で利用できるモデルを読み込みます。",
        "尚未加载模型。加载 AetherLink Runtime 可用的模型。",
        "Aucun modèle chargé. Chargez les modèles disponibles via AetherLink Runtime.",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_path.relative_to(ROOT)}: Missing macOS empty-state accessibility regression {snippet}.")

    return failures


def macos_sidebar_preference_accessibility_guard_failures() -> list[str]:
    failures: list[str] = []
    view_path = ROOT / "apps/macos/LocalAgentBridgeApp/Sources/ContentView.swift"
    test_path = ROOT / "apps/macos/LocalAgentBridgeApp/Tests/AetherLinkLocalizationTests.swift"

    if not view_path.exists() or not test_path.exists():
        failures.append("macOS sidebar preference accessibility guard files are missing.")
        return failures

    view_text = view_path.read_text(encoding="utf-8", errors="replace")
    test_text = test_path.read_text(encoding="utf-8", errors="replace")
    view_relative = view_path.relative_to(ROOT)
    test_relative = test_path.relative_to(ROOT)

    required_view_snippets = (
        (
            ".accessibilityValue(Text(AetherLinkAppAppearance.normalized(appearance).title))",
            "Appearance picker must expose the current selected appearance as its accessibility value.",
        ),
        (
            ".accessibilityValue(Text(AetherLinkAppLanguage.normalized(languageTag).title))",
            "Language picker must expose the current selected language as its accessibility value.",
        ),
    )
    for snippet, guidance in required_view_snippets:
        if snippet not in view_text:
            failures.append(f"{view_relative}: {guidance}")

    required_test_snippets = (
        "testSidebarPreferencePickerAccessibilityValuesUseSelectedLanguage",
        '("ko", "다크", "한국어")',
        '("ja", "ダーク", "日本語")',
        '("zh-Hans", "深色", "简体中文")',
        '("fr", "Sombre", "Français")',
        'AetherLinkAppAppearance.normalized("dark").title',
        "AetherLinkAppLanguage.normalized(expectation.languageTag).title",
    )
    for snippet in required_test_snippets:
        if snippet not in test_text:
            failures.append(f"{test_relative}: Missing macOS sidebar preference accessibility regression {snippet}.")

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
            "Android first-run language picker before pairing",
            "Default no-device gate coverage summary must mention Android first-run language picker before pairing.",
        ),
        (
            "Android translated Memory noun",
            "Default no-device gate coverage summary must mention Android translated Memory noun coverage.",
        ),
        (
            "Android OS app-language handoff",
            "Default no-device gate coverage summary must mention Android OS app-language handoff coverage.",
        ),
        (
            "RuntimeClientViewModelTest.viewModelReconcilesSystemAppLanguageUntilInAppLanguageIsSelected",
            "Default no-device gate must run the Android OS app-language handoff regression.",
        ),
        (
            "RuntimeClientViewModelTest.systemAppLanguageHelperDoesNotOverrideInAppLanguageSelection",
            "Default no-device gate must run the app-language source persistence regression.",
        ),
        (
            "RuntimeAttachmentPromptResourceTest.attachmentOnlyPromptHeaderUsesLocalizedAndroidResources",
            "Default no-device gate must run the Android attachment-only prompt resource regression.",
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
            "Android QR scanner permission/settings/torch/cancel chrome",
            "Default no-device gate coverage summary must mention Android QR scanner settings recovery coverage.",
        ),
        (
            "Android QR scanner five-language chrome accessibility",
            "Default no-device gate coverage summary must mention Android QR scanner five-language chrome accessibility.",
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
            "Android chat top-bar model search interaction",
            "Default no-device gate coverage summary must mention Android chat top-bar model search interaction coverage.",
        ),
        (
            "Android search clear action labels",
            "Default no-device gate coverage summary must mention Android search clear action labels.",
        ),
        (
            "Android chat top-bar model row accessibility summaries",
            "Default no-device gate coverage summary must mention Android chat top-bar model row accessibility summaries.",
        ),
        (
            "Android chat top-bar model row action labels",
            "Default no-device gate coverage summary must mention Android chat top-bar model row action labels.",
        ),
        (
            "Android drawer chat options contextual accessibility",
            "Default no-device gate coverage summary must mention drawer chat options contextual accessibility.",
        ),
        (
            "Android drawer chat menu contextual action labels",
            "Default no-device gate coverage summary must mention drawer chat menu contextual action labels.",
        ),
        (
            "Android drawer chat row accessibility summaries",
            "Default no-device gate coverage summary must mention drawer chat row accessibility summaries.",
        ),
        (
            "Android drawer chat search interaction",
            "Default no-device gate coverage summary must mention drawer chat search interaction coverage.",
        ),
        (
            "Settings chat history search interaction",
            "Default no-device gate coverage summary must mention Settings chat-history search interaction coverage.",
        ),
        (
            "Android QR-first chat empty state",
            "Default no-device gate coverage summary must mention Android QR-first chat empty-state coverage.",
        ),
        (
            "Android Settings QR scan disabled reason",
            "Default no-device gate coverage summary must mention Android Settings QR scan disabled reason.",
        ),
        (
            "Android diagnostic QR text state accessibility",
            "Default no-device gate coverage summary must mention Android diagnostic QR text state accessibility.",
        ),
        (
            "Android diagnostic QR text contextual action labels",
            "Default no-device gate coverage summary must mention Android diagnostic QR text contextual action labels.",
        ),
        (
            "Android connect action disabled reason",
            "Default no-device gate coverage summary must mention Android connect action disabled reason.",
        ),
        (
            "Android trusted-route connect label",
            "Default no-device gate coverage summary must mention Android trusted-route connect label coverage.",
        ),
        (
            "Android manual diagnostic host QR-first guard",
            "Default no-device gate coverage summary must mention Android manual diagnostic host QR-first guard coverage.",
        ),
        (
            "Android model refresh action accessibility state",
            "Default no-device gate coverage summary must mention Android model refresh action accessibility state.",
        ),
        (
            "Android New Chat disabled reason",
            "Default no-device gate coverage summary must mention Android New Chat disabled reason.",
        ),
        (
            "Android New Chat pairing-required disabled reason",
            "Default no-device gate coverage summary must mention Android New Chat pairing-required disabled reason.",
        ),
        (
            "Android New Chat action labels",
            "Default no-device gate coverage summary must mention Android New Chat action labels.",
        ),
        (
            "Android permanent rail New Chat pairing gate",
            "Default no-device gate coverage summary must mention Android permanent rail New Chat pairing gate coverage.",
        ),
        (
            "Android permanent rail Chat pairing gate",
            "Default no-device gate coverage summary must mention Android permanent rail Chat pairing gate coverage.",
        ),
        (
            "Android chat empty route guidance full-wrap layout",
            "Default no-device gate coverage summary must mention Android chat empty route guidance full-wrap layout.",
        ),
        (
            "Android route-recovery empty-state live-region accessibility",
            "Default no-device gate coverage summary must mention Android route-recovery empty-state live-region accessibility.",
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
            "Android composer latest QR readiness hint",
            "Default no-device gate coverage summary must mention Android composer latest QR readiness hint coverage.",
        ),
        (
            "Android composer input readiness accessibility state",
            "Default no-device gate coverage summary must mention Android composer input readiness accessibility state.",
        ),
        (
            "Android composer readiness live-region accessibility",
            "Default no-device gate coverage summary must mention Android composer readiness live-region accessibility.",
        ),
        (
            "Android memory input readiness accessibility state",
            "Default no-device gate coverage summary must mention Android memory input readiness accessibility state.",
        ),
        (
            "Android send button readiness accessibility state",
            "Default no-device gate coverage summary must mention Android send button readiness accessibility state.",
        ),
        (
            "Android composer primary action click labels",
            "Default no-device gate coverage summary must mention Android composer primary action click labels.",
        ),
        (
            "Android composer attach action accessibility state",
            "Default no-device gate coverage summary must mention Android composer attach action accessibility coverage.",
        ),
        (
            "Android attachment-only prompt resource localization",
            "Default no-device gate coverage summary must mention Android attachment-only prompt resource localization coverage.",
        ),
        (
            "Android attachment picker single-dispatch guard",
            "Default no-device gate coverage summary must mention Android attachment picker single-dispatch coverage.",
        ),
        (
            "Android connected action accessibility states",
            "Default no-device gate coverage summary must mention Android connected action accessibility states.",
        ),
        (
            "Android streaming cancel Compose action",
            "Default no-device gate coverage summary must mention Android streaming cancel Compose action coverage.",
        ),
        (
            "Android streaming cancel accessibility state",
            "Default no-device gate coverage summary must mention Android streaming cancel accessibility state coverage.",
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
            "Android message copy accessibility labels",
            "Default no-device gate coverage summary must mention Android message copy accessibility labels.",
        ),
        (
            "Android copy success live-region accessibility",
            "Default no-device gate coverage summary must mention Android copy success live-region accessibility.",
        ),
        (
            "Android QR pairing live-region accessibility",
            "Default no-device gate coverage summary must mention Android QR pairing live-region accessibility.",
        ),
        (
            "Android code block copy accessibility labels",
            "Default no-device gate coverage summary must mention Android code block copy accessibility labels.",
        ),
        (
            "Android multi-code-block copy action labels",
            "Default no-device gate coverage summary must mention Android multi-code-block copy action labels.",
        ),
        (
            "Android backend readiness banner accessibility summary",
            "Default no-device gate coverage summary must mention Android backend readiness banner accessibility summary.",
        ),
        (
            "Android backend readiness refresh accessibility state",
            "Default no-device gate coverage summary must mention Android backend readiness refresh accessibility state.",
        ),
        (
            "Android generic error banner accessibility summary",
            "Default no-device gate coverage summary must mention Android generic error banner accessibility summary.",
        ),
        (
            "Android route notice action accessibility labels",
            "Default no-device gate coverage summary must mention Android route notice action accessibility labels.",
        ),
        (
            "Android route notice accessibility summaries",
            "Default no-device gate coverage summary must mention Android route notice accessibility summary coverage.",
        ),
        (
            "Android route notice accessibility state",
            "Default no-device gate coverage summary must mention Android route notice accessibility state coverage.",
        ),
        (
            "Android route notice QR recovery steps",
            "Default no-device gate coverage summary must mention Android route notice QR recovery steps.",
        ),
        (
            "Android primary pairing cross-network route copy",
            "Default no-device gate coverage summary must mention Android primary pairing cross-network route copy.",
        ),
        (
            "Android relay auth failure QR recovery notice",
            "Default no-device gate coverage summary must mention Android relay auth failure QR recovery notice coverage.",
        ),
        (
            "Android relay auth failure auto-retry stop",
            "Default no-device gate coverage summary must mention Android relay auth failure auto-retry stop coverage.",
        ),
        (
            "Android relay auth failure post-clear QR action",
            "Default no-device gate coverage summary must mention Android relay auth failure post-clear QR action coverage.",
        ),
        (
            "Android relay auth failure empty-chat copy",
            "Default no-device gate coverage summary must mention Android relay auth failure empty-chat copy coverage.",
        ),
        (
            "Android route rejection empty-chat copy",
            "Default no-device gate coverage summary must mention Android route rejection empty-chat copy coverage.",
        ),
        (
            "Android expired route empty-chat copy",
            "Default no-device gate coverage summary must mention Android expired route empty-chat copy coverage.",
        ),
        (
            "Android expired remote-route QR recovery action",
            "Default no-device gate coverage summary must mention Android expired remote-route QR recovery action coverage.",
        ),
        (
            "Android expired remote-route QR recovery localization",
            "Default no-device gate coverage summary must mention Android expired remote-route QR recovery localization coverage.",
        ),
        (
            "Android expired relay route purge",
            "Default no-device gate coverage summary must mention Android expired relay route purge coverage.",
        ),
        (
            "Android relay secret store boundary",
            "Default no-device gate coverage summary must mention Android relay secret store boundary coverage.",
        ),
        (
            "macOS relay secret store boundary",
            "Default no-device gate coverage summary must mention macOS relay secret store boundary coverage.",
        ),
        (
            "Android route.refresh terminal expiry state guard",
            "Default no-device gate coverage summary must mention Android route.refresh terminal expiry state guard coverage.",
        ),
        (
            "Android provider diagnostics expanded state",
            "Default no-device gate coverage summary must mention Android provider diagnostics expanded-state coverage.",
        ),
        (
            "Android provider diagnostics named accessibility labels",
            "Default no-device gate coverage summary must mention Android provider diagnostics named accessibility labels.",
        ),
        (
            "Android provider row accessibility summaries",
            "Default no-device gate coverage summary must mention Android provider row accessibility summaries.",
        ),
        (
            "Android attachment remove disabled reason",
            "Default no-device gate coverage summary must mention Android attachment remove disabled-reason coverage.",
        ),
        (
            "Android suggested-question accessibility labels",
            "Default no-device gate coverage summary must mention Android suggested-question accessibility labels.",
        ),
        (
            "Android suggested-question action accessibility labels",
            "Default no-device gate coverage summary must mention Android suggested-question action accessibility labels.",
        ),
        (
            "Android generating suggestions live-region accessibility",
            "Default no-device gate coverage summary must mention Android generating suggestions live-region accessibility.",
        ),
        (
            "Android reasoning accessibility summary",
            "Default no-device gate coverage summary must mention Android reasoning accessibility summary.",
        ),
        (
            "Android streaming assistant live-region accessibility",
            "Default no-device gate coverage summary must mention Android streaming assistant live-region accessibility.",
        ),
        (
            "Android jump-to-latest Compose interaction",
            "Default no-device gate coverage summary must mention Android jump-to-latest Compose interaction coverage.",
        ),
        (
            "Android jump-to-latest accessibility state",
            "Default no-device gate coverage summary must mention Android jump-to-latest accessibility state coverage.",
        ),
        (
            "Settings expandable section accessibility state",
            "Default no-device gate coverage summary must mention Settings expandable section accessibility coverage.",
        ),
        (
            "Settings expandable section action accessibility labels",
            "Default no-device gate coverage summary must mention Settings expandable section action accessibility labels.",
        ),
        (
            "Settings switch action accessibility labels",
            "Default no-device gate coverage summary must mention Settings switch action accessibility labels.",
        ),
        (
            "Settings expandable section duplicate icon semantics guard",
            "Default no-device gate coverage summary must mention Settings expandable section duplicate icon semantics guard.",
        ),
        (
            "Settings preference option accessibility summaries",
            "Default no-device gate coverage summary must mention Settings preference option accessibility summaries.",
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
            "Settings discovered route unavailable accessibility summaries",
            "Default no-device gate coverage summary must mention Settings discovered route unavailable accessibility summaries.",
        ),
        (
            "Settings discovery action accessibility states",
            "Default no-device gate coverage summary must mention Settings discovery action accessibility states.",
        ),
        (
            "Android embedding model row accessibility summaries",
            "Default no-device gate coverage summary must mention Android embedding model row accessibility summaries.",
        ),
        (
            "Settings memory contextual action accessibility",
            "Default no-device gate coverage summary must mention Settings memory contextual action accessibility.",
        ),
        (
            "Settings memory capped action accessibility labels",
            "Default no-device gate coverage summary must mention Settings memory capped action accessibility labels.",
        ),
        (
            "Settings memory add readiness accessibility state",
            "Default no-device gate coverage summary must mention Settings memory add readiness accessibility state.",
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
            "chat history destructive confirmation action labels",
            "Default no-device gate coverage summary must mention chat-history destructive confirmation action labels.",
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
            "macOS app-language region tag normalization",
            "Default no-device gate coverage summary must mention macOS app-language region tag normalization coverage.",
        ),
        (
            "macOS connection recovery form field accessibility",
            "Default no-device gate coverage summary must mention macOS connection recovery form field accessibility coverage.",
        ),
        (
            "macOS connection recovery QR action accessibility reason",
            "Default no-device gate coverage summary must mention macOS connection recovery QR action accessibility reason.",
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
            "Android trusted-runtime forget named accessibility label",
            "Default no-device gate coverage summary must mention trusted-runtime forget named accessibility label coverage.",
        ),
        (
            "chat history per-chat contextual action accessibility",
            "Default no-device gate coverage summary must mention chat-history contextual action accessibility.",
        ),
        (
            "chat history per-chat disabled accessibility state",
            "Default no-device gate coverage summary must mention chat-history per-chat disabled accessibility state.",
        ),
        (
            "chat history row accessibility summaries",
            "Default no-device gate coverage summary must mention chat-history row accessibility summaries.",
        ),
        (
            "Android rename chat readiness accessibility state",
            "Default no-device gate coverage summary must mention Android rename-chat readiness accessibility state.",
        ),
        (
            "chat history bulk expander accessibility state",
            "Default no-device gate coverage summary must mention chat-history bulk expander accessibility state.",
        ),
        (
            "chat history bulk action disabled accessibility state",
            "Default no-device gate coverage summary must mention chat-history bulk action disabled accessibility state.",
        ),
        (
            "Android platform-neutral connect guidance copy",
            "Default no-device gate coverage summary must mention Android platform-neutral connect guidance copy.",
        ),
        (
            "Android connection status hero accessibility summary",
            "Default no-device gate coverage summary must mention Android connection-status hero accessibility summary.",
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
            "macOS Pairing QR image accessibility element",
            "Default no-device gate coverage summary must mention macOS Pairing QR image accessibility element.",
        ),
        (
            "macOS Pairing QR time remaining accessibility value",
            "Default no-device gate coverage summary must mention macOS Pairing QR time remaining accessibility value.",
        ),
        (
            "macOS Pairing QR route notice accessibility status",
            "Default no-device gate coverage summary must mention macOS Pairing QR route notice accessibility status.",
        ),
        (
            "macOS Pairing QR remote-route expiry accessibility hint",
            "Default no-device gate coverage summary must mention macOS Pairing QR remote-route expiry accessibility hint.",
        ),
        (
            "macOS Pairing QR generation action accessibility reason",
            "Default no-device gate coverage summary must mention macOS Pairing QR generation action accessibility reason.",
        ),
        (
            "macOS active Pairing QR renewal accessibility hint",
            "Default no-device gate coverage summary must mention macOS active Pairing QR renewal accessibility hint.",
        ),
        (
            "macOS sidebar brand accessibility label",
            "Default no-device gate coverage summary must mention macOS sidebar brand accessibility label.",
        ),
        (
            "macOS page header accessibility labels",
            "Default no-device gate coverage summary must mention macOS page header accessibility labels.",
        ),
        (
            "macOS CJK page-header accessibility spacing",
            "Default no-device gate coverage summary must mention macOS CJK page-header accessibility spacing.",
        ),
        (
            "macOS empty-state accessibility labels",
            "Default no-device gate coverage summary must mention macOS empty-state accessibility labels.",
        ),
        (
            "macOS sidebar preference picker accessibility values",
            "Default no-device gate coverage summary must mention macOS sidebar preference picker accessibility values.",
        ),
        (
            "macOS nearby-only connection guidance copy",
            "Default no-device gate coverage summary must mention macOS nearby-only connection guidance copy.",
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
            "macOS trusted-device row accessibility visual-summary separation",
            "Default no-device gate coverage summary must mention macOS trusted-device row accessibility visual-summary separation.",
        ),
        (
            "macOS trusted-device removal confirmation localization",
            "Default no-device gate coverage summary must mention macOS trusted-device removal confirmation localization.",
        ),
        (
            "macOS trusted-device confirm-remove action accessibility labels",
            "Default no-device gate coverage summary must mention macOS trusted-device confirm-remove action accessibility labels.",
        ),
        (
            "macOS trusted-device refresh accessibility hint",
            "Default no-device gate coverage summary must mention macOS trusted-device refresh accessibility hint.",
        ),
        (
            "macOS Activity trusted-device audit copy",
            "Default no-device gate coverage summary must mention macOS Activity trusted-device audit copy.",
        ),
        (
            "macOS Activity row tone accessibility labels",
            "Default no-device gate coverage summary must mention macOS Activity row tone accessibility labels.",
        ),
        (
            "macOS Activity technical-details accessibility state",
            "Default no-device gate coverage summary must mention macOS Activity technical-details accessibility state.",
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
            "macOS model group header accessibility labels",
            "Default no-device gate coverage summary must mention macOS model group header accessibility labels.",
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
            "macOS menu-bar status and command localization",
            "Default no-device gate coverage summary must mention macOS menu-bar status and command localization.",
        ),
        (
            "macOS quick action accessibility hints",
            "Default no-device gate coverage summary must mention macOS quick action accessibility hints.",
        ),
        (
            "macOS menu-bar quick action accessibility parity",
            "Default no-device gate coverage summary must mention macOS menu-bar quick action accessibility parity.",
        ),
        (
            "macOS first-run Pairing QR primary action ordering",
            "Default no-device gate coverage summary must mention macOS first-run Pairing QR primary action ordering.",
        ),
        (
            "macOS Connection Recovery private-overlay toggle accessibility labels",
            "Default no-device gate coverage summary must mention macOS Connection Recovery private-overlay toggle accessibility labels.",
        ),
        (
            "macOS Connection Recovery fallback-action accessibility hints",
            "Default no-device gate coverage summary must mention macOS Connection Recovery fallback-action accessibility hints.",
        ),
        (
            "macOS Connection Recovery and diagnostics disclosure accessibility state",
            "Default no-device gate coverage summary must mention macOS Connection Recovery and diagnostics disclosure accessibility state.",
        ),
        (
            "macOS menu-bar Pairing QR active-session title",
            "Default no-device gate coverage summary must mention macOS menu-bar Pairing QR active-session title.",
        ),
        (
            "Android chat top-bar model picker streaming disabled state",
            "Default no-device gate coverage summary must mention Android chat top-bar model picker streaming disabled state.",
        ),
        (
            "Android chat top-bar model picker closed-button accessibility summary",
            "Default no-device gate coverage summary must mention Android chat top-bar model picker closed-button accessibility summary.",
        ),
        (
            "Settings memory action accessibility labels",
            "Default no-device gate coverage summary must mention Settings memory action accessibility labels.",
        ),
        (
            "Settings memory delete confirmation action labels",
            "Default no-device gate coverage summary must mention Settings memory delete confirmation action labels.",
        ),
        (
            "chat history bulk expander action labels",
            "Default no-device gate coverage summary must mention chat history bulk expander action labels.",
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
        (
            "Tap Connect",
            "Android string parity must reject touch-specific Connect guidance.",
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
            "trustedDevicePairingAccessibilitySummary(pairedAt: pairedAt, deviceID: deviceID)",
            "macOS localization guard must keep trusted-device row accessibility separate from visual metadata.",
        ),
        (
            "Paired %@. Device ID ending %@",
            "macOS localization guard must require an accessibility-only trusted-device pairing summary.",
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
            "trustedDeviceConfirmRemoveAccessibilityLabel(for: pendingRemovalDevice)",
            "macOS localization guard must require contextual trusted-device confirmation action labels.",
        ),
        (
            "Confirm removing trust for %@. Key fingerprint %@",
            "macOS localization guard must require the trusted-device confirmation action localization key.",
        ),
        (
            "trustedDeviceRefreshActionAccessibilityHint()",
            "macOS localization guard must require Trusted Devices refresh action hints.",
        ),
        (
            "trustedDeviceRefreshActionAccessibilityValue()",
            "macOS localization guard must require Trusted Devices refresh action values.",
        ),
        (
            "Refresh trusted devices from AetherLink Runtime.",
            "macOS localization guard must require the Trusted Devices refresh action hint string.",
        ),
        (
            "logTechnicalDetailsAccessibilityLabel(summary: display.summary)",
            "macOS localization guard must require contextual Activity technical-details accessibility labels.",
        ),
        (
            "logTechnicalDetailsAccessibilityValue(isExpanded: diagnosticsExpanded)",
            "macOS localization guard must require Activity technical-details accessibility values.",
        ),
        (
            "logTechnicalDetailsAccessibilityHint(isExpanded: diagnosticsExpanded)",
            "macOS localization guard must require Activity technical-details accessibility hints.",
        ),
        (
            "logRowAccessibilityLabel(summary: display.summary, tone: tone)",
            "macOS localization guard must require Activity row tone accessibility labels.",
        ),
        (
            "Activity item %@. Status %@.",
            "macOS localization guard must require the Activity row tone accessibility localization key.",
        ),
        (
            "Image(systemName: tone.systemImage)",
            "macOS localization guard must inspect Activity row tone icons.",
        ),
        (
            ".accessibilityHidden(true)",
            "macOS localization guard must require decorative Activity row tone icons to stay hidden from assistive tech.",
        ),
        (
            "Technical details for %@",
            "macOS localization guard must require the Activity technical-details accessibility localization key.",
        ),
        (
            "Activity technical details expanded",
            "macOS localization guard must require the Activity technical-details expanded-state key.",
        ),
        (
            "Expand to show activity technical details.",
            "macOS localization guard must require the Activity technical-details collapsed-state hint key.",
        ),
        (
            "Trusted device %@",
            "macOS localization guard must require explicit trusted-device Activity audit copy.",
        ),
        (
            "Removed trust for %@",
            "macOS localization guard must require explicit trust-removal Activity audit copy.",
        ),
        (
            "trustedDeviceAuditLogName(",
            "macOS Activity audit copy must trim device names and use a localized fallback.",
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
            "routeDiagnosticDisclosureAccessibilityValue(isExpanded: isExpanded)",
            "macOS localization guard must require route diagnostic expanded-state accessibility values.",
        ),
        (
            "routeDiagnosticDisclosureAccessibilityHint()",
            "macOS localization guard must require route diagnostic disclosure accessibility hints.",
        ),
        (
            "connectionRecoveryDisclosureAccessibilityLabel()",
            "macOS localization guard must require Connection Recovery disclosure accessibility labels.",
        ),
        (
            "connectionRecoveryDisclosureAccessibilityValue(isExpanded: isAdvancedRouteSettingsExpanded)",
            "macOS localization guard must require Connection Recovery disclosure expanded-state accessibility values.",
        ),
        (
            "connectionRecoveryDisclosureAccessibilityHint()",
            "macOS localization guard must require Connection Recovery disclosure accessibility hints.",
        ),
        (
            "Connection diagnostics",
            "macOS localization guard must require the route diagnostic technical-details fallback key.",
        ),
        (
            "Connection Recovery settings",
            "macOS localization guard must require Connection Recovery disclosure accessibility label localization.",
        ),
        (
            "Connection Recovery settings expanded",
            "macOS localization guard must require Connection Recovery expanded accessibility value localization.",
        ),
        (
            "Connection Recovery settings collapsed",
            "macOS localization guard must require Connection Recovery collapsed accessibility value localization.",
        ),
        (
            "Show or hide advanced connection recovery fields.",
            "macOS localization guard must require Connection Recovery disclosure accessibility hint localization.",
        ),
        (
            "Connection diagnostics expanded",
            "macOS localization guard must require connection diagnostics expanded accessibility value localization.",
        ),
        (
            "Connection diagnostics collapsed",
            "macOS localization guard must require connection diagnostics collapsed accessibility value localization.",
        ),
        (
            "Show or hide connection diagnostic details.",
            "macOS localization guard must require connection diagnostics disclosure accessibility hint localization.",
        ),
        (
            "connectionRecoveryTextFieldAccessibilityValue(",
            "macOS localization guard must require Connection Recovery text-field accessibility values.",
        ),
        (
            "connectionRecoveryOptionalSecureFieldAccessibilityValue(",
            "macOS localization guard must require Connection Recovery secure optional field accessibility values.",
        ),
        (
            "connectionRecoveryGeneratedSecretAccessibilityValue(",
            "macOS localization guard must require Connection Recovery generated-secret accessibility values.",
        ),
        (
            "connectionRecoveryGenerateLatestQRActionAccessibilityValue(",
            "macOS localization guard must require Connection Recovery QR action accessibility values.",
        ),
        (
            "connectionRecoveryGenerateLatestQRActionAccessibilityHint(",
            "macOS localization guard must require Connection Recovery QR action accessibility hints.",
        ),
        (
            "pairingQRCodeAccessibilityHint(remoteRouteExpiresAt:",
            "macOS localization guard must require Pairing QR remote-route expiry accessibility hints.",
        ),
        (
            "pairingQRRemoteRouteExpirationText(",
            "macOS localization guard must require shared Pairing QR route-expiry accessibility copy.",
        ),
        (
            ".accessibilityHint(Text(generateLatestQRHint))",
            "macOS localization guard must require Connection Recovery QR action accessibility hints on the button.",
        ),
        (
            "connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel(",
            "macOS localization guard must require bootstrap private-overlay toggle accessibility labels.",
        ),
        (
            "connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel(",
            "macOS localization guard must require fallback private-overlay toggle accessibility labels.",
        ),
        (
            "connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled:",
            "macOS localization guard must require private-overlay toggle accessibility values.",
        ),
        (
            ".accessibilityLabel(Text(connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel()))",
            "macOS localization guard must attach bootstrap private-overlay contextual accessibility labels.",
        ),
        (
            ".accessibilityLabel(Text(connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel()))",
            "macOS localization guard must attach fallback private-overlay contextual accessibility labels.",
        ),
        (
            "Bootstrap relay Private Overlay Route",
            "macOS localization guard must require bootstrap private-overlay accessibility localization.",
        ),
        (
            "Fallback connection Private Overlay Route",
            "macOS localization guard must require fallback private-overlay accessibility localization.",
        ),
        (
            "Enabled",
            "macOS localization guard must require private-overlay enabled accessibility value localization.",
        ),
        (
            "Disabled",
            "macOS localization guard must require private-overlay disabled accessibility value localization.",
        ),
        (
            "testConnectionRecoveryPrivateOverlayToggleAccessibilityDistinguishesRouteContext",
            "macOS localization guard must require private-overlay toggle accessibility XCTest coverage.",
        ),
        (
            "testConnectionRecoveryAndRouteDiagnosticDisclosuresExposeLocalizedExpandedState",
            "macOS localization guard must require Connection Recovery and route diagnostic disclosure expanded-state XCTest coverage.",
        ),
        (
            ".accessibilityLabel(Text(NSLocalizedString(\\\"Bootstrap relay endpoints\\\"",
            "macOS localization guard must require explicit Connection Recovery form field accessibility labels.",
        ),
        (
            "\"Entered\"",
            "macOS localization guard must require secure field entered-state localization.",
        ),
        (
            "connectionRecoverySaveConnectionActionAccessibilityValue(host: String, port: String)",
            "macOS localization guard must require Save Connection accessibility value helper.",
        ),
        (
            "testConnectionRecoverySaveConnectionAccessibilityValueExplainsInvalidInputs",
            "macOS localization guard must require Save Connection invalid-input accessibility value coverage.",
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

    macos_relay_secret_store_failures = macos_relay_secret_store_guard_failures()
    if macos_relay_secret_store_failures:
        print("macOS relay secret-store guard failed:", file=sys.stderr)
        for failure in macos_relay_secret_store_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_pairing_qr_accessibility_failures = macos_pairing_qr_accessibility_guard_failures()
    if macos_pairing_qr_accessibility_failures:
        print("macOS Pairing QR accessibility guard failed:", file=sys.stderr)
        for failure in macos_pairing_qr_accessibility_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_quick_action_accessibility_failures = macos_quick_action_accessibility_guard_failures()
    if macos_quick_action_accessibility_failures:
        print("macOS quick action accessibility guard failed:", file=sys.stderr)
        for failure in macos_quick_action_accessibility_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_sidebar_brand_accessibility_failures = macos_sidebar_brand_accessibility_guard_failures()
    if macos_sidebar_brand_accessibility_failures:
        print("macOS sidebar brand accessibility guard failed:", file=sys.stderr)
        for failure in macos_sidebar_brand_accessibility_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_page_header_accessibility_failures = macos_page_header_accessibility_guard_failures()
    if macos_page_header_accessibility_failures:
        print("macOS page header accessibility guard failed:", file=sys.stderr)
        for failure in macos_page_header_accessibility_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_empty_state_accessibility_failures = macos_empty_state_accessibility_guard_failures()
    if macos_empty_state_accessibility_failures:
        print("macOS empty-state accessibility guard failed:", file=sys.stderr)
        for failure in macos_empty_state_accessibility_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    macos_sidebar_preference_accessibility_failures = macos_sidebar_preference_accessibility_guard_failures()
    if macos_sidebar_preference_accessibility_failures:
        print("macOS sidebar preference accessibility guard failed:", file=sys.stderr)
        for failure in macos_sidebar_preference_accessibility_failures:
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

    android_reasoning_accessibility_failures = android_reasoning_accessibility_guard_failures()
    if android_reasoning_accessibility_failures:
        print("Android reasoning accessibility guard failed:", file=sys.stderr)
        for failure in android_reasoning_accessibility_failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    android_streaming_assistant_live_region_failures = android_streaming_assistant_live_region_guard_failures()
    if android_streaming_assistant_live_region_failures:
        print("Android streaming assistant live-region guard failed:", file=sys.stderr)
        for failure in android_streaming_assistant_live_region_failures:
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
