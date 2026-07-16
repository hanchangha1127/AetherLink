import XCTest
import CompanionCore
import OllamaBackend
@testable import LocalAgentBridge
import TrustedDevices

final class AetherLinkLocalizationTests: XCTestCase {
    func testModelPullApprovalCopyLocalizesAcrossSupportedLanguages() {
        let expectations: [(String, String, String, String, String)] = [
            ("en", "Download completed", "Download request cancelled after authentication changed", "Download request cancelled after permission policy changed", "This model download review is no longer available."),
            ("ko", "다운로드 완료", "인증 변경 후 다운로드 요청 취소됨", "권한 정책 변경 후 다운로드 요청 취소됨", "이 모델 다운로드 검토는 더 이상 사용할 수 없습니다."),
            ("ja", "ダウンロード完了", "認証変更後にダウンロードのリクエストをキャンセルしました", "権限ポリシー変更後にダウンロードのリクエストをキャンセルしました", "このモデルダウンロード審査は利用できなくなりました。"),
            ("zh-Hans", "下载完成", "身份验证变更后已取消下载请求", "权限策略变更后已取消下载请求", "此模型下载审核已不可用。"),
            ("fr", "Téléchargement terminé", "Demande de téléchargement annulée après modification de l’authentification", "Demande de téléchargement annulée après modification de la politique d’autorisation", "Cet examen de téléchargement de modèle n’est plus disponible."),
        ]
        let errorExpectations: [String: [String]] = [
            "en": [
                "Model download approval is unavailable on this runtime host.",
                "The runtime host model download review queue is full.",
                "This model download review is no longer available.",
                "Another model download decision is already in progress.",
                "The runtime host could not record the model download decision.",
                "The requesting device authentication changed before approval.",
                "The runtime host permission policy changed before approval.",
            ],
            "ko": [
                "이 런타임 호스트에서는 모델 다운로드 승인을 사용할 수 없습니다.",
                "런타임 호스트의 모델 다운로드 검토 대기열이 가득 찼습니다.",
                "이 모델 다운로드 검토는 더 이상 사용할 수 없습니다.",
                "다른 모델 다운로드 결정이 이미 진행 중입니다.",
                "런타임 호스트에서 모델 다운로드 결정을 기록하지 못했습니다.",
                "승인 전에 요청 기기의 인증이 변경되었습니다.",
                "승인 전에 런타임 호스트 권한 정책이 변경되었습니다.",
            ],
            "ja": [
                "このランタイムホストではモデルのダウンロードを承認できません。",
                "ランタイムホストのモデルダウンロード審査キューがいっぱいです。",
                "このモデルダウンロード審査は利用できなくなりました。",
                "別のモデルダウンロードの判断が進行中です。",
                "ランタイムホストはモデルダウンロードの判断を記録できませんでした。",
                "承認前にリクエスト元デバイスの認証が変更されました。",
                "承認前にランタイムホストの権限ポリシーが変更されました。",
            ],
            "zh-Hans": [
                "此运行时主机无法批准模型下载。",
                "运行时主机的模型下载审核队列已满。",
                "此模型下载审核已不可用。",
                "另一个模型下载决定正在处理中。",
                "运行时主机无法记录模型下载决定。",
                "请求设备的身份验证在批准前已发生变化。",
                "运行时主机的权限策略在批准前已发生变化。",
            ],
            "fr": [
                "L’approbation du téléchargement de modèles n’est pas disponible sur cet hôte d’exécution.",
                "La file d’examen des téléchargements de modèles de l’hôte d’exécution est pleine.",
                "Cet examen de téléchargement de modèle n’est plus disponible.",
                "Une autre décision de téléchargement de modèle est déjà en cours.",
                "L’hôte d’exécution n’a pas pu enregistrer la décision de téléchargement du modèle.",
                "L’authentification de l’appareil demandeur a changé avant l’approbation.",
                "La politique d’autorisation de l’hôte d’exécution a changé avant l’approbation.",
            ],
        ]
        XCTAssertEqual(expectations.map(\.0), AetherLinkAppLanguage.allCases.map(\.rawValue))
        XCTAssertEqual(Set(errorExpectations.keys), Set(AetherLinkAppLanguage.allCases.map(\.rawValue)))

        for (languageTag, success, authenticationChanged, permissionChanged, reviewNotFound) in expectations {
            withStoredAppLanguage(languageTag) {
                XCTAssertEqual(localizedModelPullAuditEvent("success"), success, languageTag)
                XCTAssertEqual(
                    localizedModelPullAuditEvent("authentication_changed"),
                    authenticationChanged,
                    languageTag
                )
                XCTAssertEqual(
                    localizedModelPullAuditEvent("permission_changed"),
                    permissionChanged,
                    languageTag
                )
                XCTAssertNotEqual(
                    NSLocalizedString("Approve Download", comment: ""),
                    "",
                    languageTag
                )
                XCTAssertNotEqual(
                    NSLocalizedString("I approve this runtime-host model download.", comment: ""),
                    "",
                    languageTag
                )
                XCTAssertEqual(
                    localizedModelPullApprovalError(
                        RuntimeModelPullApprovalBrokerError.reviewNotFound.localizationKey
                    ),
                    reviewNotFound,
                    languageTag
                )
                XCTAssertEqual(
                    RuntimeModelPullApprovalBrokerError.allCases.map {
                        localizedModelPullApprovalError($0.localizationKey)
                    },
                    errorExpectations[languageTag],
                    languageTag
                )
            }
        }
    }

    func testModelPullApprovalRequiresExactExplicitConfirmation() {
        let operationID = "00000000-0000-0000-0000-000000000001"

        XCTAssertFalse(modelPullApprovalIsEnabled(
            operationID: operationID,
            confirmedOperationIDs: [],
            reviewIsDispatching: false,
            decisionIsInFlight: false
        ))
        XCTAssertFalse(modelPullApprovalIsEnabled(
            operationID: operationID,
            confirmedOperationIDs: ["00000000-0000-0000-0000-000000000002"],
            reviewIsDispatching: false,
            decisionIsInFlight: false
        ))
        XCTAssertTrue(modelPullApprovalIsEnabled(
            operationID: operationID,
            confirmedOperationIDs: [operationID],
            reviewIsDispatching: false,
            decisionIsInFlight: false
        ))
        XCTAssertFalse(modelPullApprovalIsEnabled(
            operationID: operationID,
            confirmedOperationIDs: [operationID],
            reviewIsDispatching: true,
            decisionIsInFlight: false
        ))
        XCTAssertFalse(modelPullApprovalIsEnabled(
            operationID: operationID,
            confirmedOperationIDs: [operationID],
            reviewIsDispatching: false,
            decisionIsInFlight: true
        ))
    }

    func testModelPullRequesterUsesHostOwnedBidiIsolationAcrossSupportedLanguages() {
        let requester = "جهاز Android"
        for language in AetherLinkAppLanguage.allCases {
            withStoredAppLanguage(language.rawValue) {
                let localized = localizedModelPullRequester(requester)
                XCTAssertTrue(localized.contains("\u{2068}\(requester)\u{2069}"))
                XCTAssertEqual(localized.unicodeScalars.filter { $0.value == 0x2068 }.count, 1)
                XCTAssertEqual(localized.unicodeScalars.filter { $0.value == 0x2069 }.count, 1)
            }
        }
    }

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

    func testSidebarPreferencePickerAccessibilityHintsUseSelectedLanguage() {
        let expectations: [(languageTag: String, appearanceHint: String, languageHint: String)] = [
            (
                "en",
                "Choose how AetherLink Runtime appears. This setting is saved for future launches.",
                "Choose the app language. This setting is saved for future launches."
            ),
            (
                "ko",
                "AetherLink Runtime의 외관을 선택합니다. 이 설정은 다음 실행에도 저장됩니다.",
                "앱 언어를 선택합니다. 이 설정은 다음 실행에도 저장됩니다."
            ),
            (
                "ja",
                "AetherLink Runtime の外観を選択します。この設定は次回起動時にも保存されます。",
                "アプリの言語を選択します。この設定は次回起動時にも保存されます。"
            ),
            (
                "zh-Hans",
                "选择 AetherLink Runtime 的外观。此设置会保存到以后启动时使用。",
                "选择应用语言。此设置会保存到以后启动时使用。"
            ),
            (
                "fr",
                "Choisissez l’apparence d’AetherLink Runtime. Ce réglage est enregistré pour les prochains lancements.",
                "Choisissez la langue de l’app. Ce réglage est enregistré pour les prochains lancements."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(appAppearancePickerAccessibilityHint(), expectation.appearanceHint)
                XCTAssertEqual(appLanguagePickerAccessibilityHint(), expectation.languageHint)
            }
        }
    }

    func testSidebarPreferenceGroupLabelUsesSelectedLanguage() {
        let expectations: [(languageTag: String, label: String)] = [
            ("en", "App Preferences"),
            ("ko", "앱 설정"),
            ("ja", "アプリ設定"),
            ("zh-Hans", "应用偏好设置"),
            ("fr", "Préférences de l’app"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(appPreferencesAccessibilityLabel(), expectation.label)
            }
        }
    }

