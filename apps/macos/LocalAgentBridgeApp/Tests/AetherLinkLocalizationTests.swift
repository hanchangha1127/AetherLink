import XCTest
import CompanionCore
import OllamaBackend
@testable import LocalAgentBridge
import TrustedDevices

final class AetherLinkLocalizationTests: XCTestCase {
    func testAppLanguageListStaysLimitedToInitialFiveLanguages() {
        XCTAssertEqual(
            AetherLinkAppLanguage.allCases.map(\.rawValue),
            ["en", "ko", "ja", "zh-Hans", "fr"]
        )
    }

    func testAppLanguagePickerOptionsStayAlignedWithInitialFiveLanguages() {
        XCTAssertEqual(AetherLinkAppLanguage.pickerOptions, AetherLinkAppLanguage.allCases)
        XCTAssertEqual(
            AetherLinkAppLanguage.pickerOptions.map(\.rawValue),
            ["en", "ko", "ja", "zh-Hans", "fr"]
        )
    }

    func testAppLanguagePickerTitlesUseNativeLabelsAcrossSelectedLanguages() {
        let expectedTitles = ["English", "한국어", "日本語", "简体中文", "Français"]

        for language in AetherLinkAppLanguage.allCases {
            withStoredAppLanguage(language.rawValue) {
                XCTAssertEqual(
                    AetherLinkAppLanguage.pickerOptions.map(\.title),
                    expectedTitles,
                    language.rawValue
                )
            }
        }
    }

    func testSidebarPreferencePickerAccessibilityValuesUseSelectedLanguage() {
        let expectations: [(languageTag: String, appearanceValue: String, languageValue: String)] = [
            ("en", "Dark", "English"),
            ("ko", "다크", "한국어"),
            ("ja", "ダーク", "日本語"),
            ("zh-Hans", "深色", "简体中文"),
            ("fr", "Sombre", "Français"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(AetherLinkAppAppearance.normalized("dark").title, expectation.appearanceValue)
                XCTAssertEqual(
                    AetherLinkAppLanguage.normalized(expectation.languageTag).title,
                    expectation.languageValue
                )
            }
        }
    }

