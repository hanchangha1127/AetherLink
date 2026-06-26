#!/usr/bin/env python3
"""Check Android string resource locale parity, key order, and placeholders."""

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ANDROID_ROOT = ROOT / "apps" / "android"
ANDROID_APP_ROOT = ANDROID_ROOT / "app"
RUNTIME_UI_STATE_SOURCE = (
    ANDROID_APP_ROOT
    / "src"
    / "main"
    / "java"
    / "com"
    / "localagentbridge"
    / "android"
    / "runtime"
    / "RuntimeUiState.kt"
)
RUNTIME_LOCAL_STORE_SOURCE = (
    ANDROID_APP_ROOT
    / "src"
    / "main"
    / "java"
    / "com"
    / "localagentbridge"
    / "android"
    / "runtime"
    / "RuntimeLocalStore.kt"
)
MAIN_ACTIVITY_SOURCE = (
    ANDROID_APP_ROOT
    / "src"
    / "main"
    / "java"
    / "com"
    / "localagentbridge"
    / "android"
    / "MainActivity.kt"
)
CLIENT_SCREENS_SOURCE = (
    ANDROID_APP_ROOT
    / "src"
    / "main"
    / "java"
    / "com"
    / "localagentbridge"
    / "android"
    / "ui"
    / "ClientScreens.kt"
)
LOCALE_DIRS = ("values-en", "values-ko", "values-ja", "values-zh-rCN", "values-fr")
EXPECTED_RUNTIME_LANGUAGES = {
    "English": "en",
    "Korean": "ko",
    "Japanese": "ja",
    "SimplifiedChinese": "zh-CN",
    "French": "fr",
}
EXPECTED_RUNTIME_THEMES = {
    "System": "system",
    "Light": "light",
    "Dark": "dark",
}
REQUIRED_LANGUAGE_KEYS = (
    "language_title",
    "language_english",
    "language_korean",
    "language_japanese",
    "language_simplified_chinese",
    "language_french",
)
REQUIRED_APPEARANCE_KEYS = (
    "appearance_title",
    "appearance_system",
    "appearance_light",
    "appearance_dark",
)
REQUIRED_RELEASE_COPY_VALUES = {
    "values": {
        "enter_qr_payload": "Diagnostic QR text",
        "manual_qr_payload_title": "Diagnostic QR text",
        "manual_qr_payload_detail": (
            "Diagnostic fallback only. Paste AetherLink Runtime QR text when camera scanning "
            "cannot be tested; normal pairing remains camera QR scanning."
        ),
        "usb_reverse": "USB connection",
        "emulator": "Emulator connection",
        "provider_host_detail": "Status detail: %1$s",
        "provider_error_code": "Reference code: %1$s",
        "provider_show_diagnostics": "Show details",
        "provider_hide_diagnostics": "Hide details",
        "error_select_embedding_model": "Choose a memory indexing model.",
        "assistant_reasoning_label": "Thinking",
        "assistant_reasoning_show": "Show thinking",
        "assistant_reasoning_hide": "Hide thinking",
    },
    "values-en": {
        "enter_qr_payload": "Diagnostic QR text",
        "manual_qr_payload_title": "Diagnostic QR text",
        "manual_qr_payload_detail": (
            "Diagnostic fallback only. Paste AetherLink Runtime QR text when camera scanning "
            "cannot be tested; normal pairing remains camera QR scanning."
        ),
        "usb_reverse": "USB connection",
        "emulator": "Emulator connection",
        "provider_host_detail": "Status detail: %1$s",
        "provider_error_code": "Reference code: %1$s",
        "provider_show_diagnostics": "Show details",
        "provider_hide_diagnostics": "Hide details",
        "error_select_embedding_model": "Choose a memory indexing model.",
        "assistant_reasoning_label": "Thinking",
        "assistant_reasoning_show": "Show thinking",
        "assistant_reasoning_hide": "Hide thinking",
    },
    "values-ko": {
        "enter_qr_payload": "진단용 QR 텍스트",
        "manual_qr_payload_title": "진단용 QR 텍스트",
        "manual_qr_payload_detail": (
            "진단용 대체 수단입니다. 카메라 스캔을 테스트할 수 없을 때만 AetherLink Runtime QR 텍스트를 "
            "붙여넣으세요. 일반 페어링은 카메라 QR 스캔만 사용합니다."
        ),
        "usb_reverse": "USB 연결",
        "emulator": "에뮬레이터 연결",
        "provider_host_detail": "상태 세부 정보: %1$s",
        "provider_error_code": "참조 코드: %1$s",
        "provider_show_diagnostics": "세부 정보 보기",
        "provider_hide_diagnostics": "세부 정보 숨기기",
        "error_select_embedding_model": "Memory 색인 모델을 선택하세요.",
        "assistant_reasoning_label": "생각",
        "assistant_reasoning_show": "생각 펼치기",
        "assistant_reasoning_hide": "생각 접기",
    },
    "values-ja": {
        "enter_qr_payload": "診断用 QR テキスト",
        "manual_qr_payload_title": "診断用 QR テキスト",
        "manual_qr_payload_detail": (
            "診断用の代替手段です。カメラスキャンをテストできない場合にのみ、AetherLink Runtime の QR "
            "テキストを貼り付けてください。通常のペアリングはカメラ QR スキャンのままです。"
        ),
        "usb_reverse": "USB 接続",
        "emulator": "エミュレーター接続",
        "provider_host_detail": "状態の詳細: %1$s",
        "provider_error_code": "参照コード: %1$s",
        "provider_show_diagnostics": "詳細を表示",
        "provider_hide_diagnostics": "詳細を非表示",
        "error_select_embedding_model": "Memory インデックスモデルを選択してください。",
        "assistant_reasoning_label": "思考",
        "assistant_reasoning_show": "思考を表示",
        "assistant_reasoning_hide": "思考を非表示",
    },
    "values-zh-rCN": {
        "enter_qr_payload": "诊断二维码文本",
        "manual_qr_payload_title": "诊断二维码文本",
        "manual_qr_payload_detail": (
            "仅作为诊断备用方式。无法测试相机扫描时，粘贴 AetherLink Runtime 的二维码文本；"
            "正常配对仍使用相机二维码扫描。"
        ),
        "usb_reverse": "USB 连接",
        "emulator": "模拟器连接",
        "provider_host_detail": "状态详情：%1$s",
        "provider_error_code": "参考代码：%1$s",
        "provider_show_diagnostics": "显示详情",
        "provider_hide_diagnostics": "隐藏详情",
        "error_select_embedding_model": "请选择 Memory 索引模型。",
        "assistant_reasoning_label": "思考",
        "assistant_reasoning_show": "展开思考",
        "assistant_reasoning_hide": "收起思考",
    },
    "values-fr": {
        "enter_qr_payload": "Texte QR de diagnostic",
        "manual_qr_payload_title": "Texte QR de diagnostic",
        "manual_qr_payload_detail": (
            "Solution de diagnostic uniquement. Collez le texte QR d’AetherLink Runtime lorsque le scan "
            "caméra ne peut pas être testé; le jumelage normal reste le scan QR par caméra."
        ),
        "usb_reverse": "Connexion USB",
        "emulator": "Connexion émulateur",
        "provider_host_detail": "Détail de l’état : %1$s",
        "provider_error_code": "Code de référence : %1$s",
        "provider_show_diagnostics": "Afficher les détails",
        "provider_hide_diagnostics": "Masquer les détails",
        "error_select_embedding_model": "Choisissez un modèle d’indexation Memory.",
        "assistant_reasoning_label": "Réflexion",
        "assistant_reasoning_show": "Afficher la réflexion",
        "assistant_reasoning_hide": "Masquer la réflexion",
    },
}
FORBIDDEN_STALE_STRING_NAMES = (
    "tab_pairing",
    "tab_status",
    "tab_models",
    "chat_input_placeholder",
    "chat_select_model_from_runtime",
    "archive_all_chats_confirm",
    "delete_all_chats",
    "delete_all_chats_confirm",
    "delete_chat_confirm",
    "empty_chat_title",
    "empty_chat",
    "clear_chat_history",
    "clear_chat_history_confirm",
)
FORBIDDEN_STALE_VALUE_PATTERNS = (
    re.compile(r"\bAsk anything\b|무엇이든 부탁", re.IGNORECASE),
    re.compile(r"\bShow diagnostics\b|\bHide diagnostics\b", re.IGNORECASE),
    re.compile(r"\b(?:Ollama URL|LM Studio URL)\b", re.IGNORECASE),
    re.compile(r"\b(?:enter .*Ollama|enter .*LM Studio)\b", re.IGNORECASE),
    re.compile(r"\b(?:manual endpoint|manual host|fixed IP|fixed address)\b", re.IGNORECASE),
    re.compile(r"\b(?:connect directly to Ollama|connect directly to LM Studio)\b", re.IGNORECASE),
    re.compile(
        r"\bruntime identit(?:y|ies)\b|trusted identity|"
        r"런타임 신원|신원 정보|신원 확인|"
        r"ランタイム ID|信頼済み ID|識別情報|"
        r"运行时身份|可信身份|身份未知|"
        r"identit[ée]s? de runtime|identit[ée] approuv[ée]e|identit[ée] inconnue",
        re.IGNORECASE,
    ),
)
PLACEHOLDER_RE = re.compile(r"(?<!%)%(?:\d+\$)?[a-zA-Z]")
RUNTIME_LANGUAGE_ENUM_RE = re.compile(
    r"enum\s+class\s+RuntimeAppLanguage\s*\([^)]*\)\s*\{(?P<body>.*?)\n\s*companion\s+object",
    re.DOTALL,
)
RUNTIME_LANGUAGE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9]*)\(\"([^\"]*)\"\)[,;]?\s*$", re.MULTILINE)
RUNTIME_THEME_ENUM_RE = re.compile(
    r"enum\s+class\s+RuntimeAppTheme\s*\([^)]*\)\s*\{(?P<body>.*?)\n\s*companion\s+object",
    re.DOTALL,
)
RUNTIME_THEME_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9]*)\(\"([^\"]*)\"\)[,;]?\s*$", re.MULTILINE)