    func testSidebarPreferenceDetailTextUsesSelectedLanguage() {
        let expectations: [(languageTag: String, appearanceDetail: String, languageDetail: String)] = [
            (
                "en",
                "System follows this device's appearance. Saved for future launches.",
                "Choose one of the supported app languages. Saved for future launches."
            ),
            (
                "ko",
                "시스템은 이 기기의 외관 설정을 따릅니다. 다음 실행에도 저장됩니다.",
                "지원되는 앱 언어 중 하나를 선택하세요. 다음 실행에도 저장됩니다."
            ),
            (
                "ja",
                "システムはこのデバイスの外観設定に従います。次回起動時にも保存されます。",
                "対応しているアプリ言語から選択します。次回起動時にも保存されます。"
            ),
            (
                "zh-Hans",
                "系统会跟随此设备的外观设置。此设置会保存到以后启动时使用。",
                "选择一种受支持的应用语言。此设置会保存到以后启动时使用。"
            ),
            (
                "fr",
                "Le mode système suit l’apparence de cet appareil. Ce réglage est enregistré pour les prochains lancements.",
                "Choisissez l’une des langues prises en charge. Ce réglage est enregistré pour les prochains lancements."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(appAppearancePickerDetailText(), expectation.appearanceDetail)
                XCTAssertEqual(appLanguagePickerDetailText(), expectation.languageDetail)
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
                    "Document Sources": "Document Sources",
                    "Activity": "Activity",
                    "App Preferences": "App Preferences",
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
                    "Document Sources": "문서 소스",
                    "Activity": "활동",
                    "App Preferences": "앱 설정",
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
                    "Document Sources": "ドキュメントソース",
                    "Activity": "アクティビティ",
                    "App Preferences": "アプリ設定",
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
                    "Document Sources": "文档源",
                    "Activity": "活动",
                    "App Preferences": "应用偏好设置",
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
                    "Document Sources": "Sources documentaires",
                    "Activity": "Activité",
                    "App Preferences": "Préférences de l’app",
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

    func testDocumentSourceInspectorErrorsActionsAndTargetLabelsLocalizeAcrossLanguages() {
        let issues: [RuntimeDocumentSourceManagementError] = [
            .sourceUnavailable,
            .unsupportedOrUnreadableDocument,
            .resourceLimitExceeded,
            .reviewExpired,
            .invalidConfirmation,
            .sourceChanged,
            .storageUnavailable,
        ]
        let englishMessages = Dictionary(uniqueKeysWithValues: issues.map { issue in
            (String(describing: issue), issue.localizedDescription)
        })

        for language in AetherLinkAppLanguage.allCases {
            withStoredAppLanguage(language.rawValue) {
                for issue in issues {
                    let localized = localizedRuntimeDocumentSourceIssue(issue)
                    XCTAssertFalse(localized.isEmpty)
                    if language != .english {
                        XCTAssertNotEqual(localized, englishMessages[String(describing: issue)])
                    }
                }
                XCTAssertNotEqual(
                    runtimeDocumentAuditActionText(.approved),
                    runtimeDocumentAuditActionText(.indexed)
                )
                let fileName = "quarterly-source.txt"
                XCTAssertTrue(
                    String(
                        format: NSLocalizedString("Remove source %@?", comment: ""),
                        fileName
                    ).contains(fileName)
                )
                XCTAssertTrue(
                    String(
                        format: NSLocalizedString("Review expires %@", comment: ""),
                        "12:00"
                    ).contains("12:00")
                )
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

    func testCompanionPanelHeaderAccessibilityLabelUsesSelectedLanguageAndFallbacks() {
        let expectations: [(languageTag: String, label: String)] = [
            ("en", "Readiness"),
            ("ko", "준비 상태"),
            ("ja", "準備状況"),
            ("zh-Hans", "就绪情况"),
            ("fr", "Préparation"),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    companionPanelHeaderAccessibilityLabel(title: NSLocalizedString("Readiness", comment: "")),
                    expectation.label
                )
            }
        }

        withStoredAppLanguage("en") {
            XCTAssertEqual(companionPanelHeaderAccessibilityLabel(title: " Quick Actions "), "Quick Actions")
            XCTAssertEqual(companionPanelHeaderAccessibilityLabel(title: "   "), "")
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

    func testModelProviderEmptyStateAccessibilityLabelUsesSelectedLanguage() {
        let expectations: [(languageTag: String, label: String)] = [
            (
                "en",
                "No model providers available. AetherLink Runtime has not reported any model providers yet."
            ),
            (
                "ko",
                "사용 가능한 모델 제공자 없음. AetherLink Runtime이 아직 모델 제공자를 보고하지 않았습니다."
            ),
            (
                "ja",
                "利用可能なモデルプロバイダーはありません。AetherLink Runtime はまだモデルプロバイダーを報告していません。"
            ),
            (
                "zh-Hans",
                "没有可用的模型提供方。AetherLink Runtime 尚未报告模型提供方信息。"
            ),
            (
                "fr",
                "Aucun fournisseur de modèles disponible. AetherLink Runtime n’a pas encore signalé de fournisseur de modèles."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    companionEmptyStateAccessibilityLabel(
                        title: NSLocalizedString("No model providers available", comment: ""),
                        description: NSLocalizedString("AetherLink Runtime has not reported any model providers yet.", comment: "")
                    ),
                    expectation.label
                )
            }
        }
    }

    func testBackendSummaryTreatsEmptyProviderListAsNoProvidersAvailable() {
        XCTAssertEqual(AetherLinkAppLanguage.allCases.map(\.rawValue), ["en", "ko", "ja", "zh-Hans", "fr"])

        for language in AetherLinkAppLanguage.allCases {
            withStoredAppLanguage(language.rawValue) {
                let summary = modelProviderBackendSummary(for: [])

                XCTAssertEqual(summary.value, NSLocalizedString("No model providers available", comment: ""))
                XCTAssertEqual(
                    summary.detail,
                    NSLocalizedString("AetherLink Runtime has not reported any model providers yet.", comment: "")
                )
            }
        }

        withStoredAppLanguage("en") {
            let summary = modelProviderBackendSummary(for: [
                .notChecked(provider: .ollama),
                .notChecked(provider: .lmStudio),
            ])

            XCTAssertEqual(summary.value, "Not checked")
            XCTAssertEqual(summary.detail, "Model provider status has not been checked yet.")
        }
    }

    func testPairingQRCodeAccessibilityCopyUsesSelectedLanguageAndState() {
        let routeExpirationDate = Date(timeIntervalSince1970: 1_000)
        let expectations: [
            (languageTag: String, label: String, activeValue: String, expiredValue: String, unavailableValue: String, hint: String, routeExpirationFormat: String)
        ] = [
            (
                "en",
                "Pairing QR code",
                "Scan this QR from AetherLink.",
                "Pairing QR expired. Generate a new QR.",
                "Pairing QR code unavailable",
                "This QR verifies AetherLink Runtime and includes connection details for pairing or refresh.",
                "Connection details from this QR expire at %@. Generate a new QR if a device scans later."
            ),
            (
                "ko",
                "페어링 QR 코드",
                "AetherLink에서 이 QR을 스캔하세요.",
                "페어링 QR이 만료되었습니다. 새 QR을 생성하세요.",
                "페어링 QR 코드를 사용할 수 없음",
                "이 QR은 AetherLink Runtime을 확인하고 페어링 또는 갱신에 필요한 연결 정보를 포함합니다.",
                "이 QR의 연결 정보는 %@에 만료됩니다. 기기가 나중에 스캔한다면 새 QR을 생성하세요."
            ),
            (
                "ja",
                "ペアリング QR コード",
                "AetherLink でこの QR をスキャンしてください。",
                "ペアリング QR の有効期限が切れました。新しい QR を生成してください。",
                "ペアリング QR コードを利用できません",
                "この QR は AetherLink Runtime を確認し、ペアリングまたは更新用の接続情報を含みます。",
                "この QR の接続情報は %@ に期限切れになります。後でデバイスがスキャンする場合は新しい QR を生成してください。"
            ),
            (
                "zh-Hans",
                "配对 QR 码",
                "请在 AetherLink 中扫描此二维码。",
                "配对二维码已过期。请生成新二维码。",
                "配对 QR 码不可用",
                "此二维码会验证 AetherLink Runtime，并包含配对或刷新所需的连接信息。",
                "此二维码中的连接信息将于 %@ 过期。如果设备稍后扫描，请生成新的二维码。"
            ),
            (
                "fr",
                "QR code de jumelage",
                "Scannez ce QR dans AetherLink.",
                "Le QR de jumelage a expiré. Générez un nouveau QR.",
                "QR code de jumelage indisponible",
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
                XCTAssertEqual(pairingQRCodeAccessibilityValue(isExpired: false, isAvailable: false), expectation.unavailableValue)
                XCTAssertEqual(pairingQRCodeAccessibilityValue(isExpired: true, isAvailable: false), expectation.unavailableValue)
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
                XCTAssertEqual(pairingQRExpirationAccessibilityLabel(), expectation.label)
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
                "This QR includes connection details for relay.example.test. Pairing or refresh still requires the scanning device to reach that route."
            ),
            (
                "ko",
                "페어링 QR 상태",
                "페어링 QR이 연결 정보를 기다리는 중입니다.",
                "이 QR에는 relay.example.test의 연결 정보가 포함되어 있습니다. 페어링이나 갱신은 스캔하는 기기에서 해당 경로에 도달할 수 있어야 완료됩니다."
            ),
            (
                "ja",
                "ペアリング QR の状態",
                "ペアリング QR は接続情報を待っています。",
                "この QR には relay.example.test の接続情報が含まれています。ペアリングまたは更新を完了するには、スキャンするデバイスがその経路に到達できる必要があります。"
            ),
            (
                "zh-Hans",
                "配对 QR 状态",
                "配对二维码正在等待连接信息。",
                "此二维码包含 relay.example.test 的连接信息。配对或刷新仍需要扫码设备能够访问该路由。"
            ),
            (
                "fr",
                "État du QR de jumelage",
                "Le QR de jumelage attend les informations de connexion.",
                "Ce QR inclut les informations de connexion de relay.example.test. Le jumelage ou l’actualisation exige encore que l’appareil qui scanne puisse atteindre cette route."
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
                            "This QR includes connection details for %@. Pairing or refresh still requires the scanning device to reach that route.",
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
                capabilities: ["chat", "vision", "raw_future_capability"],
                installed: true,
                source: .local,
                contextWindowTokens: 32_768
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

    func testRuntimeOverviewTreatsHiddenModelsAsNotLoaded() {
        let hiddenOnlyGroups = visibleModelGroups(for: [
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
        let visibleModelCount = hiddenOnlyGroups.reduce(0) { count, group in count + group.models.count }

        XCTAssertTrue(hiddenOnlyGroups.isEmpty)
        XCTAssertEqual(visibleModelCount, 0)
        XCTAssertEqual(
            statusRuntimeOverviewFocus(
                isRuntimeAdvertising: true,
                isBackendReady: true,
                hasTrustedDevices: true,
                hasLoadedModels: visibleModelCount > 0,
                hasRoutePreparationIssue: false,
                hasDevelopmentRelayRoute: false,
                isDevelopmentRelayQRCodeReady: false
            ),
            .models
        )
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
                "モデル Nomic Embed。ID nomic-embed-text。タイプ メモリ インデックス。プロバイダー LM Studio。ソース ローカル。状態 未実行。サイズ サイズ不明",
                "モデル 名前のないモデル。ID 不明なモデル ID。タイプ 不明なモデルタイプ。プロバイダー 不明なプロバイダー。ソース 不明なソース。状態 未実行。サイズ サイズ不明"
            ),
            (
                "zh-Hans",
                "模型 Llama 3。ID llama3:8b。类型 聊天。提供方 Ollama。来源 本地。状态 运行中。大小 4.7 GB",
                "模型 Nomic Embed。ID nomic-embed-text。类型 记忆索引。提供方 LM Studio。来源 本地。状态 未运行。大小 大小未知",
                "模型 未命名模型。ID 未知模型 ID。类型 未知模型类型。提供方 未知提供方。来源 未知来源。状态 未运行。大小 大小未知"
            ),
            (
                "fr",
                "Modèle Llama 3. ID llama3:8b. Type Discussion. Fournisseur Ollama. Source Localement installé. État En cours. Taille 4.7 GB",
                "Modèle Nomic Embed. ID nomic-embed-text. Type Indexation de la mémoire. Fournisseur LM Studio. Source Localement installé. État À l’arrêt. Taille Taille inconnue",
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

    func testModelCapabilityDisplayProjectsOnlyKnownCapabilitiesAcrossSupportedLanguages() {
        let expectations: [(
            languageTag: String,
            chatLine: String,
            embeddingLine: String,
            visionBadge: String,
            chatContextBadge: String,
            embeddingContextBadge: String
        )] = [
            (
                "en",
                "Vision, Context: 32,768 tokens",
                "Context: 8,192 tokens",
                "Vision",
                "Context: 32,768 tokens",
                "Context: 8,192 tokens"
            ),
            (
                "ko",
                "비전, 컨텍스트: 32,768 토큰",
                "컨텍스트: 8,192 토큰",
                "비전",
                "컨텍스트: 32,768 토큰",
                "컨텍스트: 8,192 토큰"
            ),
            (
                "ja",
                "ビジョン、コンテキスト：32,768 トークン",
                "コンテキスト：8,192 トークン",
                "ビジョン",
                "コンテキスト：32,768 トークン",
                "コンテキスト：8,192 トークン"
            ),
            (
                "zh-Hans",
                "视觉、上下文：32,768 个词元",
                "上下文：8,192 个词元",
                "视觉",
                "上下文：32,768 个词元",
                "上下文：8,192 个词元"
            ),
            (
                "fr",
                "Vision, Contexte : 32\u{202F}768 jetons",
                "Contexte : 8\u{202F}192 jetons",
                "Vision",
                "Contexte : 32\u{202F}768 jetons",
                "Contexte : 8\u{202F}192 jetons"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let chatDisplay = modelCapabilityDisplay(
                    for: ModelInfo(
                        id: "vision-chat",
                        name: "Vision Chat",
                        kind: .chat,
                        capabilities: ["chat", "vision", "raw_future_capability"],
                        contextWindowTokens: 32_768
                    )
                )
                XCTAssertEqual(chatDisplay.accessibilityLine, expectation.chatLine)
                XCTAssertEqual(chatDisplay.additionalBadges.map(\.id), ["vision", "context-window"])
                XCTAssertEqual(
                    chatDisplay.additionalBadges.map(\.text),
                    [expectation.visionBadge, expectation.chatContextBadge]
                )
                XCTAssertFalse(chatDisplay.accessibilityLine?.contains("raw_future_capability") == true)

                let embeddingDisplay = modelCapabilityDisplay(
                    for: ModelInfo(
                        id: "local-embedding",
                        name: "Local Embedding",
                        kind: .embedding,
                        capabilities: ["embedding", "raw_future_capability"],
                        contextWindowTokens: 8_192
                    )
                )
                XCTAssertEqual(embeddingDisplay.accessibilityLine, expectation.embeddingLine)
                XCTAssertEqual(embeddingDisplay.additionalBadges.map(\.id), ["context-window"])
                XCTAssertEqual(
                    embeddingDisplay.additionalBadges.map(\.text),
                    [expectation.embeddingContextBadge]
                )
                XCTAssertFalse(embeddingDisplay.accessibilityLine?.contains("raw_future_capability") == true)
            }
        }
    }

    func testModelCapabilityDisplayOmitsInvalidContextAndRawUnknownCapabilities() {
        for alias in ["vision", "image", "multimodal"] {
            let display = modelCapabilityDisplay(
                for: ModelInfo(
                    id: "chat-\(alias)",
                    name: "Chat \(alias)",
                    kind: .chat,
                    capabilities: ["chat", alias]
                )
            )
            XCTAssertEqual(display.additionalBadges.map(\.id), ["vision"])
            XCTAssertEqual(display.accessibilityLine, NSLocalizedString("Vision", comment: ""))
        }

        for contextWindowTokens in [nil, 0, -1] as [Int?] {
            let display = modelCapabilityDisplay(
                for: ModelInfo(
                    id: "unknown-chat",
                    name: "Unknown Chat",
                    kind: .chat,
                    capabilities: ["chat", "raw_future_capability", " vision "],
                    contextWindowTokens: contextWindowTokens
                )
            )
            XCTAssertEqual(display.additionalBadges, [])
            XCTAssertNil(display.accessibilityLine)
        }
    }

    func testModelRowAccessibilityLabelIncludesKnownCapabilitiesAcrossSupportedLanguages() {
        let expectations: [(languageTag: String, label: String)] = [
            (
                "en",
                "Model Vision Chat. ID vision-chat. Type Chat. Provider Ollama. Source Local. State Not running. Size Size unknown. Capabilities: Vision, Context: 32,768 tokens."
            ),
            (
                "ko",
                "모델 Vision Chat. ID vision-chat. 유형 채팅. 제공자 Ollama. 출처 로컬. 상태 실행 안 됨. 크기 크기 알 수 없음. 기능: 비전, 컨텍스트: 32,768 토큰."
            ),
            (
                "ja",
                "モデル Vision Chat。ID vision-chat。タイプ チャット。プロバイダー Ollama。ソース ローカル。状態 未実行。サイズ サイズ不明。機能：ビジョン、コンテキスト：32,768 トークン。"
            ),
            (
                "zh-Hans",
                "模型 Vision Chat。ID vision-chat。类型 聊天。提供方 Ollama。来源 本地。状态 未运行。大小 大小未知。功能：视觉、上下文：32,768 个词元。"
            ),
            (
                "fr",
                "Modèle Vision Chat. ID vision-chat. Type Discussion. Fournisseur Ollama. Source Localement installé. État À l’arrêt. Taille Taille inconnue. Capacités : Vision, Contexte : 32\u{202F}768 jetons."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let display = modelCapabilityDisplay(
                    for: ModelInfo(
                        id: "vision-chat",
                        name: "Vision Chat",
                        kind: .chat,
                        capabilities: ["chat", "vision", "raw_future_capability"],
                        contextWindowTokens: 32_768
                    )
                )
                XCTAssertEqual(
                    modelRowAccessibilityLabel(
                        name: "Vision Chat",
                        identifier: "vision-chat",
                        kind: NSLocalizedString("Chat", comment: ""),
                        provider: NSLocalizedString("Ollama", comment: ""),
                        source: NSLocalizedString("Local", comment: ""),
                        running: false,
                        size: nil,
                        capabilities: display.accessibilityLine
                    ),
                    expectation.label
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
                    "モデルセクション メモリ インデックスモデル。1 件のモデル",
                    "モデルセクション モデルセクション。モデル数なし"
                ),
            (
                "zh-Hans",
                "模型分区 聊天模型。2 个模型",
                "模型分区 记忆索引模型。1 个模型",
                "模型分区 模型分区。没有模型数量"
            ),
            (
                "fr",
                "Section de modèles Modèles de chat. 2 modèles",
                "Section de modèles Modèles d’indexation de la mémoire. 1 modèle",
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
                localizedRuntimeActiveChatSessionCount(1),
                localizedRuntimeActiveChatSessionCount(2),
                localizedRuntimeArchivedChatSessionCount(1),
                localizedRuntimeArchivedChatSessionCount(3),
                localizedRuntimeSavedChatSessionCount(1),
                localizedRuntimeSavedChatSessionCount(3),
                localizedRuntimeChatMessageCount(1),
                localizedRuntimeChatMessageCount(5),
                localizedRuntimeSavedMemoryCount(1),
                localizedRuntimeSavedMemoryCount(3),
                localizedRuntimeEnabledMemoryCount(1),
                localizedRuntimeEnabledMemoryCount(2),
                localizedRuntimePausedMemoryCount(1),
                localizedRuntimePausedMemoryCount(4),
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
            XCTAssertEqual(copy[10], "1 active chat")
            XCTAssertEqual(copy[11], "2 active chats")
            XCTAssertEqual(copy[12], "1 archived chat")
            XCTAssertEqual(copy[13], "3 archived chats")
            XCTAssertEqual(copy[14], "1 saved chat")
            XCTAssertEqual(copy[15], "3 saved chats")
            XCTAssertEqual(localizedRuntimeActiveChatSessionCount(-3), "0 active chats")
            XCTAssertEqual(localizedRuntimeArchivedChatSessionCount(-3), "0 archived chats")
            XCTAssertEqual(localizedRuntimeSavedChatSessionCount(-3), "0 saved chats")
            XCTAssertEqual(runtimeHistoryCardValue(activeCount: 2, archivedCount: 1), "3 saved chats")
            XCTAssertEqual(
                runtimeHistoryCardDetail(activeCount: 2, archivedCount: 1),
                "Runtime context: 2 active chats. Archived: 1 archived chat."
            )
            XCTAssertEqual(
                runtimeHistoryInspectorSummaryAccessibilityLabel(
                    value: runtimeHistoryCardValue(activeCount: 2, archivedCount: 1),
                    detail: runtimeHistoryCardDetail(activeCount: 2, archivedCount: 1)
                ),
                "Runtime history summary. 3 saved chats. Runtime context: 2 active chats. Archived: 1 archived chat."
            )
            XCTAssertEqual(
                runtimeHistoryCardDetail(activeCount: 0, archivedCount: 0),
                "No runtime chat sessions are stored on AetherLink Runtime."
            )
            XCTAssertEqual(copy[16], "1 message")
            XCTAssertEqual(copy[17], "5 messages")
            XCTAssertEqual(localizedRuntimeChatMessageCount(-3), "0 messages")
            XCTAssertEqual(copy[18], "1 saved memory note")
            XCTAssertEqual(copy[19], "3 saved memory notes")
            XCTAssertEqual(localizedRuntimeSavedMemoryCount(-3), "0 saved memory notes")
            XCTAssertEqual(copy[20], "1 enabled memory note")
            XCTAssertEqual(copy[21], "2 enabled memory notes")
            XCTAssertEqual(copy[22], "1 paused memory note")
            XCTAssertEqual(copy[23], "4 paused memory notes")
            XCTAssertEqual(runtimeMemoryCardValue(enabledCount: 2, pausedCount: 1), "3 saved memory notes")
            XCTAssertEqual(
                runtimeMemoryCardDetail(enabledCount: 2, pausedCount: 1),
                "Runtime context: 2 enabled memory notes. Paused: 1 paused memory note."
            )
            XCTAssertEqual(
                runtimeMemoryInspectorSummaryAccessibilityLabel(
                    value: runtimeMemoryCardValue(enabledCount: 2, pausedCount: 1),
                    detail: runtimeMemoryCardDetail(enabledCount: 2, pausedCount: 1)
                ),
                "Runtime memory summary. 3 saved memory notes. Runtime context: 2 enabled memory notes. Paused: 1 paused memory note."
            )
            XCTAssertEqual(runtimeMemoryCardValue(enabledCount: -2, pausedCount: 1), "1 saved memory note")
            XCTAssertEqual(
                runtimeMemoryCardDetail(enabledCount: 0, pausedCount: 0),
                "No runtime memory notes are stored on AetherLink Runtime."
            )
            XCTAssertEqual(copy[24], "Ollama llama3.1 active. Idle unload after 1 minute.")
            XCTAssertEqual(copy[25], "Ollama llama3.1 active. Idle unload after 10 minutes.")
            XCTAssertFalse(copy.contains { $0.contains("(s)") })
        }

        withStoredAppLanguage("ko") {
            XCTAssertEqual(localizedTrustedDeviceCount(2), "신뢰 기기 2대")
            XCTAssertEqual(localizedLoadedModelCount(2), "모델 2개 불러옴")
            XCTAssertEqual(localizedLoadedLocalModelLogCount("2"), "모델 2개 불러옴")
            XCTAssertEqual(localizedRuntimeActiveChatSessionCount(2), "활성 채팅 2개")
            XCTAssertEqual(localizedRuntimeSavedChatSessionCount(3), "저장된 채팅 3개")
            XCTAssertEqual(
                runtimeHistoryCardDetail(activeCount: 2, archivedCount: 1),
                "런타임 컨텍스트: 활성 채팅 2개. 보관됨: 보관된 채팅 1개."
            )
            XCTAssertEqual(localizedRuntimeChatMessageCount(2), "메시지 2개")
            XCTAssertEqual(localizedRuntimeSavedMemoryCount(3), "저장된 메모리 노트 3개")
            XCTAssertEqual(localizedRuntimeEnabledMemoryCount(2), "사용 중인 메모리 노트 2개")
            XCTAssertEqual(
                runtimeMemoryCardDetail(enabledCount: 2, pausedCount: 1),
                "런타임 컨텍스트: 사용 중인 메모리 노트 2개. 일시 중지: 일시 중지된 메모리 노트 1개."
            )
        }

        withStoredAppLanguage("ja") {
            XCTAssertEqual(localizedRuntimeSavedChatSessionCount(3), "保存済みチャット 3 件")
            XCTAssertEqual(
                runtimeHistoryCardDetail(activeCount: 2, archivedCount: 1),
                "ランタイムコンテキスト: アクティブなチャット 2 件。アーカイブ済み: アーカイブ済みチャット 1 件。"
            )
            XCTAssertEqual(localizedRuntimeSavedMemoryCount(3), "保存済みメモリノート 3 件")
            XCTAssertEqual(localizedRuntimeEnabledMemoryCount(2), "有効なメモリノート 2 件")
            XCTAssertEqual(localizedRuntimePausedMemoryCount(1), "一時停止中のメモリノート 1 件")
            XCTAssertEqual(
                runtimeMemoryCardDetail(enabledCount: 2, pausedCount: 1),
                "ランタイムコンテキスト: 有効なメモリノート 2 件。一時停止: 一時停止中のメモリノート 1 件。"
            )
        }

        withStoredAppLanguage("zh-Hans") {
            XCTAssertEqual(localizedRuntimeSavedChatSessionCount(3), "3 个已保存聊天")
            XCTAssertEqual(
                runtimeHistoryCardDetail(activeCount: 2, archivedCount: 1),
                "运行时上下文：2 个活跃聊天。已归档：1 个已归档聊天。"
            )
            XCTAssertEqual(localizedRuntimeSavedMemoryCount(3), "3 条已保存记忆")
            XCTAssertEqual(localizedRuntimeEnabledMemoryCount(2), "2 条已启用记忆")
            XCTAssertEqual(localizedRuntimePausedMemoryCount(1), "1 条已暂停记忆")
            XCTAssertEqual(
                runtimeMemoryCardDetail(enabledCount: 2, pausedCount: 1),
                "运行时上下文：2 条已启用记忆。已暂停：1 条已暂停记忆。"
            )
        }

        withStoredAppLanguage("fr") {
            XCTAssertEqual(localizedTrustedDeviceCount(1), "1 appareil approuvé")
            XCTAssertEqual(localizedTrustedDeviceCount(2), "2 appareils approuvés")
            XCTAssertEqual(localizedAvailableModelProviderCount(1), "1 fournisseur de modèles disponible")
            XCTAssertEqual(localizedAvailableModelProviderCount(2), "2 fournisseurs de modèles disponibles")
            XCTAssertEqual(localizedRuntimeArchivedChatSessionCount(2), "2 chats archivés")
            XCTAssertEqual(localizedRuntimeSavedChatSessionCount(3), "3 chats enregistrés")
            XCTAssertEqual(
                runtimeHistoryCardDetail(activeCount: 2, archivedCount: 1),
                "Contexte du runtime : 2 chats actifs. Archivés : 1 chat archivé."
            )
            XCTAssertEqual(localizedRuntimeChatMessageCount(2), "2 messages")
            XCTAssertEqual(localizedRuntimeSavedMemoryCount(3), "3 notes mémoire enregistrées")
            XCTAssertEqual(localizedRuntimePausedMemoryCount(2), "2 notes mémoire suspendues")
            XCTAssertEqual(
                runtimeMemoryCardDetail(enabledCount: 2, pausedCount: 1),
                "Contexte du runtime : 2 notes mémoire activées. En pause : 1 note mémoire suspendue."
            )
        }
    }

    func testCompactionCalibrationCopyLocalizesAcrossSupportedLanguages() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                NSLocalizedString("Inspect Compaction Calibration", comment: ""),
                "Inspect Compaction Calibration"
            )
            XCTAssertEqual(localizedCompactionCalibrationSampleCount(2), "2 calibration samples")
            XCTAssertEqual(localizedCompactionCalibrationSampleCount(-1), "0 calibration samples")
            XCTAssertEqual(localizedCompactionCalibrationGroupCount(1), "1 model configuration")
            XCTAssertEqual(localizedCompactionCalibrationStatus(.collecting), "Collecting")
            XCTAssertEqual(localizedCompactionCalibrationStatus(.readyForReview), "Ready for review")
            XCTAssertEqual(
                localizedCompactionCalibrationStatus(.inputBudgetExceededObserved),
                "Input budget exceeded"
            )
            XCTAssertEqual(
                localizedCompactionCalibrationWireMode("lmstudio_openai_compat"),
                "LM Studio OpenAI-compatible"
            )
        }

        withStoredAppLanguage("ko") {
            XCTAssertEqual(NSLocalizedString("Compaction Calibration", comment: ""), "압축 보정")
            XCTAssertEqual(localizedCompactionCalibrationSampleCount(2), "보정 표본 2개")
            XCTAssertEqual(localizedCompactionCalibrationGroupCount(1), "모델 구성 1개")
            XCTAssertEqual(localizedCompactionCalibrationStatus(.collecting), "수집 중")
            XCTAssertEqual(localizedCompactionCalibrationStatus(.readyForReview), "검토 준비됨")
            XCTAssertEqual(
                localizedCompactionCalibrationStatus(.inputBudgetExceededObserved),
                "입력 예산 초과"
            )
        }

        withStoredAppLanguage("ja") {
            XCTAssertEqual(NSLocalizedString("Compaction Calibration", comment: ""), "圧縮キャリブレーション")
            XCTAssertEqual(localizedCompactionCalibrationSampleCount(2), "キャリブレーションサンプル2件")
            XCTAssertEqual(localizedCompactionCalibrationGroupCount(1), "モデル構成1件")
            XCTAssertEqual(localizedCompactionCalibrationStatus(.readyForReview), "レビュー可能")
        }

        withStoredAppLanguage("zh-Hans") {
            XCTAssertEqual(NSLocalizedString("Compaction Calibration", comment: ""), "压缩校准")
            XCTAssertEqual(localizedCompactionCalibrationSampleCount(2), "2 个校准样本")
            XCTAssertEqual(localizedCompactionCalibrationGroupCount(1), "1 个模型配置")
            XCTAssertEqual(localizedCompactionCalibrationStatus(.readyForReview), "可供审核")
        }

        withStoredAppLanguage("fr") {
            XCTAssertEqual(NSLocalizedString("Compaction Calibration", comment: ""), "Étalonnage de compression")
            XCTAssertEqual(localizedCompactionCalibrationSampleCount(2), "2 échantillons d’étalonnage")
            XCTAssertEqual(localizedCompactionCalibrationGroupCount(1), "1 configuration de modèle")
            XCTAssertEqual(localizedCompactionCalibrationStatus(.readyForReview), "Prêt pour examen")
        }
    }

    func testRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime History", comment: ""), "Inspect Runtime History")
            XCTAssertEqual(NSLocalizedString("Inspect runtime-owned chat sessions stored on AetherLink Runtime.", comment: ""), "Inspect runtime-owned chat sessions stored on AetherLink Runtime.")
            XCTAssertEqual(NSLocalizedString("Runtime History Inspector", comment: ""), "Runtime History Inspector")
            XCTAssertEqual(NSLocalizedString("Close Runtime History Inspector", comment: ""), "Close Runtime History Inspector")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime History Inspector", comment: ""), "Refresh Runtime History Inspector")
            XCTAssertEqual(NSLocalizedString("Deleted Chat Retention", comment: ""), "Deleted Chat Retention")
            XCTAssertEqual(NSLocalizedString("Clean Deleted History", comment: ""), "Clean Deleted History")
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(CompanionRuntimeChatRetentionStatus()),
                "Deleted chats are kept for 90 days, then removed automatically from this runtime host."
            )
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(CompanionRuntimeChatRetentionStatus(state: .running)),
                "Cleaning expired deleted chats."
            )
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(
                    CompanionRuntimeChatRetentionStatus(state: .completed, prunedDeletedSessionCount: 0)
                ),
                "Cleanup finished. No expired deleted chats were found."
            )
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(
                    CompanionRuntimeChatRetentionStatus(state: .completed, prunedDeletedSessionCount: 2)
                ),
                "Cleanup finished. 2 deleted chats removed."
            )
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(CompanionRuntimeChatRetentionStatus(state: .failed)),
                "Cleanup failed. Check Activity and try again."
            )
            XCTAssertEqual(
                runtimeHistoryRetentionActionAccessibilityHint(),
                "Remove chats deleted at least 90 days ago from this runtime host."
            )
            XCTAssertEqual(localizedRuntimeDeletedChatCount(1), "1 deleted chat")
            XCTAssertEqual(localizedRuntimeDeletedChatCount(2), "2 deleted chats")
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions", comment: ""), "No runtime chat sessions")
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions are stored on AetherLink Runtime.", comment: ""), "No runtime chat sessions are stored on AetherLink Runtime.")
            XCTAssertEqual(NSLocalizedString("Runtime history summary. %@. %@", comment: ""), "Runtime history summary. %@. %@")
            XCTAssertEqual(NSLocalizedString("Transcript Preview", comment: ""), "Transcript Preview")
            XCTAssertEqual(NSLocalizedString("Load transcript preview", comment: ""), "Load transcript preview")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityLabel(title: " Release planning "), "Load transcript preview for Release planning")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityLabel(title: " "), "Load transcript preview for Untitled chat")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: true), "Selected")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: false), "Not selected")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityHint(), "Load this runtime-owned transcript preview.")
            XCTAssertEqual(NSLocalizedString("No transcript messages", comment: ""), "No transcript messages")
            XCTAssertEqual(NSLocalizedString("Thinking", comment: ""), "Thinking")
            XCTAssertEqual(runtimeTranscriptReasoningToggleTitle(isExpanded: false), "Show thinking")
            XCTAssertEqual(runtimeTranscriptReasoningToggleTitle(isExpanded: true), "Hide thinking")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityValue(isExpanded: false), "Thinking collapsed")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityValue(isExpanded: true), "Thinking expanded")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded: false), "Expand to show full thinking.")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded: true), "Collapse to keep thinking preview short.")
            XCTAssertEqual(localizedRuntimeChatSessionStatus("active"), "Active")
            XCTAssertEqual(localizedRuntimeChatSessionStatus("archived"), "Archived")
            XCTAssertEqual(runtimeHistoryEventDisplayName("done"), "Completed")
            XCTAssertEqual(runtimeTranscriptRoleDisplayName("user"), "User")
            XCTAssertEqual(runtimeTranscriptRoleDisplayName("assistant"), "Assistant")
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: "Jun 29, 2026 at 2:00 AM"),
                "Created Jun 29, 2026 at 2:00 AM"
            )
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: " "),
                "Created Unknown creation time"
            )
            XCTAssertEqual(
                runtimeChatSessionAccessibilityLabel(
                    title: " Release planning ",
                    status: "Active",
                    model: "ollama:llama3.1:8b",
                    messageCount: "4 messages",
                    updatedAt: "Jun 29, 2026 at 2:00 AM"
                ),
                "Chat session Release planning. Status Active. Model ollama:llama3.1:8b. 4 messages. Updated Jun 29, 2026 at 2:00 AM."
            )
            XCTAssertEqual(
                runtimeChatSessionAccessibilityLabel(
                    title: " Damaged count ",
                    status: "Active",
                    model: "ollama:llama3.1:8b",
                    messageCount: localizedRuntimeChatMessageCount(-3),
                    updatedAt: "Jun 29, 2026 at 2:00 AM"
                ),
                "Chat session Damaged count. Status Active. Model ollama:llama3.1:8b. 0 messages. Updated Jun 29, 2026 at 2:00 AM."
            )
        }

        withStoredAppLanguage("ko") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime History", comment: ""), "런타임 기록 점검")
            XCTAssertEqual(NSLocalizedString("Inspect runtime-owned chat sessions stored on AetherLink Runtime.", comment: ""), "AetherLink Runtime에 저장된 런타임 소유 채팅 세션을 확인합니다.")
            XCTAssertEqual(NSLocalizedString("Runtime History Inspector", comment: ""), "런타임 기록 점검")
            XCTAssertEqual(NSLocalizedString("Close Runtime History Inspector", comment: ""), "런타임 기록 점검 닫기")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime History Inspector", comment: ""), "런타임 기록 점검 새로 고침")
            XCTAssertEqual(NSLocalizedString("Deleted Chat Retention", comment: ""), "삭제된 채팅 보존")
            XCTAssertEqual(NSLocalizedString("Clean Deleted History", comment: ""), "삭제된 기록 정리")
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(
                    CompanionRuntimeChatRetentionStatus(state: .completed, prunedDeletedSessionCount: 2)
                ),
                "정리 완료: 삭제된 채팅 2개 제거됨."
            )
            XCTAssertEqual(localizedRuntimeDeletedChatCount(1), "삭제된 채팅 1개")
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions", comment: ""), "런타임 채팅 세션 없음")
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions are stored on AetherLink Runtime.", comment: ""), "AetherLink Runtime에 저장된 런타임 채팅 세션이 없습니다.")
            XCTAssertEqual(NSLocalizedString("Runtime history summary. %@. %@", comment: ""), "런타임 기록 요약. %@. %@")
            XCTAssertEqual(NSLocalizedString("Transcript Preview", comment: ""), "대화 미리보기")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityLabel(title: " 출시 계획 "), "출시 계획 대화 미리보기 불러오기")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: true), "선택됨")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: false), "선택되지 않음")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityHint(), "이 런타임 소유 대화 미리보기를 불러옵니다.")
            XCTAssertEqual(NSLocalizedString("No transcript messages", comment: ""), "대화 메시지 없음")
            XCTAssertEqual(NSLocalizedString("Thinking", comment: ""), "생각")
            XCTAssertEqual(runtimeTranscriptReasoningToggleTitle(isExpanded: false), "생각 펼치기")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityValue(isExpanded: true), "생각 펼쳐짐")
            XCTAssertEqual(runtimeTranscriptRoleDisplayName("user"), "사용자")
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: "2026년 6월 29일 오전 2:00"),
                "생성 2026년 6월 29일 오전 2:00"
            )
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: ""),
                "생성 알 수 없는 생성 시간"
            )
            XCTAssertEqual(localizedRuntimeChatSessionStatus("archived"), "보관됨")
        }

        withStoredAppLanguage("ja") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime History", comment: ""), "ランタイム履歴を確認")
            XCTAssertEqual(NSLocalizedString("Inspect runtime-owned chat sessions stored on AetherLink Runtime.", comment: ""), "AetherLink Runtime に保存されたランタイム所有のチャットセッションを確認します。")
            XCTAssertEqual(NSLocalizedString("Runtime History Inspector", comment: ""), "ランタイム履歴インスペクタ")
            XCTAssertEqual(NSLocalizedString("Close Runtime History Inspector", comment: ""), "ランタイム履歴インスペクタを閉じる")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime History Inspector", comment: ""), "ランタイム履歴インスペクタを更新")
            XCTAssertEqual(NSLocalizedString("Deleted Chat Retention", comment: ""), "削除済みチャットの保持")
            XCTAssertEqual(NSLocalizedString("Clean Deleted History", comment: ""), "削除済み履歴をクリーンアップ")
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(
                    CompanionRuntimeChatRetentionStatus(state: .completed, prunedDeletedSessionCount: 2)
                ),
                "クリーンアップが完了しました。2件の削除済みチャットを削除しました。"
            )
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions", comment: ""), "ランタイムチャットセッションはありません")
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions are stored on AetherLink Runtime.", comment: ""), "AetherLink Runtime にランタイムチャットセッションは保存されていません。")
            XCTAssertEqual(NSLocalizedString("Runtime history summary. %@. %@", comment: ""), "ランタイム履歴の概要。%@。%@")
            XCTAssertEqual(NSLocalizedString("Transcript Preview", comment: ""), "会話プレビュー")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityLabel(title: " リリース計画 "), "「リリース計画」の会話プレビューを読み込む")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: true), "選択済み")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: false), "未選択")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityHint(), "このランタイム所有の会話プレビューを読み込みます。")
            XCTAssertEqual(NSLocalizedString("No transcript messages", comment: ""), "会話メッセージはありません")
            XCTAssertEqual(NSLocalizedString("Thinking", comment: ""), "思考")
            XCTAssertEqual(runtimeTranscriptReasoningToggleTitle(isExpanded: true), "思考を隠す")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded: false), "展開して思考全文を表示します。")
            XCTAssertEqual(runtimeTranscriptRoleDisplayName("assistant"), "アシスタント")
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: "2026年6月29日 2:00"),
                "作成 2026年6月29日 2:00"
            )
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: "\n\t"),
                "作成 不明な作成時刻"
            )
            XCTAssertEqual(localizedRuntimeChatSessionStatus("active"), "アクティブ")
        }

        withStoredAppLanguage("zh-Hans") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime History", comment: ""), "检查运行时历史")
            XCTAssertEqual(NSLocalizedString("Inspect runtime-owned chat sessions stored on AetherLink Runtime.", comment: ""), "检查 AetherLink Runtime 中存储的运行时拥有的聊天会话。")
            XCTAssertEqual(NSLocalizedString("Runtime History Inspector", comment: ""), "运行时历史检查器")
            XCTAssertEqual(NSLocalizedString("Close Runtime History Inspector", comment: ""), "关闭运行时历史检查器")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime History Inspector", comment: ""), "刷新运行时历史检查器")
            XCTAssertEqual(NSLocalizedString("Deleted Chat Retention", comment: ""), "已删除聊天保留")
            XCTAssertEqual(NSLocalizedString("Clean Deleted History", comment: ""), "清理已删除历史记录")
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(
                    CompanionRuntimeChatRetentionStatus(state: .completed, prunedDeletedSessionCount: 2)
                ),
                "清理完成。已移除2条已删除聊天。"
            )
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions", comment: ""), "没有运行时聊天会话")
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions are stored on AetherLink Runtime.", comment: ""), "AetherLink Runtime 中没有已保存的运行时聊天会话。")
            XCTAssertEqual(NSLocalizedString("Runtime history summary. %@. %@", comment: ""), "运行时历史摘要。%@。%@")
            XCTAssertEqual(NSLocalizedString("Transcript Preview", comment: ""), "对话预览")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityLabel(title: " 发布计划 "), "加载“发布计划”的对话预览")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: true), "已选择")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: false), "未选择")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityHint(), "加载这个由运行时拥有的对话预览。")
            XCTAssertEqual(NSLocalizedString("No transcript messages", comment: ""), "没有对话消息")
            XCTAssertEqual(NSLocalizedString("Thinking", comment: ""), "思考")
            XCTAssertEqual(runtimeTranscriptReasoningToggleTitle(isExpanded: false), "显示思考")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityValue(isExpanded: false), "思考已折叠")
            XCTAssertEqual(runtimeTranscriptRoleDisplayName("system"), "系统消息")
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: "2026年6月29日 2:00"),
                "创建 2026年6月29日 2:00"
            )
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: ""),
                "创建 未知创建时间"
            )
            XCTAssertEqual(localizedRuntimeChatSessionStatus("archived"), "已归档")
        }

        withStoredAppLanguage("fr") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime History", comment: ""), "Inspecter l’historique du runtime")
            XCTAssertEqual(NSLocalizedString("Inspect runtime-owned chat sessions stored on AetherLink Runtime.", comment: ""), "Inspecter les sessions de chat détenues par le runtime et stockées dans AetherLink Runtime.")
            XCTAssertEqual(NSLocalizedString("Runtime History Inspector", comment: ""), "Inspecteur d’historique du runtime")
            XCTAssertEqual(NSLocalizedString("Close Runtime History Inspector", comment: ""), "Fermer l’inspecteur d’historique du runtime")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime History Inspector", comment: ""), "Actualiser l’inspecteur d’historique du runtime")
            XCTAssertEqual(NSLocalizedString("Deleted Chat Retention", comment: ""), "Conservation des chats supprimés")
            XCTAssertEqual(NSLocalizedString("Clean Deleted History", comment: ""), "Nettoyer l’historique supprimé")
            XCTAssertEqual(
                runtimeHistoryRetentionDetail(
                    CompanionRuntimeChatRetentionStatus(state: .completed, prunedDeletedSessionCount: 2)
                ),
                "Nettoyage terminé : 2 chats supprimés."
            )
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions", comment: ""), "Aucune session de chat du runtime")
            XCTAssertEqual(NSLocalizedString("No runtime chat sessions are stored on AetherLink Runtime.", comment: ""), "Aucune session de chat du runtime n’est stockée dans AetherLink Runtime.")
            XCTAssertEqual(NSLocalizedString("Runtime history summary. %@. %@", comment: ""), "Résumé de l’historique du runtime. %@. %@")
            XCTAssertEqual(NSLocalizedString("Transcript Preview", comment: ""), "Aperçu de la transcription")
            XCTAssertEqual(
                runtimeTranscriptPreviewLoadAccessibilityLabel(title: " Planification de version "),
                "Charger l’aperçu de la transcription pour Planification de version"
            )
            XCTAssertEqual(
                runtimeTranscriptPreviewLoadAccessibilityLabel(title: ""),
                "Charger l’aperçu de la transcription pour Chat sans titre"
            )
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: true), "Sélectionné")
            XCTAssertEqual(runtimeChatSessionSelectionAccessibilityValue(isSelected: false), "Non sélectionné")
            XCTAssertEqual(runtimeTranscriptPreviewLoadAccessibilityHint(), "Charger cet aperçu de transcription détenu par le runtime.")
            XCTAssertEqual(NSLocalizedString("No transcript messages", comment: ""), "Aucun message de transcription")
            XCTAssertEqual(NSLocalizedString("Thinking", comment: ""), "Réflexion")
            XCTAssertEqual(runtimeTranscriptReasoningToggleTitle(isExpanded: false), "Afficher la réflexion")
            XCTAssertEqual(runtimeTranscriptReasoningToggleTitle(isExpanded: true), "Masquer la réflexion")
            XCTAssertEqual(runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded: true), "Réduire pour garder un aperçu court de la réflexion.")
            XCTAssertEqual(runtimeTranscriptRoleDisplayName("assistant"), "Assistant IA")
            XCTAssertEqual(runtimeTranscriptRoleDisplayName("other"), "Message")
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: "29 juin 2026 à 02:00"),
                "Créé 29 juin 2026 à 02:00"
            )
            XCTAssertEqual(
                runtimeTranscriptMessageCreatedAccessibilityLabel(createdAt: ""),
                "Créé Heure de création inconnue"
            )
            XCTAssertEqual(localizedRuntimeChatSessionStatus("active"), "Actif")
        }
    }

    func testRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded() {
        let reasoning = "first step\nsecond step\nthird step\nfourth step"
        let collapsed = runtimeTranscriptReasoningDisplayPolicy(
            reasoning: reasoning,
            expanded: false
        )
        let expanded = runtimeTranscriptReasoningDisplayPolicy(
            reasoning: reasoning,
            expanded: true
        )

        XCTAssertEqual(collapsed.text, "first step\nsecond step\nthird step")
        XCTAssertEqual(collapsed.maxLines, runtimeTranscriptReasoningPreviewMaxLines)
        XCTAssertEqual(collapsed.contentOpacity, runtimeTranscriptReasoningCollapsedOpacity)
        XCTAssertTrue(collapsed.expandable)
        XCTAssertFalse(collapsed.isExpanded)

        XCTAssertEqual(expanded.text, reasoning)
        XCTAssertNil(expanded.maxLines)
        XCTAssertEqual(expanded.contentOpacity, runtimeTranscriptReasoningExpandedOpacity)
        XCTAssertTrue(expanded.expandable)
        XCTAssertTrue(expanded.isExpanded)
    }

    func testRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs() {
        XCTAssertFalse(runtimeTranscriptReasoningNeedsExpansion("first step\nsecond step\nthird step"))
        XCTAssertFalse(runtimeTranscriptReasoningNeedsExpansion(" \n\t\n "))

        let longParagraph = Array(repeating: "planning", count: 80).joined(separator: " ")
        let preview = runtimeTranscriptReasoningPreview(longParagraph)

        XCTAssertTrue(runtimeTranscriptReasoningNeedsExpansion(longParagraph))
        XCTAssertTrue(preview.hasSuffix("..."))
        XCTAssertLessThanOrEqual(preview.count, 183)
    }

    func testRuntimeMemoryInspectorCopyLocalizesAcrossSupportedLanguages() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime Memory", comment: ""), "Inspect Runtime Memory")
            XCTAssertEqual(NSLocalizedString("Runtime Memory Inspector", comment: ""), "Runtime Memory Inspector")
            XCTAssertEqual(NSLocalizedString("Close Runtime Memory Inspector", comment: ""), "Close Runtime Memory Inspector")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime Memory Inspector", comment: ""), "Refresh Runtime Memory Inspector")
            XCTAssertEqual(NSLocalizedString("No runtime memory notes", comment: ""), "No runtime memory notes")
            XCTAssertEqual(NSLocalizedString("Paused", comment: ""), "Paused")
            XCTAssertEqual(NSLocalizedString("Approved from older chat", comment: ""), "Approved from older chat")
            XCTAssertEqual(NSLocalizedString("Show source excerpts", comment: ""), "Show source excerpts")
            XCTAssertEqual(NSLocalizedString("Hide source excerpts", comment: ""), "Hide source excerpts")

            let source = RuntimeMemoryEntrySource(
                kind: "long_inactivity_summary",
                draftID: "draft-debug-id",
                summaryMethod: "extractive",
                session: RuntimeMemoryEntrySourceSession(
                    sessionID: "session-debug-id",
                    title: "Release planning",
                    model: "qwen-local",
                    lastActivityAt: Date(timeIntervalSince1970: 100),
                    messageCount: 4,
                    inactiveSeconds: 7200
                ),
                sourceMessageCount: 4,
                sourceRange: "Messages 1-4",
                sourcePointers: [
                    RuntimeMemoryEntrySourcePointer(
                        sessionID: "session-debug-id",
                        messageIndex: 0,
                        role: "user",
                        createdAt: Date(timeIntervalSince1970: 100),
                        excerpt: "Prefer concise release notes."
                    ),
                    RuntimeMemoryEntrySourcePointer(
                        sessionID: "session-debug-id",
                        messageIndex: 1,
                        role: "assistant",
                        createdAt: Date(timeIntervalSince1970: 110),
                        excerpt: "Use short sections."
                    ),
                    RuntimeMemoryEntrySourcePointer(
                        sessionID: "session-debug-id",
                        messageIndex: 2,
                        role: "system",
                        createdAt: Date(timeIntervalSince1970: 120),
                        excerpt: "Never expose this third item by default."
                    ),
                ]
            )
            let collapsedSourceLabel = runtimeMemorySourceReviewAccessibilityLabel(source: source, isExpanded: false)

            XCTAssertEqual(runtimeMemorySourceSessionTitle(source), "Release planning")
            XCTAssertEqual(runtimeMemorySourceSessionText(source), "Source chat: Release planning")
            XCTAssertEqual(runtimeMemorySourceCoverageText(source), "Source coverage: Messages 1-4")
            XCTAssertEqual(runtimeMemorySourceVisiblePointers(source).count, 2)
            XCTAssertEqual(runtimeMemorySourcePointerText(source.sourcePointers[0]), "Source excerpt User: Prefer concise release notes.")
            XCTAssertEqual(runtimeMemorySourceHiddenExcerptText(1), "1 more source excerpts hidden")
            XCTAssertEqual(
                collapsedSourceLabel,
                "Memory source. Source chat: Release planning. Source coverage: Messages 1-4. Source review collapsed."
            )
            XCTAssertEqual(
                runtimeMemoryEntryAccessibilityLabel(
                    content: " Prefer concise answers ",
                    status: NSLocalizedString("Enabled", comment: ""),
                    createdAt: "Jun 29, 2026 at 12:50 AM",
                    updatedAt: "Jun 29, 2026 at 1:00 AM",
                    sourceSummary: collapsedSourceLabel
                ),
                "Memory note Prefer concise answers. Status Enabled. Created Jun 29, 2026 at 12:50 AM. Updated Jun 29, 2026 at 1:00 AM. Memory source. Source chat: Release planning. Source coverage: Messages 1-4. Source review collapsed."
            )

            let blankSource = RuntimeMemoryEntrySource(
                kind: "long_inactivity_summary",
                draftID: "blank-debug-id",
                summaryMethod: "extractive",
                session: RuntimeMemoryEntrySourceSession(
                    sessionID: "blank-session-debug-id",
                    title: " ",
                    model: "qwen-local",
                    lastActivityAt: Date(timeIntervalSince1970: 100),
                    messageCount: 1,
                    inactiveSeconds: 7200
                ),
                sourceMessageCount: 1,
                sourceRange: " ",
                sourcePointers: [
                    RuntimeMemoryEntrySourcePointer(
                        sessionID: "blank-session-debug-id",
                        messageIndex: 0,
                        role: "assistant",
                        createdAt: nil,
                        excerpt: " "
                    ),
                ]
            )
            XCTAssertEqual(runtimeMemorySourceSessionTitle(blankSource), "Untitled chat")
            XCTAssertEqual(runtimeMemorySourceCoverageText(blankSource), "Source coverage: Source coverage unavailable")
            XCTAssertEqual(
                runtimeMemorySourcePointerText(blankSource.sourcePointers[0]),
                "Source excerpt Assistant: Source excerpt unavailable"
            )
        }

        withStoredAppLanguage("ko") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime Memory", comment: ""), "런타임 메모리 점검")
            XCTAssertEqual(NSLocalizedString("Runtime Memory Inspector", comment: ""), "런타임 메모리 점검")
            XCTAssertEqual(NSLocalizedString("Close Runtime Memory Inspector", comment: ""), "런타임 메모리 점검 닫기")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime Memory Inspector", comment: ""), "런타임 메모리 점검 새로 고침")
            XCTAssertEqual(NSLocalizedString("No runtime memory notes", comment: ""), "런타임 메모리 노트 없음")
            XCTAssertEqual(NSLocalizedString("Paused", comment: ""), "일시 중지됨")
            XCTAssertEqual(NSLocalizedString("Approved from older chat", comment: ""), "이전 채팅에서 승인됨")
            XCTAssertEqual(NSLocalizedString("Show source excerpts", comment: ""), "원본 발췌 보기")
            XCTAssertEqual(NSLocalizedString("Hide source excerpts", comment: ""), "원본 발췌 숨기기")
        }

        withStoredAppLanguage("ja") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime Memory", comment: ""), "ランタイムメモリを確認")
            XCTAssertEqual(NSLocalizedString("Runtime Memory Inspector", comment: ""), "ランタイムメモリインスペクタ")
            XCTAssertEqual(NSLocalizedString("Close Runtime Memory Inspector", comment: ""), "ランタイムメモリインスペクタを閉じる")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime Memory Inspector", comment: ""), "ランタイムメモリインスペクタを更新")
            XCTAssertEqual(NSLocalizedString("No runtime memory notes", comment: ""), "ランタイムメモリノートはありません")
            XCTAssertEqual(NSLocalizedString("Paused", comment: ""), "一時停止")
            XCTAssertEqual(NSLocalizedString("Approved from older chat", comment: ""), "以前のチャットから承認済み")
            XCTAssertEqual(NSLocalizedString("Show source excerpts", comment: ""), "参照抜粋を表示")
            XCTAssertEqual(NSLocalizedString("Hide source excerpts", comment: ""), "参照抜粋を隠す")
        }

        withStoredAppLanguage("zh-Hans") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime Memory", comment: ""), "检查运行时记忆")
            XCTAssertEqual(NSLocalizedString("Runtime Memory Inspector", comment: ""), "运行时记忆检查器")
            XCTAssertEqual(NSLocalizedString("Close Runtime Memory Inspector", comment: ""), "关闭运行时记忆检查器")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime Memory Inspector", comment: ""), "刷新运行时记忆检查器")
            XCTAssertEqual(NSLocalizedString("No runtime memory notes", comment: ""), "没有运行时记忆笔记")
            XCTAssertEqual(NSLocalizedString("Paused", comment: ""), "已暂停")
            XCTAssertEqual(NSLocalizedString("Approved from older chat", comment: ""), "来自旧聊天的已批准内容")
            XCTAssertEqual(NSLocalizedString("Show source excerpts", comment: ""), "显示来源摘录")
            XCTAssertEqual(NSLocalizedString("Hide source excerpts", comment: ""), "隐藏来源摘录")
        }

        withStoredAppLanguage("fr") {
            XCTAssertEqual(NSLocalizedString("Inspect Runtime Memory", comment: ""), "Inspecter la mémoire du runtime")
            XCTAssertEqual(NSLocalizedString("Runtime Memory Inspector", comment: ""), "Inspecteur de mémoire du runtime")
            XCTAssertEqual(NSLocalizedString("Close Runtime Memory Inspector", comment: ""), "Fermer l’inspecteur de mémoire du runtime")
            XCTAssertEqual(NSLocalizedString("Refresh Runtime Memory Inspector", comment: ""), "Actualiser l’inspecteur de mémoire du runtime")
            XCTAssertEqual(NSLocalizedString("No runtime memory notes", comment: ""), "Aucune note de mémoire du runtime")
            XCTAssertEqual(NSLocalizedString("Paused", comment: ""), "Suspendu")
            XCTAssertEqual(NSLocalizedString("Approved from older chat", comment: ""), "Approuvé depuis un ancien chat")
            XCTAssertEqual(NSLocalizedString("Show source excerpts", comment: ""), "Afficher les extraits source")
            XCTAssertEqual(NSLocalizedString("Hide source excerpts", comment: ""), "Masquer les extraits source")
        }
    }

    func testEnglishLocalizationKeepsReleaseFacingConnectionAndDetailsCopy() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(NSLocalizedString("Technical Details", comment: ""), "Details")
            XCTAssertEqual(NSLocalizedString("Provider endpoint redacted.", comment: ""), "Provider address hidden.")
            XCTAssertEqual(NSLocalizedString("Connection Recovery", comment: ""), "Connection Recovery")
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
        let expectations: [(languageTag: String, label: String, punctuatedLabel: String, fallbackLabel: String)] = [
            (
                "en",
                "Details for Received device runtime request",
                "Details for Saved connection details removed",
                "Details for Runtime event recorded"
            ),
            (
                "ko",
                "기기 런타임 요청 수신의 세부 정보",
                "저장된 연결 정보를 제거했습니다의 세부 정보",
                "런타임 이벤트가 기록되었습니다의 세부 정보"
            ),
            (
                "ja",
                "デバイスランタイムリクエストを受信しました の詳細",
                "保存済みの接続情報を削除しました の詳細",
                "ランタイムイベントを記録しました の詳細"
            ),
            (
                "zh-Hans",
                "已收到设备运行时请求 的详情",
                "已移除保存的连接信息 的详情",
                "已记录运行时事件 的详情"
            ),
            (
                "fr",
                "Détails pour Requête runtime d’appareil reçue",
                "Détails pour Informations de connexion enregistrées supprimées",
                "Détails pour Événement du runtime enregistré"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let receivedSummary = localizedLogDisplay("Received chat.send").summary
                let punctuatedSummary = localizedLogDisplay("Remote route disabled").summary
                XCTAssertEqual(logTechnicalDetailsAccessibilityLabel(summary: " \(receivedSummary) "), expectation.label)
                XCTAssertEqual(logTechnicalDetailsAccessibilityLabel(summary: " \(punctuatedSummary)． "), expectation.punctuatedLabel)
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
        let expectations: [(languageTag: String, warningLabel: String, positionedWarningLabel: String, fallbackLabel: String)] = [
            (
                "en",
                "Activity item AetherLink Runtime needs attention. Status Needs attention.",
                "Activity item 2 of 5. AetherLink Runtime needs attention. Status Needs attention.",
                "Activity item Runtime event recorded. Status Pending."
            ),
            (
                "ko",
                "활동 항목 AetherLink Runtime 확인이 필요합니다. 상태 확인 필요.",
                "활동 항목 2/5. AetherLink Runtime 확인이 필요합니다. 상태 확인 필요.",
                "활동 항목 런타임 이벤트가 기록되었습니다. 상태 대기 중."
            ),
            (
                "ja",
                "アクティビティ項目 AetherLink Runtime の確認が必要です。ステータス 確認が必要。",
                "アクティビティ項目 2/5。AetherLink Runtime の確認が必要です。ステータス 確認が必要。",
                "アクティビティ項目 ランタイムイベントを記録しました。ステータス 保留中。"
            ),
            (
                "zh-Hans",
                "活动项 AetherLink Runtime 需要检查。状态 需要注意。",
                "活动项 2/5。AetherLink Runtime 需要检查。状态 需要注意。",
                "活动项 已记录运行时事件。状态 待处理。"
            ),
            (
                "fr",
                "Élément d’activité AetherLink Runtime demande une vérification. État Attention requise.",
                "Élément d’activité 2 sur 5. AetherLink Runtime demande une vérification. État Attention requise.",
                "Élément d’activité Événement du runtime enregistré. État En attente."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let warningSummary = localizedLogDisplay("Runtime listener failed: port unavailable").summary
                XCTAssertEqual(logRowAccessibilityLabel(summary: warningSummary, tone: .warning), expectation.warningLabel)
                XCTAssertEqual(
                    logRowAccessibilityLabel(summary: warningSummary, tone: .warning, position: 2, totalCount: 5),
                    expectation.positionedWarningLabel
                )
                XCTAssertEqual(logRowAccessibilityLabel(summary: " ", tone: .neutral), expectation.fallbackLabel)
            }
        }
    }

    func testActivityLogListAccessibilitySummaryUsesSelectedLanguage() {
        let expectations: [(languageTag: String, label: String, oneItemValue: String, multipleItemsValue: String)] = [
            (
                "en",
                "Activity log",
                "1 activity item",
                "3 activity items"
            ),
            (
                "ko",
                "활동 로그",
                "활동 항목 1개",
                "활동 항목 3개"
            ),
            (
                "ja",
                "アクティビティログ",
                "アクティビティ項目 1 件",
                "アクティビティ項目 3 件"
            ),
            (
                "zh-Hans",
                "活动日志",
                "1 个活动项",
                "3 个活动项"
            ),
            (
                "fr",
                "Journal d’activité",
                "1 élément d’activité",
                "3 éléments d’activité"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(activityLogListAccessibilityLabel(), expectation.label, expectation.languageTag)
                XCTAssertEqual(activityLogListAccessibilityValue(count: 1), expectation.oneItemValue, expectation.languageTag)
                XCTAssertEqual(activityLogListAccessibilityValue(count: 3), expectation.multipleItemsValue, expectation.languageTag)
            }
        }
    }

    func testActivityRouteSuccessLogRowsUseReadyTone() {
        let expectations: [(languageTag: String, readyLabel: String)] = [
            (
                "en",
                "Activity item Connection details are ready. Status Ready."
            ),
            (
                "ko",
                "활동 항목 연결 정보가 준비되었습니다. 상태 준비됨."
            ),
            (
                "ja",
                "アクティビティ項目 接続情報の準備ができました。ステータス 準備完了。"
            ),
            (
                "zh-Hans",
                "活动项 连接信息已就绪。状态 就绪。"
            ),
            (
                "fr",
                "Élément d’activité Informations de connexion prêtes. État Prêt."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let readyLine = "Remote route ready: relay.example.test:43171"
                let readySummary = localizedLogDisplay(readyLine).summary

                XCTAssertEqual(activityLogTone(for: "Route secret regenerated"), .ready)
                XCTAssertEqual(activityLogTone(for: "Remote route enabled: relay.example.test:43171"), .ready)
                XCTAssertEqual(activityLogTone(for: "Remote route configured: relay.example.test:43171"), .ready)
                XCTAssertEqual(activityLogTone(for: "Remote route allocated: relay.example.test:43171"), .ready)
                XCTAssertEqual(activityLogTone(for: "Remote route bootstrap allocated route abc"), .ready)
                XCTAssertEqual(activityLogTone(for: readyLine), .ready)
                XCTAssertEqual(activityLogTone(for: "Remote route ready: relay.example.test:43171"), .ready)
                XCTAssertEqual(activityLogTone(for: "Remote route lease refreshed: relay.example.test:43171"), .ready)
                XCTAssertEqual(activityLogTone(for: "Remote route allocation failed: denied"), .warning)
                XCTAssertEqual(
                    logRowAccessibilityLabel(summary: readySummary, tone: activityLogTone(for: readyLine)),
                    expectation.readyLabel,
                    expectation.languageTag
                )
            }
        }
    }

    func testActivityModelResidencyLogSummariesUseSpecificLocalizedEvents() {
        let expectations: [
            (
                languageTag: String,
                active: String,
                requested: String,
                unloaded: String,
                failed: String,
                manualRequested: String,
                manualUnloaded: String,
                manualFailed: String,
                activeAccessibility: String,
                failedAccessibility: String,
                manualFailedAccessibility: String
            )
        ] = [
            (
                "en",
                "Active model is ready for runtime requests.",
                "Model unload requested by runtime policy.",
                "Model unloaded by runtime policy.",
                "Model unload failed. Check Activity.",
                "Manual model unload requested.",
                "Manual model unloaded.",
                "Manual model unload failed. Check Activity.",
                "Activity item Active model is ready for runtime requests. Status Ready.",
                "Activity item Model unload failed. Check Activity. Status Needs attention.",
                "Activity item Manual model unload failed. Check Activity. Status Needs attention."
            ),
            (
                "ko",
                "활성 모델이 런타임 요청을 처리할 준비가 되었습니다.",
                "런타임 정책이 모델 언로드를 요청했습니다.",
                "런타임 정책으로 모델을 언로드했습니다.",
                "모델 내리기에 실패했습니다. 활동을 확인하세요.",
                "수동 모델 언로드를 요청했습니다.",
                "수동으로 모델을 언로드했습니다.",
                "수동 모델 언로드에 실패했습니다. 활동을 확인하세요.",
                "활동 항목 활성 모델이 런타임 요청을 처리할 준비가 되었습니다. 상태 준비됨.",
                "활동 항목 모델 내리기에 실패했습니다. 활동을 확인하세요. 상태 확인 필요.",
                "활동 항목 수동 모델 언로드에 실패했습니다. 활동을 확인하세요. 상태 확인 필요."
            ),
            (
                "ja",
                "アクティブなモデルはランタイムリクエストを処理できます。",
                "ランタイムポリシーがモデルのアンロードを要求しました。",
                "ランタイムポリシーによりモデルをアンロードしました。",
                "モデルのアンロードに失敗しました。アクティビティを確認してください。",
                "手動モデルアンロードを要求しました。",
                "手動でモデルをアンロードしました。",
                "手動モデルのアンロードに失敗しました。アクティビティを確認してください。",
                "アクティビティ項目 アクティブなモデルはランタイムリクエストを処理できます。ステータス 準備完了。",
                "アクティビティ項目 モデルのアンロードに失敗しました。アクティビティを確認してください。ステータス 確認が必要。",
                "アクティビティ項目 手動モデルのアンロードに失敗しました。アクティビティを確認してください。ステータス 確認が必要。"
            ),
            (
                "zh-Hans",
                "活动模型已准备好处理运行时请求。",
                "运行时策略已请求卸载模型。",
                "已通过运行时策略卸载模型。",
                "模型卸载失败。请查看活动。",
                "已请求手动卸载模型。",
                "已手动卸载模型。",
                "手动卸载模型失败。请查看活动。",
                "活动项 活动模型已准备好处理运行时请求。状态 就绪。",
                "活动项 模型卸载失败。请查看活动。状态 需要注意。",
                "活动项 手动卸载模型失败。请查看活动。状态 需要注意。"
            ),
            (
                "fr",
                "Le modèle actif est prêt pour les requêtes du runtime.",
                "La stratégie du runtime a demandé le déchargement du modèle.",
                "Le modèle a été déchargé par la stratégie du runtime.",
                "Échec du déchargement du modèle. Consultez Activité.",
                "Déchargement manuel du modèle demandé.",
                "Modèle déchargé manuellement.",
                "Échec du déchargement manuel du modèle. Consultez Activité.",
                "Élément d’activité Le modèle actif est prêt pour les requêtes du runtime. État Prêt.",
                "Élément d’activité Échec du déchargement du modèle. Consultez Activité. État Attention requise.",
                "Élément d’activité Échec du déchargement manuel du modèle. Consultez Activité. État Attention requise."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        let activeLine = "Model residency active: Ollama llama3.1"
        let requestedLine = "Model unload requested: Ollama llama3.1 (model switch)"
        let unloadedLine = "Model unloaded: Ollama llama3.1 (idle timeout)"
        let failedLine = "Model unload failed: LM Studio qwen3 (idle timeout): provider refused unload"
        let manualRequestedLine = "Model unload requested: Ollama llama3.1 (manual)"
        let manualUnloadedLine = "Model unloaded: Ollama llama3.1 (manual)"
        let manualFailedLine = "Model unload failed: LM Studio qwen3 (manual): provider refused unload"

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let activeDisplay = localizedLogDisplay(activeLine)
                let requestedDisplay = localizedLogDisplay(requestedLine)
                let unloadedDisplay = localizedLogDisplay(unloadedLine)
                let failedDisplay = localizedLogDisplay(failedLine)
                let manualRequestedDisplay = localizedLogDisplay(manualRequestedLine)
                let manualUnloadedDisplay = localizedLogDisplay(manualUnloadedLine)
                let manualFailedDisplay = localizedLogDisplay(manualFailedLine)

                XCTAssertEqual(activeDisplay.summary, expectation.active, expectation.languageTag)
                XCTAssertEqual(requestedDisplay.summary, expectation.requested, expectation.languageTag)
                XCTAssertEqual(unloadedDisplay.summary, expectation.unloaded, expectation.languageTag)
                XCTAssertEqual(failedDisplay.summary, expectation.failed, expectation.languageTag)
                XCTAssertEqual(manualRequestedDisplay.summary, expectation.manualRequested, expectation.languageTag)
                XCTAssertEqual(manualUnloadedDisplay.summary, expectation.manualUnloaded, expectation.languageTag)
                XCTAssertEqual(manualFailedDisplay.summary, expectation.manualFailed, expectation.languageTag)
                XCTAssertEqual(modelResidencyEventSummary(manualRequestedLine), expectation.manualRequested, expectation.languageTag)
                XCTAssertEqual(modelResidencyEventSummary(manualUnloadedLine), expectation.manualUnloaded, expectation.languageTag)
                XCTAssertEqual(modelResidencyEventSummary(manualFailedLine), expectation.manualFailed, expectation.languageTag)
                XCTAssertEqual(activeDisplay.diagnostic, activeLine, expectation.languageTag)
                XCTAssertEqual(requestedDisplay.diagnostic, requestedLine, expectation.languageTag)
                XCTAssertEqual(unloadedDisplay.diagnostic, unloadedLine, expectation.languageTag)
                XCTAssertEqual(failedDisplay.diagnostic, failedLine, expectation.languageTag)
                XCTAssertEqual(manualRequestedDisplay.diagnostic, manualRequestedLine, expectation.languageTag)
                XCTAssertEqual(manualUnloadedDisplay.diagnostic, manualUnloadedLine, expectation.languageTag)
                XCTAssertEqual(manualFailedDisplay.diagnostic, manualFailedLine, expectation.languageTag)
                XCTAssertFalse(activeDisplay.summary.contains("Model residency updated"), expectation.languageTag)
                XCTAssertFalse(requestedDisplay.summary.contains("Model residency updated"), expectation.languageTag)
                XCTAssertFalse(unloadedDisplay.summary.contains("Model residency updated"), expectation.languageTag)
                XCTAssertFalse(failedDisplay.summary.contains("Model residency updated"), expectation.languageTag)
                XCTAssertFalse(manualRequestedDisplay.summary.contains("runtime policy"), expectation.languageTag)
                XCTAssertFalse(manualUnloadedDisplay.summary.contains("runtime policy"), expectation.languageTag)
                XCTAssertFalse(manualFailedDisplay.summary.contains("runtime policy"), expectation.languageTag)

                XCTAssertEqual(activityLogTone(for: activeLine), .ready, expectation.languageTag)
                XCTAssertEqual(activityLogTone(for: requestedLine), .neutral, expectation.languageTag)
                XCTAssertEqual(activityLogTone(for: unloadedLine), .neutral, expectation.languageTag)
                XCTAssertEqual(activityLogTone(for: failedLine), .warning, expectation.languageTag)
                XCTAssertEqual(activityLogTone(for: manualRequestedLine), .neutral, expectation.languageTag)
                XCTAssertEqual(activityLogTone(for: manualUnloadedLine), .neutral, expectation.languageTag)
                XCTAssertEqual(activityLogTone(for: manualFailedLine), .warning, expectation.languageTag)
                XCTAssertEqual(
                    logRowAccessibilityLabel(summary: activeDisplay.summary, tone: activityLogTone(for: activeLine)),
                    expectation.activeAccessibility,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    logRowAccessibilityLabel(summary: failedDisplay.summary, tone: activityLogTone(for: failedLine)),
                    expectation.failedAccessibility,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    logRowAccessibilityLabel(summary: manualFailedDisplay.summary, tone: activityLogTone(for: manualFailedLine)),
                    expectation.manualFailedAccessibility,
                    expectation.languageTag
                )
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
    func testRouteDiagnosticsPanelStaysHiddenOnCleanFirstRunAndPairingHidesSetup() throws {
        let cleanFirstRunModel = CompanionAppModel(
            environment: isolatedRuntimeIdentityEnvironment(),
            userDefaults: try isolatedDefaults()
        )
        XCTAssertFalse(cleanFirstRunModel.hasDevelopmentRelayRoute)
        XCTAssertFalse(cleanFirstRunModel.bootstrapRelaySettings.isEnabled)
        XCTAssertNil(cleanFirstRunModel.remoteRoutePreparationIssue)
        XCTAssertFalse(shouldShowRouteDiagnosticsPanel(model: cleanFirstRunModel))
        XCTAssertFalse(shouldShowPairingRouteSetupPanel(model: cleanFirstRunModel))

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
        XCTAssertTrue(shouldShowPairingRouteSetupPanel(model: savedRouteModel))

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
        XCTAssertTrue(shouldShowPairingRouteSetupPanel(model: routeIssueModel))
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
            runtimeStatusAccessibilityLabel: String,
            modelServiceStatus: String,
            modelServiceStatusAccessibilityLabel: String,
            commandTitles: MenuBarCommandTitles
        )] = [
            (
                "en",
                "Runtime: Ready for devices",
                "Runtime status: Ready for devices",
                "Model service: Not checked",
                "Model service status: Not checked",
                MenuBarCommandTitles(
                    openAetherLink: "Open AetherLink",
                    refresh: "Refresh",
                    loadModels: "Load Models",
                    refreshModelResidency: "Refresh Model Residency",
                    unloadResidentModel: "Unload Resident Model",
                    quit: "Quit"
                )
            ),
            (
                "ko",
                "런타임: 기기 연결 준비됨",
                "런타임 상태: 기기 연결 준비됨",
                "모델 서비스: 확인 전",
                "모델 서비스 상태: 확인 전",
                MenuBarCommandTitles(
                    openAetherLink: "AetherLink 열기",
                    refresh: "새로고침",
                    loadModels: "모델 불러오기",
                    refreshModelResidency: "모델 상주 상태 새로 고침",
                    unloadResidentModel: "상주 모델 언로드",
                    quit: "종료"
                )
            ),
            (
                "ja",
                "ランタイム: デバイスの準備完了",
                "ランタイム状態: デバイスの準備完了",
                "モデルサービス: 未確認",
                "モデルサービス状態: 未確認",
                MenuBarCommandTitles(
                    openAetherLink: "AetherLink を開く",
                    refresh: "更新",
                    loadModels: "モデルを読み込む",
                    refreshModelResidency: "モデル常駐状態を更新",
                    unloadResidentModel: "常駐モデルをアンロード",
                    quit: "終了"
                )
            ),
            (
                "zh-Hans",
                "运行时：已准备连接设备",
                "运行时状态：已准备连接设备",
                "模型服务：未检查",
                "模型服务状态：未检查",
                MenuBarCommandTitles(
                    openAetherLink: "打开 AetherLink",
                    refresh: "刷新",
                    loadModels: "加载模型",
                    refreshModelResidency: "刷新模型驻留状态",
                    unloadResidentModel: "卸载驻留模型",
                    quit: "退出"
                )
            ),
            (
                "fr",
                "Runtime : Prêt pour les appareils",
                "État du runtime : Prêt pour les appareils",
                "Service de modèles : Non vérifié",
                "État du service de modèles : Non vérifié",
                MenuBarCommandTitles(
                    openAetherLink: "Ouvrir AetherLink",
                    refresh: "Actualiser",
                    loadModels: "Charger les modèles",
                    refreshModelResidency: "Actualiser la résidence du modèle",
                    unloadResidentModel: "Décharger le modèle résident",
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
                    menuBarRuntimeStatusAccessibilityLabel(.advertising(serviceName: "AetherLink", port: 43170)),
                    expectation.runtimeStatusAccessibilityLabel,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    menuBarModelServiceStatusText([]),
                    expectation.modelServiceStatus,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    menuBarModelServiceStatusAccessibilityLabel([]),
                    expectation.modelServiceStatusAccessibilityLabel,
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

    func testMenuBarWindowAndQuitAccessibilityHintsUseSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            openHint: String,
            quitHint: String
        )] = [
            (
                "en",
                "Open the AetherLink window and bring it to the front.",
                "Quit AetherLink Runtime."
            ),
            (
                "ko",
                "AetherLink 창을 열고 앞으로 가져옵니다.",
                "AetherLink Runtime을 종료합니다."
            ),
            (
                "ja",
                "AetherLink ウインドウを開いて前面に表示します。",
                "AetherLink Runtime を終了します。"
            ),
            (
                "zh-Hans",
                "打开 AetherLink 窗口并置于前台。",
                "退出 AetherLink Runtime。"
            ),
            (
                "fr",
                "Ouvre la fenêtre AetherLink et la place au premier plan.",
                "Quitte AetherLink Runtime."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    menuBarOpenAetherLinkAccessibilityHint(),
                    expectation.openHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    menuBarQuitAccessibilityHint(),
                    expectation.quitHint,
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
            loadModelsHint: String,
            refreshRuntimeDataHint: String,
            refreshModelResidencyHint: String,
            unloadResidentModelHint: String,
            unloadResidentModelNoModelValue: String,
            unloadResidentModelNoModelHint: String,
            unloadResidentModelBusyValue: String,
            unloadResidentModelBusyHint: String,
            inspectHistoryHint: String,
            inspectMemoryHint: String
        )] = [
            (
                "en",
                "Ready",
                "Check model provider availability through AetherLink Runtime.",
                "Load the installed local model list through AetherLink Runtime.",
                "Refresh runtime-owned chat history and memory counts.",
                "Refresh the runtime model residency status.",
                "Unload the active resident model now through AetherLink Runtime.",
                "No resident model",
                "No resident model is active through AetherLink Runtime.",
                "Generation in progress",
                "Wait for the active generation to finish before unloading the resident model.",
                "Inspect runtime-owned chat sessions stored on AetherLink Runtime.",
                "Inspect runtime-owned memory notes stored on AetherLink Runtime."
            ),
            (
                "ko",
                "준비됨",
                "AetherLink Runtime을 통해 모델 제공자 사용 가능 여부를 확인합니다.",
                "AetherLink Runtime을 통해 설치된 로컬 모델 목록을 불러옵니다.",
                "런타임에 저장된 채팅 기록과 메모리 개수를 새로 고칩니다.",
                "런타임 모델 상주 상태를 새로 고칩니다.",
                "AetherLink Runtime을 통해 활성 상주 모델을 지금 언로드합니다.",
                "상주 모델 없음",
                "AetherLink Runtime에 활성 상주 모델이 없습니다.",
                "생성 진행 중",
                "상주 모델을 언로드하기 전에 활성 생성을 마칠 때까지 기다립니다.",
                "AetherLink Runtime에 저장된 런타임 소유 채팅 세션을 확인합니다.",
                "AetherLink Runtime에 저장된 런타임 소유 메모리 노트를 확인합니다."
            ),
            (
                "ja",
                "準備完了",
                "AetherLink Runtime 経由でモデルプロバイダーの利用可否を確認します。",
                "AetherLink Runtime 経由でインストール済みローカルモデルの一覧を読み込みます。",
                "ランタイムが保持するチャット履歴とメモリ数を更新します。",
                "ランタイムのモデル常駐状態を更新します。",
                "AetherLink Runtime 経由でアクティブな常駐モデルを今すぐアンロードします。",
                "常駐モデルなし",
                "AetherLink Runtime でアクティブな常駐モデルはありません。",
                "生成中",
                "常駐モデルをアンロードする前に、アクティブな生成が完了するまで待ちます。",
                "AetherLink Runtime に保存されたランタイム所有のチャットセッションを確認します。",
                "AetherLink Runtime に保存されたランタイム所有のメモリノートを確認します。"
            ),
            (
                "zh-Hans",
                "就绪",
                "通过 AetherLink Runtime 检查模型提供方可用性。",
                "通过 AetherLink Runtime 加载已安装的本地模型列表。",
                "刷新运行时保存的聊天历史和记忆数量。",
                "刷新运行时模型驻留状态。",
                "通过 AetherLink Runtime 立即卸载活动驻留模型。",
                "无驻留模型",
                "AetherLink Runtime 中没有活动驻留模型。",
                "正在生成",
                "等待活动生成完成后再卸载驻留模型。",
                "检查 AetherLink Runtime 中存储的运行时拥有的聊天会话。",
                "检查 AetherLink Runtime 中存储的运行时拥有的记忆笔记。"
            ),
            (
                "fr",
                "Prêt",
                "Vérifie la disponibilité des fournisseurs de modèles via AetherLink Runtime.",
                "Charge la liste des modèles locaux installés via AetherLink Runtime.",
                "Actualise l’historique de chat et les compteurs de mémoire conservés par le runtime.",
                "Actualise l’état de résidence du modèle du runtime.",
                "Décharge immédiatement le modèle résident actif via AetherLink Runtime.",
                "Aucun modèle résident",
                "Aucun modèle résident n’est actif via AetherLink Runtime.",
                "Génération en cours",
                "Attendez la fin de la génération active avant de décharger le modèle résident.",
                "Inspecter les sessions de chat détenues par le runtime et stockées dans AetherLink Runtime.",
                "Inspecter les notes de mémoire détenues par le runtime et stockées dans AetherLink Runtime."
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
                XCTAssertEqual(
                    refreshRuntimeDataActionAccessibilityValue(),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    refreshRuntimeDataActionAccessibilityHint(),
                    expectation.refreshRuntimeDataHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    refreshModelResidencyActionAccessibilityValue(),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    refreshModelResidencyActionAccessibilityHint(),
                    expectation.refreshModelResidencyHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityValue(canUnload: true, inFlightGenerations: 0),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityHint(canUnload: true, inFlightGenerations: 0),
                    expectation.unloadResidentModelHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityValue(canUnload: false, inFlightGenerations: 0),
                    expectation.unloadResidentModelNoModelValue,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityHint(canUnload: false, inFlightGenerations: 0),
                    expectation.unloadResidentModelNoModelHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityValue(canUnload: false, inFlightGenerations: 1),
                    expectation.unloadResidentModelBusyValue,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityHint(canUnload: false, inFlightGenerations: 1),
                    expectation.unloadResidentModelBusyHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    inspectRuntimeHistoryActionAccessibilityValue(),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    inspectRuntimeHistoryActionAccessibilityHint(),
                    expectation.inspectHistoryHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    inspectRuntimeMemoryActionAccessibilityValue(),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    inspectRuntimeMemoryActionAccessibilityHint(),
                    expectation.inspectMemoryHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testModelIdleUnloadPolicyPickerUsesSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            label: String,
            options: [String],
            hint: String,
            updatingHint: String,
            unavailable: String,
            unsupportedHint: String
        )] = [
            (
                "en",
                "Idle Unload",
                ["5 min", "10 min", "30 min"],
                "Choose when an idle resident model is unloaded.",
                "Wait for the current idle unload policy update to finish.",
                "Unavailable",
                "Model residency is not managed by this provider."
            ),
            (
                "ko",
                "유휴 시 언로드",
                ["5분", "10분", "30분"],
                "유휴 상태인 상주 모델을 언제 언로드할지 선택합니다.",
                "현재 유휴 언로드 정책 업데이트가 끝날 때까지 기다리세요.",
                "사용 불가",
                "이 제공자는 모델 상주 정책을 관리하지 않습니다."
            ),
            (
                "ja",
                "アイドル時アンロード",
                ["5分", "10分", "30分"],
                "アイドル状態の常駐モデルをアンロードするまでの時間を選択します。",
                "現在のアイドルアンロードポリシーの更新が完了するまでお待ちください。",
                "利用不可",
                "このプロバイダーではモデル常駐を管理していません。"
            ),
            (
                "zh-Hans",
                "空闲卸载",
                ["5 分", "10 分", "30 分"],
                "选择何时卸载空闲的驻留模型。",
                "请等待当前空闲卸载策略更新完成。",
                "不可用",
                "此提供方不管理模型驻留。"
            ),
            (
                "fr",
                "Déchargement après inactivité",
                ["5 min", "10 min", "30 min"],
                "Choisissez quand décharger un modèle résident inactif.",
                "Attendez la fin de la mise à jour de la stratégie de déchargement après inactivité.",
                "Indisponible",
                "La résidence du modèle n’est pas gérée par ce fournisseur."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))
        XCTAssertEqual(RuntimeModelIdleUnloadPolicy.allCases.map(\.minutes), [5, 10, 30])

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    NSLocalizedString("Idle Unload", comment: ""),
                    expectation.label,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    RuntimeModelIdleUnloadPolicy.allCases.map(modelIdleUnloadPolicyOptionTitle),
                    expectation.options,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelIdleUnloadPolicyPickerAccessibilityValue(
                        policy: .tenMinutes,
                        isSupported: true
                    ),
                    expectation.options[1],
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelIdleUnloadPolicyPickerAccessibilityHint(isSupported: true),
                    expectation.hint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelIdleUnloadPolicyPickerAccessibilityHint(
                        isSupported: true,
                        isUpdating: true
                    ),
                    expectation.updatingHint,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelIdleUnloadPolicyPickerAccessibilityValue(
                        policy: .tenMinutes,
                        isSupported: false
                    ),
                    expectation.unavailable,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    modelIdleUnloadPolicyPickerAccessibilityHint(isSupported: false),
                    expectation.unsupportedHint,
                    expectation.languageTag
                )
            }
        }
    }

    func testModelResidencyUnloadConfirmationStatesUseSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            unloading: String,
            unloadingDetail: String,
            unloadingActionValue: String,
            unloadingActionHint: String,
            needsAttention: String,
            failureDetail: String
        )] = [
            (
                "en",
                "Unloading",
                "Ollama qwen-local is being unloaded by AetherLink Runtime.",
                "Model unload in progress",
                "Wait for the current model unload to finish.",
                "Needs attention",
                "Could not confirm Ollama qwen-local was unloaded. It may still be resident."
            ),
            (
                "ko",
                "언로드 중",
                "AetherLink Runtime에서 Ollama qwen-local 모델을 언로드하고 있습니다.",
                "모델 언로드 진행 중",
                "현재 모델 언로드가 끝날 때까지 기다리세요.",
                "확인 필요",
                "Ollama qwen-local 모델이 언로드되었는지 확인할 수 없습니다. 아직 상주 중일 수 있습니다."
            ),
            (
                "ja",
                "アンロード中",
                "AetherLink Runtime が Ollama qwen-local をアンロードしています。",
                "モデルのアンロード中",
                "現在のモデルのアンロードが完了するまでお待ちください。",
                "確認が必要",
                "Ollama qwen-local がアンロードされたことを確認できません。まだ常駐している可能性があります。"
            ),
            (
                "zh-Hans",
                "正在卸载",
                "AetherLink Runtime 正在卸载 Ollama qwen-local。",
                "正在卸载模型",
                "请等待当前模型卸载完成。",
                "需要注意",
                "无法确认 Ollama qwen-local 已卸载。它可能仍驻留在内存中。"
            ),
            (
                "fr",
                "Déchargement",
                "AetherLink Runtime décharge Ollama qwen-local.",
                "Déchargement du modèle en cours",
                "Attendez la fin du déchargement du modèle actuel.",
                "Attention requise",
                "Impossible de confirmer que Ollama qwen-local a été déchargé. Il est peut-être encore en mémoire."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                let unloading = CompanionModelResidencyStatus(
                    activeProvider: .ollama,
                    activeModelID: "qwen-local",
                    inFlightGenerations: 0,
                    idleUnloadDelaySeconds: 600,
                    unloadingProvider: .ollama,
                    unloadingModelID: "qwen-local",
                    unloadingReason: .manual,
                    lastEvent: nil,
                    supported: true
                )
                XCTAssertEqual(
                    localizedModelResidencyStatusValue(unloading),
                    expectation.unloading,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    localizedModelResidencyStatusDetail(unloading),
                    expectation.unloadingDetail,
                    expectation.languageTag
                )
                XCTAssertEqual(modelResidencyStatusTone(unloading), .neutral, expectation.languageTag)
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityValue(
                        canUnload: false,
                        inFlightGenerations: 0,
                        isUnloading: true
                    ),
                    expectation.unloadingActionValue,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    unloadResidentModelActionAccessibilityHint(
                        canUnload: false,
                        inFlightGenerations: 0,
                        isUnloading: true
                    ),
                    expectation.unloadingActionHint,
                    expectation.languageTag
                )

                let failure = CompanionModelResidencyStatus(
                    activeProvider: .lmStudio,
                    activeModelID: "new-model",
                    inFlightGenerations: 0,
                    idleUnloadDelaySeconds: 600,
                    lastUnloadFailure: RuntimeModelResidencyUnloadFailure(
                        provider: .ollama,
                        modelID: "qwen-local",
                        reason: .modelSwitch
                    ),
                    lastEvent: "Model residency active: LM Studio new-model",
                    supported: true
                )
                XCTAssertEqual(
                    localizedModelResidencyStatusValue(failure),
                    expectation.needsAttention,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    localizedModelResidencyStatusDetail(failure),
                    expectation.failureDetail,
                    expectation.languageTag
                )
                XCTAssertEqual(modelResidencyStatusTone(failure), .warning, expectation.languageTag)
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

    func testReadinessRowAccessibilityLabelUsesTitleStatusDetailAndFallbacks() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Readiness AetherLink Runtime. Status Ready. Ready for paired devices.",
                "Readiness Readiness item. Status Unknown status. No readiness details"
            ),
            (
                "ko",
                "준비 상태 AetherLink 런타임. 상태 준비됨. 페어링된 기기 연결 준비됨.",
                "준비 상태 준비 항목. 상태 알 수 없음. 준비 세부 정보 없음"
            ),
            (
                "ja",
                "準備状況 AetherLink ランタイム。ステータス 準備完了。ペアリング済みデバイスの準備完了。",
                "準備状況 準備項目。ステータス 不明な状態。準備状況の詳細なし"
            ),
            (
                "zh-Hans",
                "就绪情况 AetherLink 运行时。状态 就绪。已准备好连接已配对设备。",
                "就绪情况 就绪项。状态 未知状态。无就绪详情"
            ),
            (
                "fr",
                "Préparation Runtime AetherLink. État Prêt. Prêt pour les appareils jumelés.",
                "Préparation Élément de préparation. État État inconnu. Aucun détail de préparation"
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
                XCTAssertEqual(
                    readinessRowAccessibilityLabel(title: " ", status: " ", detail: " "),
                    expectation.fallbackLabel
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

        withStoredAppLanguage("en") {
            for diagnostic in unsafeDiagnostics {
                XCTAssertEqual(sanitizedTechnicalDiagnostic(diagnostic), "Provider address hidden.")
            }

            XCTAssertEqual(
                sanitizedTechnicalDiagnostic("Remote route failed: relay.example.test:43171"),
                "Remote route failed: relay.example.test:43171"
            )
        }
    }

    func testActivityTechnicalDetailsRedactRouteSecrets() {
        let diagnostics = [
            "relay_secret=secret route_token=token rs=compact rt=route-token",
            #"{"relay_secret":"secret","relay_id":"room","relay_nonce":"nonce"}"#,
            "relaySecret: secret routeToken: token relayId: room relayNonce: nonce",
            "allocationToken bearer-token rrn=nonce ri=room",
            "p2p_record_id=record-1 p2p_encrypted_body=opaque-body-1 p2p_anti_replay_nonce=nonce-1",
            "p2pRouteClass: p2p_rendezvous p2pRecordID: record-2 p2pEncryptedBody: opaque-body-2 p2pExpiresAtEpochMillis: 4102444800000 p2pAntiReplayNonce: nonce-2",
            "p2pRecordId=record-2b p2pExpiresAt=4102444800000 p2pProtocolVersion=1",
            "pc=p2p_rendezvous prid=record-3 peb=opaque-body-3 px=4102444800000 pn=nonce-3 pv=1",
        ]

        withStoredAppLanguage("en") {
            for diagnostic in diagnostics {
                XCTAssertEqual(
                    sanitizedTechnicalDiagnostic(diagnostic),
                    "Sensitive technical detail redacted."
                )
            }
        }
    }

    func testRouteDiagnosticDisclosureRedactsSensitiveDetails() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("relay_secret=secret route_token=token rs=compact rt=route-token"),
                "Sensitive technical detail redacted."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText(#"{"relaySecret":"secret","routeToken":"token","relayNonce":"nonce"}"#),
                "Sensitive technical detail redacted."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("allocation_token: bearer-token relayId: room"),
                "Sensitive technical detail redacted."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("p2p_record_id=record-1 p2p_encrypted_body=opaque-body-1 p2p_anti_replay_nonce=nonce-1"),
                "Sensitive technical detail redacted."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText(#"{"p2pRecordID":"record-2","p2pEncryptedBody":"opaque-body-2","p2pAntiReplayNonce":"nonce-2"}"#),
                "Sensitive technical detail redacted."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("p2pRecordId=record-2b p2pExpiresAtEpochMillis=4102444800000 p2pProtocolVersion=1"),
                "Sensitive technical detail redacted."
            )
            XCTAssertEqual(
                sanitizedRouteDiagnosticDisclosureText("pc=p2p_rendezvous prid=record-3 peb=opaque-body-3 px=4102444800000 pn=nonce-3 pv=1"),
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

    func testConnectionRecoveryResultAccessibilityLabelUsesSelectedLanguageAndTone() {
        let expectations: [(
            languageTag: String,
            ready: String,
            warning: String,
            fallback: String
        )] = [
            (
                "en",
                "Connection Recovery result. Status Ready. Connection details prepared.",
                "Connection Recovery result. Status Needs attention. Check Connection Recovery.",
                "Connection Recovery result. Status Pending. No details available."
            ),
            (
                "ko",
                "연결 복구 결과. 상태 준비됨. 연결 세부 정보가 준비되었습니다.",
                "연결 복구 결과. 상태 확인 필요. 연결 복구를 확인하세요.",
                "연결 복구 결과. 상태 대기 중. 사용 가능한 세부 정보가 없습니다."
            ),
            (
                "ja",
                "接続の復旧結果。ステータス 準備完了。接続詳細を準備しました。",
                "接続の復旧結果。ステータス 確認が必要。接続の復旧を確認してください。",
                "接続の復旧結果。ステータス 保留中。利用できる詳細はありません。"
            ),
            (
                "zh-Hans",
                "连接恢复结果。状态 就绪。连接详情已准备好。",
                "连接恢复结果。状态 需要注意。检查连接恢复。",
                "连接恢复结果。状态 待处理。没有可用详情。"
            ),
            (
                "fr",
                "Résultat de récupération de connexion. État Prêt. Détails de connexion préparés.",
                "Résultat de récupération de connexion. État Attention requise. Vérifiez la récupération de connexion.",
                "Résultat de récupération de connexion. État En attente. Aucun détail disponible."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoveryResultAccessibilityLabel(
                        message: localizedConnectionRecoveryResultTestMessage(
                            "Connection details prepared.",
                            expectation.languageTag
                        ),
                        tone: .ready
                    ),
                    expectation.ready
                )
                XCTAssertEqual(
                    connectionRecoveryResultAccessibilityLabel(
                        message: localizedConnectionRecoveryResultTestMessage(
                            "Check Connection Recovery.",
                            expectation.languageTag
                        ),
                        tone: .warning
                    ),
                    expectation.warning
                )
                XCTAssertEqual(
                    connectionRecoveryResultAccessibilityLabel(message: "   ", tone: .neutral),
                    expectation.fallback
                )
            }
        }
    }

    func testConnectionRecoveryHostWarningAccessibilityLabelUsesSelectedLanguageAndTone() {
        let expectations: [(
            languageTag: String,
            warningMessage: String,
            label: String,
            fallback: String
        )] = [
            (
                "en",
                "This connection address is local-network only.",
                "Connection Recovery warning. Status Needs attention. This connection address is local-network only.",
                "Connection Recovery warning. Status Needs attention. No details available."
            ),
            (
                "ko",
                "이 연결 주소는 로컬 네트워크 전용입니다.",
                "연결 복구 경고. 상태 확인 필요. 이 연결 주소는 로컬 네트워크 전용입니다.",
                "연결 복구 경고. 상태 확인 필요. 사용 가능한 세부 정보가 없습니다."
            ),
            (
                "ja",
                "この接続アドレスはローカルネットワーク専用です。",
                "接続の復旧警告。ステータス 確認が必要。この接続アドレスはローカルネットワーク専用です。",
                "接続の復旧警告。ステータス 確認が必要。利用できる詳細はありません。"
            ),
            (
                "zh-Hans",
                "此连接地址仅限本地网络。",
                "连接恢复警告。状态 需要注意。此连接地址仅限本地网络。",
                "连接恢复警告。状态 需要注意。没有可用详情。"
            ),
            (
                "fr",
                "Cette adresse de connexion est réservée au réseau local.",
                "Avertissement de récupération de connexion. État Attention requise. Cette adresse de connexion est réservée au réseau local.",
                "Avertissement de récupération de connexion. État Attention requise. Aucun détail disponible."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoveryHostWarningAccessibilityLabel(message: expectation.warningMessage),
                    expectation.label,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryHostWarningAccessibilityLabel(message: "   "),
                    expectation.fallback,
                    expectation.languageTag
                )
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
            routeNotReadyValue: String,
            readyHint: String,
            routeNotReadyHint: String,
            missingActionHint: String
        )] = [
            (
                "en",
                "Ready",
                "Unavailable",
                "Connection details not ready",
                "Generate the latest pairing QR with saved connection details.",
                "Connection details are not ready for QR generation. Check Connection Recovery settings.",
                "Latest QR generation is unavailable from this view."
            ),
            (
                "ko",
                "준비됨",
                "사용 불가",
                "연결 정보가 준비되지 않음",
                "저장된 연결 정보로 최신 페어링 QR을 생성합니다.",
                "QR 생성을 위한 연결 정보가 준비되지 않았습니다. 연결 복구 설정을 확인하세요.",
                "이 화면에서는 최신 QR을 생성할 수 없습니다."
            ),
            (
                "ja",
                "準備完了",
                "利用不可",
                "接続情報が未準備",
                "保存済みの接続情報で最新のペアリング QR を生成します。",
                "QR 生成用の接続情報は準備できていません。接続の復旧設定を確認してください。",
                "この画面では最新の QR を生成できません。"
            ),
            (
                "zh-Hans",
                "就绪",
                "不可用",
                "连接信息尚未就绪",
                "使用已保存的连接信息生成最新配对二维码。",
                "用于生成二维码的连接信息尚未就绪。请检查连接恢复设置。",
                "此视图无法生成最新二维码。"
            ),
            (
                "fr",
                "Prêt",
                "Indisponible",
                "Informations de connexion non prêtes",
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
                    expectation.routeNotReadyValue,
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

    func testConnectionRecoverySaveBootstrapRelayAccessibilityValueUsesSelectedLanguage() {
        let expectations: [(languageTag: String, ready: String, clearsSavedRelay: String)] = [
            (
                "en",
                "Ready",
                "Will remove saved bootstrap relay"
            ),
            (
                "ko",
                "준비됨",
                "저장된 부트스트랩 릴레이를 제거합니다"
            ),
            (
                "ja",
                "準備完了",
                "保存済みブートストラップリレーを削除します"
            ),
            (
                "zh-Hans",
                "就绪",
                "将移除已保存的引导中继"
            ),
            (
                "fr",
                "Prêt",
                "Supprimera le relais d’amorçage enregistré"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoverySaveBootstrapRelayActionAccessibilityValue(
                        endpoints: "relay.example.test:43171",
                        allocationToken: "token"
                    ),
                    expectation.ready,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoverySaveBootstrapRelayActionAccessibilityValue(endpoints: "   "),
                    expectation.clearsSavedRelay,
                    expectation.languageTag
                )
            }
        }
    }

    func testConnectionRecoveryBootstrapAllocationTokenWarningUsesSelectedLanguage() {
        let expectations: [(languageTag: String, warning: String, missingToken: String, ready: String)] = [
            (
                "en",
                "Add an allocation token before using a non-local bootstrap relay.",
                "Missing token for non-local bootstrap relay",
                "Ready"
            ),
            (
                "ko",
                "로컬이 아닌 부트스트랩 릴레이를 사용하기 전에 할당 토큰을 추가하세요.",
                "로컬이 아닌 부트스트랩 릴레이에 토큰이 없습니다",
                "준비됨"
            ),
            (
                "ja",
                "非ローカルのブートストラップリレーを使用する前に割り当てトークンを追加してください。",
                "非ローカルのブートストラップリレーのトークンがありません",
                "準備完了"
            ),
            (
                "zh-Hans",
                "使用非本地引导中继前，请添加分配令牌。",
                "非本地引导中继缺少令牌",
                "就绪"
            ),
            (
                "fr",
                "Ajoutez un jeton d’allocation avant d’utiliser un relais d’amorçage non local.",
                "Jeton manquant pour le relais d’amorçage non local",
                "Prêt"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    connectionRecoveryBootstrapAllocationTokenWarning(
                        endpoints: "relay.example.test:43171",
                        allocationToken: " "
                    ),
                    expectation.warning,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoveryBootstrapAllocationTokenAccessibilityValue(
                        endpoints: "relay.example.test:43171",
                        allocationToken: " "
                    ),
                    expectation.missingToken,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoverySaveBootstrapRelayActionAccessibilityValue(
                        endpoints: "relay.example.test:43171",
                        allocationToken: " "
                    ),
                    expectation.missingToken,
                    expectation.languageTag
                )
                XCTAssertNil(
                    connectionRecoveryBootstrapAllocationTokenWarning(
                        endpoints: "127.0.0.1:43171",
                        allocationToken: " "
                    ),
                    expectation.languageTag
                )
                XCTAssertNil(
                    connectionRecoveryBootstrapAllocationTokenWarning(
                        endpoints: "relay.example.test:43171",
                        allocationToken: "token"
                    ),
                    expectation.languageTag
                )
                XCTAssertEqual(
                    connectionRecoverySaveBootstrapRelayActionAccessibilityValue(
                        endpoints: "relay.example.test:43171",
                        allocationToken: "token"
                    ),
                    expectation.ready,
                    expectation.languageTag
                )
            }
        }
    }

    func testBootstrapRelayAllocationTokenWarningClassifiesNonLocalEndpoints() {
        let nonLocalEndpoints = [
            "relay.example.test:443",
            "https://relay.example.test:443/bootstrap",
            "10.8.0.5:443",
            "[2001:db8::42]:443",
        ]
        let localEndpoints = [
            "localhost:43171",
            "127.0.0.1:43171",
            "runtime.local:43171",
            "[::1]:43171",
            "169.254.1.10:43171",
            "[fe80::1]:43171",
        ]

        for endpoint in nonLocalEndpoints {
            XCTAssertTrue(bootstrapRelayEndpointsNeedAllocationToken(endpoint), endpoint)
        }
        for endpoint in localEndpoints {
            XCTAssertFalse(bootstrapRelayEndpointsNeedAllocationToken(endpoint), endpoint)
        }
    }

    func testConnectionRecoveryBootstrapRelayRemovalAccessibilityUsesSelectedLanguage() {
        let expectations: [(
            languageTag: String,
            actionTitle: String,
            dialogTitle: String,
            dialogMessage: String,
            removedMessage: String,
            actionHint: String,
            label: String,
            fallbackLabel: String,
            cancelLabel: String,
            fallbackCancelLabel: String
        )] = [
            (
                "en",
                "Remove Bootstrap Relay",
                "Remove saved bootstrap relay?",
                "Saved bootstrap relay settings will be removed. Devices on another network may need a fresh pairing QR before route preparation can run again.",
                "Saved bootstrap relay removed.",
                "Remove saved bootstrap relay settings used to prepare pairing QR connection details.",
                "Remove bootstrap relay settings for relay.example.test:43171",
                "Remove bootstrap relay settings for saved bootstrap relay",
                "Cancel removing bootstrap relay settings for relay.example.test:43171",
                "Cancel removing bootstrap relay settings for saved bootstrap relay"
            ),
            (
                "ko",
                "부트스트랩 릴레이 제거",
                "저장된 부트스트랩 릴레이를 제거할까요?",
                "저장된 부트스트랩 릴레이 설정이 제거됩니다. 다른 네트워크의 기기는 경로 준비를 다시 실행하기 전에 새 페어링 QR이 필요할 수 있습니다.",
                "저장된 부트스트랩 릴레이를 제거했습니다.",
                "페어링 QR 연결 정보를 준비하는 데 쓰는 저장된 부트스트랩 릴레이 설정을 제거합니다.",
                "relay.example.test:43171의 부트스트랩 릴레이 설정 제거",
                "저장된 부트스트랩 릴레이의 부트스트랩 릴레이 설정 제거",
                "relay.example.test:43171의 부트스트랩 릴레이 설정 제거 취소",
                "저장된 부트스트랩 릴레이의 부트스트랩 릴레이 설정 제거 취소"
            ),
            (
                "ja",
                "ブートストラップリレーを削除",
                "保存済みブートストラップリレーを削除しますか？",
                "保存済みブートストラップリレー設定は削除されます。別のネットワーク上のデバイスは、ルート準備を再実行する前に新しいペアリング QR が必要になる場合があります。",
                "保存済みブートストラップリレーを削除しました。",
                "ペアリング QR 接続情報の準備に使う保存済みブートストラップリレー設定を削除します。",
                "relay.example.test:43171 のブートストラップリレー設定を削除",
                "保存済みブートストラップリレー のブートストラップリレー設定を削除",
                "relay.example.test:43171 のブートストラップリレー設定の削除をキャンセル",
                "保存済みブートストラップリレー のブートストラップリレー設定の削除をキャンセル"
            ),
            (
                "zh-Hans",
                "移除引导中继",
                "要移除已保存的引导中继吗？",
                "已保存的引导中继设置将被移除。其他网络上的设备可能需要新的配对二维码，才能再次运行路由准备。",
                "已移除保存的引导中继。",
                "移除用于准备配对二维码连接信息的已保存引导中继设置。",
                "移除 relay.example.test:43171 的引导中继设置",
                "移除 已保存的引导中继 的引导中继设置",
                "取消移除 relay.example.test:43171 的引导中继设置",
                "取消移除 已保存的引导中继 的引导中继设置"
            ),
            (
                "fr",
                "Supprimer le relais d’amorçage",
                "Supprimer le relais d’amorçage enregistré ?",
                "Les réglages du relais d’amorçage enregistré seront supprimés. Les appareils sur un autre réseau peuvent avoir besoin d’un nouveau QR de jumelage avant de relancer la préparation de route.",
                "Relais d’amorçage enregistré supprimé.",
                "Supprime les réglages du relais d’amorçage enregistré utilisés pour préparer les informations de connexion du QR de jumelage.",
                "Supprimer les réglages du relais d’amorçage pour relay.example.test:43171",
                "Supprimer les réglages du relais d’amorçage pour relais d’amorçage enregistré",
                "Annuler la suppression des réglages du relais d’amorçage pour relay.example.test:43171",
                "Annuler la suppression des réglages du relais d’amorçage pour relais d’amorçage enregistré"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(NSLocalizedString("Remove Bootstrap Relay", comment: ""), expectation.actionTitle)
                XCTAssertEqual(NSLocalizedString("Remove saved bootstrap relay?", comment: ""), expectation.dialogTitle)
                XCTAssertEqual(
                    NSLocalizedString("Saved bootstrap relay settings will be removed. Devices on another network may need a fresh pairing QR before route preparation can run again.", comment: ""),
                    expectation.dialogMessage
                )
                XCTAssertEqual(NSLocalizedString("Saved bootstrap relay removed.", comment: ""), expectation.removedMessage)
                XCTAssertEqual(
                    removeSavedBootstrapRelayAccessibilityHint(),
                    expectation.actionHint
                )
                XCTAssertEqual(
                    removeSavedBootstrapRelayAccessibilityLabel(endpoints: " relay.example.test:43171 "),
                    expectation.label
                )
                XCTAssertEqual(
                    removeSavedBootstrapRelayAccessibilityLabel(endpoints: " "),
                    expectation.fallbackLabel
                )
                XCTAssertEqual(
                    cancelRemoveSavedBootstrapRelayAccessibilityLabel(endpoints: " relay.example.test:43171 "),
                    expectation.cancelLabel
                )
                XCTAssertEqual(
                    cancelRemoveSavedBootstrapRelayAccessibilityLabel(endpoints: " "),
                    expectation.fallbackCancelLabel
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

    func testRemoveSavedConnectionDetailsAccessibilityUsesSelectedLanguage() {
        let expectations: [(languageTag: String, actionTitle: String, actionHint: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Remove Saved Connection Details",
                "Remove saved fallback connection details used for future pairing QR routes.",
                "Remove saved connection details for relay.example.test:43171",
                "Remove saved connection details for saved connection"
            ),
            (
                "ko",
                "저장된 연결 정보 제거",
                "향후 페어링 QR 경로에 사용할 저장된 예비 연결 정보를 제거합니다.",
                "relay.example.test:43171의 저장된 연결 정보 제거",
                "저장된 연결의 저장된 연결 정보 제거"
            ),
            (
                "ja",
                "保存済み接続情報を削除",
                "今後のペアリング QR ルートに使う保存済みフォールバック接続情報を削除します。",
                "relay.example.test:43171 の保存済み接続情報を削除",
                "保存済みの接続 の保存済み接続情報を削除"
            ),
            (
                "zh-Hans",
                "移除已保存的连接信息",
                "移除用于后续配对二维码路径的已保存备用连接信息。",
                "移除 relay.example.test:43171 的已保存连接信息",
                "移除 已保存的连接 的已保存连接信息"
            ),
            (
                "fr",
                "Supprimer les informations de connexion enregistrées",
                "Supprime les informations de connexion de secours enregistrées utilisées pour les futurs itinéraires QR de jumelage.",
                "Supprimer les informations de connexion enregistrées pour relay.example.test:43171",
                "Supprimer les informations de connexion enregistrées pour connexion enregistrée"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    NSLocalizedString("Remove Saved Connection Details", comment: ""),
                    expectation.actionTitle
                )
                XCTAssertEqual(
                    removeSavedConnectionDetailsAccessibilityHint(),
                    expectation.actionHint
                )
                XCTAssertEqual(
                    removeSavedConnectionDetailsAccessibilityLabel(endpoint: " relay.example.test:43171 "),
                    expectation.label
                )
                XCTAssertEqual(
                    removeSavedConnectionDetailsAccessibilityLabel(endpoint: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testCancelRemoveSavedConnectionDetailsAccessibilityLabelUsesRouteContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Cancel removing saved connection details for relay.example.test:43171",
                "Cancel removing saved connection details for saved connection"
            ),
            (
                "ko",
                "relay.example.test:43171의 저장된 연결 정보 제거 취소",
                "저장된 연결의 저장된 연결 정보 제거 취소"
            ),
            (
                "ja",
                "relay.example.test:43171 の保存済み接続情報の削除をキャンセル",
                "保存済みの接続 の保存済み接続情報の削除をキャンセル"
            ),
            (
                "zh-Hans",
                "取消移除 relay.example.test:43171 的已保存连接信息",
                "取消移除 已保存的连接 的已保存连接信息"
            ),
            (
                "fr",
                "Annuler la suppression des informations de connexion enregistrées pour relay.example.test:43171",
                "Annuler la suppression des informations de connexion enregistrées pour connexion enregistrée"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    cancelRemoveSavedConnectionDetailsAccessibilityLabel(endpoint: " relay.example.test:43171 "),
                    expectation.label
                )
                XCTAssertEqual(
                    cancelRemoveSavedConnectionDetailsAccessibilityLabel(endpoint: " "),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testProviderStatusTechnicalDetailsRedactEndpointsButKeepSafeFields() {
        withStoredAppLanguage("en") {
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
    }

    func testProviderStatusTechnicalDetailsRedactUnsafeCodes() {
        withStoredAppLanguage("en") {
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

    func testProviderStatusRowAccessibilityLabelUsesProviderContext() {
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Provider Ollama. Status Available. Model provider is responding.",
                "Provider Model provider. Status Not checked. No provider details"
            ),
            (
                "ko",
                "Ollama. 상태 사용 가능. 모델 제공자가 응답 중입니다.",
                "모델 제공자. 상태 확인 전. 제공자 세부 정보 없음"
            ),
            (
                "ja",
                "Ollama。状態 利用可能。モデルプロバイダーが応答しています。",
                "モデルプロバイダー。状態 未確認。プロバイダー詳細なし"
            ),
            (
                "zh-Hans",
                "Ollama。状态 可用。模型提供方正在响应。",
                "模型提供方。状态 未检查。没有提供方详情"
            ),
            (
                "fr",
                "Fournisseur Ollama. État Disponible. Le fournisseur de modèles répond.",
                "Fournisseur Fournisseur de modèles. État Non vérifié. Aucun détail sur le fournisseur"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    providerStatusRowAccessibilityLabel(
                        providerName: " Ollama ",
                        status: NSLocalizedString("Available", comment: ""),
                        detail: NSLocalizedString("Model provider is responding.", comment: "")
                    ),
                    expectation.label
                )
                XCTAssertEqual(
                    providerStatusRowAccessibilityLabel(providerName: " ", status: " ", detail: " "),
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

    func testTrustedDeviceCancelRemoveActionAccessibilityLabelUsesDeviceContext() {
        let device = TrustedDevice(
            id: "device-1",
            name: "Pixel",
            publicKeyBase64: "aGVsbG8=",
            pairedAt: Date(timeIntervalSince1970: 0)
        )
        let expectations: [(languageTag: String, label: String, fallbackLabel: String)] = [
            (
                "en",
                "Cancel removing trust for Pixel. Key fingerprint 2C:F2:4D:BA:5F:B0",
                "Cancel removing trust for Selected device. Key fingerprint Unavailable"
            ),
            (
                "ko",
                "Pixel 신뢰 해제 취소. 키 지문 2C:F2:4D:BA:5F:B0",
                "선택한 항목 신뢰 해제 취소. 키 지문 사용 불가"
            ),
            (
                "ja",
                "Pixel の信頼解除をキャンセル。キー指紋 2C:F2:4D:BA:5F:B0",
                "選択したデバイス の信頼解除をキャンセル。キー指紋 利用不可"
            ),
            (
                "zh-Hans",
                "取消移除 Pixel 的信任。密钥指纹 2C:F2:4D:BA:5F:B0",
                "取消移除 所选设备 的信任。密钥指纹 不可用"
            ),
            (
                "fr",
                "Annuler le retrait de l’approbation de Pixel. Empreinte de clé 2C:F2:4D:BA:5F:B0",
                "Annuler le retrait de l’approbation de Appareil sélectionné. Empreinte de clé Indisponible"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    trustedDeviceCancelRemoveAccessibilityLabel(for: device),
                    expectation.label
                )
                XCTAssertEqual(
                    trustedDeviceCancelRemoveAccessibilityLabel(for: nil),
                    expectation.fallbackLabel
                )
            }
        }
    }

    func testTrustedDeviceRowAccessibilityLabelUsesDeviceContext() {
        let date = Date(timeIntervalSince1970: 0)
        let expectations: [(languageTag: String, fallbackDisplayName: String, fallbackPairingSummary: String, fallbackLabel: String)] = [
            (
                "en",
                "Selected device",
                "Device ID ending ice-1",
                "Trusted device Selected device. Pairing details unavailable. Key fingerprint Unavailable"
            ),
            (
                "ko",
                "선택한 항목",
                "기기 ID 끝자리 ice-1",
                "신뢰 기기 선택한 항목. 페어링 세부 정보를 사용할 수 없습니다. 키 지문 사용 불가"
            ),
            (
                "ja",
                "選択したデバイス",
                "デバイス ID 末尾 ice-1",
                "信頼済みデバイス 選択したデバイス。ペアリングの詳細は利用できません。キー指紋 利用不可"
            ),
            (
                "zh-Hans",
                "所选设备",
                "设备 ID 结尾 ice-1",
                "受信任设备 所选设备。配对详情不可用。密钥指纹 不可用"
            ),
            (
                "fr",
                "Appareil sélectionné",
                "ID de l’appareil finissant par ice-1",
                "Appareil approuvé Appareil sélectionné. Détails de jumelage indisponibles. Empreinte de clé Indisponible"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(trustedDeviceDisplayName(" Pixel "), "Pixel", expectation.languageTag)
                XCTAssertEqual(trustedDeviceDisplayName("   "), expectation.fallbackDisplayName, expectation.languageTag)
                XCTAssertEqual(trustedDeviceDisplayName(nil), expectation.fallbackDisplayName, expectation.languageTag)
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
                    trustedDevicePairingAccessibilitySummary(pairedAt: nil, deviceID: " ice-1 "),
                    expectation.fallbackPairingSummary,
                    expectation.languageTag
                )
                XCTAssertEqual(
                    trustedDeviceRowAccessibilityLabel(
                        name: " Pixel ",
                        pairedAt: nil,
                        deviceID: " ice-1 ",
                        keyFingerprint: " 2C:F2:4D:BA:5F:B0 "
                    ),
                    String(
                        format: NSLocalizedString("Trusted device %@. %@. Key fingerprint %@", comment: ""),
                        "Pixel",
                        expectation.fallbackPairingSummary,
                        "2C:F2:4D:BA:5F:B0"
                    ),
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

    func testTrustedDeviceRemoveButtonAccessibilityHintUsesSelectedLanguage() {
        let expectations: [(languageTag: String, hint: String, fallbackHint: String)] = [
            (
                "en",
                "After removal, Pixel must pair again before it can use AetherLink Runtime.",
                "After removal, Selected device must pair again before it can use AetherLink Runtime."
            ),
            (
                "ko",
                "제거 후 Pixel은(는) AetherLink Runtime을 사용하려면 다시 페어링해야 합니다.",
                "제거 후 선택한 항목은(는) AetherLink Runtime을 사용하려면 다시 페어링해야 합니다."
            ),
            (
                "ja",
                "削除後、Pixel は AetherLink Runtime を使用する前に再度ペアリングが必要です。",
                "削除後、選択したデバイス は AetherLink Runtime を使用する前に再度ペアリングが必要です。"
            ),
            (
                "zh-Hans",
                "移除后，Pixel 必须重新配对才能使用 AetherLink Runtime。",
                "移除后，所选设备 必须重新配对才能使用 AetherLink Runtime。"
            ),
            (
                "fr",
                "Après le retrait, Pixel doit être jumelé à nouveau avant de pouvoir utiliser AetherLink Runtime.",
                "Après le retrait, Appareil sélectionné doit être jumelé à nouveau avant de pouvoir utiliser AetherLink Runtime."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    trustedDeviceRemoveAccessibilityHint(name: " Pixel "),
                    expectation.hint
                )
                XCTAssertEqual(
                    trustedDeviceRemoveAccessibilityHint(name: " "),
                    expectation.fallbackHint
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

    func testTrustedDeviceListAccessibilityUsesSelectedLanguage() {
        let expectations: [(languageTag: String, label: String, value: String)] = [
            (
                "en",
                "Allowed Devices",
                "2 trusted devices"
            ),
            (
                "ko",
                "허용된 기기",
                "신뢰 기기 2대"
            ),
            (
                "ja",
                "許可済みデバイス",
                "信頼済みデバイス 2 台"
            ),
            (
                "zh-Hans",
                "允许的设备",
                "2 台受信任设备"
            ),
            (
                "fr",
                "Appareils autorisés",
                "2 appareils approuvés"
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(trustedDeviceListAccessibilityLabel(), expectation.label)
                XCTAssertEqual(trustedDeviceListAccessibilityValue(count: 2), expectation.value)
                XCTAssertEqual(trustedDeviceListAccessibilityValue(count: -1), localizedTrustedDeviceCount(0))
            }
        }
    }

    func testTrustedDevicesEmptyStateCopyUsesRuntimeRequestsAcrossSupportedLanguages() {
        let expectations: [(languageTag: String, value: String)] = [
            (
                "en",
                "Pair a device before allowing runtime requests."
            ),
            (
                "ko",
                "런타임 요청을 허용하기 전에 기기를 페어링하세요."
            ),
            (
                "ja",
                "ランタイムリクエストを許可する前に、デバイスをペアリングしてください。"
            ),
            (
                "zh-Hans",
                "允许运行时请求前，请先配对设备。"
            ),
            (
                "fr",
                "Jumelez un appareil avant d’autoriser les requêtes du runtime."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    NSLocalizedString("Pair a device before allowing runtime requests.", comment: ""),
                    expectation.value
                )
            }
        }
    }

    func testTrustedDevicesHeaderSubtitleUsesProductNeutralCopyAcrossSupportedLanguages() {
        let expectations: [(languageTag: String, value: String)] = [
            (
                "en",
                "Manage devices trusted to use AetherLink Runtime. Remove trust when a device should pair again."
            ),
            (
                "ko",
                "AetherLink Runtime 사용을 신뢰한 기기를 관리하세요. 기기가 다시 페어링해야 할 때 신뢰를 해제하세요."
            ),
            (
                "ja",
                "AetherLink Runtime の使用を信頼したデバイスを管理します。デバイスを再度ペアリングさせる必要がある場合は、信頼を解除してください。"
            ),
            (
                "zh-Hans",
                "管理已信任可使用 AetherLink Runtime 的设备。当设备需要重新配对时，请移除信任。"
            ),
            (
                "fr",
                "Gérez les appareils approuvés pour utiliser AetherLink Runtime. Retirez l’approbation lorsqu’un appareil doit être jumelé à nouveau."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    NSLocalizedString("Manage devices trusted to use AetherLink Runtime. Remove trust when a device should pair again.", comment: ""),
                    expectation.value
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

    func testRemoteRelayConnectionFailureRecoveryCopyRequiresFreshQR() {
        let expectations: [(languageTag: String, copy: String)] = [
            (
                "en",
                "Connection through relay.example.test:43171 failed. Check Connection Recovery, then generate a fresh QR."
            ),
            (
                "ko",
                "relay.example.test:43171을(를) 통한 연결에 실패했습니다. 연결 복구를 확인한 뒤 새 QR을 생성하세요."
            ),
            (
                "ja",
                "relay.example.test:43171 経由の接続に失敗しました。接続の復旧を確認してから、新しい QR を生成してください。"
            ),
            (
                "zh-Hans",
                "通过 relay.example.test:43171 的连接失败。请检查连接恢复，然后生成新的二维码。"
            ),
            (
                "fr",
                "La connexion via relay.example.test:43171 a échoué. Vérifiez la récupération de connexion, puis générez un nouveau QR."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))

        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(
                    remoteRelayConnectionFailureRecoveryText(endpoint: "relay.example.test:43171"),
                    expectation.copy,
                    expectation.languageTag
                )
                XCTAssertFalse(remoteRelayConnectionFailureRecoveryText(endpoint: "relay.example.test:43171").contains("try again"))
            }
        }

        withStoredAppLanguage("en") {
            XCTAssertEqual(
                remoteRelayConnectionFailureRecoveryText(endpoint: "relay_secret=secret route_token=token"),
                "Connection failed. Check Connection Recovery, then generate a fresh QR."
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

            let loopbackSettings = CompanionDevelopmentRelaySettings(
                isEnabled: true,
                host: "127.0.0.1",
                port: 43171,
                relayID: "relay-1",
                relaySecret: "secret-1"
            )
            let loopbackDetail = remoteRouteScopeDetail(
                settings: loopbackSettings,
                bootstrapSettings: .disabled,
                canPrepareAutomatically: false
            )
            XCTAssertEqual(
                loopbackDetail,
                "Loopback routes only work on this device or USB diagnostics, not from another network."
            )
            XCTAssertFalse(loopbackDetail.contains("runtime host"))

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

    private func localizedConnectionRecoveryResultTestMessage(_ key: String, _ languageTag: String) -> String {
        let messages: [String: [String: String]] = [
            "en": [
                "Connection details prepared.": "Connection details prepared.",
                "Check Connection Recovery.": "Check Connection Recovery.",
            ],
            "ko": [
                "Connection details prepared.": "연결 세부 정보가 준비되었습니다.",
                "Check Connection Recovery.": "연결 복구를 확인하세요.",
            ],
            "ja": [
                "Connection details prepared.": "接続詳細を準備しました。",
                "Check Connection Recovery.": "接続の復旧を確認してください。",
            ],
            "zh-Hans": [
                "Connection details prepared.": "连接详情已准备好。",
                "Check Connection Recovery.": "检查连接恢复。",
            ],
            "fr": [
                "Connection details prepared.": "Détails de connexion préparés.",
                "Check Connection Recovery.": "Vérifiez la récupération de connexion.",
            ],
        ]
        return messages[languageTag]?[key] ?? key
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
