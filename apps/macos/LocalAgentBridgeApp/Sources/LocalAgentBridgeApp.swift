import AppKit
import CompanionCore
import SwiftUI

@main
struct LocalAgentBridgeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.openWindow) private var openWindow
    @StateObject private var model = CompanionAppModel()

    var body: some Scene {
        WindowGroup(NSLocalizedString("AetherLink", comment: ""), id: "main") {
            ContentView(model: model)
                .frame(minWidth: 860, minHeight: 560)
                .task {
                    model.start()
                }
        }
        .commands {
            CommandGroup(after: .appInfo) {
                Button(NSLocalizedString("Refresh Backend Status", comment: "")) {
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
                    format: NSLocalizedString("Backend: %@", comment: ""),
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
            Button(NSLocalizedString("Start Pairing", comment: "")) {
                model.beginPairing()
            }
            Divider()
            Button(NSLocalizedString("Quit", comment: "")) {
                NSApp.terminate(nil)
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}