def string_entries(path: Path) -> list[tuple[str, str]]:
    root = ET.parse(path).getroot()
    return [
        (
            node.attrib["name"],
            "".join(node.itertext()),
        )
        for node in root.findall("string")
    ]


def string_names(path: Path) -> list[str]:
    return [name for name, _ in string_entries(path)]


def duplicate_names(names: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []

    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)

    return duplicates


def placeholders(text: str) -> list[str]:
    return sorted(PLACEHOLDER_RE.findall(text))


def stale_value_patterns(values: dict[str, str]) -> list[str]:
    failures: list[str] = []
    for name, value in values.items():
        for pattern in FORBIDDEN_STALE_VALUE_PATTERNS:
            if pattern.search(value):
                failures.append(f"{name!r} contains stale visible copy matching {pattern.pattern!r}")
    return failures


def release_copy_value_failures(resource_dir_name: str, values: dict[str, str], relative_path: Path) -> list[str]:
    expected_values = REQUIRED_RELEASE_COPY_VALUES.get(resource_dir_name, {})
    failures: list[str] = []
    for name, expected_value in expected_values.items():
        actual_value = values.get(name)
        if actual_value != expected_value:
            failures.append(
                f"{relative_path}: release copy mismatch for {name!r} "
                f"(expected={expected_value!r}, actual={actual_value!r})"
            )
    return failures


