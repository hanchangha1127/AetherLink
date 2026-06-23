import AppKit
import CompanionCore
import SwiftUI

@main
struct LocalAgentBridgeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.openWindow) private var openWindow
    @StateObject private var model = CompanionAppModel()

    var body: some Scene {
        WindowGroup("AetherLink", id: "main") {
            ContentView(model: model)
                .frame(minWidth: 860, minHeight: 560)
                .task {
                    model.start()
                }
        }
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Refresh Backend Status") {
                    Task { await model.refreshBackendStatus() }
                }
                .keyboardShortcut("r", modifiers: [.command])
            }
        }

        MenuBarExtra("AetherLink", systemImage: "bolt.horizontal.circle") {
            Text(
                String(
                    format: NSLocalizedString("Companion: %@", comment: ""),
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
            Button("Open AetherLink") {
                openWindow(id: "main")
                NSApp.activate(ignoringOtherApps: true)
            }
            Button("Refresh") {
                Task { await model.refreshBackendStatus() }
            }
            Button("Load Models") {
                Task { await model.loadModels() }
            }
            Button("Start Pairing") {
                model.beginPairing()
            }
            Divider()
            Button("Quit") {
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
