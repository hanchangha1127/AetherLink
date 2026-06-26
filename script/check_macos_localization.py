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
STATUS_VIEW_SOURCE = SOURCE_ROOT / "StatusView.swift"
TRUSTED_DEVICES_VIEW_SOURCE = SOURCE_ROOT / "TrustedDevicesView.swift"
REMOTE_RELAY_ROUTE_PANEL_SOURCE = SOURCE_ROOT / "RemoteRelayRoutePanel.swift"
REMOTE_ROUTE_PREPARATION_COPY_SOURCE = SOURCE_ROOT / "RemoteRoutePreparationCopy.swift"
ACTIVITY_LOGS_SOURCE = SOURCE_ROOT / "LogsView.swift"
COMPANION_APP_MODEL_SOURCE = (
    ROOT / "apps" / "macos" / "CompanionCore" / "Sources" / "CompanionAppModel.swift"
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
    "Disable saved connection details?",
    "Saved connection details will be removed. Devices on another network may need a fresh pairing QR before they can reconnect.",
)
REQUIRED_ACTIVITY_REDACTION_KEYS = (
    "Provider endpoint redacted.",
    "Sensitive technical detail redacted.",
)
REQUIRED_TRUSTED_DEVICE_KEYS = (
    "Key fingerprint %@",
    "%@ will need to pair again before it can use AetherLink Runtime. Key fingerprint %@",
    "Selected device",
)
REQUIRED_REMOTE_ROUTE_PREPARATION_KEYS = (
    "AetherLink could not get connection details from the route service. Check Advanced Connection Setup, then generate a fresh QR.",
    "Connection details for %@ cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.",
    "Connection details cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.",
    "Connection details for %@ could not be prepared automatically. Check Advanced Connection Setup, then generate a fresh QR.",
    "Connection details could not be prepared automatically. Check Advanced Connection Setup, then generate a fresh QR.",
    "Connection details need a secure connection secret before they can be included in a QR.",
    "Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.",
    "Connection failed. Check Advanced Connection Setup, then generate a fresh QR.",
)
REQUIRED_RELEASE_COPY_VALUES = {
    "en": {
        "Generated automatically if blank": "Created automatically if left blank",
        "Rotate Secret": "Refresh Key",
        "Technical Details": "Details",
        "Provider endpoint redacted.": "Provider address hidden.",
        "Advanced connection setup needs attention.": "Connection Recovery needs attention.",
        "Advanced Connection Setup": "Connection Recovery",
        "Connection Setup": "Recovery Details",
        "Connection setup secret": "Protected connection key",
        "Connection setup secret regenerated.": "Protected connection key refreshed.",
        "Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.": (
            "Connection through %@ failed. Check Connection Recovery, then generate a fresh QR."
        ),
    },
    "ko": {
        "Generated automatically if blank": "비워두면 자동으로 생성됩니다",
        "Rotate Secret": "키 새로 고침",
        "Technical Details": "세부 정보",
        "Provider endpoint redacted.": "제공자 주소가 숨겨졌습니다.",
        "Advanced connection setup needs attention.": "연결 복구 확인이 필요합니다.",
        "Advanced Connection Setup": "연결 복구",
        "Connection Setup": "복구 세부 정보",
        "Connection setup secret": "보호된 연결 키",
        "Connection setup secret regenerated.": "보호된 연결 키를 새로 고쳤습니다.",
        "Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.": (
            "%@을(를) 통한 연결에 실패했습니다. 연결 복구를 확인한 뒤 새 QR을 생성하세요."
        ),
    },
    "ja": {
        "Generated automatically if blank": "空欄の場合は自動で作成されます",
        "Rotate Secret": "キーを更新",
        "Technical Details": "詳細",
        "Provider endpoint redacted.": "プロバイダーのアドレスは非表示です。",
        "Advanced connection setup needs attention.": "接続の復旧に確認が必要です。",
        "Advanced Connection Setup": "接続の復旧",
        "Connection Setup": "復旧の詳細",
        "Connection setup secret": "保護された接続キー",
        "Connection setup secret regenerated.": "保護された接続キーを更新しました。",
        "Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.": (
            "%@ 経由の接続に失敗しました。接続の復旧を確認してから、新しい QR を生成してください。"
        ),
    },
    "zh-Hans": {
        "Generated automatically if blank": "留空则自动创建",
        "Rotate Secret": "刷新密钥",
        "Technical Details": "详情",
        "Provider endpoint redacted.": "提供方地址已隐藏。",
        "Advanced connection setup needs attention.": "连接恢复需要检查。",
        "Advanced Connection Setup": "连接恢复",
        "Connection Setup": "恢复详情",
        "Connection setup secret": "受保护的连接密钥",
        "Connection setup secret regenerated.": "已刷新受保护的连接密钥。",
        "Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.": (
            "通过 %@ 的连接失败。请检查连接恢复，然后生成新的二维码。"
        ),
    },
    "fr": {
        "Generated automatically if blank": "Créée automatiquement si le champ est vide",
        "Rotate Secret": "Actualiser la clé",
        "Technical Details": "Détails",
        "Provider endpoint redacted.": "Adresse du fournisseur masquée.",
        "Advanced connection setup needs attention.": "La récupération de connexion demande une vérification.",
        "Advanced Connection Setup": "Récupération de connexion",
        "Connection Setup": "Détails de récupération",
        "Connection setup secret": "Clé de connexion protégée",
        "Connection setup secret regenerated.": "Clé de connexion protégée actualisée.",
        "Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.": (
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
    \s*\(\s*"
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
    )

    return [
        *missing_source_snippets(APP_ENTRY_SOURCE, app_entry_snippets, "macOS app appearance wiring"),
        *missing_source_snippets(APP_CONTENT_SOURCE, content_view_snippets, "macOS sidebar appearance wiring"),
    ]


def check_no_raw_swiftui_visible_literals() -> list[str]:
    failures: list[str] = []

    for path in sorted(SOURCE_ROOT.glob("*.swift")):
        relative_path = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if RAW_SWIFTUI_VISIBLE_LITERAL_RE.search(line):
                failures.append(
                    f"{relative_path}:{line_number}: visible SwiftUI text must use "
                    "NSLocalizedString so the in-app language setting applies."
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
    return missing_source_snippets(
        REMOTE_RELAY_ROUTE_PANEL_SOURCE,
        (
            "@State private var isDisableConnectionConfirmationPresented = false",
            "isDisableConnectionConfirmationPresented = true",
            '.confirmationDialog(\n            NSLocalizedString("Disable saved connection details?", comment: "")',
            "model.clearDevelopmentRelay()",
            'Button(NSLocalizedString("Disable Connection", comment: ""), role: .destructive)',
            'Button(NSLocalizedString("Cancel", comment: ""), role: .cancel)',
            'Text(NSLocalizedString("Saved connection details will be removed. Devices on another network may need a fresh pairing QR before they can reconnect.", comment: ""))',
        ),
        "macOS remote connection destructive confirmation",
    )


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
            "relay_secret|route_secret|route_token|pairing_secret",
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
            "relay_secret|route_secret|route_token|pairing_secret",
            "api/(?:tags|ps|pull|chat|show|v1)",
        ),
        "macOS companion log storage endpoint redaction",
    ))
    return failures


def check_provider_status_redaction() -> list[str]:
    return missing_source_snippets(
        STATUS_VIEW_SOURCE,
        (
            "providerStatusDiagnosticDetail(",
            "sanitizedTechnicalDiagnostic(message)",
            "sanitizedProviderStatusCode",
            'lines.append("code=\\(code)")',
            'lines.append("retryable=\\(retryable ? "true" : "false")")',
        ),
        "macOS Model Providers technical-details endpoint redaction",
    )


def check_trusted_device_identity_display() -> list[str]:
    return missing_source_snippets(
        TRUSTED_DEVICES_VIEW_SOURCE,
        (
            "trustedDeviceKeyFingerprint(device.publicKeyBase64)",
            "func trustedDeviceKeyFingerprint(_ publicKeyBase64: String) -> String",
            "SHA256.hash(data: keyData)",
            "Key fingerprint %@",
            "trustedDeviceRemovalMessage(for: pendingRemovalDevice)",
            "%@ will need to pair again before it can use AetherLink Runtime. Key fingerprint %@",
        ),
        "macOS trusted-device identity display",
    )


def check_remote_route_preparation_issue_display() -> list[str]:
    failures: list[str] = []
    failures.extend(missing_source_snippets(
        REMOTE_ROUTE_PREPARATION_COPY_SOURCE,
        (
            "func remoteRoutePreparationIssueText(_ issue: CompanionRemoteRoutePreparationIssue) -> String",
            "Connection details for %@ cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.",
            "Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.",
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
        STATUS_VIEW_SOURCE,
        (
            "model.remoteRoutePreparationIssue",
            "remoteRoutePreparationIssueText(issue)",
            "Connection details need attention",
        ),
        "macOS Status route preparation issue display",
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
        ):
            if key not in base_key_set:
                failures.append(f"{strings_path(BASE_LOCALE).relative_to(ROOT)}: missing app key {key!r}")

    failures.extend(check_app_language_selector())
    failures.extend(check_app_appearance_selector())
    failures.extend(check_app_appearance_wiring())
    failures.extend(check_no_raw_swiftui_visible_literals())
    failures.extend(check_no_parenthetical_plural_resources())
    failures.extend(check_remote_connection_destructive_confirmation())
    failures.extend(check_activity_log_redaction())
    failures.extend(check_provider_status_redaction())
    failures.extend(check_trusted_device_identity_display())
    failures.extend(check_remote_route_preparation_issue_display())

    if failures:
        print("macOS localization check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"macOS localization parity OK for {len(LOCALES)} locale(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
