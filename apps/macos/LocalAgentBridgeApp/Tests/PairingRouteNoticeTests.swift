import XCTest
@testable import LocalAgentBridge

final class PairingRouteNoticeTests: XCTestCase {
    func testRepresentativePairingRouteStatesUseExactNoticeText() {
        withStoredAppLanguage("en") {
            XCTAssertEqual(
                makePairingRouteNotice(for: .preparing).text,
                "Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready."
            )
            XCTAssertEqual(
                makePairingRouteNotice(
                    for: .configuredRoute(
                        endpoint: "relay.example.test:43171",
                        isEligibleForQRCode: false,
                        isPreparedForQRCode: false,
                        isQRCodeReady: false,
                        frameEncryptionEnabled: true
                    )
                ).text,
                "Connection details for relay.example.test:43171 cannot be included in this QR. Connection Recovery needs an address both devices can reach."
            )
            XCTAssertEqual(
                makePairingRouteNotice(
                    for: .configuredRoute(
                        endpoint: "relay.example.test:43171",
                        isEligibleForQRCode: true,
                        isPreparedForQRCode: true,
                        isQRCodeReady: true,
                        frameEncryptionEnabled: true
                    )
                ).text,
                "This QR includes connection details for relay.example.test:43171. Pairing or refresh still requires the scanning device to reach that route."
            )
            XCTAssertEqual(
                makePairingRouteNotice(
                    for: .configuredRoute(
                        endpoint: "relay.example.test:43171",
                        isEligibleForQRCode: true,
                        isPreparedForQRCode: true,
                        isQRCodeReady: true,
                        frameEncryptionEnabled: false
                    )
                ).text,
                "This QR includes connection details for relay.example.test:43171, but the secure connection secret is missing."
            )
            XCTAssertEqual(
                makePairingRouteNotice(for: .issue("Connection preparation failed.")).text,
                "Connection preparation failed."
            )
            XCTAssertEqual(
                makePairingRouteNotice(for: .localDiagnostic("Same-Wi-Fi diagnostic route.")).text,
                "Same-Wi-Fi diagnostic route."
            )
        }
    }

    func testRepresentativeStatesRemainLocalizedAcrossSupportedLanguages() {
        for language in AetherLinkAppLanguage.allCases {
            withStoredAppLanguage(language.rawValue) {
                let preparing = makePairingRouteNotice(for: .preparing).text
                let ready = makePairingRouteNotice(
                    for: .configuredRoute(
                        endpoint: "relay.example.test:43171",
                        isEligibleForQRCode: true,
                        isPreparedForQRCode: true,
                        isQRCodeReady: true,
                        frameEncryptionEnabled: true
                    )
                ).text

                XCTAssertFalse(preparing.isEmpty, language.rawValue)
                XCTAssertFalse(ready.isEmpty, language.rawValue)
                XCTAssertTrue(ready.contains("relay.example.test:43171"), language.rawValue)
            }
        }
    }

    private func withStoredAppLanguage(_ languageTag: String, assertions: () -> Void) {
        let previous = UserDefaults.standard.string(forKey: AetherLinkAppLanguageStorageKey)
        UserDefaults.standard.set(languageTag, forKey: AetherLinkAppLanguageStorageKey)
        defer {
            if let previous {
                UserDefaults.standard.set(previous, forKey: AetherLinkAppLanguageStorageKey)
            } else {
                UserDefaults.standard.removeObject(forKey: AetherLinkAppLanguageStorageKey)
            }
        }
        assertions()
    }
}
