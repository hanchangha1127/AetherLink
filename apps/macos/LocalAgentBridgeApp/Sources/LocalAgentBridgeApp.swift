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
                .help(modelProviderCheckActionAccessibilityHint())
                .accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))
                .accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))
            }
        }

        MenuBarExtra(NSLocalizedString("AetherLink", comment: ""), systemImage: "bolt.horizontal.circle") {
            let commandTitles = menuBarCommandTitles()

            Text(menuBarRuntimeStatusText(model.transportState))
                .accessibilityLabel(Text(menuBarRuntimeStatusAccessibilityLabel(model.transportState)))
            Text(menuBarModelServiceStatusText(model.providerStatuses))
                .accessibilityLabel(Text(menuBarModelServiceStatusAccessibilityLabel(model.providerStatuses)))
            Divider()
            Button(commandTitles.openAetherLink) {
                openWindow(id: "main")
                NSApp.activate(ignoringOtherApps: true)
            }
            .help(menuBarOpenAetherLinkAccessibilityHint())
            .accessibilityHint(Text(menuBarOpenAetherLinkAccessibilityHint()))
            ForEach(companionPrimaryActionOrder(trustedDeviceCount: model.trustedDevices.count)) { action in
                menuBarPrimaryAction(action, commandTitles: commandTitles)
            }
            Divider()
            Button(commandTitles.quit) {
                NSApp.terminate(nil)
            }
            .help(menuBarQuitAccessibilityHint())
            .accessibilityHint(Text(menuBarQuitAccessibilityHint()))
        }
    }

    private var currentAppLanguage: AetherLinkAppLanguage {
        AetherLinkAppLanguage.normalized(appLanguageTag)
    }

    private var currentAppAppearance: AetherLinkAppAppearance {
        AetherLinkAppAppearance.normalized(appAppearance)
    }

    private var canGeneratePairingQR: Bool {
        pairingQRGenerationCommandAvailable(
            canPrepareAutomatically: model.canPrepareRemoteRelayRouteAutomatically,
            isRouteEligibleForQRCode: model.isDevelopmentRelayRouteEligibleForQRCode
        )
    }

    @ViewBuilder
    private func menuBarPrimaryAction(
        _ action: CompanionPrimaryAction,
        commandTitles: MenuBarCommandTitles
    ) -> some View {
        switch action {
        case .refreshProviders:
            Button(commandTitles.refresh) {
                Task { await model.refreshBackendStatus() }
            }
            .help(modelProviderCheckActionAccessibilityHint())
            .accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))
            .accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))

        case .loadModels:
            Button(commandTitles.loadModels) {
                Task { await model.loadModels() }
            }
            .help(modelListLoadActionAccessibilityHint())
            .accessibilityValue(Text(modelListLoadActionAccessibilityValue()))
            .accessibilityHint(Text(modelListLoadActionAccessibilityHint()))

        case .pairingQR:
            Button(pairingQRGenerationCommandTitle(hasActiveSession: model.pairingSession != nil)) {
                model.beginPairing()
                requestedSection = .pairing
                openWindow(id: "main")
                NSApp.activate(ignoringOtherApps: true)
            }
            .disabled(!canGeneratePairingQR)
            .help(pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR))
            .accessibilityValue(Text(pairingQRGenerationActionAccessibilityValue(isAvailable: canGeneratePairingQR)))
            .accessibilityHint(Text(pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR)))
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}
