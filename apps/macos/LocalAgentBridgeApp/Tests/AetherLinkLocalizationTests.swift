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

    func testPairingQRGenerationRequiresAutomaticPreparationOrEligibleRoute() {
        XCTAssertTrue(
            pairingQRGenerationAvailable(
                canPrepareAutomatically: true,
                isRouteEligibleForQRCode: false
            )
        )
        XCTAssertTrue(
            pairingQRGenerationAvailable(
                canPrepareAutomatically: false,
                isRouteEligibleForQRCode: true
            )
        )
        XCTAssertFalse(
            pairingQRGenerationAvailable(
                canPrepareAutomatically: false,
                isRouteEligibleForQRCode: false
            )
        )
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

    func testTrustedDeviceKeyFingerprintUsesPublicKeyHashOnly() {
        XCTAssertEqual(trustedDeviceKeyFingerprint(" aGVsbG8= "), "2C:F2:4D:BA:5F:B0")
    }

    func testTrustedDeviceRemovalMessageIncludesKeyFingerprint() {
        withStoredAppLanguage("en") {
            let device = TrustedDevice(
                id: "device-1",
                name: "Pixel",
                publicKeyBase64: "aGVsbG8=",
                pairedAt: Date(timeIntervalSince1970: 0)
            )

            XCTAssertEqual(
                trustedDeviceRemovalMessage(for: device),
                "Pixel will need to pair again before it can use AetherLink Runtime. Key fingerprint 2C:F2:4D:BA:5F:B0"
            )
        }
    }

    func testTrustedDeviceRemovalMessageUsesFallbackName() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                trustedDeviceRemovalMessage(for: nil),
                "Selected device will need to pair again before it can use AetherLink Runtime. Key fingerprint Unavailable"
            )
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
