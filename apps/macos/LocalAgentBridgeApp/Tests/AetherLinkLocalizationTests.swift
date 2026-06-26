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

    func testAppLanguageDefaultsToEnglish() {
        XCTAssertEqual(AetherLinkAppLanguage.defaultLanguage, .english)
        XCTAssertEqual(AetherLinkAppLanguage.normalized(nil), .english)
        XCTAssertEqual(AetherLinkAppLanguage.normalized(""), .english)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("unknown"), .english)
    }

    func testAppLanguageNormalizesSupportedTagsAndChineseAliases() {
        XCTAssertEqual(AetherLinkAppLanguage.normalized(" KO "), .korean)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("ja"), .japanese)
        XCTAssertEqual(AetherLinkAppLanguage.normalized("FR"), .french)
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

    func testPairingQRCodeAccessibilityCopyUsesSelectedLanguageAndState() {
        let expectations: [(languageTag: String, activeValue: String, expiredValue: String, hint: String)] = [
            (
                "en",
                "Scan this QR from AetherLink.",
                "Pairing QR expired. Generate a new QR.",
                "This QR verifies AetherLink Runtime and includes connection details for pairing or refresh."
            ),
            (
                "ko",
                "AetherLink에서 이 QR을 스캔하세요.",
                "페어링 QR이 만료되었습니다. 새 QR을 생성하세요.",
                "이 QR은 AetherLink Runtime을 확인하고 페어링 또는 갱신에 필요한 연결 정보를 포함합니다."
            ),
            (
                "ja",
                "AetherLink でこの QR をスキャンしてください。",
                "ペアリング QR の有効期限が切れました。新しい QR を生成してください。",
                "この QR は AetherLink Runtime を確認し、ペアリングまたは更新用の接続情報を含みます。"
            ),
            (
                "zh-Hans",
                "请在 AetherLink 中扫描此二维码。",
                "配对二维码已过期。请生成新二维码。",
                "此二维码会验证 AetherLink Runtime，并包含配对或刷新所需的连接信息。"
            ),
            (
                "fr",
                "Scannez ce QR dans AetherLink.",
                "Le QR de jumelage a expiré. Générez un nouveau QR.",
                "Ce QR vérifie AetherLink Runtime et inclut les informations de connexion pour le jumelage ou l’actualisation."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(pairingQRCodeAccessibilityValue(isExpired: false), expectation.activeValue)
                XCTAssertEqual(pairingQRCodeAccessibilityValue(isExpired: true), expectation.expiredValue)
                XCTAssertEqual(pairingQRCodeAccessibilityHint(), expectation.hint)
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
            XCTAssertEqual(NSLocalizedString("Connection setup secret", comment: ""), "Protected connection key")
            XCTAssertEqual(
                NSLocalizedString("Connection setup secret regenerated.", comment: ""),
                "Protected connection key refreshed."
            )
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

    @MainActor
    func testRouteDiagnosticsPanelStaysHiddenOnCleanFirstRunUntilRouteStateExists() throws {
        let cleanFirstRunModel = CompanionAppModel(
            environment: [:],
            userDefaults: try isolatedDefaults()
        )
        XCTAssertFalse(cleanFirstRunModel.hasDevelopmentRelayRoute)
        XCTAssertFalse(cleanFirstRunModel.bootstrapRelaySettings.isEnabled)
        XCTAssertNil(cleanFirstRunModel.remoteRoutePreparationIssue)
        XCTAssertFalse(shouldShowRouteDiagnosticsPanel(model: cleanFirstRunModel))

        let savedRouteModel = CompanionAppModel(
            environment: [:],
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
            environment: [:],
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
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            ("en", "Details for Connection health", "Details for Connection diagnostics"),
            ("ko", "연결 상태의 세부 정보", "연결 진단의 세부 정보"),
            ("ja", "接続状態 の詳細", "接続診断 の詳細"),
            ("zh-Hans", "连接状态 的详情", "连接诊断 的详情"),
            ("fr", "Détails pour État de connexion", "Détails pour Diagnostics de connexion"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    routeDiagnosticDisclosureAccessibilityLabel(
                        context: NSLocalizedString("Connection health", comment: "")
                    ),
                    expectation.label
                )
                XCTAssertEqual(
                    routeDiagnosticDisclosureAccessibilityLabel(context: "   "),
                    expectation.fallbackLabel
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

    func testTrustedDeviceRowAccessibilityLabelUsesDeviceContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Trusted device Pixel. Paired Jan 1, 1970 · ID ending ice-1. Key fingerprint 2C:F2:4D:BA:5F:B0",
                "Trusted device Selected device. Pairing details unavailable. Key fingerprint Unavailable"
            ),
            (
                "ko",
                "신뢰 기기 Pixel. Paired Jan 1, 1970 · ID ending ice-1. 키 지문 2C:F2:4D:BA:5F:B0",
                "신뢰 기기 선택한 항목. 페어링 세부 정보를 사용할 수 없습니다. 키 지문 사용 불가"
            ),
            (
                "ja",
                "信頼済みデバイス Pixel。Paired Jan 1, 1970 · ID ending ice-1。キー指紋 2C:F2:4D:BA:5F:B0",
                "信頼済みデバイス 選択したデバイス。ペアリングの詳細は利用できません。キー指紋 利用不可"
            ),
            (
                "zh-Hans",
                "受信任设备 Pixel。Paired Jan 1, 1970 · ID ending ice-1。密钥指纹 2C:F2:4D:BA:5F:B0",
                "受信任设备 所选设备。配对详情不可用。密钥指纹 不可用"
            ),
            (
                "fr",
                "Appareil approuvé Pixel. Paired Jan 1, 1970 · ID ending ice-1. Empreinte de clé 2C:F2:4D:BA:5F:B0",
                "Appareil approuvé Appareil sélectionné. Détails de jumelage indisponibles. Empreinte de clé Indisponible"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    trustedDeviceRowAccessibilityLabel(
                        name: " Pixel ",
                        pairedSummary: " Paired Jan 1, 1970 · ID ending ice-1 ",
                        keyFingerprint: " 2C:F2:4D:BA:5F:B0 "
                    ),
                    expectation.label
                )
                XCTAssertEqual(
                    trustedDeviceRowAccessibilityLabel(name: " ", pairedSummary: " ", keyFingerprint: " "),
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
                        pairedSummary: pairedSummary,
                        keyFingerprint: "2C:F2:4D:BA:5F:B0"
                    ),
                    String(
                        format: NSLocalizedString("Trusted device %@. %@. Key fingerprint %@", comment: ""),
                        "Pixel",
                        pairedSummary,
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