def check_runtime_language_selector(default_names: list[str]) -> list[str]:
    failures: list[str] = []
    ui_state_relative = RUNTIME_UI_STATE_SOURCE.relative_to(ROOT)
    local_store_relative = RUNTIME_LOCAL_STORE_SOURCE.relative_to(ROOT)

    if not RUNTIME_UI_STATE_SOURCE.exists():
        return [f"{ui_state_relative}: missing RuntimeAppLanguage source"]
    if not RUNTIME_LOCAL_STORE_SOURCE.exists():
        return [f"{local_store_relative}: missing persisted runtime data source"]

    ui_state_source = RUNTIME_UI_STATE_SOURCE.read_text(encoding="utf-8")
    local_store_source = RUNTIME_LOCAL_STORE_SOURCE.read_text(encoding="utf-8")
    enum_match = RUNTIME_LANGUAGE_ENUM_RE.search(ui_state_source)
    if enum_match is None:
        return [f"{ui_state_relative}: RuntimeAppLanguage enum not found"]
    languages = dict(RUNTIME_LANGUAGE_RE.findall(enum_match.group("body")))

    if languages != EXPECTED_RUNTIME_LANGUAGES:
        failures.append(
            f"{ui_state_relative}: expected app languages {EXPECTED_RUNTIME_LANGUAGES}, found {languages}"
        )

    if "val selectedLanguageTag: String = RuntimeAppLanguage.English.languageTag" not in ui_state_source:
        failures.append(f"{ui_state_relative}: UI language default must remain English")

    if "val appLanguageTag: String = RuntimeAppLanguage.English.languageTag" not in local_store_source:
        failures.append(f"{local_store_relative}: persisted language default must remain English")

    for key in REQUIRED_LANGUAGE_KEYS:
        if key not in default_names:
            failures.append(f"{ui_state_relative}: missing language resource key {key!r}")

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


