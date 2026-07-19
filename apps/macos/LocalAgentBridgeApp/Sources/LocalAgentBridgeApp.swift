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
                    model.requestStartForUserInterface()
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
            Button(commandTitles.refreshModelResidency) {
                model.refreshModelResidencyStatus()
            }
            .help(refreshModelResidencyActionAccessibilityHint())
            .accessibilityValue(Text(refreshModelResidencyActionAccessibilityValue()))
            .accessibilityHint(Text(refreshModelResidencyActionAccessibilityHint()))
            Button(commandTitles.unloadResidentModel) {
                Task { await model.unloadResidentModelNow() }
            }
            .disabled(!canUnloadResidentModel)
            .help(unloadResidentModelActionAccessibilityHint(
                canUnload: canUnloadResidentModel,
                inFlightGenerations: model.modelResidency.inFlightGenerations,
                isUnloading: model.modelResidency.unloadingModelID != nil
            ))
            .accessibilityValue(Text(unloadResidentModelActionAccessibilityValue(
                canUnload: canUnloadResidentModel,
                inFlightGenerations: model.modelResidency.inFlightGenerations,
                isUnloading: model.modelResidency.unloadingModelID != nil
            )))
            .accessibilityHint(Text(unloadResidentModelActionAccessibilityHint(
                canUnload: canUnloadResidentModel,
                inFlightGenerations: model.modelResidency.inFlightGenerations,
                isUnloading: model.modelResidency.unloadingModelID != nil
            )))
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
            canRequestRemotePairing: model.canRequestRemotePairingForUserInterface
        )
    }

    private var canUnloadResidentModel: Bool {
        model.modelResidency.supported &&
            model.modelResidency.activeModelID != nil &&
            model.modelResidency.unloadingModelID == nil &&
            model.modelResidency.inFlightGenerations == 0
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
                model.requestRemotePairingForUserInterface()
                requestedSection = .pairing
                openWindow(id: "main")
                NSApp.activate(ignoringOtherApps: true)
            }
            .disabled(!canGeneratePairingQR)
            .help(
                pairingQRGenerationActionAccessibilityHint(
                    isAvailable: canGeneratePairingQR,
                    isPreparing: model.isRemoteRoutePreparationInFlight
                )
            )
            .accessibilityValue(
                Text(
                    pairingQRGenerationActionAccessibilityValue(
                        isAvailable: canGeneratePairingQR,
                        isPreparing: model.isRemoteRoutePreparationInFlight
                    )
                )
            )
            .accessibilityHint(
                Text(
                    pairingQRGenerationActionAccessibilityHint(
                        isAvailable: canGeneratePairingQR,
                        isPreparing: model.isRemoteRoutePreparationInFlight
                    )
                )
            )
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}
