import AppKit
import CompanionCore
import SwiftUI
import XCTest
@testable import LocalAgentBridge

@MainActor
final class AetherLinkRenderSmokeTests: XCTestCase {
    private let minimumWindowSize = CGSize(width: 860, height: 560)
    private let minimumDetailSize = CGSize(width: 680, height: 560)

    func testCompanionShellRendersAtMinimumWindowAcrossLanguagesAndAppearances() throws {
        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let bitmap = try render(
                        ContentView(
                            model: renderSmokeModel(),
                            requestedSection: .constant(.pairing)
                        )
                        .environment(\.locale, Locale(identifier: language.localeIdentifier))
                        .preferredColorScheme(appearance.preferredColorScheme),
                        size: minimumWindowSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "ContentView \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testPrimaryCompanionSurfacesRenderAtMinimumDetailSizeAcrossLanguagesAndAppearances() throws {
        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let model = renderSmokeModel()
                    let surfaces: [(String, AnyView)] = [
                        ("StatusView", AnyView(StatusView(model: model))),
                        ("PairingView", AnyView(PairingView(model: model))),
                        ("RemoteRelayRoutePanel", AnyView(RemoteRelayRoutePanel(model: model))),
                        ("TrustedDevicesView", AnyView(TrustedDevicesView(model: model))),
                        ("LogsView", AnyView(LogsView(model: model))),
                    ]

                    for (name, surface) in surfaces {
                        let bitmap = try render(
                            surface
                                .environment(\.locale, Locale(identifier: language.localeIdentifier))
                                .preferredColorScheme(appearance.preferredColorScheme),
                            size: minimumDetailSize
                        )

                        assertMeaningfulRender(
                            bitmap,
                            label: "\(name) \(language.rawValue) \(appearance.rawValue)"
                        )
                    }
                }
            }
        }
    }

    private func render<Content: View>(_ view: Content, size: CGSize) throws -> NSBitmapImageRep {
        let hostingView = NSHostingView(rootView: view.frame(width: size.width, height: size.height))
        hostingView.frame = NSRect(origin: .zero, size: size)

        let window = NSWindow(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        window.contentView = hostingView
        window.layoutIfNeeded()
        hostingView.layoutSubtreeIfNeeded()
        hostingView.displayIfNeeded()
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))

        guard let bitmap = hostingView.bitmapImageRepForCachingDisplay(in: hostingView.bounds) else {
            throw RenderSmokeFailure.bitmapAllocationFailed
        }
        hostingView.cacheDisplay(in: hostingView.bounds, to: bitmap)
        window.contentView = nil
        return bitmap
    }

    private func assertMeaningfulRender(
        _ bitmap: NSBitmapImageRep,
        label: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertGreaterThan(bitmap.pixelsWide, 0, "\(label) width", file: file, line: line)
        XCTAssertGreaterThan(bitmap.pixelsHigh, 0, "\(label) height", file: file, line: line)

        let stepX = max(bitmap.pixelsWide / 18, 1)
        let stepY = max(bitmap.pixelsHigh / 14, 1)
        var colors = Set<String>()
        var opaqueSamples = 0

        for y in stride(from: 0, to: bitmap.pixelsHigh, by: stepY) {
            for x in stride(from: 0, to: bitmap.pixelsWide, by: stepX) {
                guard let color = bitmap.colorAt(x: x, y: y)?
                    .usingColorSpace(.deviceRGB)
                else {
                    continue
                }
                if color.alphaComponent > 0.2 {
                    opaqueSamples += 1
                }
                colors.insert(
                    [
                        color.redComponent,
                        color.greenComponent,
                        color.blueComponent,
                        color.alphaComponent,
                    ]
                    .map { Int(($0 * 255).rounded()).clamped(to: 0...255) }
                    .map { String(format: "%02X", $0) }
                    .joined()
                )
            }
        }

        XCTAssertGreaterThan(opaqueSamples, 20, "\(label) opaque samples", file: file, line: line)
        XCTAssertGreaterThanOrEqual(colors.count, 4, "\(label) sampled colors", file: file, line: line)
    }

    private func withStoredPreferences<T>(
        language: AetherLinkAppLanguage,
        appearance: AetherLinkAppAppearance,
        assertions: () throws -> T
    ) throws -> T {
        let previousLanguage = UserDefaults.standard.string(forKey: AetherLinkAppLanguageStorageKey)
        let previousAppearance = UserDefaults.standard.string(forKey: AetherLinkAppAppearanceStorageKey)
        UserDefaults.standard.set(language.rawValue, forKey: AetherLinkAppLanguageStorageKey)
        UserDefaults.standard.set(appearance.rawValue, forKey: AetherLinkAppAppearanceStorageKey)
        defer {
            restore(previousLanguage, forKey: AetherLinkAppLanguageStorageKey)
            restore(previousAppearance, forKey: AetherLinkAppAppearanceStorageKey)
        }
        return try assertions()
    }

    private func restore(_ value: String?, forKey key: String) {
        if let value {
            UserDefaults.standard.set(value, forKey: key)
        } else {
            UserDefaults.standard.removeObject(forKey: key)
        }
    }

    private func isolatedDefaults() -> UserDefaults {
        let suiteName = "dev.aetherlink.render-smoke.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }

    private func renderSmokeModel() -> CompanionAppModel {
        CompanionAppModel(
            environment: [:],
            userDefaults: isolatedDefaults(),
            runtimeRouteHostProvider: { "127.0.0.1" }
        )
    }
}

private enum RenderSmokeFailure: Error {
    case bitmapAllocationFailed
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}