def check_runtime_theme_selector(default_names: list[str]) -> list[str]:
    failures: list[str] = []
    ui_state_relative = RUNTIME_UI_STATE_SOURCE.relative_to(ROOT)
    local_store_relative = RUNTIME_LOCAL_STORE_SOURCE.relative_to(ROOT)

    if not RUNTIME_UI_STATE_SOURCE.exists():
        return [f"{ui_state_relative}: missing RuntimeAppTheme source"]
    if not RUNTIME_LOCAL_STORE_SOURCE.exists():
        return [f"{local_store_relative}: missing persisted runtime data source"]

    ui_state_source = RUNTIME_UI_STATE_SOURCE.read_text(encoding="utf-8")
    local_store_source = RUNTIME_LOCAL_STORE_SOURCE.read_text(encoding="utf-8")
    enum_match = RUNTIME_THEME_ENUM_RE.search(ui_state_source)
    if enum_match is None:
        return [f"{ui_state_relative}: RuntimeAppTheme enum not found"]
    themes = dict(RUNTIME_THEME_RE.findall(enum_match.group("body")))

    if themes != EXPECTED_RUNTIME_THEMES:
        failures.append(
            f"{ui_state_relative}: expected app themes {EXPECTED_RUNTIME_THEMES}, found {themes}"
        )

    if "val selectedTheme: RuntimeAppTheme = RuntimeAppTheme.System" not in ui_state_source:
        failures.append(f"{ui_state_relative}: UI theme default must remain System")

    if "val appTheme: String = RuntimeAppTheme.System.storageValue" not in local_store_source:
        failures.append(f"{local_store_relative}: persisted theme default must remain System")

    if "appTheme = RuntimeAppTheme.fromStorage(appTheme).storageValue" not in local_store_source:
        failures.append(f"{local_store_relative}: persisted theme must normalize through RuntimeAppTheme")

    for key in REQUIRED_APPEARANCE_KEYS:
        if key not in default_names:
            failures.append(f"{ui_state_relative}: missing appearance resource key {key!r}")

    failures.extend(
        missing_source_snippets(
            CLIENT_SCREENS_SOURCE,
            (
                "internal fun appThemePreferenceOptions(): List<Pair<RuntimeAppTheme, Int>>",
                "RuntimeAppTheme.System to R.string.appearance_system",
                "RuntimeAppTheme.Light to R.string.appearance_light",
                "RuntimeAppTheme.Dark to R.string.appearance_dark",
            ),
            "Android appearance settings options",
        )
    )
    failures.extend(
        missing_source_snippets(
            MAIN_ACTIVITY_SOURCE,
            (
                "AetherLinkTheme(theme = state.selectedTheme)",
                "RuntimeAppTheme.System -> systemDarkTheme",
                "RuntimeAppTheme.Light -> false",
                "RuntimeAppTheme.Dark -> true",
            ),
            "Android app theme wiring",
        )
    )

    return failures


