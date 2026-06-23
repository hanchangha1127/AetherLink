import AppKit
import CompanionCore
import SwiftUI

@main
struct LocalAgentBridgeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
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
                Button("Refresh Ollama Status") {
                    Task { await model.refreshOllamaStatus() }
                }
                .keyboardShortcut("r", modifiers: [.command])
            }
        }

        MenuBarExtra("AetherLink", systemImage: "bolt.horizontal.circle") {
            Text(localizedStatus(model.backendStatus))
            Button("Open AetherLink") {
                NSApp.activate(ignoringOtherApps: true)
            }
            Button("Refresh Ollama") {
                Task { await model.refreshOllamaStatus() }
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
