#!/usr/bin/env python3
"""Check macOS Localizable.strings locale parity, order, duplicates, and format args."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = (
    ROOT
    / "apps"
    / "macos"
    / "LocalAgentBridgeApp"
    / "Sources"
    / "Resources"
)
SOURCE_ROOT = ROOT / "apps" / "macos" / "LocalAgentBridgeApp" / "Sources"
APP_LOCALIZATION_SOURCE = SOURCE_ROOT / "AetherLinkLocalization.swift"
APP_ENTRY_SOURCE = SOURCE_ROOT / "LocalAgentBridgeApp.swift"
APP_CONTENT_SOURCE = SOURCE_ROOT / "ContentView.swift"
COMPANION_CHROME_SOURCE = SOURCE_ROOT / "CompanionChrome.swift"
STATUS_VIEW_SOURCE = SOURCE_ROOT / "StatusView.swift"
TRUSTED_DEVICES_VIEW_SOURCE = SOURCE_ROOT / "TrustedDevicesView.swift"
REMOTE_RELAY_ROUTE_PANEL_SOURCE = SOURCE_ROOT / "RemoteRelayRoutePanel.swift"
REMOTE_ROUTE_PREPARATION_COPY_SOURCE = SOURCE_ROOT / "RemoteRoutePreparationCopy.swift"
ACTIVITY_LOGS_SOURCE = SOURCE_ROOT / "LogsView.swift"
COMPANION_APP_MODEL_SOURCE = (
    ROOT / "apps" / "macos" / "CompanionCore" / "Sources" / "CompanionAppModel.swift"
)
LOCALIZATION_TEST_SOURCE = (
    ROOT / "apps" / "macos" / "LocalAgentBridgeApp" / "Tests" / "AetherLinkLocalizationTests.swift"
)
LOCALES = ("en", "ko", "ja", "zh-Hans", "fr")
BASE_LOCALE = "en"
EXPECTED_APP_LANGUAGES = {
    "english": "en",
    "korean": "ko",
    "japanese": "ja",
    "simplifiedChinese": "zh-Hans",
    "french": "fr",
}
EXPECTED_APP_LANGUAGE_TITLES = {
    "english": "English",
    "korean": "한국어",
    "japanese": "日本語",
    "simplifiedChinese": "简体中文",
    "french": "Français",
}
EXPECTED_APP_APPEARANCES = ("system", "light", "dark")
REQUIRED_LANGUAGE_KEYS = (
    "Language",
    "English",
    "Korean",
    "Japanese",
    "Simplified Chinese",
    "French",
)
REQUIRED_APPEARANCE_KEYS = (
    "Appearance",
    "System",
    "Light",
    "Dark",
)
REQUIRED_CONNECTION_SAFETY_KEYS = (
    "Remove Saved Connection Details",
    "Remove saved connection details?",
    "Remove saved connection details for %@",
    "Cancel removing saved connection details for %@",
    "Saved connection details removed.",
    "Saved connection details will be removed. Devices on another network may need a fresh pairing QR before they can reconnect.",
)
REQUIRED_ACTIVITY_REDACTION_KEYS = (
    "Provider endpoint redacted.",
    "Sensitive technical detail redacted.",
    "Activity technical details expanded",
    "Activity technical details collapsed",
    "Collapse to hide activity technical details.",
    "Expand to show activity technical details.",
)
REQUIRED_TRUSTED_DEVICE_KEYS = (
    "Key fingerprint %@",
    "%@ will need to pair again before it can use AetherLink Runtime. Key fingerprint %@",
    "Selected device",
    "Cancel removing trust for %@. Key fingerprint %@",
)
REQUIRED_REMOTE_ROUTE_PREPARATION_KEYS = (
    "Connection Recovery result",
    "%@. Status %@. %@",
    "Connection health",
    "Connection preparation",
    "Connection diagnostics",
    "AetherLink could not get connection details from the route service. Check Connection Recovery, then generate a fresh QR.",
    "Connection details for %@ cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.",
    "Connection details cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.",
    "Connection details for %@ could not be prepared automatically. Check Connection Recovery, then generate a fresh QR.",
    "Connection details could not be prepared automatically. Check Connection Recovery, then generate a fresh QR.",
    "Connection details need a secure connection secret before they can be included in a QR.",
    "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR.",
    "Connection failed. Check Connection Recovery, then generate a fresh QR.",
)
REQUIRED_CONNECTION_RECOVERY_ACCESSIBILITY_KEYS = (
    "Bootstrap relay Private Overlay Route",
    "Fallback connection Private Overlay Route",
    "Enabled",
    "Disabled",
    "Connection Recovery settings",
    "Connection Recovery settings expanded",
    "Connection Recovery settings collapsed",
    "Show or hide advanced connection recovery fields.",
    "Connection diagnostics expanded",
    "Connection diagnostics collapsed",
    "Show or hide connection diagnostic details.",
    "Enter a connection address.",
    "Enter only the connection address. Put the port in the Port field.",
    "Enter a valid connection port.",
)
REQUIRED_RUNTIME_REASONING_KEYS = (
    "Thinking",
    "Show thinking",
    "Hide thinking",
    "Thinking expanded",
    "Thinking collapsed",
    "Expand to show full thinking.",
    "Collapse to keep thinking preview short.",
)
REQUIRED_RUNTIME_HISTORY_KEYS = (
    "Selected",
    "Not selected",
    "Load this runtime-owned transcript preview.",
)
REQUIRED_RELEASE_COPY_VALUES = {
    "en": {
        "Generated automatically if blank": "Created automatically if left blank",
        "Rotate Secret": "Refresh Key",
        "Technical Details": "Details",
        "Provider endpoint redacted.": "Provider address hidden.",
        "Connection Recovery needs attention.": "Connection Recovery needs attention.",
        "Connection Recovery": "Connection Recovery",
        "Connection Setup": "Recovery Details",
        "Connection setup secret": "Protected connection key",
        "Connection setup secret regenerated.": "Protected connection key refreshed.",
        "Close Runtime History Inspector": "Close Runtime History Inspector",
        "Close Runtime Memory Inspector": "Close Runtime Memory Inspector",
        "Refresh Runtime History Inspector": "Refresh Runtime History Inspector",
        "Refresh Runtime Memory Inspector": "Refresh Runtime Memory Inspector",
        "Selected": "Selected",
        "Not selected": "Not selected",
        "Load this runtime-owned transcript preview.": "Load this runtime-owned transcript preview.",
        "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR.": (
            "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR."
        ),
    },
    "ko": {
        "Generated automatically if blank": "비워두면 자동으로 생성됩니다",
        "Rotate Secret": "키 새로 고침",
        "Technical Details": "세부 정보",
        "Provider endpoint redacted.": "제공자 주소가 숨겨졌습니다.",
        "Connection Recovery needs attention.": "연결 복구 확인이 필요합니다.",
        "Connection Recovery": "연결 복구",
        "Connection Setup": "복구 세부 정보",
        "Connection setup secret": "보호된 연결 키",
        "Connection setup secret regenerated.": "보호된 연결 키를 새로 고쳤습니다.",
        "Close Runtime History Inspector": "런타임 기록 점검 닫기",
        "Close Runtime Memory Inspector": "런타임 메모리 점검 닫기",
        "Refresh Runtime History Inspector": "런타임 기록 점검 새로 고침",
        "Refresh Runtime Memory Inspector": "런타임 메모리 점검 새로 고침",
        "Selected": "선택됨",
        "Not selected": "선택되지 않음",
        "Load this runtime-owned transcript preview.": "이 런타임 소유 대화 미리보기를 불러옵니다.",
        "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR.": (
            "%@을(를) 통한 연결에 실패했습니다. 연결 복구를 확인한 뒤 새 QR을 생성하세요."
        ),
    },
    "ja": {
        "Generated automatically if blank": "空欄の場合は自動で作成されます",
        "Rotate Secret": "キーを更新",
        "Technical Details": "詳細",
        "Provider endpoint redacted.": "プロバイダーのアドレスは非表示です。",
        "Connection Recovery needs attention.": "接続の復旧に確認が必要です。",
        "Connection Recovery": "接続の復旧",
        "Connection Setup": "復旧の詳細",
        "Connection setup secret": "保護された接続キー",
        "Connection setup secret regenerated.": "保護された接続キーを更新しました。",
        "Close Runtime History Inspector": "ランタイム履歴インスペクタを閉じる",
        "Close Runtime Memory Inspector": "ランタイムメモリインスペクタを閉じる",
        "Refresh Runtime History Inspector": "ランタイム履歴インスペクタを更新",
        "Refresh Runtime Memory Inspector": "ランタイムメモリインスペクタを更新",
        "Selected": "選択済み",
        "Not selected": "未選択",
        "Load this runtime-owned transcript preview.": "このランタイム所有の会話プレビューを読み込みます。",
        "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR.": (
            "%@ 経由の接続に失敗しました。接続の復旧を確認してから、新しい QR を生成してください。"
        ),
    },
    "zh-Hans": {
        "Generated automatically if blank": "留空则自动创建",
        "Rotate Secret": "刷新密钥",
        "Technical Details": "详情",
        "Provider endpoint redacted.": "提供方地址已隐藏。",
        "Connection Recovery needs attention.": "连接恢复需要检查。",
        "Connection Recovery": "连接恢复",
        "Connection Setup": "恢复详情",
        "Connection setup secret": "受保护的连接密钥",
        "Connection setup secret regenerated.": "已刷新受保护的连接密钥。",
        "Close Runtime History Inspector": "关闭运行时历史检查器",
        "Close Runtime Memory Inspector": "关闭运行时记忆检查器",
        "Refresh Runtime History Inspector": "刷新运行时历史检查器",
        "Refresh Runtime Memory Inspector": "刷新运行时记忆检查器",
        "Selected": "已选择",
        "Not selected": "未选择",
        "Load this runtime-owned transcript preview.": "加载这个由运行时拥有的对话预览。",
        "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR.": (
            "通过 %@ 的连接失败。请检查连接恢复，然后生成新的二维码。"
        ),
    },
    "fr": {
        "Generated automatically if blank": "Créée automatiquement si le champ est vide",
        "Rotate Secret": "Actualiser la clé",
        "Technical Details": "Détails",
        "Provider endpoint redacted.": "Adresse du fournisseur masquée.",
        "Connection Recovery needs attention.": "La récupération de connexion demande une vérification.",
        "Connection Recovery": "Récupération de connexion",
        "Connection Setup": "Détails de récupération",
        "Connection setup secret": "Clé de connexion protégée",
        "Connection setup secret regenerated.": "Clé de connexion protégée actualisée.",
        "Assistant": "Assistant IA",
        "Chat": "Discussion",
        "Close Runtime History Inspector": "Fermer l’inspecteur d’historique du runtime",
        "Close Runtime Memory Inspector": "Fermer l’inspecteur de mémoire du runtime",
        "Refresh Runtime History Inspector": "Actualiser l’inspecteur d’historique du runtime",
        "Refresh Runtime Memory Inspector": "Actualiser l’inspecteur de mémoire du runtime",
        "Selected": "Sélectionné",
        "Not selected": "Non sélectionné",
        "Load this runtime-owned transcript preview.": "Charger cet aperçu de transcription détenu par le runtime.",
        "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR.": (
            "La connexion via %@ a échoué. Vérifiez la récupération de connexion, puis générez un nouveau QR."
        ),
    },
}
FORBIDDEN_STALE_KEYS = (
    "Desktop Runtime",
    "Runtime Logs",
    "Route host",
    "Remote route host",
    "Enter a route host.",
    "Enter only a route host or IP address. Put the port in the port field.",
    "This route address points back to this device. A device on another network cannot reach it.",
    "Enter only the route host name or IP address. Put the port in the Port field.",
    "This route host is a private network address. Use a public, VPN, or tunnel address reachable from both devices.",
    "This route host is local-network only. Use a public, VPN, or tunnel address for different networks.",
    "Ollama and LM Studio are checked on this device.",
    "Model providers are checked from this device.",
    "Model providers are checked from the runtime host.",
    "Review runtime-owned chat sessions stored on this runtime host.",
    "Loopback routes only work on this runtime host or USB diagnostics, not from another network.",
    "Pair a device before allowing runtime commands.",
    "%@ is not responding from this device.",
    "%@ is not responding on this device.",
    "%@ is not responding on the runtime host.",
    "Open a local model provider on this device, then check again.",
    "Open a model provider on this device, then check again.",
    "Open a model provider on the runtime host, then check again.",
    "Start a model provider on this device, then check again.",
    "Start a model provider on the runtime host, then check again.",
    "Keep the runtime host awake until pairing completes.",
    "New QR codes include %@ after AetherLink Runtime registers with that route.",
    "Using %@ from saved connection settings. Generate a fresh QR after changing the connection.",
)

ENTRY_RE = re.compile(
    r"""
    ^\s*
    "((?:\\.|[^"\\])*)"
    \s*=\s*
    "((?:\\.|[^"\\])*)"
    \s*;
    \s*$
    """,
    re.VERBOSE,
)
NSLOCALIZEDSTRING_RE = re.compile(r'NSLocalizedString\("((?:\\.|[^"\\])*)"')
FORMAT_PLACEHOLDER_RE = re.compile(
    r"""
    (?<!%)
    %
    (?:\d+\$)?
    [-+\ \#0]*
    (?:\d+|\*)?
    (?:\.(?:\d+|\*))?
    (?:hh|h|ll|l|L|z|t|j)?
    [@diuoxXfFeEgGaAcCsSp]
    """,
    re.VERBOSE,
)
APP_LANGUAGE_CASE_RE = re.compile(r"case\s+([A-Za-z][A-Za-z0-9]*)\s*=\s*\"([^\"]+)\"")
APP_APPEARANCE_CASE_RE = re.compile(
    r"enum\s+AetherLinkAppAppearance[\s\S]*?\{(?P<body>[\s\S]*?)\n\}"
)
APP_APPEARANCE_PICKER_RE = re.compile(
    r"static\s+let\s+pickerOptions:\s+\[AetherLinkAppAppearance\]\s*=\s*\[(?P<body>[\s\S]*?)\]"
)
RAW_SWIFTUI_VISIBLE_LITERAL_RE = re.compile(
    r"""
    \b
    (?:
        Text|Button|Label|Picker|Toggle|Section|NavigationLink|Menu|
        TextField|SecureField
    )
    \s*\(\s*
    (?:
        title\s*:\s*
    )?
    "
    |
    \.
    (?:
        alert|confirmationDialog
    )
    \s*\(\s*"
    """,
    re.VERBOSE,
)


def strings_path(locale: str) -> Path:
    return RESOURCE_ROOT / f"{locale}.lproj" / "Localizable.strings"


def lint_with_plutil(path: Path) -> str | None:
    plutil = shutil.which("plutil")
    if plutil is None:
        return None

    result = subprocess.run(
        [plutil, "-lint", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return None

    detail = (result.stderr or result.stdout).strip()
    return detail or "plutil reported invalid property-list strings syntax"


def unescape_key(value: str) -> str:
    return (
        value.replace(r"\"", '"')
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )


def parse_entries(path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    entries: list[tuple[str, str]] = []
    failures: list[str] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        match = ENTRY_RE.match(line)
        if match is None:
            failures.append(f"line {line_number}: could not parse strings entry")
            continue

        entries.append((unescape_key(match.group(1)), match.group(2)))

    return entries, failures


def entry_keys(entries: list[tuple[str, str]]) -> list[str]:
    return [key for key, _ in entries]


def duplicate_keys(keys: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []

    for key in keys:
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)

    return duplicates


def format_placeholders(value: str) -> list[str]:
    placeholders = FORMAT_PLACEHOLDER_RE.findall(value)
    if placeholders and all("$" in placeholder for placeholder in placeholders):
        return sorted(placeholders)
    return placeholders


def release_copy_value_failures(locale: str, values: dict[str, str], relative_path: Path) -> list[str]:
    expected_values = REQUIRED_RELEASE_COPY_VALUES.get(locale, {})
    failures: list[str] = []
    for key, expected_value in expected_values.items():
        actual_value = values.get(key)
        if actual_value != expected_value:
            failures.append(
                f"{relative_path}: release copy mismatch for {key!r} "
                f"(expected={expected_value!r}, actual={actual_value!r})"
            )
    return failures


def source_localized_keys() -> list[tuple[str, Path, int]]:
    keys: list[tuple[str, Path, int]] = []

    for path in sorted(SOURCE_ROOT.rglob("*.swift")):
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in NSLOCALIZEDSTRING_RE.finditer(line):
                keys.append((unescape_key(match.group(1)), relative_path, line_number))

    return keys


def check_app_language_selector() -> list[str]:
    failures: list[str] = []
    relative_path = APP_LOCALIZATION_SOURCE.relative_to(ROOT)

    if not APP_LOCALIZATION_SOURCE.exists():
        return [f"{relative_path}: missing macOS app language selector"]

    source = APP_LOCALIZATION_SOURCE.read_text(encoding="utf-8")
    cases = dict(APP_LANGUAGE_CASE_RE.findall(source))

    if cases != EXPECTED_APP_LANGUAGES:
        failures.append(
            f"{relative_path}: expected app languages {EXPECTED_APP_LANGUAGES}, found {cases}"
        )

    if "static let defaultLanguage = AetherLinkAppLanguage.english" not in source:
        failures.append(f"{relative_path}: app language default must remain English")

    if 'let AetherLinkAppLanguageStorageKey = "aetherlink.appLanguageTag"' not in source:
        failures.append(f"{relative_path}: app language storage key changed unexpectedly")

    for expected_snippet in (
        'let baseLanguage = normalized.split(separator: "-", maxSplits: 1).first.map(String.init) ?? normalized',
        'language.rawValue.caseInsensitiveCompare(baseLanguage) == .orderedSame',
    ):
        if expected_snippet not in source:
            failures.append(
                f"{relative_path}: app language normalization must accept region-qualified tags"
            )

    for case_name, title in EXPECTED_APP_LANGUAGE_TITLES.items():
        expected_snippet = f"case .{case_name}:\n            return \"{title}\""
        if expected_snippet not in source:
            failures.append(
                f"{relative_path}: language picker case {case_name!r} must use native label {title!r}"
            )

    for locale in EXPECTED_APP_LANGUAGES.values():
        if locale not in LOCALES:
            failures.append(f"{relative_path}: app language {locale!r} is not in LOCALES")

    return failures


def swift_enum_case_names(enum_body: str) -> list[str]:
    names: list[str] = []
    for match in re.finditer(r"\bcase\s+([A-Za-z][A-Za-z0-9]*)\b", enum_body):
        names.append(match.group(1))
    return names


def check_app_appearance_selector() -> list[str]:
    failures: list[str] = []
    relative_path = APP_LOCALIZATION_SOURCE.relative_to(ROOT)

    if not APP_LOCALIZATION_SOURCE.exists():
        return [f"{relative_path}: missing macOS app appearance selector"]

    source = APP_LOCALIZATION_SOURCE.read_text(encoding="utf-8")
    enum_match = APP_APPEARANCE_CASE_RE.search(source)
    if enum_match is None:
        return [f"{relative_path}: AetherLinkAppAppearance enum not found"]

    cases = tuple(swift_enum_case_names(enum_match.group("body")))
    if cases != EXPECTED_APP_APPEARANCES:
        failures.append(
            f"{relative_path}: expected app appearances {EXPECTED_APP_APPEARANCES}, found {cases}"
        )

    picker_match = APP_APPEARANCE_PICKER_RE.search(source)
    if picker_match is None:
        failures.append(f"{relative_path}: AetherLinkAppAppearance.pickerOptions not found")
    else:
        picker_cases = tuple(
            match.group(1)
            for match in re.finditer(r"\.([A-Za-z][A-Za-z0-9]*)\b", picker_match.group("body"))
        )
        if picker_cases != EXPECTED_APP_APPEARANCES:
            failures.append(
                f"{relative_path}: expected app appearance picker options "
                f"{EXPECTED_APP_APPEARANCES}, found {picker_cases}"
            )

    if "static let defaultAppearance = AetherLinkAppAppearance.system" not in source:
        failures.append(f"{relative_path}: app appearance default must remain System")

    if 'let AetherLinkAppAppearanceStorageKey = "aetherlink.appAppearance"' not in source:
        failures.append(f"{relative_path}: app appearance storage key changed unexpectedly")

    if "case .system:\n            return nil" not in source:
        failures.append(f"{relative_path}: system appearance must follow the OS color scheme")

    if "case .light:\n            return .light" not in source:
        failures.append(f"{relative_path}: light appearance must map to ColorScheme.light")

    if "case .dark:\n            return .dark" not in source:
        failures.append(f"{relative_path}: dark appearance must map to ColorScheme.dark")

    return failures


def missing_source_snippets(path: Path, expected_snippets: tuple[str, ...], label: str) -> list[str]:
    relative_path = path.relative_to(ROOT)
    if not path.exists():
        return [f"{relative_path}: missing {label}"]

    source = path.read_text(encoding="utf-8")
    failures: list[str] = []
    for snippet in expected_snippets:
        if snippet not in source:
            failures.append(f"{relative_path}: missing {label} snippet {snippet!r}")
    return failures


def check_app_appearance_wiring() -> list[str]:
    app_entry_snippets = (
        "@AppStorage(AetherLinkAppAppearanceStorageKey) private var appAppearance = "
        "AetherLinkAppAppearance.defaultAppearance.rawValue",
        ".preferredColorScheme(currentAppAppearance.preferredColorScheme)",
        "private var currentAppAppearance: AetherLinkAppAppearance",
        "AetherLinkAppAppearance.normalized(appAppearance)",
    )
    content_view_snippets = (
        "@AppStorage(AetherLinkAppAppearanceStorageKey) private var appAppearance = "
        "AetherLinkAppAppearance.defaultAppearance.rawValue",
        "AetherLinkAppearancePicker(appearance: appearanceBinding)",
        "private var appearanceBinding: Binding<String>",
        "AetherLinkAppAppearance.normalized(appAppearance).rawValue",
        "appAppearance = AetherLinkAppAppearance.normalized(newValue).rawValue",
        ".accessibilityHidden(true)",
        ".accessibilityElement(children: .ignore)",
        ".accessibilityLabel(Text(sidebarBrandAccessibilityLabel()))",
        ".accessibilityAddTraits(.isHeader)",
        "func sidebarBrandAccessibilityLabel() -> String",
        "Text(appPreferencesAccessibilityLabel())",
        "func appPreferencesAccessibilityLabel() -> String",
        "func appAppearancePickerDetailText() -> String",
        "func appLanguagePickerDetailText() -> String",
        ".accessibilityValue(Text(AetherLinkAppAppearance.normalized(appearance).title))",
        ".accessibilityValue(Text(AetherLinkAppLanguage.normalized(languageTag).title))",
        ".accessibilityHint(Text(appAppearancePickerAccessibilityHint()))",
        ".accessibilityHint(Text(appLanguagePickerAccessibilityHint()))",
        "System follows this device's appearance. Saved for future launches.",
        "Choose one of the supported app languages. Saved for future launches.",
        "App Preferences",
        "Choose how AetherLink Runtime appears. This setting is saved for future launches.",
        "Choose the app language. This setting is saved for future launches.",
    )

    return [
        *missing_source_snippets(APP_ENTRY_SOURCE, app_entry_snippets, "macOS app appearance wiring"),
        *missing_source_snippets(APP_CONTENT_SOURCE, content_view_snippets, "macOS sidebar appearance wiring"),
        *missing_source_snippets(
            LOCALIZATION_TEST_SOURCE,
            (
                "testSidebarPreferencePickerAccessibilityHintsUseSelectedLanguage",
                "testSidebarPreferenceGroupLabelUsesSelectedLanguage",
                "testSidebarPreferenceDetailTextUsesSelectedLanguage",
                "appAppearancePickerAccessibilityHint()",
                "appLanguagePickerAccessibilityHint()",
                "appPreferencesAccessibilityLabel()",
                "appAppearancePickerDetailText()",
                "appLanguagePickerDetailText()",
                "This setting is saved for future launches.",
            ),
            "macOS sidebar preference picker accessibility hint tests",
        ),
    ]


def check_companion_page_header_accessibility() -> list[str]:
    companion_chrome_snippets = (
        ".accessibilityElement(children: .ignore)",
        ".accessibilityLabel(Text(companionPageHeaderAccessibilityLabel(title: title, subtitle: subtitle)))",
        ".accessibilityAddTraits(.isHeader)",
        "func companionPageHeaderAccessibilityLabel(title: String, subtitle: String) -> String",
        "NSLocalizedString(\"%@. %@\"",
    )

    return missing_source_snippets(
        COMPANION_CHROME_SOURCE,
        companion_chrome_snippets,
        "macOS page header accessibility wiring",
    )


def check_companion_panel_header_accessibility() -> list[str]:
    companion_chrome_snippets = (
        ".accessibilityLabel(Text(companionPanelHeaderAccessibilityLabel(title: title)))",
        ".accessibilityAddTraits(.isHeader)",
        "func companionPanelHeaderAccessibilityLabel(title: String) -> String",
    )

    return missing_source_snippets(
        COMPANION_CHROME_SOURCE,
        companion_chrome_snippets,
        "macOS panel header accessibility wiring",
    )


def check_companion_empty_state_accessibility() -> list[str]:
    empty_state_helper_snippets = (
        "func companionEmptyStateAccessibilityLabel(title: String, description: String) -> String",
        "companionPageHeaderAccessibilityLabel(title: title, subtitle: description)",
    )
    empty_state_source_snippets = (
        ".accessibilityLabel(\n                            Text(\n                                companionEmptyStateAccessibilityLabel(",
        "emptyModelsTitle",
        "emptyModelsDescription",
        "emptyModelProvidersTitle",
        "emptyModelProvidersDescription",
        "ContentUnavailableView(\n                            emptyModelProvidersTitle,",
        "emptyPairingTitle",
        "emptyPairingDescription",
        "emptyTrustedDevicesTitle",
        "emptyTrustedDevicesDescription",
        "emptyActivityTitle",
        "emptyActivityDescription",
    )

    return [
        *missing_source_snippets(
            COMPANION_CHROME_SOURCE,
            empty_state_helper_snippets,
            "macOS empty state accessibility helper",
        ),
        *missing_source_snippets(
            STATUS_VIEW_SOURCE,
            empty_state_source_snippets[:6],
            "macOS Status empty state accessibility wiring",
        ),
        *missing_source_snippets(
            SOURCE_ROOT / "PairingView.swift",
            (
                ".accessibilityLabel(\n                                Text(\n                                    companionEmptyStateAccessibilityLabel(",
                "emptyPairingTitle",
                "emptyPairingDescription",
            ),
            "macOS Pairing empty state accessibility wiring",
        ),
        *missing_source_snippets(
            TRUSTED_DEVICES_VIEW_SOURCE,
            (
                ".accessibilityLabel(\n                        Text(\n                            companionEmptyStateAccessibilityLabel(",
                "emptyTrustedDevicesTitle",
                "emptyTrustedDevicesDescription",
            ),
            "macOS Trusted Devices empty state accessibility wiring",
        ),
        *missing_source_snippets(
            ACTIVITY_LOGS_SOURCE,
            (
                ".accessibilityLabel(\n                        Text(\n                            companionEmptyStateAccessibilityLabel(",
                "emptyActivityTitle",
                "emptyActivityDescription",
            ),
            "macOS Activity empty state accessibility wiring",
        ),
    ]


def check_no_raw_swiftui_visible_literals() -> list[str]:
    failures: list[str] = []

    for path in sorted(SOURCE_ROOT.glob("*.swift")):
        relative_path = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for match in RAW_SWIFTUI_VISIBLE_LITERAL_RE.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            failures.append(
                f"{relative_path}:{line_number}: visible SwiftUI text must use "
                "NSLocalizedString so the in-app language setting applies."
            )

    return failures


def raw_swiftui_visible_literal_matcher_self_test_failures() -> list[str]:
    failures: list[str] = []
    unsafe_samples = (
        ("positional Text", 'Text("Raw visible copy")'),
        ("multiline Text", 'let value = 1\nText(\n    "Raw visible copy"\n)'),
        ("positional Button", 'Button("Raw action") {}'),
        ("multiline Button", 'Button(\n    "Raw action"\n) {}'),
        ("raw Label", 'Label("Raw label", systemImage: "bolt")'),
        ("raw Picker title", 'Picker(title: "Raw picker", selection: $selection) {}'),
        ("raw alert", '.alert("Raw alert", isPresented: $isPresented) {}'),
        ("multiline alert", '.alert(\n    "Raw alert",\n    isPresented: $isPresented\n) {}'),
        ("multiline confirmation dialog", '.confirmationDialog(\n    "Raw confirmation",\n    isPresented: $isPresented\n) {}'),
    )
    safe_samples = (
        ("localized Text", 'Text(NSLocalizedString("app.name", comment: ""))'),
        ("localized Button", 'Button(NSLocalizedString("Save", comment: "")) {}'),
    )

    for label, sample in unsafe_samples:
        matches = list(RAW_SWIFTUI_VISIBLE_LITERAL_RE.finditer(sample))
        if not matches:
            failures.append(
                "raw SwiftUI visible-string matcher missed required sample "
                f"{label}: {sample!r}"
            )
            continue
        if label == "multiline Text":
            line_number = sample.count("\n", 0, matches[0].start()) + 1
            if line_number != 2:
                failures.append(
                    "raw SwiftUI visible-string matcher reported "
                    f"line {line_number} for {label}, expected 2"
                )

    for label, sample in safe_samples:
        if RAW_SWIFTUI_VISIBLE_LITERAL_RE.search(sample) is not None:
            failures.append(
                "raw SwiftUI visible-string matcher rejected localized sample "
                f"{label}: {sample!r}"
            )

    return failures


def check_no_parenthetical_plural_resources() -> list[str]:
    failures: list[str] = []

    for locale in LOCALES:
        path = strings_path(locale)
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "(s)" in line:
                failures.append(
                    f"{relative_path}:{line_number}: avoid parenthetical plural copy in localized UI resources."
                )

    return failures


def check_remote_connection_destructive_confirmation() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        REMOTE_RELAY_ROUTE_PANEL_SOURCE,
        (
            "@State private var isRemoveSavedConnectionDetailsConfirmationPresented = false",
            "isRemoveSavedConnectionDetailsConfirmationPresented = true",
            '.confirmationDialog(\n            NSLocalizedString("Remove saved connection details?", comment: "")',
            "model.clearDevelopmentRelay()",
            'Button(NSLocalizedString("Remove Saved Connection Details", comment: ""), role: .destructive)',
            ".accessibilityLabel(\n                Text(\n                    removeSavedConnectionDetailsAccessibilityLabel(",
            ".accessibilityLabel(Text(removeSavedConnectionDetailsAccessibilityLabel(endpoint: settings.endpointLabel)))",
            ".accessibilityHint(Text(removeSavedConnectionDetailsAccessibilityHint()))",
            "func removeSavedConnectionDetailsAccessibilityLabel(endpoint: String?) -> String",
            "func removeSavedConnectionDetailsAccessibilityHint() -> String",
            "Remove saved connection details for %@",
            "Remove saved fallback connection details used for future pairing QR routes.",
            'Button(NSLocalizedString("Cancel", comment: ""), role: .cancel)',
            ".accessibilityLabel(\n                    Text(\n                        cancelRemoveSavedConnectionDetailsAccessibilityLabel(",
            "func cancelRemoveSavedConnectionDetailsAccessibilityLabel(endpoint: String?) -> String",
            "Cancel removing saved connection details for %@",
            'Text(NSLocalizedString("Saved connection details will be removed. Devices on another network may need a fresh pairing QR before they can reconnect.", comment: ""))',
        ),
        "macOS remote connection destructive confirmation",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "testRemoveSavedConnectionDetailsAccessibilityUsesSelectedLanguage",
            "testCancelRemoveSavedConnectionDetailsAccessibilityLabelUsesRouteContext",
            "removeSavedConnectionDetailsAccessibilityHint()",
            "cancelRemoveSavedConnectionDetailsAccessibilityLabel(",
        ),
        "macOS remote connection destructive confirmation localization tests",
    ))
    failures.extend(missing_source_snippets(
        REMOTE_RELAY_ROUTE_PANEL_SOURCE,
        (
            "accessibilityContext: NSLocalizedString(\"Connection Recovery result\", comment: \"\")",
            "accessibilityContext: NSLocalizedString(\"Connection health\", comment: \"\")",
            "accessibilityContext: NSLocalizedString(\"Connection preparation\", comment: \"\")",
            "routeDiagnosticDisclosureAccessibilityLabel(context: accessibilityContext)",
            "routeDiagnosticDisclosureAccessibilityValue(isExpanded: isExpanded)",
            "routeDiagnosticDisclosureAccessibilityHint()",
            "connectionRecoveryResultAccessibilityLabel(message: message, tone: messageTone)",
            "func connectionRecoveryResultAccessibilityLabel(message: String, tone: StatusTone) -> String",
            ".accessibilityLabel(Text(connectionRecoveryHostWarningAccessibilityLabel(message: warningText)))",
            "func connectionRecoveryHostWarningAccessibilityLabel(message: String) -> String",
            "Connection Recovery warning",
            "No details available.",
            "%@. Status %@. %@",
            "func routeDiagnosticDisclosureAccessibilityLabel(context: String) -> String",
            "func routeDiagnosticDisclosureAccessibilityValue(isExpanded: Bool) -> String",
            "func routeDiagnosticDisclosureAccessibilityHint() -> String",
            "connectionRecoveryDisclosureAccessibilityLabel()",
            "connectionRecoveryDisclosureAccessibilityValue(isExpanded: isAdvancedRouteSettingsExpanded)",
            "connectionRecoveryDisclosureAccessibilityHint()",
            "func connectionRecoveryDisclosureAccessibilityLabel() -> String",
            "func connectionRecoveryDisclosureAccessibilityValue(isExpanded: Bool) -> String",
            "func connectionRecoveryDisclosureAccessibilityHint() -> String",
            "Connection diagnostics",
            "Technical details for %@",
            "Connection Recovery settings",
            "Connection Recovery settings expanded",
            "Connection Recovery settings collapsed",
            "Show or hide advanced connection recovery fields.",
            "Connection diagnostics expanded",
            "Connection diagnostics collapsed",
            "Show or hide connection diagnostic details.",
            "RelayStatusRow(",
            ".accessibilityElement(children: .ignore)",
            "relayStatusRowAccessibilityLabel(title: title, value: value, detail: detail)",
            "func relayStatusRowAccessibilityLabel(title: String, value: String, detail: String) -> String",
            "connectionRecoveryTextFieldAccessibilityValue(",
            "connectionRecoveryOptionalSecureFieldAccessibilityValue(",
            "connectionRecoveryGeneratedSecretAccessibilityValue(",
            "connectionRecoveryGenerateLatestQRActionAccessibilityValue(",
            "Connection details not ready",
            "connectionRecoveryGenerateLatestQRActionAccessibilityHint(",
            "connectionRecoverySaveBootstrapRelayActionAccessibilityHint(",
            "connectionRecoveryBootstrapAllocationTokenWarning(",
            "connectionRecoveryBootstrapAllocationTokenAccessibilityValue(",
            "bootstrapRelayEndpointsNeedAllocationToken(",
            "connectionRecoverySaveBootstrapRelayActionAccessibilityValue(",
            "func connectionRecoverySaveBootstrapRelayActionAccessibilityValue(\n    endpoints: String,\n    allocationToken: String = \"\"",
            "allocationToken: String = \"\"",
            "allocationToken: bootstrapAllocationToken",
            "removeSavedBootstrapRelayAccessibilityLabel(",
            "cancelRemoveSavedBootstrapRelayAccessibilityLabel(",
            "connectionRecoverySaveConnectionActionAccessibilityValue(",
            "connectionRecoverySaveConnectionActionAccessibilityValue(host: String, port: String)",
            "connectionRecoverySaveConnectionActionAccessibilityHint(",
            "connectionRecoveryRotateSecretActionAccessibilityHint(",
            "connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel(",
            "connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel(",
            "connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled:",
            ".accessibilityLabel(Text(NSLocalizedString(\"Bootstrap relay endpoints\"",
            ".accessibilityLabel(Text(connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel()))",
            ".accessibilityLabel(Text(connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel()))",
            ".accessibilityValue(Text(connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: bootstrapAllowsPrivateOverlay)))",
            ".accessibilityValue(Text(connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: allowsPrivateOverlay)))",
            "connectionRecoverySaveBootstrapRelayActionAccessibilityValue(\n                                    endpoints: bootstrapEndpoints,\n                                    allocationToken: bootstrapAllocationToken",
            ".accessibilityValue(Text(saveConnectionActionValue))",
            ".accessibilityHint(Text(generateLatestQRHint))",
            ".accessibilityHint(Text(removeSavedBootstrapRelayAccessibilityHint()))",
            "func removeSavedBootstrapRelayAccessibilityHint() -> String",
            ".accessibilityHint(Text(NSLocalizedString(\"Enable only when this bootstrap relay is reachable through a VPN, tunnel, or private overlay shared by both devices.\", comment: \"\")))",
            ".accessibilityHint(Text(NSLocalizedString(\"Enable only when this private address is reachable through a VPN, tunnel, or private overlay shared by both devices.\", comment: \"\")))",
            ".accessibilityHint(Text(connectionRecoverySaveBootstrapRelayActionAccessibilityHint()))",
            ".accessibilityHint(Text(connectionRecoverySaveConnectionActionAccessibilityHint()))",
            ".accessibilityHint(Text(connectionRecoveryRotateSecretActionAccessibilityHint()))",
            "Entered",
            "Connection route",
            "Connection setting",
            "No details available.",
            "Connection setting %@. Status %@. %@",
            "Generate the latest pairing QR with saved connection details.",
            "Connection details are not ready for QR generation. Check Connection Recovery settings.",
            "Latest QR generation is unavailable from this view.",
            "Save bootstrap relay settings for future pairing QR connection details.",
            "Add an allocation token before using a non-local bootstrap relay.",
            "Missing token for non-local bootstrap relay",
            "Will remove saved bootstrap relay",
            "Remove Bootstrap Relay",
            "Remove saved bootstrap relay?",
            "Saved bootstrap relay removed.",
            "Save fallback connection details for future pairing QR routes.",
            "Create a new connection setup secret for future pairing QR connection details.",
        ),
        "macOS connection recovery accessibility labels",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "testConnectionRecoveryPrivateOverlayToggleAccessibilityDistinguishesRouteContext",
            "connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel()",
            "connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel()",
            "connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: true)",
            "connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: false)",
            "testConnectionRecoveryAndRouteDiagnosticDisclosuresExposeLocalizedExpandedState",
            "connectionRecoveryDisclosureAccessibilityValue(isExpanded: true)",
            "connectionRecoveryDisclosureAccessibilityValue(isExpanded: false)",
            "routeDiagnosticDisclosureAccessibilityValue(isExpanded: true)",
            "routeDiagnosticDisclosureAccessibilityValue(isExpanded: false)",
            "testConnectionRecoveryResultAccessibilityLabelUsesSelectedLanguageAndTone",
            "connectionRecoveryResultAccessibilityLabel(",
            "Connection Recovery result. Status Ready. Connection details prepared.",
            "연결 복구 결과. 상태 준비됨. 연결 세부 정보가 준비되었습니다.",
            "接続の復旧結果。ステータス 準備完了。接続詳細を準備しました。",
            "连接恢复结果。状态 就绪。连接详情已准备好。",
            "Résultat de récupération de connexion. État Prêt. Détails de connexion préparés.",
            "testConnectionRecoveryHostWarningAccessibilityLabelUsesSelectedLanguageAndTone",
            "connectionRecoveryHostWarningAccessibilityLabel(",
            "Connection Recovery warning. Status Needs attention. This connection address is local-network only.",
            "연결 복구 경고. 상태 확인 필요. 이 연결 주소는 로컬 네트워크 전용입니다.",
            "接続の復旧警告。ステータス 確認が必要。この接続アドレスはローカルネットワーク専用です。",
            "连接恢复警告。状态 需要注意。此连接地址仅限本地网络。",
            "Avertissement de récupération de connexion. État Attention requise. Cette adresse de connexion est réservée au réseau local.",
            "testConnectionRecoverySaveBootstrapRelayAccessibilityValueUsesSelectedLanguage",
            "testConnectionRecoveryBootstrapAllocationTokenWarningUsesSelectedLanguage",
            "testBootstrapRelayAllocationTokenWarningClassifiesNonLocalEndpoints",
            "connectionRecoverySaveBootstrapRelayActionAccessibilityValue(\n                        endpoints: \"relay.example.test:43171\",\n                        allocationToken: \"token\"",
            "connectionRecoveryBootstrapAllocationTokenWarning(",
            "connectionRecoveryBootstrapAllocationTokenAccessibilityValue(",
            "bootstrapRelayEndpointsNeedAllocationToken(endpoint)",
            "Add an allocation token before using a non-local bootstrap relay.",
            "Missing token for non-local bootstrap relay",
            "로컬이 아닌 부트스트랩 릴레이를 사용하기 전에 할당 토큰을 추가하세요.",
            "非ローカルのブートストラップリレーを使用する前に割り当てトークンを追加してください。",
            "使用非本地引导中继前，请添加分配令牌。",
            "Ajoutez un jeton d’allocation avant d’utiliser un relais d’amorçage non local.",
            "connectionRecoverySaveBootstrapRelayActionAccessibilityValue(endpoints: \"   \")",
            "Will remove saved bootstrap relay",
            "저장된 부트스트랩 릴레이를 제거합니다",
            "保存済みブートストラップリレーを削除します",
            "将移除已保存的引导中继",
            "Supprimera le relais d’amorçage enregistré",
            "testConnectionRecoveryBootstrapRelayRemovalAccessibilityUsesSelectedLanguage",
            "removeSavedBootstrapRelayAccessibilityLabel(endpoints:",
            "cancelRemoveSavedBootstrapRelayAccessibilityLabel(endpoints:",
            "Remove bootstrap relay settings for relay.example.test:43171",
            "relay.example.test:43171의 부트스트랩 릴레이 설정 제거",
            "relay.example.test:43171 のブートストラップリレー設定を削除",
            "移除 relay.example.test:43171 的引导中继设置",
            "Supprimer les réglages du relais d’amorçage pour relay.example.test:43171",
            "testConnectionRecoverySaveConnectionAccessibilityValueExplainsInvalidInputs",
            "connectionRecoverySaveConnectionActionAccessibilityValue(host: \"relay.example.test\", port: \"43171\")",
            "connectionRecoverySaveConnectionActionAccessibilityValue(host: \"   \", port: \"43171\")",
            "connectionRecoverySaveConnectionActionAccessibilityValue(host: \"relay.example.test:43171\", port: \"43171\")",
            "connectionRecoverySaveConnectionActionAccessibilityValue(host: \"relay.example.test\", port: \"not-a-port\")",
        ),
        "macOS connection recovery private-overlay toggle accessibility regression",
    ))
    return failures


def check_activity_log_redaction() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        ACTIVITY_LOGS_SOURCE,
        (
            "self.diagnostic = sanitizedTechnicalDiagnostic(diagnostic)",
            "func sanitizedTechnicalDiagnostic(_ diagnostic: String?) -> String?",
            "Provider endpoint redacted.",
            "Sensitive technical detail redacted.",
            "providerEndpointDiagnosticPatterns",
            "sensitiveRouteDiagnosticPatterns",
            "relay_secret|relaySecret|route_secret|routeSecret|route_token|routeToken|pairing_secret|pairingSecret",
            "allocation_token|allocationToken|rs|rt|ri|rrn",
            "api/(?:tags|ps|pull|chat|show|v1)",
            "v1/(?:models|chat|chat/completions)",
        ),
        "macOS Activity technical-details endpoint redaction",
    ))
    failures.extend(missing_source_snippets(
        COMPANION_APP_MODEL_SOURCE,
        (
            "logs.insert(sanitizedCompanionLogMessage(message), at: 0)",
            "func sanitizedCompanionLogMessage(_ message: String) -> String",
            "companionLogRedactionPatterns",
            "relay_secret|relaySecret|route_secret|routeSecret|route_token|routeToken|pairing_secret|pairingSecret",
            "allocation_token|allocationToken|rs|rt|ri|rrn",
            "api/(?:tags|ps|pull|chat|show|v1)",
        ),
        "macOS companion log storage endpoint redaction",
    ))
    failures.extend(missing_source_snippets(
        ACTIVITY_LOGS_SOURCE,
        (
            "Image(systemName: tone.systemImage)",
            ".accessibilityHidden(true)",
            "logTechnicalDetailsAccessibilityLabel(summary: display.summary)",
            "logTechnicalDetailsAccessibilityValue(isExpanded: diagnosticsExpanded)",
            "logTechnicalDetailsAccessibilityHint(isExpanded: diagnosticsExpanded)",
            "func logTechnicalDetailsAccessibilityLabel(summary: String) -> String",
            "normalizedLogAccessibilitySummary(summary)",
            "normalizedLogAccessibilitySummaryFragment",
            "logAccessibilityTerminalPunctuation",
            "func logTechnicalDetailsAccessibilityValue(isExpanded: Bool) -> String",
            "func logTechnicalDetailsAccessibilityHint(isExpanded: Bool) -> String",
            "ForEach(Array(model.logs.enumerated()), id: \\.offset)",
            "position: index + 1",
            "totalCount: model.logs.count",
            "logRowAccessibilityLabel(",
            "summary: display.summary,",
            "position: position,",
            "totalCount: totalCount",
            ".accessibilityLabel(",
            "func logRowAccessibilityLabel(summary: String, tone: StatusTone) -> String",
            "func logRowAccessibilityLabel(summary: String, tone: StatusTone, position: Int, totalCount: Int) -> String",
            "activityLogListAccessibilityLabel()",
            "activityLogListAccessibilityValue(count: model.logs.count)",
            "func activityLogListAccessibilityLabel() -> String",
            "func activityLogListAccessibilityValue(count: Int) -> String",
            "func activityLogTone(for line: String) -> StatusTone",
            "func logToneAccessibilityStatus(_ tone: StatusTone) -> String",
            "Remote route ready:",
            "Remote route lease refreshed:",
            "Activity log",
            "%d activity items",
            "Activity item %@. Status %@.",
            "Activity item %d of %d. %@. Status %@.",
            "Technical details for %@",
            "Activity technical details expanded",
            "Activity technical details collapsed",
            "Collapse to hide activity technical details.",
            "Expand to show activity technical details.",
            "Trusted device %@",
            "Removed trust for %@",
            "trustedDeviceAuditLogName(",
        ),
        "macOS activity technical-details accessibility label",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "testActivityLogListAccessibilitySummaryUsesSelectedLanguage",
            "activityLogListAccessibilityLabel()",
            "activityLogListAccessibilityValue(count: 3)",
            "testActivityRouteSuccessLogRowsUseReadyTone",
            "activityLogTone(for: \"Remote route ready: relay.example.test:43171\")",
            "Activity item Connection details are ready. Status Ready.",
        ),
        "macOS activity route-success ready-tone regression",
    ))
    activity_logs_text = ACTIVITY_LOGS_SOURCE.read_text(encoding="utf-8", errors="replace")
    if ".accessibilityElement(children: .combine)" in activity_logs_text:
        failures.append(
            "apps/macos/LocalAgentBridgeApp/Sources/LogsView.swift: "
            "Activity rows with technical details must not merge disclosure controls."
        )
    return failures


def check_menu_bar_localization_helpers() -> list[str]:
    return [
        *missing_source_snippets(
            COMPANION_CHROME_SOURCE,
            (
                "struct MenuBarCommandTitles: Equatable",
                "func menuBarRuntimeStatusText(_ status: CompanionTransportStatus) -> String",
                "func menuBarRuntimeStatusAccessibilityLabel(_ status: CompanionTransportStatus) -> String",
                "func menuBarModelServiceStatusText(_ statuses: [CompanionProviderStatus]) -> String",
                "func menuBarModelServiceStatusAccessibilityLabel(_ statuses: [CompanionProviderStatus]) -> String",
                "func menuBarCommandTitles() -> MenuBarCommandTitles",
                "func menuBarOpenAetherLinkAccessibilityHint() -> String",
                "func menuBarQuitAccessibilityHint() -> String",
                "func pairingQRGenerationCommandTitle(hasActiveSession: Bool) -> String",
                "func modelProviderCheckActionAccessibilityValue() -> String",
                "func modelProviderCheckActionAccessibilityHint() -> String",
                "func modelListLoadActionAccessibilityValue() -> String",
                "func modelListLoadActionAccessibilityHint() -> String",
                "func refreshRuntimeDataActionAccessibilityValue() -> String",
                "func refreshRuntimeDataActionAccessibilityHint() -> String",
                "func inspectRuntimeHistoryActionAccessibilityValue() -> String",
                "func inspectRuntimeHistoryActionAccessibilityHint() -> String",
                "func inspectRuntimeMemoryActionAccessibilityValue() -> String",
                "func inspectRuntimeMemoryActionAccessibilityHint() -> String",
                "Runtime: %@",
                "Runtime status: %@",
                "Model service: %@",
                "Model service status: %@",
                "Open AetherLink",
                "Generate Pairing QR",
                "Generate New QR",
                "Load Models",
                "Open the AetherLink window and bring it to the front.",
                "Quit AetherLink Runtime.",
                "Check model provider availability through AetherLink Runtime.",
                "Load the installed local model list through AetherLink Runtime.",
            ),
            "macOS menu-bar localization helpers",
        ),
        *missing_source_snippets(
            APP_ENTRY_SOURCE,
            (
                """Button(NSLocalizedString("Check Model Providers", comment: "")) {
                    Task { await model.refreshBackendStatus() }
                }
                .keyboardShortcut("r", modifiers: [.command])
                .help(modelProviderCheckActionAccessibilityHint())
                .accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))
                .accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))""",
                "let commandTitles = menuBarCommandTitles()",
                "Text(menuBarRuntimeStatusText(model.transportState))",
                ".accessibilityLabel(Text(menuBarRuntimeStatusAccessibilityLabel(model.transportState)))",
                "Text(menuBarModelServiceStatusText(model.providerStatuses))",
                ".accessibilityLabel(Text(menuBarModelServiceStatusAccessibilityLabel(model.providerStatuses)))",
                "Button(commandTitles.openAetherLink)",
                ".help(menuBarOpenAetherLinkAccessibilityHint())",
                ".accessibilityHint(Text(menuBarOpenAetherLinkAccessibilityHint()))",
                """Button(commandTitles.refresh) {
                Task { await model.refreshBackendStatus() }
            }
            .help(modelProviderCheckActionAccessibilityHint())
            .accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))
            .accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))""",
                """Button(commandTitles.loadModels) {
                Task { await model.loadModels() }
            }
            .help(modelListLoadActionAccessibilityHint())
            .accessibilityValue(Text(modelListLoadActionAccessibilityValue()))
            .accessibilityHint(Text(modelListLoadActionAccessibilityHint()))""",
                "Button(pairingQRGenerationCommandTitle(hasActiveSession: model.pairingSession != nil))",
                "Button(commandTitles.quit)",
                ".help(menuBarQuitAccessibilityHint())",
                ".accessibilityHint(Text(menuBarQuitAccessibilityHint()))",
            ),
            "macOS menu-bar helper wiring",
        ),
        *missing_source_snippets(
            STATUS_VIEW_SOURCE,
            (
                ".accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))",
                ".accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))",
                ".accessibilityValue(Text(modelListLoadActionAccessibilityValue()))",
                ".accessibilityHint(Text(modelListLoadActionAccessibilityHint()))",
                ".help(refreshRuntimeDataActionAccessibilityHint())",
                ".accessibilityValue(Text(refreshRuntimeDataActionAccessibilityValue()))",
                ".accessibilityHint(Text(refreshRuntimeDataActionAccessibilityHint()))",
                ".help(inspectRuntimeHistoryActionAccessibilityHint())",
                ".accessibilityValue(Text(inspectRuntimeHistoryActionAccessibilityValue()))",
                ".accessibilityHint(Text(inspectRuntimeHistoryActionAccessibilityHint()))",
                ".help(inspectRuntimeMemoryActionAccessibilityHint())",
                ".accessibilityValue(Text(inspectRuntimeMemoryActionAccessibilityValue()))",
                ".accessibilityHint(Text(inspectRuntimeMemoryActionAccessibilityHint()))",
            ),
            "macOS quick action accessibility wiring",
        ),
        *missing_source_snippets(
            APP_CONTENT_SOURCE,
            (
                ".help(modelProviderCheckActionAccessibilityHint())",
                ".accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))",
                ".accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))",
                ".help(modelListLoadActionAccessibilityHint())",
                ".accessibilityValue(Text(modelListLoadActionAccessibilityValue()))",
                ".accessibilityHint(Text(modelListLoadActionAccessibilityHint()))",
            ),
            "macOS toolbar quick action accessibility wiring",
        ),
        *missing_source_snippets(
            LOCALIZATION_TEST_SOURCE,
            (
                "testMenuBarStatusAndCommandTitlesUseSelectedLanguage",
                "testMenuBarPairingQRCommandTitleTracksActiveSessionAndLanguage",
                "testMenuBarWindowAndQuitAccessibilityHintsUseSelectedLanguage",
                "testPrimaryActionsPrioritizePairingQRWhenNoTrustedDevicesExist",
                "testQuickActionAccessibilityUsesSelectedLanguage",
                "companionPrimaryActionOrder(trustedDeviceCount: 0)",
                "menuBarRuntimeStatusText(.advertising(serviceName: \"AetherLink\", port: 43170))",
                "menuBarRuntimeStatusAccessibilityLabel(.advertising(serviceName: \"AetherLink\", port: 43170))",
                "menuBarModelServiceStatusText([])",
                "menuBarModelServiceStatusAccessibilityLabel([])",
                "menuBarCommandTitles()",
                "pairingQRGenerationCommandTitle(hasActiveSession: true)",
                "menuBarOpenAetherLinkAccessibilityHint()",
                "menuBarQuitAccessibilityHint()",
                "modelProviderCheckActionAccessibilityHint()",
                "modelListLoadActionAccessibilityHint()",
                "refreshRuntimeDataActionAccessibilityValue()",
                "refreshRuntimeDataActionAccessibilityHint()",
                "inspectRuntimeHistoryActionAccessibilityValue()",
                "inspectRuntimeHistoryActionAccessibilityHint()",
                "inspectRuntimeMemoryActionAccessibilityValue()",
                "inspectRuntimeMemoryActionAccessibilityHint()",
            ),
            "macOS menu-bar localization tests",
        ),
    ]


def check_provider_status_redaction() -> list[str]:
    return missing_source_snippets(
        STATUS_VIEW_SOURCE,
        (
            "providerStatusDiagnosticDetail(",
            "sanitizedTechnicalDiagnostic(message)",
            "sanitizedProviderStatusCode",
            "readinessRowAccessibilityLabel(",
            "func readinessRowAccessibilityLabel(title: String, status: String, detail: String) -> String",
            "Readiness %@. Status %@. %@",
            "Readiness item",
            "No readiness details",
            "runtimeOverviewAccessibilityLabel(",
            "func runtimeOverviewAccessibilityLabel(title: String, status: String, detail: String, footnote: String) -> String",
            "Runtime overview %@. Status %@. %@ %@",
            "statusCardAccessibilityLabel(",
            "func statusCardAccessibilityLabel(title: String, value: String, detail: String) -> String",
            "Status %@. Current state %@. %@",
            "modelRowAccessibilityLabel(",
            "func modelRowAccessibilityLabel(",
            "Model %@. ID %@. Type %@. Provider %@. Source %@. State %@. Size %@",
            "modelGroupHeaderAccessibilityLabel(title: group.title, count: group.countText)",
            ".accessibilityAddTraits(.isHeader)",
            "func modelGroupHeaderAccessibilityLabel(title: String, count: String) -> String",
            "Model section %@. %@",
            "providerStatusTechnicalDetailsAccessibilityLabel(providerName: status.name)",
            "providerStatusTechnicalDetailsAccessibilityValue(isExpanded: diagnosticsExpanded)",
            "providerStatusTechnicalDetailsAccessibilityHint(isExpanded: diagnosticsExpanded)",
            "func providerStatusTechnicalDetailsAccessibilityLabel(providerName: String) -> String",
            "func providerStatusTechnicalDetailsAccessibilityValue(isExpanded: Bool) -> String",
            "func providerStatusTechnicalDetailsAccessibilityHint(isExpanded: Bool) -> String",
            "Model provider",
            "Provider details expanded",
            "Provider details collapsed",
            "Collapse to hide provider details.",
            "Expand to show provider details.",
            'lines.append("code=\\(code)")',
            'lines.append("retryable=\\(retryable ? "true" : "false")")',
            "providerStatusPillAccessibilityLabel(",
            "func providerStatusPillAccessibilityLabel(providerName: String, status: String) -> String",
            "Provider %@ status %@",
            "providerStatusRowAccessibilityLabel(",
            "func providerStatusRowAccessibilityLabel(providerName: String, status: String, detail: String) -> String",
            "Provider %@. Status %@. %@",
            "Image(systemName: status.systemImage)",
            ".accessibilityHidden(true)",
        ),
        "macOS Status readiness and Model Providers decorative-icon accessibility labels",
    ) + missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "testModelGroupHeaderAccessibilityLabelUsesSelectedLanguage",
            "testReadinessRowAccessibilityLabelUsesTitleStatusDetailAndFallbacks",
            "testProviderStatusRowAccessibilityLabelUsesProviderContext",
            "No readiness details",
            "providerStatusRowAccessibilityLabel(",
            "No provider details",
        ),
        "macOS Status model group and provider row accessibility tests",
    )


def check_trusted_device_identity_display() -> list[str]:
    failures = missing_source_snippets(
        TRUSTED_DEVICES_VIEW_SOURCE,
        (
            "trustedDeviceKeyFingerprint(device.publicKeyBase64)",
            "func trustedDeviceKeyFingerprint(_ publicKeyBase64: String) -> String",
            "SHA256.hash(data: keyData)",
            "Key fingerprint %@",
            ".accessibilityHidden(true)",
            "trustedDevicePairingAccessibilitySummary(pairedAt: pairedAt, deviceID: deviceID)",
            "func trustedDevicePairingAccessibilitySummary(pairedAt: Date?, deviceID: String) -> String",
            "guard let pairedAt else",
            "Device ID ending %@",
            "Paired %@. Device ID ending %@",
            "let displayName = trustedDeviceDisplayName(name)",
            "func trustedDeviceDisplayName(_ name: String?) -> String",
            "Text(displayName)",
            "trustedDeviceRowAccessibilityLabel(",
            "func trustedDeviceRowAccessibilityLabel(name: String, pairedAt: Date?, deviceID: String, keyFingerprint: String) -> String",
            "Pairing details unavailable.",
            "Trusted device %@. %@. Key fingerprint %@",
            "trustedDeviceRemovalMessage(for: pendingRemovalDevice)",
            "%@ will need to pair again before it can use AetherLink Runtime. Key fingerprint %@",
            ".accessibilityLabel(Text(trustedDeviceConfirmRemoveAccessibilityLabel(for: pendingRemovalDevice)))",
            "func trustedDeviceConfirmRemoveAccessibilityLabel(for device: TrustedDevice?) -> String",
            "Confirm removing trust for %@. Key fingerprint %@",
            'Button(NSLocalizedString("Cancel", comment: ""), role: .cancel)',
            ".accessibilityLabel(Text(trustedDeviceCancelRemoveAccessibilityLabel(for: pendingRemovalDevice)))",
            "func trustedDeviceCancelRemoveAccessibilityLabel(for device: TrustedDevice?) -> String",
            "Cancel removing trust for %@. Key fingerprint %@",
            "trustedDeviceRemoveAccessibilityLabel(name: displayName, keyFingerprint: keyFingerprint)",
            "func trustedDeviceRemoveAccessibilityLabel(name: String, keyFingerprint: String) -> String",
            "Remove trust for %@. Key fingerprint %@",
            ".accessibilityHint(Text(trustedDeviceRemoveAccessibilityHint(name: displayName)))",
            "func trustedDeviceRemoveAccessibilityHint(name: String) -> String",
            "After removal, %@ must pair again before it can use AetherLink Runtime.",
            "trustedDeviceRefreshActionAccessibilityHint()",
            "func trustedDeviceRefreshActionAccessibilityHint() -> String",
            "trustedDeviceRefreshActionAccessibilityValue()",
            "func trustedDeviceRefreshActionAccessibilityValue() -> String",
            "Refresh trusted devices from AetherLink Runtime.",
        ),
        "macOS trusted-device identity display",
    )
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "testTrustedDeviceConfirmRemoveActionAccessibilityLabelUsesDeviceContext",
            "testTrustedDeviceCancelRemoveActionAccessibilityLabelUsesDeviceContext",
            "trustedDevicePairingAccessibilitySummary(pairedAt: nil, deviceID: \" ice-1 \")",
            "pairedAt: nil,\n                        deviceID: \" ice-1 \",",
            "fallbackPairingSummary",
            "trustedDeviceDisplayName(\"   \")",
            "fallbackDisplayName",
            "testTrustedDeviceRemoveButtonAccessibilityHintUsesSelectedLanguage",
            "trustedDeviceRemoveAccessibilityHint(name: \" Pixel \")",
            "trustedDeviceCancelRemoveAccessibilityLabel(",
        ),
        "macOS trusted-device removal dialog localization tests",
    ))
    return failures


def check_remote_route_preparation_issue_display() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        REMOTE_ROUTE_PREPARATION_COPY_SOURCE,
        (
            "func remoteRoutePreparationIssueText(_ issue: CompanionRemoteRoutePreparationIssue) -> String",
            "Connection details for %@ cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.",
            "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR.",
        ),
        "macOS remote-route preparation issue copy",
    ))
    failures.extend(missing_source_snippets(
        SOURCE_ROOT / "PairingView.swift",
        (
            "model.remoteRoutePreparationIssue",
            "remoteRoutePreparationIssueText(issue)",
        ),
        "macOS Pairing QR preparation issue display",
    ))
    failures.extend(missing_source_snippets(
        SOURCE_ROOT / "PairingView.swift",
        (
            "let qrImage = pairingQRCodeImage(from: qrPayload)",
            "let isAvailable = qrImage != nil",
            "QRCodeView(image: qrImage)",
            "func pairingQRCodeImage(from text: String) -> NSImage?",
            "pairingQRCodeAccessibilityValue(isExpired: isExpired, isAvailable: isAvailable)",
            "func pairingQRCodeAccessibilityValue(isExpired: Bool, isAvailable: Bool = true) -> String",
            "Pairing QR code unavailable",
            "pairingQRCodeAccessibilityHint(remoteRouteExpiresAt:",
            "pairingQRRemoteRouteExpirationText(",
        ),
        "macOS Pairing QR availability and remote-route accessibility state",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "unavailableValue",
            "pairingQRCodeAccessibilityValue(isExpired: false, isAvailable: false)",
            "pairingQRCodeAccessibilityValue(isExpired: true, isAvailable: false)",
            "Pairing QR code unavailable",
            "페어링 QR 코드를 사용할 수 없음",
            "ペアリング QR コードを利用できません",
            "配对 QR 码不可用",
            "QR code de jumelage indisponible",
        ),
        "macOS Pairing QR unavailable accessibility regression",
    ))
    failures.extend(missing_source_snippets(
        STATUS_VIEW_SOURCE,
        (
            "model.remoteRoutePreparationIssue",
            "remoteRoutePreparationIssueText(issue)",
            "Connection details need attention",
            "No cross-network connection details are saved yet. Nearby pairing still works. For another network, use a reachable relay, VPN, or tunnel before generating the latest QR.",
        ),
        "macOS Status route preparation issue display",
    ))
    return failures


def check_runtime_inspector_close_button_accessibility() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        STATUS_VIEW_SOURCE,
        (
            'Text(NSLocalizedString("Close", comment: ""))',
            '.accessibilityLabel(Text(NSLocalizedString("Refresh Runtime History Inspector", comment: "")))',
            '.accessibilityLabel(Text(NSLocalizedString("Close Runtime History Inspector", comment: "")))',
            '.accessibilityLabel(Text(NSLocalizedString("Refresh Runtime Memory Inspector", comment: "")))',
            '.accessibilityLabel(Text(NSLocalizedString("Close Runtime Memory Inspector", comment: "")))',
            "runtimeChatSessionSelectionAccessibilityValue(isSelected: isSelected)",
            "runtimeTranscriptPreviewLoadAccessibilityHint()",
            "runtimeTranscriptPreviewLoadAccessibilityLabel(title: titleText)",
            'func runtimeTranscriptPreviewLoadAccessibilityLabel(title: String) -> String',
            'func runtimeChatSessionSelectionAccessibilityValue(isSelected: Bool) -> String',
            'func runtimeTranscriptPreviewLoadAccessibilityHint() -> String',
            'NSLocalizedString("Load transcript preview for %@", comment: "")',
            'NSLocalizedString("Load this runtime-owned transcript preview.", comment: "")',
        ),
        "macOS runtime inspector close-button accessibility labels",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            'NSLocalizedString("Close Runtime History Inspector", comment: "")',
            'NSLocalizedString("Close Runtime Memory Inspector", comment: "")',
            'NSLocalizedString("Refresh Runtime History Inspector", comment: "")',
            'NSLocalizedString("Refresh Runtime Memory Inspector", comment: "")',
            "Actualiser l’inspecteur d’historique du runtime",
            "Actualiser l’inspecteur de mémoire du runtime",
            "Fermer l’inspecteur d’historique du runtime",
            "Fermer l’inspecteur de mémoire du runtime",
            "runtimeTranscriptPreviewLoadAccessibilityLabel(title:",
            "Load transcript preview for Release planning",
            "Charger l’aperçu de la transcription pour Planification de version",
            "Charger l’aperçu de la transcription pour Chat sans titre",
            'runtimeChatSessionSelectionAccessibilityValue(isSelected: true)',
            'runtimeChatSessionSelectionAccessibilityValue(isSelected: false)',
            "Load this runtime-owned transcript preview.",
            "이 런타임 소유 대화 미리보기를 불러옵니다.",
            "このランタイム所有の会話プレビューを読み込みます。",
            "加载这个由运行时拥有的对话预览。",
            "Charger cet aperçu de transcription détenu par le runtime.",
        ),
        "macOS runtime inspector close-button localization tests",
    ))
    return failures


def check_runtime_transcript_reasoning_preview() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        STATUS_VIEW_SOURCE,
        (
            "RuntimeTranscriptReasoningBlock(reasoning: reasoning)",
            "runtimeTranscriptReasoningDisplayPolicy(",
            "runtimeTranscriptReasoningPreviewMaxLines = 3",
            "runtimeTranscriptReasoningSingleLinePreviewLimit = 180",
            "runtimeTranscriptReasoningCollapsedOpacity",
            "runtimeTranscriptReasoningExpandedOpacity",
            "runtimeTranscriptReasoningToggleTitle(isExpanded:",
            "runtimeTranscriptReasoningToggleAccessibilityValue(isExpanded:",
            "runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded:",
        ),
        "macOS runtime transcript reasoning preview and toggle wiring",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "testRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded",
            "testRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs",
            "runtimeTranscriptReasoningToggleTitle(isExpanded: false)",
            "runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded: true)",
            "runtimeTranscriptReasoningDisplayPolicy(",
            "runtimeTranscriptReasoningNeedsExpansion(longParagraph)",
        ),
        "macOS runtime transcript reasoning preview localization tests",
    ))
    return failures


def check_runtime_history_message_count_clamp() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        APP_LOCALIZATION_SOURCE,
        (
            "func localizedRuntimeChatMessageCount(_ count: Int) -> String",
            "localizedCount(max(0, count), singularKey: \"1 message\", pluralKey: \"%d messages\")",
        ),
        "macOS runtime history message-count clamp helper",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "localizedRuntimeChatMessageCount(-3)",
            "\"0 messages\"",
            "runtimeChatSessionAccessibilityLabel(",
            "\"Chat session Damaged count. Status Active. Model ollama:llama3.1:8b. 0 messages. Updated Jun 29, 2026 at 2:00 AM.\"",
        ),
        "macOS runtime history message-count clamp localization tests",
    ))
    return failures


def check_runtime_history_card_summary() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        APP_LOCALIZATION_SOURCE,
        (
            "func localizedRuntimeSavedChatSessionCount(_ count: Int) -> String",
            "localizedCount(max(0, count), singularKey: \"1 active chat\", pluralKey: \"%d active chats\")",
            "localizedCount(max(0, count), singularKey: \"1 archived chat\", pluralKey: \"%d archived chats\")",
            "localizedCount(max(0, count), singularKey: \"1 saved chat\", pluralKey: \"%d saved chats\")",
        ),
        "macOS runtime history saved/active/archived count helpers",
    ))
    failures.extend(missing_source_snippets(
        STATUS_VIEW_SOURCE,
        (
            "runtimeHistoryCardValue(",
            "runtimeHistoryCardDetail(",
            "RuntimeHistoryInspectorSummary(",
            "sessions.filter { $0.status != \"archived\" }.count",
            "sessions.filter { $0.status == \"archived\" }.count",
            "private struct RuntimeHistoryInspectorSummary: View",
            "runtimeHistoryInspectorSummaryAccessibilityLabel(value: valueText, detail: detailText)",
            "func runtimeHistoryInspectorSummaryAccessibilityLabel(value: String, detail: String) -> String",
            "NSLocalizedString(\"Runtime history summary. %@. %@\", comment: \"\")",
            "localizedRuntimeSavedChatSessionCount(max(0, activeCount) + max(0, archivedCount))",
            "NSLocalizedString(\"No runtime chat sessions are stored on AetherLink Runtime.\", comment: \"\")",
            "NSLocalizedString(\"Runtime context: %@. Archived: %@.\", comment: \"\")",
            "runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: createdAtText)",
            "func runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: String) -> String",
            "NSLocalizedString(\"Created %@\", comment: \"\")",
            "NSLocalizedString(\"Unknown creation time\", comment: \"\")",
        ),
        "macOS runtime history card saved/archived summary wiring",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "localizedRuntimeSavedChatSessionCount(3)",
            "localizedRuntimeSavedChatSessionCount(-3)",
            "runtimeHistoryCardValue(activeCount: 2, archivedCount: 1)",
            "runtimeHistoryCardDetail(activeCount: 2, archivedCount: 1)",
            "\"Runtime context: 2 active chats. Archived: 1 archived chat.\"",
            "\"런타임 컨텍스트: 활성 채팅 2개. 보관됨: 보관된 채팅 1개.\"",
            "\"ランタイムコンテキスト: アクティブなチャット 2 件。アーカイブ済み: アーカイブ済みチャット 1 件。\"",
            "\"运行时上下文：2 个活跃聊天。已归档：1 个已归档聊天。\"",
            "\"Contexte du runtime : 2 chats actifs. Archivés : 1 chat archivé.\"",
            "runtimeHistoryInspectorSummaryAccessibilityLabel(",
            "\"Runtime history summary. 3 saved chats. Runtime context: 2 active chats. Archived: 1 archived chat.\"",
            "runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: \"Jun 29, 2026 at 2:00 AM\")",
            "\"Created Jun 29, 2026 at 2:00 AM\"",
            "\"생성 알 수 없는 생성 시간\"",
            "\"作成 不明な作成時刻\"",
            "\"创建 未知创建时间\"",
            "\"Créé Heure de création inconnue\"",
        ),
        "macOS runtime history card summary localization tests",
    ))
    return failures


def check_runtime_memory_card_summary() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        APP_LOCALIZATION_SOURCE,
        (
            "func localizedRuntimeSavedMemoryCount(_ count: Int) -> String",
            "localizedCount(max(0, count), singularKey: \"1 saved memory note\", pluralKey: \"%d saved memory notes\")",
            "localizedCount(max(0, count), singularKey: \"1 enabled memory note\", pluralKey: \"%d enabled memory notes\")",
            "localizedCount(max(0, count), singularKey: \"1 paused memory note\", pluralKey: \"%d paused memory notes\")",
        ),
        "macOS runtime memory saved/enabled/paused count helpers",
    ))
    failures.extend(missing_source_snippets(
        STATUS_VIEW_SOURCE,
        (
            "runtimeMemoryCardValue(",
            "runtimeMemoryCardDetail(",
            "RuntimeMemoryInspectorSummary(",
            "entries.filter { $0.enabled }.count",
            "entries.filter { !$0.enabled }.count",
            "private struct RuntimeMemoryInspectorSummary: View",
            "runtimeMemoryInspectorSummaryAccessibilityLabel(value: valueText, detail: detailText)",
            "func runtimeMemoryInspectorSummaryAccessibilityLabel(value: String, detail: String) -> String",
            "NSLocalizedString(\"Runtime memory summary. %@. %@\", comment: \"\")",
            "localizedRuntimeSavedMemoryCount(max(0, enabledCount) + max(0, pausedCount))",
            "NSLocalizedString(\"No runtime memory notes are stored on AetherLink Runtime.\", comment: \"\")",
            "NSLocalizedString(\"Runtime context: %@. Paused: %@.\", comment: \"\")",
            "createdAt: localizedCompanionDateString(from: entry.createdAt)",
            "func runtimeMemoryEntryAccessibilityLabel(content: String, status: String, createdAt: String, updatedAt: String) -> String",
            "NSLocalizedString(\"Memory note %@. Status %@. Created %@. Updated %@.\", comment: \"\")",
        ),
        "macOS runtime memory card saved/paused summary wiring",
    ))
    failures.extend(missing_source_snippets(
        LOCALIZATION_TEST_SOURCE,
        (
            "localizedRuntimeSavedMemoryCount(3)",
            "localizedRuntimeSavedMemoryCount(-3)",
            "runtimeMemoryCardValue(enabledCount: 2, pausedCount: 1)",
            "runtimeMemoryCardDetail(enabledCount: 2, pausedCount: 1)",
            "\"Runtime context: 2 enabled memory notes. Paused: 1 paused memory note.\"",
            "\"런타임 컨텍스트: 사용 중인 메모리 노트 2개. 일시 중지: 일시 중지된 메모리 노트 1개.\"",
            "\"ランタイムコンテキスト: 有効なメモリノート 2 件。一時停止: 一時停止中のメモリノート 1 件。\"",
            "\"运行时上下文：2 条已启用记忆。已暂停：1 条已暂停记忆。\"",
            "\"Contexte du runtime : 2 notes mémoire activées. En pause : 1 note mémoire suspendue.\"",
            "runtimeMemoryInspectorSummaryAccessibilityLabel(",
            "\"Runtime memory summary. 3 saved memory notes. Runtime context: 2 enabled memory notes. Paused: 1 paused memory note.\"",
            "createdAt: \"Jun 29, 2026 at 12:50 AM\"",
            "\"Memory note Prefer concise answers. Status Enabled. Created Jun 29, 2026 at 12:50 AM. Updated Jun 29, 2026 at 1:00 AM.\"",
        ),
        "macOS runtime memory card summary localization tests",
    ))
    return failures


def main() -> int:
    failures: list[str] = []
    locale_keys: dict[str, list[str]] = {}
    locale_values: dict[str, dict[str, str]] = {}

    for locale in LOCALES:
        path = strings_path(locale)
        relative_path = path.relative_to(ROOT)

        if not path.exists():
            failures.append(f"{relative_path}: missing")
            continue

        lint_failure = lint_with_plutil(path)
        if lint_failure is not None:
            failures.append(f"{relative_path}: {lint_failure}")

        entries, parse_failures = parse_entries(path)
        for parse_failure in parse_failures:
            failures.append(f"{relative_path}: {parse_failure}")

        keys = entry_keys(entries)
        duplicates = duplicate_keys(keys)
        if duplicates:
            failures.append(f"{relative_path}: duplicate keys {duplicates}")

        stale_keys = [key for key in FORBIDDEN_STALE_KEYS if key in keys]
        if stale_keys:
            failures.append(f"{relative_path}: stale localization keys {stale_keys}")

        locale_keys[locale] = keys
        locale_values[locale] = dict(entries)
        failures.extend(release_copy_value_failures(locale, locale_values[locale], relative_path))

    base_keys = locale_keys.get(BASE_LOCALE)
    if base_keys is None:
        failures.append(f"{BASE_LOCALE}.lproj/Localizable.strings: base locale unavailable")
    else:
        base_key_set = set(base_keys)
        missing_source_keys: dict[str, tuple[Path, int]] = {}
        for key, relative_path, line_number in source_localized_keys():
            if key not in base_key_set and key not in missing_source_keys:
                missing_source_keys[key] = (relative_path, line_number)

        for key, (relative_path, line_number) in missing_source_keys.items():
            failures.append(
                f"{relative_path}:{line_number}: NSLocalizedString key missing from "
                f"{strings_path(BASE_LOCALE).relative_to(ROOT)}: {key!r}"
            )

        for locale in LOCALES:
            if locale == BASE_LOCALE or locale not in locale_keys:
                continue

            keys = locale_keys[locale]
            if keys != base_keys:
                missing = [key for key in base_keys if key not in keys]
                extra = [key for key in keys if key not in base_keys]
                failures.append(
                    f"{strings_path(locale).relative_to(ROOT)}: key order/parity mismatch "
                    f"(missing={missing}, extra={extra})"
                )

            base_values = locale_values[BASE_LOCALE]
            values = locale_values[locale]
            for key in base_keys:
                if key not in values:
                    continue

                base_placeholders = format_placeholders(base_values[key])
                locale_placeholders = format_placeholders(values[key])
                if locale_placeholders != base_placeholders:
                    failures.append(
                        f"{strings_path(locale).relative_to(ROOT)}: format placeholder mismatch "
                        f"for {key!r} (base={base_placeholders}, locale={locale_placeholders})"
                    )

        for key in (
            REQUIRED_LANGUAGE_KEYS
            + REQUIRED_APPEARANCE_KEYS
            + REQUIRED_CONNECTION_SAFETY_KEYS
            + REQUIRED_ACTIVITY_REDACTION_KEYS
            + REQUIRED_TRUSTED_DEVICE_KEYS
            + REQUIRED_REMOTE_ROUTE_PREPARATION_KEYS
            + REQUIRED_CONNECTION_RECOVERY_ACCESSIBILITY_KEYS
            + REQUIRED_RUNTIME_REASONING_KEYS
            + REQUIRED_RUNTIME_HISTORY_KEYS
        ):
            if key not in base_key_set:
                failures.append(f"{strings_path(BASE_LOCALE).relative_to(ROOT)}: missing app key {key!r}")

    failures.extend(check_app_language_selector())
    failures.extend(check_app_appearance_selector())
    failures.extend(check_app_appearance_wiring())
    failures.extend(check_companion_page_header_accessibility())
    failures.extend(check_companion_panel_header_accessibility())
    failures.extend(check_companion_empty_state_accessibility())
    failures.extend(raw_swiftui_visible_literal_matcher_self_test_failures())
    failures.extend(check_no_raw_swiftui_visible_literals())
    failures.extend(check_no_parenthetical_plural_resources())
    failures.extend(check_remote_connection_destructive_confirmation())
    failures.extend(check_activity_log_redaction())
    failures.extend(check_menu_bar_localization_helpers())
    failures.extend(check_provider_status_redaction())
    failures.extend(check_trusted_device_identity_display())
    failures.extend(check_remote_route_preparation_issue_display())
    failures.extend(check_runtime_inspector_close_button_accessibility())
    failures.extend(check_runtime_transcript_reasoning_preview())
    failures.extend(check_runtime_history_message_count_clamp())
    failures.extend(check_runtime_history_card_summary())
    failures.extend(check_runtime_memory_card_summary())

    if failures:
        print("macOS localization check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"macOS localization parity OK for {len(LOCALES)} locale(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