    func testAppLanguageDefaultsToEnglish() {
        XCTAssertEqual(AetherLinkAppLanguage.defaultLanguage, .english)
        XCTAssertEqual(AetherLinkAppLanguage.normalized(nil), .english)
        XCTAssertEqual(AetherLinkAppLanguage.normalized(""), .english)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("unknown"), .english)
    }

    func testAppLanguageNormalizesSupportedTagsAndChineseAliases() {
        XCTAssertEqual(AetherLinkAppLanguage.normalized(" KO "), .korean)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("ko-KR"), .korean)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("ja"), .japanese)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("ja-JP"), .japanese)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("FR"), .french)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("fr-FR"), .french)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("en-US"), .english)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("zh-CN"), .simplifiedChinese)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("zh_Hans"), .simplifiedChinese)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("zh-rCN"), .simplifiedChinese)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("zh-Hans-CN"), .simplifiedChinese)
    }

    func testAppLanguageStorageKeyStaysStable() {
        XCTAssertEqual(AetherLinkAppLanguageStorageKey, "aetherlink.appLanguageTag")
    }

    func testLocalizedStringUsesSelectedAppLanguage() {
        withStoredAppLanguage("ko") {
            XCTAssertEqual(AetherLinkAppLanguage.selected, .korean)
            XCTAssertEqual(NSLocalizedString("Language", comment: ""), "언어")
            XCTAssertEqual(NSLocalizedString("Appearance", comment: ""), "외관")
        }
    }

    func testLocalizedVisibleAnchorsAcrossInitialLanguages() {
        let expectations: [(String, [String: String])] = [
            (
                "en",
                [
                    "Status": "Status",
                    "Pairing": "Pairing",
                    "Trusted Devices": "Trusted Devices",
                    "Activity": "Activity",
                    "Language": "Language",
                    "Appearance": "Appearance",
                ]
            ),
            (
                "ko",
                [
                    "Status": "상태",
                    "Pairing": "페어링",
                    "Trusted Devices": "신뢰 기기",
                    "Activity": "활동",
                    "Language": "언어",
                    "Appearance": "외관",
                ]
            ),
            (
                "ja",
                [
                    "Status": "ステータス",
                    "Pairing": "ペアリング",
                    "Trusted Devices": "信頼済みデバイス",
                    "Activity": "アクティビティ",
                    "Language": "言語",
                    "Appearance": "外観",
                ]
            ),
            (
                "zh-Hans",
                [
                    "Status": "状态",
                    "Pairing": "配对",
                    "Trusted Devices": "受信任设备",
                    "Activity": "活动",
                    "Language": "语言",
                    "Appearance": "外观",
                ]
            ),
            (
                "fr",
                [
                    "Status": "État",
                    "Pairing": "Jumelage",
                    "Trusted Devices": "Appareils approuvés",
                    "Activity": "Activité",
                    "Language": "Langue",
                    "Appearance": "Apparence",
                ]
            ),
        ]

        XCTAssertEqual(expectations.map(\.0), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for (languageTag, anchors) in expectations {
            withStoredAppLanguage(languageTag) {
                for (key, expectedValue) in anchors {
                    XCTAssertEqual(
                        NSLocalizedString(key, comment: ""),
                        expectedValue,
                        "\(languageTag) \(key)"
                    )
                }
            }
        }
    }

    func testSidebarBrandAccessibilityLabelUsesSelectedLanguage() {
        let expectations: [(languageTag: String, label: String)] = [
            ("en", "AetherLink Runtime"),
            ("ko", "AetherLink 런타임"),
            ("ja", "AetherLink ランタイム"),
            ("zh-Hans", "AetherLink 运行时"),
            ("fr", "Runtime AetherLink"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(sidebarBrandAccessibilityLabel(), expectation.label)
            }
        }
    }

    func testCompanionPageHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks() {
        let expectations: [(languageTag: String, label: String)] = [
            (
                "en",
                "AetherLink Runtime. Bridge trusted devices through AetherLink Runtime to local models."
            ),
            (
                "ko",
                "AetherLink 런타임. 신뢰된 기기를 AetherLink Runtime을 통해 로컬 모델에 연결합니다."
            ),
            (
                "ja",
                "AetherLink ランタイム。信頼済みデバイスを AetherLink Runtime 経由でローカルモデルに接続します。"
            ),
            (
                "zh-Hans",
                "AetherLink 运行时。通过 AetherLink Runtime 将受信任设备连接到本地模型。"
            ),
            (
                "fr",
                "Runtime AetherLink. Relie les appareils approuvés aux modèles locaux via AetherLink Runtime."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    companionPageHeaderAccessibilityLabel(
                        title: NSLocalizedString("AetherLink Runtime", comment: ""),
                        subtitle: NSLocalizedString("Bridge trusted devices through AetherLink Runtime to local models.", comment: "")
                    ),
                    expectation.label
                )
            }
        }

        withStoredAppLanguage("en") {
            XCTAssertEqual(companionPageHeaderAccessibilityLabel(title: " Status ", subtitle: ""), "Status")
            XCTAssertEqual(companionPageHeaderAccessibilityLabel(title: "", subtitle: " Details "), "Details")
            XCTAssertEqual(companionPageHeaderAccessibilityLabel(title: "   ", subtitle: "   "), "")
        }
    }

    func testCompanionEmptyStateAccessibilityLabelUsesSelectedLanguageAndFallbacks() {
        let expectations: [(languageTag: String, label: String)] = [
            (
                "en",
                "No models loaded. Load models available through AetherLink Runtime."
            ),
            (
                "ko",
                "불러온 모델 없음. AetherLink Runtime에서 사용할 수 있는 모델을 불러오세요."
            ),
            (
                "ja",
                "読み込まれたモデルはありません。AetherLink Runtime で利用できるモデルを読み込みます。"
            ),
            (
                "zh-Hans",
                "尚未加载模型。加载 AetherLink Runtime 可用的模型。"
            ),
            (
                "fr",
                "Aucun modèle chargé. Chargez les modèles disponibles via AetherLink Runtime."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    companionEmptyStateAccessibilityLabel(
                        title: NSLocalizedString("No models loaded", comment: ""),
                        description: NSLocalizedString("Load models available through AetherLink Runtime.", comment: "")
                    ),
                    expectation.label
                )
            }
        }

        withStoredAppLanguage("en") {
            XCTAssertEqual(companionEmptyStateAccessibilityLabel(title: " Empty ", description: ""), "Empty")
            XCTAssertEqual(companionEmptyStateAccessibilityLabel(title: "", description: " Recovery "), "Recovery")
            XCTAssertEqual(companionEmptyStateAccessibilityLabel(title: "   ", description: "   "), "")
        }
    }

    func testPairingQRCodeAccessibilityCopyUsesSelectedLanguageAndState() {
        let routeExpirationDate = Date(timeIntervalSince1970: 1_000)
        let expectations: [
            (languageTag: String, label: String, activeValue: String, expiredValue: String, hint: String, routeExpirationFormat: String)
        ] = [
            (
                "en",
                "Pairing QR code",
                "Scan this QR from AetherLink.",
                "Pairing QR expired. Generate a new QR.",
                "This QR verifies AetherLink Runtime and includes connection details for pairing or refresh.",
                "Connection details from this QR expire at %@. Generate a new QR if a device scans later."
            ),
            (
                "ko",
                "페어링 QR 코드",
                "AetherLink에서 이 QR을 스캔하세요.",
                "페어링 QR이 만료되었습니다. 새 QR을 생성하세요.",
                "이 QR은 AetherLink Runtime을 확인하고 페어링 또는 갱신에 필요한 연결 정보를 포함합니다.",
                "이 QR의 연결 정보는 %@에 만료됩니다. 기기가 나중에 스캔한다면 새 QR을 생성하세요."
            ),
            (
                "ja",
                "ペアリング QR コード",
                "AetherLink でこの QR をスキャンしてください。",
                "ペアリング QR の有効期限が切れました。新しい QR を生成してください。",
                "この QR は AetherLink Runtime を確認し、ペアリングまたは更新用の接続情報を含みます。",
                "この QR の接続情報は %@ に期限切れになります。後でデバイスがスキャンする場合は新しい QR を生成してください。"
            ),
            (
                "zh-Hans",
                "配对 QR 码",
                "请在 AetherLink 中扫描此二维码。",
                "配对二维码已过期。请生成新二维码。",
                "此二维码会验证 AetherLink Runtime，并包含配对或刷新所需的连接信息。",
                "此二维码中的连接信息将于 %@ 过期。如果设备稍后扫描，请生成新的二维码。"
            ),
            (
                "fr",
                "QR code de jumelage",
                "Scannez ce QR dans AetherLink.",
                "Le QR de jumelage a expiré. Générez un nouveau QR.",
                "Ce QR vérifie AetherLink Runtime et inclut les informations de connexion pour le jumelage ou l’actualisation.",
                "Les informations de connexion de ce QR expirent à %@. Générez un nouveau QR si un appareil scanne plus tard."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let language = AetherLinkAppLanguage(rawValue: expectation.languageTag) ?? .english
                let routeExpirationText = String(
                    format: expectation.routeExpirationFormat,
                    expectedCompanionDateString(from: routeExpirationDate, language: language)
                )
                XCTAssertEqual(pairingQRCodeAccessibilityLabel(), expectation.label)
                XCTAssertEqual(pairingQRCodeAccessibilityValue(isExpired: false), expectation.activeValue)
                XCTAssertEqual(pairingQRCodeAccessibilityValue(isExpired: true), expectation.expiredValue)
                XCTAssertEqual(pairingQRCodeAccessibilityHint(), expectation.hint)
                XCTAssertEqual(pairingQRRemoteRouteExpirationText(routeExpirationDate), routeExpirationText)
                XCTAssertEqual(
                    pairingQRCodeAccessibilityHint(remoteRouteExpiresAt: routeExpirationDate),
                    "\(expectation.hint) \(routeExpirationText)"
                )
            }
        }
    }

    func testPairingQRExpirationProgressAccessibilityUsesSelectedLanguage() {
        let now = Date(timeIntervalSince1970: 1_000)
        let activeExpiration = now.addingTimeInterval(125)
        let expiredAt = now.addingTimeInterval(-1)
        let expectations: [(languageTag: String, label: String, activeValue: String, expiredValue: String)] = [
            (
                "en",
                "Pairing QR time remaining",
                "Expires in 2 min 05 sec",
                "Pairing QR expired. Generate a new QR."
            ),
            (
                "ko",
                "페어링 QR 남은 시간",
                "2분 05초 후 만료",
                "페어링 QR이 만료되었습니다. 새 QR을 생성하세요."
            ),
            (
                "ja",
                "ペアリング QR の残り時間",
                "あと2分05秒で期限切れ",
                "ペアリング QR の有効期限が切れました。新しい QR を生成してください。"
            ),
            (
                "zh-Hans",
                "配对 QR 剩余时间",
                "2 分 05 秒后过期",
                "配对二维码已过期。请生成新二维码。"
            ),
            (
                "fr",
                "Temps restant du QR de jumelage",
                "Expire dans 2 min 05 s",
                "Le QR de jumelage a expiré. Générez un nouveau QR."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(NSLocalizedString("Pairing QR time remaining", comment: ""), expectation.label)
                XCTAssertEqual(
                    pairingQRExpirationText(expiresAt: activeExpiration, at: now),
                    expectation.activeValue
                )
                XCTAssertEqual(
                    pairingQRExpirationText(expiresAt: expiredAt, at: now),
                    expectation.expiredValue
                )
            }
        }
    }

    func testPairingRouteNoticeAccessibilityUsesSelectedLanguage() {
        let expectations: [(languageTag: String, label: String, waiting: String, ready: String)] = [
            (
                "en",
                "Pairing QR status",
                "Pairing QR is waiting for connection details.",
                "This QR includes connection details for relay.example.test. Devices can scan it in AetherLink to pair or refresh their saved connection."
            ),
            (
                "ko",
                "페어링 QR 상태",
                "페어링 QR이 연결 정보를 기다리는 중입니다.",
                "이 QR에는 relay.example.test의 연결 정보가 포함되어 있습니다. 기기는 AetherLink에서 스캔해 페어링하거나 저장된 연결을 갱신할 수 있습니다."
            ),
            (
                "ja",
                "ペアリング QR の状態",
                "ペアリング QR は接続情報を待っています。",
                "この QR には relay.example.test の接続情報が含まれています。デバイスは AetherLink でスキャンしてペアリングまたは保存済み接続の更新ができます。"
            ),
            (
                "zh-Hans",
                "配对 QR 状态",
                "配对二维码正在等待连接信息。",
                "此二维码包含 relay.example.test 的连接信息。设备可在 AetherLink 中扫描以配对或刷新已保存的连接。"
            ),
            (
                "fr",
                "État du QR de jumelage",
                "Le QR de jumelage attend les informations de connexion.",
                "Ce QR inclut les informations de connexion de relay.example.test. Les appareils peuvent le scanner dans AetherLink pour se jumeler ou actualiser leur connexion enregistrée."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(pairingRouteNoticeAccessibilityLabel(), expectation.label)
                XCTAssertEqual(
                    NSLocalizedString("Pairing QR is waiting for connection details.", comment: ""),
                    expectation.waiting
                )
                XCTAssertEqual(
                    String(
                        format: NSLocalizedString(
                            "This QR includes connection details for %@. Devices can scan it in AetherLink to pair or refresh their saved connection.",
                            comment: ""
                        ),
                        "relay.example.test"
                    ),
                    expectation.ready
                )
            }
        }
    }

    func testVisibleModelGroupsShowOnlyInstalledLocalModels() {
        let groups = visibleModelGroups(for: [
            ModelInfo(
                id: "local-chat",
                name: "Local Chat",
                kind: .chat,
                installed: true,
                source: .local
            ),
            ModelInfo(
                id: "provider-managed-chat",
                name: "Provider Managed Chat",
                kind: .chat,
                installed: true,
                source: .cloud,
                remoteModel: "remote-chat"
            ),
            ModelInfo(
                id: "uninstalled-chat",
                name: "Uninstalled Chat",
                kind: .chat,
                installed: false,
                source: .local
            ),
            ModelInfo(
                id: "local-embedding",
                name: "Local Embedding",
                kind: .embedding,
                installed: true,
                source: .local
            ),
            ModelInfo(
                id: "provider-managed-embedding",
                name: "Provider Managed Embedding",
                kind: .embedding,
                installed: true,
                source: .cloud,
                remoteModel: "remote-embedding"
            ),
            ModelInfo(
                id: "uninstalled-embedding",
                name: "Uninstalled Embedding",
                kind: .embedding,
                installed: false,
                source: .local
            ),
        ])

        XCTAssertEqual(groups.map(\.kind), [.chat, .embedding])
        XCTAssertEqual(groups.first(where: { $0.kind == .chat })?.models.map(\.id), ["local-chat"])
        XCTAssertEqual(groups.first(where: { $0.kind == .embedding })?.models.map(\.id), ["local-embedding"])
        XCTAssertFalse(groups.flatMap(\.models).contains { $0.source == .cloud || !$0.installed })
    }

    func testModelRowAccessibilityLabelUsesModelContext() {
        let expectations: [(languageTag: String, chatLabel: String, embeddingLabel: String, fallbackLabel: String)] = [
            (
                "en",
                "Model Llama 3. ID llama3:8b. Type Chat. Provider Ollama. Source Local. State Running. Size 4.7 GB",
                "Model Nomic Embed. ID nomic-embed-text. Type Embedding. Provider LM Studio. Source Local. State Not running. Size Size unknown",
                "Model Unnamed model. ID Unknown model ID. Type Unknown model type. Provider Unknown provider. Source Unknown source. State Not running. Size Size unknown"
            ),
            (
                "ko",
                "모델 Llama 3. ID llama3:8b. 유형 채팅. 제공자 Ollama. 출처 로컬. 상태 실행 중. 크기 4.7 GB",
                "모델 Nomic Embed. ID nomic-embed-text. 유형 임베딩. 제공자 LM Studio. 출처 로컬. 상태 실행 안 됨. 크기 크기 알 수 없음",
                "모델 이름 없는 모델. ID 알 수 없는 모델 ID. 유형 알 수 없는 모델 유형. 제공자 알 수 없는 제공자. 출처 알 수 없는 출처. 상태 실행 안 됨. 크기 크기 알 수 없음"
            ),
            (
                "ja",
                "モデル Llama 3。ID llama3:8b。タイプ チャット。プロバイダー Ollama。ソース ローカル。状態 実行中。サイズ 4.7 GB",
                "モデル Nomic Embed。ID nomic-embed-text。タイプ 埋め込み。プロバイダー LM Studio。ソース ローカル。状態 未実行。サイズ サイズ不明",
                "モデル 名前のないモデル。ID 不明なモデル ID。タイプ 不明なモデルタイプ。プロバイダー 不明なプロバイダー。ソース 不明なソース。状態 未実行。サイズ サイズ不明"
            ),
            (
                "zh-Hans",
                "模型 Llama 3。ID llama3:8b。类型 聊天。提供方 Ollama。来源 本地。状态 运行中。大小 4.7 GB",
                "模型 Nomic Embed。ID nomic-embed-text。类型 嵌入。提供方 LM Studio。来源 本地。状态 未运行。大小 大小未知",
                "模型 未命名模型。ID 未知模型 ID。类型 未知模型类型。提供方 未知提供方。来源 未知来源。状态 未运行。大小 大小未知"
            ),
            (
                "fr",
                "Modèle Llama 3. ID llama3:8b. Type Chat. Fournisseur Ollama. Source Local. État En cours. Taille 4.7 GB",
                "Modèle Nomic Embed. ID nomic-embed-text. Type Embedding. Fournisseur LM Studio. Source Local. État À l’arrêt. Taille Taille inconnue",
                "Modèle Modèle sans nom. ID ID de modèle inconnu. Type Type de modèle inconnu. Fournisseur Fournisseur inconnu. Source Source inconnue. État À l’arrêt. Taille Taille inconnue"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    modelRowAccessibilityLabel(
                        name: " Llama 3 ",
                        identifier: " llama3:8b ",
                        kind: NSLocalizedString("Chat", comment: ""),
                        provider: NSLocalizedString("Ollama", comment: ""),
                        source: NSLocalizedString("Local", comment: ""),
                        running: true,
                        size: " 4.7 GB "
                    ),
                    expectation.chatLabel
                )
                XCTAssertEqual(
                    modelRowAccessibilityLabel(
                        name: "Nomic Embed",
                        identifier: "nomic-embed-text",
                        kind: NSLocalizedString("Embedding", comment: ""),
                        provider: NSLocalizedString("LM Studio", comment: ""),
                        source: NSLocalizedString("Local", comment: ""),
                        running: false,
                        size: nil
                    ),
                    expectation.embeddingLabel
                )
                XCTAssertEqual(
                    modelRowAccessibilityLabel(
                        name: " ",
                        identifier: " ",
                        kind: " ",
                        provider: " ",
                        source: " ",
                        running: false,
                        size: " "
                    ),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testModelGroupHeaderAccessibilityLabelUsesSelectedLanguage() {
        let expectations: [(languageTag: String, chatLabel: String, embeddingLabel: String, fallbackLabel: String)] = [
            (
                "en",
                "Model section Chat Models. 2 models",
                "Model section Embedding Models. 1 model",
                "Model section Model section. No model count"
            ),
                (
                    "ko",
                    "모델 섹션 채팅 모델. 모델 2개",
                    "모델 섹션 임베딩 모델. 모델 1개",
                    "모델 섹션 모델 섹션. 모델 수 없음"
                ),
                (
                    "ja",
                    "モデルセクション チャットモデル。2 件のモデル",
                    "モデルセクション 埋め込みモデル。1 件のモデル",
                    "モデルセクション モデルセクション。モデル数なし"
                ),
            (
                "zh-Hans",
                "模型分区 聊天模型。2 个模型",
                "模型分区 嵌入模型。1 个模型",
                "模型分区 模型分区。没有模型数量"
            ),
            (
                "fr",
                "Section de modèles Modèles de chat. 2 modèles",
                "Section de modèles Modèles d’embedding. 1 modèle",
                "Section de modèles Section de modèles. Aucun nombre de modèles"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    modelGroupHeaderAccessibilityLabel(
                        title: NSLocalizedString("Chat Models", comment: ""),
                        count: localizedModelCount(2)
                    ),
                    expectation.chatLabel,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelGroupHeaderAccessibilityLabel(
                        title: NSLocalizedString("Embedding Models", comment: ""),
                        count: localizedModelCount(1)
                    ),
                    expectation.embeddingLabel,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelGroupHeaderAccessibilityLabel(title: " ", count: "\n"),
                    expectation.fallbackLabel,
                    expectation.languageTag
                )
            }
        }
    }

    func testLocalizedStringDefaultsToEnglishForUnsupportedStoredLanguage() {
        withStoredAppLanguage("unsupported") {
            XCTAssertEqual(AetherLinkAppLanguage.selected, .english)
            XCTAssertEqual(NSLocalizedString("Language", comment: ""), "Language")
            XCTAssertEqual(NSLocalizedString("Appearance", comment: ""), "Appearance")
        }
    }

    func testLocalizedStringFallsBackToKeyWhenMissing() {
        withStoredAppLanguage("ko") {
            XCTAssertEqual(NSLocalizedString("Missing Test Key", comment: ""), "Missing Test Key")
        }
    }

    func testLocalizedCountHelpersUseNaturalSingularAndPluralCopy() {
        withStoredAppLanguage("en") {
            let copy = [
                localizedTrustedDeviceCount(1),
                localizedTrustedDeviceCount(2),
                localizedModelCount(1),
                localizedModelCount(4),
                localizedLoadedModelCount(1),
                localizedLoadedModelCount(3),
                localizedAvailableModelProviderCount(1),
                localizedAvailableModelProviderCount(2),
                localizedLoadedLocalModelLogCount("1"),
                localizedLoadedLocalModelLogCount("2"),
                localizedModelResidencyActiveDetail(providerName: "Ollama", modelID: "llama3.1", idleUnloadMinutes: 1),
                localizedModelResidencyActiveDetail(providerName: "Ollama", modelID: "llama3.1", idleUnloadMinutes: 10),
            ]

            XCTAssertEqual(copy[0], "1 trusted device")
            XCTAssertEqual(copy[1], "2 trusted devices")
            XCTAssertEqual(copy[2], "1 model")
            XCTAssertEqual(copy[3], "4 models")
            XCTAssertEqual(copy[4], "1 model loaded")
            XCTAssertEqual(copy[5], "3 models loaded")
            XCTAssertEqual(copy[6], "1 model provider available")
            XCTAssertEqual(copy[7], "2 model providers available")
            XCTAssertEqual(copy[8], "Loaded 1 model")
            XCTAssertEqual(copy[9], "Loaded 2 models")
            XCTAssertEqual(copy[10], "Ollama llama3.1 active. Idle unload after 1 minute.")
            XCTAssertEqual(copy[11], "Ollama llama3.1 active. Idle unload after 10 minutes.")
            XCTAssertFalse(copy.contains { $0.contains("(s)") })
        }

        withStoredAppLanguage("ko") {
            XCTAssertEqual(localizedTrustedDeviceCount(2), "신뢰 기기 2대")
            XCTAssertEqual(localizedLoadedModelCount(2), "모델 2개 불러옴")
            XCTAssertEqual(localizedLoadedLocalModelLogCount("2"), "모델 2개 불러옴")
        }

        withStoredAppLanguage("fr") {
            XCTAssertEqual(localizedTrustedDeviceCount(1), "1 appareil approuvé")
            XCTAssertEqual(localizedTrustedDeviceCount(2), "2 appareils approuvés")
            XCTAssertEqual(localizedAvailableModelProviderCount(1), "1 fournisseur de modèles disponible")
            XCTAssertEqual(localizedAvailableModelProviderCount(2), "2 fournisseurs de modèles disponibles")
        }
    }

    func testEnglishLocalizationKeepsReleaseFacingConnectionAndDetailsCopy() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(NSLocalizedString("Technical Details", comment: ""), "Details")
            XCTAssertEqual(NSLocalizedString("Provider endpoint redacted.", comment: ""), "Provider address hidden.")
            XCTAssertEqual(NSLocalizedString("Advanced Connection Setup", comment: ""), "Connection Recovery")
            XCTAssertEqual(NSLocalizedString("Connection Setup", comment: ""), "Recovery Details")
            XCTAssertEqual(NSLocalizedString("Connection Recovery result", comment: ""), "Connection Recovery result")
            XCTAssertEqual(NSLocalizedString("Connection setup secret", comment: ""), "Protected connection key")
            XCTAssertEqual(
                NSLocalizedString("Connection setup secret regenerated.", comment: ""),
                "Protected connection key refreshed."
            )
        }
    }

    func testStatusNearbyOnlyConnectionGuidanceUsesActionableCopyAcrossLanguages() {
        let key = "No cross-network connection details are saved yet. Nearby pairing still works. For another network, use a reachable relay, VPN, or tunnel before generating the latest QR."
        let expectations: [(languageTag: String, detail: String)] = [
            (
                "en",
                "No cross-network connection details are saved yet. Nearby pairing still works. For another network, use a reachable relay, VPN, or tunnel before generating the latest QR."
            ),
            (
                "ko",
                "다른 네트워크용 연결 정보가 아직 저장되어 있지 않습니다. 근처 페어링은 계속 동작합니다. 다른 네트워크에서는 최신 QR을 생성하기 전에 접근 가능한 릴레이, VPN 또는 터널을 사용하세요."
            ),
            (
                "ja",
                "別ネットワーク用の接続情報はまだ保存されていません。近くでのペアリングは引き続き機能します。別ネットワークでは、最新の QR を生成する前に到達可能なリレー、VPN、またはトンネルを使用してください。"
            ),
            (
                "zh-Hans",
                "尚未保存跨网络连接信息。附近配对仍可使用。跨网络时，请先使用可访问的中继、VPN 或隧道，再生成最新二维码。"
            ),
            (
                "fr",
                "Aucune information de connexion interréseau n’est encore enregistrée. Le jumelage à proximité fonctionne toujours. Pour un autre réseau, utilisez un relais, VPN ou tunnel joignable avant de générer le dernier QR."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let detail = NSLocalizedString(key, comment: "")
                XCTAssertEqual(detail, expectation.detail, expectation.languageTag)
                XCTAssertFalse(detail.localizedCaseInsensitiveContains("prepared later"), expectation.languageTag)
            }
        }
    }

    func testActivityTechnicalDetailsAccessibilityLabelUsesEventContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Details for Received device runtime request",
                "Details for Runtime event recorded."
            ),
            (
                "ko",
                "기기 런타임 요청 수신의 세부 정보",
                "런타임 이벤트가 기록되었습니다.의 세부 정보"
            ),
            (
                "ja",
                "デバイスランタイムリクエストを受信しました の詳細",
                "ランタイムイベントを記録しました。 の詳細"
            ),
            (
                "zh-Hans",
                "已收到设备运行时请求 的详情",
                "已记录运行时事件。 的详情"
            ),
            (
                "fr",
                "Détails pour Requête runtime d’appareil reçue",
                "Détails pour Événement du runtime enregistré."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let receivedSummary = localizedLogDisplay("Received chat.send").summary
                XCTAssertEqual(logTechnicalDetailsAccessibilityLabel(summary: " \(receivedSummary) "), expectation.label)
                XCTAssertEqual(logTechnicalDetailsAccessibilityLabel(summary: " "), expectation.fallbackLabel)
            }
        }
    }

    func testActivityTechnicalDetailsAccessibilityStateUsesSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            expandedValue: String,
            collapsedValue: String,
            expandedHint: String,
            collapsedHint: String
        )] = [
            (
                "en",
                "Activity details expanded",
                "Activity details collapsed",
                "Collapse to hide activity details.",
                "Expand to show activity details."
            ),
            (
                "ko",
                "활동 세부 정보 펼쳐짐",
                "활동 세부 정보 접힘",
                "활동 세부 정보를 숨기려면 접으세요.",
                "활동 세부 정보를 보려면 펼치세요."
            ),
            (
                "ja",
                "アクティビティ詳細は展開済み",
                "アクティビティ詳細は折りたたみ済み",
                "アクティビティ詳細を非表示にするには折りたたみます。",
                "アクティビティ詳細を表示するには展開します。"
            ),
            (
                "zh-Hans",
                "活动详情已展开",
                "活动详情已折叠",
                "折叠以隐藏活动详情。",
                "展开以显示活动详情。"
            ),
            (
                "fr",
                "Détails d’activité développés",
                "Détails d’activité réduits",
                "Réduire pour masquer les détails d’activité.",
                "Développer pour afficher les détails d’activité."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    logTechnicalDetailsAccessibilityValue(isExpanded: true),
                    expectation.expandedValue,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    logTechnicalDetailsAccessibilityValue(isExpanded: false),
                    expectation.collapsedValue,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    logTechnicalDetailsAccessibilityHint(isExpanded: true),
                    expectation.expandedHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    logTechnicalDetailsAccessibilityHint(isExpanded: false),
                    expectation.collapsedHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testActivityLogRowAccessibilityLabelIncludesLocalizedTone() {
        let expectations: [(languageTag: String, warningLabel: String, fallbackLabel: String)] = [
            (
                "en",
                "Activity item AetherLink Runtime needs attention. Status Needs attention.",
                "Activity item Runtime event recorded. Status Pending."
            ),
            (
                "ko",
                "활동 항목 AetherLink Runtime 확인이 필요합니다. 상태 확인 필요.",
                "활동 항목 런타임 이벤트가 기록되었습니다. 상태 대기 중."
            ),
            (
                "ja",
                "アクティビティ項目 AetherLink Runtime の確認が必要です。ステータス 確認が必要。",
                "アクティビティ項目 ランタイムイベントを記録しました。ステータス 保留中。"
            ),
            (
                "zh-Hans",
                "活动项 AetherLink Runtime 需要检查。状态 需要注意。",
                "活动项 已记录运行时事件。状态 待处理。"
            ),
            (
                "fr",
                "Élément d’activité AetherLink Runtime demande une vérification. État Attention requise.",
                "Élément d’activité Événement du runtime enregistré. État En attente."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let warningSummary = localizedLogDisplay("Runtime listener failed: port unavailable").summary
                XCTAssertEqual(logRowAccessibilityLabel(summary: warningSummary, tone: .warning), expectation.warningLabel)
                XCTAssertEqual(logRowAccessibilityLabel(summary: " ", tone: .neutral), expectation.fallbackLabel)
            }
        }
    }

    func testActivityTrustedDeviceLogSummariesUseDeviceContextAcrossLanguages() {
        let expectations: [(languageTag: String, trusted: String, removed: String, fallbackTrusted: String)] = [
            (
                "en",
                "Trusted device Pixel",
                "Removed trust for Pixel",
                "Trusted device Selected device"
            ),
            (
                "ko",
                "신뢰 기기 Pixel 등록됨",
                "Pixel 신뢰 해제됨",
                "신뢰 기기 선택한 항목 등록됨"
            ),
            (
                "ja",
                "信頼済みデバイス Pixel を登録しました",
                "Pixel の信頼を解除しました",
                "信頼済みデバイス 選択したデバイス を登録しました"
            ),
            (
                "zh-Hans",
                "已信任设备 Pixel",
                "已移除 Pixel 的信任",
                "已信任设备 所选设备"
            ),
            (
                "fr",
                "Appareil Pixel approuvé",
                "Approbation retirée pour Pixel",
                "Appareil Appareil sélectionné approuvé"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(localizedLogDisplay("Trusted Pixel").summary, expectation.trusted)
                XCTAssertEqual(localizedLogDisplay("Removed Pixel").summary, expectation.removed)
                XCTAssertEqual(localizedLogDisplay("Trusted   ").summary, expectation.fallbackTrusted)
                XCTAssertFalse(localizedLogDisplay("Removed Pixel").summary.contains("Removed Pixel"))
            }
        }
    }

    @MainActor
    func testRouteDiagnosticsPanelStaysHiddenOnCleanFirstRunUntilRouteStateExists() throws {
        let cleanFirstRunModel = CompanionAppModel(
            environment: isolatedRuntimeIdentityEnvironment(),
            userDefaults: try isolatedDefaults()
        )
        XCTAssertFalse(cleanFirstRunModel.hasDevelopmentRelayRoute)
        XCTAssertFalse(cleanFirstRunModel.bootstrapRelaySettings.isEnabled)
        XCTAssertNil(cleanFirstRunModel.remoteRoutePreparationIssue)
        XCTAssertFalse(shouldShowRouteDiagnosticsPanel(model: cleanFirstRunModel))

        let savedRouteModel = CompanionAppModel(
            environment: isolatedRuntimeIdentityEnvironment(),
            userDefaults: try isolatedDefaults()
        )
        savedRouteModel.configureDevelopmentRelay(
            host: "relay.example.test",
            port: 443,
            relaySecret: "secret-1"
        )
        XCTAssertTrue(savedRouteModel.hasDevelopmentRelayRoute)
        XCTAssertTrue(shouldShowRouteDiagnosticsPanel(model: savedRouteModel))

        let routeIssueModel = CompanionAppModel(
            environment: isolatedRuntimeIdentityEnvironment(),
            userDefaults: try isolatedDefaults()
        )
        routeIssueModel.configureDevelopmentRelay(
            host: "https://relay.example.test",
            port: 443,
            relaySecret: "secret-1"
        )
        XCTAssertNotNil(routeIssueModel.remoteRoutePreparationIssue)
        XCTAssertTrue(shouldShowRouteDiagnosticsPanel(model: routeIssueModel))
    }

    func testAppAppearancePickerOptionsStaySystemLightDark() {
        XCTAssertEqual(AetherLinkAppAppearance.allCases.map(\.rawValue), ["system", "light", "dark"])
        XCTAssertEqual(AetherLinkAppAppearance.pickerOptions, AetherLinkAppAppearance.allCases)
    }

    func testAppAppearanceDefaultsToSystem() {
        XCTAssertEqual(AetherLinkAppAppearance.defaultAppearance, .system)
        XCTAssertEqual(AetherLinkAppAppearance.normalized(nil), .system)
        XCTAssertEqual(AetherLinkAppAppearance.normalized(""), .system)
        XCTAssertEqual(AetherLinkAppAppearance.normalized("unknown"), .system)
    }

    func testAppAppearanceNormalizesSupportedValues() {
        XCTAssertEqual(AetherLinkAppAppearance.normalized(" LIGHT "), .light)
        XCTAssertEqual(AetherLinkAppAppearance.normalized("dark"), .dark)
        XCTAssertEqual(AetherLinkAppAppearance.normalized("SYSTEM"), .system)
    }

    func testAppAppearancePreferredColorSchemeMapping() {
        XCTAssertNil(AetherLinkAppAppearance.system.preferredColorScheme)
        XCTAssertEqual(AetherLinkAppAppearance.light.preferredColorScheme, .light)
        XCTAssertEqual(AetherLinkAppAppearance.dark.preferredColorScheme, .dark)
    }

    func testAppAppearanceStorageKeyStaysStable() {
        XCTAssertEqual(AetherLinkAppAppearanceStorageKey, "aetherlink.appAppearance")
    }

    func testCompanionFirstLaunchStartsWithPairingWhenNoTrustedDevicesExist() {
        XCTAssertEqual(
            companionOnboardingSection(current: .status, trustedDeviceCount: 0),
            .pairing
        )
        XCTAssertEqual(
            companionOnboardingSection(current: .status, trustedDeviceCount: 1),
            .status
        )
        XCTAssertEqual(
            companionOnboardingSection(current: .logs, trustedDeviceCount: 0),
            .pairing
        )
        XCTAssertEqual(
            companionOnboardingSection(current: .trustedDevices, trustedDeviceCount: 0),
            .pairing
        )
    }

    func testExternalPairingRequestOverridesCurrentCompanionSection() {
        XCTAssertEqual(
            companionSectionAfterExternalRequest(
                current: .logs,
                trustedDeviceCount: 2,
                requested: .pairing
            ),
            .pairing
        )
        XCTAssertEqual(
            companionSectionAfterExternalRequest(
                current: .trustedDevices,
                trustedDeviceCount: 0,
                requested: .pairing
            ),
            .pairing
        )
        XCTAssertEqual(
            companionSectionAfterExternalRequest(
                current: .status,
                trustedDeviceCount: 0,
                requested: nil
            ),
            .pairing
        )
    }

    func testTrustedDeviceCountChangeReturnsUnpairedRuntimeToPairing() {
        XCTAssertEqual(
            companionSectionAfterTrustedDeviceCountChange(
                current: .trustedDevices,
                trustedDeviceCount: 0
            ),
            .pairing
        )
        XCTAssertEqual(
            companionSectionAfterTrustedDeviceCountChange(
                current: .logs,
                trustedDeviceCount: 0
            ),
            .pairing
        )
        XCTAssertEqual(
            companionSectionAfterTrustedDeviceCountChange(
                current: .logs,
                trustedDeviceCount: 1
            ),
            .logs
        )
    }

    func testToolbarAndMenuPairingQRGenerationUsesSharedAvailabilityContract() {
        let cases: [(canPrepareAutomatically: Bool, isRouteEligibleForQRCode: Bool, isAvailable: Bool)] = [
            (true, false, true),
            (false, true, true),
            (false, false, false),
        ]

        for testCase in cases {
            XCTAssertEqual(
                pairingQRGenerationCommandAvailable(
                    canPrepareAutomatically: testCase.canPrepareAutomatically,
                    isRouteEligibleForQRCode: testCase.isRouteEligibleForQRCode
                ),
                testCase.isAvailable
            )
            XCTAssertEqual(
                pairingQRGenerationCommandAvailable(
                    canPrepareAutomatically: testCase.canPrepareAutomatically,
                    isRouteEligibleForQRCode: testCase.isRouteEligibleForQRCode
                ),
                pairingQRGenerationAvailable(
                    canPrepareAutomatically: testCase.canPrepareAutomatically,
                    isRouteEligibleForQRCode: testCase.isRouteEligibleForQRCode
                )
            )
        }
    }

    func testPrimaryActionsPrioritizePairingQRWhenNoTrustedDevicesExist() {
        XCTAssertEqual(
            companionPrimaryActionOrder(trustedDeviceCount: -1),
            [.pairingQR, .refreshProviders, .loadModels]
        )
        XCTAssertEqual(
            companionPrimaryActionOrder(trustedDeviceCount: 0),
            [.pairingQR, .refreshProviders, .loadModels]
        )
        XCTAssertEqual(
            companionPrimaryActionOrder(trustedDeviceCount: 1),
            [.refreshProviders, .loadModels, .pairingQR]
        )
    }

    func testMenuBarStatusAndCommandTitlesUseSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            runtimeStatus: String,
            modelServiceStatus: String,
            commandTitles: MenuBarCommandTitles
        )] = [
            (
                "en",
                "Runtime: Ready for devices",
                "Model service: Not checked",
                MenuBarCommandTitles(
                    openAetherLink: "Open AetherLink",
                    refresh: "Refresh",
                    loadModels: "Load Models",
                    quit: "Quit"
                )
            ),
            (
                "ko",
                "런타임: 기기 연결 준비됨",
                "모델 서비스: 확인 전",
                MenuBarCommandTitles(
                    openAetherLink: "AetherLink 열기",
                    refresh: "새로고침",
                    loadModels: "모델 불러오기",
                    quit: "종료"
                )
            ),
            (
                "ja",
                "ランタイム: デバイスの準備完了",
                "モデルサービス: 未確認",
                MenuBarCommandTitles(
                    openAetherLink: "AetherLink を開く",
                    refresh: "更新",
                    loadModels: "モデルを読み込む",
                    quit: "終了"
                )
            ),
            (
                "zh-Hans",
                "运行时：已准备连接设备",
                "模型服务：未检查",
                MenuBarCommandTitles(
                    openAetherLink: "打开 AetherLink",
                    refresh: "刷新",
                    loadModels: "加载模型",
                    quit: "退出"
                )
            ),
            (
                "fr",
                "Runtime : Prêt pour les appareils",
                "Service de modèles : Non vérifié",
                MenuBarCommandTitles(
                    openAetherLink: "Ouvrir AetherLink",
                    refresh: "Actualiser",
                    loadModels: "Charger les modèles",
                    quit: "Quitter"
                )
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    menuBarRuntimeStatusText(.advertising(serviceName: "AetherLink", port: 43170)),
                    expectation.runtimeStatus,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    menuBarModelServiceStatusText([]),
                    expectation.modelServiceStatus,
                    expectation.languageTag
                )
                XCTAssertEqual(menuBarCommandTitles(), expectation.commandTitles, expectation.languageTag)
            }
        }
    }

    func testMenuBarPairingQRCommandTitleTracksActiveSessionAndLanguage() {
        let expectations: [(
            languageTag: String,
            inactiveTitle: String,
            activeTitle: String
        )] = [
            ("en", "Generate Pairing QR", "Generate New QR"),
            ("ko", "페어링 QR 생성", "새 QR 생성"),
            ("ja", "ペアリング QR を生成", "新しい QR を生成"),
            ("zh-Hans", "生成配对二维码", "生成新二维码"),
            ("fr", "Générer le QR de jumelage", "Générer un nouveau QR"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    pairingQRGenerationCommandTitle(hasActiveSession: false),
                    expectation.inactiveTitle,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    pairingQRGenerationCommandTitle(hasActiveSession: true),
                    expectation.activeTitle,
                    expectation.languageTag
                )
            }
        }
    }

    func testQuickActionAccessibilityUsesSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            ready: String,
            checkProvidersHint: String,
            loadModelsHint: String
        )] = [
            (
                "en",
                "Ready",
                "Check model provider availability through AetherLink Runtime.",
                "Load the installed local model list through AetherLink Runtime."
            ),
            (
                "ko",
                "준비됨",
                "AetherLink Runtime을 통해 모델 제공자 사용 가능 여부를 확인합니다.",
                "AetherLink Runtime을 통해 설치된 로컬 모델 목록을 불러옵니다."
            ),
            (
                "ja",
                "準備完了",
                "AetherLink Runtime 経由でモデルプロバイダーの利用可否を確認します。",
                "AetherLink Runtime 経由でインストール済みローカルモデルの一覧を読み込みます。"
            ),
            (
                "zh-Hans",
                "就绪",
                "通过 AetherLink Runtime 检查模型提供方可用性。",
                "通过 AetherLink Runtime 加载已安装的本地模型列表。"
            ),
            (
                "fr",
                "Prêt",
                "Vérifie la disponibilité des fournisseurs de modèles via AetherLink Runtime.",
                "Charge la liste des modèles locaux installés via AetherLink Runtime."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    modelProviderCheckActionAccessibilityValue(),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelProviderCheckActionAccessibilityHint(),
                    expectation.checkProvidersHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelListLoadActionAccessibilityValue(),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelListLoadActionAccessibilityHint(),
                    expectation.loadModelsHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testPairingQRGenerationActionAccessibilityUsesSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            ready: String,
            unavailable: String,
            disabledHint: String,
            missingActionHint: String,
            activeRenewalHint: String
        )] = [
            (
                "en",
                "Ready",
                "Unavailable",
                "Pairing from another network needs a relay, VPN, tunnel, or private-overlay route inside the pairing QR.",
                "Pairing QR generation is unavailable from this view.",
                "Generate New QR"
            ),
            (
                "ko",
                "준비됨",
                "사용 불가",
                "다른 네트워크에서 페어링하려면 페어링 QR 안에 릴레이, VPN, 터널 또는 프라이빗 오버레이 경로가 필요합니다.",
                "이 화면에서는 페어링 QR을 생성할 수 없습니다.",
                "새 QR 생성"
            ),
            (
                "ja",
                "準備完了",
                "利用不可",
                "別ネットワークからペアリングするには、ペアリング QR 内にリレー、VPN、トンネル、またはプライベートオーバーレイ経路が必要です。",
                "この画面ではペアリング QR を生成できません。",
                "新しい QR を生成"
            ),
            (
                "zh-Hans",
                "就绪",
                "不可用",
                "从另一个网络配对时，配对二维码内需要包含中继、VPN、隧道或私有覆盖网络路径。",
                "此视图无法生成配对二维码。",
                "生成新二维码"
            ),
            (
                "fr",
                "Prêt",
                "Indisponible",
                "Le jumelage depuis un autre réseau nécessite une route relais, VPN, tunnel ou overlay privé dans le QR de jumelage.",
                "La génération du QR de jumelage n'est pas disponible depuis cette vue.",
                "Générer un nouveau QR"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    pairingQRGenerationActionAccessibilityValue(isAvailable: true),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    pairingQRGenerationActionAccessibilityValue(isAvailable: false),
                    expectation.unavailable,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    pairingQRGenerationActionAccessibilityValue(isAvailable: true, hasAction: false),
                    expectation.unavailable,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    pairingQRGenerationActionAccessibilityHint(isAvailable: false),
                    expectation.disabledHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    pairingQRGenerationActionAccessibilityHint(isAvailable: true, hasAction: false),
                    expectation.missingActionHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    activePairingQRRenewalActionAccessibilityHint(),
                    expectation.activeRenewalHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testStatusOverviewPrioritizesPairingBeforeProviderRepairOnFirstLaunch() {
        XCTAssertEqual(
            statusRuntimeOverviewFocus(
                isRuntimeAdvertising: true,
                isBackendReady: false,
                hasTrustedDevices: false,
                hasLoadedModels: false,
                hasRoutePreparationIssue: false,
                hasDevelopmentRelayRoute: false,
                isDevelopmentRelayQRCodeReady: false
            ),
            .pairing
        )
    }

    func testStatusOverviewShowsProviderRepairAfterPairingExists() {
        XCTAssertEqual(
            statusRuntimeOverviewFocus(
                isRuntimeAdvertising: true,
                isBackendReady: false,
                hasTrustedDevices: true,
                hasLoadedModels: false,
                hasRoutePreparationIssue: false,
                hasDevelopmentRelayRoute: false,
                isDevelopmentRelayQRCodeReady: false
            ),
            .backend
        )
    }

    func testRuntimeOverviewAccessibilityLabelUsesTitleStatusDetailAndFootnote() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Runtime overview Ready for Devices. Status Ready. Model provider is responding. AetherLink Runtime mediates device requests. Model providers stay private.",
                "Runtime overview Runtime overview. Status Unknown status. No overview details No additional guidance"
            ),
            (
                "ko",
                "런타임 요약 기기 준비 완료. 상태 준비됨. 모델 제공자가 응답 중입니다. AetherLink Runtime이 기기 요청을 중계합니다. 모델 제공자는 비공개로 유지됩니다.",
                "런타임 요약 런타임 요약. 상태 알 수 없음. 요약 세부 정보 없음 추가 안내 없음"
            ),
            (
                "ja",
                "ランタイム概要 デバイスの準備完了。ステータス 準備完了。モデルプロバイダーが応答しています。 AetherLink Runtime がデバイス要求を仲介します。モデルプロバイダーは非公開です。",
                "ランタイム概要 ランタイム概要。ステータス 不明な状態。概要の詳細なし 追加案内なし"
            ),
            (
                "zh-Hans",
                "运行时概览 设备已准备好。状态 就绪。模型提供方正在响应。 AetherLink Runtime 中介设备请求。模型提供方保持私有。",
                "运行时概览 运行时概览。状态 未知状态。无概览详情 无其他指引"
            ),
            (
                "fr",
                "Vue d’ensemble du runtime Prêt pour les appareils. État Prêt. Le fournisseur de modèles répond. AetherLink Runtime médie les requêtes des appareils. Les fournisseurs de modèles restent privés.",
                "Vue d’ensemble du runtime Vue d’ensemble du runtime. État État inconnu. Aucun détail d’aperçu Aucune indication supplémentaire"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    runtimeOverviewAccessibilityLabel(
                        title: NSLocalizedString("Ready for Devices", comment: ""),
                        status: NSLocalizedString("Ready", comment: ""),
                        detail: NSLocalizedString("Model provider is responding.", comment: ""),
                        footnote: NSLocalizedString("AetherLink Runtime mediates device requests. Model providers stay private.", comment: "")
                    ),
                    expectation.label
                )
                XCTAssertEqual(
                    runtimeOverviewAccessibilityLabel(title: " ", status: " ", detail: " ", footnote: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testStatusCardAccessibilityLabelUsesTitleStatusAndDetail() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Status Runtime. Current state Ready. Ready for paired devices.",
                "Status Status item. Current state Unknown status. No status details"
            ),
            (
                "ko",
                "상태 카드 런타임. 현재 상태 준비됨. 페어링된 기기 연결 준비됨.",
                "상태 카드 상태 항목. 현재 상태 알 수 없음. 상태 세부 정보 없음"
            ),
            (
                "ja",
                "ステータスカード ランタイム。現在の状態 準備完了。ペアリング済みデバイスの準備完了。",
                "ステータスカード ステータス項目。現在の状態 不明な状態。ステータス詳細なし"
            ),
            (
                "zh-Hans",
                "状态卡 运行时。当前状态 就绪。已准备好连接已配对设备。",
                "状态卡 状态项。当前状态 未知状态。无状态详情"
            ),
            (
                "fr",
                "État Runtime. État actuel Prêt. Prêt pour les appareils jumelés.",
                "État Élément d’état. État actuel État inconnu. Aucun détail d’état"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    statusCardAccessibilityLabel(
                        title: NSLocalizedString("Runtime", comment: ""),
                        value: NSLocalizedString("Ready", comment: ""),
                        detail: NSLocalizedString("Ready for paired devices.", comment: "")
                    ),
                    expectation.label
                )
                XCTAssertEqual(
                    statusCardAccessibilityLabel(title: " ", value: " ", detail: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testReadinessRowAccessibilityLabelUsesTitleStatusAndDetail() {
        let expectations: [(languageTag: String, label: String)] = [
            (
                "en",
                "Readiness AetherLink Runtime. Status Ready. Ready for paired devices."
            ),
            (
                "ko",
                "준비 상태 AetherLink 런타임. 상태 준비됨. 페어링된 기기 연결 준비됨."
            ),
            (
                "ja",
                "準備状況 AetherLink ランタイム。ステータス 準備完了。ペアリング済みデバイスの準備完了。"
            ),
            (
                "zh-Hans",
                "就绪情况 AetherLink 运行时。状态 就绪。已准备好连接已配对设备。"
            ),
            (
                "fr",
                "Préparation Runtime AetherLink. État Prêt. Prêt pour les appareils jumelés."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    readinessRowAccessibilityLabel(
                        title: NSLocalizedString("AetherLink Runtime", comment: ""),
                        status: NSLocalizedString("Ready", comment: ""),
                        detail: NSLocalizedString("Ready for paired devices.", comment: "")
                    ),
                    expectation.label
                )
            }
        }
    }

    func testActivityTechnicalDetailsRedactProviderEndpoints() {
        let unsafeDiagnostics = [
            "Model list failed: http://127.0.0.1:11434/api/tags",
            "Model list failed: http://192.168.1.23:11434/api/tags",
            "Provider failed at model-provider.example.test:1234/v1/models",
            "Provider failed at localhost:1234/v1/models",
            "LM Studio URL rejected",
            "Runtime tried /api/chat directly",
        ]

        for diagnostic in unsafeDiagnostics {
            XCTAssertEqual(sanitizedTechnicalDiagnostic(diagnostic), "Provider address hidden.")
        }

        XCTAssertEqual(
            sanitizedTechnicalDiagnostic("Remote route failed: relay.example.test:43171"),
            "Remote route failed: relay.example.test:43171"
        )
    }

    func testActivityTechnicalDetailsRedactRouteSecrets() {
        let diagnostic = "relay_secret=secret route_token=token rs=compact rt=route-token"

        XCTAssertEqual(sanitizedTechnicalDiagnostic(diagnostic), "Sensitive technical detail redacted.")
    }

    func testRouteDiagnosticDisclosureRedactsSensitiveDetails() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("relay_secret=secret route_token=token rs=compact rt=route-token"),
                "Sensitive technical detail redacted."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("Model list failed: http://127.0.0.1:11434/api/tags"),
                "Provider address hidden."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("Remote route failed: relay.example.test:43171"),
                "Remote route failed: relay.example.test:43171"
            )
        }
    }

    func testRouteDiagnosticDisclosureAccessibilityLabelUsesConnectionContext() {
        let expectations: [(languageTag: String, healthLabel: String, resultLabel: String, fallbackLabel: String)] = [
            ("en", "Details for Connection health", "Details for Connection Recovery result", "Details for Connection diagnostics"),
            ("ko", "연결 상태의 세부 정보", "연결 복구 결과의 세부 정보", "연결 진단의 세부 정보"),
            ("ja", "接続状態 の詳細", "接続の復旧結果 の詳細", "接続診断 の詳細"),
            ("zh-Hans", "连接状态 的详情", "连接恢复结果 的详情", "连接诊断 的详情"),
            ("fr", "Détails pour État de connexion", "Détails pour Résultat de récupération de connexion", "Détails pour Diagnostics de connexion"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    routeDiagnosticDisclosureAccessibilityLabel(
                        context: NSLocalizedString("Connection health", comment: "")
                    ),
                    expectation.healthLabel
                )
                XCTAssertEqual(
                    routeDiagnosticDisclosureAccessibilityLabel(
                        context: NSLocalizedString("Connection Recovery result", comment: "")
                    ),
                    expectation.resultLabel
                )
                XCTAssertEqual(
                    routeDiagnosticDisclosureAccessibilityLabel(context: "   "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testConnectionRecoveryAndRouteDiagnosticDisclosuresExposeLocalizedExpandedState() {
        let expectations: [(
            languageTag: String,
            recoveryLabel: String,
            recoveryExpanded: String,
            recoveryCollapsed: String,
            recoveryHint: String,
            diagnosticExpanded: String,
            diagnosticCollapsed: String,
            diagnosticHint: String
        )] = [
            (
                "en",
                "Connection Recovery settings",
                "Connection Recovery settings expanded",
                "Connection Recovery settings collapsed",
                "Show or hide advanced connection recovery fields.",
                "Connection diagnostics expanded",
                "Connection diagnostics collapsed",
                "Show or hide connection diagnostic details."
            ),
            (
                "ko",
                "연결 복구 설정",
                "연결 복구 설정 펼쳐짐",
                "연결 복구 설정 접힘",
                "고급 연결 복구 필드를 표시하거나 숨깁니다.",
                "연결 진단 펼쳐짐",
                "연결 진단 접힘",
                "연결 진단 세부 정보를 표시하거나 숨깁니다."
            ),
            (
                "ja",
                "接続の復旧設定",
                "接続の復旧設定は展開済み",
                "接続の復旧設定は折りたたみ済み",
                "高度な接続の復旧フィールドを表示または非表示にします。",
                "接続診断は展開済み",
                "接続診断は折りたたみ済み",
                "接続診断の詳細を表示または非表示にします。"
            ),
            (
                "zh-Hans",
                "连接恢复设置",
                "连接恢复设置已展开",
                "连接恢复设置已折叠",
                "显示或隐藏高级连接恢复字段。",
                "连接诊断已展开",
                "连接诊断已折叠",
                "显示或隐藏连接诊断详情。"
            ),
            (
                "fr",
                "Réglages de récupération de connexion",
                "Réglages de récupération de connexion développés",
                "Réglages de récupération de connexion réduits",
                "Afficher ou masquer les champs avancés de récupération de connexion.",
                "Diagnostics de connexion développés",
                "Diagnostics de connexion réduits",
                "Afficher ou masquer les détails de diagnostic de connexion."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(connectionRecoveryDisclosureAccessibilityLabel(), expectation.recoveryLabel)
                XCTAssertEqual(
                    connectionRecoveryDisclosureAccessibilityValue(isExpanded: true),
                    expectation.recoveryExpanded
                )
                XCTAssertEqual(
                    connectionRecoveryDisclosureAccessibilityValue(isExpanded: false),
                    expectation.recoveryCollapsed
                )
                XCTAssertEqual(connectionRecoveryDisclosureAccessibilityHint(), expectation.recoveryHint)
                XCTAssertEqual(
                    routeDiagnosticDisclosureAccessibilityValue(isExpanded: true),
                    expectation.diagnosticExpanded
                )
                XCTAssertEqual(
                    routeDiagnosticDisclosureAccessibilityValue(isExpanded: false),
                    expectation.diagnosticCollapsed
                )
                XCTAssertEqual(routeDiagnosticDisclosureAccessibilityHint(), expectation.diagnosticHint)
            }
        }
    }

    func testConnectionRecoveryFormFieldAccessibilityValuesUseSelectedLanguageAndHideSecrets() {
        let secretToken = "relay-token-should-not-be-read"
        let routeSecret = "route-secret-should-not-be-read"
        let expectations: [(languageTag: String, empty: String, entered: String, optional: String, generated: String)] = [
            ("en", "Empty", "Entered", "Optional", "Created automatically if left blank"),
            ("ko", "비어 있음", "입력됨", "선택 사항", "비워두면 자동으로 생성됩니다"),
            ("ja", "空", "入力済み", "任意", "空欄の場合は自動で作成されます"),
            ("zh-Hans", "空", "已输入", "可选", "留空则自动创建"),
            ("fr", "Vide", "Renseigné", "Facultatif", "Créée automatiquement si le champ est vide"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(NSLocalizedString("Bootstrap relay endpoints", comment: ""), localizedConnectionFieldLabel("Bootstrap relay endpoints", expectation.languageTag))
                XCTAssertEqual(NSLocalizedString("Bootstrap allocation token", comment: ""), localizedConnectionFieldLabel("Bootstrap allocation token", expectation.languageTag))
                XCTAssertEqual(NSLocalizedString("Connection address", comment: ""), localizedConnectionFieldLabel("Connection address", expectation.languageTag))
                XCTAssertEqual(NSLocalizedString("Port", comment: ""), localizedConnectionFieldLabel("Port", expectation.languageTag))
                XCTAssertEqual(NSLocalizedString("Connection setup secret", comment: ""), localizedConnectionFieldLabel("Connection setup secret", expectation.languageTag))

                XCTAssertEqual(connectionRecoveryTextFieldAccessibilityValue("   "), expectation.empty)
                XCTAssertEqual(connectionRecoveryTextFieldAccessibilityValue(" relay.example.test:43171 "), "relay.example.test:43171")
                XCTAssertEqual(connectionRecoveryTextFieldAccessibilityValue(" 43171 "), "43171")

                XCTAssertEqual(connectionRecoveryOptionalSecureFieldAccessibilityValue(" "), expectation.optional)
                XCTAssertEqual(connectionRecoveryOptionalSecureFieldAccessibilityValue(secretToken), expectation.entered)
                XCTAssertFalse(connectionRecoveryOptionalSecureFieldAccessibilityValue(secretToken).contains(secretToken))

                XCTAssertEqual(connectionRecoveryGeneratedSecretAccessibilityValue(" "), expectation.generated)
                XCTAssertEqual(connectionRecoveryGeneratedSecretAccessibilityValue(routeSecret), expectation.entered)
                XCTAssertFalse(connectionRecoveryGeneratedSecretAccessibilityValue(routeSecret).contains(routeSecret))
            }
        }
    }

    func testConnectionRecoveryGenerateLatestQRActionAccessibilityUsesSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            ready: String,
            unavailable: String,
            readyHint: String,
            routeNotReadyHint: String,
            missingActionHint: String
        )] = [
            (
                "en",
                "Ready",
                "Unavailable",
                "Generate the latest pairing QR with saved connection details.",
                "Connection details are not ready for QR generation. Check Connection Recovery settings.",
                "Latest QR generation is unavailable from this view."
            ),
            (
                "ko",
                "준비됨",
                "사용 불가",
                "저장된 연결 정보로 최신 페어링 QR을 생성합니다.",
                "QR 생성을 위한 연결 정보가 준비되지 않았습니다. 연결 복구 설정을 확인하세요.",
                "이 화면에서는 최신 QR을 생성할 수 없습니다."
            ),
            (
                "ja",
                "準備完了",
                "利用不可",
                "保存済みの接続情報で最新のペアリング QR を生成します。",
                "QR 生成用の接続情報は準備できていません。接続の復旧設定を確認してください。",
                "この画面では最新の QR を生成できません。"
            ),
            (
                "zh-Hans",
                "就绪",
                "不可用",
                "使用已保存的连接信息生成最新配对二维码。",
                "用于生成二维码的连接信息尚未就绪。请检查连接恢复设置。",
                "此视图无法生成最新二维码。"
            ),
            (
                "fr",
                "Prêt",
                "Indisponible",
                "Générer le dernier QR de jumelage avec les informations de connexion enregistrées.",
                "Les informations de connexion ne sont pas prêtes pour générer le QR. Vérifiez les réglages de récupération de connexion.",
                "La génération du dernier QR n'est pas disponible depuis cette vue."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoveryGenerateLatestQRActionAccessibilityValue(isRouteReadyForQRCode: true),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryGenerateLatestQRActionAccessibilityValue(isRouteReadyForQRCode: false),
                    expectation.unavailable,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryGenerateLatestQRActionAccessibilityValue(
                        isRouteReadyForQRCode: true,
                        hasAction: false
                    ),
                    expectation.unavailable,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryGenerateLatestQRActionAccessibilityHint(isRouteReadyForQRCode: true),
                    expectation.readyHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryGenerateLatestQRActionAccessibilityHint(isRouteReadyForQRCode: false),
                    expectation.routeNotReadyHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryGenerateLatestQRActionAccessibilityHint(
                        isRouteReadyForQRCode: true,
                        hasAction: false
                    ),
                    expectation.missingActionHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testConnectionRecoveryFallbackActionAccessibilityHintsUseSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            saveBootstrapRelayHint: String,
            saveConnectionHint: String,
            rotateSecretHint: String
        )] = [
            (
                "en",
                "Save bootstrap relay settings for future pairing QR connection details.",
                "Save fallback connection details for future pairing QR routes.",
                "Create a new connection setup secret for future pairing QR connection details."
            ),
            (
                "ko",
                "향후 페어링 QR 연결 정보에 사용할 부트스트랩 릴레이 설정을 저장합니다.",
                "향후 페어링 QR 경로에 사용할 예비 연결 정보를 저장합니다.",
                "향후 페어링 QR 연결 정보에 사용할 새 연결 설정 비밀값을 생성합니다."
            ),
            (
                "ja",
                "今後のペアリング QR 接続情報に使うブートストラップリレー設定を保存します。",
                "今後のペアリング QR ルートに使うフォールバック接続情報を保存します。",
                "今後のペアリング QR 接続情報に使う新しい接続設定シークレットを作成します。"
            ),
            (
                "zh-Hans",
                "保存用于后续配对二维码连接信息的引导中继设置。",
                "保存用于后续配对二维码路径的备用连接信息。",
                "创建用于后续配对二维码连接信息的新连接设置密钥。"
            ),
            (
                "fr",
                "Enregistre les réglages du relais d’amorçage pour les futures informations de connexion du QR de jumelage.",
                "Enregistre les informations de connexion de secours pour les futurs itinéraires QR de jumelage.",
                "Crée un nouveau secret de configuration de connexion pour les futurs QR de jumelage."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoverySaveBootstrapRelayActionAccessibilityHint(),
                    expectation.saveBootstrapRelayHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoverySaveConnectionActionAccessibilityHint(),
                    expectation.saveConnectionHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryRotateSecretActionAccessibilityHint(),
                    expectation.rotateSecretHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testConnectionRecoverySaveConnectionAccessibilityValueExplainsInvalidInputs() {
        let expectations: [(
            languageTag: String,
            ready: String,
            missingAddress: String,
            invalidAddress: String,
            invalidPort: String
        )] = [
            (
                "en",
                "Ready",
                "Enter a connection address.",
                "Enter only the connection address. Put the port in the Port field.",
                "Enter a valid connection port."
            ),
            (
                "ko",
                "준비됨",
                "연결 주소를 입력하세요.",
                "연결 주소만 입력하세요. 포트는 포트 필드에 입력하세요.",
                "올바른 연결 포트를 입력하세요."
            ),
            (
                "ja",
                "準備完了",
                "接続アドレスを入力してください。",
                "接続アドレスだけを入力してください。ポートはポート欄に入力してください。",
                "有効な接続ポートを入力してください。"
            ),
            (
                "zh-Hans",
                "就绪",
                "请输入连接地址。",
                "只输入连接地址。端口请填入端口字段。",
                "请输入有效的连接端口。"
            ),
            (
                "fr",
                "Prêt",
                "Saisissez une adresse de connexion.",
                "Saisissez uniquement l'adresse de connexion. Indiquez le port dans le champ Port.",
                "Saisissez un port de connexion valide."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoverySaveConnectionActionAccessibilityValue(host: "relay.example.test", port: "43171"),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoverySaveConnectionActionAccessibilityValue(host: "   ", port: "43171"),
                    expectation.missingAddress,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoverySaveConnectionActionAccessibilityValue(host: "relay.example.test:43171", port: "43171"),
                    expectation.invalidAddress,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoverySaveConnectionActionAccessibilityValue(host: "relay.example.test", port: "not-a-port"),
                    expectation.invalidPort,
                    expectation.languageTag
                )
            }
        }
    }

    func testRelayStatusRowAccessibilityLabelUsesTitleStatusAndDetail() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Connection setting Connection route. Status Reachable connection. Connection details can be included.",
                "Connection setting Connection setting. Status Not checked. No details available."
            ),
            (
                "ko",
                "연결 설정 연결 경로. 상태 Reachable connection. Connection details can be included.",
                "연결 설정 연결 설정. 상태 확인 전. 사용 가능한 세부 정보가 없습니다."
            ),
            (
                "ja",
                "接続設定 接続ルート。ステータス Reachable connection。Connection details can be included.",
                "接続設定 接続設定。ステータス 未確認。利用できる詳細はありません。"
            ),
            (
                "zh-Hans",
                "连接设置 连接路由。状态 Reachable connection。Connection details can be included.",
                "连接设置 连接设置。状态 未检查。没有可用详情。"
            ),
            (
                "fr",
                "Paramètre de connexion Route de connexion. État Reachable connection. Connection details can be included.",
                "Paramètre de connexion Paramètre de connexion. État Non vérifié. Aucun détail disponible."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    relayStatusRowAccessibilityLabel(
                        title: NSLocalizedString("Connection route", comment: ""),
                        value: " Reachable connection ",
                        detail: " Connection details can be included. "
                    ),
                    expectation.label
                )
                XCTAssertEqual(
                    relayStatusRowAccessibilityLabel(title: " ", value: " ", detail: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testDisableConnectionAccessibilityLabelUsesRouteContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Disable saved connection details for relay.example.test:43171",
                "Disable saved connection details for saved connection"
            ),
            (
                "ko",
                "relay.example.test:43171 정보 끄기",
                "저장된 연결 정보 끄기"
            ),
            (
                "ja",
                "relay.example.test:43171 の保存済み接続情報を無効化",
                "保存済みの接続 の保存済み接続情報を無効化"
            ),
            (
                "zh-Hans",
                "禁用 relay.example.test:43171 的已保存连接信息",
                "禁用 已保存的连接 的已保存连接信息"
            ),
            (
                "fr",
                "Désactiver les informations de connexion enregistrées pour relay.example.test:43171",
                "Désactiver les informations de connexion enregistrées pour connexion enregistrée"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    disableConnectionAccessibilityLabel(endpoint: " relay.example.test:43171 "),
                    expectation.label
                )
                XCTAssertEqual(
                    disableConnectionAccessibilityLabel(endpoint: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testProviderStatusTechnicalDetailsRedactEndpointsButKeepSafeFields() {
        XCTAssertEqual(
            providerStatusDiagnosticDetail(
                message: "Model list failed: http://192.168.1.23:11434/api/tags",
                code: "backend_unavailable",
                retryable: true
            ),
            [
                "Provider address hidden.",
                "code=backend_unavailable",
                "retryable=true",
            ].joined(separator: "\n")
        )
    }

    func testProviderStatusTechnicalDetailsRedactUnsafeCodes() {
        XCTAssertEqual(
            providerStatusDiagnosticDetail(
                message: "Remote route failed: relay.example.test:43171",
                code: "route_token=secret",
                retryable: false
            ),
            [
                "Remote route failed: relay.example.test:43171",
                "code=Sensitive technical detail redacted.",
                "retryable=false",
            ].joined(separator: "\n")
        )
    }

    func testProviderStatusTechnicalDetailsAccessibilityLabelUsesProviderContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Details for Ollama",
                "Details for Model provider"
            ),
            (
                "ko",
                "Ollama의 세부 정보",
                "모델 제공자의 세부 정보"
            ),
            (
                "ja",
                "Ollama の詳細",
                "モデルプロバイダー の詳細"
            ),
            (
                "zh-Hans",
                "Ollama 的详情",
                "模型提供方 的详情"
            ),
            (
                "fr",
                "Détails pour Ollama",
                "Détails pour Fournisseur de modèles"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    providerStatusTechnicalDetailsAccessibilityLabel(providerName: " Ollama "),
                    expectation.label
                )
                XCTAssertEqual(
                    providerStatusTechnicalDetailsAccessibilityLabel(providerName: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testProviderStatusTechnicalDetailsAccessibilityStateUsesSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            expandedValue: String,
            collapsedValue: String,
            expandedHint: String,
            collapsedHint: String
        )] = [
            (
                "en",
                "Provider details expanded",
                "Provider details collapsed",
                "Collapse to hide provider details.",
                "Expand to show provider details."
            ),
            (
                "ko",
                "제공자 세부 정보 펼쳐짐",
                "제공자 세부 정보 접힘",
                "제공자 세부 정보를 숨기려면 접으세요.",
                "제공자 세부 정보를 보려면 펼치세요."
            ),
            (
                "ja",
                "プロバイダー詳細は展開済み",
                "プロバイダー詳細は折りたたみ済み",
                "プロバイダー詳細を非表示にするには折りたたみます。",
                "プロバイダー詳細を表示するには展開します。"
            ),
            (
                "zh-Hans",
                "提供方详情已展开",
                "提供方详情已折叠",
                "折叠以隐藏提供方详情。",
                "展开以显示提供方详情。"
            ),
            (
                "fr",
                "Détails du fournisseur développés",
                "Détails du fournisseur réduits",
                "Réduire pour masquer les détails du fournisseur.",
                "Développer pour afficher les détails du fournisseur."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    providerStatusTechnicalDetailsAccessibilityValue(isExpanded: true),
                    expectation.expandedValue,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    providerStatusTechnicalDetailsAccessibilityValue(isExpanded: false),
                    expectation.collapsedValue,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    providerStatusTechnicalDetailsAccessibilityHint(isExpanded: true),
                    expectation.expandedHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    providerStatusTechnicalDetailsAccessibilityHint(isExpanded: false),
                    expectation.collapsedHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testProviderStatusPillAccessibilityLabelUsesProviderContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Provider Ollama status Available",
                "Provider Model provider status Not checked"
            ),
            (
                "ko",
                "Ollama 상태 사용 가능",
                "모델 제공자 상태 확인 전"
            ),
            (
                "ja",
                "Ollama の状態 利用可能",
                "モデルプロバイダー の状態 未確認"
            ),
            (
                "zh-Hans",
                "Ollama 状态 可用",
                "模型提供方 状态 未检查"
            ),
            (
                "fr",
                "État de Ollama : Disponible",
                "État de Fournisseur de modèles : Non vérifié"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    providerStatusPillAccessibilityLabel(
                        providerName: " Ollama ",
                        status: NSLocalizedString("Available", comment: "")
                    ),
                    expectation.label
                )
                XCTAssertEqual(
                    providerStatusPillAccessibilityLabel(providerName: " ", status: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testTrustedDeviceKeyFingerprintUsesPublicKeyHashOnly() {
        XCTAssertEqual(trustedDeviceKeyFingerprint(" aGVsbG8= "), "2C:F2:4D:BA:5F:B0")
    }

    func testTrustedDeviceRemovalMessageUsesSelectedLanguageAndKeyFingerprint() {
        let device = TrustedDevice(
            id: "device-1",
            name: "Pixel",
            publicKeyBase64: "aGVsbG8=",
            pairedAt: Date(timeIntervalSince1970: 0)
        )
        let expectations: [(languageTag: String, message: String, fallbackMessage: String)] = [
            (
                "en",
                "Pixel will need to pair again before it can use AetherLink Runtime. Key fingerprint 2C:F2:4D:BA:5F:B0",
                "Selected device will need to pair again before it can use AetherLink Runtime. Key fingerprint Unavailable"
            ),
            (
                "ko",
                "Pixel은(는) AetherLink Runtime을 다시 사용하려면 다시 페어링해야 합니다. 키 지문 2C:F2:4D:BA:5F:B0",
                "선택한 항목은(는) AetherLink Runtime을 다시 사용하려면 다시 페어링해야 합니다. 키 지문 사용 불가"
            ),
            (
                "ja",
                "Pixel は AetherLink Runtime を使用する前に再度ペアリングが必要です。キー指紋 2C:F2:4D:BA:5F:B0",
                "選択したデバイス は AetherLink Runtime を使用する前に再度ペアリングが必要です。キー指紋 利用不可"
            ),
            (
                "zh-Hans",
                "Pixel 需要重新配对后才能使用 AetherLink Runtime。密钥指纹 2C:F2:4D:BA:5F:B0",
                "所选设备 需要重新配对后才能使用 AetherLink Runtime。密钥指纹 不可用"
            ),
            (
                "fr",
                "Pixel devra être jumelé à nouveau avant de pouvoir utiliser AetherLink Runtime. Empreinte de clé 2C:F2:4D:BA:5F:B0",
                "Appareil sélectionné devra être jumelé à nouveau avant de pouvoir utiliser AetherLink Runtime. Empreinte de clé Indisponible"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(trustedDeviceRemovalMessage(for: device), expectation.message)
                XCTAssertEqual(trustedDeviceRemovalMessage(for: nil), expectation.fallbackMessage)
            }
        }
    }

    func testTrustedDeviceConfirmRemoveActionAccessibilityLabelUsesDeviceContext() {
        let device = TrustedDevice(
            id: "device-1",
            name: "Pixel",
            publicKeyBase64: "aGVsbG8=",
            pairedAt: Date(timeIntervalSince1970: 0)
        )
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Confirm removing trust for Pixel. Key fingerprint 2C:F2:4D:BA:5F:B0",
                "Confirm removing trust for Selected device. Key fingerprint Unavailable"
            ),
            (
                "ko",
                "Pixel 신뢰 해제를 확인합니다. 키 지문 2C:F2:4D:BA:5F:B0",
                "선택한 항목 신뢰 해제를 확인합니다. 키 지문 사용 불가"
            ),
            (
                "ja",
                "Pixel の信頼解除を確認。キー指紋 2C:F2:4D:BA:5F:B0",
                "選択したデバイス の信頼解除を確認。キー指紋 利用不可"
            ),
            (
                "zh-Hans",
                "确认移除 Pixel 的信任。密钥指纹 2C:F2:4D:BA:5F:B0",
                "确认移除 所选设备 的信任。密钥指纹 不可用"
            ),
            (
                "fr",
                "Confirmer le retrait de l’approbation de Pixel. Empreinte de clé 2C:F2:4D:BA:5F:B0",
                "Confirmer le retrait de l’approbation de Appareil sélectionné. Empreinte de clé Indisponible"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    trustedDeviceConfirmRemoveAccessibilityLabel(for: device),
                    expectation.label
                )
                XCTAssertEqual(
                    trustedDeviceConfirmRemoveAccessibilityLabel(for: nil),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testTrustedDeviceRowAccessibilityLabelUsesDeviceContext() {
        let date = Date(timeIntervalSince1970: 0)
        let expectations: [(languageTag: String, fallbackLabel: String)] = [
            (
                "en",
                "Trusted device Selected device. Pairing details unavailable. Key fingerprint Unavailable"
            ),
            (
                "ko",
                "신뢰 기기 선택한 항목. 페어링 세부 정보를 사용할 수 없습니다. 키 지문 사용 불가"
            ),
            (
                "ja",
                "信頼済みデバイス 選択したデバイス。ペアリングの詳細は利用できません。キー指紋 利用不可"
            ),
            (
                "zh-Hans",
                "受信任设备 所选设备。配对详情不可用。密钥指纹 不可用"
            ),
            (
                "fr",
                "Appareil approuvé Appareil sélectionné. Détails de jumelage indisponibles. Empreinte de clé Indisponible"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let pairingSummary = String(
                    format: NSLocalizedString("Paired %@. Device ID ending %@", comment: ""),
                    localizedCompanionDateString(from: date),
                    "ice-1"
                )
                let label = trustedDeviceRowAccessibilityLabel(
                    name: " Pixel ",
                    pairedAt: date,
                    deviceID: " ice-1 ",
                    keyFingerprint: " 2C:F2:4D:BA:5F:B0 "
                )

                XCTAssertEqual(
                    trustedDevicePairingAccessibilitySummary(pairedAt: date, deviceID: " ice-1 "),
                    pairingSummary,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    label,
                    String(
                        format: NSLocalizedString("Trusted device %@. %@. Key fingerprint %@", comment: ""),
                        "Pixel",
                        pairingSummary,
                        "2C:F2:4D:BA:5F:B0"
                    ),
                    expectation.languageTag
                )
                XCTAssertFalse(label.contains("·"), expectation.languageTag)
                if expectation.languageTag != "en" {
                    XCTAssertFalse(label.contains("Paired "), expectation.languageTag)
                    XCTAssertFalse(label.contains("ID ending"), expectation.languageTag)
                }
                XCTAssertEqual(
                    trustedDeviceRowAccessibilityLabel(
                        name: " ",
                        pairedAt: nil,
                        deviceID: " ",
                        keyFingerprint: " "
                    ),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testCompanionDateFormattingUsesSelectedAppLanguage() {
        let date = Date(timeIntervalSince1970: 0)

        for language in AetherLinkAppLanguage.allCases {
            withStoredAppLanguage(language.rawValue) {
                let expectedDate = expectedCompanionDateString(from: date, language: language)
                let pairedSummary = String(
                    format: NSLocalizedString("Paired %@ · ID ending %@", comment: ""),
                    localizedCompanionDateString(from: date),
                    "ice-1"
                )

                XCTAssertEqual(localizedCompanionDateString(from: date), expectedDate, language.rawValue)
                XCTAssertTrue(pairedSummary.contains(expectedDate), language.rawValue)
                XCTAssertEqual(
                    trustedDeviceRowAccessibilityLabel(
                        name: "Pixel",
                        pairedAt: date,
                        deviceID: "ice-1",
                        keyFingerprint: "2C:F2:4D:BA:5F:B0"
                    ),
                    String(
                        format: NSLocalizedString("Trusted device %@. %@. Key fingerprint %@", comment: ""),
                        "Pixel",
                        trustedDevicePairingAccessibilitySummary(pairedAt: date, deviceID: "ice-1"),
                        "2C:F2:4D:BA:5F:B0"
                    ),
                    language.rawValue
                )
            }
        }
    }

    func testCompanionByteCountFormattingUsesSelectedAppLanguage() {
        let byteCount: Int64 = 4_700_000_000

        for language in AetherLinkAppLanguage.allCases {
            withStoredAppLanguage(language.rawValue) {
                let expectedSize = expectedCompanionByteCountString(
                    fromByteCount: byteCount,
                    language: language
                )

                XCTAssertEqual(
                    localizedCompanionByteCountString(fromByteCount: byteCount),
                    expectedSize,
                    language.rawValue
                )
                XCTAssertEqual(
                    modelRowAccessibilityLabel(
                        name: "Llama 3",
                        identifier: "llama3:8b",
                        kind: NSLocalizedString("Chat", comment: ""),
                        provider: NSLocalizedString("Ollama", comment: ""),
                        source: NSLocalizedString("Local", comment: ""),
                        running: true,
                        size: localizedCompanionByteCountString(fromByteCount: byteCount)
                    ),
                    String(
                        format: NSLocalizedString(
                            "Model %@. ID %@. Type %@. Provider %@. Source %@. State %@. Size %@",
                            comment: ""
                        ),
                        "Llama 3",
                        "llama3:8b",
                        NSLocalizedString("Chat", comment: ""),
                        NSLocalizedString("Ollama", comment: ""),
                        NSLocalizedString("Local", comment: ""),
                        NSLocalizedString("Running", comment: ""),
                        expectedSize
                    ),
                    language.rawValue
                )
            }
        }
    }

    func testTrustedDeviceRemoveButtonAccessibilityLabelUsesDeviceContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Remove trust for Pixel. Key fingerprint 2C:F2:4D:BA:5F:B0",
                "Remove trust for Selected device. Key fingerprint Unavailable"
            ),
            (
                "ko",
                "Pixel 신뢰 해제. 키 지문 2C:F2:4D:BA:5F:B0",
                "선택한 항목 신뢰 해제. 키 지문 사용 불가"
            ),
            (
                "ja",
                "Pixel の信頼を解除。キー指紋 2C:F2:4D:BA:5F:B0",
                "選択したデバイス の信頼を解除。キー指紋 利用不可"
            ),
            (
                "zh-Hans",
                "移除 Pixel 的信任。密钥指纹 2C:F2:4D:BA:5F:B0",
                "移除 所选设备 的信任。密钥指纹 不可用"
            ),
            (
                "fr",
                "Retirer l’approbation de Pixel. Empreinte de clé 2C:F2:4D:BA:5F:B0",
                "Retirer l’approbation de Appareil sélectionné. Empreinte de clé Indisponible"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    trustedDeviceRemoveAccessibilityLabel(name: " Pixel ", keyFingerprint: " 2C:F2:4D:BA:5F:B0 "),
                    expectation.label
                )
                XCTAssertEqual(
                    trustedDeviceRemoveAccessibilityLabel(name: " ", keyFingerprint: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testTrustedDeviceRefreshActionAccessibilityUsesSelectedLanguage() {
        let expectations: [(languageTag: String, value: String, hint: String)] = [
            (
                "en",
                "Ready",
                "Refresh trusted devices from AetherLink Runtime."
            ),
            (
                "ko",
                "준비됨",
                "AetherLink Runtime에서 신뢰 기기 목록을 새로고침합니다."
            ),
            (
                "ja",
                "準備完了",
                "AetherLink Runtime から信頼済みデバイスを更新します。"
            ),
            (
                "zh-Hans",
                "就绪",
                "从 AetherLink Runtime 刷新受信任设备。"
            ),
            (
                "fr",
                "Prêt",
                "Actualise les appareils approuvés depuis AetherLink Runtime."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(trustedDeviceRefreshActionAccessibilityValue(), expectation.value)
                XCTAssertEqual(trustedDeviceRefreshActionAccessibilityHint(), expectation.hint)
            }
        }
    }

    func testRemoteRoutePreparationIssueCopyIsActionableForRejectedRoute() {
        withStoredAppLanguage("en") {
            let issue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationRejected,
                endpoint: "192.168.50.10:43171",
                message: "This AetherLink Runtime connection address is not reachable from another network."
            )

            XCTAssertEqual(
                remoteRoutePreparationIssueText(issue),
                "Connection details for 192.168.50.10:43171 cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR."
            )
        }
    }

    func testRemoteRoutePreparationIssueCopyUsesSelectedLocalizationAndRedactsSensitiveEndpoint() {
        withStoredAppLanguage("ko") {
            let issue = CompanionRemoteRoutePreparationIssue(
                kind: .automaticPreparationRejected,
                endpoint: "relay_secret=secret route_token=token",
                message: "pairing_secret=secret"
            )
            let copy = remoteRoutePreparationIssueText(issue)

            XCTAssertEqual(
                copy,
                "연결 정보는 다른 네트워크에서 사용할 수 없습니다. 공용, VPN 또는 릴레이 주소를 사용한 뒤 새 QR을 생성하세요."
            )
            XCTAssertFalse(copy.contains("relay_secret"))
            XCTAssertFalse(copy.contains("route_token"))
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("relay_secret=secret route_token=token"),
                "민감한 기술 세부정보가 숨겨졌습니다."
            )
        }
    }

    func testRemoteRoutePreparationIssueCopyIsActionableForRelayFailure() {
        withStoredAppLanguage("en") {
            let issue = CompanionRemoteRoutePreparationIssue(
                kind: .relayConnectionFailed,
                endpoint: "relay.example.test:43171",
                message: "Connection refused"
            )

            XCTAssertEqual(
                remoteRoutePreparationIssueText(issue),
                "Connection through relay.example.test:43171 failed. Check Connection Recovery, then generate a fresh QR."
            )
        }
    }

    func testRemoteRoutePreparationIssueCopyCoversRoutePreparationFailures() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                remoteRoutePreparationIssueText(
                    CompanionRemoteRoutePreparationIssue(
                        kind: .automaticPreparationUnavailable,
                        message: "Route service unavailable"
                    )
                ),
                "AetherLink could not get connection details from the route service. Check Connection Recovery, then generate a fresh QR."
            )
            XCTAssertEqual(
                remoteRoutePreparationIssueText(
                    CompanionRemoteRoutePreparationIssue(
                        kind: .automaticPreparationFailed,
                        endpoint: "relay.example.test:43171",
                        message: "Connection refused"
                    )
                ),
                "Connection details for relay.example.test:43171 could not be prepared automatically. Check Connection Recovery, then generate a fresh QR."
            )
            XCTAssertEqual(
                remoteRoutePreparationIssueText(
                    CompanionRemoteRoutePreparationIssue(
                        kind: .routeLeaseRefreshFailed,
                        message: "Lease expired"
                    )
                ),
                "Connection details could not be prepared automatically. Check Connection Recovery, then generate a fresh QR."
            )
            XCTAssertEqual(
                remoteRoutePreparationIssueText(
                    CompanionRemoteRoutePreparationIssue(
                        kind: .routeLeaseSecretMissing,
                        endpoint: "relay.example.test:43171",
                        message: "Route secret is missing."
                    )
                ),
                "Connection details need a secure connection secret before they can be included in a QR."
            )
            XCTAssertEqual(
                remoteRoutePreparationIssueText(
                    CompanionRemoteRoutePreparationIssue(
                        kind: .relayConnectionFailed,
                        message: "Connection refused"
                    )
                ),
                "Connection failed. Check Connection Recovery, then generate a fresh QR."
            )
        }
    }

    func testConnectionRecoveryPrivateOverlayToggleAccessibilityDistinguishesRouteContext() {
        let expectations: [(
            languageTag: String,
            bootstrapLabel: String,
            fallbackLabel: String,
            enabledValue: String,
            disabledValue: String,
            bootstrapHint: String,
            fallbackHint: String
        )] = [
            (
                "en",
                "Bootstrap relay Private Overlay Route",
                "Fallback connection Private Overlay Route",
                "Enabled",
                "Disabled",
                "Enable only when this bootstrap relay is reachable through a VPN, tunnel, or private overlay shared by both devices.",
                "Enable only when this private address is reachable through a VPN, tunnel, or private overlay shared by both devices."
            ),
            (
                "ko",
                "부트스트랩 릴레이 사설 오버레이 경로",
                "예비 연결 사설 오버레이 경로",
                "켜짐",
                "꺼짐",
                "두 기기가 공유하는 VPN, 터널 또는 프라이빗 오버레이를 통해 이 부트스트랩 릴레이에 접근할 수 있을 때만 켜세요.",
                "이 사설 주소가 두 기기에서 공유하는 VPN, 터널 또는 사설 오버레이를 통해 접근 가능할 때만 켜세요."
            ),
            (
                "ja",
                "ブートストラップリレーのプライベートオーバーレイルート",
                "フォールバック接続のプライベートオーバーレイルート",
                "オン",
                "オフ",
                "両方のデバイスで共有する VPN、トンネル、またはプライベートオーバーレイ経由でこのブートストラップリレーに到達できる場合のみ有効にしてください。",
                "このプライベートアドレスが、両方のデバイスで共有する VPN、トンネル、またはプライベートオーバーレイ経由で到達できる場合にのみ有効にしてください。"
            ),
            (
                "zh-Hans",
                "引导中继私有覆盖路由",
                "备用连接私有覆盖路由",
                "已启用",
                "已关闭",
                "仅当两台设备通过共享的 VPN、隧道或私有覆盖网络可访问此引导中继时启用。",
                "仅当此私有地址可通过两个设备共享的 VPN、隧道或私有覆盖网络访问时启用。"
            ),
            (
                "fr",
                "Route en superposition privée du relais d’amorçage",
                "Route en superposition privée de la connexion de secours",
                "Activé",
                "Désactivé",
                "Activez ceci uniquement lorsque ce relais d’amorçage est joignable via un VPN, un tunnel ou un overlay privé partagé par les deux appareils.",
                "Activez cette option uniquement si cette adresse privée est joignable via un VPN, un tunnel ou une superposition privée partagée par les deux appareils."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel(),
                    expectation.bootstrapLabel
                )
                XCTAssertEqual(
                    connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel(),
                    expectation.fallbackLabel
                )
                XCTAssertNotEqual(
                    connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel(),
                    connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel()
                )
                XCTAssertEqual(
                    connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: true),
                    expectation.enabledValue
                )
                XCTAssertEqual(
                    connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: false),
                    expectation.disabledValue
                )
                XCTAssertEqual(
                    NSLocalizedString("Enable only when this bootstrap relay is reachable through a VPN, tunnel, or private overlay shared by both devices.", comment: ""),
                    expectation.bootstrapHint
                )
                XCTAssertEqual(
                    NSLocalizedString("Enable only when this private address is reachable through a VPN, tunnel, or private overlay shared by both devices.", comment: ""),
                    expectation.fallbackHint
                )
            }
        }
    }

    func testRemoteRouteScopeCopyDistinguishesAutomaticRemoteAndLocalRoutes() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                remoteRouteScopeLabel(
                    settings: .disabled,
                    bootstrapSettings: CompanionBootstrapRelaySettings(isEnabled: true, endpoints: "relay.example.test:43171"),
                    canPrepareAutomatically: false
                ),
                "Automatic route"
            )
            XCTAssertEqual(
                remoteRouteScopeDetail(
                    settings: .disabled,
                    bootstrapSettings: CompanionBootstrapRelaySettings(isEnabled: true, endpoints: "relay.example.test:43171"),
                    canPrepareAutomatically: false
                ),
                "AetherLink will request fresh QR connection details from the saved bootstrap relay."
            )

            let remoteSettings = CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: "relay.example.test",
                port: 43171,
                relayID: "relay-1",
                relaySecret: "secret-1"
            )
            XCTAssertEqual(
                remoteRouteScopeLabel(
                    settings: remoteSettings,
                    bootstrapSettings: .disabled,
                    canPrepareAutomatically: false
                ),
                "Reachable connection"
            )
            XCTAssertEqual(
                remoteRouteScopeDetail(
                    settings: remoteSettings,
                    bootstrapSettings: .disabled,
                    canPrepareAutomatically: false
                ),
                "Connection details can be included in QR for devices outside this local network."
            )

            let privateSettings = CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: "192.168.0.102",
                port: 43171,
                relayID: "relay-1",
                relaySecret: "secret-1"
            )
            XCTAssertEqual(
                remoteRouteScopeLabel(
                    settings: privateSettings,
                    bootstrapSettings: .disabled,
                    canPrepareAutomatically: false
                ),
                "Local network only"
            )
            XCTAssertEqual(
                remoteRouteScopeDetail(
                    settings: privateSettings,
                    bootstrapSettings: .disabled,
                    canPrepareAutomatically: false
                ),
                "Private addresses usually do not cross unrelated networks. Use a reachable relay, VPN, tunnel, or private overlay."
            )

            let overlaySettings = CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: "192.168.0.102",
                port: 43171,
                relayID: "relay-1",
                relaySecret: "secret-1",
                allowsPrivateOverlay: true
            )
            XCTAssertEqual(
                remoteRouteScopeLabel(
                    settings: overlaySettings,
                    bootstrapSettings: .disabled,
                    canPrepareAutomatically: false
                ),
                "Private overlay"
            )
            XCTAssertEqual(
                remoteRouteScopeDetail(
                    settings: overlaySettings,
                    bootstrapSettings: .disabled,
                    canPrepareAutomatically: false
                ),
                "Use this only when both devices can reach the same VPN, tunnel, or private overlay."
            )
        }
    }

    func testRelayQRCodeReadinessCopyUsesPreparedButStoppedState() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                relayQRCodeReadinessText(
                    settings: relayQRCodeReadinessSettings(),
                    isEligibleForQRCode: true,
                    isPreparedForQRCode: true,
                    connectionStatus: CompanionDevelopmentRelayStatus(
                        status: .stopped,
                        endpoint: "relay.example.test:43171"
                    )
                ),
                "Connection details are prepared, but the connection is stopped. Start AetherLink Runtime, then generate the latest QR."
            )
        }
    }

    func testRelayQRCodeReadinessCopyUsesPreparedButConnectingState() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                relayQRCodeReadinessText(
                    settings: relayQRCodeReadinessSettings(),
                    isEligibleForQRCode: true,
                    isPreparedForQRCode: true,
                    connectionStatus: CompanionDevelopmentRelayStatus(
                        status: .connecting,
                        endpoint: "relay.example.test:43171"
                    )
                ),
                "Connection details are prepared. AetherLink Runtime is connecting; generate the latest QR after the connection is ready."
            )
        }
    }

    func testRelayQRCodeReadinessCopyUsesPreparedButFailedState() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                relayQRCodeReadinessText(
                    settings: relayQRCodeReadinessSettings(),
                    isEligibleForQRCode: true,
                    isPreparedForQRCode: true,
                    connectionStatus: CompanionDevelopmentRelayStatus(
                        status: .failed("Connection refused"),
                        endpoint: "relay.example.test:43171"
                    )
                ),
                "Connection through relay.example.test:43171 failed. Check Connection Recovery, then generate a fresh QR."
            )
        }
    }

    func testRelayQRCodeReadinessCopyUsesReadyState() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                relayQRCodeReadinessText(
                    settings: relayQRCodeReadinessSettings(),
                    isEligibleForQRCode: true,
                    isPreparedForQRCode: true,
                    connectionStatus: CompanionDevelopmentRelayStatus(
                        status: .waitingForPeer,
                        endpoint: "relay.example.test:43171"
                    )
                ),
                "Connection details are ready. Generate the latest QR to pair this device."
            )
        }
    }

    private func localizedConnectionFieldLabel(_ key: String, _ languageTag: String) -> String {
        let labels: [String: [String: String]] = [
            "en": [
                "Bootstrap relay endpoints": "Bootstrap relay endpoints",
                "Bootstrap allocation token": "Bootstrap allocation token",
                "Connection address": "Connection address",
                "Port": "Port",
                "Connection setup secret": "Protected connection key",
            ],
            "ko": [
                "Bootstrap relay endpoints": "부트스트랩 릴레이 엔드포인트",
                "Bootstrap allocation token": "부트스트랩 할당 토큰",
                "Connection address": "연결 주소",
                "Port": "포트",
                "Connection setup secret": "보호된 연결 키",
            ],
            "ja": [
                "Bootstrap relay endpoints": "ブートストラップリレーエンドポイント",
                "Bootstrap allocation token": "ブートストラップ割り当てトークン",
                "Connection address": "接続アドレス",
                "Port": "ポート",
                "Connection setup secret": "保護された接続キー",
            ],
            "zh-Hans": [
                "Bootstrap relay endpoints": "引导中继端点",
                "Bootstrap allocation token": "引导分配令牌",
                "Connection address": "连接地址",
                "Port": "端口",
                "Connection setup secret": "受保护的连接密钥",
            ],
            "fr": [
                "Bootstrap relay endpoints": "Points de terminaison du relais d’amorçage",
                "Bootstrap allocation token": "Jeton d’allocation du relais",
                "Connection address": "Adresse de connexion",
                "Port": "Port",
                "Connection setup secret": "Clé de connexion protégée",
            ],
        ]
        return labels[languageTag]?[key] ?? key
    }

    private func withStoredAppLanguage(_ languageTag: String?, assertions: () -> Void) {
        let previous = UserDefaults.standard.string(forKey: AetherLinkAppLanguageStorageKey)
        if let languageTag {
            UserDefaults.standard.set(languageTag, forKey: AetherLinkAppLanguageStorageKey)
        } else {
            UserDefaults.standard.removeObject(forKey: AetherLinkAppLanguageStorageKey)
        }
        defer {
            if let previous {
                UserDefaults.standard.set(previous, forKey: AetherLinkAppLanguageStorageKey)
            } else {
                UserDefaults.standard.removeObject(forKey: AetherLinkAppLanguageStorageKey)
            }
        }

        assertions()
    }

    private func expectedCompanionDateString(
        from date: Date,
        language: AetherLinkAppLanguage
    ) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: language.localeIdentifier)
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }

    private func expectedCompanionByteCountString(
        fromByteCount byteCount: Int64,
        language: AetherLinkAppLanguage
    ) -> String {
        byteCount.formatted(
            .byteCount(style: .file)
                .locale(Locale(identifier: language.localeIdentifier))
        )
    }

    private func isolatedDefaults() throws -> UserDefaults {
        let suiteName = "dev.aetherlink.localization-tests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }

    private func isolatedRuntimeIdentityEnvironment() -> [String: String] {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-runtime-identity-\(UUID().uuidString).json")
        return ["AETHERLINK_RUNTIME_IDENTITY_FILE": fileURL.path]
    }

    private func relayQRCodeReadinessSettings() -> CompanionDevelopmentRelaySettings {
        CompanionDevelopmentRelaySettings(
            isEnabled: true,
            host: "relay.example.test",
            port: 43171,
            relayID: "relay-1",
            relaySecret: "secret-1"
        )
    }
}
