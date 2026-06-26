import AppKit
import CompanionCore
import SwiftUI

@main
struct LocalAgentBridgeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.openWindow) private var openWindow
    @AppStorage(AetherLinkAppLanguageStorageKey) private var appLanguageTag = AetherLinkAppLanguage.defaultLanguage.rawValue
    @AppStorage(AetherLinkAppAppearanceStorageKey) private var appAppearance = AetherLinkAppAppearance.defaultAppearance.rawValue
    @StateObject private var model = CompanionAppModel()
    @State private var requestedSection: CompanionSection?

    var body: some Scene {
        WindowGroup(NSLocalizedString("AetherLink", comment: ""), id: "main") {
            ContentView(model: model, requestedSection: $requestedSection)
                .environment(\.locale, Locale(identifier: currentAppLanguage.localeIdentifier))
                .id(currentAppLanguage.rawValue)
                .preferredColorScheme(currentAppAppearance.preferredColorScheme)
                .frame(minWidth: 860, minHeight: 560)
                .task {
                    model.start()
                }
        }
        .commands {
            CommandGroup(after: .appInfo) {
                Button(NSLocalizedString("Check Model Providers", comment: "")) {
                    Task { await model.refreshBackendStatus() }
                }
                .keyboardShortcut("r", modifiers: [.command])
            }
        }

        MenuBarExtra(NSLocalizedString("AetherLink", comment: ""), systemImage: "bolt.horizontal.circle") {
            Text(
                String(
                    format: NSLocalizedString("Runtime: %@", comment: ""),
                    localizedTransportStatus(model.transportState)
                )
            )
            Text(
                String(
                    format: NSLocalizedString("Model service: %@", comment: ""),
                    localizedBackendStatus(model.providerStatuses)
                )
            )
            Divider()
            Button(NSLocalizedString("Open AetherLink", comment: "")) {
                openWindow(id: "main")
                NSApp.activate(ignoringOtherApps: true)
            }
            Button(NSLocalizedString("Refresh", comment: "")) {
                Task { await model.refreshBackendStatus() }
            }
            Button(NSLocalizedString("Load Models", comment: "")) {
                Task { await model.loadModels() }
            }
            Button(NSLocalizedString("Generate Pairing QR", comment: "")) {
                model.beginPairing()
                requestedSection = .pairing
                openWindow(id: "main")
                NSApp.activate(ignoringOtherApps: true)
            }
            Divider()
            Button(NSLocalizedString("Quit", comment: "")) {
                NSApp.terminate(nil)
            }
        }
    }

    private var currentAppLanguage: AetherLinkAppLanguage {
        AetherLinkAppLanguage.normalized(appLanguageTag)
    }

    private var currentAppAppearance: AetherLinkAppAppearance {
        AetherLinkAppAppearance.normalized(appAppearance)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}