def main() -> int:
    failures: list[str] = []
    default_files = sorted(
        ANDROID_ROOT.glob("**/src/main/res/values/strings.xml"),
        key=lambda path: str(path),
    )

    if not default_files:
        print("No Android default strings.xml files found.", file=sys.stderr)
        return 1

    for default_file in default_files:
        default_entries = string_entries(default_file)
        default_names = [name for name, _ in default_entries]
        default_values = dict(default_entries)
        res_dir = default_file.parents[1]
        module = default_file.relative_to(ROOT)

        duplicates = duplicate_names(default_names)
        if duplicates:
            failures.append(f"{module}: duplicate keys {duplicates}")

        stale_names = [name for name in FORBIDDEN_STALE_STRING_NAMES if name in default_names]
        if stale_names:
            failures.append(f"{module}: stale string resource names {stale_names}")

        for stale_value in stale_value_patterns(default_values):
            failures.append(f"{module}: {stale_value}")

        failures.extend(release_copy_value_failures("values", default_values, module))

        for locale_dir_name in LOCALE_DIRS:
            locale_file = res_dir / locale_dir_name / "strings.xml"
            if not locale_file.exists():
                failures.append(f"{module}: missing {locale_dir_name}/strings.xml")
                continue

            locale_entries = string_entries(locale_file)
            locale_names = [name for name, _ in locale_entries]
            locale_values = dict(locale_entries)
            locale_relative = locale_file.relative_to(ROOT)

            duplicates = duplicate_names(locale_names)
            if duplicates:
                failures.append(f"{locale_relative}: duplicate keys {duplicates}")

            stale_names = [name for name in FORBIDDEN_STALE_STRING_NAMES if name in locale_names]
            if stale_names:
                failures.append(f"{locale_relative}: stale string resource names {stale_names}")

            for stale_value in stale_value_patterns(locale_values):
                failures.append(f"{locale_relative}: {stale_value}")

            failures.extend(release_copy_value_failures(locale_dir_name, locale_values, locale_relative))

            if locale_names != default_names:
                missing = [name for name in default_names if name not in locale_names]
                extra = [name for name in locale_names if name not in default_names]
                failures.append(
                    f"{locale_relative}: key order/parity mismatch "
                    f"(missing={missing}, extra={extra})"
                )
                continue

            for name in default_names:
                default_placeholders = placeholders(default_values[name])
                locale_placeholders = placeholders(locale_values[name])
                if locale_placeholders != default_placeholders:
                    failures.append(
                        f"{locale_relative}: placeholder mismatch for {name!r} "
                        f"(default={default_placeholders}, locale={locale_placeholders})"
                    )

        failures.extend(check_runtime_language_selector(default_names))
        failures.extend(check_runtime_theme_selector(default_names))

    if failures:
        print("Android string parity check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    module_count = len(default_files)
    locale_count = len(LOCALE_DIRS)
    localized_resource_count = module_count * locale_count
    print(
        "Android string parity OK for "
        f"{module_count} module resource set(s), "
        f"{locale_count} locale(s), "
        f"{localized_resource_count} localized strings.xml file(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
