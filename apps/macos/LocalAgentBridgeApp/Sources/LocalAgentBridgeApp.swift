import AppKit
import CompanionCore
import SwiftUI

@main
struct LocalAgentBridgeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @Environment(\.openWindow) private var openWindow
    @AppStorage(AetherLinkAppLanguageStorageKey) private var appLanguageTag = AetherLinkAppLanguage.defaultLanguage.rawValue
    @AppStorage(AetherLinkAppAppearanceStorageKey) private var appAppearance = AetherLinkAppAppearance.defaultAppearance.rawValue
    @StateObject private var model: CompanionAppModel
    @State private var requestedSection: CompanionSection?
    @State private var pairingFocusSequence = 0
    @State private var pairingFocusIntent: PairingFocusIntent?

    init() {
        let initializedModel = CompanionAppModel()
        if let stateRecoveryProbe = PackagedStateRecoveryProbe.prepareIfRequested() {
            FileHandle.standardOutput.write(
                stateRecoveryProbe.observationResultLine(
                    sessions: initializedModel.runtimeChatSessions,
                    storeError: initializedModel.runtimeChatSessionsError
                )
            )
        }
        _model = StateObject(wrappedValue: initializedModel)
    }

    var body: some Scene {
        Window(NSLocalizedString("AetherLink", comment: ""), id: "main") {
            ContentView(
                model: model,
                requestedSection: $requestedSection,
                pairingFocusSequence: $pairingFocusSequence,
                pairingFocusIntent: $pairingFocusIntent
            )
                .environment(\.locale, Locale(identifier: currentAppLanguage.localeIdentifier))
                .id(currentAppLanguage.rawValue)
                .preferredColorScheme(currentAppAppearance.preferredColorScheme)
                .frame(minWidth: 860, minHeight: 560)
                .task {
                    appDelegate.installRuntimeLifecycleIfNeeded(model)
                    appDelegate.requestRuntimeStartForUserInterface()
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
            canRequestPairing: model.canRequestPairingForUserInterface
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

@MainActor
protocol RuntimeApplicationLifecycle: AnyObject {
    @discardableResult
    func requestStartForUserInterface(port: UInt16) -> Bool

    @discardableResult
    func suspendForSystemSleep() -> Bool

    @discardableResult
    func resumeAfterSystemWake() -> Bool

    func beginApplicationTermination()
    func drainApplicationTermination() async
    func stop()
}

extension RuntimeApplicationLifecycle {
    func beginApplicationTermination() {
        stop()
    }

    func drainApplicationTermination() async {}
}

extension CompanionAppModel: RuntimeApplicationLifecycle {}

private enum RuntimeApplicationTerminationRaceResult: Sendable {
    case drained
    case timedOut
}

private actor RuntimeApplicationTerminationRace {
    private var result: RuntimeApplicationTerminationRaceResult?
    private var continuation:
        CheckedContinuation<RuntimeApplicationTerminationRaceResult, Never>?

    func wait() async -> RuntimeApplicationTerminationRaceResult {
        if let result {
            return result
        }
        return await withCheckedContinuation { continuation in
            if let result {
                continuation.resume(returning: result)
            } else {
                self.continuation = continuation
            }
        }
    }

    func resolve(_ result: RuntimeApplicationTerminationRaceResult) {
        guard self.result == nil else { return }
        self.result = result
        let continuation = self.continuation
        self.continuation = nil
        continuation?.resume(returning: result)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    nonisolated static let defaultApplicationTerminationTimeoutNanoseconds:
        UInt64 = 5_000_000_000

    private let workspaceNotificationCenter: NotificationCenter
    private let applicationTerminationTimeoutNanoseconds: UInt64
    private let applicationTerminationSleeper:
        @Sendable (UInt64) async throws -> Void
    private let applicationTerminationReply: @MainActor (Bool) -> Void
    private weak var runtimeLifecycle: (any RuntimeApplicationLifecycle)?
    private var workspaceLifecycleObservers: [NSObjectProtocol] = []
    private var isSystemSleeping = false
    private var runtimeSuspendedForSystemSleep = false
    private var pendingRuntimeStartAfterSystemWake: UInt16?
    private var didHandleApplicationTermination = false
    private var didReplyToApplicationTermination = false
    private var applicationTerminationTask: Task<Void, Never>?

    override init() {
        workspaceNotificationCenter = NSWorkspace.shared.notificationCenter
        applicationTerminationTimeoutNanoseconds =
            Self.defaultApplicationTerminationTimeoutNanoseconds
        applicationTerminationSleeper = {
            try await Task.sleep(nanoseconds: $0)
        }
        applicationTerminationReply = {
            NSApp.reply(toApplicationShouldTerminate: $0)
        }
        super.init()
    }

    init(
        workspaceNotificationCenter: NotificationCenter,
        applicationTerminationTimeoutNanoseconds: UInt64 =
            AppDelegate.defaultApplicationTerminationTimeoutNanoseconds,
        applicationTerminationSleeper:
            @escaping @Sendable (UInt64) async throws -> Void = {
                try await Task.sleep(nanoseconds: $0)
            },
        applicationTerminationReply:
            @escaping @MainActor (Bool) -> Void = {
                NSApp.reply(toApplicationShouldTerminate: $0)
            }
    ) {
        self.workspaceNotificationCenter = workspaceNotificationCenter
        self.applicationTerminationTimeoutNanoseconds = max(
            1,
            applicationTerminationTimeoutNanoseconds
        )
        self.applicationTerminationSleeper = applicationTerminationSleeper
        self.applicationTerminationReply = applicationTerminationReply
        super.init()
    }

    func installRuntimeLifecycleIfNeeded(
        _ lifecycle: any RuntimeApplicationLifecycle
    ) {
        guard !didHandleApplicationTermination,
              runtimeLifecycle == nil else {
            return
        }
        runtimeLifecycle = lifecycle
    }

    @discardableResult
    func requestRuntimeStartForUserInterface(
        port: UInt16 = 43170
    ) -> Bool {
        guard !didHandleApplicationTermination,
              let runtimeLifecycle else {
            return false
        }
        guard !isSystemSleeping else {
            pendingRuntimeStartAfterSystemWake = port
            return false
        }
        pendingRuntimeStartAfterSystemWake = nil
        return runtimeLifecycle.requestStartForUserInterface(port: port)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        startObservingWorkspaceLifecycleIfNeeded()
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminate(
        _ sender: NSApplication
    ) -> NSApplication.TerminateReply {
        if didHandleApplicationTermination {
            return didReplyToApplicationTermination
                ? .terminateNow
                : .terminateLater
        }
        guard let runtimeLifecycle else {
            didHandleApplicationTermination = true
            stopObservingWorkspaceLifecycle()
            clearPendingRuntimeLifecycleState()
            return .terminateNow
        }

        didHandleApplicationTermination = true
        stopObservingWorkspaceLifecycle()
        clearPendingRuntimeLifecycleState()
        self.runtimeLifecycle = nil
        runtimeLifecycle.beginApplicationTermination()
        applicationTerminationTask = Task { [weak self, runtimeLifecycle] in
            guard let self else { return }
            await self.waitForApplicationTerminationDrainOrTimeout(
                runtimeLifecycle
            )
            guard !Task.isCancelled else { return }
            self.replyToApplicationTerminationIfNeeded()
        }
        return .terminateLater
    }

    func applicationWillTerminate(_ notification: Notification) {
        guard !didHandleApplicationTermination else { return }
        didHandleApplicationTermination = true
        stopObservingWorkspaceLifecycle()
        let lifecycle = runtimeLifecycle
        runtimeLifecycle = nil
        clearPendingRuntimeLifecycleState()
        lifecycle?.stop()
    }

    func startObservingWorkspaceLifecycleIfNeeded() {
        guard !didHandleApplicationTermination,
              workspaceLifecycleObservers.isEmpty else {
            return
        }
        let willSleepObserver = workspaceNotificationCenter.addObserver(
            forName: NSWorkspace.willSleepNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated {
                self?.handleWorkspaceWillSleep()
            }
        }
        let didWakeObserver = workspaceNotificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated {
                self?.handleWorkspaceDidWake()
            }
        }
        workspaceLifecycleObservers = [
            willSleepObserver,
            didWakeObserver,
        ]
    }

    private func stopObservingWorkspaceLifecycle() {
        for observer in workspaceLifecycleObservers {
            workspaceNotificationCenter.removeObserver(observer)
        }
        workspaceLifecycleObservers.removeAll()
    }

    private func clearPendingRuntimeLifecycleState() {
        pendingRuntimeStartAfterSystemWake = nil
        runtimeSuspendedForSystemSleep = false
        isSystemSleeping = false
    }

    private func waitForApplicationTerminationDrainOrTimeout(
        _ runtimeLifecycle: any RuntimeApplicationLifecycle
    ) async {
        let race = RuntimeApplicationTerminationRace()
        let drainTask = Task { @MainActor in
            await runtimeLifecycle.drainApplicationTermination()
            await race.resolve(.drained)
        }
        let timeoutNanoseconds = applicationTerminationTimeoutNanoseconds
        let sleeper = applicationTerminationSleeper
        let timeoutTask = Task {
            do {
                try await sleeper(timeoutNanoseconds)
                await race.resolve(.timedOut)
            } catch {
                if !Task.isCancelled {
                    await race.resolve(.timedOut)
                }
            }
        }
        switch await race.wait() {
        case .drained:
            timeoutTask.cancel()
        case .timedOut:
            drainTask.cancel()
        }
    }

    private func replyToApplicationTerminationIfNeeded() {
        guard !didReplyToApplicationTermination else { return }
        didReplyToApplicationTermination = true
        applicationTerminationTask = nil
        applicationTerminationReply(true)
    }

    private func handleWorkspaceWillSleep() {
        guard !didHandleApplicationTermination,
              !isSystemSleeping else {
            return
        }
        isSystemSleeping = true
        runtimeSuspendedForSystemSleep =
            runtimeLifecycle?.suspendForSystemSleep() == true
    }

    private func handleWorkspaceDidWake() {
        guard !didHandleApplicationTermination,
              isSystemSleeping else {
            return
        }
        isSystemSleeping = false
        if runtimeSuspendedForSystemSleep {
            runtimeSuspendedForSystemSleep = false
            pendingRuntimeStartAfterSystemWake = nil
            _ = runtimeLifecycle?.resumeAfterSystemWake()
            return
        }
        guard let pendingRuntimeStartAfterSystemWake else {
            return
        }
        self.pendingRuntimeStartAfterSystemWake = nil
        _ = runtimeLifecycle?.requestStartForUserInterface(
            port: pendingRuntimeStartAfterSystemWake
        )
    }
}
